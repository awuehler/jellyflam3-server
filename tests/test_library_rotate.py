"""Unit tests for pipeline.library_rotate (Shears cascade, floor, git feedstock)."""

from __future__ import annotations

from pathlib import Path

from pipeline.library_disk import _Usage, sheep_mount_should_refuse
from pipeline.library_rotate import catalog_rotate_candidates, run_rotate
from pipeline.shears import discover_cascade, drop_git_feedstock_from_cascade


GiB = 1024**3


def _usage(*, total_gb: float, used_gb: float) -> _Usage:
    total = int(total_gb * GiB)
    used = int(used_gb * GiB)
    return _Usage(total=total, used=used, free=total - used)


def _cfg(tmp: Path, **disk) -> dict:
    media = tmp / "media"
    inbox = tmp / "genomes" / "inbox"
    done = tmp / "genomes" / "done"
    peers = tmp / "genomes" / "peers"
    for d in (
        media / "by-generation" / "247",
        inbox,
        done,
        tmp / "genomes" / "quarantine",
        tmp / "jobs",
        tmp / "frames",
        peers / "inbox",
        peers / "share-out",
        tmp / "genomes" / "samples",
        tmp / "genomes" / "pedigree",
    ):
        d.mkdir(parents=True, exist_ok=True)
    block = {
        "check_scratch": False,
        "rotate_enabled": True,
        "rotate_floor": 1,
        "rotate_max_per_run": 8,
        "rotate_until": "ok",
        "worker_refuse_on_sheep_bad": True,
    }
    block.update(disk)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "genomes_inbox": str(inbox),
            "genomes_quarantine": str(tmp / "genomes" / "quarantine"),
            "genomes_done": str(done),
            "jobs_dir": str(tmp / "jobs"),
            "frames_scratch": str(tmp / "frames"),
            "media_library": str(media),
        },
        "peering": {
            "peers_dir": str(peers),
            "peers_inbox": str(peers / "inbox"),
        },
        "jellyfin": {"url": "", "api_key": ""},
        "library_disk": block,
    }


def _mp4(cfg: dict, stem: str, *, mtime: float) -> Path:
    media = Path(cfg["paths"]["media_library"])
    cat = media / "by-generation" / "247"
    cat.mkdir(parents=True, exist_ok=True)
    mp4 = cat / f"{stem}.mp4"
    mp4.write_bytes(b"mp4")
    import os

    os.utime(mp4, (mtime, mtime))
    return mp4


def test_candidates_oldest_mtime_first(tmp_path: Path):
    cfg = _cfg(tmp_path)
    a = _mp4(cfg, "electricsheep.247.00001", mtime=200.0)
    b = _mp4(cfg, "electricsheep.247.00002", mtime=100.0)
    order = catalog_rotate_candidates(cfg)
    assert order == [b, a]


def test_plan_skips_when_under_threshold(tmp_path: Path):
    cfg = _cfg(tmp_path)
    _mp4(cfg, "electricsheep.247.00001", mtime=1.0)
    media = str(Path(cfg["paths"]["media_library"]))
    out = run_rotate(cfg, apply=False, usage_for={media: _usage(total_gb=100, used_gb=10)})
    assert out["action"] == "skip"
    assert out["reason"] == "under_threshold"
    assert out["planned"] == []


def test_plan_oldest_and_keeps_floor(tmp_path: Path):
    cfg = _cfg(tmp_path, rotate_floor=1, rotate_max_per_run=8)
    old = _mp4(cfg, "electricsheep.247.00001", mtime=10.0)
    _mp4(cfg, "electricsheep.247.00002", mtime=20.0)
    media = str(Path(cfg["paths"]["media_library"]))
    out = run_rotate(cfg, apply=False, usage_for={media: _usage(total_gb=100, used_gb=96)})
    assert out["action"] == "plan"
    assert [e["stem"] for e in out["planned"]] == ["electricsheep.247.00001"]
    assert out["remaining"] == 1
    assert old.is_file()


def test_floor_blocks_when_at_floor(tmp_path: Path):
    cfg = _cfg(tmp_path, rotate_floor=2)
    _mp4(cfg, "electricsheep.247.00001", mtime=10.0)
    _mp4(cfg, "electricsheep.247.00002", mtime=20.0)
    media = str(Path(cfg["paths"]["media_library"]))
    out = run_rotate(cfg, apply=False, usage_for={media: _usage(total_gb=100, used_gb=96)})
    assert out["reason"] == "floor"
    assert out["planned"] == []


def test_disabled_skip(tmp_path: Path):
    cfg = _cfg(tmp_path, rotate_enabled=False)
    _mp4(cfg, "electricsheep.247.00001", mtime=10.0)
    media = str(Path(cfg["paths"]["media_library"]))
    out = run_rotate(cfg, apply=True, usage_for={media: _usage(total_gb=100, used_gb=96)})
    assert out["reason"] == "disabled"
    assert out["action"] == "skip"


def test_apply_deletes_catalog_keeps_git_feedstock(tmp_path: Path):
    cfg = _cfg(tmp_path)
    stem = "electricsheep.247.00505"
    mp4 = _mp4(cfg, stem, mtime=10.0)
    _mp4(cfg, "electricsheep.247.00999", mtime=99.0)
    sample = Path(cfg["_repo_root"]) / "genomes" / "samples" / f"{stem}.flam3"
    sample.write_text("<flame/>", encoding="utf-8")
    report = drop_git_feedstock_from_cascade(cfg, discover_cascade(cfg, stem))
    assert sample not in report.genomes
    assert sample.is_file()
    media = str(Path(cfg["paths"]["media_library"]))
    out = run_rotate(cfg, apply=True, usage_for={media: _usage(total_gb=100, used_gb=96)})
    assert out["action"] == "rotate"
    assert not mp4.is_file()
    assert sample.is_file()


def test_worker_refuse_bad_only(tmp_path: Path):
    cfg = _cfg(tmp_path)
    media = str(Path(cfg["paths"]["media_library"]))
    Path(media).mkdir(parents=True, exist_ok=True)
    assert sheep_mount_should_refuse(cfg, usage_for={media: _usage(total_gb=100, used_gb=96)})
    assert not sheep_mount_should_refuse(cfg, usage_for={media: _usage(total_gb=100, used_gb=81)})
    cfg["library_disk"]["worker_refuse_on_sheep_bad"] = False
    assert not sheep_mount_should_refuse(cfg, usage_for={media: _usage(total_gb=100, used_gb=96)})
