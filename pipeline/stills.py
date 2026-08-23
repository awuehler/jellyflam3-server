"""Purpose: Extract screensaver stills from catalog sheep MP4s (Phase 3 guide 01).

Requirements: ffmpeg + ffprobe; configs ``stills.*``; optional idle_gate for CPU extract.

Usage:
  python3 -m pipeline.stills --config configs/jellyflam3.yaml --dry-run
  python3 -m pipeline.stills --config configs/jellyflam3.yaml --limit 5
  python3 -m pipeline.stills --sheep electricsheep.247.00505

Assumptions: Frames land under ``by-generation/{gen}/stills/{stem}/frame_XX.jpg``
(matches Shears cascade). Tag stills as screensaver-safe in sidecar. Extraction
respects idle-gate when enabled so TV playback stays responsive.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path
from pipeline.idle_gate import is_gate_open
from pipeline.media_layout import ensure_catalog_dir, ensure_catalog_file_mode
from pipeline.poster import probe_duration_sec
from pipeline.sheep_names import catalog_generation
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.stills")


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stills_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return dict(cfg.get("stills") or {})


def stills_dir_for_mp4(media_root: Path, mp4: Path) -> Path:
    """Canonical stills directory: ``by-generation/{gen}/stills/{stem}/``."""
    stem = mp4.stem
    gen = catalog_generation(stem)
    return Path(media_root) / "by-generation" / gen / "stills" / stem


def frame_path(stills_dir: Path, index: int) -> Path:
    return stills_dir / f"frame_{index:02d}.jpg"


def seek_points_sec(duration_sec: float, count: int) -> list[float]:
    """Evenly spaced seek times across the loop (midpoints of N equal segments)."""
    n = max(1, int(count))
    dur = max(0.0, float(duration_sec))
    if dur <= 0:
        return [0.0] * n
    return [(i + 0.5) / n * dur for i in range(n)]


def sidecar_path_for_mp4(mp4: Path) -> Path:
    return mp4.with_suffix(".jellyflam3.json")


def load_sidecar(mp4: Path) -> dict[str, Any]:
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
    path = sidecar_path_for_mp4(mp4)
    path.write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")


def iter_catalog_mp4s(media_root: Path) -> list[Path]:
    if not media_root.is_dir():
        return []
    # Prefer by-generation tree; skip edges if present
    root = media_root / "by-generation"
    if root.is_dir():
        return sorted(
            p
            for p in root.rglob("*.mp4")
            if p.is_file() and "/edges/" not in p.as_posix().replace("\\", "/")
        )
    return sorted(p for p in media_root.rglob("*.mp4") if p.is_file())


def existing_frame_count(stills_dir: Path) -> int:
    if not stills_dir.is_dir():
        return 0
    return sum(1 for p in stills_dir.glob("frame_*.jpg") if p.is_file() and p.stat().st_size > 0)


def extract_stills_for_mp4(
    cfg: dict[str, Any],
    mp4: Path,
    *,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Extract N JPEG frames for one catalog MP4; update sidecar ``stills`` block."""
    sc = stills_cfg(cfg)
    count = max(1, int(sc.get("count", 4)))
    q = int(sc.get("jpeg_quality", 2))
    media_root = resolve_path(cfg, "media_library")
    dest_dir = stills_dir_for_mp4(media_root, mp4)
    have = existing_frame_count(dest_dir)
    if have >= count and not force:
        return {
            "ok": True,
            "status": "already_complete",
            "sheep": mp4.stem,
            "dir": str(dest_dir),
            "count": have,
            "screensaver_safe": True,
        }

    ffmpeg = _tool(cfg, "ffmpeg")
    ffprobe = _tool(cfg, "ffprobe")
    sidecar = load_sidecar(mp4)
    dur = sidecar.get("duration_sec")
    try:
        duration = float(dur) if dur is not None else probe_duration_sec(ffprobe, mp4)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "probe_failed",
            "sheep": mp4.stem,
            "error": str(exc),
        }

    seeks = seek_points_sec(duration, count)
    result: dict[str, Any] = {
        "ok": True,
        "status": "extracted",
        "sheep": mp4.stem,
        "dir": str(dest_dir),
        "count": count,
        "duration_sec": duration,
        "seeks": seeks,
        "screensaver_safe": True,
        "paths": [],
    }

    if dry_run:
        result["status"] = "dry_run"
        result["paths"] = [str(frame_path(dest_dir, i)) for i in range(count)]
        return result

    ensure_catalog_dir(dest_dir)
    written: list[str] = []
    for i, seek in enumerate(seeks):
        out = frame_path(dest_dir, i)
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{seek:.3f}",
            "-i",
            str(mp4),
            "-frames:v",
            "1",
            "-q:v",
            str(q),
            str(out),
        ]
        log.info("stills extract: %s", " ".join(cmd))
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as exc:
            return {
                "ok": False,
                "status": "ffmpeg_failed",
                "sheep": mp4.stem,
                "error": (exc.stderr or b"").decode("utf-8", errors="replace")[:400],
                "frame": i,
            }
        if not out.is_file() or out.stat().st_size <= 0:
            return {
                "ok": False,
                "status": "empty_frame",
                "sheep": mp4.stem,
                "frame": i,
                "path": str(out),
            }
        ensure_catalog_file_mode(out)
        written.append(str(out))

    result["paths"] = written
    sidecar["stills"] = {
        "ok": True,
        "status": "extracted",
        "count": len(written),
        "dir": str(dest_dir),
        "paths": [Path(p).name for p in written],
        "screensaver_safe": True,
        "extracted_at": _utc_now(),
    }
    write_sidecar(mp4, sidecar)
    return result


@dataclass
class StillsStats:
    scanned: int = 0
    skipped: int = 0
    extracted: int = 0
    failed: int = 0
    dry_run: int = 0
    gate_blocked: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def bump(self, reason: str) -> None:
        self.reasons[reason] = self.reasons.get(reason, 0) + 1


def run_backfill(
    cfg: dict[str, Any],
    *,
    limit: int | None = None,
    force: bool = False,
    dry_run: bool = False,
    sheep: str | None = None,
) -> dict[str, Any]:
    """Walk catalog MP4s and extract stills (honors idle-gate when configured)."""
    sc = stills_cfg(cfg)
    if not bool(sc.get("enabled", True)):
        return {"ok": False, "error": "stills.enabled is false"}

    media_root = resolve_path(cfg, "media_library")
    respect_gate = bool(sc.get("respect_idle_gate", True))
    stats = StillsStats()
    results: list[dict[str, Any]] = []

    mp4s = iter_catalog_mp4s(media_root)
    if sheep:
        needle = sheep.lower().removesuffix(".mp4").removesuffix(".flam3")
        mp4s = [p for p in mp4s if needle in p.stem.lower()]

    for mp4 in mp4s:
        if limit is not None and stats.extracted + stats.dry_run + stats.failed >= limit:
            break
        stats.scanned += 1
        if respect_gate and not dry_run and not is_gate_open(cfg):
            stats.gate_blocked += 1
            stats.bump("gate_closed")
            log.info("stills: idle-gate closed — stop after %s", mp4.name)
            break

        out = extract_stills_for_mp4(cfg, mp4, force=force, dry_run=dry_run)
        results.append(out)
        if out.get("status") == "already_complete":
            stats.skipped += 1
            stats.bump("already_complete")
        elif out.get("status") == "dry_run":
            stats.dry_run += 1
        elif out.get("ok"):
            stats.extracted += 1
            stats.bump("extracted")
        else:
            stats.failed += 1
            stats.bump(str(out.get("status") or "failed"))

    return {
        "ok": stats.failed == 0,
        "stats": {
            "scanned": stats.scanned,
            "skipped": stats.skipped,
            "extracted": stats.extracted,
            "failed": stats.failed,
            "dry_run": stats.dry_run,
            "gate_blocked": stats.gate_blocked,
            "reasons": stats.reasons,
        },
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Extract screensaver stills (Phase 3 guide 01)")
    ap.add_argument("--config", default="configs/jellyflam3.yaml")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sheep", default=None, help="Substring filter on catalog stem")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    summary = run_backfill(
        cfg,
        limit=args.limit,
        force=args.force,
        dry_run=args.dry_run,
        sheep=args.sheep,
    )
    print(json.dumps(summary, indent=2))
    return 0 if summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
