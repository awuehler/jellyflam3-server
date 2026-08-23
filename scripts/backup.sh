#!/usr/bin/env bash

# Purpose: Backup JellyFlam3 config, secrets, genomes, and Sheep library.
# Requirements: bash, sudo, tar; optional jellyflam3 user for chown.
#
# Usage:
#   ./scripts/backup.sh                      # full (sheep + genomes + config)
#   ./scripts/backup.sh /path/to/out.tar.gz
#   ./scripts/backup.sh --config-only
#
# When to run: Before disk rotate (Phase 4 guide 06), before OS upgrades, or before Shears/Hammer bulk deletes.
# Success: tar.gz under /var/lib/jellyflam3/backups/ (or OUT path); config-only is small.
# Fail: sudo/tar errors; full backup can fill the destination disk.
# Docs: docs/phase4/06_LIBRARY_DISK_ROTATE.md (when rotating); Phase 4 end-user guide will cite this.
#
# Assumptions: Default out under /var/lib/jellyflam3/backups/; full backup may be large.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CONFIG_ONLY=0
OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config-only) CONFIG_ONLY=1; shift ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      OUT="$1"
      shift
      ;;
  esac
done

if [[ -z "$OUT" ]]; then
  if [[ "$CONFIG_ONLY" -eq 1 ]]; then
    OUT="/var/lib/jellyflam3/backups/jellyflam3-config-$STAMP.tar.gz"
  else
    OUT="/var/lib/jellyflam3/backups/jellyflam3-$STAMP.tar.gz"
  fi
fi

sudo mkdir -p "$(dirname "$OUT")"

TMP="$(mktemp -d /tmp/jellyflam3-backup.XXXXXX)"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT

mkdir -p "$TMP/bundle"
if [[ -f "$ROOT/configs/jellyflam3.yaml" ]]; then
  cp -a "$ROOT/configs/jellyflam3.yaml" "$TMP/bundle/"
fi
if [[ -f "$ROOT/secrets.env" ]]; then
  cp -a "$ROOT/secrets.env" "$TMP/bundle/"
fi

if [[ "$CONFIG_ONLY" -eq 1 ]]; then
  sudo tar -czf "$OUT" -C "$TMP/bundle" .
else
  # Full: config/secrets + genomes + sheep flock (may be large)
  INCLUDE_SHEEP=0
  INCLUDE_GENOMES=0
  [[ -d /media/sheep ]] && INCLUDE_SHEEP=1
  [[ -d /var/lib/jellyflam3/genomes ]] && INCLUDE_GENOMES=1
  ARGS=( -czf "$OUT" -C "$TMP/bundle" . )
  if [[ "$INCLUDE_GENOMES" -eq 1 ]]; then
    ARGS+=( -C / var/lib/jellyflam3/genomes )
  fi
  if [[ "$INCLUDE_SHEEP" -eq 1 ]]; then
    ARGS+=( -C / media/sheep )
  fi
  sudo tar "${ARGS[@]}"
fi

sudo chown jellyflam3:jellyflam3 "$OUT" 2>/dev/null || true
echo "Wrote $OUT"
sudo ls -lh "$OUT"
