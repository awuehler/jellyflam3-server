"""Purpose: TV-port / optimize — 16:9 aspect, Gold Sheep Lite quality, ambient palette.

Requirements: pipeline.resize_genome, pipeline.palette_harmony; cfg ``render.*`` / ``palette.*``.

Usage: ``tv_optimize_xml`` / ``tv_optimize_file`` from worker and archive_seed.

Assumptions: Order is resize → Gold Sheep Lite knobs → OkLCh palette; edition off/stock skips quality stamp.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pipeline.palette_harmony import HarmonyResult, apply_palette_harmony
from pipeline.resize_genome import resize_flam3_xml

log = logging.getLogger("jellyflam3.tv_optimize")

# Moderate quality > quantity for 3-core Pi (below full Gold ss4/q2000/ts1000).
# Used for -16/-08 (gold_sheep_lite) and -04 (compact = same quality, shorter loops).
GOLD_SHEEP_LITE_DEFAULTS: dict[str, str] = {
    "supersample": "2",
    "filter": "1",
    "filter_shape": "gaussian",
    "temporal_filter_type": "box",
    "temporal_filter_width": "1.2",
    "quality": "900",
    "passes": "1",
    "temporal_samples": "450",
    "estimator_radius": "9",
    "estimator_minimum": "0",
    "estimator_curve": "0.6",
    "gamma_threshold": "0.01",
}


def _edition_base_attrs(edition: str) -> dict[str, str] | None:
    """Return Gold Sheep Lite attr defaults for edition, or None if stock/off."""
    ed = edition.lower().strip()
    if ed in ("off", "none", "stock", "false"):
        return None
    # gold_sheep_lite / compact (-04) / legacy derated → same Lite knobs.
    # Duration/disk differ in profile overlays + profile_04_short_bias, not here.
    return dict(GOLD_SHEEP_LITE_DEFAULTS)


def gold_lite_attrs(cfg: dict[str, Any]) -> dict[str, str]:
    """Quality knobs for TV-port (Gold Sheep Lite / compact), with render.* overlays."""
    render = cfg.get("render") or {}
    edition = str(render.get("edition") or "gold_sheep_lite")
    base = _edition_base_attrs(edition)
    if base is None:
        return {}
    attrs = base
    mapping = {
        "quality": "quality",
        "temporal_samples": "temporal_samples",
        "supersample": "supersample",
        "temporal_filter_width": "temporal_filter_width",
        "estimator_radius": "estimator_radius",
    }
    for cfg_key, attr in mapping.items():
        if cfg_key in render and render[cfg_key] is not None:
            attrs[attr] = str(render[cfg_key])
    return attrs


def apply_gold_lite_quality(xml_text: str, cfg: dict[str, Any]) -> str:
    """Stamp edition quality knobs onto every <flame> (Pi-friendly)."""
    edition = str((cfg.get("render") or {}).get("edition") or "gold_sheep_lite").lower()
    if edition in ("off", "none", "stock", "false"):
        return xml_text

    attrs = gold_lite_attrs(cfg)
    if not attrs:
        return xml_text
    decl = ""
    m = re.match(r"^\s*<\?xml[^>]+\?>\s*", xml_text)
    if m:
        decl = m.group(0)
        xml_text = xml_text[m.end() :]

    multi_root = False
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        root = ET.fromstring(f"<flames>{xml_text}</flames>")
        multi_root = True

    flames = [root] if root.tag == "flame" else list(root.iter("flame"))
    for flame in flames:
        for k, v in attrs.items():
            flame.set(k, v)

    if multi_root:
        return decl + "".join(ET.tostring(child, encoding="unicode") for child in list(root))
    return decl + ET.tostring(root, encoding="unicode")


def tv_optimize_xml(xml_text: str, cfg: dict[str, Any]) -> tuple[str, HarmonyResult | None]:
    """16:9 TV aspect → Gold Sheep Lite quality → ambient OkLCh palette."""
    render = cfg.get("render") or {}
    tw = int(render.get("target_width", 1920))
    th = int(render.get("target_height", 1080))
    xml = resize_flam3_xml(xml_text, tw, th)
    xml = apply_gold_lite_quality(xml, cfg)
    harmony = apply_palette_harmony(xml, cfg)
    if harmony is not None:
        log.info(
            "palette mode=%s seed=%s complement=%s",
            harmony.mode,
            harmony.seed_hex,
            harmony.complement_hex,
        )
        return harmony.xml, harmony
    return xml, None


def tv_optimize_file(src: Path, dest: Path, cfg: dict[str, Any]) -> tuple[Path, HarmonyResult | None]:
    """TV-optimize ``src`` to ``dest``; return (dest, harmony or None)."""
    text = src.read_text(encoding="utf-8", errors="replace")
    out, harmony = tv_optimize_xml(text, cfg)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(out, encoding="utf-8")
    return dest, harmony


def cache_edition_key(cfg: dict[str, Any]) -> str:
    """Cache key fragment from render edition + palette mode (for archive TV-port cache)."""
    render = cfg.get("render") or {}
    pal = cfg.get("palette") or {}
    edition = str(render.get("edition") or "gold_sheep_lite")
    mode = str(pal.get("mode") or "off")
    return f"{edition}-{mode}"
