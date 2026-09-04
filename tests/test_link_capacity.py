"""Unit tests for pipeline.link_capacity (N_max formula, profiles, CLI)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.link_capacity import (
    DEFAULT_HEADROOM,
    HLS_REMUX_MULTIPLIER,
    PROFILES,
    estimate,
    format_estimate,
    main,
    n_max_from_bps,
    parse_bitrate_bps,
    resolve_profile_id,
    session_bps_for_mode,
    summarize_bps,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "configs" / "jellyflam3.yaml.example"


def test_parse_bitrate_ffmpeg_strings():
    assert parse_bitrate_bps("4M") == 4_000_000
    assert parse_bitrate_bps("4m") == 4_000_000
    assert parse_bitrate_bps("3M") == 3_000_000
    assert parse_bitrate_bps("4000k") == 4_000_000
    assert parse_bitrate_bps("8Mbps") == 8_000_000
    assert parse_bitrate_bps(4_000_000) == 4_000_000
    assert parse_bitrate_bps(4.0) == 4_000_000  # small number = Mbps


def test_parse_bitrate_rejects_non_positive():
    with pytest.raises(ValueError):
        parse_bitrate_bps("0")
    with pytest.raises(ValueError):
        parse_bitrate_bps(-1)


def test_n_max_wifi_pi_directplay_lab():
    # 35 Mbps usable, 30% headroom, 4 Mbps session → floor(24.5 / 4) = 6
    usable = 35_000_000
    assert n_max_from_bps(usable, 0.30, 4_000_000) == 6
    assert n_max_from_bps(usable, 0.30, 8_000_000) == 3
    assert n_max_from_bps(900_000_000, 0.30, 4_000_000) == 157


def test_n_max_warns_below_one():
    assert n_max_from_bps(3_000_000, 0.30, 4_000_000) == 0
    est = estimate(profile="wifi-pi", usable_mbps=3.0, session_mbps=4.0, headroom=0.30)
    assert est.n_max == 0
    assert est.warn and "N_max=0" in est.warn


def test_headroom_bounds():
    with pytest.raises(ValueError):
        n_max_from_bps(35_000_000, 1.0, 4_000_000)
    with pytest.raises(ValueError):
        n_max_from_bps(35_000_000, -0.1, 4_000_000)


def test_estimate_uses_encode_bitrate_and_profiles():
    est = estimate(profile="wifi-pi", mode="directplay", encode_bitrate="4M")
    assert est.n_max == 6
    assert est.kind == "wifi"
    assert est.usable_source == "lab"
    assert est.session_mbps == pytest.approx(4.0)
    assert "4M" in est.session_source
    eth = estimate(profile="eth", mode="directplay", encode_bitrate="4M")
    assert eth.profile == "eth-gigabit"
    assert eth.kind == "eth"
    assert eth.n_max == 157
    compact = estimate(profile="wifi-pi", mode="directplay", encode_bitrate="3M")
    assert compact.n_max == 8  # 24.5 / 3


def test_hls_remux_and_transcode_modes():
    dp, _ = session_bps_for_mode("directplay", directplay_bps=4_000_000)
    hls, src = session_bps_for_mode("hls-remux", directplay_bps=4_000_000)
    assert hls == int(4_000_000 * HLS_REMUX_MULTIPLIER)
    assert "remux" in src.lower()
    tr, tsrc = session_bps_for_mode("transcode", directplay_bps=4_000_000)
    assert tr == 8_000_000
    assert "transcode" in tsrc.lower()
    est = estimate(profile="wifi-pi", mode="transcode", encode_bitrate="4M")
    assert est.n_max == 3
    assert est.session_mbps == pytest.approx(8.0)


def test_summarize_bps_percentiles():
    s = summarize_bps([1, 2, 3, 4, 5])
    assert s["count"] == 5
    assert s["min_bps"] == 1
    assert s["max_bps"] == 5
    assert s["p50_bps"] == 3
    empty = summarize_bps([])
    assert empty["count"] == 0
    assert empty["mean_bps"] is None


def test_resolve_profile_aliases():
    assert resolve_profile_id("wifi") == "wifi-pi"
    assert resolve_profile_id("eth-gigabit") == "eth-gigabit"
    with pytest.raises(SystemExit):
        resolve_profile_id("token-ring")


def test_cli_estimate_json_and_profiles(capsys):
    rc = main(["estimate", "--config", str(EXAMPLE), "--profile", "wifi-pi", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["n_max"] >= 1
    assert data["profile"] == "wifi-pi"
    assert data["headroom"] == pytest.approx(DEFAULT_HEADROOM)
    assert "H.264" in data["codec"]

    rc = main(["profiles"])
    assert rc == 0
    out = capsys.readouterr().out
    for pid in PROFILES:
        assert pid in out
    assert "not a Jellyfin cap" in out


def test_cli_estimate_human_and_format(capsys):
    rc = main(
        [
            "estimate",
            "--config",
            str(EXAMPLE),
            "--profile",
            "wifi-pi",
            "--mode",
            "directplay",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "N_max=6" in out
    assert "wifi-uplinked Pi" in out
    est = estimate(profile="wifi-pi", encode_bitrate="4M")
    text = format_estimate(est)
    assert "kind=wifi" in text
    assert "headroom=30%" in text


def test_example_yaml_documents_link_capacity():
    text = EXAMPLE.read_text(encoding="utf-8")
    assert "link_capacity:" in text
    assert "python3 -m pipeline.link_capacity" in text
