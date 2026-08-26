"""Unit tests for pipeline.tailscale_watch (mocked systemctl / Tailscale)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pipeline import tailscale_watch as tw


def _cfg(tmp_path: Path, *, opted_in: bool) -> dict:
    peers = tmp_path / "peers"
    peers.mkdir()
    if opted_in:
        (peers / "OPT_IN").write_text("{}", encoding="utf-8")
    return {
        "_repo_root": str(tmp_path),
        "peering": {
            "peers_dir": str(peers),
            "opt_in_ack": str(peers / "OPT_IN"),
            "status_file": str(tmp_path / "peering_status.json"),
            "tailscale": {"tag": "tag:jellyflam3", "auth_key_env": "TS_AUTHKEY"},
        },
    }


def test_watch_skips_when_opt_out(tmp_path: Path):
    cfg = _cfg(tmp_path, opted_in=False)
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
    with patch("pipeline.tailscale_watch.assess_peering_readiness", return_value=live):
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
