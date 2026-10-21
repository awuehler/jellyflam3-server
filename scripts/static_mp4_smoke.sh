#!/usr/bin/env bash

# Purpose: Negative check that Static MP4 still plays when legacy HLS auth is rejected.
# Requirements: python3; secrets.env with JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_USER_ID.
#
# Usage: ./scripts/static_mp4_smoke.sh
#   Optional STATIC_MP4_ITEM selects one catalog item. Otherwise the HLS smoke pick is used.
#
# When to run: After a Jellyfin upgrade, or when an HLS client falls back to Static MP4.
# Success: legacy api_key on main.m3u8 returns 401, and stream.mp4?Static=true returns an ftyp box.
# Fail: Jellyfin accepts api_key on the playlist, or the Static MP4 response is not a playable MP4.
# Docs: docs/phase2/03_HLS_CLIENT_STREAMING.md
#
# This does not drive a Roku. It checks the URL the channel's HLS-to-MP4 fallback would open.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 "$ROOT/scripts/static_mp4_check.py"
