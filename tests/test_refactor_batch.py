"""Pathway D tests for sheep refactor batch (route B/C with limit)."""

from __future__ import annotations

from pathlib import Path

from pipeline.poster import poster_path_for_mp4
from pipeline.refactor import ApplyResult, BatchResult, QuarantineResult, run_batch
from pipeline.stills import sidecar_path_for_mp4


def _cfg(tmp: Path) -> dict:
    media = tmp / "media"
    (media / "by-generation" / "247").mkdir(parents=True)
    done = tmp / "genomes" / "done"
    done.mkdir(parents=True)
    inbox = tmp / "genomes" / "inbox"
    inbox.mkdir(parents=True)
    q = tmp / "genomes" / "quarantine"
    q.mkdir(parents=True)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "media_library": str(media),
            "genomes_done": str(done),
            "genomes_inbox": str(inbox),
            "genomes_quarantine": str(q),
        },
        "palette": {"mode": "complementary", "seed": "genome_accent"},
        "sheep_tax": {"enabled": True, "repair": False},
        "vod": {
            "min_duration_sec": 7,
            "max_duration_sec": 37,
            "max_duration_sec_hard": 90,
            "allow_bypass_max": True,
        },
        "render": {"target_width": 1920, "target_height": 1080},
        "tools": {},
    }


def _seed_mp4(cfg: dict, stem: str, *, duration: float = 23.0) -> Path:
    mp4 = Path(cfg["paths"]["media_library"]) / "by-generation" / "247" / f"{stem}.mp4"
    mp4.write_bytes(b"fake-mp4")
    poster_path_for_mp4(mp4).write_bytes(b"jpg")
    sidecar_path_for_mp4(mp4).write_text(
        f'{{"id": "{stem}", "duration_sec": {duration}}}',
        encoding="utf-8",
    )
    return mp4


def _good_xml() -> str:
    return """<flame name="t" size="1920 1080" quality="900" supersample="2" filter="1">
  <xform weight="1" julia="0.95" coefs="1 0 0 1 0 0" color="0"/>
  <color index="0" rgb="180 60 40"/>
  <color index="1" rgb="40 80 200"/>
</flame>"""


def _bad_xml() -> str:
    return """<flame name="t" size="800 600" quality="100">
  <xform weight="1" coefs="1 0 0 1 0 0" color="0"/>
  <color index="0" rgb="255 0 255"/>
  <color index="1" rgb="0 255 0"/>
</flame>"""


def test_batch_dry_run_routes_by_verdict(tmp_path: Path):
    cfg = _cfg(tmp_path)
    cand = "electricsheep.247.00100"
    quar = "electricsheep.247.00200"
    _seed_mp4(cfg, cand, duration=120.0)  # likely candidate via duration
    (Path(cfg["paths"]["genomes_done"]) / f"{cand}.flam3").write_text(
        _good_xml(), encoding="utf-8"
    )
    _seed_mp4(cfg, quar)
    (Path(cfg["paths"]["genomes_done"]) / f"{quar}.flam3").write_text(
        _bad_xml(), encoding="utf-8"
    )

    applied: list[str] = []
    quarantined: list[str] = []

    def fake_apply(cfg, sheep_id, **kwargs):
        applied.append(sheep_id)
        return ApplyResult(id=sheep_id, dry_run=True, notes=["stub_apply"])

    def fake_quarantine(cfg, sheep_id, **kwargs):
        quarantined.append(sheep_id)
        return QuarantineResult(id=sheep_id, dry_run=True, notes=["stub_q"])

    result = run_batch(
        cfg,
        dry_run=True,
        limit=10,
        failing_only=True,
        apply_fn=fake_apply,
        quarantine_fn=fake_quarantine,
    )
    assert isinstance(result, BatchResult)
    assert result.dry_run is True
    actions = {i.id: i.action for i in result.items}
    # At least one of the seeded sheep should be routed (depending on score).
    assert actions
    assert "furnace_async_via_worker" in result.notes


def test_batch_limit(tmp_path: Path):
    cfg = _cfg(tmp_path)
    for i in range(5):
        stem = f"electricsheep.247.00{i:03d}"
        _seed_mp4(cfg, stem, duration=120.0)
        (Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3").write_text(
            _good_xml(), encoding="utf-8"
        )

    calls: list[str] = []

    def fake_apply(cfg, sheep_id, **kwargs):
        calls.append(sheep_id)
        return ApplyResult(id=sheep_id, dry_run=True)

    def fake_quarantine(cfg, sheep_id, **kwargs):
        calls.append(sheep_id)
        return QuarantineResult(id=sheep_id, dry_run=True)

    result = run_batch(
        cfg,
        dry_run=True,
        limit=2,
        failing_only=True,
        apply_fn=fake_apply,
        quarantine_fn=fake_quarantine,
    )
    assert len(result.items) <= 2
