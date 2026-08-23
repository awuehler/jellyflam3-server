"""Purpose: sheepscale-style flam3 size/scale rewrite for TV aspect ratios.

Requirements: stdlib XML (ElementTree); valid flam3 ``<flame>`` XML (single or concatenated).

Usage: ``resize_flam3_xml(text, w, h)`` or ``resize_file(src, dest, …)`` from TV-optimize.

Assumptions: Scales ``scale`` by min(tw/cw, th/ch); default source size 800×592 when missing.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def _parse_size(flame: ET.Element) -> tuple[int, int]:
    """Read flame width/height from ``size`` or width/height attrs (fallback 800×592)."""
    size = flame.get("size")
    if size:
        parts = size.split()
        return int(float(parts[0])), int(float(parts[1]))
    w = flame.get("width")
    h = flame.get("height")
    if w and h:
        return int(float(w)), int(float(h))
    return 800, 592


def resize_flam3_xml(
    xml_text: str,
    target_width: int,
    target_height: int,
) -> str:
    """Rewrite every ``<flame>`` to target size and proportionally adjust ``scale``."""
    decl = ""
    m = re.match(r"^\s*<\?xml[^>]+\?>\s*", xml_text)
    if m:
        decl = m.group(0)
        xml_text = xml_text[m.end() :]

    multi_root = False
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        # Concatenated <flame> documents (common in Electric Sheep genomes).
        root = ET.fromstring(f"<flames>{xml_text}</flames>")
        multi_root = True

    flames = [root] if root.tag == "flame" else list(root.iter("flame"))
    if not flames:
        raise ValueError("no <flame> elements found")

    for flame in flames:
        cw, ch = _parse_size(flame)
        scale_factor = min(target_width / cw, target_height / ch)
        scale_attr = flame.get("scale")
        if scale_attr and scale_attr.lower() != "nan":
            try:
                current_scale = float(scale_attr)
                if math.isnan(current_scale):
                    current_scale = float(ch)
                flame.set("scale", str(current_scale * scale_factor))
            except ValueError:
                pass
        flame.set("size", f"{target_width} {target_height}")
        if "width" in flame.attrib:
            flame.set("width", str(target_width))
        if "height" in flame.attrib:
            flame.set("height", str(target_height))

    if multi_root:
        return decl + "".join(ET.tostring(child, encoding="unicode") for child in list(root))
    return decl + ET.tostring(root, encoding="unicode")


def resize_file(
    src: Path,
    dest: Path,
    target_width: int = 1920,
    target_height: int = 1080,
) -> Path:
    """Read ``src``, resize XML to target dimensions, write ``dest``; return ``dest``."""
    text = src.read_text(encoding="utf-8", errors="replace")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(resize_flam3_xml(text, target_width, target_height), encoding="utf-8")
    return dest
