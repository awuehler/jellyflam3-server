#!/usr/bin/env python3
"""Purpose: Stage voted catalog sheep into peers/share-out (Phase 4 / Wave 3).

Requirements: catalog sidecars with ``viewer_feedback``; Opt In; ``pipeline.peering.publish``
  (sheep tax + share-security). Does **not** promote into ``genomes/inbox``.

Usage:
  python3 -m pipeline.share_votes --json
  python3 -m pipeline.share_votes --apply --json
  python3 -m pipeline.share_votes --dry-run --json

Assumptions: Sidecar ``viewer_feedback`` is the only vote SoT. Kill-switch
  ``share_votes.enabled``. Receive path stays gated ``promote --apply``.
Docs: docs/phase4/08_VIEWER_FEEDBACK_LOOP.md · docs/phase4/01_PEER_SHARE_PATH.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path
from pipeline.license_filter import is_commercial_allowed
from pipeline.media_layout import is_unpublished_media_path
from pipeline.peering import is_opted_in, publish
from pipeline.refactor_scan import find_genome_for_stem
from pipeline.sheep_naming import iter_sidecars, sidecar_stem
from pipeline.sheep_votes import normalize_feedback

log = logging.getLogger("jellyflam3.share_votes")


def share_votes_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return ``share_votes`` merged with defaults (kill-switch on)."""
    defaults = {
        "enabled": True,
        "min_votes": 1,
        "min_loves": 0,
        "require_opt_in": True,
        "require_share_candidate": True,
    }
    raw = dict(cfg.get("share_votes") or {})
    return {**defaults, **raw}


def _is_under(child: Path, root: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def sidecar_tags(data: dict[str, Any]) -> list[str]:
    """License tags from a catalog sidecar (worker ``tags`` + ``license``)."""
    tags: list[str] = []
    raw = data.get("tags")
    if isinstance(raw, list):
        tags.extend(str(t) for t in raw)
    lic = data.get("license")
    if lic:
        tags.append(str(lic))
    return tags


def meets_share_threshold(feedback: dict[str, Any], sv: dict[str, Any]) -> bool:
    """True when sidecar vote tallies pass min votes / loves / share_candidate."""
    fb = normalize_feedback(feedback)
    if sv.get("require_share_candidate", True) and not fb.get("share_candidate"):
        return False
    if int(fb.get("votes") or 0) < int(sv.get("min_votes", 1)):
        return False
    if int(fb.get("loves") or 0) < int(sv.get("min_loves", 0)):
        return False
    return True


def find_shareable_genome(cfg: dict[str, Any], stem: str) -> Path | None:
    """Locate a rendered ``.flam3`` (not inbox / quarantine)."""
    path = find_genome_for_stem(cfg, stem)
    if path is None or not path.is_file():
        return None
    for key in ("genomes_inbox", "genomes_quarantine"):
        try:
            root = resolve_path(cfg, key)
        except (KeyError, TypeError):
            continue
        if _is_under(path, root):
            return None
    return path


def _scan_candidates(cfg: dict[str, Any]) -> tuple[list[Path], list[dict[str, Any]]]:
    """Return genomes to publish plus skip records for the JSON report."""
    sv = share_votes_cfg(cfg)
    media = resolve_path(cfg, "media_library")
    sources: list[Path] = []
    skipped: list[dict[str, Any]] = []
    seen: set[str] = set()

    for side in iter_sidecars(media):
        stem = sidecar_stem(side)
        rec: dict[str, Any] = {"stem": stem, "sidecar": str(side)}
        if is_unpublished_media_path(side):
            rec["reason"] = "unpublished"
            skipped.append(rec)
            continue
        try:
            data = json.loads(side.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            rec["reason"] = "unreadable_sidecar"
            skipped.append(rec)
            continue
        if not isinstance(data, dict):
            rec["reason"] = "unreadable_sidecar"
            skipped.append(rec)
            continue
        fb = normalize_feedback(data.get("viewer_feedback"))
        rec["viewer_feedback"] = {
            "votes": fb.get("votes"),
            "loves": fb.get("loves"),
            "share_candidate": fb.get("share_candidate"),
        }
        if not meets_share_threshold(fb, sv):
            rec["reason"] = "below_threshold"
            skipped.append(rec)
            continue
        if not is_commercial_allowed(sidecar_tags(data), cfg):
            rec["reason"] = "commercial_nc"
            skipped.append(rec)
            continue
        genome = find_shareable_genome(cfg, stem)
        if genome is None:
            rec["reason"] = "genome_missing"
            skipped.append(rec)
            continue
        key = genome.resolve().as_posix()
        if key in seen:
            rec["reason"] = "duplicate_genome"
            skipped.append(rec)
            continue
        seen.add(key)
        sources.append(genome)

    return sources, skipped


def run_share_votes(
    cfg: dict[str, Any],
    *,
    apply: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Plan or copy voted genomes into ``peers/share-out``. Never promotes inbound."""
    sv = share_votes_cfg(cfg)
    opted = is_opted_in(cfg)
    out: dict[str, Any] = {
        "ok": True,
        "action": "plan",
        "apply": bool(apply) and not dry_run,
        "opted_in": opted,
        "candidates": 0,
        "published": [],
        "skipped": [],
        "reason": None,
        "note": (
            "Stages peers/share-out via peering.publish (copy). "
            "Does not promote into genomes/inbox."
        ),
    }
    if not sv.get("enabled", True):
        out["action"] = "skip"
        out["reason"] = "disabled"
        return out
    if sv.get("require_opt_in", True) and not opted:
        out["action"] = "skip"
        out["reason"] = "opt_out"
        return out

    sources, skipped = _scan_candidates(cfg)
    out["skipped"] = skipped
    out["candidates"] = len(sources)
    if not sources:
        out["action"] = "skip"
        out["reason"] = "no_candidates"
        return out

    do_apply = bool(apply) and not dry_run
    summary = publish(
        cfg,
        sources,
        apply=do_apply,
        skip_tax=False,
        dry_run=False,
        move=False,
    )
    results = summary.get("results") or []
    out["published"] = results
    out["action"] = "share" if do_apply else "plan"
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI: plan or apply vote-driven share-out."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description="Stage voted catalog sheep to peers/share-out (not genomes/inbox)"
    )
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    p.add_argument("--apply", action="store_true", help="Copy into share-out (default: plan)")
    p.add_argument("--dry-run", action="store_true", help="Force plan-only")
    p.add_argument("--json", action="store_true", help="Print the result JSON (always on)")
    args = p.parse_args(argv)
    cfg = load_config(args.config, strict_secrets=False)
    payload = run_share_votes(cfg, apply=args.apply, dry_run=args.dry_run)
    print(json.dumps(payload, indent=2))
    if not payload.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
