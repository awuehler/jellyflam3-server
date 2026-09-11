"""Purpose: Extract mid-loop poster JPEGs into the catalog stills folder.

Requirements: ffmpeg (and ffprobe when duration is not passed).

Usage: ``extract_mid_loop_poster(ffmpeg=…, mp4=…, …)`` from flock artwork / backfill.

Assumptions: Canonical path is ``by-generation/{gen}/stills/{stem}/{stem}-poster.jpg``
(same folder as screensaver frames). Legacy sibling ``{stem}-poster.jpg`` next to the
MP4 is relocated on backfill. Parked quarantine/preview trees keep a sibling poster.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from pipeline.media_layout import ensure_stills_dir, is_unpublished_media_path, stills_dir_for_mp4

log = logging.getLogger("jellyflam3.poster")


def poster_filename(stem: str) -> str:
    return f"{stem}-poster.jpg"


def legacy_poster_path_for_mp4(mp4: Path) -> Path:
    """Pre-consolidation sibling: ``{stem}-poster.jpg`` next to the MP4."""
    mp4 = Path(mp4)
    return mp4.with_name(poster_filename(mp4.stem))


def _media_root_from_catalog_mp4(mp4: Path) -> Path | None:
    parts = Path(mp4).parts
    if "by-generation" not in parts:
        return None
    idx = parts.index("by-generation")
    if idx == 0:
        return Path(".")
    root = Path(parts[0])
    for part in parts[1:idx]:
        root /= part
    return root


def poster_path_for_mp4(mp4: Path, *, media_root: Path | None = None) -> Path:
    """Canonical poster: ``stills/{stem}/{stem}-poster.jpg`` (sibling if unpublished)."""
    mp4 = Path(mp4)
    name = poster_filename(mp4.stem)
    if is_unpublished_media_path(mp4):
        return mp4.with_name(name)
    root = media_root if media_root is not None else _media_root_from_catalog_mp4(mp4)
    if root is not None:
        return stills_dir_for_mp4(root, mp4) / name
    return mp4.parent / "stills" / mp4.stem / name


def resolve_poster_path(mp4: Path, *, media_root: Path | None = None) -> Path:
    """Existing poster path: canonical stills file, else legacy sibling, else canonical."""
    canonical = poster_path_for_mp4(mp4, media_root=media_root)
    if canonical.is_file() and canonical.stat().st_size > 0:
        return canonical
    legacy = legacy_poster_path_for_mp4(mp4)
    if legacy.is_file() and legacy.stat().st_size > 0:
        return legacy
    return canonical


def relocate_legacy_poster(mp4: Path, *, media_root: Path | None = None) -> Path | None:
    """Move a sibling ``{stem}-poster.jpg`` into the stills folder. Returns dest if present."""
    dest = poster_path_for_mp4(mp4, media_root=media_root)
    legacy = legacy_poster_path_for_mp4(mp4)
    try:
        if dest.exists() and legacy.exists() and dest.resolve() == legacy.resolve():
            return dest
    except OSError:
        pass
    if dest.is_file() and dest.stat().st_size > 0:
        if legacy.is_file() and legacy != dest:
            try:
                legacy.unlink()
            except OSError as exc:
                log.warning("legacy poster remove failed %s: %s", legacy, exc)
        return dest
    if not legacy.is_file() or legacy.stat().st_size <= 0:
        return dest if dest.is_file() else None
    _ensure_poster_parent(mp4, dest)
    try:
        shutil.move(str(legacy), str(dest))
    except OSError as exc:
        log.warning("legacy poster move failed %s -> %s: %s", legacy, dest, exc)
        return legacy if legacy.is_file() else None
    return dest


def _ensure_poster_parent(mp4: Path, dest: Path) -> None:
    """Create the stills folder (+ Jellyfin ``.ignore``) for live catalog posters."""
    if dest.parent.name == Path(mp4).stem and dest.parent.parent.name == "stills":
        ensure_stills_dir(dest.parent)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)


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
    """Write a mid-loop JPEG into the stills folder (or to ``dest``) and return its path.

    Does not upload to Jellyfin (Images API is ``flock_artwork`` / ``backfill_posters``).
    """
    mp4 = Path(mp4)
    if not mp4.is_file():
        raise FileNotFoundError(f"MP4 not found: {mp4}")

    out = Path(dest) if dest is not None else poster_path_for_mp4(mp4)
    _ensure_poster_parent(mp4, out)

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
