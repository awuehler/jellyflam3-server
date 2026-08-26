#!/usr/bin/env bash

# Purpose: Cron — poll Tailscale / Opt-In share and heal when not live (fleet).
# Requirements: bash, flock, python3; pipeline.tailscale_watch; sudo for systemctl
#          + tailscale (same passwordless sudo as peering opt-in); secrets.env TS_AUTHKEY.
#
# Usage:
#   ./scripts/cron_tailscale_watch.sh [--config PATH] [--dry-run]
#   python3 -m pipeline.tailscale_watch --config configs/jellyflam3.yaml --json
#
# When to run: crontab as user jellyflam3 every few minutes on Opt-In fleet hosts.
# Success: log DONE action=ok|skip|heal with ok; share_live true when Opt In.
# Fail: exit 1 when Opt In and still not live after heal (see log JSON).
# Docs: docs/phase2/05_SYNCTHING_GENOME_PEERING.md · deploy/peering/README.md
#
# Opt Out: no-op (action=skip). Does not force Tailscale up when not peered.
#
# ---------------------------------------------------------------------------
# Lab crontab (user jellyflam3) — every 5 minutes on 16a / 08a / 04a:
#
#   */5 * * * *  /opt/jellyflam3-server/scripts/cron_tailscale_watch.sh \
#       >>/var/log/jellyflam3/tailscale_watch.log 2>&1
#
# Ensure /var/log/jellyflam3 exists and is writable by the cron user.
# ---------------------------------------------------------------------------
#
# Environment overrides (optional):
#   JELLYFLAM3_CONFIG              path to jellyflam3.yaml
#   TAILSCALE_WATCH_DRY_RUN=1      print heal plan only
#   TAILSCALE_WATCH_CRON_LOCK      flock path

set -euo pipefail

export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${JELLYFLAM3_CONFIG:-$ROOT/configs/jellyflam3.yaml}"
LOCK="${TAILSCALE_WATCH_CRON_LOCK:-/var/lock/jellyflam3-tailscale-watch.lock}"
DRY_RUN=0

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

usage() {
  sed -n '2,40p' "$0"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    --dry-run) DRY_RUN=1; shift ;;
    --config)
      CFG="$2"
      shift 2
      ;;
    *)
      log "ERROR unknown arg: $1"
      exit 2
      ;;
  esac
done

if [[ ! -f "$CFG" ]]; then
  log "ERROR config not found: $CFG"
  exit 1
fi

if ! touch "$LOCK" 2>/dev/null; then
  LOCK="/tmp/jellyflam3-tailscale-watch.lock"
  touch "$LOCK"
fi
exec 9>"$LOCK"
if ! flock -n 9; then
  log "SKIP another tailscale-watch run holds $LOCK"
  exit 0
fi

CMD=(python3 -m pipeline.tailscale_watch --config "$CFG" --json)
if [[ "$DRY_RUN" == "1" || "${TAILSCALE_WATCH_DRY_RUN:-0}" == "1" ]]; then
  CMD+=(--dry-run)
fi

log "RUN ${CMD[*]}"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
set +e
OUT="$("${CMD[@]}")"
RC=$?
set -e
printf '%s\n' "$OUT"
ACTION="$(printf '%s\n' "$OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('action','?'))" 2>/dev/null || echo '?')"
REASON="$(printf '%s\n' "$OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('reason','?'))" 2>/dev/null || echo '?')"
log "DONE action=$ACTION reason=$REASON rc=$RC"
exit "$RC"
