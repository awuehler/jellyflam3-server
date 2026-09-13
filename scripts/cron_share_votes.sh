#!/usr/bin/env bash

# Purpose: Periodic cron — stage liked catalog sheep into peers/share-out (Phase 4 / 08).
# Requirements: bash, python3, flock; pipeline.share_votes; Opt In for live mesh.
#          Does **not** promote into genomes/inbox (gated promote --apply stays).
#
# Usage:
#   ./scripts/cron_share_votes.sh [--config PATH] [--dry-run]
#   python3 -m pipeline.share_votes --config configs/jellyflam3.yaml --json
#   python3 -m pipeline.share_votes --apply --json
#
# When to run: crontab as user jellyflam3. Lab fleet: 06:41 local daily
#   (after 05:11 idle-breed; staggered from ~10-day archive DOM).
# Success: JSON action=share|plan|skip (opt_out, disabled, no_candidates, …).
# Fail: missing config → exit 1. Tax/integrity refuse is per-file in JSON.
# Docs: docs/phase4/08_VIEWER_FEEDBACK_LOOP.md
#
# Assumptions: Sidecar viewer_feedback is SoT. Kill-switch share_votes.enabled.
# Commercial-mode furnaces skip NC. Copy into share-out; leave genomes_done.
#
# ---------------------------------------------------------------------------
# Lab crontab (user jellyflam3) — 06:41 local daily on 16a / 08a / 04a:
#
#   41 6 * * *  /opt/jellyflam3-server/scripts/cron_share_votes.sh \
#       >>/var/log/jellyflam3/share_votes.log 2>&1
#
# Idle breed remains:
#   11 5 * * *  /opt/jellyflam3-server/scripts/cron_breed_idle.sh \
#       >>/var/log/jellyflam3/breed_idle.log 2>&1
#
# Ensure /var/log/jellyflam3 exists and is writable by the cron user.
# ---------------------------------------------------------------------------
#
# Environment overrides (optional):
#   JELLYFLAM3_CONFIG           path to jellyflam3.yaml
#   SHARE_VOTES_DRY_RUN=1       plan only (no copy)
#   SHARE_VOTES_CRON_LOCK       flock path (default: /var/lock/jellyflam3-share-votes.lock)

set -euo pipefail

export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${JELLYFLAM3_CONFIG:-$ROOT/configs/jellyflam3.yaml}"
LOCK="${SHARE_VOTES_CRON_LOCK:-/var/lock/jellyflam3-share-votes.lock}"
DRY_RUN=0

log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

usage() {
  sed -n '2,50p' "$0"
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
  log "ERROR config not found: $CFG (set JELLYFLAM3_CONFIG or create configs/jellyflam3.yaml)"
  exit 1
fi

if ! touch "$LOCK" 2>/dev/null; then
  LOCK="/tmp/jellyflam3-share-votes.lock"
  touch "$LOCK"
fi
exec 9>"$LOCK"
if ! flock -n 9; then
  log "SKIP another share-votes run holds $LOCK"
  exit 0
fi

CMD=(python3 -m pipeline.share_votes --config "$CFG" --json)
if [[ "$DRY_RUN" == "1" || "${SHARE_VOTES_DRY_RUN:-0}" == "1" ]]; then
  CMD+=(--dry-run)
else
  CMD+=(--apply)
fi

log "RUN ${CMD[*]}"
cd "$ROOT"
OUT="$("${CMD[@]}")"
printf '%s\n' "$OUT"
ACTION="$(printf '%s\n' "$OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('action','?'))")"
log "DONE action=$ACTION"
