#!/usr/bin/env bash

# Purpose: Quick pass/fail ops check for mounts, systemd units, peering, idle gate, tools, and inbox.
# Requirements: bash, systemctl (optional), python3, PyYAML; vcgencmd optional (Pi).
#          flam3-genome/animate + ffmpeg/ffprobe on PATH (this script prepends /usr/local/bin).
#
# Usage: ./scripts/healthcheck.sh [config.yaml]
#
# When to run: After git pull / unit install / RC acceptance (docs/phase3/10_TESTING_AND_ACCEPTANCE.md).
# Success: exit 0 — required units active, flam3+ffmpeg present, idle-gate status readable.
# Fail: exit 1 — missing tools (often PATH), units down, status file missing, or Opt In without live share.
#
# Assumptions: Run on the JellyFlam3 host; STATUS_FILE defaults to /var/lib/jellyflam3/idle_gate_status.json.

set -euo pipefail

# flam3 make install lands in /usr/local/bin; non-login shells often miss it.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${1:-$ROOT/configs/jellyflam3.yaml}"
STATUS="${STATUS_FILE:-/var/lib/jellyflam3/idle_gate_status.json}"
ERR=0

echo "== mounts =="
df -h /media/sheep /var/cache/jellyflam3 /var/lib/jellyflam3 2>/dev/null || df -h

echo "== services =="
for u in jellyflam3-worker jellyflam3-idlegate jellyfin; do
  if systemctl is-active --quiet "$u" 2>/dev/null; then
    echo "OK $u active"
  else
    echo "BAD $u not active ($(systemctl is-active "$u" 2>/dev/null || echo missing))"
    ERR=1
  fi
done
# Display profile sink is optional until guide 04 F is enabled on the host.
if systemctl list-unit-files jellyflam3-display-sink.service &>/dev/null; then
  if systemctl is-active --quiet jellyflam3-display-sink 2>/dev/null; then
    echo "OK jellyflam3-display-sink active"
  else
    echo "WARN jellyflam3-display-sink not active (guide 04 F)"
  fi
fi

echo "== peering (guide 05) =="
export JF_CFG="$CFG" JF_ROOT="$ROOT"
if ! python3 - <<'PY'
from pathlib import Path
import os
import sys

from pipeline.config import load_config
from pipeline.peering import assess_peering_readiness, write_status

cfg_path = Path(os.environ["JF_CFG"])
root = Path(os.environ["JF_ROOT"])
if not cfg_path.is_file():
    print("FAIL config missing", cfg_path)
    sys.exit(1)
cfg = load_config(cfg_path, repo_root=root, strict_secrets=False)
live = assess_peering_readiness(cfg)
write_status(cfg, {"last_action": "healthcheck"})

if not live["share_opt_in"]:
    print("OK peering Opt Out (default)")
    if live["syncthing_unit"] == "active":
        print(
            "BAD jellyflam3-syncthing active while Opt Out "
            "— run: python3 -m pipeline.peering opt-out"
        )
        sys.exit(1)
    print("OK jellyflam3-syncthing inactive (Opt Out)")
    sys.exit(0)

print("share_opt_in= True")
print(f"syncthing_unit= {live['syncthing_unit']} (live)")
ts = live["tailscale"]
print(
    f"tailscale= {ts.get('backend_state', 'missing')} "
    f"online={ts.get('online')}"
)
print(f"inbox_flam3= {live['inbox_flam3_count']}")
if live["share_live"]:
    print("OK share live (Syncthing + Tailscale)")
    sys.exit(0)

for issue in live["issues"]:
    print(f"BAD share not live — {issue}")
print(
    "FIX: python3 -m pipeline.peering opt-in "
    "(needs TS_AUTHKEY + syncthing unit) or opt-out to disable sharing"
)
sys.exit(1)
PY
then
  echo "FAIL peering probe"
  ERR=1
fi

echo "== throttle =="
if command -v vcgencmd >/dev/null 2>&1; then
  vcgencmd get_throttled || true
else
  echo "vcgencmd not available (ok on non-Pi)"
fi

echo "== idle gate =="
if [[ -f "$STATUS" ]]; then
  python3 -c "import json;print(json.dumps(json.load(open('$STATUS')), indent=2))"
  gate=$(python3 -c "import json;print(json.load(open('$STATUS')).get('gate'))")
  echo "gate=$gate"
else
  echo "status file missing: $STATUS"
  ERR=1
fi

echo "== tools =="
# flam3 is typically /usr/local/bin/flam3-genome; PATH is prepended at the top of this script.
for t in flam3-genome flam3-animate ffmpeg ffprobe; do
  if command -v "$t" >/dev/null 2>&1; then echo "OK $t"; else echo "MISSING $t"; ERR=1; fi
done

echo "== queue =="
export JF_CFG="$CFG" JF_ROOT="$ROOT"
if ! python3 - <<'PY'
from pathlib import Path
import os
import sys
import yaml
cfg_path = Path(os.environ["JF_CFG"])
root = Path(os.environ["JF_ROOT"])
if not cfg_path.is_file():
    print("FAIL config missing", cfg_path)
    sys.exit(1)
cfg = yaml.safe_load(cfg_path.read_text()) or {}
paths = cfg.get("paths") or {}
if "genomes_inbox" not in paths:
    print("FAIL paths.genomes_inbox missing in", cfg_path)
    sys.exit(1)
inbox = Path(paths["genomes_inbox"])
if not inbox.is_absolute():
    inbox = root / inbox
print("inbox", inbox, "count", len(list(inbox.glob("*.flam3"))))
PY
then
  echo "FAIL queue probe"
  ERR=1
fi

exit "$ERR"
