#!/usr/bin/env bash

# Purpose: Daily cron — breed one pedigree sheep when inbox is empty and worker is idle
#          so the furnace keeps working between ~10-day archive fills (Phase 2 guide 07).
# Requirements: bash, python3, flock; pipeline.breed_idle; flam3-genome on PATH
#          (/usr/local/bin — this wrapper prepends it; cron PATH is often /usr/bin:/bin).
#          Writable inbox + history file (breed.idle_breed.history_file).
#
# Usage:
#   ./scripts/cron_breed_idle.sh [--config PATH] [--dry-run] [--evaluate]
#   python3 -m pipeline.breed_idle --config configs/jellyflam3.yaml --json
#
# When to run: crontab as user jellyflam3 (not root). Lab fleet: 05:11 local daily.
# Success: log DONE action=breed (one child in genomes/inbox) or action=skip with a reason
#   (inbox_not_empty, gate_closed, live_render, too_close_to_archive, …).
# Fail: FileNotFoundError flam3-genome → PATH; see /var/log/jellyflam3/breed_idle.log.
# Benign stderr: flam3-genome may print "warning: reached maximum attempts, giving up."
#   during mutate/cross when its internal optimizer exhausts retries — OK if JSON shows action=breed.
# Docs: docs/phase2/07_PEDIGREE_BREEDING.md
#
# Assumptions: Inbox must be empty; idle gate open; no live render jobs; parent pool
# from genomes_done + genomes/samples + genomes/pedigree; dedup vs recent history.
#
# ---------------------------------------------------------------------------
# Lab crontab (user jellyflam3) — 05:11 local daily on 16a / 08a / 04a:
#
#   11 5 * * *  /opt/jellyflam3-server/scripts/cron_breed_idle.sh \
#       >>/var/log/jellyflam3/breed_idle.log 2>&1
#
# Archive seed is a separate ~10-day cron (staggered DOM per host). Example 04a:
#   17 3 3,13,23 * *  /opt/jellyflam3-server/scripts/cron_archive_seed.sh \
#       >>/var/log/jellyflam3/archive_seed.log 2>&1
#
# Ensure /var/log/jellyflam3 exists and is writable by the cron user.
# ---------------------------------------------------------------------------
#
# Environment overrides (optional):
#   JELLYFLAM3_CONFIG           path to jellyflam3.yaml
#   BREED_IDLE_DRY_RUN=1        print actions only
#   BREED_IDLE_CRON_LOCK        flock path (default: /var/lock/jellyflam3-breed-idle.lock)

set -euo pipefail

# flam3 make install lands in /usr/local/bin; cron PATH is often just /usr/bin:/bin.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${JELLYFLAM3_CONFIG:-$ROOT/configs/jellyflam3.yaml}"
LOCK="${BREED_IDLE_CRON_LOCK:-/var/lock/jellyflam3-breed-idle.lock}"
DRY_RUN=0
EVALUATE=0

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
    --evaluate) EVALUATE=1; shift ;;
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
  LOCK="/tmp/jellyflam3-breed-idle.lock"
  touch "$LOCK"
fi
exec 9>"$LOCK"
if ! flock -n 9; then
  log "SKIP another breed-idle run holds $LOCK"
  exit 0
fi

CMD=(python3 -m pipeline.breed_idle --config "$CFG" --json)
if [[ "$DRY_RUN" == "1" || "${BREED_IDLE_DRY_RUN:-0}" == "1" ]]; then
  CMD+=(--dry-run)
fi
if [[ "$EVALUATE" == "1" ]]; then
  CMD+=(--evaluate)
fi

log "RUN ${CMD[*]}"
cd "$ROOT"
OUT="$("${CMD[@]}")"
printf '%s\n' "$OUT"
ACTION="$(printf '%s\n' "$OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('action','?'))")"
log "DONE action=$ACTION"
