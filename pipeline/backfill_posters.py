"""Purpose: One-shot backfill of posters, screensaver stills, and Jellyfin images.

Requirements: Config with media_library; ffmpeg/ffprobe; optional Jellyfin api_key and idle_gate.

Usage:
  python -m pipeline.backfill_posters --config configs/jellyflam3.yaml --dry-run
  python -m pipeline.backfill_posters --config configs/jellyflam3.yaml --limit 20

Assumptions: Sidecar ``*.jellyflam3.json`` tracks completion; soft-fails leave partial sidecar
state. ``local_primary`` is not complete (stills/.ignore). Disk frames are not Backdrops —
``jellyfin_stills`` must be ``uploaded``. Stills ride the same path as posters (never from
tuples). Operator backfill force-extracts stills and replaces Jellyfin Backdrops. Does not
walk ``_refactor-quarantine/`` or ``_refactor-preview/`` (stills always land under live
``by-generation/{gen}/stills/{stem}/``).
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path
from pipeline.flock_artwork import (
    attach_primary_after_refresh,
    attach_stills_backdrops,
    extract_poster_for_mp4,
)
from pipeline.idle_gate import is_gate_open
from pipeline.jellyfin_client import JellyfinClient
from pipeline.media_layout import is_unpublished_media_path
from pipeline.poster import probe_duration_sec, relocate_legacy_poster, resolve_poster_path
from pipeline.sheep_names import is_tuple_catalog
from pipeline.stills import extract_stills_for_mp4, iter_catalog_mp4s as iter_live_catalog_mp4s, stills_cfg
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.backfill_posters")


@dataclass
class BackfillStats:
    scanned: int = 0
    skipped: int = 0
    processed: int = 0
    extracted: int = 0
    uploaded: int = 0
    failed: int = 0
    dry_run_would_process: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def bump_reason(self, reason: str) -> None:
        self.reasons[reason] = self.reasons.get(reason, 0) + 1


def iter_catalog_mp4s(media_root: Path) -> list[Path]:
    """Live catalog ``*.mp4`` under ``by-generation/`` (skips quarantine, preview, edges)."""
    return iter_live_catalog_mp4s(media_root, skip_tuples=False)


def sidecar_path_for_mp4(mp4: Path) -> Path:
    return mp4.with_suffix(".jellyflam3.json")


def load_sidecar(mp4: Path) -> dict[str, Any]:
    """Load ``*.jellyflam3.json`` beside ``mp4``, or a minimal ``{id}`` stub."""
    path = sidecar_path_for_mp4(mp4)
    if not path.is_file():
        return {"id": mp4.stem}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("id", mp4.stem)
            return data
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("sidecar read failed for %s: %s", path, exc)
    return {"id": mp4.stem}


def write_sidecar(mp4: Path, sidecar: dict[str, Any]) -> None:
    """Persist sidecar JSON as given (does not strip reserved / unknown keys)."""
    path = sidecar_path_for_mp4(mp4)
    path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")


def _primary_upload_complete(img: dict[str, Any]) -> bool:
    """True when sidecar records a live Images API Primary (not stills/.ignore leftover)."""
    status = str(img.get("status") or "")
    if status == "local_primary":
        return False
    return img.get("ok") is True or status == "uploaded"


def _backdrop_upload_complete(sidecar: dict[str, Any]) -> bool:
    """True when sidecar records Backdrop Images API upload (disk frames are not Backdrops)."""
    jf = sidecar.get("jellyfin_stills") or {}
    status = str(jf.get("status") or "")
    if status == "skipped_tuple":
        return True
    return jf.get("ok") is True or status == "uploaded"


def needs_backfill(
    mp4: Path,
    sidecar: dict[str, Any],
    *,
    force: bool = False,
) -> tuple[bool, str]:
    """Return (needed, reason) based on poster file + sidecar Jellyfin fields."""
    if is_unpublished_media_path(mp4):
        return False, "unpublished"
    if force:
        return True, "force"
    poster = resolve_poster_path(mp4)
    has_poster = poster.is_file() and poster.stat().st_size > 0
    img = sidecar.get("jellyfin_image") or {}
    meta = sidecar.get("jellyfin_metadata") or {}
    img_ok = _primary_upload_complete(img)
    meta_ok = meta.get("ok") is True or meta.get("status") in ("enriched", "tags_only")
    if has_poster and img_ok and meta_ok:
        if is_tuple_catalog(mp4, sidecar):
            return False, "already_complete"
        stills_block = sidecar.get("stills") or {}
        if stills_block.get("status") in ("extracted", "already_complete") or stills_block.get(
            "screensaver_safe"
        ):
            if not _backdrop_upload_complete(sidecar):
                return True, "missing_backdrops"
            return False, "already_complete"
        return True, "missing_stills"
    if not has_poster:
        return True, "missing_poster"
    if not img_ok:
        return True, "missing_primary"
    if not meta_ok:
        return True, "missing_metadata"
    return True, "incomplete"


def resolve_duration_sec(cfg: dict[str, Any], mp4: Path, sidecar: dict[str, Any]) -> float:
    """Duration for mid-loop seek: sidecar first, else ffprobe, else 13s fallback."""
    if sidecar.get("duration_sec") is not None:
        try:
            return float(sidecar["duration_sec"])
        except (TypeError, ValueError):
            pass
    try:
        return probe_duration_sec(_tool(cfg, "ffprobe"), mp4)
    except Exception as exc:  # noqa: BLE001
        log.warning("ffprobe duration failed for %s (%s); using 13s mid-seek fallback", mp4, exc)
        return 13.0


def wait_for_gate(cfg: dict[str, Any], *, sleep: Any = time.sleep) -> None:
    """Block until idle-gate is open (no-op when idle_gate is disabled)."""
    ig = cfg.get("idle_gate") or {}
    if not ig.get("enabled", True):
        return
    while not is_gate_open(cfg):
        log.info("idle-gate closed; waiting 15s before backfill continues")
        sleep(15)


def backfill_one(
    cfg: dict[str, Any],
    mp4: Path,
    *,
    client: JellyfinClient | None = None,
    force: bool = False,
    sleep: Any = time.sleep,
    skip_jellyfin: bool = False,
) -> dict[str, Any]:
    """Extract/upload/enrich one catalog MP4. Soft-fail; updates sidecar on disk."""
    if is_unpublished_media_path(mp4):
        return {"mp4": str(mp4), "status": "skipped", "reason": "unpublished"}
    relocate_legacy_poster(mp4)
    sidecar = load_sidecar(mp4)
    needed, reason = needs_backfill(mp4, sidecar, force=force)
    if not needed:
        return {"mp4": str(mp4), "status": "skipped", "reason": reason}

    duration_sec = resolve_duration_sec(cfg, mp4, sidecar)
    tags = list(sidecar.get("tags") or [])
    sidecar.setdefault("id", mp4.stem)
    sidecar.setdefault("duration_sec", duration_sec)

    if skip_jellyfin:
        poster_info = extract_poster_for_mp4(
            cfg, mp4, duration_sec=duration_sec, force=True
        )
        sidecar["poster"] = poster_info
        if poster_info.get("poster_path"):
            sidecar["poster_path"] = poster_info["poster_path"]
        if is_tuple_catalog(mp4, sidecar):
            sidecar["stills"] = {
                "ok": True,
                "status": "skipped_tuple",
                "screensaver_safe": False,
            }
        elif bool(stills_cfg(cfg).get("enabled", True)):
            sidecar["stills"] = extract_stills_for_mp4(cfg, mp4, force=True)
        write_sidecar(mp4, sidecar)
        return {
            "mp4": str(mp4),
            "status": "poster_only",
            "reason": reason,
            "poster": poster_info,
        }

    # Reuse ingest orchestration but without per-item Library/Refresh.
    # Operator backfill always extracts, even when ingest attach_posters is auto/never.
    poster_info = extract_poster_for_mp4(
        cfg, mp4, duration_sec=duration_sec, force=True
    )
    sidecar["poster"] = poster_info
    if poster_info.get("poster_path"):
        sidecar["poster_path"] = poster_info["poster_path"]
    poster_path = (
        Path(poster_info["poster_path"])
        if poster_info.get("ok") and poster_info.get("poster_path")
        else None
    )
    # If extract failed but an older poster exists, still try upload.
    if poster_path is None:
        existing = resolve_poster_path(mp4)
        if existing.is_file() and existing.stat().st_size > 0:
            poster_path = existing

    attach = attach_primary_after_refresh(
        cfg,
        mp4,
        poster_path,
        tags=tags,
        sidecar=sidecar,
        client=client,
        sleep=sleep,
        refresh=False,
        force=True,
    )
    sidecar["jellyfin_image"] = attach
    if isinstance(attach.get("metadata"), dict):
        sidecar["jellyfin_metadata"] = attach["metadata"]

    stills_info: dict[str, Any]
    if is_tuple_catalog(mp4, sidecar):
        stills_info = {
            "ok": True,
            "status": "skipped_tuple",
            "screensaver_safe": False,
        }
        sidecar["stills"] = stills_info
    elif bool(stills_cfg(cfg).get("enabled", True)):
        stills_info = extract_stills_for_mp4(cfg, mp4, force=True)
        sidecar["stills"] = stills_info
        item_id = str(attach.get("item_id") or "")
        if item_id:
            try:
                sidecar["jellyfin_stills"] = attach_stills_backdrops(
                    cfg,
                    mp4,
                    stills_info,
                    client=client or JellyfinClient.from_config(cfg),
                    item_id=item_id,
                    sleep=sleep,
                    replace=True,
                )
            except Exception as exc:  # noqa: BLE001
                sidecar["jellyfin_stills"] = {
                    "ok": False,
                    "status": "failed",
                    "error": str(exc),
                }
    write_sidecar(mp4, sidecar)
    return {
        "mp4": str(mp4),
        "status": "processed",
        "reason": reason,
        "poster": poster_info,
        "jellyfin_image": attach,
    }


def run_backfill(
    cfg: dict[str, Any],
    *,
    dry_run: bool = False,
    force: bool = False,
    limit: int | None = None,
    interval_sec: float = 1.0,
    skip_jellyfin: bool = False,
    client: JellyfinClient | None = None,
    sleep: Any = time.sleep,
) -> BackfillStats:
    """Scan catalog MP4s and backfill posters/Primary/metadata; returns aggregate stats."""
    media = resolve_path(cfg, "media_library")
    mp4s = iter_catalog_mp4s(media)
    stats = BackfillStats(scanned=len(mp4s))
    jf = cfg.get("jellyfin") or {}

    todo: list[Path] = []
    for mp4 in mp4s:
        sidecar = load_sidecar(mp4)
        needed, reason = needs_backfill(mp4, sidecar, force=force)
        stats.bump_reason(reason)
        if needed:
            todo.append(mp4)
        else:
            stats.skipped += 1

    if limit is not None and limit >= 0:
        todo = todo[:limit]

    if dry_run:
        stats.dry_run_would_process = len(todo)
        log.info(
            "dry-run: scanned=%s skip=%s would_process=%s reasons=%s",
            stats.scanned,
            stats.skipped,
            stats.dry_run_would_process,
            stats.reasons,
        )
        return stats

    for mp4 in mp4s:
        relocate_legacy_poster(mp4)

    use_client = client
    if not skip_jellyfin and jf.get("api_key"):
        use_client = use_client or JellyfinClient.from_config(cfg)
        try:
            use_client.refresh_library()
            settle = float(jf.get("refresh_settle_sec", 2))
            if settle > 0:
                sleep(settle)
        except Exception as exc:  # noqa: BLE001
            log.warning("initial library refresh failed (continuing): %s", exc)

    for mp4 in todo:
        wait_for_gate(cfg, sleep=sleep)
        log.info("backfill %s", mp4)
        try:
            result = backfill_one(
                cfg,
                mp4,
                client=use_client,
                force=force,
                sleep=sleep,
                skip_jellyfin=skip_jellyfin or not jf.get("api_key"),
            )
            stats.processed += 1
            poster = result.get("poster") or {}
            if poster.get("ok"):
                stats.extracted += 1
            img = result.get("jellyfin_image") or {}
            if img.get("ok") or img.get("status") == "uploaded":
                stats.uploaded += 1
            if result.get("status") == "processed" and img and not img.get("ok"):
                if img.get("status") not in ("metadata_only", "skipped"):
                    stats.failed += 1
        except Exception as exc:  # noqa: BLE001
            stats.failed += 1
            log.warning("backfill failed for %s: %s", mp4, exc)
        if interval_sec > 0:
            sleep(interval_sec)

    log.info(
        "backfill done: scanned=%s skipped=%s processed=%s extracted=%s uploaded=%s failed=%s",
        stats.scanned,
        stats.skipped,
        stats.processed,
        stats.extracted,
        stats.uploaded,
        stats.failed,
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    """CLI: walk catalog MP4s and backfill missing posters / Jellyfin Primary."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Backfill flock posters + Jellyfin Primary/metadata")
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    p.add_argument("--dry-run", action="store_true", help="Scan and report only")
    p.add_argument("--force", action="store_true", help="Re-process even if sidecar looks complete")
    p.add_argument("--limit", type=int, default=None, help="Max MP4s to process")
    p.add_argument(
        "--interval-sec",
        type=float,
        default=1.0,
        help="Pause between items (rate limit; default 1s)",
    )
    p.add_argument(
        "--poster-only",
        action="store_true",
        help="Extract FS posters only; skip Jellyfin API",
    )
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    stats = run_backfill(
        cfg,
        dry_run=args.dry_run,
        force=args.force,
        limit=args.limit,
        interval_sec=args.interval_sec,
        skip_jellyfin=args.poster_only,
    )
    print(json.dumps(stats.__dict__, indent=2, sort_keys=True))
    return 1 if stats.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
