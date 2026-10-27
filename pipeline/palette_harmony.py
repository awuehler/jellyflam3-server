"""Purpose: Ambient-TV palette harmonies in OkLCh (no third-party color deps).

Requirements: stdlib only (math, re, xml.etree). Inline ``<color rgb=…>`` strips are sampled directly. A flam3 ``palette="N"`` index is resolved from ``flam3-palettes.xml`` before sampling.

Usage: ``apply_palette_harmony(xml_text, cfg)`` from TV-optimize / worker; helpers for OkLCh convert + dual-pole gradients.

Assumptions: Rewrites toward complementary / split-complementary dual-pole gradients suited to living-room ambient viewing; ``palette.mode`` off/none skips. A missing color strip is never replaced with gray. An unresolved palette index is left for flam3-render; a genome with neither colors nor an index is refused.
"""

from __future__ import annotations

import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


# --- sRGB ↔ linear ↔ OkLab / OkLCh (Björn Ottosson) ---------------------------------


def _srgb_to_linear(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    if c <= 0.0031308:
        v = 12.92 * c
    else:
        v = 1.055 * (c ** (1 / 2.4)) - 0.055
    return max(0.0, min(255.0, v * 255.0))


def srgb_to_oklab(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert 0–255 sRGB channels to OkLab (L, a, b)."""
    lr, lg, lb = _srgb_to_linear(r), _srgb_to_linear(g), _srgb_to_linear(b)
    l_ = 0.4122214708 * lr + 0.5363325363 * lg + 0.0514459929 * lb
    m_ = 0.2119034982 * lr + 0.6806995451 * lg + 0.1073969566 * lb
    s_ = 0.0883024619 * lr + 0.2817188376 * lg + 0.6299787005 * lb
    l = l_ ** (1 / 3)
    m = m_ ** (1 / 3)
    s = s_ ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b_ = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, a, b_


def oklab_to_srgb(L: float, a: float, b_: float) -> tuple[int, int, int]:
    """Convert OkLab to integer 0–255 sRGB (clamped)."""
    l_ = L + 0.3963377774 * a + 0.2158037573 * b_
    m_ = L - 0.1055613458 * a - 0.0638541728 * b_
    s_ = L - 0.0894841775 * a - 1.2914855480 * b_
    l = l_ * l_ * l_
    m = m_ * m_ * m_
    s = s_ * s_ * s_
    lr = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    lg = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    lb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return (
        int(round(_linear_to_srgb(lr))),
        int(round(_linear_to_srgb(lg))),
        int(round(_linear_to_srgb(lb))),
    )


def oklab_to_oklch(L: float, a: float, b_: float) -> tuple[float, float, float]:
    """OkLab → OkLCh (L, C, hue degrees)."""
    C = math.sqrt(a * a + b_ * b_)
    h = math.degrees(math.atan2(b_, a)) % 360.0
    return L, C, h


def oklch_to_oklab(L: float, C: float, h_deg: float) -> tuple[float, float, float]:
    """OkLCh (hue in degrees) → OkLab."""
    h = math.radians(h_deg)
    return L, C * math.cos(h), C * math.sin(h)


def srgb_to_oklch(r: float, g: float, b: float) -> tuple[float, float, float]:
    return oklab_to_oklch(*srgb_to_oklab(r, g, b))


def oklch_to_srgb(L: float, C: float, h_deg: float) -> tuple[int, int, int]:
    return oklab_to_srgb(*oklch_to_oklab(L, C, h_deg))


@dataclass(frozen=True)
class HarmonyResult:
    mode: str
    seed_hex: str
    complement_hex: str
    xml: str
    # inline | index | curator | deferred | unresolved
    source: str = "inline"


def _parse_rgb_attr(val: str) -> tuple[int, int, int] | None:
    parts = val.replace(",", " ").split()
    if len(parts) < 3:
        return None
    try:
        return int(float(parts[0])), int(float(parts[1])), int(float(parts[2]))
    except ValueError:
        return None


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #RRGGBB, got {h!r}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


_PALETTE_CACHE: dict[str, tuple[int, dict[int, list[tuple[int, int, int]]]]] = {}


def _most_chromatic(colors: Iterable[tuple[int, int, int]]) -> tuple[int, int, int] | None:
    best: tuple[int, int, int] | None = None
    best_c = -1.0
    for rgb in colors:
        _L, chroma, _h = srgb_to_oklch(*rgb)
        if chroma > best_c:
            best_c = chroma
            best = rgb
    return best


def sample_genome_accent(xml_text: str) -> tuple[int, int, int] | None:
    """Pick the most chromatic inline ``rgb`` color, or None when the strip is absent."""
    found: list[tuple[int, int, int]] = []
    for m in re.finditer(r'rgb\s*=\s*"([^"]+)"', xml_text, re.I):
        rgb = _parse_rgb_attr(m.group(1))
        if rgb:
            found.append(rgb)
    return _most_chromatic(found)


def _rgb_to_hsv(r: int, g: int, b: int) -> tuple[float, float, float]:
    rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    delta = mx - mn
    if delta == 0 or mx == 0:
        return 0.0, 0.0, mx
    if mx == rf:
        hue = ((gf - bf) / delta) % 6.0
    elif mx == gf:
        hue = (bf - rf) / delta + 2.0
    else:
        hue = (rf - gf) / delta + 4.0
    return (hue / 6.0) % 1.0, delta / mx, mx


def _hsv_to_rgb(h: float, s: float, v: float) -> tuple[int, int, int]:
    h = h % 1.0
    sector = int(h * 6.0) % 6
    frac = h * 6.0 - int(h * 6.0)
    p = v * (1.0 - s)
    q = v * (1.0 - frac * s)
    t = v * (1.0 - (1.0 - frac) * s)
    rf, gf, bf = (
        (v, t, p),
        (q, v, p),
        (p, v, t),
        (p, q, v),
        (t, p, v),
        (v, p, q),
    )[sector]
    return int(round(rf * 255)), int(round(gf * 255)), int(round(bf * 255))


def rotate_palette_hue(
    colors: Iterable[tuple[int, int, int]],
    hue: float,
) -> list[tuple[int, int, int]]:
    """Rotate each color by flam3's 0–1 hue attribute. 0 and 1 leave the color in place."""
    turn = float(hue) % 1.0
    if turn == 0.0:
        return list(colors)
    out: list[tuple[int, int, int]] = []
    for r, g, b in colors:
        h, s, v = _rgb_to_hsv(r, g, b)
        out.append(_hsv_to_rgb(h + turn, s, v))
    return out


def _colors_from_palette_data(data: str) -> list[tuple[int, int, int]] | None:
    hexes = re.sub(r"[^0-9A-Fa-f]", "", data or "")
    width = 8 if len(hexes) >= 256 * 8 else 6
    if len(hexes) < 256 * width:
        return None
    colors: list[tuple[int, int, int]] = []
    for i in range(256):
        chunk = hexes[i * width : i * width + 6]
        colors.append((int(chunk[0:2], 16), int(chunk[2:4], 16), int(chunk[4:6], 16)))
    return colors


def parse_flam3_palettes(xml_text: str) -> dict[int, list[tuple[int, int, int]]]:
    """Index flam3 palette numbers to their 256 RGB entries."""
    root = ET.fromstring(xml_text)
    table: dict[int, list[tuple[int, int, int]]] = {}
    for el in root.iter("palette"):
        number = el.get("number")
        if number is None:
            continue
        try:
            index = int(float(number))
        except ValueError:
            continue
        colors = _colors_from_palette_data(el.get("data") or el.text or "")
        if colors:
            table[index] = colors
    return table


def flam3_palette_paths(cfg: dict[str, Any] | None = None) -> list[Path]:
    pal = (cfg or {}).get("palette") or {}
    paths: list[Path] = []
    configured = pal.get("flam3_palettes")
    if configured:
        paths.append(Path(str(configured)))
    env = os.environ.get("FLAM3_PALETTES")
    if env:
        paths.append(Path(env))
    paths.extend(
        [
            Path("/usr/local/share/flam3/flam3-palettes.xml"),
            Path("/usr/share/flam3/flam3-palettes.xml"),
        ]
    )
    return paths


def load_flam3_palettes(cfg: dict[str, Any] | None = None) -> dict[int, list[tuple[int, int, int]]] | None:
    """Load the first readable flam3 palette file. None when no file is installed."""
    for path in flam3_palette_paths(cfg):
        try:
            stat = path.stat()
        except OSError:
            continue
        cached = _PALETTE_CACHE.get(str(path))
        if cached and cached[0] == stat.st_mtime_ns:
            return cached[1]
        try:
            table = parse_flam3_palettes(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, ET.ParseError):
            continue
        if table:
            _PALETTE_CACHE[str(path)] = (stat.st_mtime_ns, table)
            return table
    return None


def _flame_palette_refs(xml_text: str) -> list[tuple[int | None, float]]:
    """Each flame's palette index and hue, in document order."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        try:
            root = ET.fromstring(f"<flames>{xml_text}</flames>")
        except ET.ParseError:
            return []
    flames = [root] if root.tag == "flame" else list(root.iter("flame"))
    refs: list[tuple[int | None, float]] = []
    for flame in flames:
        raw = flame.get("palette")
        index: int | None
        try:
            index = int(float(raw)) if raw not in (None, "") else None
        except ValueError:
            index = None
        if index is not None and index < 0:
            index = None
        try:
            hue = float(flame.get("hue") or 0.0)
        except ValueError:
            hue = 0.0
        refs.append((index, hue))
    return refs


def resolve_indexed_palette(
    xml_text: str,
    cfg: dict[str, Any] | None = None,
    *,
    palette_table: dict[int, list[tuple[int, int, int]]] | None = None,
) -> list[tuple[int, int, int]] | None:
    """Colors for every resolvable palette index. None when an index cannot be loaded."""
    refs = [(index, hue) for index, hue in _flame_palette_refs(xml_text) if index is not None]
    if not refs:
        return None
    table = palette_table if palette_table is not None else load_flam3_palettes(cfg)
    if not table:
        return None
    colors: list[tuple[int, int, int]] = []
    for index, hue in refs:
        found = table.get(index)
        if not found:
            return None
        colors.extend(rotate_palette_hue(found, hue))
    return colors or None


def harmony_poles(
    seed_rgb: tuple[int, int, int],
    *,
    mode: str = "complementary",
    split_delta_deg: float = 30.0,
    lightness_bias: str = "asymmetric",
    saturation_cap: float = 0.55,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Derive dual RGB poles from a seed (complementary or split-complementary).

    Caps chroma and optionally biases lightness for ambient midtones.
    """
    L, C, h = srgb_to_oklch(*seed_rgb)
    C = min(C, saturation_cap)
    if lightness_bias == "asymmetric":
        L_seed = min(0.78, max(0.42, L + 0.06))
        L_opp = min(0.55, max(0.28, L - 0.12))
    else:
        L_seed = L_opp = min(0.72, max(0.35, L))

    if mode == "split_complementary":
        h2 = (h + 180.0 - split_delta_deg) % 360.0
    else:
        h2 = (h + 180.0) % 360.0

    pole_a = oklch_to_srgb(L_seed, C, h)
    pole_b = oklch_to_srgb(L_opp, min(C * 0.92, saturation_cap), h2)
    return pole_a, pole_b


def dual_pole_gradient(
    pole_a: tuple[int, int, int],
    pole_b: tuple[int, int, int],
    n: int = 256,
) -> list[tuple[int, int, int]]:
    """Interpolate in OkLCh between poles across flam3's 256 palette slots."""
    La, Ca, ha = srgb_to_oklch(*pole_a)
    Lb, Cb, hb = srgb_to_oklch(*pole_b)
    # Shortest hue arc
    dh = ((hb - ha + 540) % 360) - 180
    out: list[tuple[int, int, int]] = []
    for i in range(n):
        t = i / (n - 1) if n > 1 else 0.0
        # Ease through mid so ambient midtones aren't neon
        te = t * t * (3 - 2 * t)
        L = La + (Lb - La) * te
        C = Ca + (Cb - Ca) * te
        h = (ha + dh * te) % 360.0
        out.append(oklch_to_srgb(L, C, h))
    return out


def _flame_elements(root: ET.Element) -> list[ET.Element]:
    if root.tag == "flame":
        return [root]
    return list(root.iter("flame"))


def rewrite_flam3_palette(
    xml_text: str,
    colors: Iterable[tuple[int, int, int]],
) -> str:
    """Replace each flame's ``<color>`` children with the given 256-slot RGB strip."""
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

    palette = list(colors)
    if len(palette) < 256:
        palette = palette + [palette[-1]] * (256 - len(palette))
    palette = palette[:256]

    for flame in _flame_elements(root):
        # Drop existing color children; replace with harmony strip.
        for child in list(flame):
            if child.tag == "color":
                flame.remove(child)
        for i, (r, g, b) in enumerate(palette):
            el = ET.Element("color", {"index": str(i), "rgb": f"{r} {g} {b}"})
            flame.append(el)
        flame.set("palette_mode", flame.get("palette_mode") or "linear")

    if multi_root:
        return decl + "".join(ET.tostring(child, encoding="unicode") for child in list(root))
    return decl + ET.tostring(root, encoding="unicode")


def _rewrite_from_seed(
    xml_text: str,
    cfg: dict[str, Any],
    seed_rgb: tuple[int, int, int],
    *,
    mode: str,
    source: str,
) -> HarmonyResult:
    pal = cfg.get("palette") or {}
    pole_a, pole_b = harmony_poles(
        seed_rgb,
        mode=mode,
        split_delta_deg=float(pal.get("split_delta_deg", 30)),
        lightness_bias=str(pal.get("lightness_bias") or "asymmetric"),
        saturation_cap=float(pal.get("saturation_cap", 0.55)),
    )
    colors = dual_pole_gradient(pole_a, pole_b, 256)
    return HarmonyResult(
        mode=mode,
        seed_hex=_rgb_to_hex(*pole_a),
        complement_hex=_rgb_to_hex(*pole_b),
        xml=rewrite_flam3_palette(xml_text, colors),
        source=source,
    )


def apply_palette_harmony(
    xml_text: str,
    cfg: dict[str, Any],
    *,
    palette_table: dict[int, list[tuple[int, int, int]]] | None = None,
) -> HarmonyResult | None:
    """Apply cfg ``palette`` harmony.

    Inline colors are sampled as they stand. A flam3 palette index is resolved
    and sampled when the palette file has that number. An index that cannot be
    resolved is left unchanged (``source="deferred"``) so flam3-render can load
    it and the preview gate can judge the still. A genome with neither colors
    nor an index is ``source="unresolved"`` and must not be rendered.
    """
    pal = cfg.get("palette") or {}
    mode = str(pal.get("mode", "complementary")).lower()
    if mode in ("", "off", "none", "false", "0"):
        return None

    seed_src = str(pal.get("seed") or "genome_accent")
    if seed_src == "curator_hex" and pal.get("curator_hex"):
        return _rewrite_from_seed(
            xml_text, cfg, _hex_to_rgb(str(pal["curator_hex"])), mode=mode, source="curator"
        )

    accent = sample_genome_accent(xml_text)
    if accent is not None:
        return _rewrite_from_seed(xml_text, cfg, accent, mode=mode, source="inline")

    indexed = resolve_indexed_palette(xml_text, cfg, palette_table=palette_table)
    if indexed:
        accent = _most_chromatic(indexed)
        if accent is not None:
            return _rewrite_from_seed(xml_text, cfg, accent, mode=mode, source="index")

    has_index = any(index is not None for index, _hue in _flame_palette_refs(xml_text))
    if has_index:
        return HarmonyResult(
            mode=mode, seed_hex="", complement_hex="", xml=xml_text, source="deferred"
        )
    return HarmonyResult(
        mode=mode, seed_hex="", complement_hex="", xml=xml_text, source="unresolved"
    )
