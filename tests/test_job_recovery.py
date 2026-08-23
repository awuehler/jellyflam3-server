import json
from pathlib import Path

from pipeline.job_recovery import (
    JobRecord,
    catalog_mp4_for_base,
    is_orphan,
    reclaim_job,
    reclaim_orphans,
)


def _cfg(tmp: Path) -> dict:
    media = tmp / "media"
    inbox = tmp / "inbox"
    jobs = tmp / "jobs"
    frames = tmp / "frames"
    for p in (media, inbox, jobs, frames):
        p.mkdir(parents=True, exist_ok=True)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "media_library": str(media),
            "genomes_inbox": str(inbox),
            "jobs_dir": str(jobs),
            "frames_scratch": str(frames),
        },
    }


def _write_job(jobs: Path, job_id: str, data: dict) -> Path:
    d = jobs / job_id
    d.mkdir(parents=True, exist_ok=True)
    path = d / "job.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_is_orphan_startup_treats_inflight():
    job = JobRecord("abcdef012345", Path("x"), {"state": "rendering"})
    assert is_orphan(job, live_ids=set(), treat_all_inflight_as_orphan=True)
    assert not is_orphan(
        JobRecord("abcdef012345", Path("x"), {"state": "ingested"}),
        live_ids=set(),
        treat_all_inflight_as_orphan=True,
    )


def test_is_orphan_skips_live():
    job = JobRecord("abcdef012345", Path("x"), {"state": "rendering"})
    assert not is_orphan(
        job, live_ids={"abcdef012345"}, treat_all_inflight_as_orphan=False
    )
    assert is_orphan(job, live_ids=set(), treat_all_inflight_as_orphan=False)


def test_reclaim_superseded_when_catalog_exists(tmp_path: Path):
    cfg = _cfg(tmp_path)
    base = "electricsheep.247.14136"
    mp4 = tmp_path / "media" / "by-generation" / "247" / f"{base}.mp4"
    mp4.parent.mkdir(parents=True, exist_ok=True)
    mp4.write_bytes(b"fake")
    src = tmp_path / "inbox" / f"{base}.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    jpath = _write_job(
        tmp_path / "jobs",
        "aaaabbbbcccc",
        {"id": "aaaabbbbcccc", "state": "rendering", "src": str(src), "nframes": 10},
    )
    frame_dir = tmp_path / "frames" / "aaaabbbbcccc"
    frame_dir.mkdir(parents=True)
    (frame_dir / "f00000.png").write_bytes(b"x")

    job = JobRecord("aaaabbbbcccc", jpath, json.loads(jpath.read_text(encoding="utf-8")))
    action = reclaim_job(cfg, job, dry_run=False)
    assert action.outcome == "superseded"
    assert action.frames_removed
    assert not frame_dir.exists()
    data = json.loads(jpath.read_text(encoding="utf-8"))
    assert data["state"] == "superseded"
    assert catalog_mp4_for_base(cfg, base) == mp4


def test_reclaim_orphaned_requeues_missing_inbox(tmp_path: Path):
    cfg = _cfg(tmp_path)
    job_id = "ddddeeeeffff"
    work = tmp_path / "jobs" / job_id
    work.mkdir(parents=True)
    opt = work / "tv_optimized.flam3"
    opt.write_text('<flame size="1920 1080" quality="900" />\n' + ("x" * 40), encoding="utf-8")
    # src claimed under inbox but file missing
    missing = tmp_path / "inbox" / "electricsheep.243.14985.flam3"
    jpath = work / "job.json"
    jpath.write_text(
        json.dumps(
            {
                "id": job_id,
                "state": "rendering",
                "src": str(missing),
                "nframes": 552,
            }
        ),
        encoding="utf-8",
    )
    frame_dir = tmp_path / "frames" / job_id
    frame_dir.mkdir()
    (frame_dir / "f00000.png").write_bytes(b"x")

    actions = reclaim_orphans(cfg, startup=True, requeue=True)
    assert len(actions) == 1
    assert actions[0].outcome == "orphaned"
    assert actions[0].requeued == "electricsheep.243.14985.flam3"
    assert (tmp_path / "inbox" / "electricsheep.243.14985.flam3").is_file()
    assert not frame_dir.exists()


def test_reclaim_skips_manual_sample_requeue(tmp_path: Path):
    """Legacy configs/samples/ path is still treated as manual (do not re-queue)."""
    cfg = _cfg(tmp_path)
    sample = tmp_path / "configs" / "samples" / "demo.flam3"
    sample.parent.mkdir(parents=True)
    sample.write_text("<flame/>", encoding="utf-8")
    jpath = _write_job(
        tmp_path / "jobs",
        "111122223333",
        {
            "id": "111122223333",
            "state": "rendering",
            "src": str(sample),
            "nframes": 984,
        },
    )
    action = reclaim_job(cfg, JobRecord("111122223333", jpath, json.loads(jpath.read_text())), dry_run=False)
    assert action.outcome == "orphaned"
    assert action.requeued is None
    assert list((tmp_path / "inbox").glob("*.flam3")) == []


def test_dry_run_does_not_mutate(tmp_path: Path):
    cfg = _cfg(tmp_path)
    src = tmp_path / "inbox" / "electricsheep.244.00001.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    jpath = _write_job(
        tmp_path / "jobs",
        "abcd1234abcd",
        {"id": "abcd1234abcd", "state": "encoding", "src": str(src)},
    )
    frame_dir = tmp_path / "frames" / "abcd1234abcd"
    frame_dir.mkdir()
    (frame_dir / "f00000.png").write_bytes(b"x")
    actions = reclaim_orphans(cfg, dry_run=True, startup=True)
    assert actions[0].dry_run
    assert json.loads(jpath.read_text())["state"] == "encoding"
    assert frame_dir.exists()
