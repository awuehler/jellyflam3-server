#!/usr/bin/env bash
# Purpose: 72h log rollover entrypoint — logrotate then age compress/purge.
# Requirements: root (or sudo); logrotate; scripts/log_hygiene_age.sh.
#
# Usage:
#   sudo ./scripts/log_hygiene.sh
#   sudo /opt/jellyflam3-server/scripts/log_hygiene.sh
#
# When to run: jellyflam3-logrotate.timer (OnUnitActiveSec=72h).
# Docs: docs/phase2/09_PI_FROM_SCRATCH.md
#
# Configs live under /etc/jellyflam3/logrotate.d/ (not /etc/logrotate.d/) so the
# distro daily logrotate.timer does not rotate these every day.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="/usr/sbin:/usr/bin:/bin:${PATH:-}"
CONF_DIR="${JELLYFLAM3_LOGROTATE_DIR:-/etc/jellyflam3/logrotate.d}"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

if [[ "$(id -u)" -ne 0 ]]; then
  log "ERROR must run as root (sudo)"
  exit 1
fi

mkdir -p /var/log/jellyflam3
if id jellyflam3 >/dev/null 2>&1; then
  chown jellyflam3:jellyflam3 /var/log/jellyflam3 || true
fi

CFGS=()
shopt -s nullglob
for f in "$CONF_DIR"/*; do
  [[ -f "$f" ]] && CFGS+=("$f")
done
shopt -u nullglob

if [[ ${#CFGS[@]} -eq 0 ]]; then
  log "WARN no configs in $CONF_DIR — age hygiene only"
else
  log "RUN logrotate ${CFGS[*]}"
  # Configs omit daily/weekly/size → rotate on each 72h invocation.
  /usr/sbin/logrotate "${CFGS[@]}"
fi

AGE="$ROOT/scripts/log_hygiene_age.sh"
if [[ -x "$AGE" ]]; then
  log "RUN $AGE"
  "$AGE"
else
  log "WARN missing $AGE"
fi

log "DONE log hygiene"
