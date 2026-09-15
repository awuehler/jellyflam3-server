"""Active worker quality gates for preventing sub-standard catalog publication.

Genetic and palette checks run before the expensive animation. A single rendered
preview and the encoded midpoint are checked for visual desaturation. Rejected
jobs raise ``QualityGateRejected`` so the worker's normal failure path moves the
claimed genome to quarantine instead of publishing it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.genome_signals import (
    extract_genome_signals,
    is_linear_only_genome,
    is_singularity_cloned,
)


class QualityGateRejected(RuntimeError):
    """A job failed an active artistic-quality admission check."""


def _hex_chroma(hex_color: str | None) -> float | None:
    """Return normalized RGB channel spread for ``#RRGGBB``."""
    if not hex_color:
        return None
    hx = hex_color.lstrip("#")
    if len(hx) != 6:
        return None
    try:
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    except ValueError:
        return None
    return (max(r, g, b) - min(r, g, b)) / 255.0


def palette_washed_out(
    palette: dict[str, Any],
    *,
    max_chroma: float = 0.40,
) -> bool:
    """True when both harmony poles have low absolute chroma."""
    seed = palette.get("seed_hex")
    complement = palette.get("complement_hex")
    s = _hex_chroma(seed if isinstance(seed, str) else None)
    c = _hex_chroma(complement if isinstance(complement, str) else None)
    if s is None or c is None:
        return False
    return s < max_chroma and c < max_chroma


def image_mean_saturation(path: Path, *, sample_w: int = 64) -> float | None:
    """Mean per-pixel RGB channel spread in [0, 1] over a small sample."""
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        im = Image.open(path).convert("RGB")
    except OSError:
        return None
    w, h = im.size
    if w < 1 or h < 1:
        return None
    tw = max(8, min(sample_w, w))
    th = max(8, int(tw * h / w))
    small = im.resize((tw, th), Image.Resampling.BILINEAR)
    total = 0.0
    n = 0
    pixels = getattr(small, "get_flattened_data", None)
    data = pixels() if callable(pixels) else small.getdata()
    for r, g, b in data:
        mx = max(r, g, b)
        sat = 0.0 if mx == 0 else (mx - min(r, g, b)) / 255.0
        total += sat
        n += 1
    if n == 0:
        return None
    return total / n


def genome_dud_reasons(xml_text: str) -> list[str]:
    """Return stable reason codes for genetics that cannot be repaired by retint."""
    reasons: list[str] = []
    if is_linear_only_genome(xml_text):
        reasons.append("genome_linear_only")
    if is_singularity_cloned(xml_text):
        reasons.append("genome_singularity_cloned")
    return reasons


def quality_gate_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return active gate policy with fail-closed production defaults."""
    raw = dict(cfg.get("quality_gate") or {})
    refactor = dict(cfg.get("refactor") or {})
    return {
        "enabled": bool(raw.get("enabled", True)),
        "reject_linear_only": bool(raw.get("reject_linear_only", True)),
        "reject_singularity_cloned": bool(raw.get("reject_singularity_cloned", True)),
        "reject_orbit_frozen": bool(raw.get("reject_orbit_frozen", True)),
        "reject_washed_palette": bool(raw.get("reject_washed_palette", True)),
        "check_preview_saturation": bool(raw.get("check_preview_saturation", True)),
        "check_output_saturation": bool(raw.get("check_output_saturation", True)),
        "fail_on_unreadable_image": bool(raw.get("fail_on_unreadable_image", True)),
        "palette_max_chroma": float(raw.get("palette_max_chroma", 0.40)),
        "desat_mean_max": float(
            raw.get("desat_mean_max", refactor.get("desat_mean_max", 0.12))
        ),
    }


def _result(
    stage: str,
    reasons: list[str],
    *,
    metrics: dict[str, Any] | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "rejected" if reasons else ("passed" if enabled else "disabled"),
        "reasons": reasons,
        "metrics": metrics or {},
    }


def assess_genome_quality(
    cfg: dict[str, Any],
    xml_text: str,
    *,
    palette: dict[str, Any] | None = None,
    is_tuple: bool = False,
) -> dict[str, Any]:
    """Assess defects knowable before rendering any animation frames."""
    policy = quality_gate_cfg(cfg)
    if not policy["enabled"]:
        return _result("pre_render_genome", [], enabled=False)

    signals = extract_genome_signals(xml_text)
    reasons: list[str] = []
    duds = genome_dud_reasons(xml_text)
    if policy["reject_linear_only"] and "genome_linear_only" in duds:
        reasons.append("genome_linear_only")
    if policy["reject_singularity_cloned"] and "genome_singularity_cloned" in duds:
        reasons.append("genome_singularity_cloned")

    # Multi-flame tuple/control-point inputs can visibly morph even when every
    # individual orbit is stationary. Reject only the single-flame static shape.
    if (
        policy["reject_orbit_frozen"]
        and not is_tuple
        and int(signals.get("flame_count") or 0) < 2
        and bool(signals.get("orbit_frozen"))
    ):
        reasons.append("genome_orbit_frozen")

    pal = dict(palette or {})
    if policy["reject_washed_palette"] and pal and palette_washed_out(
        pal, max_chroma=policy["palette_max_chroma"]
    ):
        reasons.append("palette_washed_out")

    return _result(
        "pre_render_genome",
        list(dict.fromkeys(reasons)),
        metrics={
            "flame_count": signals.get("flame_count"),
            "effective_animate_count": signals.get("effective_animate_count"),
            "orbit_frozen": signals.get("orbit_frozen"),
            "palette": pal,
        },
    )


def assess_image_quality(
    cfg: dict[str, Any],
    image: Path,
    *,
    stage: str,
) -> dict[str, Any]:
    """Reject a washed-out preview/output image using refactor's saturation metric."""
    policy = quality_gate_cfg(cfg)
    if not policy["enabled"]:
        return _result(stage, [], enabled=False)
    if stage == "pre_render_preview" and not policy["check_preview_saturation"]:
        return _result(stage, [], enabled=False)
    if stage == "pre_publish_output" and not policy["check_output_saturation"]:
        return _result(stage, [], enabled=False)

    mean_sat = image_mean_saturation(Path(image))
    reasons: list[str] = []
    if mean_sat is None:
        if policy["fail_on_unreadable_image"]:
            reasons.append("quality_image_unreadable")
    elif mean_sat < policy["desat_mean_max"]:
        reasons.append("catalog_desaturated")
    return _result(
        stage,
        reasons,
        metrics={
            "image": str(image),
            "mean_saturation": mean_sat,
            "minimum_mean_saturation": policy["desat_mean_max"],
        },
    )


def enforce_quality(result: dict[str, Any]) -> None:
    """Raise when an assessment rejected the job."""
    if result.get("status") != "rejected":
        return
    stage = str(result.get("stage") or "unknown")
    reasons = ", ".join(str(x) for x in (result.get("reasons") or []))
    raise QualityGateRejected(f"quality gate {stage} rejected: {reasons}")
