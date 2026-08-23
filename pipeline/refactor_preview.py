"""Sheep refactor Pathway P — Jellyfin-visible palette / still preview."""

from __future__ import annotations

import copy
import logging
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from pipeline.config import resolve_path
from pipeline.media_layout import ensure_refactor_preview_dir
from pipeline.palette_harmony import apply_palette_harmony
from pipeline.poster import extract_mid_loop_poster
from pipeline.refactor_scan import find_genome_for_stem
from pipeline.sheep_names import normalize_stem, stem_of
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.refactor")


def preview_root(cfg: dict[str, Any]) -> Path:
    """Jellyfin-visible preview root (``_refactor-preview`` under the sheep mount)."""
    paths = cfg.get("paths") or {}
    if paths.get("refactor_preview_root"):
        return resolve_path(cfg, "refactor_preview_root")
    media = resolve_path(cfg, "media_library")
    return ensure_refactor_preview_dir(media)


def preview_dir_for(cfg: dict[str, Any], sheep_id: str) -> Path:
    stem = normalize_stem(stem_of(sheep_id))
    return preview_root(cfg) / stem


def cfg_with_palette_overrides(
    cfg: dict[str, Any],
    *,
    palette_mode: str | None = None,
    palette_seed: str | None = None,
) -> dict[str, Any]:
    """Copy cfg with optional per-sheep palette mode/seed overrides."""
    out = copy.deepcopy(cfg)
    pal = dict(out.get("palette") or {})
    if palette_mode is not None:
        mode = str(palette_mode).strip().lower()
        aliases = {
            "complementary": "complementary",
            "complement": "complementary",
            "split_complementary": "split_complementary",
            "split": "split_complementary",
            "off": "off",
            "none": "off",
        }
        pal["mode"] = aliases.get(mode, mode)
    if palette_seed is not None:
        seed = str(palette_seed).strip()
        if seed and not seed.startswith("#"):
            seed = f"#{seed}"
        pal["seed"] = "curator_hex"
        pal["curator_hex"] = seed
    out["palette"] = pal
    return out


def _hex_to_ffmpeg_color(hex_color: str | None, fallback: str = "0x334455") -> str:
    if not hex_color:
        return fallback
    hx = hex_color.lstrip("#")
    if len(hx) != 6:
        return fallback
    return f"0x{hx}"


def encode_palette_preview_mp4(
    *,
    ffmpeg: str,
    dest: Path,
    seed_hex: str | None,
    complement_hex: str | None,
    duration_sec: float = 2.0,
) -> Path:
    """Short H.264 palette-pole proxy (seed vs complement panels).

    Sibling to the flam3 sheep still — useful for confirming harmony poles, not art.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    c1 = _hex_to_ffmpeg_color(seed_hex, "0x4488cc")
    c2 = _hex_to_ffmpeg_color(complement_hex, "0xcc6644")
    filt = (
        f"color=c={c1}:s=640x360:d={duration_sec}[a];"
        f"color=c={c2}:s=640x360:d={duration_sec}[b];"
        f"[a][b]hstack=inputs=2"
    )
    cmd = [
        ffmpeg,
        "-y",
        "-f",
        "lavfi",
        "-i",
        filt,
        "-t",
        str(duration_sec),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-an",
        str(dest),
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def render_flam3_still(
    *,
    flam3_render: str,
    genome: Path,
    dest_png: Path,
    size_scale: float = 0.5,
    quality_scale: float = 0.35,
) -> Path:
    """Render one still from a (retinted) ``.flam3`` via ``flam3-render``."""
    genome = Path(genome)
    dest_png = Path(dest_png)
    if not genome.is_file():
        raise FileNotFoundError(genome)
    dest_png.parent.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "in": str(genome),
        "out": str(dest_png),
        "ss": str(size_scale),
        "qs": str(quality_scale),
    }
    subprocess.check_call(
        [flam3_render],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not dest_png.is_file():
        # Some builds write prefix0000.png beside out; accept common siblings.
        siblings = sorted(dest_png.parent.glob(f"{dest_png.stem}*"))
        pngs = [p for p in siblings if p.suffix.lower() in (".png", ".jpg", ".jpeg")]
        if not pngs:
            raise RuntimeError(f"flam3-render produced no image for {genome}")
        if pngs[0] != dest_png:
            shutil.copy2(pngs[0], dest_png)
    return dest_png


def encode_still_preview_mp4(
    *,
    ffmpeg: str,
    still: Path,
    dest: Path,
    duration_sec: float = 2.0,
) -> Path:
    """Short H.264 clip from a still (Jellyfin-playable sheep preview)."""
    still = Path(still)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-i",
        str(still),
        "-t",
        str(duration_sec),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-an",
        str(dest),
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def write_jpeg_from_image(
    *,
    ffmpeg: str,
    src: Path,
    dest: Path,
) -> Path:
    """Convert a PNG/JPEG still to Jellyfin-friendly JPEG poster."""
    src = Path(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(dest),
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def write_preview_poster(
    *,
    ffmpeg: str,
    mp4: Path,
    dest: Path,
    ffprobe: str | None = None,
) -> Path:
    """Extract a poster JPEG beside the preview MP4 (guide sibling naming)."""
    return extract_mid_loop_poster(
        ffmpeg=ffmpeg,
        mp4=mp4,
        dest=dest,
        duration_sec=1.0 if ffprobe is None else None,
        ffprobe=ffprobe,
    )


def soft_refresh_jellyfin(cfg: dict[str, Any]) -> dict[str, Any]:
    """Best-effort Jellyfin library refresh (preview library pickup)."""
    try:
        from pipeline.jellyfin_client import JellyfinClient

        client = JellyfinClient.from_config(cfg)
        client.refresh_library()
        return {"ok": True, "status": "refreshed"}
    except Exception as exc:  # noqa: BLE001
        log.warning("Jellyfin refresh skipped/failed: %s", exc)
        return {"ok": False, "status": "skipped", "error": str(exc)}


@dataclass
class PreviewResult:
    """Pathway P outcome (never mutates live catalog)."""

    id: str
    preview_dir: str
    preview_genome: str | None = None
    preview_mp4: str | None = None
    preview_poster: str | None = None
    preview_still: str | None = None
    palette_preview_mp4: str | None = None
    palette_after: dict[str, Any] = field(default_factory=dict)
    jellyfin: dict[str, Any] = field(default_factory=dict)
    discarded: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_preview(
    cfg: dict[str, Any],
    sheep_id: str,
    *,
    palette_mode: str | None = None,
    palette_seed: str | None = None,
    preview_poster: bool = True,
    refresh_jellyfin: bool = True,
    encode_fn: Callable[..., Path] | None = None,
    still_fn: Callable[..., Path] | None = None,
    still_mp4_fn: Callable[..., Path] | None = None,
    palette_encode_fn: Callable[..., Path] | None = None,
    poster_fn: Callable[..., Path] | None = None,
    refresh_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> PreviewResult:
    """Pathway P: retint staging genome + sheep still + palette-pole proxy (no catalog replace)."""
    stem = normalize_stem(stem_of(sheep_id))
    notes: list[str] = []
    work_cfg = cfg_with_palette_overrides(
        cfg, palette_mode=palette_mode, palette_seed=palette_seed
    )

    genome = find_genome_for_stem(cfg, stem)
    if genome is None:
        raise FileNotFoundError(f"no genome found for {stem}")

    xml = genome.read_text(encoding="utf-8", errors="replace")
    harmony = apply_palette_harmony(xml, work_cfg)
    if harmony is None:
        retinted = xml
        palette_after = {
            "mode": "off",
            "seed_hex": None,
            "complement_hex": None,
            "source": "disabled",
        }
        notes.append("palette_disabled")
    else:
        retinted = harmony.xml
        palette_after = {
            "mode": harmony.mode,
            "seed_hex": harmony.seed_hex,
            "complement_hex": harmony.complement_hex,
            "source": str((work_cfg.get("palette") or {}).get("seed") or "genome_accent"),
        }

    dest_dir = preview_dir_for(cfg, stem)
    ensure_refactor_preview_dir(resolve_path(cfg, "media_library"))
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        from pipeline.media_layout import CATALOG_DIR_MODE
        import stat as _stat

        if _stat.S_IMODE(dest_dir.stat().st_mode) != CATALOG_DIR_MODE:
            dest_dir.chmod(CATALOG_DIR_MODE)
    except OSError:
        pass

    genome_out = dest_dir / f"{stem}.flam3"
    genome_out.write_text(retinted, encoding="utf-8")

    mp4_out: Path | None = None
    poster_out: Path | None = None
    still_out: Path | None = None
    palette_mp4_out: Path | None = None
    if preview_poster:
        ffmpeg = _tool(cfg, "ffmpeg")
        flam3_render = _tool(cfg, "flam3_render")

        still_png = dest_dir / f"{stem}-preview-still.png"
        still_out = dest_dir / f"{stem}-preview-still.jpg"
        poster_out = dest_dir / f"{stem}-preview-poster.jpg"
        mp4_out = dest_dir / f"{stem}-preview.mp4"
        palette_mp4_out = dest_dir / f"{stem}-palette-preview.mp4"

        # 1) Real sheep still from retinted genome (flam3-render).
        render = still_fn or render_flam3_still
        render(
            flam3_render=flam3_render,
            genome=genome_out,
            dest_png=still_png,
        )
        jpeg = poster_fn or write_jpeg_from_image
        # Prefer explicit still JPEG + Jellyfin sibling poster from the same frame.
        jpeg(ffmpeg=ffmpeg, src=still_png, dest=still_out)
        jpeg(ffmpeg=ffmpeg, src=still_png, dest=poster_out)

        # 2) Jellyfin-playable preview clip from that still.
        still_enc = still_mp4_fn or encode_still_preview_mp4
        still_enc(ffmpeg=ffmpeg, still=still_out, dest=mp4_out)

        # 3) Palette-pole color proxy (both types).
        pal_enc = palette_encode_fn or encode_fn or encode_palette_preview_mp4
        pal_enc(
            ffmpeg=ffmpeg,
            dest=palette_mp4_out,
            seed_hex=palette_after.get("seed_hex"),
            complement_hex=palette_after.get("complement_hex"),
        )

        notes.append("preview_still_flam3_render")
        notes.append("preview_mp4_from_still")
        notes.append("palette_preview_mp4_proxy")
        notes.append("live_catalog_untouched")

    jelly: dict[str, Any] = {"ok": False, "status": "skipped"}
    if refresh_jellyfin:
        refresher = refresh_fn or soft_refresh_jellyfin
        jelly = refresher(cfg)

    return PreviewResult(
        id=stem,
        preview_dir=str(dest_dir),
        preview_genome=str(genome_out),
        preview_mp4=str(mp4_out) if mp4_out else None,
        preview_poster=str(poster_out) if poster_out else None,
        preview_still=str(still_out) if still_out else None,
        palette_preview_mp4=str(palette_mp4_out) if palette_mp4_out else None,
        palette_after=palette_after,
        jellyfin=jelly,
        discarded=False,
        notes=notes,
    )


def discard_preview(
    cfg: dict[str, Any],
    sheep_id: str,
    *,
    refresh_jellyfin: bool = True,
    refresh_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> PreviewResult:
    """Remove ``_refactor-preview/<id>/`` and optionally refresh Jellyfin."""
    stem = normalize_stem(stem_of(sheep_id))
    dest_dir = preview_dir_for(cfg, stem)
    existed = dest_dir.is_dir()
    if existed:
        shutil.rmtree(dest_dir)
    jelly: dict[str, Any] = {"ok": False, "status": "skipped"}
    if refresh_jellyfin:
        refresher = refresh_fn or soft_refresh_jellyfin
        jelly = refresher(cfg)
    return PreviewResult(
        id=stem,
        preview_dir=str(dest_dir),
        discarded=True,
        jellyfin=jelly,
        notes=["removed" if existed else "already_absent"],
    )
