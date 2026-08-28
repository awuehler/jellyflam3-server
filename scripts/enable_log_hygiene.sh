#!/usr/bin/env bash
# Purpose: Enable persistent journald + 72h logrotate hygiene on a furnace Pi.
# Requirements: root; repo at /opt/jellyflam3-server (or run from checkout).
#
# Usage:
#   sudo ./scripts/enable_log_hygiene.sh
#   sudo ./scripts/enable_log_hygiene.sh --check
#   sudo ./scripts/enable_log_hygiene.sh --class 04
#
# Policy:
#   - journald Storage=persistent; size cap 512M (16/08) or 200M (04); retain 23d
#   - logrotate every 72h (systemd timer); compress backups after 11d; purge after 23d
# Docs: docs/phase2/09_PI_FROM_SCRATCH.md

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHECK=0
CLASS=""

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

usage() {
  sed -n '2,20p' "$0"
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage ;;
    --check) CHECK=1; shift ;;
    --class)
      CLASS="$2"
      shift 2
      ;;
    *)
      log "ERROR unknown arg: $1"
      exit 2
      ;;
  esac
done

if [[ "$(id -u)" -ne 0 ]]; then
  log "ERROR must run as root (sudo)"
  exit 1
fi

detect_class() {
  local host
  host="$(hostname -s 2>/dev/null || hostname)"
  case "$host" in
    *jellyflam3-04*|*jellyflam3-4*|-04*|04a|04b) echo 04 ;;
    *jellyflam3-08*|*jellyflam3-8*|08a|08b) echo 08 ;;
    *jellyflam3-16*|16a|16b) echo 16 ;;
    *) echo 16 ;;
  esac
}

[[ -n "$CLASS" ]] || CLASS="$(detect_class)"

check_only() {
  echo "hostname=$(hostname -s) class=$CLASS"
  echo "--- journald ---"
  systemd-analyze cat-config systemd/journald.conf 2>/dev/null | grep -E '^(Storage|SystemMaxUse|MaxRetentionSec|RuntimeMaxUse)=' || true
  ls -la /etc/systemd/journald.conf.d/jellyflam3*.conf 2>/dev/null || echo "(no jellyflam3 journald drop-in)"
  journalctl --disk-usage 2>/dev/null || true
  echo "--- logrotate configs ---"
  ls -la /etc/jellyflam3/logrotate.d/ 2>/dev/null || echo "(missing)"
  ls /etc/logrotate.d/jellyflam3* 2>/dev/null && echo "WARN: legacy files in /etc/logrotate.d (remove)" || true
  echo "--- timer ---"
  systemctl is-enabled jellyflam3-logrotate.timer 2>/dev/null || echo "timer not enabled"
  systemctl list-timers jellyflam3-logrotate.timer --no-pager 2>/dev/null || true
  echo "--- log dirs ---"
  du -sh /var/log/jellyflam3 /var/log/jellyfin /var/log/journal 2>/dev/null || true
}

if [[ "$CHECK" -eq 1 ]]; then
  check_only
  exit 0
fi

log "enable log hygiene class=$CLASS root=$ROOT"

# --- journald ---
mkdir -p /var/log/journal /etc/systemd/journald.conf.d
if [[ "$CLASS" == "04" ]]; then
  install -m 0644 "$ROOT/deploy/journald/jellyflam3-persist-04.conf" \
    /etc/systemd/journald.conf.d/jellyflam3-persist.conf
  # Remove legacy vacuum-only name if present (merged into persist-04).
  rm -f /etc/systemd/journald.conf.d/jellyflam3-04.conf
else
  install -m 0644 "$ROOT/deploy/journald/jellyflam3-persist.conf" \
    /etc/systemd/journald.conf.d/jellyflam3-persist.conf
fi
systemctl restart systemd-journald
log "journald restarted; $(journalctl --disk-usage 2>/dev/null | tr '\n' ' ')"

# --- logrotate configs (dedicated dir — not distro daily /etc/logrotate.d) ---
mkdir -p /etc/jellyflam3/logrotate.d
install -m 0644 "$ROOT/deploy/logrotate/jellyflam3" /etc/jellyflam3/logrotate.d/jellyflam3
# Jellyfin uses dated files — age compress/purge only (no logrotate stanza).
rm -f /etc/jellyflam3/logrotate.d/jellyflam3-jellyfin
# Remove mistaken earlier installs that would rotate daily via distro timer.
rm -f /etc/logrotate.d/jellyflam3 /etc/logrotate.d/jellyflam3-jellyfin
mkdir -p /var/log/jellyflam3
if id jellyflam3 >/dev/null 2>&1; then
  chown jellyflam3:jellyflam3 /var/log/jellyflam3
fi

# --- 72h timer ---
install -m 0644 "$ROOT/deploy/systemd/jellyflam3-logrotate.service" /etc/systemd/system/
install -m 0644 "$ROOT/deploy/systemd/jellyflam3-logrotate.timer" /etc/systemd/system/
# Make hygiene scripts executable if checkout lost +x
chmod +x "$ROOT/scripts/log_hygiene.sh" "$ROOT/scripts/log_hygiene_age.sh" 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now jellyflam3-logrotate.timer
log "timer enabled: $(systemctl is-enabled jellyflam3-logrotate.timer)"

# One-shot dry path (age + rotate) so ops see immediate effect
if [[ -x "$ROOT/scripts/log_hygiene.sh" ]]; then
  log "RUN initial log_hygiene.sh"
  "$ROOT/scripts/log_hygiene.sh" || log "WARN initial hygiene rc=$?"
fi

log "DONE — re-check with: sudo $ROOT/scripts/enable_log_hygiene.sh --check"
