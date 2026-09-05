"""Purpose: Phase 4 tuples — one MP4 of loop A + watermarked edge(A→B) + loop B.

Requirements: two single-flame parent ``.flam3`` files; flam3-genome ``sequence=`` (3 stages);
ffmpeg overlay on the middle stage; catalog under ``by-generation/tuple/``.

Usage::

  python3 -m pipeline.sheep_tuple --config configs/jellyflam3.yaml --from A.flam3 --to B.flam3
  python3 -m pipeline.sheep_tuple --dry-run --from A.flam3 --to B.flam3

Assumptions: A→B and B→A are distinct. Seamless motion comes from one ``sequence=`` of both
control points (rotate A, morph, rotate B) — not concat of independently encoded catalog MP4s.
Watermark applies only to the edge stage. Idle cron may pick ``tuple`` as a breed mode.
"""

from __future__ import annotations

import argparse
import logging
import os
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from pipeline.choose_duration import duration_for_nframes, effective_max_sec, nframes_for_duration
from pipeline.config import load_config, resolve_path
from pipeline.genome_signals import _flames, _parse_root, is_linear_only_genome, is_orbit_frozen
from pipeline.sheep_names import SHEEP_PREFIX, kind_of, normalize_stem, stem_of

log = logging.getLogger("jellyflam3.tuple")

TUPLE_KIND = "tuple"
_TO = "_to_"


def tuple_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """``tuple`` + ``watermark`` sections with defaults."""
    raw = dict(cfg.get("tuple") or {})
    wm = dict(cfg.get("watermark") or {})
    return {
        "enabled": bool(raw.get("enabled", True)),
        "stage_duration_sec": float(raw.get("stage_duration_sec", 13)),
        "watermark_on_edge": bool(raw.get("watermark_on_edge", True)),
        "watermark": {
            "enabled": bool(wm.get("enabled", True)),
            "style": str(wm.get("style") or "text"),
            "text": str(wm.get("text") or "Electric Sheep"),
            "font": str(wm.get("font") or ""),
            "opacity": float(wm.get("opacity", 0.45)),
            "position": str(wm.get("position") or "lower_right"),
            "image": str(wm.get("image") or ""),
        },
    }


def is_tuple_stem(stem: str) -> bool:
    """True when catalog/inbox stem is ``electricsheep.tuple.*``."""
    return (kind_of(stem_of(stem)) or "").lower() == TUPLE_KIND


def _bare_id(stem: str) -> str:
    """Strip ``electricsheep.`` prefix for compact tuple filenames."""
    s = normalize_stem(stem)
    prefix = f"{SHEEP_PREFIX}."
    if s.lower().startswith(prefix):
        return s[len(prefix) :]
    return s


def tuple_stem(from_stem: str, to_stem: str) -> str:
    """Catalog stem: ``electricsheep.tuple.{from}_to_{to}`` (order-sensitive)."""
    return f"{SHEEP_PREFIX}.{TUPLE_KIND}.{_bare_id(from_stem)}{_TO}{_bare_id(to_stem)}"


def tuple_flam3_name(from_stem: str, to_stem: str) -> str:
    from pipeline.sheep_names import tuple_filename

    return tuple_filename(from_stem, to_stem)


def parse_tuple_ids(stem: str) -> tuple[str, str] | None:
    """Return ``(from_id, to_id)`` full stems, or None if not a tuple name."""
    s = normalize_stem(stem)
    prefix = f"{SHEEP_PREFIX}.{TUPLE_KIND}."
    if not s.lower().startswith(prefix):
        return None
    rest = s[len(prefix) :]
    if _TO not in rest:
        return None
    a, b = rest.split(_TO, 1)
    if not a or not b:
        return None
    return f"{SHEEP_PREFIX}.{a}", f"{SHEEP_PREFIX}.{b}"


def catalog_tuple_mp4(cfg: dict[str, Any], from_stem: str, to_stem: str) -> Path:
    """``/media/sheep/by-generation/tuple/{stem}.mp4``."""
    media = resolve_path(cfg, "media_library")
    return media / "by-generation" / TUPLE_KIND / f"{tuple_stem(from_stem, to_stem)}.mp4"


def tuple_exists(cfg: dict[str, Any], from_stem: str, to_stem: str) -> bool:
    return catalog_tuple_mp4(cfg, from_stem, to_stem).is_file()


def stage_nframes(cfg: dict[str, Any]) -> int:
    """Frame count **per** flam3-genome sequence stage (loop A, edge, loop B)."""
    vod = cfg.get("vod") or {}
    fps = float(vod.get("fps", 24))
    stage_sec = float(tuple_cfg(cfg)["stage_duration_sec"])
    hard = effective_max_sec(cfg)
    # Three stages must stay at or under the hard duration ceiling.
    max_stage = max(1.0, (hard - 0.51) / 3.0)
    stage_sec = min(stage_sec, max_stage)
    return max(1, nframes_for_duration(stage_sec, fps))


def tuple_duration_sec(cfg: dict[str, Any]) -> float:
    vod = cfg.get("vod") or {}
    fps = float(vod.get("fps", 24))
    return duration_for_nframes(stage_nframes(cfg) * 3, fps)


def segment_times(cfg: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Start/end seconds for loop A, edge, loop B (equal stages)."""
    vod = cfg.get("vod") or {}
    fps = float(vod.get("fps", 24))
    stage = duration_for_nframes(stage_nframes(cfg), fps)
    return {
        "loop_a": {"start_sec": 0.0, "end_sec": stage},
        "edge": {"start_sec": stage, "end_sec": stage * 2.0},
        "loop_b": {"start_sec": stage * 2.0, "end_sec": stage * 3.0},
    }


def _first_flame(xml_text: str) -> ET.Element:
    root = _parse_root(xml_text)
    flames = _flames(root)
    if not flames:
        raise ValueError("genome has no <flame>")
    return flames[0]


def parent_eligible(xml_text: str) -> bool:
    """Single-flame, orbitable, non-linear-only parent."""
    try:
        root = _parse_root(xml_text)
    except ET.ParseError:
        return False
    if len(_flames(root)) != 1:
        return False
    if is_linear_only_genome(xml_text) or is_orbit_frozen(xml_text):
        return False
    return True


def combine_parent_genomes(
    xml_a: str,
    xml_b: str,
    *,
    from_stem: str,
    to_stem: str,
) -> str:
    """Two ``<flame>`` control points (time 0 then 1) for ``flam3-genome sequence=``."""
    fa = _first_flame(xml_a)
    fb = _first_flame(xml_b)
    fa.set("time", "0")
    fb.set("time", "1")
    fa.set("name", normalize_stem(from_stem))
    fb.set("name", normalize_stem(to_stem))
    return ET.tostring(fa, encoding="unicode") + ET.tostring(fb, encoding="unicode")


def _default_fonts() -> list[Path]:
    return [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
    ]


def resolve_watermark_font(cfg: dict[str, Any]) -> Path | None:
    wm = tuple_cfg(cfg)["watermark"]
    raw = str(wm.get("font") or "").strip()
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw))
    candidates.extend(_default_fonts())
    for p in candidates:
        if p.is_file():
            return p
    return None


def watermark_drawtext_filter(cfg: dict[str, Any]) -> str | None:
    """ffmpeg ``drawtext`` filter enabled only on the edge stage, or None if unavailable."""
    tc = tuple_cfg(cfg)
    wm = tc["watermark"]
    if not tc["watermark_on_edge"] or not wm["enabled"]:
        return None
    if str(wm.get("style") or "text").lower() == "image":
        return None
    font = resolve_watermark_font(cfg)
    if font is None:
        return None
    segs = segment_times(cfg)
    start = segs["edge"]["start_sec"]
    end = segs["edge"]["end_sec"]
    text = str(wm.get("text") or "Electric Sheep").replace(":", "\\:").replace("'", "\\'")
    opacity = max(0.05, min(1.0, float(wm.get("opacity", 0.45))))
    pos = str(wm.get("position") or "lower_right").lower()
    if pos in ("upper_left", "top_left"):
        xy = "x=48:y=36"
    elif pos in ("upper_right", "top_right"):
        xy = "x=w-tw-48:y=36"
    elif pos in ("lower_left", "bottom_left"):
        xy = "x=48:y=h-th-36"
    else:
        xy = "x=w-tw-48:y=h-th-36"
    font_esc = str(font).replace("\\", "/").replace(":", "\\:")
    return (
        f"drawtext=fontfile='{font_esc}':text='{text}':fontsize=28:"
        f"fontcolor=white@{opacity:.2f}:{xy}:"
        f"enable='between(t,{start:.3f},{end:.3f})'"
    )


def watermark_overlay_filter(cfg: dict[str, Any]) -> tuple[str, Path] | None:
    """Optional PNG overlay on the edge stage: ``(filter, image_path)``."""
    tc = tuple_cfg(cfg)
    wm = tc["watermark"]
    if not tc["watermark_on_edge"] or not wm["enabled"]:
        return None
    if str(wm.get("style") or "").lower() != "image":
        return None
    raw = str(wm.get("image") or "").strip()
    if not raw:
        return None
    img = Path(raw)
    if not img.is_file():
        return None
    segs = segment_times(cfg)
    start = segs["edge"]["start_sec"]
    end = segs["edge"]["end_sec"]
    opacity = max(0.05, min(1.0, float(wm.get("opacity", 0.45))))
    filt = (
        f"[1:v]format=rgba,colorchannelmixer=aa={opacity:.2f}[wm];"
        f"[0:v][wm]overlay=W-w-48:H-h-36:enable='between(t,{start:.3f},{end:.3f})'"
    )
    return filt, img


def stage_tuple_inbox(
    cfg: dict[str, Any],
    parent_a: Path,
    parent_b: Path,
    *,
    dry_run: bool = False,
) -> Path:
    """Write combined two-flame genome into ``genomes_inbox``. Refuse if catalog exists."""
    from_stem = normalize_stem(stem_of(parent_a))
    to_stem = normalize_stem(stem_of(parent_b))
    if from_stem == to_stem:
        raise ValueError("tuple parents must differ")
    if is_tuple_stem(from_stem) or is_tuple_stem(to_stem):
        raise ValueError("tuple parents cannot themselves be tuples")
    xml_a = parent_a.read_text(encoding="utf-8", errors="replace")
    xml_b = parent_b.read_text(encoding="utf-8", errors="replace")
    if not parent_eligible(xml_a) or not parent_eligible(xml_b):
        raise ValueError("tuple parents must be single-flame orbitable genomes")
    dest_mp4 = catalog_tuple_mp4(cfg, from_stem, to_stem)
    if dest_mp4.is_file():
        raise FileExistsError(f"tuple already in catalog: {dest_mp4}")
    name = tuple_flam3_name(from_stem, to_stem)
    inbox = resolve_path(cfg, "genomes_inbox")
    dest = inbox / name
    if dry_run:
        return dest
    body = combine_parent_genomes(xml_a, xml_b, from_stem=from_stem, to_stem=to_stem)
    inbox.mkdir(parents=True, exist_ok=True)
    dest.write_text(body, encoding="utf-8")
    log.info("staged tuple genome %s", dest)
    return dest


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="Stage a tuple genome (loop A + edge + loop B)")
    ap.add_argument("--config", default=os.environ.get("JELLYFLAM3_CONFIG", "configs/jellyflam3.yaml"))
    ap.add_argument("--from", dest="src_from", required=True, help="Parent A .flam3")
    ap.add_argument("--to", dest="src_to", required=True, help="Parent B .flam3")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    dest = stage_tuple_inbox(
        cfg, Path(args.src_from), Path(args.src_to), dry_run=args.dry_run
    )
    print(dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
