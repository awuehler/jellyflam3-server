"""Unit tests for Phase 3 sheep refactor Pathway A (scan/score/report)."""

from __future__ import annotations

from pathlib import Path

from pipeline.palette_harmony import apply_palette_harmony
from pipeline.poster import poster_path_for_mp4
from pipeline.refactor import SheepScore, filter_report, format_table, score_sheep
from pipeline.stills import sidecar_path_for_mp4


def _cfg(tmp: Path, **overrides) -> dict:
    base = {
        "_repo_root": str(tmp),
        "paths": {
            "media_library": str(tmp / "media"),
            "genomes_done": str(tmp / "genomes" / "done"),
            "genomes_inbox": str(tmp / "genomes" / "inbox"),
            "genomes_quarantine": str(tmp / "genomes" / "quarantine"),
        },
        "vod": {
            "min_duration_sec": 7,
            "max_duration_sec": 37,
            "max_duration_sec_hard": 90,
            "allow_bypass_max": True,
        },
        "palette": {"mode": "complementary", "seed": "genome_accent"},
        "sheep_tax": {"enabled": True, "repair": False},
        "tools": {},
    }
    base.update(overrides)
    return base


def _good_xml(*, size: str = "1920 1080", quality: bool = True) -> str:
    attrs = f'name="t" size="{size}"'
    if quality:
        attrs += ' quality="900" supersample="2" filter="1"'
    return f"""<flame {attrs}>
  <xform weight="1" coefs="1 0 0 1 0 0" color="0"/>
  <color index="0" rgb="180 60 40"/>
  <color index="1" rgb="40 80 200"/>
</flame>"""


def _mp4(tmp: Path, stem: str = "electricsheep.247.00505") -> Path:
    media = tmp / "media" / "by-generation" / "247"
    media.mkdir(parents=True, exist_ok=True)
    mp4 = media / f"{stem}.mp4"
    mp4.write_bytes(b"fake-mp4")
    return mp4


def _with_poster_and_duration(mp4: Path, duration_sec: float = 23.0) -> None:
    poster_path_for_mp4(mp4).write_bytes(b"jpg")
    sidecar_path_for_mp4(mp4).write_text(
        f'{{"id": "{mp4.stem}", "duration_sec": {duration_sec}}}',
        encoding="utf-8",
    )


def test_missing_poster_is_candidate(tmp_path: Path):
    mp4 = _mp4(tmp_path)
    genome = tmp_path / "genomes" / "done" / f"{mp4.stem}.flam3"
    genome.parent.mkdir(parents=True, exist_ok=True)
    xml = _good_xml()
    genome.write_text(xml, encoding="utf-8")
    sidecar_path_for_mp4(mp4).write_text('{"duration_sec": 23}', encoding="utf-8")
    row = score_sheep(_cfg(tmp_path), mp4, genome_path=genome, xml_text=xml)
    assert "missing_poster" in row.reasons
    assert row.verdict in ("candidate", "quarantine")
    assert row.score >= 25.0
    assert row.palette.get("seed_hex")
    assert row.palette.get("complement_hex")


def test_duration_above_hard_band(tmp_path: Path):
    mp4 = _mp4(tmp_path)
    _with_poster_and_duration(mp4, 120.0)
    genome = tmp_path / "g.flam3"
    xml = _good_xml()
    genome.write_text(xml, encoding="utf-8")
    row = score_sheep(_cfg(tmp_path), mp4, genome_path=genome, xml_text=xml)
    assert "duration_above_hard" in row.reasons
    assert row.duration_sec == 120.0


def test_sheep_tax_fail_quarantine(tmp_path: Path):
    mp4 = _mp4(tmp_path)
    _with_poster_and_duration(mp4, 23.0)
    bad_xml = "not xml at all <<<"
    genome = tmp_path / "bad.flam3"
    genome.write_text(bad_xml, encoding="utf-8")
    row = score_sheep(_cfg(tmp_path), mp4, genome_path=genome, xml_text=bad_xml)
    assert row.verdict == "quarantine"
    assert "sheep_tax_fail" in row.reasons


def test_missing_genome_quarantine(tmp_path: Path):
    mp4 = _mp4(tmp_path)
    _with_poster_and_duration(mp4, 23.0)
    row = score_sheep(_cfg(tmp_path), mp4)
    assert row.verdict == "quarantine"
    assert "missing_genome" in row.reasons
    assert row.palette.get("source") == "unavailable"


def test_aspect_not_16_9(tmp_path: Path):
    mp4 = _mp4(tmp_path)
    _with_poster_and_duration(mp4, 23.0)
    xml = _good_xml(size="800 600")
    genome = tmp_path / "g.flam3"
    genome.write_text(xml, encoding="utf-8")
    row = score_sheep(_cfg(tmp_path), mp4, genome_path=genome, xml_text=xml)
    assert "aspect_not_16_9" in row.reasons
    assert row.aspect == "800x600"


def test_palette_override_changes_complement(tmp_path: Path):
    xml = _good_xml()
    cfg_a = _cfg(tmp_path)
    cfg_b = _cfg(
        tmp_path,
        palette={"mode": "complementary", "seed": "curator_hex", "curator_hex": "#88aaff"},
    )
    a = apply_palette_harmony(xml, cfg_a)
    b = apply_palette_harmony(xml, cfg_b)
    assert a is not None and b is not None
    assert (a.seed_hex, a.complement_hex) != (b.seed_hex, b.complement_hex)


def test_filter_and_format_table():
    rows = [
        SheepScore(
            id="a",
            mp4="/a.mp4",
            verdict="ok",
            score=0.0,
            palette={"seed_hex": "#111111", "complement_hex": "#eeeeee"},
        ),
        SheepScore(
            id="b",
            mp4="/b.mp4",
            verdict="candidate",
            score=25.0,
            reasons=["missing_poster"],
            palette={"seed_hex": "#222222", "complement_hex": "#dddddd"},
        ),
    ]
    failing = filter_report(rows, failing_only=True)
    assert len(failing) == 1 and failing[0].id == "b"
    text = format_table(failing)
    assert "candidate" in text and "missing_poster" in text
