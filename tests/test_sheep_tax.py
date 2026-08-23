"""Unit tests for pipeline.sheep_tax (guide 06)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.sheep_tax import scan_file, tax_xml


def _cfg(**overrides):
    base = {
        "sheep_tax": {
            "enabled": True,
            "repair": True,
            "multi_flame": "strip_to_first",
            "strip_unknown_elements": False,
        }
    }
    base["sheep_tax"].update(overrides)
    return base


def test_ok_sample_genome():
    root = Path(__file__).resolve().parents[1]
    sample = root / "genomes" / "samples" / "electricsheep.247.00505.flam3"
    result = tax_xml(sample.read_text(encoding="utf-8"), _cfg())
    assert result["ok"] is True
    assert result["status"] in ("ok", "repaired")
    assert result["flame_count"] == 1


def test_broken_xml_quarantine():
    result = tax_xml("not xml at all <<<", _cfg())
    assert result["ok"] is False
    assert result["status"] == "quarantined"
    assert any(i["code"] == "xml_invalid" for i in result["issues"])


def test_missing_flame_quarantine():
    result = tax_xml("<root/>", _cfg())
    assert result["ok"] is False


def test_multi_flame_strip():
    xml = (
        '<flame name="a" size="800 600" scale="600">'
        '<xform weight="1" coefs="1 0 0 1 0 0"/>'
        "</flame>"
        '<flame name="b" size="800 600" scale="600">'
        '<xform weight="1" coefs="1 0 0 1 0 0"/>'
        "</flame>"
    )
    result = tax_xml(xml, _cfg(multi_flame="strip_to_first"))
    assert result["ok"] is True
    assert result["status"] == "repaired"
    assert result["flame_count"] == 1
    assert "name=\"a\"" in result["xml"] or "name='a'" in result["xml"] or 'name="a"' in (
        result["xml"] or ""
    )
    assert result["xml"].count("<flame") == 1


def test_multi_flame_reject():
    xml = (
        '<flame name="a" size="800 600" scale="600">'
        '<xform weight="1" coefs="1 0 0 1 0 0"/>'
        "</flame>"
        '<flame name="b" size="800 600" scale="600">'
        '<xform weight="1" coefs="1 0 0 1 0 0"/>'
        "</flame>"
    )
    result = tax_xml(xml, _cfg(multi_flame="reject"))
    assert result["ok"] is False
    assert result["status"] == "quarantined"


def test_missing_size_and_scale_repaired():
    xml = '<flame name="x"><xform weight="1" coefs="1 0 0 1 0 0"/></flame>'
    result = tax_xml(xml, _cfg())
    assert result["ok"] is True
    assert result["status"] == "repaired"
    assert 'size="800 592"' in (result["xml"] or "")
    assert "scale=" in (result["xml"] or "")


def test_color_index_clamp():
    xml = (
        '<flame size="100 100" scale="100">'
        '<xform weight="1" coefs="1 0 0 1 0 0"/>'
        '<color index="300" rgb="10 20 30"/>'
        "</flame>"
    )
    result = tax_xml(xml, _cfg())
    assert result["ok"] is True
    assert 'index="255"' in (result["xml"] or "")


def test_scan_file_writes_repair(tmp_path: Path):
    p = tmp_path / "g.flam3"
    p.write_text(
        '<flame name="x"><xform weight="1" coefs="1 0 0 1 0 0"/></flame>',
        encoding="utf-8",
    )
    result = scan_file(p, _cfg())
    assert result["ok"] is True
    text = p.read_text(encoding="utf-8")
    assert "size=" in text


def test_real_multi_flame_sample():
    root = Path(__file__).resolve().parents[1]
    sample = root / "genomes" / "samples" / "electricsheep.242.00172.flam3"
    if not sample.is_file():
        pytest.skip(f"missing sample {sample}")
    result = tax_xml(sample.read_text(encoding="utf-8"), _cfg())
    assert result["ok"] is True
    assert result["flame_count"] == 1
