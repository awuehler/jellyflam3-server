"""Purpose: Watchdog — keep Tailscale (and Opt-In Syncthing) live on fleet Pis.

When peering is Opt In, poll ``tailscale status`` / unit state and heal if share is
not live. Heal order: LAN/gateway check → optional Wi‑Fi bounce (cooldown) →
restart ``tailscaled`` → ``tailscale up`` → restart Syncthing if inactive.
Opt Out is a no-op.

Requirements: ``pipeline.peering`` helpers; optional systemctl + sudo (same as opt-in);
``secrets.env`` ``TS_AUTHKEY`` for re-auth; ``ip`` / ``ping``; optional ``nmcli``.

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


def watchdog_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    pc = peering_cfg(cfg)
    return dict(pc.get("watchdog") or {})


def _cooldown_path(cfg: dict[str, Any]) -> Path:
    wc = watchdog_cfg(cfg)
    raw = wc.get("lan_heal_cooldown_file") or "/var/lib/jellyflam3/lan_heal_cooldown"
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cfg["_repo_root"]) / path
    return path


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


def _mark_cooldown(cfg: dict[str, Any]) -> None:
    path = _cooldown_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{time.time():.3f}\n", encoding="utf-8")


def heal_lan(cfg: dict[str, Any], lan: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Bounce Wi‑Fi (nmcli preferred) when LAN is down and iface is wireless."""
    wc = watchdog_cfg(cfg)
    if not bool(wc.get("lan_heal_enabled", True)):
        return {"ok": False, "step": "lan heal disabled", "skipped": True}

    rem = _cooldown_remaining(cfg)
    if rem > 0:
        return {
            "ok": False,
            "step": f"lan heal cooldown {rem}s remaining",
            "skipped": True,
            "cooldown_sec": rem,
        }

    iface = lan.get("iface") or ""
    if not iface:
        return {"ok": False, "step": "lan heal skipped (no iface)", "skipped": True}

    # Do not bounce ethernet — only Wi‑Fi style names (and explicit wlan*).
    wireless = iface.startswith("wlan") or iface.startswith("wl")
    if not wireless:
        return {
            "ok": False,
            "step": f"lan heal skipped (iface {iface} not wifi)",
            "skipped": True,
            "iface": iface,
        }

    steps: list[str] = []
    if _have("nmcli"):
        # disconnect → wait → connect (NetworkManager re-associates).
        for args in (
            ["sudo", "nmcli", "device", "disconnect", iface],
            ["sudo", "nmcli", "device", "connect", iface],
        ):
            if args[3] == "connect" and not dry_run:
                time.sleep(2)
            proc = _run(args, dry_run=dry_run)
            steps.append(f"{' '.join(args[1:])} rc={proc.returncode}")
            if proc.returncode != 0 and not dry_run:
                break
    else:
        # Fallback: link flap
        for state in ("down", "up"):
            proc = _run(["sudo", "ip", "link", "set", iface, state], dry_run=dry_run)
            steps.append(f"ip link set {iface} {state} rc={proc.returncode}")
            if not dry_run:
                time.sleep(2)

    if not dry_run:
        _mark_cooldown(cfg)
        time.sleep(3)

    after = check_lan(cfg)
    return {
        "ok": bool(after.get("lan_ok")),
        "step": "lan heal " + ("ok" if after.get("lan_ok") else "still_down"),
        "skipped": False,
        "iface": iface,
        "actions": steps,
        "lan_after": after,
    }


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

    # 0) LAN / Wi‑Fi heal when gateway unreachable (Tailscale-only heal cannot fix this).
    if not lan_before.get("lan_ok"):
        lan_heal = heal_lan(cfg, lan_before, dry_run=dry_run)
        steps.append(lan_heal.get("step", "lan heal"))
        for a in lan_heal.get("actions") or []:
            steps.append(a)
        if lan_heal.get("cooldown_sec"):
            steps.append(f"cooldown_sec={lan_heal['cooldown_sec']}")
        lan_before = lan_heal.get("lan_after") or check_lan(cfg)
        steps.append(f"lan_after_ok={lan_before.get('lan_ok')}")

    # 1) Ensure tailscaled daemon is up.
    ts_unit = unit_active(TAILSCALED_UNIT)
    steps.append(f"tailscaled was {ts_unit}")
    if ts_unit != "active":
        _systemctl("restart", TAILSCALED_UNIT, dry_run=dry_run)
        steps.append(f"restart {TAILSCALED_UNIT}")
        if not dry_run:
            time.sleep(2)

    # 2) Re-auth / bring interface up when not Running+online.
    ts = before.get("tailscale") or {}
    need_up = True
    if ts.get("backend_state") == "Running" and ts.get("online") is True:
        need_up = False
    if need_up:
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
    if not dry_run:
        write_status(
            cfg,
            {
                "last_action": "tailscale_watch",
                "steps": steps,
                "healed": bool(after.get("share_live")),
                "lan_ok": bool(lan_after.get("lan_ok")),
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
