"""Tests for Phase 3 JellyFlam3 Hammer (local factory reset)."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.hammer import (
    CONFIRM_TOKEN,
    apply_plan,
    build_plan,
    confirm_tokens,
    resolve_tier,
    run_hammer,
)


def _cfg(tmp: Path) -> dict:
    media = tmp / "media"
    inbox = tmp / "genomes" / "inbox"
    quarantine = tmp / "genomes" / "quarantine"
    done = tmp / "genomes" / "done"
    jobs = tmp / "jobs"
    frames = tmp / "frames"
    logs = tmp / "logs"
    peers = tmp / "genomes" / "peers"
    samples = tmp / "genomes" / "samples"
    pedigree = tmp / "genomes" / "pedigree"
    for d in (
        media / "by-generation" / "247",
        inbox,
        quarantine,
        done,
        jobs / "job1",
        frames / "job1",
        logs,
        peers / "inbox",
        samples,
        pedigree,
    ):
        d.mkdir(parents=True, exist_ok=True)
    (inbox / "electricsheep.247.00505.flam3").write_text("<flame/>", encoding="utf-8")
    (inbox / ".gitkeep").write_text("", encoding="utf-8")
    (quarantine / "bad.flam3").write_text("<flame/>", encoding="utf-8")
    (done / "electricsheep.247.00505.flam3").write_text("<flame/>", encoding="utf-8")
    (jobs / "job1" / "job.json").write_text("{}", encoding="utf-8")
    (frames / "job1" / "0001.png").write_bytes(b"png")
    (logs / "worker.log").write_text("log\n", encoding="utf-8")
    cat = media / "by-generation" / "247"
    (cat / "electricsheep.247.00505.mp4").write_bytes(b"mp4")
    (cat / "electricsheep.247.00505.jellyflam3.json").write_text("{}", encoding="utf-8")
    stills = cat / "stills" / "electricsheep.247.00505"
    stills.mkdir(parents=True)
    (stills / "frame_00.jpg").write_bytes(b"jpg")
    (samples / "keep-me.flam3").write_text("<flame/>", encoding="utf-8")
    (pedigree / "keep-me.flam3").write_text("<flame/>", encoding="utf-8")
    (tmp / "secrets.env").write_text("JELLYFIN_API_KEY=secret\n", encoding="utf-8")
    (tmp / "configs").mkdir(exist_ok=True)
    (tmp / "configs" / "jellyflam3.yaml").write_text("paths: {}\n", encoding="utf-8")
    status = tmp / "idle_gate_status.json"
    status.write_text(json.dumps({"gate": "closed"}), encoding="utf-8")
    return {
        "_repo_root": str(tmp),
        "paths": {
            "genomes_inbox": str(inbox),
            "genomes_quarantine": str(quarantine),
            "genomes_done": str(done),
            "jobs_dir": str(jobs),
            "frames_scratch": str(frames),
            "media_library": str(media),
            "log_dir": str(logs),
            "status_file": str(status),
        },
        "peering": {
            "peers_dir": str(peers),
            "peers_inbox": str(peers / "inbox"),
        },
        "idle_gate": {"worker_unit": "jellyflam3-worker.service"},
        "jellyfin": {"url": "", "api_key": ""},
    }


def test_confirm_tokens_include_hammer():
    assert CONFIRM_TOKEN in confirm_tokens()


def test_resolve_tier_default_all():
    ns = type("NS", (), {"worker": False, "inputs": False, "outputs": False, "all": False})()
    assert resolve_tier(ns) == "all"


def test_dry_run_does_not_delete(tmp_path: Path):
    cfg = _cfg(tmp_path)
    plan = build_plan(cfg, tier="all")
    names = {c.name for c in plan.classes}
    assert "jobs" in names
    assert "genomes_inbox" in names
    assert "media_library" in names
    assert sum(c.file_count for c in plan.classes) > 0
    apply_plan(cfg, plan, dry_run=True)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    assert (inbox / "electricsheep.247.00505.flam3").is_file()
    media = Path(cfg["paths"]["media_library"])
    assert (media / "by-generation" / "247" / "electricsheep.247.00505.mp4").is_file()


def test_wrong_confirm_is_error(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr("pipeline.hammer.is_worker_active", lambda _c: False)
    rc = run_hammer(
        cfg,
        tier="worker",
        confirm="DELETE",
        force_stop=False,
        peers_inbox=False,
        transcode_cache=False,
        as_json=True,
    )
    assert rc == 2
    assert (Path(cfg["paths"]["jobs_dir"]) / "job1" / "job.json").is_file()


def test_worker_tier_keeps_inbox_and_media(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr("pipeline.hammer.is_worker_active", lambda _c: False)
    monkeypatch.setattr("pipeline.hammer.stop_worker_unit", lambda _c: None)
    plan = build_plan(cfg, tier="worker")
    apply_plan(cfg, plan, dry_run=False)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    assert (inbox / "electricsheep.247.00505.flam3").is_file()
    media = Path(cfg["paths"]["media_library"])
    assert (media / "by-generation" / "247" / "electricsheep.247.00505.mp4").is_file()
    jobs = Path(cfg["paths"]["jobs_dir"])
    assert not (jobs / "job1").exists()
    frames = Path(cfg["paths"]["frames_scratch"])
    assert not (frames / "job1").exists()
    assert jobs.is_dir()
    status = Path(cfg["paths"]["status_file"])
    data = json.loads(status.read_text(encoding="utf-8"))
    assert data["gate"] == "open"
    assert data["reason"] == "hammer"


def test_all_empties_inbox_media_keeps_samples(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr("pipeline.hammer.is_worker_active", lambda _c: False)
    monkeypatch.setattr("pipeline.hammer.stop_worker_unit", lambda _c: None)
    plan = build_plan(cfg, tier="all")
    apply_plan(cfg, plan, dry_run=False)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    assert not (inbox / "electricsheep.247.00505.flam3").exists()
    assert (inbox / ".gitkeep").is_file()
    assert inbox.is_dir()
    media = Path(cfg["paths"]["media_library"])
    assert not (media / "by-generation" / "247" / "electricsheep.247.00505.mp4").exists()
    assert (media / "by-generation").is_dir()
    root = Path(cfg["_repo_root"])
    assert (root / "genomes" / "samples" / "keep-me.flam3").is_file()
    assert (root / "genomes" / "pedigree" / "keep-me.flam3").is_file()
    assert (root / "secrets.env").is_file()
    assert (root / "configs" / "jellyflam3.yaml").is_file()
    done = Path(cfg["paths"]["genomes_done"])
    assert not (done / "electricsheep.247.00505.flam3").exists()


def test_active_worker_blocks_without_force_stop(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr("pipeline.hammer.is_worker_active", lambda _c: True)
    rc = run_hammer(
        cfg,
        tier="worker",
        confirm=CONFIRM_TOKEN,
        force_stop=False,
        peers_inbox=False,
        transcode_cache=False,
        as_json=True,
    )
    assert rc == 2
    assert (Path(cfg["paths"]["jobs_dir"]) / "job1" / "job.json").is_file()


def test_forbidden_media_root_raises(tmp_path: Path):
    cfg = _cfg(tmp_path)
    cfg["paths"]["media_library"] = "/"
    try:
        build_plan(cfg, tier="all")
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "forbidden" in str(exc).lower()
