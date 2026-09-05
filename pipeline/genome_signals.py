"""Purpose: Extract flam3 genome signals for dynamic VoD duration (Phase 2 guide 08).

Requirements: Genome XML text (``<flame>`` or ``<flames>`` wrapper).

Usage: ``extract_genome_signals(xml)`` → complexity / period candidates for choose_duration.
  ``is_linear_only_genome`` / ``is_singularity_cloned`` — Pathway A dud gates.
  ``is_orbit_frozen`` / ``should_still_loop`` — static ``sequence=`` predictor (worker still-loop).

Assumptions: Periods come from rotate, color_speed, and animated xform weights; malformed XML is wrapped when needed.
  Flam3 ``symmetry>0`` on an xform implies ``animate=0`` (frozen orbit). Frozen single-flame
  genomes skip period snap and may still-loop instead of a 360° Lite animate.
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


# Non-variation <xform> / <finalxform> attributes (IFS structural knobs).
XFORM_STRUCTURAL_ATTRS = frozenset(
    {
        "weight",
        "color",
        "symmetry",
        "coefs",
        "animate",
        "color_speed",
        "opacity",
        "var_color",
        "chaos",
        "plotmode",
        "name",
    }
)


def _xform_variation_names(el: ET.Element) -> set[str]:
    """Variation names with |weight| > 0 on an xform (implicit linear if none)."""
    names: set[str] = set()
    for attr, val in el.attrib.items():
        if attr in XFORM_STRUCTURAL_ATTRS:
            continue
        try:
            if abs(float(val)) > 1e-12:
                names.add(attr)
        except ValueError:
            continue
    return names


def _xform_is_linear_only(el: ET.Element) -> bool:
    """True when the xform is implicit linear or only ``linear`` is non-zero."""
    names = _xform_variation_names(el)
    return not names or names <= {"linear"}


def _iter_xforms(xml_text: str) -> list[ET.Element] | None:
    """Return xform/finalxform elements, or None if XML cannot be parsed."""
    try:
        root = _parse_root(xml_text)
    except ET.ParseError:
        return None
    out: list[ET.Element] = []
    for flame in _flames(root):
        for child in list(flame):
            if _xform_tag(child) in ("xform", "finalxform"):
                out.append(child)
    return out


def is_linear_only_genome(xml_text: str) -> bool:
    """True when every IFS xform is linear-only (Electric Sheep singularities / voids).

    Implicit linear (no variation attrs) counts. A single non-linear variation
    (julia, spherical, spiral, …) is enough to pass. Unparseable XML is False
    so sheep_tax can own that failure.
    """
    xforms = _iter_xforms(xml_text)
    if xforms is None:
        return False
    if not xforms:
        return True
    return all(_xform_is_linear_only(el) for el in xforms)


def is_singularity_cloned(xml_text: str) -> bool:
    """True when any ``<flame singularity="cloned">`` (ES singularities brood clone)."""
    try:
        root = _parse_root(xml_text)
    except ET.ParseError:
        return False
    for flame in _flames(root):
        val = (flame.get("singularity") or "").strip().lower()
        if val == "cloned":
            return True
    return False


def _has_motion_child(el: ET.Element) -> bool:
    """True when the xform has a flam3 ``<motion>`` child (cyclic param animation)."""
    return any(_xform_tag(child) == "motion" for child in list(el))


def effective_xform_animate(el: ET.Element) -> float:
    """Flam3-effective ``animate`` for one ``<xform>`` (explicit attr wins).

    Parser rules from flam3 ``parser.c``:

    - ``animate`` present → that value
    - else deprecated ``symmetry`` present → ``0`` if ``symmetry > 0``, else ``1``
    - else omitted → ``1`` (flam3 default; xforms orbit during ``sequence=``)
    """
    raw_animate = el.get("animate")
    if raw_animate is not None and str(raw_animate).strip() != "":
        return _f(raw_animate, 0.0)
    raw_sym = el.get("symmetry")
    if raw_sym is not None and str(raw_sym).strip() != "":
        return 0.0 if _f(raw_sym, 0.0) > 0.0 else 1.0
    return 1.0


def _iter_orbit_xforms(xml_text: str) -> list[ET.Element] | None:
    """Non-final ``<xform>`` elements, or None if XML cannot be parsed.

    ``<finalxform>`` is ignored: flam3 never rotates finals during ``sequence=``.
    """
    try:
        root = _parse_root(xml_text)
    except ET.ParseError:
        return None
    out: list[ET.Element] = []
    for flame in _flames(root):
        for child in list(flame):
            if _xform_tag(child) == "xform":
                out.append(child)
    return out


def is_orbit_frozen(xml_text: str) -> bool:
    """True when ``flam3-genome sequence=`` cannot 360°-orbit any IFS xform.

    Every non-final xform is stationary (effective ``animate == 0``) and none
    carry a ``<motion>`` child. A single flame with this shape encodes as a
    still (lab: ``electricsheep.245.09797``). Unparseable XML is False.
    """
    xforms = _iter_orbit_xforms(xml_text)
    if xforms is None:
        return False
    if not xforms:
        return True
    if any(_has_motion_child(el) for el in xforms):
        return False
    return all(abs(effective_xform_animate(el)) < 1e-12 for el in xforms)


def should_still_loop(xml_text: str, cfg: dict[str, Any] | None = None) -> bool:
    """True when the worker should skip sequence/animate and encode a still-loop.

    Requires a frozen orbit, fewer than two ``<flame>`` control points (two-flame
    files can still morph on the transition stage), and
    ``render.still_loop_if_orbit_frozen`` (default **true**).
    """
    render = (cfg or {}).get("render") or {}
    if not bool(render.get("still_loop_if_orbit_frozen", True)):
        return False
    try:
        root = _parse_root(xml_text)
    except ET.ParseError:
        return False
    if len(_flames(root)) >= 2:
        return False
    return is_orbit_frozen(xml_text)


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
    effective_animate_count = 0
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
                if abs(effective_xform_animate(child)) >= 1e-12:
                    effective_animate_count += 1
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

    orbit_frozen = is_orbit_frozen(xml_text)
    if orbit_frozen:
        # Static sequence: rotate= is a camera pose, not a loop period.
        periods: list[float] = []
    else:
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
        "effective_animate_count": effective_animate_count,
        "orbit_frozen": orbit_frozen,
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
