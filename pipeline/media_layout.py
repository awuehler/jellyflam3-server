"""Purpose: Sheep library filesystem layout helpers (Jellyfin-writable catalog dirs).

Requirements: Permission to chmod under the media library (often root/setgid jellyflam3 group).

Usage:
  ensure_catalog_dir / ensure_catalog_file_mode from the worker
  python -m pipeline.media_layout [--media-root PATH]

Assumptions: Catalog dirs need ``2775`` (setgid+group-write) so Jellyfin can create ``*.trickplay`` siblings; files ``664``.
"""

from __future__ import annotations

import argparse
import logging
import os
import stat
import sys
from pathlib import Path

log = logging.getLogger("jellyflam3.media_layout")

# setgid (0o2000) + rwxrwxr-x
CATALOG_DIR_MODE = 0o2775
CATALOG_FILE_MODE = 0o664

# Sibling of by-generation/; Jellyfin Rework Poster library root (hard-separated from Sheep).
REFACTOR_PREVIEW_DIRNAME = "_refactor-preview"
# Unpublished catalog holding area (genetics stay in genomes_quarantine; files not deleted).
REFACTOR_QUARANTINE_DIRNAME = "_refactor-quarantine"


def ensure_refactor_preview_dir(media_root: Path) -> Path:
    """Create ``media_root/_refactor-preview`` with catalog dir mode (Jellyfin-writable)."""
    preview = Path(media_root) / REFACTOR_PREVIEW_DIRNAME
    preview.mkdir(parents=True, exist_ok=True)
    _try_chmod_dir(preview)
    return preview


def ensure_refactor_quarantine_dir(media_root: Path) -> Path:
    """Create ``media_root/_refactor-quarantine`` for unpublished catalog artifacts."""
    q = Path(media_root) / REFACTOR_QUARANTINE_DIRNAME
    q.mkdir(parents=True, exist_ok=True)
    _try_chmod_dir(q)
    return q


def _try_chmod_dir(path: Path) -> bool:
    """Best-effort set CATALOG_DIR_MODE on an existing directory; log and return False on OSError."""
    try:
        if not path.is_dir():
            return False
        if stat.S_IMODE(path.stat().st_mode) != CATALOG_DIR_MODE:
            path.chmod(CATALOG_DIR_MODE)
        return True
    except OSError as exc:
        log.warning("chmod %#o %s failed: %s", CATALOG_DIR_MODE, path, exc)
        return False


def ensure_catalog_dir(path: Path) -> Path:
    """Create ``path`` (and parents) and force group-writable setgid mode.

    Chmods ``path`` and each ancestor up to and including ``by-generation``.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    _try_chmod_dir(path)
    for parent in path.parents:
        _try_chmod_dir(parent)
        if parent.name == "by-generation":
            break
    return path


def ensure_catalog_file_mode(path: Path) -> None:
    """Best-effort ``664`` on a catalog file (MP4 / poster / sidecar)."""
    path = Path(path)
    if not path.is_file():
        return
    try:
        if stat.S_IMODE(path.stat().st_mode) != CATALOG_FILE_MODE:
            path.chmod(CATALOG_FILE_MODE)
    except OSError as exc:
        log.warning("chmod %#o %s failed: %s", CATALOG_FILE_MODE, path, exc)


def repair_by_generation_perms(media_root: Path) -> dict[str, int]:
    """Walk ``media_root/by-generation`` and enforce catalog dir/file modes.

    Skips ``lost+found``. Returns counts of dirs/files considered and errors.
    """
    root = Path(media_root) / "by-generation"
    stats = {"dirs": 0, "files": 0, "dir_errors": 0, "file_errors": 0}
    if not root.is_dir():
        return stats

    if not _try_chmod_dir(root):
        stats["dir_errors"] += 1
    else:
        stats["dirs"] += 1

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip Jellyfin-owned trickplay trees (and lost+found)
        dirnames[:] = [
            d
            for d in dirnames
            if d != "lost+found" and not d.endswith(".trickplay")
        ]
        p = Path(dirpath)
        if p.name.endswith(".trickplay") or any(
            part.endswith(".trickplay") for part in p.parts
        ):
            dirnames[:] = []
            continue
        if p != root:
            if _try_chmod_dir(p):
                stats["dirs"] += 1
            else:
                stats["dir_errors"] += 1
        for name in filenames:
            if name.endswith(".trickplay"):
                continue
            fp = p / name
            try:
                if not fp.is_file():
                    continue
                if stat.S_IMODE(fp.stat().st_mode) != CATALOG_FILE_MODE:
                    fp.chmod(CATALOG_FILE_MODE)
                stats["files"] += 1
            except OSError as exc:
                log.warning("chmod %#o %s failed: %s", CATALOG_FILE_MODE, fp, exc)
                stats["file_errors"] += 1
    return stats


def main(argv: list[str] | None = None) -> int:
    """CLI: repair catalog directory/file modes under media_library."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Repair JellyFlam3 sheep catalog permissions")
    ap.add_argument("--config", default="configs/jellyflam3.yaml")
    ap.add_argument(
        "--media-root",
        type=Path,
        help="Override media library root (default: paths.media_library from config)",
    )
    args = ap.parse_args(argv)

    if args.media_root:
        media = args.media_root
    else:
        from pipeline.config import load_config, resolve_path

        cfg = load_config(args.config)
        media = resolve_path(cfg, "media_library")

    stats = repair_by_generation_perms(media)
    preview = ensure_refactor_preview_dir(media)
    print(
        f"repaired {media / 'by-generation'}: "
        f"dirs={stats['dirs']} files={stats['files']} "
        f"dir_errors={stats['dir_errors']} file_errors={stats['file_errors']}"
    )
    print(f"ensured preview dir {preview} (Jellyfin Rework Poster library root)")
    return 1 if stats["dir_errors"] or stats["file_errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
