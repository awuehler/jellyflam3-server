"""Purpose: Extract flam3 genome signals for dynamic VoD duration (Phase 2 guide 08).

Requirements: Genome XML text (``<flame>`` or ``<flames>`` wrapper).

Usage: ``extract_genome_signals(xml)`` → complexity / period candidates for choose_duration.

Assumptions: Periods come from rotate, color_speed, and animated xform weights; malformed XML is wrapped when needed.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any


def _parse_root(xml_text: str) -> ET.Element:
    """Parse genome XML; wrap fragments in ``<flames>`` when bare parse fails."""
    body = xml_text.strip()
    m = re.match(r"^\s*<\?xml[^>]+\?>\s*", body)
    if m:
        body = body[m.end() :]
    try:
        return ET.fromstring(body)
    except ET.ParseError:
        return ET.fromstring(f"<flames>{body}</flames>")


def _flames(root: ET.Element) -> list[ET.Element]:
    """All ``flame`` elements under root (or ``[root]`` if root is a flame)."""
    if root.tag == "flame":
        return [root]
    return list(root.iter("flame"))


def _f(val: str | None, default: float = 0.0) -> float:
    """Parse float attribute; return ``default`` on missing/invalid."""
    if val is None or str(val).strip() == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default


def _xform_tag(el: ET.Element) -> str:
    """Local tag name without XML namespace prefix."""
    return el.tag.split("}")[-1] if "}" in el.tag else el.tag


def extract_genome_signals(xml_text: str) -> dict[str, Any]:
    """Parse genome XML into numeric signals for duration choice.

    Includes complexity heuristics and **periodic** parameter metadata
    (rotation, color_speed, animated xform weights) used to snap loop length
    so the VoD closes cleanly.
    """
    root = _parse_root(xml_text)
    flames = _flames(root)
    flame_count = len(flames)

    xform_count = 0
    animate_count = 0
    finalxform_count = 0
    variation_hits = 0
    color_speeds: list[float] = []
    weights: list[float] = []
    rotate_degs: list[float] = []

    known_vars = {
        "linear",
        "sinusoidal",
        "spherical",
        "swirl",
        "horseshoe",
        "polar",
        "handkerchief",
        "heart",
        "disc",
        "spiral",
        "hyperbolic",
        "diamond",
        "ex",
        "julia",
        "julian",
        "juliascope",
        "bent",
        "waves",
        "fisheye",
        "popcorn",
        "exponential",
        "power",
        "cosine",
        "rings",
        "fan",
        "blob",
        "pdj",
        "fan2",
        "rings2",
        "eyefish",
        "bubble",
        "cylinder",
        "perspective",
        "noise",
        "gaussian_blur",
        "radial_blur",
        "pie",
        "ngon",
        "curl",
        "rectangles",
        "arch",
        "tangent",
        "square",
        "rays",
        "blade",
        "sec",
        "super_shape",
    }

    for flame in flames:
        rotate_degs.append(_f(flame.get("rotate"), 0.0))
        for child in list(flame):
            tag = _xform_tag(child)
            if tag not in ("xform", "finalxform"):
                continue
            if tag == "finalxform":
                finalxform_count += 1
            else:
                xform_count += 1
            if _f(child.get("animate"), 0.0) != 0.0:
                animate_count += 1
            cs = child.get("color_speed")
            if cs is not None:
                color_speeds.append(abs(_f(cs, 0.0)))
            w = child.get("weight")
            if w is not None and tag == "xform":
                weights.append(abs(_f(w, 0.0)))
            for attr, val in child.attrib.items():
                if attr in known_vars:
                    try:
                        if abs(float(val)) > 1e-12:
                            variation_hits += 1
                    except ValueError:
                        pass

    complexity = (
        0.15 * xform_count
        + 0.10 * animate_count
        + 0.05 * variation_hits
        + 0.20 * max(0, flame_count - 1)
        + 0.05 * finalxform_count
    )
    multi_flame_risk = 1.0 if flame_count > 1 else 0.0

    primary_rotate = rotate_degs[0] if rotate_degs else 0.0
    rotate_turns = abs(primary_rotate) / 360.0 if abs(primary_rotate) > 1e-9 else 0.0
    rotate_closed = rotate_turns == 0.0 or abs(rotate_turns - round(rotate_turns)) < 1e-3

    periods = _period_candidates_sec(
        rotate_deg=primary_rotate,
        color_speeds=color_speeds,
        weights=weights,
        animate_count=animate_count,
    )

    return {
        "flame_count": flame_count,
        "xform_count": xform_count,
        "animate_count": animate_count,
        "finalxform_count": finalxform_count,
        "variation_hits": variation_hits,
        "complexity": round(complexity, 4),
        "multi_flame_risk": multi_flame_risk,
        "rotate_deg": primary_rotate,
        "rotate_turns": round(rotate_turns, 6),
        "rotate_closed": rotate_closed,
        "color_speeds": color_speeds,
        "xform_weights": weights,
        "period_candidates_sec": periods,
        "fundamental_period_sec": periods[0] if periods else None,
    }


def _period_candidates_sec(
    *,
    rotate_deg: float,
    color_speeds: list[float],
    weights: list[float],
    animate_count: int,
) -> list[float]:
    """Strictly periodic parameter periods (seconds) for loop-closure snap.

    - Rotation: periods that complete integer flame turns relative to a unit orbit.
    - Color shifts: ``color_speed`` as cycles/sec → period = 1/speed.
    - Transformation weights (animated): reciprocal of normalized weight.
    """
    periods: list[float] = []

    if abs(rotate_deg) > 1e-6:
        turns = abs(rotate_deg) / 360.0
        if turns > 0:
            if turns >= 1.0:
                periods.append(1.0 / turns)
            else:
                periods.append(1.0 / turns)  # time to complete one full turn
            if abs(rotate_deg % 180.0) < 1e-3 or abs((rotate_deg % 180.0) - 180) < 1e-3:
                periods.append(0.5)

    for cs in color_speeds:
        if 1e-4 < cs <= 2.0:
            periods.append(1.0 / cs)

    if animate_count > 0 and weights:
        total = sum(weights) or 1.0
        for w in weights:
            nw = w / total
            if 1e-3 < nw < 0.999:
                periods.append(1.0 / nw)

    out: list[float] = []
    for p in sorted(periods):
        if p < 0.05 or p > 60.0:
            continue
        if not out or abs(out[-1] - p) > 1e-6:
            out.append(round(p, 6))
    return out[:12]


def estimate_queue_pressure(inbox_count: int, *, soft_cap: int = 8) -> float:
    """0..2 signal: empty inbox → 0, at soft_cap → 1."""
    if soft_cap <= 0:
        return 0.0
    return min(2.0, max(0.0, inbox_count / float(soft_cap)))
