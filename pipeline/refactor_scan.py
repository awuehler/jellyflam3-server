"""Sheep refactor Pathway A — scan, score, filter, and format catalog reports."""

from __future__ import annotations

import logging
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pipeline.choose_duration import effective_min_sec, hard_max_sec, soft_max_sec
from pipeline.config import resolve_path
from pipeline.genome_signals import (
    is_linear_only_genome,
    is_orbit_frozen,
    is_singularity_cloned,
)
from pipeline.palette_harmony import HarmonyResult, apply_palette_harmony
from pipeline.poster import poster_path_for_mp4
from pipeline.sheep_names import normalize_stem, stem_of
from pipeline.sheep_tax import tax_xml
from pipeline.stills import iter_catalog_mp4s, load_sidecar
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.refactor")

SCORE_CANDIDATE_MIN = 1.0
SCORE_QUARANTINE_MIN = 80.0
# Genetics that cannot be remade by TV-port / palette apply — exclude from flock.
HARD_QUARANTINE_REASONS = frozenset(
    {
        "missing_genome",
        "sheep_tax_fail",
        "genome_linear_only",
        "genome_singularity_cloned",
    }
)
LINEAR_ONLY_SCORE_DEFAULT = 80.0
SINGULARITY_CLONED_SCORE_DEFAULT = 80.0
ORBIT_FROZEN_SCORE_DEFAULT = 25.0


@dataclass
class SheepScore:
    """One catalog sheep quality assessment (Pathway A)."""

    id: str
    mp4: str
    verdict: str  # ok | candidate | quarantine
    score: float
    reasons: list[str] = field(default_factory=list)
    palette: dict[str, Any] = field(default_factory=dict)
    duration_sec: float | None = None
    genome: str | None = None
    poster: str | None = None
    tax_status: str | None = None
    aspect: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _repo_root(cfg: dict[str, Any]) -> Path:
    raw = cfg.get("_repo_root")
    if raw:
        return Path(str(raw))
    return Path(__file__).resolve().parents[1]


def find_genome_for_stem(cfg: dict[str, Any], stem: str) -> Path | None:
    """Locate .flam3 for a catalog stem (done → inbox → quarantine → samples → pedigree)."""
    base = normalize_stem(stem_of(stem))
    names = [f"{base}.flam3"]
    if base.startswith("electricsheep."):
        names.append(f"jellyflam3.{base[len('electricsheep.'):]}.flam3")

    dirs: list[Path] = []
    for key in ("genomes_done", "genomes_inbox", "genomes_quarantine"):
        try:
            dirs.append(resolve_path(cfg, key))
        except (KeyError, TypeError):
            continue
    try:
        from pipeline.worker import genomes_done_dir

        done = genomes_done_dir(cfg)
        if done not in dirs:
            dirs.insert(0, done)
    except Exception:  # noqa: BLE001
        pass

    root = _repo_root(cfg)
    dirs.extend([root / "genomes" / "samples", root / "genomes" / "pedigree"])

    for d in dirs:
        if not d.is_dir():
            continue
        for name in names:
            flat = d / name
            if flat.is_file():
                return flat
        for name in names:
            hits = sorted(p for p in d.rglob(name) if p.is_file())
            if hits:
                return hits[0]
    return None


def find_catalog_mp4(cfg: dict[str, Any], sheep_id: str) -> Path | None:
    want = normalize_stem(stem_of(sheep_id))
    media = resolve_path(cfg, "media_library")
    for p in iter_catalog_mp4s(media):
        if normalize_stem(p.stem) == want:
            return p
    return None


def _probe_duration_sec(cfg: dict[str, Any], mp4: Path) -> float | None:
    ffprobe = _tool(cfg, "ffprobe")
    try:
        out = subprocess.check_output(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(mp4),
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=30,
        ).strip()
        return float(out)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def _flame_size(xml_text: str) -> tuple[int, int] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        try:
            root = ET.fromstring(f"<flames>{xml_text}</flames>")
        except ET.ParseError:
            return None
    flames = [root] if root.tag == "flame" else list(root.iter("flame"))
    if not flames:
        return None
    size = flames[0].get("size") or ""
    parts = size.replace(",", " ").split()
    if len(parts) < 2:
        return None
    try:
        return int(float(parts[0])), int(float(parts[1]))
    except ValueError:
        return None


def _has_gold_lite_knobs(xml_text: str) -> bool:
    """True when flame looks TV-ported (quality / supersample / filter present)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        try:
            root = ET.fromstring(f"<flames>{xml_text}</flames>")
        except ET.ParseError:
            return False
    flames = [root] if root.tag == "flame" else list(root.iter("flame"))
    if not flames:
        return False
    f = flames[0]
    return bool(f.get("quality") and (f.get("supersample") or f.get("filter")))


def _palette_block(xml_text: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Current complementary (or configured) palette — required on every report row."""
    try:
        result = apply_palette_harmony(xml_text, cfg)
    except Exception as exc:  # noqa: BLE001 — bad XML after tax fail must not crash report
        pal = cfg.get("palette") or {}
        return {
            "mode": str(pal.get("mode") or "complementary"),
            "seed_hex": None,
            "complement_hex": None,
            "source": f"error:{type(exc).__name__}",
        }
    if result is None:
        pal = cfg.get("palette") or {}
        return {
            "mode": str(pal.get("mode") or "off"),
            "seed_hex": None,
            "complement_hex": None,
            "source": "disabled",
        }
    assert isinstance(result, HarmonyResult)
    seed_src = str((cfg.get("palette") or {}).get("seed") or "genome_accent")
    return {
        "mode": result.mode,
        "seed_hex": result.seed_hex,
        "complement_hex": result.complement_hex,
        "source": seed_src,
    }


def _neon_clash(palette: dict[str, Any]) -> bool:
    """Rough chroma gate from hex poles (high-saturation ambient clash)."""
    for key in ("seed_hex", "complement_hex"):
        h = palette.get(key)
        if not h or not isinstance(h, str):
            continue
        hx = h.lstrip("#")
        if len(hx) != 6:
            continue
        try:
            r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        except ValueError:
            continue
        mx, mn = max(r, g, b), min(r, g, b)
        if mx == 0:
            continue
        sat = (mx - mn) / mx
        if sat >= 0.92 and mx >= 230:
            return True
    return False


def _hex_chroma(hex_color: str | None) -> float | None:
    """Return absolute channel spread (max-min)/255 in [0,1] for #RRGGBB."""
    if not hex_color or not isinstance(hex_color, str):
        return None
    hx = hex_color.lstrip("#")
    if len(hx) != 6:
        return None
    try:
        r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    except ValueError:
        return None
    return (max(r, g, b) - min(r, g, b)) / 255.0


def _palette_washed_out(palette: dict[str, Any], *, max_chroma: float = 0.40) -> bool:
    """True when both harmony poles have low absolute chroma (dull/muddy pair)."""
    s = _hex_chroma(palette.get("seed_hex") if isinstance(palette.get("seed_hex"), str) else None)
    c = _hex_chroma(
        palette.get("complement_hex") if isinstance(palette.get("complement_hex"), str) else None
    )
    if s is None or c is None:
        return False
    return s < max_chroma and c < max_chroma


def image_mean_saturation(path: Path, *, sample_w: int = 64) -> float | None:
    """Mean per-pixel channel-spread saturation in [0, 1] over a downscaled RGB sample.

    Used to catch washed-out / grey catalog sheep that still pass structural checks.
    """
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
        if mx == 0:
            sat = 0.0
        else:
            sat = (mx - min(r, g, b)) / 255.0
        total += sat
        n += 1
    if n == 0:
        return None
    return total / n


def catalog_saturation(
    mp4: Path,
    *,
    poster: Path | None = None,
) -> dict[str, Any]:
    """Measure catalog visual saturation from poster (preferred) or mid-frame grab."""
    out: dict[str, Any] = {
        "mean_sat": None,
        "source": None,
        "path": None,
    }
    candidates: list[tuple[str, Path]] = []
    if poster is not None and poster.is_file():
        candidates.append(("poster", poster))
    elif poster_path_for_mp4(mp4).is_file():
        candidates.append(("poster", poster_path_for_mp4(mp4)))
    for source, path in candidates:
        mean = image_mean_saturation(path)
        if mean is not None:
            out["mean_sat"] = round(mean, 4)
            out["source"] = source
            out["path"] = str(path)
            return out
    return out


def _desat_thresholds(cfg: dict[str, Any]) -> tuple[float, float]:
    """Return (mean_sat_max, score_weight) for washed-out catalog detection."""
    ref = dict(cfg.get("refactor") or {})
    mean_max = float(ref.get("desat_mean_max", 0.12))
    weight = float(ref.get("desat_score", 20.0))
    return mean_max, weight


def genome_dud_reasons(xml_text: str) -> list[str]:
    """Pathway A reasons for linear-only / ES singularities clones (order stable)."""
    reasons: list[str] = []
    if is_linear_only_genome(xml_text):
        reasons.append("genome_linear_only")
    if is_singularity_cloned(xml_text):
        reasons.append("genome_singularity_cloned")
    return reasons


def genome_dud_score(cfg: dict[str, Any], reasons: list[str]) -> float:
    """Score weight for linear-only / singularity-cloned reasons already in ``reasons``."""
    ref = dict(cfg.get("refactor") or {})
    score = 0.0
    if "genome_linear_only" in reasons:
        score += float(ref.get("linear_only_score", LINEAR_ONLY_SCORE_DEFAULT))
    if "genome_singularity_cloned" in reasons:
        score += float(ref.get("singularity_cloned_score", SINGULARITY_CLONED_SCORE_DEFAULT))
    return score


def verdict_for(score: float, reasons: list[str]) -> str:
    """Map score + hard reasons to ok / candidate / quarantine."""
    if score >= SCORE_QUARANTINE_MIN or any(r in HARD_QUARANTINE_REASONS for r in reasons):
        return "quarantine"
    if score >= SCORE_CANDIDATE_MIN:
        return "candidate"
    return "ok"


def score_sheep(
    cfg: dict[str, Any],
    mp4: Path,
    *,
    genome_path: Path | None = None,
    xml_text: str | None = None,
) -> SheepScore:
    """Score one catalog MP4 (Pathway A heuristics). Read-only."""
    stem = normalize_stem(mp4.stem)
    reasons: list[str] = []
    score = 0.0
    sidecar = load_sidecar(mp4)
    poster = poster_path_for_mp4(mp4)
    poster_s = str(poster) if poster.is_file() else None
    if not poster.is_file():
        reasons.append("missing_poster")
        score += 25.0

    dur: float | None = None
    if sidecar.get("duration_sec") is not None:
        try:
            dur = float(sidecar["duration_sec"])
        except (TypeError, ValueError):
            dur = None
    if dur is None:
        dur = _probe_duration_sec(cfg, mp4)
    if dur is None:
        reasons.append("duration_unknown")
        score += 10.0
    else:
        vod = cfg.get("vod") or {}
        soft = soft_max_sec(vod)
        hard = hard_max_sec(vod)
        lo = effective_min_sec(cfg)
        if dur < lo - 0.5:
            reasons.append("duration_below_min")
            score += 20.0
        elif dur > hard + 0.5:
            reasons.append("duration_above_hard")
            score += 35.0
        elif dur > soft + 0.5:
            reasons.append("duration_above_soft")
            score += 15.0

    genome = genome_path or find_genome_for_stem(cfg, stem)
    genome_s = str(genome) if genome else None
    tax_status: str | None = None
    aspect: str | None = None
    palette: dict[str, Any] = {
        "mode": str((cfg.get("palette") or {}).get("mode") or "complementary"),
        "seed_hex": None,
        "complement_hex": None,
        "source": "unavailable",
    }

    xml = xml_text
    if xml is None and genome is not None:
        try:
            xml = genome.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            reasons.append(f"genome_read_error:{exc}")
            score += 40.0
            xml = None

    if xml is None:
        if genome is None:
            reasons.append("missing_genome")
            score += 50.0
    else:
        tax_cfg = dict(cfg)
        st = dict(tax_cfg.get("sheep_tax") or {})
        st["repair"] = False
        tax_cfg["sheep_tax"] = st
        tax = tax_xml(xml, tax_cfg)
        tax_status = str(tax.get("status") or ("ok" if tax.get("ok") else "fail"))
        if not tax.get("ok"):
            reasons.append("sheep_tax_fail")
            score += 50.0
            for issue in tax.get("issues") or []:
                code = issue.get("code") if isinstance(issue, dict) else None
                if code:
                    reasons.append(f"tax:{code}")

        size = _flame_size(xml)
        if size:
            w, h = size
            aspect = f"{w}x{h}"
            if h <= 0 or abs((w / h) - (16 / 9)) > 0.08:
                reasons.append("aspect_not_16_9")
                score += 20.0
        else:
            reasons.append("aspect_unknown")
            score += 5.0

        if not _has_gold_lite_knobs(xml):
            reasons.append("missing_tv_quality_knobs")
            score += 10.0

        palette = _palette_block(xml, cfg)
        if _neon_clash(palette):
            reasons.append("palette_neon_clash")
            score += 15.0
        if _palette_washed_out(palette):
            reasons.append("palette_washed_out")
            score += 10.0

        for dud in genome_dud_reasons(xml):
            reasons.append(dud)
        score += genome_dud_score(cfg, reasons)

        if is_orbit_frozen(xml):
            reasons.append("genome_orbit_frozen")
            ref = dict(cfg.get("refactor") or {})
            score += float(ref.get("orbit_frozen_score", ORBIT_FROZEN_SCORE_DEFAULT))

    # Catalog visual desaturation (poster) — catches grey/muddy sheep structural checks miss.
    sat_info = catalog_saturation(mp4, poster=poster if poster.is_file() else None)
    mean_sat = sat_info.get("mean_sat")
    if isinstance(mean_sat, (int, float)):
        desat_max, desat_weight = _desat_thresholds(cfg)
        if mean_sat < desat_max:
            reasons.append("catalog_desaturated")
            score += desat_weight

    seen: set[str] = set()
    uniq: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)

    verdict = verdict_for(score, uniq)

    row = SheepScore(
        id=stem,
        mp4=str(mp4),
        verdict=verdict,
        score=round(score, 1),
        reasons=uniq,
        palette=palette,
        duration_sec=dur,
        genome=genome_s,
        poster=poster_s,
        tax_status=tax_status,
        aspect=aspect,
    )
    if isinstance(mean_sat, (int, float)):
        # Attach for JSON reports without changing dataclass schema widely.
        row.palette = dict(palette)
        row.palette["catalog_mean_sat"] = mean_sat
        row.palette["catalog_sat_source"] = sat_info.get("source")
    return row


def scan_catalog(
    cfg: dict[str, Any],
    *,
    sheep_id: str | None = None,
    limit: int | None = None,
) -> list[SheepScore]:
    """Enumerate and score catalog MP4s (Pathway A)."""
    media = resolve_path(cfg, "media_library")
    mp4s = iter_catalog_mp4s(media)
    if sheep_id:
        want = normalize_stem(stem_of(sheep_id))
        mp4s = [p for p in mp4s if normalize_stem(p.stem) == want]
        if not mp4s:
            log.warning("no catalog MP4 for id %s under %s", want, media)
    if limit is not None:
        mp4s = mp4s[: max(0, int(limit))]
    return [score_sheep(cfg, p) for p in mp4s]


def filter_report(
    rows: list[SheepScore],
    *,
    failing_only: bool = False,
    verdict: str | None = None,
) -> list[SheepScore]:
    if verdict:
        return [r for r in rows if r.verdict == verdict]
    if failing_only:
        return [r for r in rows if r.verdict != "ok"]
    return rows


def format_table(rows: list[SheepScore]) -> str:
    if not rows:
        return "(no sheep)"
    lines = [
        f"{'verdict':<12} {'score':>5}  {'id':<42}  palette  reasons",
        "-" * 100,
    ]
    for r in rows:
        pal = r.palette or {}
        pal_s = f"{pal.get('seed_hex') or '-'}->{pal.get('complement_hex') or '-'}"
        reasons = ",".join(r.reasons) if r.reasons else "-"
        lines.append(
            f"{r.verdict:<12} {r.score:>5.1f}  {r.id:<42}  {pal_s}  {reasons}"
        )
    return "\n".join(lines)
