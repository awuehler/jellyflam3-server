"""Linear-only / singularity=cloned heuristics for Pathway A."""

from __future__ import annotations

from pathlib import Path

from pipeline.genome_signals import is_linear_only_genome, is_singularity_cloned
from pipeline.poster import poster_path_for_mp4
from pipeline.refactor_scan import genome_dud_reasons, score_sheep
from pipeline.stills import sidecar_path_for_mp4

# Shape of 04a electricsheep.244.00881 (ES singularities clone).
LINEAR_CLONE_XML = """<flame name="electricsheep.244.00881" time="0" size="1920 1080"
  rotate="0" quality="900" supersample="2" filter="1" singularity="cloned">
  <xform weight="1" color="0" symmetry="0" linear="1" coefs="1 0 0 1 0.1 0" />
  <xform weight="1" color="1" symmetry="0" linear="1" coefs="1 0 0 1 0 -0.1" />
  <xform weight="1" color="0" symmetry="0" linear="1" coefs="1 0 0 1 0.1 0" />
  <xform weight="1" color="1" symmetry="0" linear="1" coefs="1 0 0 1 0 -0.1" />
  <color index="0" rgb="46 7 70" />
  <color index="1" rgb="35 5 85" />
</flame>"""

JULIA_XML = """<flame name="t" size="1920 1080" quality="900" supersample="2" filter="1">
  <xform weight="0.4" color="0" linear="0.04" julia="0.95" coefs="0.86 -0.08 0.06 0.80 -0.13 0.15" />
  <color index="0" rgb="180 60 40"/>
  <color index="1" rgb="40 80 200"/>
</flame>"""

IMPLICIT_LINEAR_XML = """<flame name="t" size="1920 1080" quality="900" supersample="2" filter="1">
  <xform weight="1" coefs="1 0 0 1 0 0" color="0"/>
</flame>"""

CLONED_BUT_JULIA_XML = """<flame name="t" size="1920 1080" quality="900" supersample="2" filter="1" singularity="cloned">
  <xform weight="1" julia="0.95" coefs="1 0 0 1 0 0" color="0"/>
</flame>"""


def test_linear_only_and_cloned_detectors():
    assert is_linear_only_genome(LINEAR_CLONE_XML)
    assert is_singularity_cloned(LINEAR_CLONE_XML)
    assert genome_dud_reasons(LINEAR_CLONE_XML) == [
        "genome_linear_only",
        "genome_singularity_cloned",
    ]
    assert not is_linear_only_genome(JULIA_XML)
    assert not is_singularity_cloned(JULIA_XML)
    assert genome_dud_reasons(JULIA_XML) == []
    assert is_linear_only_genome(IMPLICIT_LINEAR_XML)
    assert not is_singularity_cloned(IMPLICIT_LINEAR_XML)
    assert not is_linear_only_genome(CLONED_BUT_JULIA_XML)
    assert is_singularity_cloned(CLONED_BUT_JULIA_XML)
    assert genome_dud_reasons(CLONED_BUT_JULIA_XML) == ["genome_singularity_cloned"]


def _cfg(tmp: Path) -> dict:
    return {
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


def _catalog(tmp: Path, stem: str, xml: str) -> Path:
    media = tmp / "media" / "by-generation" / "244"
    media.mkdir(parents=True, exist_ok=True)
    mp4 = media / f"{stem}.mp4"
    mp4.write_bytes(b"fake-mp4")
    poster_path_for_mp4(mp4).write_bytes(b"jpg")
    sidecar_path_for_mp4(mp4).write_text(
        f'{{"id": "{stem}", "duration_sec": 18.8}}',
        encoding="utf-8",
    )
    genome = tmp / "genomes" / "done" / f"{stem}.flam3"
    genome.parent.mkdir(parents=True, exist_ok=True)
    genome.write_text(xml, encoding="utf-8")
    return mp4


def test_00881_shape_quarantines(tmp_path: Path):
    mp4 = _catalog(tmp_path, "electricsheep.244.00881", LINEAR_CLONE_XML)
    row = score_sheep(_cfg(tmp_path), mp4)
    assert row.verdict == "quarantine"
    assert "genome_linear_only" in row.reasons
    assert "genome_singularity_cloned" in row.reasons
    assert row.score >= 80.0


def test_julia_genome_not_flagged(tmp_path: Path):
    mp4 = _catalog(tmp_path, "electricsheep.244.00128", JULIA_XML)
    row = score_sheep(_cfg(tmp_path), mp4)
    assert "genome_linear_only" not in row.reasons
    assert "genome_singularity_cloned" not in row.reasons
    assert row.verdict != "quarantine"


def test_implicit_linear_quarantines(tmp_path: Path):
    mp4 = _catalog(tmp_path, "electricsheep.244.linear", IMPLICIT_LINEAR_XML)
    row = score_sheep(_cfg(tmp_path), mp4)
    assert row.verdict == "quarantine"
    assert "genome_linear_only" in row.reasons
    assert "genome_singularity_cloned" not in row.reasons
