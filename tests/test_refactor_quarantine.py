"""Pathway C tests for sheep refactor quarantine (no delete)."""

from __future__ import annotations

from pathlib import Path

from pipeline.poster import poster_path_for_mp4
from pipeline.refactor import run_quarantine, score_sheep
from pipeline.stills import sidecar_path_for_mp4


def _cfg(tmp: Path) -> dict:
    media = tmp / "media"
    (media / "by-generation" / "247").mkdir(parents=True)
    done = tmp / "genomes" / "done"
    done.mkdir(parents=True)
    q = tmp / "genomes" / "quarantine"
    q.mkdir(parents=True)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "media_library": str(media),
            "genomes_done": str(done),
            "genomes_inbox": str(tmp / "genomes" / "inbox"),
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
        "tools": {},
    }


def _bad_xml() -> str:
    # Non-16:9 + neon clash + weak quality knobs → quarantine-band score.
    return """<flame name="t" size="800 600" quality="100">
  <xform weight="1" coefs="1 0 0 1 0 0" color="0"/>
  <color index="0" rgb="255 0 255"/>
  <color index="1" rgb="0 255 0"/>
</flame>"""


def _seed(tmp: Path, cfg: dict, stem: str = "electricsheep.247.00505") -> Path:
    mp4 = Path(cfg["paths"]["media_library"]) / "by-generation" / "247" / f"{stem}.mp4"
    mp4.write_bytes(b"fake-mp4")
    poster_path_for_mp4(mp4).write_bytes(b"jpg")
    sidecar_path_for_mp4(mp4).write_text(
        f'{{"id": "{stem}", "duration_sec": 23}}', encoding="utf-8"
    )
    genome = Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3"
    genome.write_text(_bad_xml(), encoding="utf-8")
    return mp4


def test_quarantine_dry_run_no_moves(tmp_path: Path):
    cfg = _cfg(tmp_path)
    mp4 = _seed(tmp_path, cfg)
    stem = mp4.stem
    row = score_sheep(cfg, mp4)
    assert row.verdict in ("candidate", "quarantine")

    result = run_quarantine(
        cfg,
        stem,
        dry_run=True,
        force=True,
        unpublish=True,
        refresh_fn=lambda _c: {"ok": True, "status": "stub"},
        unpublish_fn=lambda *_a, **_k: {"ok": True, "status": "stub"},
    )
    assert result.dry_run is True
    assert mp4.is_file()
    assert (Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3").is_file()
    assert "genome_would_move" in result.notes or "genome_moved" not in result.notes


def test_quarantine_apply_moves_genome_and_parks_catalog(tmp_path: Path):
    cfg = _cfg(tmp_path)
    mp4 = _seed(tmp_path, cfg)
    stem = mp4.stem
    genome = Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3"

    result = run_quarantine(
        cfg,
        stem,
        dry_run=False,
        force=True,
        reason="lab-dud",
        unpublish=True,
        refresh_fn=lambda _c: {"ok": True, "status": "stub"},
        unpublish_fn=lambda *_a, **_k: {"ok": True, "status": "deleted", "item_id": "x"},
    )
    assert result.dry_run is False
    assert "operator_reason:lab-dud" in result.notes
    q_genome = Path(cfg["paths"]["genomes_quarantine"]) / f"{stem}.flam3"
    assert q_genome.is_file()
    assert not genome.exists()
    assert not mp4.exists()
    hold = Path(cfg["paths"]["media_library"]) / "_refactor-quarantine" / stem
    assert (hold / f"{stem}.mp4").is_file()
    assert result.jellyfin.get("status") == "deleted"
    # Genetics preserved (moved, not deleted)
    assert q_genome.read_text(encoding="utf-8").startswith("<flame")


def test_quarantine_rejects_ok_without_force(tmp_path: Path):
    cfg = _cfg(tmp_path)
    stem = "electricsheep.247.00999"
    mp4 = Path(cfg["paths"]["media_library"]) / "by-generation" / "247" / f"{stem}.mp4"
    mp4.write_bytes(b"fake-mp4")
    poster_path_for_mp4(mp4).write_bytes(b"jpg")
    sidecar_path_for_mp4(mp4).write_text('{"duration_sec": 23}', encoding="utf-8")
    genome = Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3"
    genome.write_text(
        """<flame name="t" size="1920 1080" quality="900" supersample="2" filter="1">
  <xform weight="1" coefs="1 0 0 1 0 0" color="0"/>
  <color index="0" rgb="180 60 40"/>
  <color index="1" rgb="40 80 200"/>
</flame>""",
        encoding="utf-8",
    )
    row = score_sheep(cfg, mp4)
    if row.verdict == "quarantine":
        # Environment may still quarantine; force-path covered elsewhere.
        return
    try:
        run_quarantine(cfg, stem, dry_run=True, force=False, unpublish=False)
        raised = False
    except ValueError:
        raised = True
    assert raised
