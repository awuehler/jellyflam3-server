"""FIFO inbox claim: arrival order, not filename order."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pipeline.inbox_queue import inbox_fifo_path, stamp_inbox_arrival, sync_inbox_fifo
from pipeline.seed_inbox import stage_file
from pipeline.worker import poll_inbox


def test_new_file_with_early_name_and_old_mtime_goes_to_tail(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ledger = tmp_path / "inbox_fifo.json"
    waiting = inbox / "electricsheep.tuple.late.flam3"
    waiting.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(waiting)
    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == [waiting.name]

    jumper = inbox / "a.flam3"
    jumper.write_text("<flame/>", encoding="utf-8")
    os.utime(jumper, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    queued = [p.name for p in sync_inbox_fifo(inbox, ledger)]
    assert queued == [waiting.name, jumper.name]


def test_same_scan_batch_follows_stamp_not_ascii(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ledger = tmp_path / "inbox_fifo.json"
    anchor = inbox / "anchor.flam3"
    anchor.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(anchor)
    sync_inbox_fifo(inbox, ledger)

    later_name = inbox / "z.flam3"
    early_name = inbox / "a.flam3"
    later_name.write_text("<flame/>", encoding="utf-8")
    early_name.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(later_name)
    stamp_inbox_arrival(early_name)

    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == [
        "anchor.flam3",
        "z.flam3",
        "a.flam3",
    ]


def test_flame_is_not_held_behind_every_flam3(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ledger = tmp_path / "inbox_fifo.json"
    anchor = inbox / "anchor.flam3"
    anchor.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(anchor)
    sync_inbox_fifo(inbox, ledger)

    flame = inbox / "first.flame"
    flam3 = inbox / "second.flam3"
    flame.write_text("<flame/>", encoding="utf-8")
    flam3.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(flame)
    stamp_inbox_arrival(flam3)
    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == [
        "anchor.flam3",
        "first.flame",
        "second.flam3",
    ]


def test_removed_genome_is_forgotten(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ledger = tmp_path / "inbox_fifo.json"
    first = inbox / "first.flam3"
    second = inbox / "second.flam3"
    first.write_text("1", encoding="utf-8")
    second.write_text("2", encoding="utf-8")
    stamp_inbox_arrival(first)
    stamp_inbox_arrival(second)
    sync_inbox_fifo(inbox, ledger)
    first.unlink()
    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == ["second.flam3"]
    # A new file must not reuse the removed sequence slot in front of second.
    third = inbox / "aaa.flam3"
    third.write_text("3", encoding="utf-8")
    stamp_inbox_arrival(third)
    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == [
        "second.flam3",
        "aaa.flam3",
    ]


def test_replaced_inode_is_a_new_arrival(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ledger = tmp_path / "inbox_fifo.json"
    early = inbox / "a.flam3"
    other = inbox / "b.flam3"
    early.write_text("old", encoding="utf-8")
    other.write_text("b", encoding="utf-8")
    stamp_inbox_arrival(early)
    stamp_inbox_arrival(other)
    sync_inbox_fifo(inbox, ledger)
    before = early.stat().st_ino
    early.unlink()
    early.write_text("new", encoding="utf-8")
    if early.stat().st_ino == before:
        pytest.skip("filesystem reused the inode")
    stamp_inbox_arrival(early)
    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == ["b.flam3", "a.flam3"]


def test_order_is_stable_across_scans(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ledger = tmp_path / "inbox_fifo.json"
    for name in ("b.flam3", "a.flam3"):
        path = inbox / name
        path.write_text(name, encoding="utf-8")
        stamp_inbox_arrival(path)
        sync_inbox_fifo(inbox, ledger)
    again = [p.name for p in sync_inbox_fifo(inbox, ledger)]
    assert again == ["b.flam3", "a.flam3"]


def test_empty_inbox_does_not_write_ledger(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ledger = tmp_path / "inbox_fifo.json"
    assert sync_inbox_fifo(inbox, ledger) == []
    assert not ledger.exists()


def test_poster_is_not_queued(tmp_path: Path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "sheep-poster.jpg").write_text("jpg", encoding="utf-8")
    genome = inbox / "sheep.flam3"
    genome.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(genome)
    assert [p.name for p in sync_inbox_fifo(inbox, tmp_path / "ledger.json")] == ["sheep.flam3"]


def test_stage_file_stamps_over_preserved_mtime(tmp_path: Path):
    inbox = tmp_path / "inbox"
    src = tmp_path / "electricsheep.247.00505.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    os.utime(src, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))
    dest = stage_file(src, inbox)
    assert dest is not None
    assert dest.stat().st_mtime_ns > src.stat().st_mtime_ns


def test_inbox_fifo_path_beside_drain_file(tmp_path: Path):
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {"worker_drain_file": str(tmp_path / "state" / "worker_drain.json")},
    }
    assert inbox_fifo_path(cfg) == tmp_path / "state" / "inbox_fifo.json"


def test_poll_inbox_claims_oldest_not_ascii(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    ledger = tmp_path / "inbox_fifo.json"
    waiting = inbox / "z-arrived-first.flam3"
    waiting.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(waiting)
    sync_inbox_fifo(inbox, ledger)

    jumper = inbox / "a-sorts-first.flam3"
    jumper.write_text("<flame/>", encoding="utf-8")
    os.utime(jumper, ns=(1_000_000_000_000_000_000, 1_000_000_000_000_000_000))

    seen: list[str] = []

    def fake_process(_cfg, src: Path) -> Path:
        seen.append(src.name)
        src.unlink()
        return tmp_path / "out.mp4"

    def stop_sleep(_sec: float) -> None:
        raise RuntimeError("idle")

    monkeypatch.setattr("pipeline.worker.process_genome", fake_process)
    monkeypatch.setattr("pipeline.worker.archive_rendered_genome", lambda *_a, **_k: None)
    monkeypatch.setattr("pipeline.worker.time.sleep", stop_sleep)
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": str(inbox),
            "genomes_quarantine": str(tmp_path / "quarantine"),
            "worker_drain_file": str(tmp_path / "worker_drain.json"),
        },
        "worker": {"reclaim_orphans_on_start": False},
        "idle_gate": {"enabled": False},
    }
    with pytest.raises(RuntimeError, match="idle"):
        poll_inbox(cfg)
    assert seen == ["z-arrived-first.flam3", "a-sorts-first.flam3"]
