"""Desaturation / washed-out heuristics for Pathway A."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from pipeline.refactor_scan import (
    _palette_washed_out,
    catalog_saturation,
    image_mean_saturation,
    score_sheep,
)


def test_image_mean_saturation_grey_vs_vivid(tmp_path: Path):
    grey = tmp_path / "grey.jpg"
    vivid = tmp_path / "vivid.jpg"
    Image.new("RGB", (64, 64), (48, 48, 52)).save(grey, quality=90)
    Image.new("RGB", (64, 64), (255, 40, 40)).save(vivid, quality=90)
    g = image_mean_saturation(grey)
    v = image_mean_saturation(vivid)
    assert g is not None and v is not None
    assert g < 0.05
    assert v > 0.5


def test_catalog_desaturated_flags_candidate(tmp_path: Path):
    media = tmp_path / "sheep" / "by-generation" / "243"
    media.mkdir(parents=True)
    mp4 = media / "electricsheep.243.grey.mp4"
    mp4.write_bytes(b"\x00\x00")  # not probed when duration in sidecar
    poster = media / "electricsheep.243.grey-poster.jpg"
    Image.new("RGB", (128, 72), (44, 42, 60)).save(poster, quality=85)
    sidecar = media / "electricsheep.243.grey.jellyflam3.json"
    sidecar.write_text(
        '{"duration_sec": 31.0, "edition": "gold_sheep_lite"}',
        encoding="utf-8",
    )
    genomes = tmp_path / "genomes" / "done"
    genomes.mkdir(parents=True)
    flam = genomes / "electricsheep.243.grey.flam3"
    # Minimal flame with Gold Lite knobs + dull colors
    flam.write_text(
        '<flame size="1920 1080" brightness="4" gamma="4" vibrancy="1" '
        'quality="900" supersample="2" temporal_samples="450">'
        '<xform weight="1" color="0.6" coefs="1 0 0 1 0 0"/>'
        "</flame>",
        encoding="utf-8",
    )
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "media_library": str(tmp_path / "sheep"),
            "genomes_done": str(genomes),
            "genomes_inbox": str(tmp_path / "genomes" / "inbox"),
            "genomes_quarantine": str(tmp_path / "genomes" / "quarantine"),
        },
        "vod": {"min_sec": 8, "soft_max_sec": 43, "hard_max_sec": 113},
        "palette": {"mode": "complementary", "seed": "genome_accent"},
        "sheep_tax": {"enabled": True, "repair": False},
        "refactor": {"desat_mean_max": 0.12, "desat_score": 20},
    }
    row = score_sheep(cfg, mp4, genome_path=flam)
    assert "catalog_desaturated" in row.reasons
    assert row.verdict == "candidate"
    assert row.score >= 20.0
    assert row.palette.get("catalog_mean_sat") is not None
    assert row.palette["catalog_mean_sat"] < 0.12


def test_palette_washed_out_both_poles():
    assert _palette_washed_out(
        {"seed_hex": "#79363c", "complement_hex": "#003436"}
    )
    assert not _palette_washed_out(
        {"seed_hex": "#ff7f4a", "complement_hex": "#0085b7"}
    )


def test_catalog_saturation_reads_poster(tmp_path: Path):
    p = tmp_path / "p.jpg"
    Image.new("RGB", (32, 32), (10, 10, 10)).save(p)
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    info = catalog_saturation(mp4, poster=p)
    assert info["source"] == "poster"
    assert info["mean_sat"] is not None
