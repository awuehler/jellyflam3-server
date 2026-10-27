import pytest

from pipeline.archive_seed import default_fetch_count, tv_port_xml
from pipeline.quality_gate import QualityGateRejected
from pipeline.palette_harmony import (
    apply_palette_harmony,
    dual_pole_gradient,
    harmony_poles,
    oklch_to_srgb,
    srgb_to_oklch,
)
from pipeline.tv_optimize import apply_gold_lite_quality, tv_optimize_xml


def test_oklch_roundtrip_approx():
    L, C, h = srgb_to_oklch(40, 180, 220)
    r, g, b = oklch_to_srgb(L, C, h)
    assert abs(r - 40) < 8 and abs(g - 180) < 8 and abs(b - 220) < 8


def test_harmony_poles_complementary_distinct():
    a, b = harmony_poles((40, 180, 220), mode="complementary")
    assert a != b


def test_dual_pole_gradient_len():
    a, b = harmony_poles((200, 80, 40), mode="complementary")
    grad = dual_pole_gradient(a, b, 256)
    assert len(grad) == 256


def test_apply_palette_rewrites_colors():
    xml = """<flame size="800 592" scale="100">
  <color index="0" rgb="10 20 30" />
  <color index="1" rgb="200 10 10" />
</flame>"""
    result = apply_palette_harmony(xml, {"palette": {"mode": "complementary"}})
    assert result is not None
    assert result.seed_hex.startswith("#")
    assert 'size="800 592"' in result.xml or "800 592" in result.xml
    assert result.xml.count("<color") == 256


def test_palette_index_is_resolved_before_sampling():
    table = {71: [(220, 20, 20)] * 256}
    xml = '<flame palette="71" hue="0" size="640 480"><xform weight="1" linear="1" coefs="1 0 0 1 0 0"/></flame>'
    result = apply_palette_harmony(
        xml, {"palette": {"mode": "complementary"}}, palette_table=table
    )
    assert result is not None
    assert result.source == "index"
    assert result.seed_hex != "#b5b5c9"
    assert result.xml.count("<color") == 256


def test_unresolved_palette_index_is_left_for_the_renderer():
    xml = '<flame palette="71" size="640 480"><xform weight="1" linear="1" coefs="1 0 0 1 0 0"/></flame>'
    result = apply_palette_harmony(
        xml, {"palette": {"mode": "complementary"}}, palette_table={}
    )
    assert result is not None
    assert result.source == "deferred"
    assert 'palette="71"' in result.xml
    assert "<color" not in result.xml


def test_missing_palette_is_unresolved():
    xml = '<flame size="640 480"><xform weight="1" linear="1" coefs="1 0 0 1 0 0"/></flame>'
    result = apply_palette_harmony(
        xml, {"palette": {"mode": "complementary"}}, palette_table={}
    )
    assert result is not None
    assert result.source == "unresolved"
    assert "<color" not in result.xml


def test_tv_port_refuses_a_genome_with_no_palette():
    xml = '<flame size="640 480"><xform weight="1" linear="1" coefs="1 0 0 1 0 0"/></flame>'
    with pytest.raises(QualityGateRejected, match="palette_unresolved"):
        tv_port_xml(xml, {"palette": {"mode": "complementary"}, "render": {"edition": "off"}})


def test_palette_off():
    xml = '<flame size="800 592"><color index="0" rgb="10 20 30" /></flame>'
    assert apply_palette_harmony(xml, {"palette": {"mode": "off"}}) is None


def test_gold_lite_quality_attrs():
    xml = '<flame size="800 592" quality="50" temporal_samples="10" supersample="1"></flame>'
    out = apply_gold_lite_quality(xml, {"render": {"edition": "gold_sheep_lite"}})
    assert 'quality="900"' in out
    assert 'temporal_samples="450"' in out
    assert 'supersample="2"' in out


def test_tv_optimize_aspect_and_quality():
    xml = '<flame size="800 592" scale="100" quality="50"><color index="0" rgb="20 180 200" /></flame>'
    out, harmony = tv_optimize_xml(
        xml,
        {
            "render": {"target_width": 1920, "target_height": 1080, "edition": "gold_sheep_lite"},
            "palette": {"mode": "complementary"},
        },
    )
    assert 'size="1920 1080"' in out
    assert 'quality="900"' in out
    assert harmony is not None
    assert out.count("<color") == 256


def test_default_fetch_count_range():
    cfg = {"seed_archive": {"fetch_count_min": 3, "fetch_count_max": 7}}
    for _ in range(20):
        n = default_fetch_count(cfg)
        assert 3 <= n <= 7
    assert default_fetch_count({"seed_archive": {"fetch_count": 4}}) == 4
