"""Purpose: Sheep refactor — scan/score/report + Jellyfin-visible preview (Phase 3 guide 09).

Requirements: Catalog under ``paths.media_library/by-generation``; genomes in done/inbox/
samples/pedigree; ``pipeline.sheep_tax``, ``palette_harmony``, ``choose_duration``, posters;
preview root ``paths.refactor_preview_root`` or ``media_library/_refactor-preview``.

Usage:
  python3 -m pipeline.refactor scan --config configs/jellyflam3.yaml
  python3 -m pipeline.refactor report --id electricsheep.247.00505
  python3 -m pipeline.refactor preview --id electricsheep.247.00505 --preview-poster
  python3 -m pipeline.refactor preview --id electricsheep.247.00505 --discard
  python3 -m pipeline.refactor quarantine --id electricsheep.247.00505
  python3 -m pipeline.refactor quarantine --id electricsheep.247.00505 --confirm QUARANTINE --unpublish
  python3 -m pipeline.refactor apply --id electricsheep.247.00505
  python3 -m pipeline.refactor apply --id electricsheep.247.00505 --confirm APPLY --palette-mode complementary

Assumptions: Pathway A is read-only. Pathway P writes only under ``_refactor-preview/``
(never live catalog Primary). Pathway C moves genetics to ``genomes_quarantine`` and may
park catalog under ``_refactor-quarantine/`` (no delete). Pathway B stages a TV-optimized
retint into ``genomes_inbox`` (furnace remains async via worker) and records sidecar
``refactor:`` history (pending companion + catalog append; worker merges on ingest).
Pathway D batches B/C. Compose existing modules — do not invent a second furnace.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from pipeline.config import load_config
from pipeline.refactor_actions import (
    APPLY_CONFIRM_TOKEN,
    BATCH_CONFIRM_TOKEN,
    QUARANTINE_CONFIRM_TOKEN,
    ApplyResult,
    BatchItemResult,
    BatchResult,
    QuarantineResult,
    catalog_quarantine_dir_for,
    catalog_quarantine_root,
    run_apply,
    run_batch,
    run_quarantine,
    soft_unpublish_jellyfin,
)
from pipeline.refactor_history import (
    REFACTOR_PENDING_SUFFIX,
    append_catalog_refactor_history,
    build_refactor_history_entry,
    load_refactor_pending,
    merge_pending_refactor_into_sidecar,
    merge_refactor_history,
    refactor_pending_path,
    write_refactor_pending,
)
from pipeline.refactor_preview import (
    PreviewResult,
    cfg_with_palette_overrides,
    discard_preview,
    encode_palette_preview_mp4,
    encode_still_preview_mp4,
    preview_dir_for,
    preview_root,
    render_flam3_still,
    run_preview,
    soft_refresh_jellyfin,
    write_jpeg_from_image,
    write_preview_poster,
)
from pipeline.refactor_scan import (
    SCORE_CANDIDATE_MIN,
    SCORE_QUARANTINE_MIN,
    SheepScore,
    filter_report,
    find_catalog_mp4,
    find_genome_for_stem,
    format_table,
    scan_catalog,
    score_sheep,
)

log = logging.getLogger("jellyflam3.refactor")

__all__ = [
    "APPLY_CONFIRM_TOKEN",
    "BATCH_CONFIRM_TOKEN",
    "QUARANTINE_CONFIRM_TOKEN",
    "REFACTOR_PENDING_SUFFIX",
    "SCORE_CANDIDATE_MIN",
    "SCORE_QUARANTINE_MIN",
    "ApplyResult",
    "BatchItemResult",
    "BatchResult",
    "PreviewResult",
    "QuarantineResult",
    "SheepScore",
    "append_catalog_refactor_history",
    "build_parser",
    "build_refactor_history_entry",
    "catalog_quarantine_dir_for",
    "catalog_quarantine_root",
    "cfg_with_palette_overrides",
    "discard_preview",
    "encode_palette_preview_mp4",
    "encode_still_preview_mp4",
    "filter_report",
    "find_catalog_mp4",
    "find_genome_for_stem",
    "format_table",
    "load_refactor_pending",
    "main",
    "merge_pending_refactor_into_sidecar",
    "merge_refactor_history",
    "preview_dir_for",
    "preview_root",
    "refactor_pending_path",
    "render_flam3_still",
    "run_apply",
    "run_batch",
    "run_preview",
    "run_quarantine",
    "scan_catalog",
    "score_sheep",
    "soft_refresh_jellyfin",
    "soft_unpublish_jellyfin",
    "write_jpeg_from_image",
    "write_preview_poster",
    "write_refactor_pending",
]


def _add_shared_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config",
        default="configs/jellyflam3.yaml",
        help="Config path (default: configs/jellyflam3.yaml)",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    p.add_argument("--id", dest="sheep_id", help="Score/preview a single sheep id/stem")
    p.add_argument("--limit", type=int, default=None, help="Max catalog rows to score")
    p.add_argument(
        "--failing",
        action="store_true",
        help="Only show candidate/quarantine rows",
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="python -m pipeline.refactor",
        description="Sheep refactor — scan/report/preview/quarantine (Phase 3 guide 09)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan/score catalog (alias of report)")
    _add_shared_args(scan)

    report = sub.add_parser("report", help="Print quality + complementary palette report")
    _add_shared_args(report)

    preview = sub.add_parser(
        "preview",
        help="Pathway P: palette override + Jellyfin-visible preview (no catalog replace)",
    )
    _add_shared_args(preview)
    preview.add_argument(
        "--preview-poster",
        action="store_true",
        help="Write preview MP4 + poster under _refactor-preview/",
    )
    preview.add_argument(
        "--discard",
        action="store_true",
        help="Remove _refactor-preview/<id>/ and refresh Jellyfin",
    )
    preview.add_argument(
        "--palette-mode",
        default=None,
        help="Override palette.mode (complementary|split_complementary|off)",
    )
    preview.add_argument(
        "--palette-seed",
        default=None,
        help="Override palette seed as #RRGGBB (sets seed=curator_hex)",
    )
    preview.add_argument(
        "--no-jellyfin-refresh",
        action="store_true",
        help="Skip Jellyfin library refresh",
    )

    quarantine = sub.add_parser(
        "quarantine",
        help="Pathway C: move genetics to genomes_quarantine; park catalog (no delete)",
    )
    _add_shared_args(quarantine)
    quarantine.add_argument(
        "--confirm",
        default=None,
        help=f"Must be {QUARANTINE_CONFIRM_TOKEN!r} to apply (default: dry-run)",
    )
    quarantine.add_argument(
        "--reason",
        default=None,
        help="Operator note recorded in the JSON report",
    )
    quarantine.add_argument(
        "--unpublish",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Park catalog under _refactor-quarantine/ + soft Jellyfin delete (default: on)",
    )
    quarantine.add_argument(
        "--force",
        action="store_true",
        help="Allow quarantine when score verdict is not quarantine",
    )
    quarantine.add_argument(
        "--no-jellyfin-refresh",
        action="store_true",
        help="Skip Jellyfin library refresh after unpublish",
    )

    apply_p = sub.add_parser(
        "apply",
        help="Pathway B: TV-optimize + palette override; stage retint into genomes_inbox",
    )
    _add_shared_args(apply_p)
    apply_p.add_argument(
        "--confirm",
        default=None,
        help=f"Must be {APPLY_CONFIRM_TOKEN!r} to stage (default: dry-run)",
    )
    apply_p.add_argument(
        "--reason",
        default=None,
        help="Operator note recorded in the JSON report",
    )
    apply_p.add_argument(
        "--palette-mode",
        default=None,
        help="Override palette.mode (complementary|split_complementary|off)",
    )
    apply_p.add_argument(
        "--palette-seed",
        default=None,
        help="Override palette seed as #RRGGBB (sets seed=curator_hex)",
    )
    apply_p.add_argument(
        "--keep-preview",
        action="store_true",
        help="Do not discard _refactor-preview/<id>/ after staging",
    )
    apply_p.add_argument(
        "--no-jellyfin-refresh",
        action="store_true",
        help="Skip Jellyfin library refresh",
    )

    batch = sub.add_parser(
        "batch",
        help="Pathway D: scan failing rows; route quarantine→C and candidates→B",
    )
    _add_shared_args(batch)
    batch.add_argument(
        "--confirm",
        default=None,
        help=f"Must be {BATCH_CONFIRM_TOKEN!r} to apply (default: dry-run)",
    )
    batch.add_argument(
        "--reason",
        default=None,
        help="Operator note recorded on each item report",
    )
    batch.add_argument(
        "--palette-mode",
        default=None,
        help="Palette mode override for apply items",
    )
    batch.add_argument(
        "--palette-seed",
        default=None,
        help="Palette seed override (#RRGGBB) for apply items",
    )
    batch.add_argument(
        "--all",
        action="store_true",
        help="Include ok rows (skipped); default is --failing candidates/quarantine only",
    )
    batch.add_argument(
        "--no-unpublish",
        action="store_true",
        help="For quarantine items: do not park catalog / soft-unpublish",
    )
    batch.add_argument(
        "--jellyfin-refresh",
        action="store_true",
        help="Refresh Jellyfin per item (default: off; expensive in batch)",
    )

    return ap


def _cmd_report(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    rows = scan_catalog(cfg, sheep_id=args.sheep_id, limit=args.limit)
    rows = filter_report(rows, failing_only=bool(args.failing))
    if args.json:
        print(json.dumps([r.to_dict() for r in rows], indent=2))
    else:
        print(format_table(rows))
        n_ok = sum(1 for r in rows if r.verdict == "ok")
        n_c = sum(1 for r in rows if r.verdict == "candidate")
        n_q = sum(1 for r in rows if r.verdict == "quarantine")
        print(f"\nsummary: ok={n_ok} candidate={n_c} quarantine={n_q} total={len(rows)}")
    return 0


def _cmd_preview(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    if not args.sheep_id:
        print("preview requires --id", file=sys.stderr)
        return 2
    if args.discard:
        result = discard_preview(
            cfg,
            args.sheep_id,
            refresh_jellyfin=not bool(args.no_jellyfin_refresh),
        )
    else:
        if not args.preview_poster:
            print(
                "preview requires --preview-poster (or --discard)",
                file=sys.stderr,
            )
            return 2
        result = run_preview(
            cfg,
            args.sheep_id,
            palette_mode=args.palette_mode,
            palette_seed=args.palette_seed,
            preview_poster=True,
            refresh_jellyfin=not bool(args.no_jellyfin_refresh),
        )
    print(json.dumps(result.to_dict(), indent=2))
    return 0


def _cmd_quarantine(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    if not args.sheep_id:
        print("quarantine requires --id", file=sys.stderr)
        return 2
    if args.confirm and args.confirm != QUARANTINE_CONFIRM_TOKEN:
        print(
            f"--confirm must be exactly {QUARANTINE_CONFIRM_TOKEN!r} "
            "(or omit for dry-run)",
            file=sys.stderr,
        )
        return 2
    dry_run = args.confirm != QUARANTINE_CONFIRM_TOKEN
    try:
        result = run_quarantine(
            cfg,
            args.sheep_id,
            dry_run=dry_run,
            reason=args.reason,
            unpublish=bool(args.unpublish),
            force=bool(args.force),
            refresh_jellyfin=not bool(args.no_jellyfin_refresh),
        )
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result.to_dict(), indent=2))
    if dry_run:
        print(
            f"\nDRY-RUN only. Re-run with --confirm {QUARANTINE_CONFIRM_TOKEN} to apply.",
            file=sys.stderr,
        )
    return 0


def _cmd_apply(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    if not args.sheep_id:
        print("apply requires --id", file=sys.stderr)
        return 2
    if args.confirm and args.confirm != APPLY_CONFIRM_TOKEN:
        print(
            f"--confirm must be exactly {APPLY_CONFIRM_TOKEN!r} "
            "(or omit for dry-run)",
            file=sys.stderr,
        )
        return 2
    dry_run = args.confirm != APPLY_CONFIRM_TOKEN
    try:
        result = run_apply(
            cfg,
            args.sheep_id,
            dry_run=dry_run,
            palette_mode=args.palette_mode,
            palette_seed=args.palette_seed,
            reason=args.reason,
            discard_preview_dir=not bool(args.keep_preview),
            refresh_jellyfin=not bool(args.no_jellyfin_refresh),
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result.to_dict(), indent=2))
    if dry_run:
        print(
            f"\nDRY-RUN only. Re-run with --confirm {APPLY_CONFIRM_TOKEN} to stage inbox.",
            file=sys.stderr,
        )
    return 0


def _cmd_batch(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    if args.confirm and args.confirm != BATCH_CONFIRM_TOKEN:
        print(
            f"--confirm must be exactly {BATCH_CONFIRM_TOKEN!r} "
            "(or omit for dry-run)",
            file=sys.stderr,
        )
        return 2
    dry_run = args.confirm != BATCH_CONFIRM_TOKEN
    # Shared --failing means failing-only; --all flips that off.
    failing_only = True
    if bool(getattr(args, "all", False)):
        failing_only = False
    elif bool(getattr(args, "failing", False)):
        failing_only = True
    result = run_batch(
        cfg,
        dry_run=dry_run,
        limit=args.limit,
        failing_only=failing_only,
        palette_mode=args.palette_mode,
        palette_seed=args.palette_seed,
        reason=args.reason,
        unpublish=not bool(args.no_unpublish),
        refresh_jellyfin=bool(args.jellyfin_refresh),
    )
    print(json.dumps(result.to_dict(), indent=2))
    if dry_run:
        print(
            f"\nDRY-RUN only. Re-run with --confirm {BATCH_CONFIRM_TOKEN} to apply.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = build_parser()
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    if args.cmd == "preview":
        return _cmd_preview(cfg, args)
    if args.cmd == "quarantine":
        return _cmd_quarantine(cfg, args)
    if args.cmd == "apply":
        return _cmd_apply(cfg, args)
    if args.cmd == "batch":
        return _cmd_batch(cfg, args)
    return _cmd_report(cfg, args)


if __name__ == "__main__":
    sys.exit(main())
