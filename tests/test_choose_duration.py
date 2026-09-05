"""Extensive tests for dynamic duration + period-aware loop closure (guide 08)."""

from __future__ import annotations

import math

import pytest

from pipeline.choose_duration import (
    assert_duration_in_band,
    choose_duration_sec,
    choose_nframes,
    duration_for_nframes,
    effective_max_sec,
    lcm_many,
    nframes_for_duration,
    snap_duration_to_periods,
)
from pipeline.genome_signals import estimate_queue_pressure, extract_genome_signals


def _cfg(**vod_updates):
    base = {
        "vod": {
            "min_duration_sec": 7,
            "max_duration_sec": 37,
            "max_duration_sec_hard": 120,
            "allow_bypass_max": False,
            "target_duration_sec": 23,
            "fps": 24,
            "nframes": 552,
            "duration_mode": "fixed",
            "smoke_duration_sec": 13,
            "smoke_nframes": 312,
        },
        "render": {},
    }
    base["vod"].update(vod_updates)
    return base


def _dyn_cfg(**extra):
    cfg = _cfg(
        duration_mode="dynamic",
        allow_bypass_max=True,
        dynamic={
            "base_sec": 23,
            "snap_to_periods": True,
            "weights": {
                "complexity": 0.35,
                "queue_pressure": -0.25,
                "jitter_sec": 0,
            },
            "profile_04_short_bias": 4,
        },
    )
    if extra:
        cfg["vod"]["dynamic"].update(extra.get("dynamic", {}))
        for k, v in extra.items():
            if k != "dynamic":
                cfg["vod"][k] = v
    return cfg


FLAME_SIMPLE = """
<flame name="t" size="800 600" scale="600" rotate="0">
  <xform weight="1" color_speed="0.5" animate="1" linear="1" coefs="1 0 0 1 0 0"/>
</flame>
"""

FLAME_ROTATE_720 = """
<flame name="r" size="800 600" scale="600" rotate="720">
  <xform weight="1" color_speed="0.5" animate="1" julian="1" coefs="1 0 0 1 0 0"/>
  <xform weight="1" color_speed="0.25" animate="1" spherical="1" coefs="1 0 0 1 0 0"/>
</flame>
"""

FLAME_MULTI = """
<flame name="a" size="100 100" scale="100" rotate="360">
  <xform weight="1" animate="1" coefs="1 0 0 1 0 0"/>
</flame>
<flame name="b" size="100 100" scale="100" rotate="0">
  <xform weight="1" animate="0" coefs="1 0 0 1 0 0"/>
</flame>
"""


# --- genome signals ---


def test_extract_signals_basic():
    s = extract_genome_signals(FLAME_SIMPLE)
    assert s["flame_count"] == 1
    assert s["xform_count"] == 1
    assert s["animate_count"] == 1
    assert s["complexity"] > 0
    assert s["multi_flame_risk"] == 0.0
    assert s["rotate_closed"] is True
    assert s["period_candidates_sec"]


def test_extract_rotate_720_closed():
    s = extract_genome_signals(FLAME_ROTATE_720)
    assert s["rotate_deg"] == 720.0
    assert s["rotate_turns"] == 2.0
    assert s["rotate_closed"] is True
    assert s["xform_count"] == 2
    assert any(abs(p - 0.5) < 1e-6 for p in s["period_candidates_sec"])  # 1/turns


def test_extract_multi_flame_risk():
    s = extract_genome_signals(FLAME_MULTI)
    assert s["flame_count"] == 2
    assert s["multi_flame_risk"] == 1.0


def test_queue_pressure():
    assert estimate_queue_pressure(0) == 0.0
    assert estimate_queue_pressure(8) == 1.0
    assert estimate_queue_pressure(16) == 2.0


# --- period snap ---


def test_lcm_many():
    assert lcm_many([4, 6], cap=1000) == 12
    assert lcm_many([24], cap=1000) == 24


def test_snap_to_period_closes_loop():
    # period 2s @ 24fps → 48 frames; target 23s → nearest multiple
    dur, meta = snap_duration_to_periods(
        23.0, [2.0], lo=7.0, hi=37.0, fps=24.0
    )
    assert meta["snapped"] is True
    n = nframes_for_duration(dur, 24)
    fund = meta["fundamental_frames"]
    assert n % fund == 0
    assert 7.0 - 1e-6 <= dur <= 37.0 + 1e-6


def test_snap_respects_hard_band():
    dur, meta = snap_duration_to_periods(
        100.0, [5.0], lo=7.0, hi=120.0, fps=24.0
    )
    assert dur <= 120.0 + 1e-9
    assert nframes_for_duration(dur, 24) % meta["fundamental_frames"] == 0


def test_snap_color_speed_period_from_signals():
    s = extract_genome_signals(FLAME_SIMPLE)
    periods = s["period_candidates_sec"]
    dur, meta = snap_duration_to_periods(23.0, periods, lo=7, hi=37, fps=24)
    assert meta["snapped"]
    assert nframes_for_duration(dur, 24) % meta["fundamental_frames"] == 0


# --- choose duration ---


def test_nframes_table():
    assert nframes_for_duration(7, 24) == 168
    assert nframes_for_duration(23, 24) == 552
    assert nframes_for_duration(37, 24) == 888
    assert nframes_for_duration(120, 24) == 2880
    assert nframes_for_duration(13, 24) == 312


def test_choose_fixed_default():
    assert choose_nframes(_cfg()) == 552


def test_clamp_job_override_soft():
    assert choose_nframes(_cfg(), {"duration_sec": 3}) == 168
    assert choose_nframes(_cfg(), {"duration_sec": 90}) == 888


def test_clamp_job_override_hard_bypass():
    cfg = _cfg(allow_bypass_max=True)
    # 90s allowed under hard 120
    assert choose_nframes(cfg, {"duration_sec": 90}) == 2160
    assert choose_nframes(cfg, {"duration_sec": 200}) == 2880  # clamp hard


def test_effective_max_soft_vs_hard():
    assert effective_max_sec(_cfg(allow_bypass_max=False)) == 37
    assert effective_max_sec(_cfg(allow_bypass_max=True)) == 120


def test_assert_band_soft():
    cfg = _cfg(allow_bypass_max=False)
    assert_duration_in_band(23.0, cfg)
    with pytest.raises(ValueError):
        assert_duration_in_band(40.0, cfg)


def test_assert_band_hard_bypass():
    cfg = _cfg(allow_bypass_max=True)
    assert_duration_in_band(90.0, cfg)
    with pytest.raises(ValueError):
        assert_duration_in_band(130.0, cfg)


def test_duration_roundtrip():
    assert abs(duration_for_nframes(552, 24) - 23.0) < 1e-9


def test_smoke_duration(monkeypatch):
    monkeypatch.setenv("JELLYFLAM3_SMOKE", "1")
    assert choose_nframes(_cfg()) == 312


def test_dynamic_orbit_frozen_ignores_injected_periods():
    cfg = _dyn_cfg()
    dur = choose_duration_sec(
        cfg,
        {
            "signals": {
                "orbit_frozen": True,
                "complexity": 0.0,
                "period_candidates_sec": [0.274595],
            }
        },
    )
    assert abs(dur - 23.0) < 1e-9


def test_dynamic_uses_complexity():
    cfg = _dyn_cfg()
    low = choose_duration_sec(cfg, {"signals": {"complexity": 0.0, "period_candidates_sec": []}})
    high = choose_duration_sec(cfg, {"signals": {"complexity": 10.0, "period_candidates_sec": []}})
    assert high > low
    assert 7 <= low <= 120
    assert 7 <= high <= 120


def test_dynamic_queue_pressure_shortens():
    cfg = _dyn_cfg()
    idle = choose_duration_sec(
        cfg, {"signals": {"complexity": 1.0, "queue_pressure": 0.0, "period_candidates_sec": []}}
    )
    busy = choose_duration_sec(
        cfg, {"signals": {"complexity": 1.0, "queue_pressure": 2.0, "period_candidates_sec": []}}
    )
    assert busy < idle


def test_dynamic_cannot_exceed_hard():
    cfg = _dyn_cfg()
    dur = choose_duration_sec(
        cfg,
        {
            "signals": {
                "complexity": 1000.0,
                "period_candidates_sec": [],
            }
        },
    )
    assert dur <= 120.0 + 1e-9


def test_dynamic_no_bypass_stays_soft():
    cfg = _dyn_cfg()
    cfg["vod"]["allow_bypass_max"] = False
    dur = choose_duration_sec(
        cfg, {"signals": {"complexity": 1000.0, "period_candidates_sec": []}}
    )
    assert dur <= 37.0 + 1e-9


def test_dynamic_from_genome_xml_snaps():
    cfg = _dyn_cfg()
    job: dict = {"genome_xml": FLAME_ROTATE_720}
    dur = choose_duration_sec(cfg, job)
    n = nframes_for_duration(dur, 24)
    meta = (job.get("duration_meta") or {}).get("period_snap") or {}
    assert meta.get("snapped") is True
    assert n % meta["fundamental_frames"] == 0
    assert 7 <= dur <= 120


def test_dynamic_profile_04_shortens():
    cfg = _dyn_cfg()
    cfg["render"] = {"hw_profile": "rpi-jellyflam3-04"}
    short = choose_duration_sec(
        cfg, {"signals": {"complexity": 1.0, "period_candidates_sec": []}}
    )
    cfg2 = _dyn_cfg()
    cfg2["render"] = {"hw_profile": "rpi-jellyflam3-16"}
    long = choose_duration_sec(
        cfg2, {"signals": {"complexity": 1.0, "period_candidates_sec": []}}
    )
    assert short < long


def test_bypass_never_past_hard_in_snap():
    cfg = _dyn_cfg()
    # Force a long period that still fits under hard max via k=1
    job = {
        "signals": {
            "complexity": 50.0,
            "period_candidates_sec": [11.0],  # 264 frames
        }
    }
    dur = choose_duration_sec(cfg, job)
    assert dur <= 120
    n = choose_nframes(cfg, job)
    assert n == nframes_for_duration(dur, 24)
    fund = job["duration_meta"]["period_snap"]["fundamental_frames"]
    assert n % fund == 0


def test_real_sample_if_present():
    from pathlib import Path

    sample = (
        Path(__file__).resolve().parents[1]
        / "configs"
        / "samples"
        / "electricsheep.247.00505.flam3"
    )
    if not sample.is_file():
        pytest.skip("sample missing")
    s = extract_genome_signals(sample.read_text(encoding="utf-8"))
    assert s["xform_count"] >= 1
    assert s["rotate_closed"] is True  # 720° = 2 turns
    cfg = _dyn_cfg()
    job = {"signals": s}
    dur = choose_duration_sec(cfg, job)
    n = choose_nframes(cfg, job)
    assert 7 <= dur <= 120
    assert n == nframes_for_duration(dur, 24)
    meta = job.get("duration_meta", {}).get("period_snap", {})
    if meta.get("snapped"):
        assert n % meta["fundamental_frames"] == 0
