"""Purpose: Watchdog — keep Tailscale (and Opt-In Syncthing) live on fleet Pis.

When peering is Opt In, poll ``tailscale status`` / unit state and heal if share is
not live. Heal order: LAN/gateway check → WAN ping → Wi‑Fi reconnect (``nmcli
connect`` while STA still has IPv4; disconnect only when unassociated) → optional
firmware-wedge escalate (brcmfmac reload; opt-in drain+reboot) → restart
``tailscaled`` → ``tailscale up`` (skipped while WAN is still down) → restart
Syncthing if inactive. Opt Out is a no-op.

Requirements: ``pipeline.peering`` helpers; optional systemctl + sudo (same as opt-in);
``secrets.env`` ``TS_AUTHKEY`` for re-auth; ``ip`` / ``ping``; optional ``nmcli`` /
``modprobe`` / ``journalctl``.

Usage:
  python3 -m pipeline.tailscale_watch [--config PATH] [--dry-run] [--json]
  ./scripts/cron_tailscale_watch.sh

When to run: crontab every few minutes on Opt-In fleet hosts (see cron wrapper).
Docs: docs/phase2/05_SYNCTHING_GENOME_PEERING.md · deploy/peering/README.md
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from pipeline.config import load_config
from pipeline.peering import (
    _have,
    _run,
    _systemctl,
    assess_peering_readiness,
    peering_cfg,
    write_status,
    unit_active,
)

log = logging.getLogger("jellyflam3.tailscale_watch")

TAILSCALED_UNIT = "tailscaled.service"
SYNCTHING_UNIT = "jellyflam3-syncthing.service"

_DEFAULT_COOLDOWN_SEC = 900
_DEFAULT_PING_TIMEOUT_SEC = 2
_DEFAULT_WAN_PING_HOST = "1.1.1.1"
_DEFAULT_REBOOT_AFTER_SEC = 1800
_WEDGE_JOURNAL_MARKERS = (
    "SCAN-FAILED ret=-110",
    "brcmf_run_escan: error",
    "brcmf_cfg80211_scan: scan error",
)


def watchdog_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    pc = peering_cfg(cfg)
    return dict(pc.get("watchdog") or {})


def _watch_state_path(cfg: dict[str, Any], key: str, default: str) -> Path:
    wc = watchdog_cfg(cfg)
    raw = wc.get(key) or default
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cfg["_repo_root"]) / path
    return path


def _cooldown_path(cfg: dict[str, Any]) -> Path:
    return _watch_state_path(cfg, "lan_heal_cooldown_file", "/var/lib/jellyflam3/lan_heal_cooldown")


def _wedge_path(cfg: dict[str, Any]) -> Path:
    return _watch_state_path(cfg, "lan_heal_wedge_file", "/var/lib/jellyflam3/lan_heal_wedge")


def default_route() -> dict[str, Any]:
    """Parse ``ip route show default`` → gateway + iface (empty if missing)."""
    if not _have("ip"):
        return {"ok": False, "error": "ip binary missing"}
    proc = subprocess.run(
        ["ip", "route", "show", "default"],
        capture_output=True,
        text=True,
        check=False,
    )
    line = (proc.stdout or "").strip().splitlines()
    if not line:
        return {"ok": False, "error": "no default route"}
    # default via 192.168.156.1 dev wlan0 proto dhcp ...
    text = line[0]
    via_m = re.search(r"\bvia\s+(\S+)", text)
    dev_m = re.search(r"\bdev\s+(\S+)", text)
    gateway = via_m.group(1) if via_m else None
    iface = dev_m.group(1) if dev_m else None
    if not gateway or not iface:
        return {"ok": False, "error": f"unparsed default route: {text[:120]}", "raw": text}
    return {"ok": True, "gateway": gateway, "iface": iface, "raw": text}


def ping_host(host: str, *, timeout_sec: int = _DEFAULT_PING_TIMEOUT_SEC) -> bool:
    """Return True if one ICMP echo to ``host`` succeeds."""
    if not _have("ping"):
        return False
    # Linux: -c count, -W timeout seconds
    proc = subprocess.run(
        ["ping", "-c", "1", "-W", str(max(1, int(timeout_sec))), host],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def check_lan(cfg: dict[str, Any]) -> dict[str, Any]:
    """Probe default-route gateway; used before Tailscale-only heal."""
    wc = watchdog_cfg(cfg)
    timeout = int(wc.get("lan_ping_timeout_sec") or _DEFAULT_PING_TIMEOUT_SEC)
    preferred = (wc.get("lan_preferred_iface") or "").strip() or None
    route = default_route()
    if not route.get("ok"):
        return {
            "ok": False,
            "lan_ok": False,
            "gateway": None,
            "iface": preferred,
            "error": route.get("error"),
        }
    iface = route["iface"]
    gateway = route["gateway"]
    if preferred and iface != preferred:
        return {
            "ok": True,
            "lan_ok": False,
            "gateway": gateway,
            "iface": iface,
            "error": f"default iface {iface} != preferred {preferred}",
        }
    ok = ping_host(gateway, timeout_sec=timeout)
    return {
        "ok": True,
        "lan_ok": ok,
        "gateway": gateway,
        "iface": iface,
        "error": None if ok else f"no ping reply from gateway {gateway}",
    }


def check_wan(cfg: dict[str, Any]) -> dict[str, Any]:
    """Probe a public IPv4 (default 1.1.1.1). Wi‑Fi can reach the LAN gateway and still have a dead STA uplink."""
    wc = watchdog_cfg(cfg)
    if not bool(wc.get("wan_heal_enabled", True)):
        return {"ok": True, "wan_ok": True, "skipped": True, "host": None, "error": None}
    host = (wc.get("wan_ping_host") or _DEFAULT_WAN_PING_HOST).strip()
    timeout = int(wc.get("wan_ping_timeout_sec") or wc.get("lan_ping_timeout_sec") or _DEFAULT_PING_TIMEOUT_SEC)
    if not host:
        return {"ok": True, "wan_ok": True, "skipped": True, "host": None, "error": None}
    ok = ping_host(host, timeout_sec=timeout)
    return {
        "ok": True,
        "wan_ok": ok,
        "skipped": False,
        "host": host,
        "error": None if ok else f"no ping reply from {host}",
    }


def _cooldown_remaining(cfg: dict[str, Any]) -> int:
    path = _cooldown_path(cfg)
    wc = watchdog_cfg(cfg)
    cooldown = int(wc.get("lan_heal_cooldown_sec") or _DEFAULT_COOLDOWN_SEC)
    if not path.is_file():
        return 0
    try:
        last = float(path.read_text(encoding="utf-8").strip().split()[0])
    except (OSError, ValueError, IndexError):
        return 0
    elapsed = time.time() - last
    rem = int(cooldown - elapsed)
    return rem if rem > 0 else 0


def _stamp_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{time.time():.3f}\n", encoding="utf-8")


def _mark_cooldown(cfg: dict[str, Any]) -> None:
    _stamp_file(_cooldown_path(cfg))


def _wedge_age_sec(cfg: dict[str, Any]) -> int | None:
    path = _wedge_path(cfg)
    if not path.is_file():
        return None
    try:
        started = float(path.read_text(encoding="utf-8").strip().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    return max(0, int(time.time() - started))


def _mark_wedge(cfg: dict[str, Any]) -> None:
    path = _wedge_path(cfg)
    if path.is_file():
        return
    _stamp_file(path)


def _clear_wedge(cfg: dict[str, Any]) -> None:
    path = _wedge_path(cfg)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _is_wifi(iface: str) -> bool:
    return bool(iface) and (iface.startswith("wlan") or iface.startswith("wl"))


def _iface_exists(iface: str) -> bool:
    return bool(iface) and Path(f"/sys/class/net/{iface}").exists()


def iface_has_ipv4(iface: str) -> bool:
    """True when ``iface`` has a non-link-local IPv4 address."""
    if not iface or not _have("ip"):
        return False
    proc = subprocess.run(
        ["ip", "-br", "addr", "show", "dev", iface],
        capture_output=True,
        text=True,
        check=False,
    )
    text = proc.stdout or ""
    for match in re.finditer(r"\b(\d+\.\d+\.\d+\.\d+)/\d+", text):
        if not match.group(1).startswith("127."):
            return True
    return False


def resolve_wifi_iface(cfg: dict[str, Any], lan: dict[str, Any]) -> str:
    """Wi‑Fi device to heal: default-route iface, preferred, or onboard wlan0.

    If the default route is already Ethernet, keep that iface so heal_lan skips
    (USB Ethernet is insurance; do not bounce it or fall through to wlan0).
    """
    wc = watchdog_cfg(cfg)
    preferred = (wc.get("lan_preferred_iface") or "").strip()
    iface = str(lan.get("iface") or "").strip()
    if _is_wifi(iface):
        return iface
    if iface and not _is_wifi(iface):
        return iface
    if _is_wifi(preferred):
        return preferred
    if _iface_exists("wlan0"):
        return "wlan0"
    return iface


def sta_associated(iface: str, lan: dict[str, Any]) -> bool:
    """STA still has L3 (IPv4 or a default-route gateway) — do not disconnect."""
    if not _is_wifi(iface):
        return False
    if lan.get("gateway"):
        return True
    return iface_has_ipv4(iface)


def wifi_firmware_wedge(*, since_min: int = 20) -> bool:
    """Kernel log shows a brcmfmac scan hang (``SCAN-FAILED ret=-110``)."""
    if not _have("journalctl"):
        return False
    proc = subprocess.run(
        ["journalctl", "-k", "--since", f"{since_min} min ago", "--no-pager", "-q"],
        capture_output=True,
        text=True,
        check=False,
    )
    text = proc.stdout or ""
    return any(marker in text for marker in _WEDGE_JOURNAL_MARKERS)


def _reload_brcmfmac(*, dry_run: bool) -> list[str]:
    if not _have("modprobe"):
        return ["modprobe missing; skip brcmfmac reload"]
    steps: list[str] = []
    for extra in (["-r", "brcmfmac"], ["brcmfmac"]):
        args = ["sudo", "modprobe", *extra]
        proc = _run(args, dry_run=dry_run)
        steps.append(f"{' '.join(args[1:])} rc={proc.returncode}")
        if not dry_run:
            time.sleep(2)
    return steps


def _request_drain(cfg: dict[str, Any], *, dry_run: bool) -> str:
    cmd = [sys.executable, "-m", "pipeline.worker_drain", "request"]
    config_path = cfg.get("_config_path")
    if config_path:
        cmd.extend(["--config", str(config_path)])
    proc = _run(cmd, dry_run=dry_run)
    return f"worker_drain request rc={proc.returncode}"


def heal_lan(cfg: dict[str, Any], lan: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Reconnect Wi‑Fi when LAN/WAN is down; escalate only on firmware wedge.

    Associated STA (IPv4 or default-route gateway): ``nmcli connect`` only.
    Disconnect / link-down only when unassociated. Connect is never skipped
    because disconnect failed. Soft reconnect still runs during cooldown;
    hard bounce, driver reload, and reboot honor cooldown / opt-in.
    """
    wc = watchdog_cfg(cfg)
    if not bool(wc.get("lan_heal_enabled", True)):
        return {"ok": False, "step": "lan heal disabled", "skipped": True}

    iface = resolve_wifi_iface(cfg, lan)
    if not iface:
        return {"ok": False, "step": "lan heal skipped (no iface)", "skipped": True}

    if not _is_wifi(iface):
        return {
            "ok": False,
            "step": f"lan heal skipped (iface {iface} not wifi)",
            "skipped": True,
            "iface": iface,
        }

    rem = _cooldown_remaining(cfg)
    associated = sta_associated(iface, lan)
    steps: list[str] = []
    heavy = False

    if associated:
        steps.append(f"skip disconnect (STA associated on {iface})")
    elif rem > 0:
        steps.append(f"hard bounce skipped (cooldown {rem}s remaining)")
    else:
        heavy = True
        if _have("nmcli"):
            proc = _run(["sudo", "nmcli", "device", "disconnect", iface], dry_run=dry_run)
            steps.append(f"nmcli device disconnect {iface} rc={proc.returncode}")
            if not dry_run:
                time.sleep(2)
        else:
            proc = _run(["sudo", "ip", "link", "set", iface, "down"], dry_run=dry_run)
            steps.append(f"ip link set {iface} down rc={proc.returncode}")
            if not dry_run:
                time.sleep(2)

    if _have("nmcli"):
        if not dry_run:
            time.sleep(2)
        proc = _run(["sudo", "nmcli", "device", "connect", iface], dry_run=dry_run)
        steps.append(f"nmcli device connect {iface} rc={proc.returncode}")
    else:
        proc = _run(["sudo", "ip", "link", "set", iface, "up"], dry_run=dry_run)
        steps.append(f"ip link set {iface} up rc={proc.returncode}")

    if not dry_run:
        time.sleep(3)

    after = check_lan(cfg)
    still_down = not bool(after.get("lan_ok"))
    journal_wedge = wifi_firmware_wedge()
    no_route = not after.get("gateway")
    driver_on = bool(wc.get("lan_heal_driver_reload_enabled", True))

    if still_down:
        _mark_wedge(cfg)
    else:
        _clear_wedge(cfg)

    if still_down and driver_on and rem == 0 and (journal_wedge or no_route or not associated):
        steps.append(
            "wifi firmware wedge"
            + (" (journal SCAN-FAILED -110)" if journal_wedge else "")
            + (" (no default route)" if no_route else "")
        )
        steps.extend(_reload_brcmfmac(dry_run=dry_run))
        heavy = True
        if not dry_run:
            time.sleep(3)
        after = check_lan(cfg)
        still_down = not bool(after.get("lan_ok"))
        if still_down:
            _mark_wedge(cfg)
        else:
            _clear_wedge(cfg)
    elif still_down and rem > 0:
        steps.append(f"driver reload skipped (cooldown {rem}s remaining)")

    if heavy and not dry_run:
        _mark_cooldown(cfg)

    reboot_on = bool(wc.get("lan_heal_reboot_enabled", False))
    reboot_after = int(wc.get("lan_heal_reboot_after_sec") or _DEFAULT_REBOOT_AFTER_SEC)
    wedge_age = _wedge_age_sec(cfg)
    if still_down and reboot_on and wedge_age is not None and wedge_age >= reboot_after:
        steps.append(f"lan wedge {wedge_age}s >= {reboot_after}s; drain+reboot")
        steps.append(_request_drain(cfg, dry_run=dry_run))
        proc = _run(["sudo", "reboot"], dry_run=dry_run)
        steps.append(f"reboot rc={proc.returncode}")
    elif still_down and not reboot_on and wedge_age is not None:
        steps.append(
            f"lan wedge {wedge_age}s (reboot disabled; "
            "set peering.watchdog.lan_heal_reboot_enabled)"
        )

    result: dict[str, Any] = {
        "ok": bool(after.get("lan_ok")),
        "step": "lan heal " + ("ok" if after.get("lan_ok") else "still_down"),
        "skipped": False,
        "iface": iface,
        "associated": associated,
        "actions": steps,
        "lan_after": after,
    }
    if rem > 0:
        result["cooldown_sec"] = rem
    return result


def _tailscale_up(cfg: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
    """Re-enroll Tailscale with pre-auth key (same flags as ``peering.opt_in``)."""
    if not _have("tailscale"):
        return {"ok": False, "step": "tailscale up skipped (binary missing)"}
    pc = peering_cfg(cfg)
    tag = (pc.get("tailscale") or {}).get("tag") or "tag:jellyflam3"
    auth_env = (pc.get("tailscale") or {}).get("auth_key_env") or "TS_AUTHKEY"
    auth_key = os.environ.get(auth_env, "").strip()
    if not auth_key:
        return {"ok": False, "step": f"tailscale up skipped ({auth_env} unset)"}
    cmd = [
        "sudo",
        "tailscale",
        "up",
        f"--auth-key={auth_key}",
        f"--advertise-tags={tag}",
        "--accept-routes=false",
    ]
    proc = _run(cmd, dry_run=dry_run)
    ok = proc.returncode == 0 or dry_run
    detail = (proc.stderr or proc.stdout or "").strip()[:300]
    return {
        "ok": ok,
        "step": f"tailscale up rc={proc.returncode}",
        "detail": detail,
    }


def heal_opt_in_share(cfg: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Attempt to restore LAN (if needed) + Tailscale (+ Syncthing) when Opt In."""
    steps: list[str] = []
    before = assess_peering_readiness(cfg)
    lan_before = check_lan(cfg)

    if not before["share_opt_in"]:
        return {
            "ok": True,
            "action": "skip",
            "reason": "opt_out",
            "before": before,
            "after": before,
            "steps": steps,
            "lan": lan_before,
        }

    if before["share_live"]:
        return {
            "ok": True,
            "action": "ok",
            "reason": "share_live",
            "before": before,
            "after": before,
            "steps": steps,
            "lan": lan_before,
        }

    steps.append(f"issues={before.get('issues')}")
    steps.append(
        f"lan_ok={lan_before.get('lan_ok')} iface={lan_before.get('iface')} "
        f"gw={lan_before.get('gateway')}"
    )
    wan_before = check_wan(cfg)
    steps.append(
        f"wan_ok={wan_before.get('wan_ok')} host={wan_before.get('host')} "
        f"skipped={wan_before.get('skipped')}"
    )

    # 0) Wi‑Fi reconnect when the gateway is unreachable, or LAN is up but WAN is dead
    # (STA uplink blackhole — Tailscale-only heal cannot fix this, and re-auth while
    # WAN is down previously logged the node out). Associated STA: connect only.
    wc = watchdog_cfg(cfg)
    wan_heal_on = bool(wc.get("wan_heal_enabled", True))
    need_wifi = not lan_before.get("lan_ok")
    if wan_heal_on and lan_before.get("lan_ok") and not wan_before.get("skipped") and not wan_before.get("wan_ok"):
        need_wifi = True
        steps.append("wan down while lan_ok; wifi reconnect")

    if need_wifi:
        lan_heal = heal_lan(cfg, lan_before, dry_run=dry_run)
        steps.append(lan_heal.get("step", "lan heal"))
        for a in lan_heal.get("actions") or []:
            steps.append(a)
        if lan_heal.get("cooldown_sec"):
            steps.append(f"cooldown_sec={lan_heal['cooldown_sec']}")
        lan_before = lan_heal.get("lan_after") or check_lan(cfg)
        steps.append(f"lan_after_ok={lan_before.get('lan_ok')}")
        wan_before = check_wan(cfg)
        steps.append(f"wan_after_ok={wan_before.get('wan_ok')}")

    # 1) Ensure tailscaled daemon is up.
    ts_unit = unit_active(TAILSCALED_UNIT)
    steps.append(f"tailscaled was {ts_unit}")
    if ts_unit != "active":
        _systemctl("restart", TAILSCALED_UNIT, dry_run=dry_run)
        steps.append(f"restart {TAILSCALED_UNIT}")
        if not dry_run:
            time.sleep(2)

    # 2) Re-auth / bring interface up when not Running+online — never while WAN is down.
    ts = before.get("tailscale") or {}
    need_up = True
    if ts.get("backend_state") == "Running" and ts.get("online") is True:
        need_up = False
    wan_now = wan_before
    if need_up:
        if wan_heal_on and not wan_now.get("skipped") and not wan_now.get("wan_ok"):
            steps.append("tailscale up skipped (wan down)")
        else:
            up = _tailscale_up(cfg, dry_run=dry_run)
            steps.append(up["step"])
            if up.get("detail"):
                steps.append(f"up_detail={up['detail']}")
            if not dry_run:
                time.sleep(2)

    # 3) Syncthing must be active for share_live.
    st_unit = unit_active(SYNCTHING_UNIT)
    steps.append(f"syncthing was {st_unit}")
    if st_unit != "active":
        _systemctl("restart", SYNCTHING_UNIT, dry_run=dry_run)
        steps.append(f"restart {SYNCTHING_UNIT}")
        if not dry_run:
            time.sleep(1)

    after = assess_peering_readiness(cfg)
    lan_after = check_lan(cfg)
    wan_after = check_wan(cfg)
    if not dry_run:
        write_status(
            cfg,
            {
                "last_action": "tailscale_watch",
                "steps": steps,
                "healed": bool(after.get("share_live")),
                "lan_ok": bool(lan_after.get("lan_ok")),
                "wan_ok": bool(wan_after.get("wan_ok")),
            },
        )

    live = bool(after.get("share_live"))
    return {
        "ok": live or dry_run,
        "action": "heal",
        "reason": "share_live" if live else "still_not_live",
        "before": before,
        "after": after,
        "steps": steps,
        "lan": lan_after,
        "wan": wan_after,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tailscale / Opt-In share watchdog")
    parser.add_argument("--config", default="configs/jellyflam3.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print result JSON")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    cfg = load_config(args.config)
    result = heal_opt_in_share(cfg, dry_run=args.dry_run)
    if args.json:
        lan = result.get("lan") or {}
        slim = {
            "ok": result["ok"],
            "action": result["action"],
            "reason": result["reason"],
            "steps": result["steps"],
            "before_share_live": (result["before"] or {}).get("share_live"),
            "after_share_live": (result["after"] or {}).get("share_live"),
            "before_issues": (result["before"] or {}).get("issues"),
            "after_issues": (result["after"] or {}).get("issues"),
            "before_tailscale": (result["before"] or {}).get("tailscale"),
            "after_tailscale": (result["after"] or {}).get("tailscale"),
            "lan_ok": lan.get("lan_ok"),
            "lan_iface": lan.get("iface"),
            "lan_gateway": lan.get("gateway"),
            "wan_ok": (result.get("wan") or {}).get("wan_ok"),
        }
        print(json.dumps(slim, indent=2))
    else:
        log.info(
            "action=%s reason=%s ok=%s",
            result["action"],
            result["reason"],
            result["ok"],
        )
        for step in result["steps"]:
            log.info("  %s", step)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
