"""Purpose: Watchdog — keep Tailscale (and Opt-In Syncthing) live on fleet Pis.

When peering is Opt In, poll ``tailscale status`` / unit state and heal if share is
not live: restart ``tailscaled``, re-run ``tailscale up`` with ``TS_AUTHKEY``, and
restart ``jellyflam3-syncthing`` when inactive. Opt Out is a no-op.

Requirements: ``pipeline.peering`` helpers; optional systemctl + sudo (same as opt-in);
``secrets.env`` ``TS_AUTHKEY`` for re-auth.

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
import sys
import time
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
    """Attempt to restore Tailscale (+ Syncthing) when Opt In but share is not live."""
    steps: list[str] = []
    before = assess_peering_readiness(cfg)

    if not before["share_opt_in"]:
        return {
            "ok": True,
            "action": "skip",
            "reason": "opt_out",
            "before": before,
            "after": before,
            "steps": steps,
        }

    if before["share_live"]:
        return {
            "ok": True,
            "action": "ok",
            "reason": "share_live",
            "before": before,
            "after": before,
            "steps": steps,
        }

    steps.append(f"issues={before.get('issues')}")

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
    if not dry_run:
        write_status(
            cfg,
            {
                "last_action": "tailscale_watch",
                "steps": steps,
                "healed": bool(after.get("share_live")),
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
        # Drop bulky nested status for CLI noise control — keep issues + states.
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
