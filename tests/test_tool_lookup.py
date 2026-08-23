"""Unit tests for pipeline.tool_lookup.tool."""

from __future__ import annotations

from pipeline.tool_lookup import tool


def test_configured_tools_name_wins():
    cfg = {"tools": {"flam3_animate": "/opt/custom/flam3-animate"}}
    assert tool(cfg, "flam3_animate") == "/opt/custom/flam3-animate"


def test_missing_key_underscore_to_hyphen():
    assert tool({"tools": {}}, "flam3_animate") == "flam3-animate"
    assert tool({}, "flam3_animate") == "flam3-animate"


def test_falsy_tools_value_falls_back_to_hyphenated():
    for raw in ("", None, 0, False):
        cfg = {"tools": {"flam3_animate": raw}}
        assert tool(cfg, "flam3_animate") == "flam3-animate", repr(raw)


def test_tools_section_missing_entirely():
    assert tool({}, "flam3_genome") == "flam3-genome"
    assert tool({"paths": {}}, "flam3_genome") == "flam3-genome"


def test_non_string_raw_coerced_via_str():
    cfg = {"tools": {"flam3_animate": Pathish("/usr/local/bin/flam3-animate")}}
    assert tool(cfg, "flam3_animate") == "/usr/local/bin/flam3-animate"
    cfg2 = {"tools": {"flam3_animate": 42}}
    assert tool(cfg2, "flam3_animate") == "42"


class Pathish:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value
