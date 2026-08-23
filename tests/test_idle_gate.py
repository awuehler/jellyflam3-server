import json
from datetime import datetime, timezone
from pathlib import Path

from pipeline.idle_gate import IdleGateSupervisor, is_gate_open, should_block_render


def _cfg(tmp_path: Path):
    return {
        "paths": {"status_file": str(tmp_path / "status.json")},
        "idle_gate": {
            "enabled": True,
            "idle_delay_sec": 60,
            "poll_interval_sec": 1,
            "tv_client_patterns": [r"(?i)roku", r"(?i)jellyflam3"],
            "block_on_any_transcode": True,
            "block_non_tv_playback": False,
        },
        "jellyfin": {"url": "http://example", "api_key": "x"},
        "_repo_root": str(tmp_path),
    }


def test_block_tv_playing(tmp_path):
    cfg = _cfg(tmp_path)
    sessions = [
        {
            "Client": "JellyFlam3",
            "DeviceName": "Roku Ultra",
            "NowPlayingItem": {"Name": "dream"},
        }
    ]
    d = should_block_render(sessions, cfg)
    assert d.blocked and d.reason == "active_tv_client"


def test_block_transcode(tmp_path):
    cfg = _cfg(tmp_path)
    sessions = [{"Client": "Web", "TranscodingInfo": {"VideoCodec": "h264"}}]
    d = should_block_render(sessions, cfg)
    assert d.blocked and d.reason == "active_transcode"


def test_idle_allows(tmp_path):
    cfg = _cfg(tmp_path)
    d = should_block_render([{"Client": "Web", "IsActive": True}], cfg)
    assert not d.blocked


def test_supervisor_opens_immediately_when_never_blocked(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["idle_gate"]["idle_delay_sec"] = 100
    sup = IdleGateSupervisor(cfg)
    st = sup.evaluate(sessions=[])
    assert st["gate"] == "open"
    assert st["reason"] == "idle"


def test_supervisor_delay_after_tv(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["idle_gate"]["idle_delay_sec"] = 100
    sup = IdleGateSupervisor(cfg)
    playing = [
        {
            "Client": "JellyFlam3",
            "DeviceName": "Roku Ultra",
            "NowPlayingItem": {"Name": "dream"},
        }
    ]
    st = sup.evaluate(sessions=playing)
    assert st["gate"] == "closed"
    assert st["reason"] == "active_tv_client"
    st2 = sup.evaluate(sessions=[])
    assert st2["gate"] == "closed"
    assert st2["reason"] == "idle_delay"
    # Simulate delay elapsed
    sup._clear_since = 0
    st3 = sup.evaluate(sessions=[])
    assert st3["gate"] == "open"


def test_is_gate_open_bootstrap_idle(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(
        "pipeline.idle_gate.fetch_sessions",
        lambda _cfg: [{"Client": "Web", "IsActive": True}],
    )
    assert is_gate_open(cfg) is True
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["gate"] == "open"
    assert status["reason"] == "bootstrap"


def test_is_gate_open_bootstrap_blocks_tv(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(
        "pipeline.idle_gate.fetch_sessions",
        lambda _cfg: [
            {
                "Client": "Jellyfin Roku",
                "NowPlayingItem": {"Name": "dream"},
            }
        ],
    )
    assert is_gate_open(cfg) is False
    assert not (tmp_path / "status.json").is_file()


def test_block_tv_recent_checkin(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["idle_gate"]["active_within_seconds"] = 120
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sessions = [
        {
            "Client": "JellyFlam3",
            "DeviceName": "Roku",
            "DeviceId": "jellyflam3-roku",
            "LastPlaybackCheckIn": now,
        }
    ]
    d = should_block_render(sessions, cfg)
    assert d.blocked and d.reason == "active_tv_client"


def test_ignore_stale_checkin(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["idle_gate"]["active_within_seconds"] = 30
    sessions = [
        {
            "Client": "JellyFlam3",
            "DeviceName": "Roku",
            "LastPlaybackCheckIn": "2020-01-01T00:00:00Z",
        }
    ]
    d = should_block_render(sessions, cfg)
    assert not d.blocked
