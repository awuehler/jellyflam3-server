"""Unit tests for pipeline.breed_idle (daily idle pedigree cron logic)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from pipeline.breed_idle import (
    BreedPlan,
    collect_parent_pool,
    evaluate_idle_breed,
    hours_until_next_archive_cron,
    next_archive_cron_at,
    pick_unique_plan,
    recent_fingerprints,
    run_idle_breed,
    save_history_entry,
)


def _cfg(tmp_path: Path, **idle_overrides) -> dict:
    inbox = tmp_path / "genomes" / "inbox"
    done = tmp_path / "genomes" / "done"
    samples = tmp_path / "genomes" / "samples"
    pedigree = tmp_path / "genomes" / "pedigree" / "smoke"
    for d in (inbox, done, samples, pedigree):
        d.mkdir(parents=True, exist_ok=True)
    history = tmp_path / "breed_idle_history.json"
    idle = {
        "enabled": True,
        "history_file": str(history),
        "small_flock_threshold": 4,
        "dedup_depth_small": 1,
        "dedup_depth_large": 2,
        "max_rerolls": 8,
        "archive_cron_dom": [3, 13, 23],
        "archive_cron_hour": 3,
        "archive_cron_minute": 17,
        "min_hours_before_archive": 1.0,
    }
    idle.update(idle_overrides)
    return {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": "genomes/inbox",
            "genomes_done": "genomes/done",
            "status_file": str(tmp_path / "idle_gate_status.json"),
            "jobs_dir": str(tmp_path / "jobs"),
            "frames_scratch": str(tmp_path / "frames"),
        },
        "breed": {"idle_breed": idle},
        "idle_gate": {"enabled": False},
    }


def test_fingerprint_mutate_and_blend(tmp_path: Path):
    a = tmp_path / "a.flam3"
    b = tmp_path / "b.flam3"
    assert BreedPlan("mutate", (a,)).fingerprint() == ("mutate", a.resolve().as_posix())
    assert BreedPlan("blend", (a, b), "alternate").fingerprint() == (
        "blend",
        tuple(sorted([a.resolve().as_posix(), b.resolve().as_posix()])),
        "alternate",
    )
    assert BreedPlan("interpolate", (a, b), "interpolate").fingerprint() == (
        "interpolate",
        tuple(sorted([a.resolve().as_posix(), b.resolve().as_posix()])),
        "interpolate",
    )


def test_collect_parent_pool_done_samples_pedigree(tmp_path: Path):
    cfg = _cfg(tmp_path)
    (tmp_path / "genomes" / "done" / "one.flam3").write_text("<flame/>", encoding="utf-8")
    (tmp_path / "genomes" / "samples" / "two.flam3").write_text("<flame/>", encoding="utf-8")
    (tmp_path / "genomes" / "pedigree" / "smoke" / "three.flam3").write_text(
        "<flame/>", encoding="utf-8"
    )
    pool = collect_parent_pool(cfg)
    names = {p.name for p in pool}
    assert names == {"one.flam3", "two.flam3", "three.flam3"}


def test_hours_until_next_archive_cron():
    now = datetime(2026, 8, 17, 22, 0, tzinfo=timezone.utc)
    hours = hours_until_next_archive_cron(now=now, dom_days=[3, 13, 23], hour=3, minute=17)
    assert 120 < hours < 130


def test_next_archive_cron_at_and_to_dict_format(tmp_path: Path):
    now = datetime(2026, 8, 19, 6, 0, tzinfo=timezone.utc)
    nxt = next_archive_cron_at(now=now, dom_days=[7, 17, 27], hour=7, minute=27)
    assert nxt is not None
    assert nxt.day == 27
    assert nxt.hour == 7
    assert nxt.minute == 27

    cfg = _cfg(tmp_path, archive_cron_dom=[7, 17, 27], archive_cron_hour=7, archive_cron_minute=27)
    (tmp_path / "genomes" / "done" / "parent.flam3").write_text("<flame/>", encoding="utf-8")
    result = evaluate_idle_breed(cfg, now=now)
    payload = result.to_dict()
    assert payload["next_archive_at"] == nxt.isoformat()
    assert payload["hours_until_archive"] == round(result.hours_until_archive or 0, 2)
    assert isinstance(payload["hours_until_archive"], float)


def test_hours_until_archive_differs_by_host_schedule():
    now = datetime(2026, 8, 19, 6, 0, tzinfo=timezone.utc)
    h16 = hours_until_next_archive_cron(
        now=now, dom_days=[7, 17, 27], hour=7, minute=27
    )
    h08 = hours_until_next_archive_cron(
        now=now, dom_days=[1, 11, 21], hour=5, minute=19
    )
    h04 = hours_until_next_archive_cron(
        now=now, dom_days=[3, 13, 23], hour=3, minute=17
    )
    assert h16 != h08
    assert h08 != h04
    assert h16 > h08  # 16a next fire is Aug 27; 08a is Aug 21


def test_evaluate_skip_when_inbox_not_empty(tmp_path: Path):
    cfg = _cfg(tmp_path)
    (tmp_path / "genomes" / "inbox" / "pending.flam3").write_text("<flame/>", encoding="utf-8")
    (tmp_path / "genomes" / "done" / "parent.flam3").write_text("<flame/>", encoding="utf-8")
    result = evaluate_idle_breed(cfg)
    assert result.action == "skip"
    assert result.reason == "inbox_not_empty"


def test_evaluate_skip_archive_imminent(tmp_path: Path):
    cfg = _cfg(tmp_path)
    (tmp_path / "genomes" / "done" / "parent.flam3").write_text("<flame/>", encoding="utf-8")
    now = datetime(2026, 8, 23, 3, 0, tzinfo=timezone.utc)
    result = evaluate_idle_breed(cfg, now=now)
    assert result.action == "skip"
    assert result.reason == "archive_cron_imminent"


def test_evaluate_breed_when_idle(tmp_path: Path):
    cfg = _cfg(tmp_path)
    (tmp_path / "genomes" / "done" / "parent.flam3").write_text("<flame/>", encoding="utf-8")
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    result = evaluate_idle_breed(cfg, now=now)
    assert result.action == "breed"
    assert result.plan is not None


def test_dedup_avoids_recent_fingerprint(tmp_path: Path):
    cfg = _cfg(tmp_path)
    a = tmp_path / "genomes" / "done" / "a.flam3"
    b = tmp_path / "genomes" / "done" / "b.flam3"
    a.write_text("<flame/>", encoding="utf-8")
    b.write_text("<flame/>", encoding="utf-8")
    pool = collect_parent_pool(cfg)
    plan = BreedPlan("mutate", (a,))
    save_history_entry(cfg, plan, [tmp_path / "genomes" / "inbox" / "child.flam3"])
    assert plan.fingerprint() in recent_fingerprints(cfg, len(pool))

    from pipeline.breed_idle import BREED_MODES

    class CrossRandom:
        def choice(self, seq):
            if seq is BREED_MODES or list(seq) == list(BREED_MODES):
                return "cross"
            return seq[0]

        def sample(self, seq, k):
            return list(seq)[:k]

    picked = pick_unique_plan(cfg, pool, rng=CrossRandom())  # type: ignore[arg-type]
    assert picked is not None
    assert picked.fingerprint() != plan.fingerprint()


def test_execute_plan_interpolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = _cfg(tmp_path)
    a = tmp_path / "genomes" / "done" / "a.flam3"
    b = tmp_path / "genomes" / "done" / "b.flam3"
    a.write_text("<flame/>", encoding="utf-8")
    b.write_text("<flame/>", encoding="utf-8")
    seen: dict[str, str] = {}

    def fake_cross(cfg, pa, pb, *, method, mode_label, dry_run=False):
        seen["method"] = method
        seen["mode_label"] = mode_label
        return tmp_path / "genomes" / "inbox" / "child.flam3"

    monkeypatch.setattr("pipeline.breed_idle.breed_cross", fake_cross)
    from pipeline.breed_idle import execute_plan

    plan = BreedPlan("interpolate", (a, b), "interpolate")
    paths = execute_plan(cfg, plan, dry_run=True)
    assert len(paths) == 1
    assert seen == {"method": "interpolate", "mode_label": "interpolate"}


def test_run_idle_breed_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = _cfg(tmp_path)
    parent = tmp_path / "genomes" / "done" / "parent.flam3"
    parent.write_text(
        '<flame name="p" size="100 100" scale="100">'
        '<xform weight="1" coefs="1 0 0 1 0 0"/></flame>',
        encoding="utf-8",
    )

    def fake_mutate(cfg, parent_path, *, count=1, dry_run=False):
        assert dry_run
        inbox = tmp_path / "genomes" / "inbox" / "dry.flam3"
        return [inbox]

    monkeypatch.setattr("pipeline.breed_idle.breed_mutate", fake_mutate)
    monkeypatch.setattr(
        "pipeline.breed_idle.pick_unique_plan",
        lambda cfg, pool, rng=None: BreedPlan("mutate", (parent,)),
    )

    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "pipeline.breed_idle.evaluate_idle_breed",
        lambda cfg, now=None: evaluate_idle_breed(cfg, now=now),
    )
    result = run_idle_breed(cfg, dry_run=True)
    assert result.action == "breed"
    assert result.staged

    assert not (tmp_path / "breed_idle_history.json").exists()
