#!/usr/bin/env python3
"""Purpose: Auto-rotate catalog sheep when the sheep mount is WARN/BAD (Phase 4 / 06).

Requirements: ``pipeline.library_disk`` thresholds; Shears cascade (not Hammer).

Usage:
  python3 -m pipeline.library_disk rotate
  python3 -m pipeline.library_disk rotate --apply
  python3 -m pipeline.library_disk rotate --json

Assumptions: Oldest catalog MP4 mtime first. Floor ≥ 1 playable catalog MP4.
  Never deletes git ``genomes/samples`` or ``genomes/pedigree``. Kill-switch
  ``library_disk.rotate_enabled``. Worker refuse is a separate BAD check.
Docs: docs/phase4/06_LIBRARY_DISK_ROTATE.md
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pipeline.config import resolve_path
from pipeline.library_disk import sheep_check
from pipeline.media_layout import is_unpublished_media_path
from pipeline.shears import (
    apply_delete,
    discover_cascade,
    drop_git_feedstock_from_cascade,
    resolve_sheep_base,
)
from pipeline.stills import iter_catalog_mp4s

log = logging.getLogger("jellyflam3.library_rotate")


def rotate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """Rotate knobs under ``library_disk`` with defaults."""
    block = dict(cfg.get("library_disk") or {})
    return {
        "rotate_enabled": bool(block.get("rotate_enabled", True)),
        "rotate_floor": max(1, int(block.get("rotate_floor", 1))),
        "rotate_max_per_run": max(1, int(block.get("rotate_max_per_run", 8))),
        "rotate_until": str(block.get("rotate_until") or "ok").strip().lower(),
    }


def _sheep_needs_rotate(level: str, until: str) -> bool:
    """True while we should keep purging toward ``until`` (ok or warn)."""
    if until == "warn":
        return level == "bad"
    return level in ("warn", "bad")


def catalog_rotate_candidates(cfg: dict[str, Any]) -> list[Path]:
    """Catalog MP4s oldest mtime first (unpublished / edges already skipped)."""
    media = resolve_path(cfg, "media_library")
    mp4s = [p for p in iter_catalog_mp4s(media) if not is_unpublished_media_path(p)]
    return sorted(mp4s, key=lambda p: (p.stat().st_mtime, str(p)))


def run_rotate(
    cfg: dict[str, Any],
    *,
    apply: bool = False,
    usage_for: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Plan or apply Shears deletes until sheep is under threshold or floor."""
    knobs = rotate_cfg(cfg)
    out: dict[str, Any] = {
        "ok": True,
        "action": "skip",
        "reason": None,
        "apply": bool(apply),
        "retired": [],
        "planned": [],
        "remaining": 0,
        "floor": knobs["rotate_floor"],
        "sheep_level": None,
    }
    if not knobs["rotate_enabled"]:
        out["reason"] = "disabled"
        return out

    row = sheep_check(cfg, usage_for=usage_for)
    if row is None:
        out["reason"] = "sheep_mount_missing"
        out["ok"] = False
        return out
    out["sheep_level"] = row.level
    if not _sheep_needs_rotate(row.level, knobs["rotate_until"]):
        out["reason"] = "under_threshold"
        return out

    candidates = catalog_rotate_candidates(cfg)
    out["remaining"] = len(candidates)
    floor = knobs["rotate_floor"]
    if len(candidates) <= floor:
        out["reason"] = "floor"
        return out

    until = knobs["rotate_until"]
    budget = knobs["rotate_max_per_run"]
    level = row.level
    for mp4 in candidates:
        if len(candidates) - len(out["planned"]) <= floor:
            break
        if len(out["planned"]) >= budget:
            out["reason"] = "max_per_run"
            break
        if not _sheep_needs_rotate(level, until) and usage_for is None:
            break
        stem = resolve_sheep_base(mp4)
        report = drop_git_feedstock_from_cascade(cfg, discover_cascade(cfg, stem))
        entry = {
            "stem": stem,
            "mp4": str(mp4),
            "mtime": mp4.stat().st_mtime,
            "paths": [str(p) for p in report.all_paths()],
        }
        out["planned"].append(entry)
        if apply:
            apply_delete(cfg, report, dry_run=False)
            out["retired"].append(entry)
        if usage_for is None:
            nxt = sheep_check(cfg)
            if nxt is not None:
                level = nxt.level
                out["sheep_level"] = level
                if not _sheep_needs_rotate(level, until):
                    break
        else:
            # Injected usage cannot drop after deletes; keep going to floor/max.
            pass

    planned_stems = {e["stem"] for e in out["planned"]}
    if apply:
        out["remaining"] = len(catalog_rotate_candidates(cfg))
    else:
        out["remaining"] = sum(1 for p in candidates if resolve_sheep_base(p) not in planned_stems)

    if out["planned"]:
        out["action"] = "rotate" if apply else "plan"
        if out["reason"] is None:
            out["reason"] = "ok" if apply else "dry_run"
    else:
        out["reason"] = out["reason"] or "no_candidates"
    return out
