"""Purpose: Sheep Shears — curator add / modify / delete with cascade (Phase 3 guide 03).

Requirements: Config paths (inbox, quarantine, done, jobs, frames, media_library);
optional peering peers dirs; in-repo ``genomes/samples`` + ``genomes/pedigree``;
optional Jellyfin for item lookup/delete.

Usage:
  python -m pipeline.shears delete electricsheep.247.00505
  python -m pipeline.shears delete electricsheep.247.00505 --confirm DELETE
  python -m pipeline.shears add path/to/sheep.flam3 [--force] [--move]
  # add copies by default (leaves source); --move relocates instead
  python -m pipeline.shears modify path/to/sheep.flam3   # re-stage to inbox
  python -m pipeline.shears audit
  python -m pipeline.shears sweep --orphans-only          # dry-run
  python -m pipeline.shears sweep --orphans-only --confirm DELETE

Assumptions: Default delete is dry-run. Never touches secrets.env, jellyflam3.yaml,
or Syncthing/Tailscale device config. Edges/stills cascade stubs until guides 01/04.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path
from pipeline.sheep_names import catalog_generation, normalize_stem, stem_of

log = logging.getLogger("jellyflam3.shears")

CONFIRM_TOKEN = "DELETE"


@dataclass
class CascadeReport:
    """Paths and notes for one sheep cascade (dry-run or apply)."""

    base: str
    genomes: list[Path] = field(default_factory=list)
    catalog: list[Path] = field(default_factory=list)
    jobs: list[Path] = field(default_factory=list)
    frames: list[Path] = field(default_factory=list)
    peers: list[Path] = field(default_factory=list)
    edges: list[Path] = field(default_factory=list)
    stills: list[Path] = field(default_factory=list)
    jellyfin_item_id: str | None = None
    jellyfin_name: str | None = None
    orphan_warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def all_paths(self) -> list[Path]:
        """Filesystem paths that would be removed (jobs = job dirs)."""
        return [
            *self.genomes,
            *self.catalog,
            *self.jobs,
            *self.frames,
            *self.peers,
            *self.edges,
            *self.stills,
        ]

    def to_dict(self) -> dict[str, Any]:
        def _p(paths: list[Path]) -> list[str]:
            return [str(p) for p in paths]

        return {
            "base": self.base,
            "genomes": _p(self.genomes),
            "catalog": _p(self.catalog),
            "jobs": _p(self.jobs),
            "frames": _p(self.frames),
            "peers": _p(self.peers),
            "edges": _p(self.edges),
            "stills": _p(self.stills),
            "jellyfin_item_id": self.jellyfin_item_id,
            "jellyfin_name": self.jellyfin_name,
            "orphan_warnings": list(self.orphan_warnings),
            "notes": list(self.notes),
        }


def resolve_sheep_base(target: str | Path) -> str:
    """Normalize operator target (stem, .flam3, MP4, or poster) to electricsheep stem."""
    p = Path(target)
    name = p.name
    lower = name.lower()
    if lower.endswith("-poster.jpg") or lower.endswith("-poster.jpeg"):
        # electricsheep.247.00505-poster.jpg → electricsheep.247.00505
        stem = name[: name.lower().rfind("-poster")]
        return normalize_stem(stem)
    if lower.endswith(".mp4"):
        return normalize_stem(p.stem)
    if lower.endswith((".flam3", ".flame")):
        return normalize_stem(p.stem)
    if lower.endswith(".jellyflam3.json"):
        return normalize_stem(name[: -len(".jellyflam3.json")])
    return normalize_stem(stem_of(name))


def _flam3_names(base: str) -> list[str]:
    """Candidate .flam3 basenames (canonical + legacy jellyflam3 prefix)."""
    names = [f"{base}.flam3"]
    if base.startswith("electricsheep."):
        legacy = "jellyflam3." + base[len("electricsheep.") :]
        names.append(f"{legacy}.flam3")
    return names


def _path_refers_to_base(path: Path | str, base: str) -> bool:
    """True when ``path`` is this sheep Id (exact stem / token), not a substring hit.

    Accepts ``{base}``, ``{base}.ext``, ``{base}-poster.*`` — rejects longer Ids that
    merely contain ``base`` as a prefix (e.g. ``…005050`` vs ``…00505``).
    """
    name = Path(path).name
    if name == base:
        return True
    if name.startswith(f"{base}.") or name.startswith(f"{base}-"):
        return True
    lower = name.lower()
    if lower.endswith(".jellyflam3.json"):
        return name[: -len(".jellyflam3.json")] == base
    if lower.endswith("-poster.jpg") or lower.endswith("-poster.jpeg"):
        return name[: lower.rfind("-poster")] == base
    return Path(name).stem == base


def _id_equals_base(raw: str, base: str) -> bool:
    """Exact sheep-Id equality after normalize (no substring)."""
    s = str(raw or "").strip()
    if not s:
        return False
    if s == base:
        return True
    try:
        return normalize_stem(stem_of(s)) == normalize_stem(base)
    except Exception:  # noqa: BLE001
        return False


def _repo_root(cfg: dict[str, Any]) -> Path:
    raw = cfg.get("_repo_root")
    if raw:
        return Path(str(raw))
    return Path(__file__).resolve().parents[1]


def _git_genome_dirs(cfg: dict[str, Any]) -> list[Path]:
    """In-repo feedstock trees: ``genomes/samples`` + ``genomes/pedigree``."""
    root = _repo_root(cfg)
    return [root / "genomes" / "samples", root / "genomes" / "pedigree"]


def _collect_named(dir_path: Path, base: str) -> list[Path]:
    """Files in ``dir_path`` matching sheep basename (+ sidecar / poster companions)."""
    if not dir_path.is_dir():
        return []
    found: list[Path] = []
    for flam3 in _flam3_names(base):
        stem = Path(flam3).stem
        for name in (
            flam3,
            f"{stem}.jellyflam3.json",
            f"{stem}-poster.jpg",
        ):
            p = dir_path / name
            if p.is_file():
                found.append(p)
    return found


def _collect_named_under(root: Path, base: str) -> list[Path]:
    """Recursive match under ``root`` (for ``genomes/samples`` / ``genomes/pedigree`` trees)."""
    if not root.is_dir():
        return []
    want: set[str] = set()
    for flam3 in _flam3_names(base):
        stem = Path(flam3).stem
        want.update({flam3, f"{stem}.jellyflam3.json", f"{stem}-poster.jpg"})
    return sorted(p for p in root.rglob("*") if p.is_file() and p.name in want)


def _runtime_genome_dirs(cfg: dict[str, Any]) -> list[Path]:
    """Inbox / quarantine / done (flat runtime pools)."""
    dirs: list[Path] = []
    for key in ("genomes_inbox", "genomes_quarantine"):
        try:
            dirs.append(resolve_path(cfg, key))
        except Exception:  # noqa: BLE001
            continue
    from pipeline.worker import genomes_done_dir

    dirs.append(genomes_done_dir(cfg))
    return dirs


def _catalog_paths(cfg: dict[str, Any], base: str) -> list[Path]:
    media = resolve_path(cfg, "media_library")
    gen = catalog_generation(base)
    folder = media / "by-generation" / gen
    out: list[Path] = []
    for name in (
        f"{base}.mp4",
        f"{base}.jellyflam3.json",
        f"{base}-poster.jpg",
    ):
        p = folder / name
        if p.is_file():
            out.append(p)
    # Legacy jellyflam3 catalog stem
    if base.startswith("electricsheep."):
        legacy = "jellyflam3." + base[len("electricsheep.") :]
        for name in (
            f"{legacy}.mp4",
            f"{legacy}.jellyflam3.json",
            f"{legacy}-poster.jpg",
        ):
            p = folder / name
            if p.is_file() and p not in out:
                out.append(p)
    return out


def _job_and_frame_paths(cfg: dict[str, Any], base: str) -> tuple[list[Path], list[Path]]:
    from pipeline.job_recovery import list_jobs, sheep_basename_from_src

    jobs_dir = resolve_path(cfg, "jobs_dir")
    frames_root = resolve_path(cfg, "frames_scratch")
    job_dirs: list[Path] = []
    frame_dirs: list[Path] = []
    for job in list_jobs(jobs_dir):
        job_base = sheep_basename_from_src(job.src)
        if job_base != base:
            continue
        job_dirs.append(job.path.parent)
        frames = frames_root / job.job_id
        if frames.is_dir():
            frame_dirs.append(frames)
    return job_dirs, frame_dirs


def _peer_paths(cfg: dict[str, Any], base: str) -> list[Path]:
    from pipeline.peering import is_opted_in, peers_inbox, peers_root

    if not is_opted_in(cfg):
        return []
    root = peers_root(cfg)
    dirs = [
        peers_inbox(cfg),
        root / "share-out",
        root / "quarantine",
    ]
    found: list[Path] = []
    for d in dirs:
        found.extend(_collect_named(d, base))
    return found


def _edge_paths(cfg: dict[str, Any], base: str) -> list[Path]:
    """Best-effort edge MP4s / sidecars that name this sheep (Phase 4 edges layout)."""
    media = resolve_path(cfg, "media_library")
    if not media.is_dir():
        return []
    found: list[Path] = []
    # …/by-generation/*/edges/*
    for edges_dir in media.glob("by-generation/*/edges"):
        if not edges_dir.is_dir():
            continue
        for p in edges_dir.iterdir():
            if not p.is_file():
                continue
            if _path_refers_to_base(p, base):
                found.append(p)
                continue
            if p.suffix.lower() == ".json":
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                from_id = str(data.get("from_id") or "")
                to_id = str(data.get("to_id") or "")
                if _id_equals_base(from_id, base) or _id_equals_base(to_id, base):
                    found.append(p)
                    mp4 = p.with_suffix(".mp4")
                    if mp4.is_file() and mp4 not in found:
                        found.append(mp4)
    return found


def _stills_paths(cfg: dict[str, Any], base: str) -> list[Path]:
    media = resolve_path(cfg, "media_library")
    gen = catalog_generation(base)
    stills_dir = media / "by-generation" / gen / "stills" / base
    if stills_dir.is_dir():
        return [stills_dir]
    # Flat stills next to catalog
    flat = media / "by-generation" / gen / "stills"
    if not flat.is_dir():
        return []
    return [p for p in flat.iterdir() if p.is_file() and _path_refers_to_base(p, base)]


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _parents_reference_base(data: dict[str, Any], base: str) -> bool:
    parents = data.get("parents")
    if not isinstance(parents, list):
        return False
    for raw in parents:
        s = str(raw)
        try:
            stem = normalize_stem(Path(s).name)
        except Exception:  # noqa: BLE001
            stem = normalize_stem(s)
        if stem == base or _id_equals_base(s, base):
            return True
    return False


def find_pedigree_orphan_warnings(cfg: dict[str, Any], base: str) -> list[str]:
    """Warn when other genomes/sidecars list this sheep as a parent."""
    warnings: list[str] = []
    roots: list[Path] = list(_runtime_genome_dirs(cfg))
    roots.extend(_git_genome_dirs(cfg))
    media = resolve_path(cfg, "media_library")
    if media.is_dir():
        roots.append(media)

    seen: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for side in root.rglob("*.jellyflam3.json"):
            if side.stem == base or side.name.startswith(f"{base}."):
                continue
            data = _load_json(side)
            if not data or not _parents_reference_base(data, base):
                continue
            child = data.get("id") or side.stem
            key = str(side)
            if key in seen:
                continue
            seen.add(key)
            warnings.append(
                f"living child references parent {base}: {child} ({side})"
            )
    return warnings


def _jellyfin_lookup(
    cfg: dict[str, Any], catalog: list[Path]
) -> tuple[str | None, str | None, list[str]]:
    notes: list[str] = []
    mp4s = [p for p in catalog if p.suffix.lower() == ".mp4"]
    if not mp4s:
        return None, None, notes
    try:
        from pipeline.jellyfin_client import JellyfinClient

        client = JellyfinClient.from_config(cfg)
    except Exception as exc:  # noqa: BLE001
        notes.append(f"jellyfin lookup skipped: {exc}")
        return None, None, notes
    if not client.api_key:
        notes.append("jellyfin lookup skipped: no api_key")
        return None, None, notes
    try:
        item = client.find_item_for_media(mp4s[0])
    except Exception as exc:  # noqa: BLE001
        notes.append(f"jellyfin lookup failed: {exc}")
        return None, None, notes
    if not item:
        notes.append("jellyfin: no matching item")
        return None, None, notes
    item_id = str(item.get("Id") or "") or None
    name = str(item.get("Name") or "") or None
    return item_id, name, notes


def discover_cascade(cfg: dict[str, Any], target: str | Path) -> CascadeReport:
    """Build a cascade report for ``target`` (dry-run friendly; no deletes)."""
    base = resolve_sheep_base(target)
    report = CascadeReport(base=base)

    for d in _runtime_genome_dirs(cfg):
        report.genomes.extend(_collect_named(d, base))
    for d in _git_genome_dirs(cfg):
        report.genomes.extend(_collect_named_under(d, base))

    report.catalog = _catalog_paths(cfg, base)
    report.jobs, report.frames = _job_and_frame_paths(cfg, base)
    report.peers = _peer_paths(cfg, base)
    report.edges = _edge_paths(cfg, base)
    report.stills = _stills_paths(cfg, base)
    report.orphan_warnings = find_pedigree_orphan_warnings(cfg, base)

    if not report.edges:
        report.notes.append("edges: none matched (Phase 4 edges layout optional)")
    if not report.stills:
        report.notes.append("stills: none matched (guide 01 layout optional)")

    item_id, name, jf_notes = _jellyfin_lookup(cfg, report.catalog)
    report.jellyfin_item_id = item_id
    report.jellyfin_name = name
    report.notes.extend(jf_notes)

    # Deduplicate paths while preserving order
    def _dedupe(paths: list[Path]) -> list[Path]:
        seen: set[Path] = set()
        out: list[Path] = []
        for p in paths:
            try:
                key = p.resolve()
            except OSError:
                key = p
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return out

    report.genomes = _dedupe(report.genomes)
    report.catalog = _dedupe(report.catalog)
    report.jobs = _dedupe(report.jobs)
    report.frames = _dedupe(report.frames)
    report.peers = _dedupe(report.peers)
    report.edges = _dedupe(report.edges)
    report.stills = _dedupe(report.stills)
    return report


def print_report(report: CascadeReport, *, dry_run: bool) -> None:
    """Human-readable cascade listing for operators."""
    mode = "DRY-RUN (no deletes)" if dry_run else "APPLY"
    print(f"=== Sheep Shears delete — {mode} ===")
    print(f"base={report.base}")
    for label, paths in (
        ("genomes", report.genomes),
        ("catalog", report.catalog),
        ("jobs", report.jobs),
        ("frames", report.frames),
        ("peers", report.peers),
        ("edges", report.edges),
        ("stills", report.stills),
    ):
        print(f"\n[{label}] ({len(paths)})")
        for p in paths:
            print(f"  {p}")
        if not paths:
            print("  (none)")
    print("\n[jellyfin]")
    if report.jellyfin_item_id:
        print(f"  itemId={report.jellyfin_item_id}  name={report.jellyfin_name}")
    else:
        print("  (none)")
    if report.orphan_warnings:
        print("\n[pedigree orphan warnings]")
        for w in report.orphan_warnings:
            print(f"  WARN: {w}")
    if report.notes:
        print("\n[notes]")
        for n in report.notes:
            print(f"  {n}")
    if dry_run:
        print(
            f"\nRe-run with --confirm {CONFIRM_TOKEN} to remove the cascade set "
            "(never secrets / Syncthing config)."
        )


def _remove_path(path: Path, *, dry_run: bool) -> None:
    if dry_run:
        log.info("dry-run would remove %s", path)
        return
    if path.is_dir():
        shutil.rmtree(path)
        log.info("removed dir %s", path)
    elif path.is_file():
        path.unlink()
        log.info("removed file %s", path)
    else:
        log.info("skip missing %s", path)


def apply_delete(
    cfg: dict[str, Any],
    report: CascadeReport,
    *,
    dry_run: bool,
    refresh_jellyfin: bool = True,
) -> CascadeReport:
    """Remove cascade filesystem paths; optionally delete Jellyfin item + refresh."""
    for p in report.all_paths():
        _remove_path(p, dry_run=dry_run)

    if report.jellyfin_item_id and not dry_run:
        try:
            from pipeline.jellyfin_client import JellyfinClient

            client = JellyfinClient.from_config(cfg)
            client.delete_item(report.jellyfin_item_id)
            log.info("deleted Jellyfin item %s", report.jellyfin_item_id)
            if refresh_jellyfin:
                client.refresh_library()
        except Exception as exc:  # noqa: BLE001
            msg = f"jellyfin delete/refresh soft-fail: {exc}"
            log.warning(msg)
            report.notes.append(msg)
    elif report.jellyfin_item_id and dry_run:
        log.info("dry-run would delete Jellyfin item %s", report.jellyfin_item_id)

    return report


def shears_add(
    cfg: dict[str, Any],
    src: Path,
    *,
    dry_run: bool = False,
    force: bool = False,
    move: bool = False,
) -> Path | None:
    """Stage a genome into the worker inbox (Shears add)."""
    from pipeline.seed_inbox import stage_file

    inbox = resolve_path(cfg, "genomes_inbox")
    return stage_file(src, inbox, dry_run=dry_run, force=force, move=move)


def shears_modify(
    cfg: dict[str, Any],
    src: Path,
    *,
    dry_run: bool = False,
    force: bool = True,
) -> Path | None:
    """Re-stage ``src`` into inbox for re-furnace (TV-port/encode on next worker pick).

    Poster/sidecar refresh after render: ``python -m pipeline.backfill_posters``.
    Full in-place catalog replace without re-queue is deferred.
    """
    if not src.is_file():
        raise FileNotFoundError(src)
    return shears_add(cfg, src, dry_run=dry_run, force=force, move=False)


def _known_flam3_bases(cfg: dict[str, Any]) -> set[str]:
    """Stems that have a ``.flam3`` under runtime or git genome trees."""
    bases: set[str] = set()
    for d in _runtime_genome_dirs(cfg):
        if not d.is_dir():
            continue
        for p in d.glob("*.flam3"):
            bases.add(resolve_sheep_base(p))
    for d in _git_genome_dirs(cfg):
        if not d.is_dir():
            continue
        for p in d.rglob("*.flam3"):
            bases.add(resolve_sheep_base(p))
    return bases


def _iter_catalog_media(cfg: dict[str, Any]) -> dict[str, dict[str, list[Path]]]:
    """Map sheep base → catalog mp4 / poster / sidecar paths under media_library."""
    media = resolve_path(cfg, "media_library")
    by: dict[str, dict[str, list[Path]]] = {}
    if not media.is_dir():
        return by
    for p in media.rglob("*"):
        if not p.is_file():
            continue
        lower = p.name.lower()
        kind: str | None = None
        if p.suffix.lower() == ".mp4":
            kind = "mp4"
        elif "-poster.jpg" in lower or "-poster.jpeg" in lower:
            kind = "poster"
        elif lower.endswith(".jellyflam3.json"):
            kind = "sidecar"
        else:
            continue
        try:
            base = resolve_sheep_base(p)
        except Exception:  # noqa: BLE001
            continue
        slot = by.setdefault(base, {"mp4": [], "poster": [], "sidecar": []})
        slot[kind].append(p)
    return by


def list_peer_junk(cfg: dict[str, Any]) -> list[Path]:
    """Unexpected ``*.mp4`` under peers inbox/share-out/quarantine (peering is flam3-first)."""
    from pipeline.peering import list_peer_junk_files

    return list_peer_junk_files(cfg)


@dataclass
class FlockAudit:
    """Catalog / genome / peer hygiene report for ``audit`` / ``sweep``."""

    sheep: dict[str, dict[str, list[Path]]] = field(default_factory=dict)
    has_genome: dict[str, bool] = field(default_factory=dict)
    catalog_without_genome: list[str] = field(default_factory=list)
    missing_poster: list[str] = field(default_factory=list)
    missing_sidecar: list[str] = field(default_factory=list)
    orphan_poster: list[str] = field(default_factory=list)
    orphan_sidecar: list[str] = field(default_factory=list)
    peer_junk: list[Path] = field(default_factory=list)
    pedigree_warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def orphan_bases(self) -> list[str]:
        """Bases safe to Shears-delete as catalog orphans (no genome, or media without mp4)."""
        bases = set(self.catalog_without_genome)
        bases.update(self.orphan_poster)
        bases.update(self.orphan_sidecar)
        return sorted(bases)

    def needs_backfill(self) -> list[str]:
        """Sheep that still have genomes but lack poster and/or sidecar."""
        out: set[str] = set()
        for b in self.missing_poster + self.missing_sidecar:
            if self.has_genome.get(b):
                out.add(b)
        return sorted(out)

    def to_dict(self) -> dict[str, Any]:
        sheep_out = {
            b: {
                "mp4": [str(p) for p in kinds["mp4"]],
                "poster": [str(p) for p in kinds["poster"]],
                "sidecar": [str(p) for p in kinds["sidecar"]],
                "has_genome": self.has_genome.get(b, False),
            }
            for b, kinds in sorted(self.sheep.items())
        }
        return {
            "sheep": sheep_out,
            "catalog_without_genome": list(self.catalog_without_genome),
            "missing_poster": list(self.missing_poster),
            "missing_sidecar": list(self.missing_sidecar),
            "orphan_poster": list(self.orphan_poster),
            "orphan_sidecar": list(self.orphan_sidecar),
            "peer_junk": [str(p) for p in self.peer_junk],
            "pedigree_warnings": list(self.pedigree_warnings),
            "needs_backfill": self.needs_backfill(),
            "orphan_bases": self.orphan_bases(),
            "notes": list(self.notes),
        }


def audit_flock(cfg: dict[str, Any]) -> FlockAudit:
    """Scan media_library + genome trees + peers for hygiene findings."""
    audit = FlockAudit()
    flam3 = _known_flam3_bases(cfg)
    audit.sheep = _iter_catalog_media(cfg)
    for base, kinds in sorted(audit.sheep.items()):
        has_g = base in flam3
        audit.has_genome[base] = has_g
        if kinds["mp4"] and not has_g:
            audit.catalog_without_genome.append(base)
        if kinds["mp4"] and not kinds["poster"]:
            audit.missing_poster.append(base)
        if kinds["mp4"] and not kinds["sidecar"]:
            audit.missing_sidecar.append(base)
        if kinds["poster"] and not kinds["mp4"]:
            audit.orphan_poster.append(base)
        if kinds["sidecar"] and not kinds["mp4"]:
            audit.orphan_sidecar.append(base)
        for w in find_pedigree_orphan_warnings(cfg, base):
            if w not in audit.pedigree_warnings:
                audit.pedigree_warnings.append(w)

    audit.peer_junk = list_peer_junk(cfg)
    if audit.needs_backfill():
        audit.notes.append(
            "Repair posters/sidecars (genomes present): "
            "python3 -m pipeline.backfill_posters --config configs/jellyflam3.yaml --force"
        )
    if audit.orphan_bases():
        audit.notes.append(
            "Cull catalog orphans: "
            "python3 -m pipeline.shears sweep --orphans-only --confirm DELETE"
        )
    if audit.peer_junk:
        audit.notes.append(
            "Remove unexpected peer MP4s: "
            "python3 -m pipeline.peering hygiene --apply"
        )
    return audit


def print_audit(audit: FlockAudit) -> None:
    """Human-readable flock hygiene report."""
    print("=== Sheep Shears audit ===")
    print(f"catalog_sheep={len(audit.sheep)}")
    for base, kinds in sorted(audit.sheep.items()):
        g = "yes" if audit.has_genome.get(base) else "NO"
        print(
            f"  {base}  mp4={len(kinds['mp4'])} poster={len(kinds['poster'])} "
            f"sidecar={len(kinds['sidecar'])} genome={g}"
        )

    def _block(title: str, items: list[str]) -> None:
        print(f"\n[{title}] ({len(items)})")
        if not items:
            print("  (none)")
            return
        for x in items:
            print(f"  {x}")

    _block("catalog_without_genome", audit.catalog_without_genome)
    _block("missing_poster", audit.missing_poster)
    _block("missing_sidecar", audit.missing_sidecar)
    _block("orphan_poster", audit.orphan_poster)
    _block("orphan_sidecar", audit.orphan_sidecar)
    print(f"\n[peer_junk] ({len(audit.peer_junk)})")
    if not audit.peer_junk:
        print("  (none)")
    else:
        for p in audit.peer_junk:
            print(f"  {p}")
    _block("pedigree_warnings", audit.pedigree_warnings)
    _block("needs_backfill", audit.needs_backfill())
    if audit.notes:
        print("\n[notes]")
        for n in audit.notes:
            print(f"  {n}")


def sweep_orphans(
    cfg: dict[str, Any],
    *,
    dry_run: bool,
    peer_junk: bool = False,
) -> dict[str, Any]:
    """Delete catalog-without-genome (and poster/sidecar-only) sheep; optional peer MP4 junk."""
    audit = audit_flock(cfg)
    results: dict[str, Any] = {
        "dry_run": dry_run,
        "orphan_bases": audit.orphan_bases(),
        "deleted": [],
        "peer_junk": [str(p) for p in audit.peer_junk],
        "peer_junk_removed": [],
    }
    for base in audit.orphan_bases():
        report = discover_cascade(cfg, base)
        if dry_run:
            print(f"DRY-RUN would delete orphan {base} paths={len(report.all_paths())}")
        else:
            apply_delete(cfg, report, dry_run=False)
            print(f"deleted orphan {base}")
        results["deleted"].append(
            {"base": base, "paths": [str(p) for p in report.all_paths()]}
        )
    if peer_junk:
        for p in audit.peer_junk:
            if dry_run:
                print(f"DRY-RUN would remove peer junk {p}")
            else:
                p.unlink(missing_ok=True)
                log.info("removed peer junk %s", p)
                print(f"removed peer junk {p}")
            results["peer_junk_removed"].append(str(p))
    return results


def cmd_delete(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    report = discover_cascade(cfg, args.target)
    dry_run = args.confirm != CONFIRM_TOKEN
    if args.json:
        payload = report.to_dict()
        payload["dry_run"] = dry_run
        print(json.dumps(payload, indent=2))
    else:
        print_report(report, dry_run=dry_run)
    if dry_run:
        if args.confirm and args.confirm != CONFIRM_TOKEN:
            print(
                f"\nERROR: --confirm must be exactly {CONFIRM_TOKEN!r} "
                f"(got {args.confirm!r})",
                flush=True,
            )
            return 2
        return 0
    apply_delete(cfg, report, dry_run=False)
    print("\nCascade delete applied.")
    return 0


def cmd_add(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    dest = shears_add(
        cfg,
        Path(args.path),
        dry_run=args.dry_run,
        force=args.force,
        move=args.move,
    )
    if dest is None:
        print("skipped (already in inbox; use --force)")
        return 0
    action = "would stage" if args.dry_run else "staged"
    print(f"{action}: {dest}")
    return 0


def cmd_modify(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    dest = shears_modify(
        cfg,
        Path(args.path),
        dry_run=args.dry_run,
        force=True,
    )
    if dest is None:
        print("skipped")
        return 0
    action = "would re-stage" if args.dry_run else "re-staged"
    print(f"{action}: {dest}")
    print(
        "Worker will re-TV-port/encode on pickup. "
        "After catalog MP4 exists, refresh posters via: "
        "python -m pipeline.backfill_posters"
    )
    return 0


def cmd_audit(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    audit = audit_flock(cfg)
    if args.json:
        print(json.dumps(audit.to_dict(), indent=2))
    else:
        print_audit(audit)
    # Exit 1 when actionable medium findings exist (orphans / peer junk)
    if audit.orphan_bases() or audit.peer_junk:
        return 1
    return 0


def cmd_sweep(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    dry_run = args.confirm != CONFIRM_TOKEN
    if args.confirm and args.confirm != CONFIRM_TOKEN:
        print(
            f"ERROR: --confirm must be exactly {CONFIRM_TOKEN!r} "
            f"(got {args.confirm!r})",
            flush=True,
        )
        return 2
    if not args.orphans_only and not args.peer_junk:
        print("Nothing selected; pass --orphans-only and/or --peer-junk")
        return 2
    if dry_run:
        print(f"=== Sheep Shears sweep — DRY-RUN (pass --confirm {CONFIRM_TOKEN}) ===")
    else:
        print("=== Sheep Shears sweep — APPLY ===")
    result: dict[str, Any] = {"dry_run": dry_run, "deleted": [], "peer_junk_removed": []}
    if args.orphans_only or args.peer_junk:
        # Always run orphan path when orphans-only; peer_junk optional alongside
        if args.orphans_only:
            result = sweep_orphans(
                cfg, dry_run=dry_run, peer_junk=bool(args.peer_junk)
            )
        elif args.peer_junk:
            audit = audit_flock(cfg)
            result["peer_junk"] = [str(p) for p in audit.peer_junk]
            for p in audit.peer_junk:
                if dry_run:
                    print(f"DRY-RUN would remove peer junk {p}")
                else:
                    p.unlink(missing_ok=True)
                    print(f"removed peer junk {p}")
                result["peer_junk_removed"].append(str(p))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        needs = audit_flock(cfg).needs_backfill()
        if needs:
            print(
                "\nRemaining sheep need poster/sidecar repair "
                f"({len(needs)}): python3 -m pipeline.backfill_posters --force"
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m pipeline.shears",
        description="Sheep Shears — add / modify / delete with cascade cleanup",
    )
    p.add_argument(
        "--config",
        default="configs/jellyflam3.yaml",
        help="Path to jellyflam3.yaml",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("delete", help="List or remove cascade artifacts for one sheep")
    d.add_argument("target", help="Stem, .flam3 path, or catalog .mp4 path")
    d.add_argument(
        "--confirm",
        default="",
        help=f"Must be {CONFIRM_TOKEN!r} to actually delete (default: dry-run)",
    )
    d.add_argument("--json", action="store_true", help="Emit cascade report as JSON")
    d.set_defaults(func=cmd_delete)

    a = sub.add_parser("add", help="Stage a .flam3 into genomes_inbox")
    a.add_argument("path", help="Source .flam3 path")
    a.add_argument("--dry-run", action="store_true")
    a.add_argument("--force", action="store_true", help="Overwrite inbox copy")
    a.add_argument(
        "--move",
        action="store_true",
        help="Move source into inbox (default: copy and leave original in place)",
    )
    a.set_defaults(func=cmd_add)

    m = sub.add_parser(
        "modify",
        help="Re-stage genome into inbox for re-queue (poster refresh via backfill)",
    )
    m.add_argument("path", help="Source .flam3 path (inbox/done/catalog-adjacent)")
    m.add_argument("--dry-run", action="store_true")
    m.set_defaults(func=cmd_modify)

    au = sub.add_parser(
        "audit",
        help="Report catalog orphans, missing posters/sidecars, peer junk",
    )
    au.add_argument("--json", action="store_true")
    au.set_defaults(func=cmd_audit)

    sw = sub.add_parser(
        "sweep",
        help="Cull catalog orphans and/or peer MP4 junk (dry-run unless --confirm DELETE)",
    )
    sw.add_argument(
        "--orphans-only",
        action="store_true",
        help="Delete catalog-without-genome and poster/sidecar-only sheep",
    )
    sw.add_argument(
        "--peer-junk",
        action="store_true",
        help="Remove unexpected *.mp4 under peers inbox/share-out/quarantine",
    )
    sw.add_argument(
        "--confirm",
        default="",
        help=f"Must be {CONFIRM_TOKEN!r} to apply (default: dry-run)",
    )
    sw.add_argument("--json", action="store_true")
    sw.set_defaults(func=cmd_sweep)

    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    return int(args.func(cfg, args))


if __name__ == "__main__":
    raise SystemExit(main())
