"""Frozen-orbit predictor, Pathway A candidate, duration snap skip, still-loop gate."""

from __future__ import annotations

from pathlib import Path

from pipeline.choose_duration import choose_duration_sec, choose_nframes
from pipeline.genome_signals import (
    extract_genome_signals,
    is_orbit_frozen,
    should_still_loop,
)
from pipeline.poster import poster_path_for_mp4
from pipeline.refactor_scan import HARD_QUARANTINE_REASONS, score_sheep, verdict_for
from pipeline.stills import sidecar_path_for_mp4
from pipeline.worker import catalog_ffmpeg_cmd

# Shape of 04a electricsheep.245.09797 — deprecated xform symmetry>0 freezes orbit.
FROZEN_09797_XML = """<flame name="electricsheep.245.09797" time="0" size="1920 1080"
  rotate="1311.02" quality="900" supersample="2">
  <xform weight="0.896543" color="0.435361" symmetry="0.793086"
    linear="0.86546" spherical="0.13454" coefs="1 0 0 1 0 0" />
  <xform weight="1" color="0" symmetry="1" linear="1" coefs="1 0 0 1 0 0" />
  <xform weight="1" color="1" symmetry="1" linear="1" coefs="1 0 0 1 0 0" />
</flame>"""

ANIMATE_EXPLICIT_XML = """<flame name="t" size="1920 1080" rotate="1311.02">
  <xform weight="1" symmetry="1" animate="1" spherical="1" coefs="1 0 0 1 0 0" />
</flame>"""

OMITTED_XML = """<flame name="t" size="1920 1080" rotate="90">
  <xform weight="1" spherical="1" coefs="1 0 0 1 0 0" />
</flame>"""

MOTION_XML = """<flame name="t" size="1920 1080">
  <xform weight="1" symmetry="1" linear="1" coefs="1 0 0 1 0 0">
    <motion motion_frequency="1" motion_function="sin" rotate="30" />
  </xform>
</flame>"""

TWO_FLAME_FROZEN_XML = """<flame name="a" time="0" size="1920 1080">
  <xform weight="1" symmetry="1" linear="1" coefs="1 0 0 1 0 0" />
</flame>
<flame name="b" time="1" size="1920 1080">
  <xform weight="1" symmetry="1" linear="1" coefs="0.5 0 0 0.5 0.1 0" />
</flame>"""

FINAL_ONLY_ANIMATE_XML = """<flame name="t" size="1920 1080">
  <xform weight="1" symmetry="1" linear="1" coefs="1 0 0 1 0 0" />
  <finalxform animate="1" spherical="1" coefs="1 0 0 1 0 0" />
</flame>"""


def test_09797_shape_is_orbit_frozen():
    assert is_orbit_frozen(FROZEN_09797_XML)
    s = extract_genome_signals(FROZEN_09797_XML)
    assert s["orbit_frozen"] is True
    assert s["effective_animate_count"] == 0
    assert s["animate_count"] == 0
    assert s["period_candidates_sec"] == []
    assert s["fundamental_period_sec"] is None
    assert s["rotate_deg"] == 1311.02


def test_explicit_animate_wins_over_symmetry():
    assert not is_orbit_frozen(ANIMATE_EXPLICIT_XML)
    s = extract_genome_signals(ANIMATE_EXPLICIT_XML)
    assert s["orbit_frozen"] is False
    assert s["effective_animate_count"] == 1
    assert s["period_candidates_sec"]  # rotate period kept


def test_omitted_animate_and_symmetry_defaults_to_orbit():
    assert not is_orbit_frozen(OMITTED_XML)
    assert extract_genome_signals(OMITTED_XML)["effective_animate_count"] == 1


def test_motion_child_not_frozen():
    assert not is_orbit_frozen(MOTION_XML)


def test_finalxform_ignored_for_orbit():
    assert is_orbit_frozen(FINAL_ONLY_ANIMATE_XML)


def test_should_still_loop_single_flame_only():
    assert should_still_loop(FROZEN_09797_XML)
    assert not should_still_loop(TWO_FLAME_FROZEN_XML)
    assert is_orbit_frozen(TWO_FLAME_FROZEN_XML)
    assert not should_still_loop(FROZEN_09797_XML, {"render": {"still_loop_if_orbit_frozen": False}})
    assert not should_still_loop(ANIMATE_EXPLICIT_XML)


def _dyn_cfg():
    return {
        "vod": {
            "min_duration_sec": 11,
            "max_duration_sec": 31,
            "max_duration_sec_hard": 60,
            "allow_bypass_max": True,
            "fps": 24,
            "duration_mode": "dynamic",
            "dynamic": {
                "base_sec": 19,
                "snap_to_periods": True,
                "weights": {"complexity": 0.0, "queue_pressure": 0.0, "jitter_sec": 0},
                "profile_04_short_bias": 0,
            },
        },
        "render": {},
    }


def test_frozen_rotate_does_not_period_snap():
    cfg = _dyn_cfg()
    s = extract_genome_signals(FROZEN_09797_XML)
    dur = choose_duration_sec(cfg, {"signals": s})
    # False 1/3.64 ≈ 0.27s period would LCM toward a different band member.
    assert abs(dur - 19.0) < 1e-9
    n = choose_nframes(cfg, {"signals": s})
    assert n == 456  # 19s * 24


def test_orbit_frozen_is_candidate_not_quarantine(tmp_path: Path):
    assert "genome_orbit_frozen" not in HARD_QUARANTINE_REASONS
    assert verdict_for(25.0, ["genome_orbit_frozen"]) == "candidate"

    media = tmp_path / "media" / "by-generation" / "245"
    media.mkdir(parents=True)
    stem = "electricsheep.245.09797"
    mp4 = media / f"{stem}.mp4"
    mp4.write_bytes(b"fake-mp4")
    poster_path_for_mp4(mp4).write_bytes(b"jpg")
    sidecar_path_for_mp4(mp4).write_text(
        f'{{"id": "{stem}", "duration_sec": 21.0}}',
        encoding="utf-8",
    )
    genome = tmp_path / "genomes" / "done" / f"{stem}.flam3"
    genome.parent.mkdir(parents=True)
    genome.write_text(FROZEN_09797_XML, encoding="utf-8")
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "media_library": str(tmp_path / "media"),
            "genomes_done": str(tmp_path / "genomes" / "done"),
            "genomes_inbox": str(tmp_path / "genomes" / "inbox"),
            "genomes_quarantine": str(tmp_path / "genomes" / "quarantine"),
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
        "refactor": {"orbit_frozen_score": 25},
    }
    row = score_sheep(cfg, mp4)
    assert "genome_orbit_frozen" in row.reasons
    assert "genome_linear_only" not in row.reasons
    assert row.verdict == "candidate"
    assert row.score >= 25.0
    assert row.score < 80.0


def test_catalog_ffmpeg_still_loop_keeps_aac():
    cmd = catalog_ffmpeg_cmd(
        {"encode": {"video_bitrate": "3M", "maxrate": "4M", "bufsize": "6M"}},
        ffmpeg="ffmpeg",
        video_args=["-loop", "1", "-framerate", "24", "-i", "still.png"],
        nframes=456,
        out_tmp=Path("out.mp4"),
        extra_output=["-t", "19.0"],
    )
    assert cmd[0] == "ffmpeg"
    assert "-loop" in cmd
    assert "anullsrc=channel_layout=stereo:sample_rate=48000" in cmd
    assert "-t" in cmd
    assert "19.0" in cmd
    assert "aac" in cmd
    assert "libx264" in cmd
    assert "3M" in cmd
