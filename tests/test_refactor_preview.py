"""Pathway P tests for sheep refactor preview (still + palette proxy)."""

from __future__ import annotations

from pathlib import Path

from pipeline.refactor import (
    cfg_with_palette_overrides,
    discard_preview,
    run_preview,
)


def _cfg(tmp: Path) -> dict:
    media = tmp / "media"
    (media / "by-generation" / "247").mkdir(parents=True)
    done = tmp / "genomes" / "done"
    done.mkdir(parents=True)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "media_library": str(media),
            "genomes_done": str(done),
            "genomes_inbox": str(tmp / "genomes" / "inbox"),
            "genomes_quarantine": str(tmp / "genomes" / "quarantine"),
        },
        "palette": {"mode": "complementary", "seed": "genome_accent"},
        "tools": {
            "ffmpeg": "ffmpeg",
            "ffprobe": "ffprobe",
            "flam3_render": "flam3-render",
        },
    }


def _genome_xml() -> str:
    return """<flame name="t" size="1920 1080" quality="900" supersample="2" filter="1">
  <xform weight="1" coefs="1 0 0 1 0 0" color="0"/>
  <color index="0" rgb="180 60 40"/>
  <color index="1" rgb="40 80 200"/>
</flame>"""


def test_cfg_palette_overrides(tmp_path: Path):
    cfg = _cfg(tmp_path)
    out = cfg_with_palette_overrides(
        cfg, palette_mode="split_complementary", palette_seed="88aaff"
    )
    assert out["palette"]["mode"] == "split_complementary"
    assert out["palette"]["seed"] == "curator_hex"
    assert out["palette"]["curator_hex"] == "#88aaff"
    assert cfg["palette"]["seed"] == "genome_accent"


def test_run_preview_both_types_and_discard(tmp_path: Path):
    cfg = _cfg(tmp_path)
    stem = "electricsheep.247.00505"
    genome = Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3"
    genome.write_text(_genome_xml(), encoding="utf-8")

    def fake_still(*, flam3_render, genome, dest_png, size_scale=0.5, quality_scale=0.35):
        Path(dest_png).write_bytes(b"fake-png")
        return Path(dest_png)

    def fake_jpeg(*, ffmpeg, src, dest):
        Path(dest).write_bytes(b"fake-jpg")
        return Path(dest)

    def fake_still_mp4(*, ffmpeg, still, dest, duration_sec=2.0):
        Path(dest).write_bytes(b"fake-still-mp4")
        return Path(dest)

    def fake_palette(*, ffmpeg, dest, seed_hex, complement_hex, duration_sec=2.0):
        Path(dest).write_bytes(b"fake-palette-mp4")
        return Path(dest)

    def fake_refresh(_cfg):
        return {"ok": True, "status": "stub"}

    result = run_preview(
        cfg,
        stem,
        palette_mode="complementary",
        palette_seed="#112233",
        preview_poster=True,
        refresh_jellyfin=True,
        still_fn=fake_still,
        poster_fn=fake_jpeg,
        still_mp4_fn=fake_still_mp4,
        palette_encode_fn=fake_palette,
        refresh_fn=fake_refresh,
    )
    assert result.discarded is False
    assert result.palette_after.get("seed_hex")
    assert Path(result.preview_genome).is_file()
    assert Path(result.preview_mp4).is_file()
    assert Path(result.preview_poster).is_file()
    assert Path(result.preview_still).is_file()
    assert Path(result.palette_preview_mp4).is_file()
    assert Path(result.preview_mp4).read_bytes() == b"fake-still-mp4"
    assert Path(result.palette_preview_mp4).read_bytes() == b"fake-palette-mp4"
    assert "preview_still_flam3_render" in result.notes
    assert "palette_preview_mp4_proxy" in result.notes
    assert "live_catalog_untouched" in result.notes
    assert "_refactor-preview" in result.preview_dir.replace("\\", "/")
    assert result.jellyfin["status"] == "stub"

    media = Path(cfg["paths"]["media_library"])
    assert not list(media.joinpath("by-generation").rglob("*-preview.mp4"))

    discarded = discard_preview(cfg, stem, refresh_fn=fake_refresh)
    assert discarded.discarded is True
    assert not Path(result.preview_dir).exists()


def test_preview_requires_genome(tmp_path: Path):
    cfg = _cfg(tmp_path)
    try:
        run_preview(
            cfg,
            "electricsheep.247.99999",
            preview_poster=True,
            refresh_jellyfin=False,
            still_fn=lambda **k: Path(k["dest_png"]),
            poster_fn=lambda **k: Path(k["dest"]),
            still_mp4_fn=lambda **k: Path(k["dest"]),
            palette_encode_fn=lambda **k: Path(k["dest"]),
        )
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised
