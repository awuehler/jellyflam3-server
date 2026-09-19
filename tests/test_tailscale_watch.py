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
            "lan_heal_wedge_file": str(tmp_path / "lan_heal_wedge"),
            "lan_heal_driver_reload_enabled": False,
            "lan_heal_reboot_enabled": False,
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


def test_lan_heal_reconnects_wifi_when_gateway_down(tmp_path: Path, monkeypatch):
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
    joined = " ".join(result["steps"])
    assert "nmcli device disconnect wlan0" not in joined
    assert "skip disconnect (STA associated on wlan0)" in joined
    assert "nmcli device connect wlan0" in joined
    assert any("lan heal ok" in s for s in result["steps"])
    # Soft reconnect does not start the hard-bounce cooldown.
    assert not Path(cfg["peering"]["watchdog"]["lan_heal_cooldown_file"]).is_file()


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
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping"}),
        patch("pipeline.tailscale_watch._run") as run,
        patch("pipeline.tailscale_watch.time.sleep"),
        patch("pipeline.tailscale_watch.write_status"),
    ):
        run.return_value = type("P", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        up.return_value = {"ok": True, "step": "tailscale up rc=0"}
        result = tw.heal_opt_in_share(cfg, dry_run=False)

    joined = " ".join(result["steps"])
    assert "cooldown" in joined
    assert "nmcli device disconnect wlan0" not in joined
    assert "nmcli device connect wlan0" in joined
    assert "modprobe" not in joined


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
    assert any("wan down while lan_ok; wifi reconnect" in s for s in result["steps"])
    joined = " ".join(result["steps"])
    assert "nmcli device disconnect wlan0" not in joined
    assert "nmcli device connect wlan0" in joined
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


def _ok_proc(rc: int = 0):
    return type("P", (), {"returncode": rc, "stdout": "", "stderr": ""})()


def test_lan_heal_disconnects_when_unassociated(tmp_path: Path):
    cfg = _cfg(tmp_path, opted_in=True)
    lan = {
        "ok": False,
        "lan_ok": False,
        "gateway": None,
        "iface": None,
        "error": "no default route",
    }
    cfg["peering"]["watchdog"]["lan_preferred_iface"] = "wlan0"
    with (
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping"}),
        patch("pipeline.tailscale_watch._run", return_value=_ok_proc()) as run,
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_ok()),
        patch("pipeline.tailscale_watch.iface_has_ipv4", return_value=False),
        patch("pipeline.tailscale_watch.wifi_firmware_wedge", return_value=False),
        patch("pipeline.tailscale_watch.time.sleep"),
    ):
        result = tw.heal_lan(cfg, lan, dry_run=False)

    cmds = [" ".join(c.args[0]) for c in run.call_args_list]
    assert any("nmcli device disconnect wlan0" in c for c in cmds)
    assert any("nmcli device connect wlan0" in c for c in cmds)
    assert result["associated"] is False
    assert Path(cfg["peering"]["watchdog"]["lan_heal_cooldown_file"]).is_file()


def test_lan_heal_connects_after_disconnect_fails(tmp_path: Path):
    cfg = _cfg(tmp_path, opted_in=True)
    lan = {
        "ok": False,
        "lan_ok": False,
        "gateway": None,
        "iface": "wlan0",
        "error": "no default route",
    }

    def _run_side(cmd, **_kwargs):
        joined = " ".join(cmd)
        return _ok_proc(1 if "disconnect" in joined else 0)

    with (
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping"}),
        patch("pipeline.tailscale_watch._run", side_effect=_run_side) as run,
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_ok()),
        patch("pipeline.tailscale_watch.iface_has_ipv4", return_value=False),
        patch("pipeline.tailscale_watch.wifi_firmware_wedge", return_value=False),
        patch("pipeline.tailscale_watch.time.sleep"),
    ):
        result = tw.heal_lan(cfg, lan, dry_run=False)

    cmds = [" ".join(c.args[0]) for c in run.call_args_list]
    assert any("disconnect" in c for c in cmds)
    assert any("connect" in c for c in cmds)
    assert any("nmcli device connect wlan0 rc=0" in a for a in result["actions"])


def test_lan_heal_driver_reload_on_firmware_wedge(tmp_path: Path):
    cfg = _cfg(
        tmp_path,
        opted_in=True,
        watchdog={"lan_heal_driver_reload_enabled": True},
    )
    lan = _lan_bad()
    with (
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping", "modprobe"}),
        patch("pipeline.tailscale_watch._run", return_value=_ok_proc()) as run,
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_bad()),
        patch("pipeline.tailscale_watch.wifi_firmware_wedge", return_value=True),
        patch("pipeline.tailscale_watch.time.sleep"),
    ):
        result = tw.heal_lan(cfg, lan, dry_run=False)

    cmds = [" ".join(c.args[0]) for c in run.call_args_list]
    assert not any("disconnect" in c for c in cmds)
    assert any("nmcli device connect wlan0" in c for c in cmds)
    assert any("modprobe -r brcmfmac" in c for c in cmds)
    assert any("modprobe brcmfmac" in c for c in cmds)
    assert result["step"] == "lan heal still_down"
    assert Path(cfg["peering"]["watchdog"]["lan_heal_cooldown_file"]).is_file()
    assert Path(cfg["peering"]["watchdog"]["lan_heal_wedge_file"]).is_file()


def test_lan_heal_reboot_opt_in_after_wedge_age(tmp_path: Path):
    cfg = _cfg(
        tmp_path,
        opted_in=True,
        watchdog={
            "lan_heal_reboot_enabled": True,
            "lan_heal_reboot_after_sec": 1800,
        },
    )
    cfg["_config_path"] = str(tmp_path / "jellyflam3.yaml")
    wedge = Path(cfg["peering"]["watchdog"]["lan_heal_wedge_file"])
    wedge.write_text(f"{__import__('time').time() - 2000:.3f}\n", encoding="utf-8")
    lan = _lan_bad()
    with (
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping"}),
        patch("pipeline.tailscale_watch._run", return_value=_ok_proc()) as run,
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_bad()),
        patch("pipeline.tailscale_watch.wifi_firmware_wedge", return_value=False),
        patch("pipeline.tailscale_watch.time.sleep"),
    ):
        result = tw.heal_lan(cfg, lan, dry_run=False)

    cmds = [" ".join(c.args[0]) for c in run.call_args_list]
    assert any("pipeline.worker_drain" in c and "request" in c for c in cmds)
    assert any(c == "sudo reboot" or c.endswith("reboot") for c in cmds)
    assert any("drain+reboot" in a for a in result["actions"])


def test_lan_heal_no_reboot_when_disabled(tmp_path: Path):
    cfg = _cfg(tmp_path, opted_in=True)
    wedge = Path(cfg["peering"]["watchdog"]["lan_heal_wedge_file"])
    wedge.write_text(f"{__import__('time').time() - 2000:.3f}\n", encoding="utf-8")
    lan = _lan_bad()
    with (
        patch("pipeline.tailscale_watch._have", side_effect=lambda c: c in {"nmcli", "ip", "ping"}),
        patch("pipeline.tailscale_watch._run", return_value=_ok_proc()) as run,
        patch("pipeline.tailscale_watch.check_lan", return_value=_lan_bad()),
        patch("pipeline.tailscale_watch.wifi_firmware_wedge", return_value=False),
        patch("pipeline.tailscale_watch.time.sleep"),
    ):
        result = tw.heal_lan(cfg, lan, dry_run=False)

    cmds = [" ".join(c.args[0]) for c in run.call_args_list]
    assert not any("reboot" in c for c in cmds)
    assert any("reboot disabled" in a for a in result["actions"])


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
