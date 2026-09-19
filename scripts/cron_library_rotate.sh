#!/usr/bin/env bash

# Purpose: Periodic cron — retire oldest catalog sheep via Shears cascade when
#          the sheep mount is WARN/BAD (Phase 4 / 06). Not Hammer.
# Requirements: bash, python3, flock; pipeline.library_disk rotate.
#
# Usage:
#   ./scripts/cron_library_rotate.sh [--config PATH] [--dry-run]
#   python3 -m pipeline.library_disk rotate --config configs/jellyflam3.yaml
#   python3 -m pipeline.library_disk rotate --apply
#
# When to run: optional daily valve. Lab 16a / 08a / 04a do **not** install this
# crontab while sheep disks are far below WARN. Enable with the recipe in
# docs/phase4/06_LIBRARY_DISK_ROTATE.md#activate-daily-rotate (and USER_GUIDE
# Activate library rotate). Manual: rotate [--apply]. Archive seed still rotates
# before fetch (existing ~10-day cron), independent of this line.
# Success: JSON action=rotate|plan|skip (disabled, under_threshold, floor, …).
# Fail: missing config → exit 1. Kill-switch library_disk.rotate_enabled.
# Docs: docs/phase4/06_LIBRARY_DISK_ROTATE.md
#
# Assumptions: Oldest catalog MP4 mtime first. Floor ≥ 1. Git samples/pedigree
# kept. Worker refuse on sheep BAD is separate (library_disk.worker_refuse_on_sheep_bad).
#
# ---------------------------------------------------------------------------
# Example crontab (user jellyflam3) — **NOT installed** on 16a / 08a / 04a.
# Suggested slot 05:23 local, after 05:11 idle-breed. How-to:
# docs/phase4/06_LIBRARY_DISK_ROTATE.md#activate-daily-rotate
#
#   23 5 * * *  /opt/jellyflam3-server/scripts/cron_library_rotate.sh \
#       >>/var/log/jellyflam3/library_rotate.log 2>&1
#
# Idle breed remains (already installed):
#   11 5 * * *  /opt/jellyflam3-server/scripts/cron_breed_idle.sh \
#       >>/var/log/jellyflam3/breed_idle.log 2>&1
#
# Ensure /var/log/jellyflam3 exists and is writable by the cron user.
# ---------------------------------------------------------------------------
#
# Environment overrides (optional):
#   JELLYFLAM3_CONFIG               path to jellyflam3.yaml
#   LIBRARY_ROTATE_DRY_RUN=1        plan only (no Shears deletes)
#   LIBRARY_ROTATE_CRON_LOCK        flock path (default: /var/lock/jellyflam3-library-rotate.lock)

set -euo pipefail

export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${JELLYFLAM3_CONFIG:-$ROOT/configs/jellyflam3.yaml}"
LOCK="${LIBRARY_ROTATE_CRON_LOCK:-/var/lock/jellyflam3-library-rotate.lock}"
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
  LOCK="/tmp/jellyflam3-library-rotate.lock"
  touch "$LOCK"
fi
exec 9>"$LOCK"
if ! flock -n 9; then
  log "SKIP another library-rotate run holds $LOCK"
  exit 0
fi

CMD=(python3 -m pipeline.library_disk rotate --config "$CFG")
if [[ "$DRY_RUN" == "1" || "${LIBRARY_ROTATE_DRY_RUN:-0}" == "1" ]]; then
  :
else
  CMD+=(--apply)
fi

log "RUN ${CMD[*]}"
cd "$ROOT"
OUT="$("${CMD[@]}")"
printf '%s\n' "$OUT"
ACTION="$(printf '%s\n' "$OUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('action','?'))")"
log "DONE action=$ACTION"
