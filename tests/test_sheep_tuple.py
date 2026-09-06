"""Phase 4 tuples: naming, parents, duration, watermark filter, inbox stage."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.sheep_tuple import (
    catalog_tuple_mp4,
    combine_parent_genomes,
    is_tuple_stem,
    parent_eligible,
    parse_tuple_ids,
    segment_times,
    stage_nframes,
    stage_tuple_inbox,
    tuple_cfg,
    tuple_duration_sec,
    tuple_stem,
    watermark_drawtext_filter,
    watermark_overlay_filter,
)

ORBITABLE = """<flame name="t" size="1920 1080" rotate="90">
  <xform weight="1" animate="1" spherical="1" coefs="1 0 0 1 0 0" />
</flame>"""

FROZEN = """<flame name="t" size="1920 1080">
  <xform weight="1" symmetry="1" linear="1" coefs="1 0 0 1 0 0" />
</flame>"""


def _cfg(tmp_path: Path, **vod) -> dict:
    inbox = tmp_path / "inbox"
    media = tmp_path / "media"
    inbox.mkdir()
    media.mkdir()
    vod_cfg = {
        "fps": 24,
        "min_duration_sec": 11,
        "max_duration_sec": 31,
        "max_duration_sec_hard": 60,
        "allow_bypass_max": True,
    }
    vod_cfg.update(vod)
    return {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": str(inbox),
            "media_library": str(media),
        },
        "vod": vod_cfg,
        "tuple": {"enabled": True, "stage_duration_sec": 13, "watermark_on_edge": True},
        "watermark": {
            "enabled": True,
            "style": "text",
            "text": "Electric Sheep",
            "opacity": 0.45,
            "position": "lower_right",
        },
    }


def test_stem_parse_roundtrip_order_sensitive():
    a = "electricsheep.247.00505"
    b = "electricsheep.245.09797"
    stem_ab = tuple_stem(a, b)
    stem_ba = tuple_stem(b, a)
    assert stem_ab == "electricsheep.tuple.247.00505_to_245.09797"
    assert stem_ab != stem_ba
    assert parse_tuple_ids(stem_ab) == (a, b)
    assert parse_tuple_ids(stem_ba) == (b, a)
    assert is_tuple_stem(stem_ab)
    assert not is_tuple_stem(a)


def test_catalog_path_under_tuple_folder(tmp_path: Path):
    cfg = _cfg(tmp_path)
    dest = catalog_tuple_mp4(cfg, "electricsheep.247.00505", "electricsheep.245.09797")
    assert dest.as_posix().endswith(
        "/by-generation/tuple/electricsheep.tuple.247.00505_to_245.09797.mp4"
    ) or dest.as_posix().replace("\\", "/").endswith(
        "by-generation/tuple/electricsheep.tuple.247.00505_to_245.09797.mp4"
    )


def test_parent_eligible_rejects_frozen_and_multi_flame():
    assert parent_eligible(ORBITABLE)
    assert not parent_eligible(FROZEN)
    two = ORBITABLE + ORBITABLE.replace('name="t"', 'name="u"')
    assert not parent_eligible(two)


def test_combine_parent_genomes_two_control_points():
    body = combine_parent_genomes(
        ORBITABLE, ORBITABLE, from_stem="electricsheep.a", to_stem="electricsheep.b"
    )
    assert body.count("<flame") == 2
    assert 'time="0"' in body
    assert 'time="1"' in body


def test_stage_nframes_clamped_to_hard_max(tmp_path: Path):
    cfg = _cfg(tmp_path, max_duration_sec_hard=60, allow_bypass_max=True)
    stage = stage_nframes(cfg)
    total = tuple_duration_sec(cfg)
    assert stage * 3 / 24 <= 60.0
    assert total <= 60.0
    segs = segment_times(cfg)
    assert segs["edge"]["start_sec"] < segs["edge"]["end_sec"]
    assert segs["loop_b"]["end_sec"] == pytest.approx(total)


def test_watermark_filter_enabled_on_edge_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = _cfg(tmp_path)
    font = tmp_path / "DejaVuSans.ttf"
    font.write_bytes(b"fake")
    monkeypatch.setattr(
        "pipeline.sheep_tuple.resolve_watermark_font", lambda _cfg: font
    )
    filt = watermark_drawtext_filter(cfg)
    assert filt is not None
    assert "drawtext=" in filt
    assert "Electric Sheep" in filt
    assert "enable='between(t," in filt
    segs = segment_times(cfg)
    assert f"{segs['edge']['start_sec']:.3f}" in filt


def test_watermark_default_is_repo_png():
    repo = Path(__file__).resolve().parents[1]
    cfg = {
        "_repo_root": str(repo),
        "vod": {"fps": 24, "max_duration_sec_hard": 60, "allow_bypass_max": True},
        "tuple": {"stage_duration_sec": 13, "watermark_on_edge": True},
        "watermark": {},
    }
    wm = tuple_cfg(cfg)["watermark"]
    assert wm["style"] == "image"
    assert wm["image"].endswith("Electric-Sheep-Icon-7A8B99.png")
    overlay = watermark_overlay_filter(cfg)
    assert overlay is not None
    filt, img = overlay
    assert img.name == "Electric-Sheep-Icon-7A8B99.png"
    assert img.is_file()
    assert "overlay=" in filt
    assert "enable='between(t," in filt
    assert watermark_drawtext_filter(cfg) is None


def test_watermark_image_missing_falls_back_to_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cfg = _cfg(tmp_path)
    cfg["watermark"] = {
        "enabled": True,
        "style": "image",
        "text": "Electric Sheep",
        "image": "docs/media/watermark/no-such.png",
        "opacity": 0.45,
        "position": "lower_right",
    }
    assert watermark_overlay_filter(cfg) is None
    font = tmp_path / "DejaVuSans.ttf"
    font.write_bytes(b"fake")
    monkeypatch.setattr(
        "pipeline.sheep_tuple.resolve_watermark_font", lambda _cfg: font
    )
    filt = watermark_drawtext_filter(cfg)
    assert filt is not None
    assert "Electric Sheep" in filt


def test_stage_tuple_inbox_and_refuse_duplicate(tmp_path: Path):
    cfg = _cfg(tmp_path)
    a = tmp_path / "a.flam3"
    b = tmp_path / "b.flam3"
    a.write_text(ORBITABLE, encoding="utf-8")
    b.write_text(ORBITABLE.replace('name="t"', 'name="u"'), encoding="utf-8")
    dest = stage_tuple_inbox(cfg, a, b)
    assert dest.is_file()
    assert dest.name == "electricsheep.tuple.a_to_b.flam3"
    catalog = catalog_tuple_mp4(cfg, "a", "b")
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(b"x")
    with pytest.raises(FileExistsError):
        stage_tuple_inbox(cfg, a, b)


def test_iter_catalog_includes_tuple_skips_edges(tmp_path: Path):
    from pipeline.stills import iter_catalog_mp4s

    media = tmp_path / "media"
    (media / "by-generation" / "tuple").mkdir(parents=True)
    (media / "by-generation" / "247" / "edges").mkdir(parents=True)
    tup = media / "by-generation" / "tuple" / "electricsheep.tuple.a_to_b.mp4"
    edge = media / "by-generation" / "247" / "edges" / "edge.mp4"
    tup.write_bytes(b"t")
    edge.write_bytes(b"e")
    names = {p.name for p in iter_catalog_mp4s(media)}
    assert "electricsheep.tuple.a_to_b.mp4" in names
    assert "edge.mp4" not in names
