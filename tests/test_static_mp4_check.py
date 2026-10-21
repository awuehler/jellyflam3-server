"""Negative check: legacy HLS auth fails and Static MP4 is still a playable file."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "static_mp4_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("static_mp4_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["static_mp4_check"] = module
    spec.loader.exec_module(module)
    return module


check = _load()
FTYP = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8


def test_legacy_hls_rejection_still_serves_static_mp4():
    assert check.failure_reason(401, 206, "video/mp4", FTYP) == ""
    assert check.failure_reason(401, 200, "video/mp4", FTYP) == ""


def test_legacy_hls_must_be_rejected():
    reason = check.failure_reason(200, 206, "video/mp4", FTYP)
    assert "401" in reason
    assert check.legacy_hls_rejected(401)
    assert not check.legacy_hls_rejected(200)


def test_static_mp4_must_be_a_playable_file():
    assert "static MP4" in check.failure_reason(401, 401, "video/mp4", FTYP)
    assert "static MP4" in check.failure_reason(401, 206, "text/plain", FTYP)
    assert "static MP4" in check.failure_reason(401, 206, "video/mp4", b"not-an-mp4")
    assert not check.static_mp4_playable(206, "video/mp4", b"")
