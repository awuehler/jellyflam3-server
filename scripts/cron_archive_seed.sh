#!/usr/bin/env bash

# Purpose: Cron wrapper to fill genomes_inbox from the Electric Sheep archive with backlog gating
#          (Phase 2 guide 01). Pairs with daily cron_breed_idle.sh for 24x7 furnace work.
# Pre-fill gate: skip/shrink fetch when inbox cannot drain before the next cron event
# (conservative wall-clock hours/sheep, Gold Sheep Lite + idle-gate pauses).
# Requirements: bash, python3, PyYAML, flock; pipeline.seed_inbox; writable inbox + lock.
#          flam3 is not required here (fetch + TV-port); worker render uses flam3 later.
#
# Usage:
#   ./scripts/cron_archive_seed.sh [--config PATH] [--fetch-count N] [--skip-catalog|--no-skip-catalog] [--dry-run]
#
# When to run: crontab as user jellyflam3. Lab fleet ~10-day staggered DOM (not exact */11).
# Success: log RUN … --skip-catalog … then DONE archive seed fetch_count=N (or SKIP backlog/no room).
# Default: --skip-catalog on (do not re-render catalog MP4s). --no-skip-catalog to overwrite.
# Docs: docs/phase2/01_ARCHIVE_SEED_LIBRARY.md
#
# Assumptions: Interval ≈ ARCHIVE_CRON_INTERVAL_DAYS (default 11) for the backlog math;
# lab hosts use ~10-day DOM lists (see crontab below). Config resolves inbox.
#
# ---------------------------------------------------------------------------
# Lab crontab (user jellyflam3), ~10 days (cron has no exact N-day step):
#   16a  27 7 7,17,27 * *   07:27 on days 7,17,27
#   08a  19 5 1,11,21 * *   05:19 on days 1,11,21
#   04a  17 3 3,13,23 * *   03:17 on days 3,13,23
#
#   17 3 3,13,23 * *  /opt/jellyflam3-server/scripts/cron_archive_seed.sh \
#       >>/var/log/jellyflam3/archive_seed.log 2>&1
#
# Script default ARCHIVE_CRON_INTERVAL_DAYS=11 is backlog math, not a DOM list.
#
# Ensure /var/log/jellyflam3 exists and is writable by the cron user, e.g.:
#   sudo mkdir -p /var/log/jellyflam3
#   sudo chown jellyflam3:jellyflam3 /var/log/jellyflam3
# ---------------------------------------------------------------------------
#
# Environment overrides (optional):
#   JELLYFLAM3_CONFIG              path to jellyflam3.yaml
#   ARCHIVE_CRON_INTERVAL_DAYS     days until next cron (default: 11) — backlog math only
#   ARCHIVE_EST_HOURS_PER_SHEEP    wall-clock hours/sheep incl. idle-gate (default: 12)
#   ARCHIVE_FETCH_COUNT            fixed N for this run (else seed_inbox 3–7 default)
#   ARCHIVE_SKIP_CATALOG=0         pass --no-skip-catalog (default is skip-catalog on)
#   ARCHIVE_DRY_RUN=1              print actions only
#   ARCHIVE_CRON_LOCK              flock path (default: /var/lock/jellyflam3-archive-seed.lock)

set -euo pipefail

# flam3 make install lands in /usr/local/bin; cron PATH is often just /usr/bin:/bin.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${JELLYFLAM3_CONFIG:-$ROOT/configs/jellyflam3.yaml}"
# Do not fall back to *.yaml.example — cron must use a real host config.

INTERVAL_DAYS="${ARCHIVE_CRON_INTERVAL_DAYS:-11}"
EST_HOURS_PER_SHEEP="${ARCHIVE_EST_HOURS_PER_SHEEP:-12}"
LOCK="${ARCHIVE_CRON_LOCK:-/var/lock/jellyflam3-archive-seed.lock}"

# UTC timestamped log line to stdout.
log() {
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

# Print file header (Purpose through env overrides) and exit.
usage() {
  sed -n '2,44p' "$0"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    --dry-run) ARCHIVE_DRY_RUN=1; shift ;;
    --config)
      CFG="$2"
      shift 2
      ;;
    --fetch-count)
      ARCHIVE_FETCH_COUNT="$2"
      shift 2
      ;;
    --skip-catalog)
      ARCHIVE_SKIP_CATALOG=1
      shift
      ;;
    --no-skip-catalog)
      ARCHIVE_SKIP_CATALOG=0
      shift
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

# Serialize overlapping cron/manual runs.
if ! touch "$LOCK" 2>/dev/null; then
  LOCK="/tmp/jellyflam3-archive-seed.lock"
  touch "$LOCK"
fi
exec 9>"$LOCK"
if ! flock -n 9; then
  log "SKIP another archive-seed run holds $LOCK"
  exit 0
fi

# Resolve inbox + count *.flam3 (same path rules as pipeline.config.resolve_path).
eval "$(
  ROOT="$ROOT" CFG="$CFG" python3 - <<'PY'
from pathlib import Path
import os
import yaml

root = Path(os.environ["ROOT"])
cfg_path = Path(os.environ["CFG"])
cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
inbox = Path((cfg.get("paths") or {}).get("genomes_inbox") or "genomes/inbox")
if not inbox.is_absolute():
    inbox = root / inbox
inbox.mkdir(parents=True, exist_ok=True)
n = sum(1 for p in inbox.iterdir() if p.suffix.lower() in {".flam3", ".flame"} and p.is_file())
# shell-safe exports
def sh(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"

print(f"INBOX={sh(str(inbox))}")
print(f"INBOX_COUNT={n}")
PY
)"

INTERVAL_HOURS=$((INTERVAL_DAYS * 24))
# Integer floor: how many sheep can finish before the next cron event.
MAX_CLEARABLE=$((INTERVAL_HOURS / EST_HOURS_PER_SHEEP))
if [[ "$MAX_CLEARABLE" -lt 1 ]]; then
  MAX_CLEARABLE=1
fi

log "inbox=$INBOX count=$INBOX_COUNT interval_days=$INTERVAL_DAYS est_h/sheep=$EST_HOURS_PER_SHEEP max_clearable=$MAX_CLEARABLE"

if [[ "$INBOX_COUNT" -ge "$MAX_CLEARABLE" ]]; then
  log "SKIP backlog too large ($INBOX_COUNT >= $MAX_CLEARABLE); cannot drain to zero before next cron"
  exit 0
fi

ROOM=$((MAX_CLEARABLE - INBOX_COUNT))

# Desired fetch size: explicit override, else leave to seed_inbox (3–7) but cap by ROOM.
DESIRED=""
if [[ -n "${ARCHIVE_FETCH_COUNT:-}" ]]; then
  DESIRED="$ARCHIVE_FETCH_COUNT"
else
  # Probe default without fetching: use seed_archive bounds midpoint capped by ROOM.
  DESIRED="$(
    CFG="$CFG" ROOM="$ROOM" python3 - <<'PY'
from pathlib import Path
import os
import random
import yaml

cfg = yaml.safe_load(Path(os.environ["CFG"]).read_text(encoding="utf-8")) or {}
ac = cfg.get("seed_archive") or {}
room = int(os.environ["ROOM"])
if ac.get("fetch_count") is not None:
    n = max(1, int(ac["fetch_count"]))
else:
    lo = int(ac.get("fetch_count_min", 3))
    hi = int(ac.get("fetch_count_max", 7))
    if hi < lo:
        lo, hi = hi, lo
    n = random.randint(lo, hi)
print(min(n, room))
PY
  )"
fi

if [[ "$DESIRED" -gt "$ROOM" ]]; then
  DESIRED="$ROOM"
fi

if [[ "$DESIRED" -lt 1 ]]; then
  log "SKIP no room to fetch (room=$ROOM)"
  exit 0
fi

CMD=(
  python3 -m pipeline.seed_inbox
  --config "$CFG"
  --archive
  --fetch-count "$DESIRED"
)
# Default skip-catalog on: do not re-render sheep that already have a catalog MP4.
# ARCHIVE_SKIP_CATALOG=0 or --no-skip-catalog opts out (overwrite / restage).
if [[ "${ARCHIVE_SKIP_CATALOG:-1}" == "0" ]]; then
  CMD+=(--no-skip-catalog)
else
  CMD+=(--skip-catalog)
fi
if [[ "${ARCHIVE_DRY_RUN:-0}" == "1" ]]; then
  CMD+=(--dry-run)
fi

log "RUN ${CMD[*]} (room=$ROOM)"
cd "$ROOT"
"${CMD[@]}"
log "DONE archive seed fetch_count=$DESIRED inbox_was=$INBOX_COUNT"
