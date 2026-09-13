from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.idle_gate import (
    IdleGateSupervisor,
    closed_wait_seconds,
    is_gate_open,
    persist_status,
    should_block_render,
)


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


def test_is_gate_open_missing_file_fail_closed(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr(
        "pipeline.idle_gate.fetch_sessions",
        lambda _cfg: (_ for _ in ()).throw(RuntimeError("must not probe")),
    )
    assert is_gate_open(cfg) is False
    assert not (tmp_path / "status.json").is_file()


def test_is_gate_open_fresh_open(tmp_path):
    cfg = _cfg(tmp_path)
    persist_status(
        tmp_path / "status.json",
        {
            "gate": "open",
            "reason": "idle",
            "seconds_until_resume": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert is_gate_open(cfg) is True


def test_is_gate_open_stale_open_fail_closed(tmp_path):
    cfg = _cfg(tmp_path)
    stale = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    persist_status(
        tmp_path / "status.json",
        {
            "gate": "open",
            "reason": "idle",
            "seconds_until_resume": 0,
            "updated_at": stale,
        },
    )
    assert is_gate_open(cfg) is False


def test_closed_wait_seconds_uses_eta_capped(tmp_path):
    cfg = _cfg(tmp_path)
    persist_status(
        tmp_path / "status.json",
        {
            "gate": "closed",
            "reason": "idle_delay",
            "seconds_until_resume": 80,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert closed_wait_seconds(cfg) == 15
    persist_status(
        tmp_path / "status.json",
        {
            "gate": "closed",
            "reason": "idle_delay",
            "seconds_until_resume": 4,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert closed_wait_seconds(cfg) == 4


def test_supervisor_hydrates_idle_delay(tmp_path):
    cfg = _cfg(tmp_path)
    cfg["idle_gate"]["idle_delay_sec"] = 100
    started = datetime.now(timezone.utc) - timedelta(seconds=40)
    persist_status(
        tmp_path / "status.json",
        {
            "gate": "closed",
            "reason": "idle_delay",
            "seconds_until_resume": 60,
            "idle_clear_since": started.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    sup = IdleGateSupervisor(cfg)
    st = sup.evaluate(sessions=[])
    assert st["gate"] == "closed"
    assert st["reason"] == "idle_delay"
    assert 50 <= int(st["seconds_until_resume"]) <= 70


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


def test_ignore_screensaver_client(tmp_path):
    """Image SS Client must not close the furnace (defaults in should_block_render)."""
    cfg = _cfg(tmp_path)
    sessions = [
        {
            "Client": "JellyFlam3-Screensaver",
            "DeviceName": "Roku",
            "NowPlayingItem": {"Id": "x"},
        }
    ]
    d = should_block_render(sessions, cfg)
    assert d.blocked is False
    assert d.reason == "idle"


def test_is_gate_open_corrupt_json_fail_closed(tmp_path, caplog):
    cfg = _cfg(tmp_path)
    (tmp_path / "status.json").write_text("{not json", encoding="utf-8")
    assert is_gate_open(cfg) is False


def test_is_gate_open_empty_file_fail_closed(tmp_path):
    cfg = _cfg(tmp_path)
    (tmp_path / "status.json").write_text("", encoding="utf-8")
    assert is_gate_open(cfg) is False


def test_supervisor_status_replace_leaves_no_tmp(tmp_path):
    cfg = _cfg(tmp_path)
    sup = IdleGateSupervisor(cfg)
    sup.evaluate(sessions=[])
    names = {p.name for p in tmp_path.iterdir()}
    assert "status.json" in names
    assert not any(n.endswith(".tmp") for n in names)
