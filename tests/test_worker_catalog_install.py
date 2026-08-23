"""Unit tests for catalog MP4 install / prior rotation (review P1)."""

from __future__ import annotations

from pathlib import Path

from pipeline.worker import install_catalog_mp4


def test_install_catalog_mp4_fresh(tmp_path: Path):
    src = tmp_path / "out.mp4"
    dest = tmp_path / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    dest.parent.mkdir(parents=True)
    src.write_bytes(b"new")
    install_catalog_mp4(src, dest)
    assert dest.read_bytes() == b"new"
    assert not src.exists()
    assert not dest.with_suffix(".mp4.prev").exists()


def test_install_catalog_mp4_rotates_existing(tmp_path: Path):
    dest = tmp_path / "electricsheep.247.00505.mp4"
    dest.write_bytes(b"old")
    prev = dest.with_suffix(".mp4.prev")
    prev.write_bytes(b"stale")
    src = tmp_path / "out.mp4"
    src.write_bytes(b"new")
    install_catalog_mp4(src, dest)
    assert dest.read_bytes() == b"new"
    assert prev.read_bytes() == b"old"
