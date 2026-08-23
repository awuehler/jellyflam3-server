import os
import stat
from pathlib import Path

import pytest

from pipeline.media_layout import (
    CATALOG_DIR_MODE,
    CATALOG_FILE_MODE,
    REFACTOR_PREVIEW_DIRNAME,
    ensure_catalog_dir,
    ensure_catalog_file_mode,
    ensure_refactor_preview_dir,
    repair_by_generation_perms,
)

# POSIX mode bits (setgid / group-write) are the production contract; Windows ACLs differ.
pytestmark = pytest.mark.skipif(os.name == "nt", reason="catalog mode 2775/664 is POSIX")


def test_ensure_catalog_dir_forces_2775(tmp_path: Path):
    media = tmp_path / "sheep"
    # Simulate umask-style 755 parent with setgid only (the failure mode)
    by_gen = media / "by-generation"
    by_gen.mkdir(parents=True)
    by_gen.chmod(0o2755)

    dest = ensure_catalog_dir(by_gen / "243")
    assert dest.is_dir()
    assert stat.S_IMODE(dest.stat().st_mode) == CATALOG_DIR_MODE
    assert stat.S_IMODE(by_gen.stat().st_mode) == CATALOG_DIR_MODE


def test_ensure_catalog_file_mode(tmp_path: Path):
    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")
    f.chmod(0o644)
    ensure_catalog_file_mode(f)
    assert stat.S_IMODE(f.stat().st_mode) == CATALOG_FILE_MODE


def test_repair_by_generation_perms(tmp_path: Path):
    media = tmp_path / "sheep"
    gen = media / "by-generation" / "243"
    gen.mkdir(parents=True)
    gen.chmod(0o2755)
    (media / "by-generation").chmod(0o2755)
    mp4 = gen / "electricsheep.243.1.mp4"
    mp4.write_bytes(b"mp4")
    mp4.chmod(0o644)

    stats = repair_by_generation_perms(media)
    assert stats["dir_errors"] == 0
    assert stats["file_errors"] == 0
    assert stat.S_IMODE(gen.stat().st_mode) == CATALOG_DIR_MODE
    assert stat.S_IMODE(mp4.stat().st_mode) == CATALOG_FILE_MODE


def test_ensure_refactor_preview_dir(tmp_path: Path):
    media = tmp_path / "sheep"
    media.mkdir()
    preview = ensure_refactor_preview_dir(media)
    assert preview == media / REFACTOR_PREVIEW_DIRNAME
    assert preview.is_dir()
    assert preview.name == "_refactor-preview"
    assert stat.S_IMODE(preview.stat().st_mode) == CATALOG_DIR_MODE
    # Sibling of by-generation — not nested under it (hard Jellyfin separation).
    assert "by-generation" not in preview.parts
    (media / "by-generation").mkdir()
    assert preview.resolve().parent == (media / "by-generation").resolve().parent
