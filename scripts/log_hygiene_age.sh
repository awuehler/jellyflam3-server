#!/usr/bin/env bash
# Purpose: Age-based compress (≥11 days) and purge (≥23 days) for furnace file logs.
# Requirements: bash, gzip, find; readable log dirs.
#
# Usage:
#   ./scripts/log_hygiene_age.sh
#   COMPRESS_AFTER_DAYS=11 PURGE_AFTER_DAYS=23 ./scripts/log_hygiene_age.sh
#
# When to run: From jellyflam3-logrotate.service (every 72h) or manually after outages.
# Docs: docs/phase2/09_PI_FROM_SCRATCH.md (log hygiene)
#
# Policy:
#   - Rollover cadence is the 72h timer + logrotate (not this script).
#   - Compress rotated / dated backups older than 11 days (never the live *.log
#     truncate targets like tailscale_watch.log / archive_seed.log).
#   - Delete backups older than 23 days (gz or plain rotated).

set -euo pipefail

COMPRESS_AFTER_DAYS="${COMPRESS_AFTER_DAYS:-11}"
PURGE_AFTER_DAYS="${PURGE_AFTER_DAYS:-23}"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

compress_old() {
  local dir="$1"
  [[ -d "$dir" ]] || return 0
  # logrotate dateext: *.log-YYYYMMDD-HHMMSS
  find "$dir" -type f -name '*.log-*' ! -name '*.gz' \
    -mtime "+${COMPRESS_AFTER_DAYS}" -print0 2>/dev/null \
    | while IFS= read -r -d '' f; do
        log "gzip $f"
        gzip -f "$f" || true
      done
  # Jellyfin dated files: jellyfinYYYYMMDD.log (not the live truncate name)
  find "$dir" -type f -name 'jellyfin[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].log' \
    ! -name '*.gz' -mtime "+${COMPRESS_AFTER_DAYS}" -print0 2>/dev/null \
    | while IFS= read -r -d '' f; do
        log "gzip $f"
        gzip -f "$f" || true
      done
}

purge_old() {
  local dir="$1"
  [[ -d "$dir" ]] || return 0
  find "$dir" -type f \
    \( -name '*.gz' -o -name '*.log-*' -o -name 'jellyfin[0-9]*.log' \) \
    -mtime "+${PURGE_AFTER_DAYS}" \
    -print -delete 2>/dev/null || true
}

log "age hygiene compress>${COMPRESS_AFTER_DAYS}d purge>${PURGE_AFTER_DAYS}d"
for d in /var/log/jellyflam3 /var/lib/jellyflam3/logs /var/log/jellyfin; do
  compress_old "$d"
  purge_old "$d"
done

# Tailscale keeps its own ring buffer; only purge old rotated copies if present.
if [[ -d /var/lib/tailscale ]]; then
  find /var/lib/tailscale -maxdepth 1 -type f -name 'tailscaled.log*.txt.*' \
    -mtime "+${PURGE_AFTER_DAYS}" -print -delete 2>/dev/null || true
fi

log "age hygiene done"
