"""Purpose: Pedigree breeding via flam3-genome (mutate / cross / interpolate; Phase 2 guide 07).

Requirements: flam3-genome binary; config paths (genomes_inbox, template); sheep_tax helpers.

Usage:
  python -m pipeline.breed --mutate PARENT.flam3
  python -m pipeline.breed --cross A.flam3 B.flam3 [--method alternate|union]
  python -m pipeline.breed --interpolate A.flam3 B.flam3

Assumptions: Children are named electricsheep.pedigree.* and staged to genomes_inbox with license sidecars.
  The worker copies lineage onto the catalog sidecar after a successful render and removes that inbox file.
  Quarantine, sheep tax, and refactor move the file with the genome. Startup reaps leftovers whose genome is already gone.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path
from pipeline.inbox_queue import stamp_inbox_arrival
from pipeline.license_filter import infer_tags_from_genome
from pipeline.sheep_tax import scan_file, tax_xml
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.breed")

CROSS_METHODS = frozenset({"alternate", "union", "interpolate"})

# Copied onto the catalog sidecar at ingest and kept across re-furnace.
# Not Phase 4 reserved keys; merge_reserved_sidecar_keys copies this list too.
PEDIGREE_LINEAGE_KEYS = (
    "origin",
    "method",
    "parents",
    "generation",
    "bred_at",
    "cross_method",
)
_SIDECAR_SUFFIX = ".jellyflam3.json"
_GENOME_SUFFIXES = (".flam3", ".flame")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def breed_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return the ``breed`` config section (empty dict if missing)."""
    return dict(cfg.get("breed") or {})


def pedigree_name(mode: str, short_id: str | None = None) -> str:
    """Filename for a new pedigree child (``electricsheep.pedigree.*``)."""
    from pipeline.sheep_names import pedigree_filename

    return pedigree_filename(mode, short_id)


def inherit_license_tags(parent_paths: list[Path]) -> list[str]:
    """Robot remix of human → NC; union tags from parents, force NC if any NC/human."""
    tags: set[str] = set()
    force_nc = False
    for p in parent_paths:
        pt = infer_tags_from_genome(p)
        tags.update(pt)
        if "cc-by-nc" in pt or "human" in pt:
            force_nc = True
    if force_nc:
        tags.discard("cc-by")
        tags.add("cc-by-nc")
        tags.add("brood")
    elif "cc-by" not in tags and "cc-by-nc" not in tags:
        tags.add("cc-by-nc")
        tags.add("brood")
    return sorted(tags)


def _multi_flame_policy(cfg: dict[str, Any]) -> str:
    bc = breed_cfg(cfg)
    if bc.get("multi_flame"):
        return str(bc["multi_flame"]).lower()
    st = cfg.get("sheep_tax") or {}
    return str(st.get("multi_flame") or "strip_to_first").lower()


def prepare_parent(path: Path, cfg: dict[str, Any], work: Path) -> Path:
    """Copy parent to work dir; sheep-tax + multi-flame policy. Returns prepared path."""
    if not path.is_file():
        raise FileNotFoundError(path)
    work.mkdir(parents=True, exist_ok=True)
    prepared = work / path.name
    shutil.copy2(path, prepared)

    bc = breed_cfg(cfg)
    tax_parents = bool(bc.get("tax_parents", True))
    policy = _multi_flame_policy(cfg)

    tax_opts = dict(cfg.get("sheep_tax") or {})
    tax_opts["enabled"] = True
    tax_opts["repair"] = True
    tax_opts["multi_flame"] = policy
    local_cfg = dict(cfg)
    local_cfg["sheep_tax"] = tax_opts

    if tax_parents:
        result = scan_file(prepared, local_cfg)
        if not result.get("ok"):
            codes = [i.get("code") for i in (result.get("issues") or [])]
            raise RuntimeError(f"parent sheep tax failed for {path.name}: {codes}")
    else:
        text = prepared.read_text(encoding="utf-8", errors="replace")
        result = tax_xml(text, local_cfg)
        if not result.get("ok"):
            raise RuntimeError(f"parent multi-flame policy failed for {path.name}")
        if result.get("changed") and result.get("xml"):
            prepared.write_text(result["xml"], encoding="utf-8")

    return prepared


def _run_flam3_genome(cfg: dict[str, Any], env_extra: dict[str, str], dest: Path) -> None:
    """Invoke flam3-genome with ``env_extra``; write stdout genome to ``dest``."""
    genome_bin = _tool(cfg, "flam3_genome")
    env = {**os.environ, **env_extra}
    template = resolve_path(cfg, "template")
    if template.is_file():
        env.setdefault("template", str(template))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as out:
        subprocess.run([genome_bin], check=True, stdout=out, env=env)
    if dest.stat().st_size < 32:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"{genome_bin} produced empty genome")


def write_pedigree_sidecar(
    flam3_path: Path,
    *,
    method: str,
    parents: list[Path],
    tags: list[str],
    cross_method: str | None = None,
    generation: int = 1,
) -> Path:
    """Write ``*.jellyflam3.json`` beside a bred genome; returns sidecar path."""
    sidecar = {
        "id": flam3_path.stem,
        "origin": "local_pedigree",
        "method": method,
        "parents": [str(p) for p in parents],
        "generation": generation,
        "license": "cc-by-nc"
        if "cc-by-nc" in tags
        else ("cc-by" if "cc-by" in tags else "unknown"),
        "tags": tags,
        "bred_at": _utc_now(),
    }
    if cross_method is not None:
        sidecar["cross_method"] = cross_method
    path = flam3_path.with_suffix(".jellyflam3.json")
    path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
    return path


def pedigree_sidecar_path(genome: Path) -> Path:
    """Breed sidecar beside a ``.flam3`` / ``.flame`` (last suffix replaced)."""
    return genome.with_suffix(_SIDECAR_SUFFIX)


def stem_from_pedigree_sidecar(path: Path) -> str:
    """Stem of ``{stem}.jellyflam3.json``. ``Path.stem`` would keep ``.jellyflam3``."""
    name = path.name
    if name.lower().endswith(_SIDECAR_SUFFIX):
        return name[: -len(_SIDECAR_SUFFIX)]
    return path.stem


def read_pedigree_sidecar(path: Path) -> dict[str, Any] | None:
    """Return the JSON object when ``path`` is a local pedigree record."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("pedigree sidecar read failed for %s: %s", path, exc)
        return None
    if not isinstance(data, dict):
        return None
    if data.get("origin") == "local_pedigree":
        return data
    parents = data.get("parents")
    if isinstance(parents, list) and parents and data.get("method"):
        return data
    return None


def path_is_under(path: Path, root: Path) -> bool:
    """True when ``path`` is ``root`` or a file inside it."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def locate_pedigree_sidecar(genome: Path, *extra_dirs: Path) -> Path | None:
    """Breed sidecar beside ``genome``, or the same filename under ``extra_dirs``."""
    candidates: list[Path] = [pedigree_sidecar_path(genome)]
    sidecar_name = pedigree_sidecar_path(Path(genome.name)).name
    for directory in extra_dirs:
        candidates.append(Path(directory) / sidecar_name)
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        if read_pedigree_sidecar(candidate) is not None:
            return candidate
    return None


def merge_pedigree_lineage(
    catalog: dict[str, Any], breed: dict[str, Any]
) -> dict[str, Any]:
    """Copy lineage keys onto ``catalog``. Values already set on ``catalog`` stay."""
    for key in PEDIGREE_LINEAGE_KEYS:
        if key not in breed:
            continue
        current = catalog.get(key)
        if current not in (None, "", []):
            continue
        catalog[key] = breed[key]
    return catalog


def adopt_pedigree_lineage(
    catalog: dict[str, Any], genome: Path, *extra_dirs: Path
) -> Path | None:
    """Merge a breed sidecar into ``catalog``. Does not delete the file.

    Caller writes the catalog sidecar first, then ``release_pedigree_sidecar``.
    """
    side = locate_pedigree_sidecar(genome, *extra_dirs)
    if side is None:
        return None
    data = read_pedigree_sidecar(side)
    if data:
        merge_pedigree_lineage(catalog, data)
    return side


def release_pedigree_sidecar(side: Path | None, *roots: Path) -> bool:
    """Unlink a breed sidecar that lives under one of ``roots``.

    Sidecars outside those roots (git ``genomes/pedigree``) stay on disk.
    """
    if side is None or not side.is_file():
        return False
    if not roots or not any(path_is_under(side, root) for root in roots):
        log.info("left pedigree sidecar outside runtime roots: %s", side)
        return False
    try:
        side.unlink()
    except OSError as exc:
        log.warning("could not remove pedigree sidecar %s: %s", side, exc)
        return False
    log.info("removed pedigree sidecar %s", side)
    return True


def move_pedigree_sidecar(side: Path, dest_genome: Path) -> Path | None:
    """Move ``side`` so it sits beside ``dest_genome``."""
    dest = pedigree_sidecar_path(dest_genome)
    try:
        if side.resolve() == dest.resolve():
            return dest
    except OSError:
        pass
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        try:
            dest.unlink()
        except OSError as exc:
            log.warning("could not replace pedigree sidecar %s: %s", dest, exc)
            return None
    try:
        shutil.move(str(side), str(dest))
    except OSError as exc:
        log.warning(
            "could not move pedigree sidecar %s -> %s: %s", side, dest, exc
        )
        return None
    log.info("moved pedigree sidecar %s -> %s", side.name, dest)
    return dest


def take_pedigree_sidecar(src_genome: Path, dest_genome: Path) -> Path | None:
    """Move the breed sidecar beside ``src_genome`` so it travels with a claim."""
    side = locate_pedigree_sidecar(src_genome)
    if side is None:
        return None
    return move_pedigree_sidecar(side, dest_genome)


def park_pedigree_sidecar(
    src_genome: Path, dest_genome: Path, *extra_dirs: Path
) -> Path | None:
    """Move a breed sidecar so it sits beside a quarantined or requeued genome."""
    side = locate_pedigree_sidecar(src_genome, *extra_dirs)
    if side is None:
        return None
    return move_pedigree_sidecar(side, dest_genome)


def _genome_in_dir(directory: Path, stem: str) -> Path | None:
    """Exact ``stem.flam3`` / ``.flame``, or the only ``stem.<token>.flam3`` copy."""
    if not directory.is_dir():
        return None
    exact: list[Path] = []
    prefixed: list[Path] = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return None
    for entry in entries:
        if not entry.is_file() or entry.suffix.lower() not in _GENOME_SUFFIXES:
            continue
        if entry.stem == stem:
            exact.append(entry)
        elif entry.stem.startswith(stem + "."):
            prefixed.append(entry)
    if exact:
        return sorted(exact)[0]
    if len(prefixed) == 1:
        return prefixed[0]
    return None


def _inbox_has_genome(inbox: Path, stem: str) -> bool:
    return any((inbox / f"{stem}{suffix}").is_file() for suffix in _GENOME_SUFFIXES)


def _catalog_mp4_for_stem(cfg: dict[str, Any], stem: str) -> Path | None:
    from pipeline.sheep_names import catalog_generation, normalize_stem

    base = normalize_stem(stem)
    try:
        media = resolve_path(cfg, "media_library")
    except Exception:  # noqa: BLE001
        return None
    path = media / "by-generation" / catalog_generation(base) / f"{base}.mp4"
    return path if path.is_file() else None


def _write_lineage_onto_catalog(mp4: Path, breed: dict[str, Any]) -> None:
    from pipeline.media_layout import ensure_catalog_file_mode
    from pipeline.stills import load_sidecar, sidecar_path_for_mp4, write_sidecar

    catalog = load_sidecar(mp4)
    merge_pedigree_lineage(catalog, breed)
    write_sidecar(mp4, catalog)
    ensure_catalog_file_mode(sidecar_path_for_mp4(mp4))


def _reap_one(
    cfg: dict[str, Any],
    side: Path,
    stem: str,
    breed: dict[str, Any],
    *,
    done: Path,
    quarantine: Path,
) -> bool:
    """Publish lineage onto the catalog, or park the file with the genome."""
    mp4 = _catalog_mp4_for_stem(cfg, stem)
    if mp4 is not None:
        _write_lineage_onto_catalog(mp4, breed)
        return release_pedigree_sidecar(side, side.parent)
    for pool in (quarantine, done):
        genome = _genome_in_dir(pool, stem)
        if genome is not None:
            return move_pedigree_sidecar(side, genome) is not None
    return move_pedigree_sidecar(side, quarantine / f"{stem}.flam3") is not None


def reap_orphaned_pedigree_sidecars(cfg: dict[str, Any]) -> int:
    """Settle inbox breed sidecars whose ``.flam3`` / ``.flame`` is already gone.

    A sidecar beside a genome still waiting in the inbox is left alone.
    """
    try:
        inbox = resolve_path(cfg, "genomes_inbox")
    except Exception as exc:  # noqa: BLE001
        log.warning("pedigree sidecar reap skipped: %s", exc)
        return 0
    if not inbox.is_dir():
        return 0
    try:
        from pipeline.worker import genomes_done_dir

        done = genomes_done_dir(cfg)
    except Exception:  # noqa: BLE001
        done = inbox.parent / "done"
    try:
        quarantine = resolve_path(cfg, "genomes_quarantine")
    except Exception:  # noqa: BLE001
        quarantine = inbox.parent / "quarantine"
    settled = 0
    for side in sorted(inbox.glob("*.jellyflam3.json")):
        breed = read_pedigree_sidecar(side)
        if breed is None:
            continue
        stem = stem_from_pedigree_sidecar(side)
        if _inbox_has_genome(inbox, stem):
            continue
        try:
            if _reap_one(cfg, side, stem, breed, done=done, quarantine=quarantine):
                settled += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("pedigree sidecar reap failed for %s: %s", side.name, exc)
    if settled:
        log.info("reaped %s orphaned pedigree sidecar(s) from %s", settled, inbox)
    return settled


def settle_pedigree_after_recovery(
    *,
    catalog_mp4: Path | None,
    job_src: Path | None,
    job_dir: Path,
    inbox: Path,
    requeued_flam3: Path | None,
    quarantine: Path | None,
) -> None:
    """Put a claimed breed sidecar back on a requeued genome, or onto the catalog.

    A sidecar that still sits beside an inbox genome is left there.
    """
    # Only sidecars that traveled with a claim (job dir) or still sit in the inbox.
    # A manual sample or git pedigree file is not a runtime leftover.
    anchor = job_dir / "missing.flam3"
    if job_src is not None and (
        path_is_under(job_src, job_dir) or path_is_under(job_src, inbox)
    ):
        anchor = job_src
    side = locate_pedigree_sidecar(anchor, job_dir, inbox)
    if side is None:
        return
    if requeued_flam3 is not None:
        move_pedigree_sidecar(side, requeued_flam3)
        return
    stem = stem_from_pedigree_sidecar(side)
    if _inbox_has_genome(inbox, stem):
        if path_is_under(side, inbox):
            return
        genome = _genome_in_dir(inbox, stem)
        if genome is not None:
            move_pedigree_sidecar(side, genome)
            return
    if catalog_mp4 is not None and catalog_mp4.is_file():
        breed = read_pedigree_sidecar(side)
        if breed:
            _write_lineage_onto_catalog(catalog_mp4, breed)
        release_pedigree_sidecar(side, job_dir, inbox)
        return
    # Recovery left the genome in the job dir. Keep the sidecar beside it.
    if job_src is not None and job_src.is_file() and path_is_under(side, job_src.parent):
        return
    if quarantine is not None:
        move_pedigree_sidecar(side, quarantine / f"{stem}.flam3")


def breed_mutate(
    cfg: dict[str, Any],
    parent: Path,
    *,
    count: int = 1,
    dry_run: bool = False,
) -> list[Path]:
    """Mutate ``parent`` into ``count`` children staged in genomes_inbox."""
    inbox = resolve_path(cfg, "genomes_inbox")
    staged: list[Path] = []
    for _ in range(max(1, count)):
        name = pedigree_name("mutate")
        dest = inbox / name
        if dry_run:
            log.info("dry-run would mutate %s -> %s", parent, dest)
            staged.append(dest)
            continue
        with tempfile.TemporaryDirectory(prefix="jellyflam3-breed-") as tmp:
            work = Path(tmp)
            prep = prepare_parent(parent, cfg, work)
            child = work / name
            _run_flam3_genome(cfg, {"mutate": str(prep)}, child)
            inbox.mkdir(parents=True, exist_ok=True)
            shutil.move(str(child), str(dest))
            stamp_inbox_arrival(dest)
            tags = inherit_license_tags([parent])
            write_pedigree_sidecar(
                dest, method="mutate", parents=[parent.resolve()], tags=tags
            )
            log.info("bred mutate %s -> %s", parent.name, dest)
            staged.append(dest)
    return staged


def breed_cross(
    cfg: dict[str, Any],
    parent_a: Path,
    parent_b: Path,
    *,
    method: str = "alternate",
    mode_label: str | None = None,
    dry_run: bool = False,
) -> Path:
    """Genetic cross of two parents. ``method`` is flam3 cross method."""
    method = method.lower()
    if method not in CROSS_METHODS:
        raise ValueError(
            f"unsupported cross method {method!r}; use {sorted(CROSS_METHODS)}"
        )
    # CLI mode name: interpolate stays "interpolate"; alternate/union → "cross"
    label = mode_label or ("interpolate" if method == "interpolate" else "cross")
    inbox = resolve_path(cfg, "genomes_inbox")
    name = pedigree_name(label)
    dest = inbox / name
    if dry_run:
        log.info(
            "dry-run would cross %s x %s method=%s -> %s",
            parent_a,
            parent_b,
            method,
            dest,
        )
        return dest

    with tempfile.TemporaryDirectory(prefix="jellyflam3-breed-") as tmp:
        work = Path(tmp)
        dir_a = work / "a"
        dir_b = work / "b"
        dir_a.mkdir()
        dir_b.mkdir()
        prep_a = prepare_parent(parent_a, cfg, dir_a)
        prep_b = prepare_parent(parent_b, cfg, dir_b)
        child = work / name
        _run_flam3_genome(
            cfg,
            {
                "cross0": str(prep_a),
                "cross1": str(prep_b),
                "method": method,
            },
            child,
        )
        inbox.mkdir(parents=True, exist_ok=True)
        shutil.move(str(child), str(dest))
        stamp_inbox_arrival(dest)
        tags = inherit_license_tags([parent_a, parent_b])
        write_pedigree_sidecar(
            dest,
            method=label,
            parents=[parent_a.resolve(), parent_b.resolve()],
            tags=tags,
            cross_method=method,
        )
        log.info(
            "bred %s %s x %s method=%s -> %s",
            label,
            parent_a.name,
            parent_b.name,
            method,
            dest,
        )
    return dest


def main(argv: list[str] | None = None) -> int:
    """CLI: mutate / cross parents into pedigreed inbox genomes."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--config", default="configs/jellyflam3.yaml")

    ap = argparse.ArgumentParser(
        description="JellyFlam3 pedigree breed - mutate / cross / interpolate (guide 07)",
        parents=[parent],
    )
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--mutate",
        type=Path,
        metavar="PARENT",
        help="Mutate one parent genome",
    )
    mode.add_argument(
        "--cross",
        nargs=2,
        type=Path,
        metavar=("PARENT_A", "PARENT_B"),
        help="Genetic cross of two parents (default method=alternate)",
    )
    mode.add_argument(
        "--interpolate",
        nargs=2,
        type=Path,
        metavar=("PARENT_A", "PARENT_B"),
        help="Two-parent interpolate (flam3 method=interpolate)",
    )
    ap.add_argument(
        "--method",
        choices=sorted(m for m in CROSS_METHODS if m != "interpolate"),
        default=None,
        help="With --cross: flam3 method (default: alternate, or breed.default_cross_method)",
    )
    ap.add_argument(
        "--count", type=int, default=1, help="With --mutate: number of children"
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    bc = breed_cfg(cfg)

    if args.mutate is not None:
        paths = breed_mutate(
            cfg, args.mutate, count=max(1, int(args.count)), dry_run=args.dry_run
        )
        for p in paths:
            print(p)
        return 0

    if args.cross is not None:
        method = args.method or str(bc.get("default_cross_method") or "alternate")
        dest = breed_cross(
            cfg,
            args.cross[0],
            args.cross[1],
            method=method,
            mode_label="cross",
            dry_run=args.dry_run,
        )
        print(dest)
        return 0

    if args.interpolate is not None:
        dest = breed_cross(
            cfg,
            args.interpolate[0],
            args.interpolate[1],
            method="interpolate",
            mode_label="interpolate",
            dry_run=args.dry_run,
        )
        print(dest)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
