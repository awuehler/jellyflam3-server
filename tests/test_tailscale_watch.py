"""Unit tests for pipeline.tailscale_watch (mocked systemctl / Tailscale / LAN)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pipeline import tailscale_watch as tw
from pipeline import peering


def _cfg(tmp_path: Path, *, opted_in: bool, watchdog: dict | None = None) -> dict:
    peers = tmp_path / "peers"
    peers.mkdir()
    if opted_in:
        (peers / "OPT_IN").write_text("{}", encoding="utf-8")
    peering_block: dict = {
        "peers_dir": str(peers),
        "opt_in_ack": str(peers / "OPT_IN"),
        "status_file": str(tmp_path / "peering_status.json"),
        "tailscale": {"tag": "tag:jellyflam3", "auth_key_env": "TS_AUTHKEY"},
        "watchdog": {
            "lan_heal_enabled": True,
            "lan_heal_cooldown_sec": 900,
            "lan_heal_cooldown_file": str(tmp_path / "lan_heal_cooldown"),
            "lan_ping_timeout_sec": 2,
            **(watchdog or {}),
        },
    }
    return {
        "_repo_root": str(tmp_path),
        "peering": peering_block,
    }


def _lan_ok(iface: str = "wlan0") -> dict:
    return {
        "ok": True,
        "lan_ok": True,
        "gateway": "192.168.156.1",
        "iface": iface,
        "error": None,
    }


def _lan_bad(iface: str = "wlan0") -> dict:
    return {
        "ok": True,
        "lan_ok": False,
        "gateway": "192.168.156.1",
        "iface": iface,
        "error": "no ping reply from gateway 192.168.156.1",
    }


def _wan_ok() -> dict:
    return {
        "ok": True,
        "wan_ok": True,
        "skipped": False,
        "host": "1.1.1.1",
        "error": None,
    }


def _wan_bad() -> dict:
    return {
        "ok": True,
        "wan_ok": False,
        "skipped": False,
        "host": "1.1.1.1",
        "error": "no ping reply from 1.1.1.1",
    }


def test_watch_skips_when_opt_out(tmp_path: Path):
    cfg = _cfg(tmp_path, opted_in=False)
    with patch("pipeline.tailscale_watch.check_lan", return_value=_lan_ok()):
        result = tw.heal_opt_in_share(cfg, dry_run=True)
    assert result["action"] == "skip"
    assert result["reason"] == "opt_out"
    assert result["ok"] is True


def test_watch_ok_when_share_live(tmp_path: Path):
    cfg = _cfg(tmp_path, opted_in=True)
    live = {
        "share_opt_in": True,
        "share_live": True,
        "syncthing_unit": "active",
        "tailscale": {
            "installed": True,
            "ok": True,
            "backend_state": "Running",
            "online": True,
        },
        "issues": [],
        "inbox_flam3_count": 0,
    }
    with (
        patch("pipeline.tailscale_watch.assess_peering_readiness", return_value=live),
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_ok()),
    ):
        result = tw.heal_opt_in_share(cfg, dry_run=True)
    assert result["action"] == "ok"
    assert result["reason"] == "share_live"
    assert result["ok"] is True


def test_watch_heals_when_not_live(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path, opted_in=True)
    monkeypatch.setenv("TS_AUTHKEY", "tskey-auth-test")
    broken = {
        "share_opt_in": True,
        "share_live": False,
        "syncthing_unit": "inactive",
        "tailscale": {
            "installed": True,
            "ok": True,
            "backend_state": "NeedsLogin",
            "online": False,
        },
        "issues": ["tailscale not connected (NeedsLogin)"],
        "inbox_flam3_count": 0,
    }
    fixed = {
        "share_opt_in": True,
        "share_live": True,
        "syncthing_unit": "active",
        "tailscale": {
            "installed": True,
            "ok": True,
            "backend_state": "Running",
            "online": True,
        },
        "issues": [],
        "inbox_flam3_count": 0,
    }
    with (
        patch(
            "pipeline.tailscale_watch.assess_peering_readiness",
            side_effect=[broken, fixed],
        ),
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_ok()),
        patch("pipeline.tailscale_watch.check_wan", return_value=_wan_ok()),
        patch("pipeline.tailscale_watch.unit_active", side_effect=["inactive", "inactive"]),
        patch("pipeline.tailscale_watch._systemctl") as sc,
        patch("pipeline.tailscale_watch._tailscale_up") as up,
        patch("pipeline.tailscale_watch.time.sleep"),
        patch("pipeline.tailscale_watch.write_status"),
    ):
        up.return_value = {"ok": True, "step": "tailscale up rc=0"}
        result = tw.heal_opt_in_share(cfg, dry_run=False)

    assert result["action"] == "heal"
    assert result["reason"] == "share_live"
    assert result["ok"] is True
    assert sc.call_count >= 2
    up.assert_called_once()


def test_lan_heal_bounces_wifi_when_gateway_down(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path, opted_in=True)
    monkeypatch.setenv("TS_AUTHKEY", "tskey-auth-test")
    broken = {
        "share_opt_in": True,
        "share_live": False,
        "syncthing_unit": "active",
        "tailscale": {
            "installed": True,
            "ok": True,
            "backend_state": "Running",
            "online": False,
        },
        "issues": ["tailscale not connected (Running)"],
        "inbox_flam3_count": 0,
    }
    fixed = dict(broken)
    fixed["share_live"] = True
    fixed["issues"] = []
    fixed["tailscale"] = {
        "installed": True,
        "ok": True,
        "backend_state": "Running",
        "online": True,
    }
    with (
        patch(
            "pipeline.tailscale_watch.assess_peering_readiness",
            side_effect=[broken, fixed],
        ),
        patch(
            "pipeline.tailscale_watch.check_lan",
            side_effect=[_lan_bad(), _lan_ok(), _lan_ok()],
        ),
        patch("pipeline.tailscale_watch.check_wan", return_value=_wan_ok()),
        patch("pipeline.tailscale_watch.unit_active", return_value="active"),
        patch("pipeline.tailscale_watch._systemctl"),
        patch("pipeline.tailscale_watch._tailscale_up") as up,
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping"}),
        patch("pipeline.tailscale_watch._run") as run,
        patch("pipeline.tailscale_watch.time.sleep"),
        patch("pipeline.tailscale_watch.write_status"),
    ):
        run.return_value = type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        up.return_value = {"ok": True, "step": "tailscale up rc=0"}
        result = tw.heal_opt_in_share(cfg, dry_run=False)

    assert result["ok"] is True
    assert any("nmcli device disconnect wlan0" in s for s in result["steps"])
    assert any("lan heal ok" in s for s in result["steps"])
    # Cooldown file written
    assert Path(cfg["peering"]["watchdog"]["lan_heal_cooldown_file"]).is_file()


def test_lan_heal_respects_cooldown(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path, opted_in=True, watchdog={"lan_heal_cooldown_sec": 900})
    monkeypatch.setenv("TS_AUTHKEY", "tskey-auth-test")
    cool = Path(cfg["peering"]["watchdog"]["lan_heal_cooldown_file"])
    cool.write_text(f"{__import__('time').time():.3f}\n", encoding="utf-8")
    broken = {
        "share_opt_in": True,
        "share_live": False,
        "syncthing_unit": "active",
        "tailscale": {
            "installed": True,
            "ok": True,
            "backend_state": "Running",
            "online": False,
        },
        "issues": ["tailscale not connected (Running)"],
        "inbox_flam3_count": 0,
    }
    with (
        patch(
            "pipeline.tailscale_watch.assess_peering_readiness",
            side_effect=[broken, broken],
        ),
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_bad()),
        patch("pipeline.tailscale_watch.check_wan", return_value=_wan_ok()),
        patch("pipeline.tailscale_watch.unit_active", return_value="active"),
        patch("pipeline.tailscale_watch._systemctl"),
        patch("pipeline.tailscale_watch._tailscale_up") as up,
        patch("pipeline.tailscale_watch._run") as run,
        patch("pipeline.tailscale_watch.time.sleep"),
        patch("pipeline.tailscale_watch.write_status"),
    ):
        up.return_value = {"ok": True, "step": "tailscale up rc=0"}
        result = tw.heal_opt_in_share(cfg, dry_run=False)

    assert any("cooldown" in s for s in result["steps"])
    run.assert_not_called()  # no nmcli during cooldown


def test_wan_heal_bounces_wifi_when_lan_up_wan_down(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path, opted_in=True)
    monkeypatch.setenv("TS_AUTHKEY", "tskey-auth-test")
    broken = {
        "share_opt_in": True,
        "share_live": False,
        "syncthing_unit": "active",
        "tailscale": {
            "installed": True,
            "ok": True,
            "backend_state": "Running",
            "online": False,
        },
        "issues": ["tailscale not connected (Running)"],
        "inbox_flam3_count": 0,
    }
    fixed = dict(broken)
    fixed["share_live"] = True
    fixed["issues"] = []
    fixed["tailscale"] = {
        "installed": True,
        "ok": True,
        "backend_state": "Running",
        "online": True,
    }
    with (
        patch(
            "pipeline.tailscale_watch.assess_peering_readiness",
            side_effect=[broken, fixed],
        ),
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_ok()),
        patch(
            "pipeline.tailscale_watch.check_wan",
            side_effect=[_wan_bad(), _wan_ok(), _wan_ok()],
        ),
        patch("pipeline.tailscale_watch.unit_active", return_value="active"),
        patch("pipeline.tailscale_watch._systemctl"),
        patch("pipeline.tailscale_watch._tailscale_up") as up,
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping"}),
        patch("pipeline.tailscale_watch._run") as run,
        patch("pipeline.tailscale_watch.time.sleep"),
        patch("pipeline.tailscale_watch.write_status"),
    ):
        run.return_value = type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        up.return_value = {"ok": True, "step": "tailscale up rc=0"}
        result = tw.heal_opt_in_share(cfg, dry_run=False)

    assert result["ok"] is True
    assert any("wan down while lan_ok" in s for s in result["steps"])
    assert any("nmcli device disconnect wlan0" in s for s in result["steps"])
    up.assert_called_once()


def test_tailscale_up_skipped_while_wan_down(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path, opted_in=True)
    monkeypatch.setenv("TS_AUTHKEY", "tskey-auth-test")
    broken = {
        "share_opt_in": True,
        "share_live": False,
        "syncthing_unit": "active",
        "tailscale": {
            "installed": True,
            "ok": True,
            "backend_state": "Running",
            "online": False,
        },
        "issues": ["tailscale not connected (Running)"],
        "inbox_flam3_count": 0,
    }
    with (
        patch(
            "pipeline.tailscale_watch.assess_peering_readiness",
            side_effect=[broken, broken],
        ),
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_ok()),
        patch("pipeline.tailscale_watch.check_wan", return_value=_wan_bad()),
        patch("pipeline.tailscale_watch.unit_active", return_value="active"),
        patch("pipeline.tailscale_watch._systemctl"),
        patch("pipeline.tailscale_watch._tailscale_up") as up,
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping"}),
        patch("pipeline.tailscale_watch._run") as run,
        patch("pipeline.tailscale_watch.time.sleep"),
        patch("pipeline.tailscale_watch.write_status"),
    ):
        run.return_value = type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        result = tw.heal_opt_in_share(cfg, dry_run=False)

    assert any("tailscale up skipped (wan down)" in s for s in result["steps"])
    up.assert_not_called()


def test_lan_heal_skips_ethernet(tmp_path: Path):
    cfg = _cfg(tmp_path, opted_in=True)
    lan = _lan_bad(iface="eth0")
    result = tw.heal_lan(cfg, lan, dry_run=True)
    assert result["skipped"] is True
    assert "not wifi" in result["step"]


def test_run_redacts_auth_key(caplog):
    import logging

    caplog.set_level(logging.INFO)
    peering._run(
        ["sudo", "tailscale", "up", "--auth-key=tskey-auth-SECRET", "--advertise-tags=tag:x"],
        dry_run=True,
    )
    joined = " ".join(r.message for r in caplog.records)
    assert "tskey-auth-SECRET" not in joined
    assert "--auth-key=<redacted>" in joined
