"""Inbox claim + quarantine hard-fail (review P5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.worker import claim_inbox_genome, quarantine_genome


def test_claim_inbox_genome_moves_atomically(tmp_path: Path):
    inbox = tmp_path / "inbox"
    work = tmp_path / "job"
    inbox.mkdir()
    work.mkdir()
    src = inbox / "electricsheep.247.00505.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    claimed = claim_inbox_genome(src, work, inbox)
    assert claimed == work / src.name
    assert claimed.is_file()
    assert not src.exists()


def test_claim_inbox_genome_leaves_non_inbox(tmp_path: Path):
    inbox = tmp_path / "inbox"
    other = tmp_path / "other"
    work = tmp_path / "job"
    inbox.mkdir()
    other.mkdir()
    work.mkdir()
    src = other / "x.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    claimed = claim_inbox_genome(src, work, inbox)
    assert claimed == src
    assert src.is_file()


def test_quarantine_genome_raises_on_failure(tmp_path: Path, monkeypatch):
    src = tmp_path / "x.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    q = tmp_path / "q"
    q.mkdir()

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr("pipeline.worker.shutil.copy2", boom)
    with pytest.raises(RuntimeError, match="quarantine copy failed"):
        quarantine_genome(src, q)
