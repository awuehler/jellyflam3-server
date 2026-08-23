"""Purpose: Pedigree breeding via flam3-genome (mutate / cross / interpolate; Phase 2 guide 07).

Requirements: flam3-genome binary; config paths (genomes_inbox, template); sheep_tax helpers.

Usage:
  python -m pipeline.breed --mutate PARENT.flam3
  python -m pipeline.breed --cross A.flam3 B.flam3 [--method alternate|union]
  python -m pipeline.breed --interpolate A.flam3 B.flam3

Assumptions: Children are named electricsheep.pedigree.* and staged to genomes_inbox with license sidecars.
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
from pipeline.license_filter import infer_tags_from_genome
from pipeline.sheep_tax import scan_file, tax_xml
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.breed")

CROSS_METHODS = frozenset({"alternate", "union", "interpolate"})


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
