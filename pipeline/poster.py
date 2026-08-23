"""Purpose: Extract mid-loop poster JPEGs beside catalog MP4s.

Requirements: ffmpeg (and ffprobe when duration is not passed).

Usage: ``extract_mid_loop_poster(ffmpeg=…, mp4=…, …)`` from flock artwork / backfill.

Assumptions: Jellyfin-friendly sibling name ``{stem}-poster.jpg``; seek at half duration.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("jellyflam3.poster")


def poster_path_for_mp4(mp4: Path) -> Path:
    """Jellyfin-friendly sibling: ``{stem}-poster.jpg`` next to the MP4."""
    return mp4.with_name(f"{mp4.stem}-poster.jpg")


def mid_loop_seek_sec(duration_sec: float) -> float:
    """Seek target for a representative mid-loop frame."""
    if duration_sec <= 0:
        return 0.0
    return max(0.0, float(duration_sec) / 2.0)


def probe_duration_sec(ffprobe: str, media: Path) -> float:
    """Return media duration in seconds via ffprobe format.duration."""
    out = subprocess.check_output(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media),
        ],
        text=True,
    ).strip()
    return float(out)


def extract_mid_loop_poster(
    *,
    ffmpeg: str,
    mp4: Path,
    dest: Path | None = None,
    duration_sec: float | None = None,
    ffprobe: str | None = None,
) -> Path:
    """Write a mid-loop JPEG beside ``mp4`` (or to ``dest``) and return its path.

    Does not upload to Jellyfin (Images API is a later flock-UX piece).
    """
    mp4 = Path(mp4)
    if not mp4.is_file():
        raise FileNotFoundError(f"MP4 not found: {mp4}")

    out = Path(dest) if dest is not None else poster_path_for_mp4(mp4)
    out.parent.mkdir(parents=True, exist_ok=True)

    dur = duration_sec
    if dur is None:
        if not ffprobe:
            raise ValueError("duration_sec or ffprobe is required")
        dur = probe_duration_sec(ffprobe, mp4)

    seek = mid_loop_seek_sec(dur)
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
        "2",
        str(out),
    ]
    log.info("poster extract: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True)
    if not out.is_file() or out.stat().st_size <= 0:
        raise RuntimeError(f"poster extract produced empty file: {out}")
    return out
