"""Purpose: Choose VoD duration (seconds / nframes) for fixed or dynamic modes (Phase 2 guide 08).

Requirements: Config ``vod`` band; optional genome XML / signals for dynamic mode.

Usage: ``choose_duration_sec(cfg, job)`` / ``choose_nframes(cfg, job)`` from the worker render path.

Assumptions: Dynamic mode snaps to periodic genome periods so catalog loops close cleanly within the band.
"""

from __future__ import annotations

import math
import os
import random
from typing import Any

from pipeline.genome_signals import extract_genome_signals


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def nframes_for_duration(duration_sec: float, fps: float) -> int:
    return int(round(duration_sec * fps))


def duration_for_nframes(nframes: int, fps: float) -> float:
    return nframes / fps


def soft_max_sec(vod: dict[str, Any]) -> float:
    """Configured soft max duration (default 37s)."""
    return float(vod.get("max_duration_sec", 37))


def hard_max_sec(vod: dict[str, Any]) -> float:
    """Hard ceiling when bypass is allowed (falls back to soft max)."""
    return float(vod.get("max_duration_sec_hard", vod.get("max_duration_sec", 120)))


def effective_max_sec(cfg: dict[str, Any]) -> float:
    """Upper clamp for chooser / ffprobe gate."""
    vod = cfg.get("vod") or {}
    soft = soft_max_sec(vod)
    hard = hard_max_sec(vod)
    if bool(vod.get("allow_bypass_max", False)):
        return hard
    return min(soft, hard)


def effective_min_sec(cfg: dict[str, Any]) -> float:
    """Lower clamp for chooser (default 7s)."""
    vod = cfg.get("vod") or {}
    return float(vod.get("min_duration_sec", 7))


def _gcd(a: int, b: int) -> int:
    return math.gcd(a, b)


def _lcm(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return abs(a * b) // _gcd(a, b)


def lcm_many(values: list[int], *, cap: int) -> int:
    """LCM of positive ints, capped; on overflow falls back to largest single period ≤ cap."""
    vals = [v for v in values if v > 0]
    if not vals:
        return 1
    out = vals[0]
    for v in vals[1:]:
        out = _lcm(out, v)
        if out > cap or out <= 0:
            # Cap runaway LCMs — fall back to GCD-friendly max single period ≤ cap
            return max(v for v in vals if v <= cap) if any(v <= cap for v in vals) else 1
    return max(1, min(out, cap))


def periods_to_frames(periods_sec: list[float], fps: float, *, max_frames: int) -> list[int]:
    """Convert period seconds to frame counts; always includes a whole-second period."""
    frames: list[int] = []
    for p in periods_sec:
        n = int(round(float(p) * fps))
        if 1 <= n <= max_frames:
            frames.append(n)
    # Always allow whole-second closure (seamless at fps boundaries)
    sec = int(round(fps))
    if 1 <= sec <= max_frames:
        frames.append(sec)
    # Dedupe
    return sorted(set(frames))


def snap_duration_to_periods(
    target_sec: float,
    periods_sec: list[float],
    *,
    lo: float,
    hi: float,
    fps: float,
) -> tuple[float, dict[str, Any]]:
    """Snap target duration to nearest loop-closing multiple of periodic periods.

    Returns (duration_sec, meta) where meta explains the snap.
    """
    max_frames = nframes_for_duration(hi, fps)
    min_frames = nframes_for_duration(lo, fps)
    period_frames = periods_to_frames(periods_sec, fps, max_frames=max_frames)
    meta: dict[str, Any] = {
        "target_sec": target_sec,
        "period_frames": period_frames,
        "snapped": False,
    }
    if not period_frames:
        dur = clamp(target_sec, lo, hi)
        meta["duration_sec"] = dur
        return dur, meta

    fund = lcm_many(period_frames, cap=max_frames)
    meta["fundamental_frames"] = fund
    if fund <= 0:
        dur = clamp(target_sec, lo, hi)
        meta["duration_sec"] = dur
        return dur, meta

    target_frames = nframes_for_duration(target_sec, fps)
    # k * fund nearest to target, within [min_frames, max_frames]
    k_min = max(1, math.ceil(min_frames / fund))
    k_max = max(k_min, math.floor(max_frames / fund))
    if k_max < k_min:
        # Cannot fit period — clamp target without snap
        dur = clamp(target_sec, lo, hi)
        meta["duration_sec"] = dur
        meta["snap_failed"] = "band_too_narrow_for_period"
        return dur, meta

    k_ideal = target_frames / fund
    k = int(round(k_ideal))
    k = int(clamp(k, k_min, k_max))
    # Prefer neighbor if closer to target
    candidates = {k}
    if k > k_min:
        candidates.add(k - 1)
    if k < k_max:
        candidates.add(k + 1)
    best_k = min(candidates, key=lambda kk: abs(kk * fund - target_frames))
    nframes = best_k * fund
    dur = duration_for_nframes(nframes, fps)
    dur = clamp(dur, lo, hi)
    # Re-derive nframes after clamp (may break exact period if clamp hits edge)
    nframes = nframes_for_duration(dur, fps)
    if nframes % fund != 0:
        # Pull back to nearest valid multiple inside band
        k2 = int(clamp(round(nframes / fund), k_min, k_max))
        nframes = k2 * fund
        dur = duration_for_nframes(nframes, fps)
    meta.update(
        {
            "snapped": True,
            "k": best_k,
            "nframes": nframes,
            "duration_sec": dur,
        }
    )
    return dur, meta


def choose_duration_sec(cfg: dict[str, Any], job: dict[str, Any] | None = None) -> float:
    """Return target duration in seconds within the effective band."""
    vod = cfg.get("vod") or {}
    lo = effective_min_sec(cfg)
    hi = effective_max_sec(cfg)
    job = job or {}

    if os.environ.get("JELLYFLAM3_SMOKE") == "1":
        fps = float(vod.get("fps", 24))
        if "smoke_duration_sec" in vod:
            return float(vod.get("smoke_duration_sec", 13))
        smoke_n = int(vod.get("smoke_nframes", 312))
        return duration_for_nframes(smoke_n, fps)

    if "duration_sec" in job:
        return clamp(float(job["duration_sec"]), lo, hi)
    if "nframes" in job and "duration_sec" not in job and job.get("signals") is None:
        fps = float(vod.get("fps", 24))
        return clamp(duration_for_nframes(int(job["nframes"]), fps), lo, hi)

    mode = str(vod.get("duration_mode", "fixed")).lower()
    base = float(vod.get("target_duration_sec", 23))
    fps = float(vod.get("fps", 24))

    if mode != "dynamic":
        return clamp(base, lo, hi)

    dyn = vod.get("dynamic") or {}
    base = float(dyn.get("base_sec", base))
    weights = dict(dyn.get("weights") or {})
    signals = dict(job.get("signals") or {})

    # Optional XML path on job
    if not signals and job.get("genome_xml"):
        signals = extract_genome_signals(str(job["genome_xml"]))
        job["signals"] = signals
    if not signals and job.get("genome_path"):
        from pathlib import Path

        p = Path(str(job["genome_path"]))
        if p.is_file():
            signals = extract_genome_signals(
                p.read_text(encoding="utf-8", errors="replace")
            )
            job["signals"] = signals

    total = base
    for key, weight in weights.items():
        if key == "jitter_sec":
            continue
        total += float(weight) * float(signals.get(key, 0.0))

    # Profile short bias (HW -04)
    profile = str((cfg.get("render") or {}).get("hw_profile") or "")
    if profile.endswith("04") or profile.endswith("-04") or profile.endswith("_04"):
        total -= float(dyn.get("profile_04_short_bias", 4) or 0)

    jitter = float(weights.get("jitter_sec", 0) or 0)
    if jitter:
        total += random.uniform(-jitter, jitter)

    # Soft max may be exceeded only when bypass enabled (hi already reflects that)
    total = clamp(total, lo, hi)

    # Period-aware loop closure. Frozen orbits have no 360° motion — do not
    # treat flame rotate= as a loop period (would snap a still to a fake length).
    periods = list(signals.get("period_candidates_sec") or [])
    if signals.get("orbit_frozen"):
        periods = []
    snap_enabled = bool(dyn.get("snap_to_periods", True))
    if snap_enabled and periods:
        snapped, meta = snap_duration_to_periods(total, periods, lo=lo, hi=hi, fps=fps)
        job.setdefault("duration_meta", {})["period_snap"] = meta
        return snapped

    return total


def choose_nframes(cfg: dict[str, Any], job: dict[str, Any] | None = None) -> int:
    """Frame count for render; wraps ``choose_duration_sec`` unless job/smoke pin nframes."""
    vod = cfg.get("vod") or {}
    fps = float(vod.get("fps", 24))
    if os.environ.get("JELLYFLAM3_SMOKE") == "1":
        if "smoke_duration_sec" in vod:
            return nframes_for_duration(float(vod.get("smoke_duration_sec", 13)), fps)
        return int(vod.get("smoke_nframes", 312))
    job = job or {}
    if "nframes" in job and "duration_sec" not in job and not job.get("signals"):
        n = int(job["nframes"])
        lo = nframes_for_duration(effective_min_sec(cfg), fps)
        hi = nframes_for_duration(effective_max_sec(cfg), fps)
        return int(clamp(n, lo, hi))
    return nframes_for_duration(choose_duration_sec(cfg, job), fps)


def assert_duration_in_band(
    duration_sec: float, cfg: dict[str, Any], *, tol: float = 0.51
) -> None:
    """Raise ValueError if duration is outside the effective band (skipped in smoke)."""
    if os.environ.get("JELLYFLAM3_SMOKE") == "1":
        return
    lo = effective_min_sec(cfg)
    hi = effective_max_sec(cfg)
    if duration_sec + tol < lo or duration_sec - tol > hi:
        raise ValueError(f"duration {duration_sec:.3f}s outside [{lo}, {hi}]")
