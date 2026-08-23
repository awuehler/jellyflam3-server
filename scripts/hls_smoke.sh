#!/usr/bin/env bash

# Purpose: Phase 2 guide 03 — PlaybackInfo + HLS remux smoke (pieces A–C).
# Requirements: bash, curl, python3, ffprobe (jellyfin-ffmpeg preferred); secrets.env.
#
# Usage: ./scripts/hls_smoke.sh  (on Pi; optional HLS_SMOKE_ITEM=… / JELLYFIN_PUBLIC_URL=…)
# Item pick: HLS_SMOKE_ITEM, else scripts/jellyfin_id_dump.py --smoke-item-id (folder-aware).
#
# When to run: After Jellyfin + flock ingest; Phase 3 RC regression (docs/phase3/10).
# Success: main.m3u8 reachable; AudioCodec=aac on the remux path (not a full transcode).
# Fail: missing secrets.env keys; 401; item not found; ffprobe missing.
# Docs: docs/phase2/03_HLS_AND_DIRECT_PLAY.md
#
# Assumptions: JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_USER_ID set; probes main.m3u8 + AudioCodec=aac.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# shellcheck disable=SC1091
set -a
[[ -f secrets.env ]] && . ./secrets.env
set +a

: "${JELLYFIN_URL:?set JELLYFIN_URL in secrets.env}"
: "${JELLYFIN_API_KEY:?set JELLYFIN_API_KEY}"
: "${JELLYFIN_USER_ID:?set JELLYFIN_USER_ID}"

BASE="${JELLYFIN_URL%/}"
AUTH="Authorization: MediaBrowser Token=${JELLYFIN_API_KEY}"
FFPROBE="${FFPROBE:-/usr/lib/jellyfin-ffmpeg/ffprobe}"
[[ -x "$FFPROBE" ]] || FFPROBE=ffprobe
TMP="${TMPDIR:-/tmp}/jellyflam3-hls-smoke.$$"
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

# Client-facing base (LAN/public). Keep BASE for on-box curl/ffprobe (often 127.0.0.1).
if [[ -n "${JELLYFIN_PUBLIC_URL:-}" ]]; then
  PUBLIC_BASE="${JELLYFIN_PUBLIC_URL%/}"
else
  LAN_HOST="${JELLYFIN_LAN_HOST:-}"
  if [[ -z "$LAN_HOST" ]]; then
    LAN_HOST="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}' || true)"
  fi
  if [[ -z "$LAN_HOST" ]]; then
    LAN_HOST="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  fi
  if [[ -z "$LAN_HOST" || "$LAN_HOST" == "127.0.0.1" ]]; then
    echo "WARN: could not detect LAN IP; set JELLYFIN_PUBLIC_URL or JELLYFIN_LAN_HOST" >&2
    LAN_HOST="127.0.0.1"
  fi
  PUBLIC_BASE="$(LAN_HOST="$LAN_HOST" python3 -c '
import os, urllib.parse
u = urllib.parse.urlparse(os.environ["JELLYFIN_URL"])
host = os.environ["LAN_HOST"]
scheme = u.scheme or "http"
netloc = f"{host}:{u.port}" if u.port else host
print(f"{scheme}://{netloc}")
')"
fi
echo "== public base for clients: $PUBLIC_BASE (API still uses $BASE) =="

ITEM_ID="${HLS_SMOKE_ITEM:-}"
if [[ -z "$ITEM_ID" ]]; then
  # Jellyfin 10.x: ParentId=library root often returns 0 videos; dump_items walks gen folders.
  ITEM_ID="$(python3 "$ROOT/scripts/jellyfin_id_dump.py" --smoke-item-id 2>/dev/null || true)"
fi
[[ -n "$ITEM_ID" ]] || {
  echo "No item id — flock empty or Jellyfin unreachable; set HLS_SMOKE_ITEM or fix secrets.env" >&2
  exit 1
}

echo "== item $ITEM_ID =="
curl -sS -H "$AUTH" "${BASE}/Users/${JELLYFIN_USER_ID}/Items/${ITEM_ID}" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("Name"), d.get("Path")); print("ImageTags", d.get("ImageTags"))'

echo "== PlaybackInfo =="
curl -sS -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"UserId\":\"${JELLYFIN_USER_ID}\"}" \
  "${BASE}/Items/${ITEM_ID}/PlaybackInfo?UserId=${JELLYFIN_USER_ID}" \
  >"$TMP/playbackinfo.json"
python3 - "$TMP/playbackinfo.json" <<'PY'
import json, sys
pi = json.load(open(sys.argv[1], encoding="utf-8"))
ms = (pi.get("MediaSources") or [None])[0] or {}
print(
    "SupportsDirectPlay", ms.get("SupportsDirectPlay"),
    "SupportsDirectStream", ms.get("SupportsDirectStream"),
    "Container", ms.get("Container"),
)
for s in ms.get("MediaStreams") or []:
    if s.get("Type") in ("Video", "Audio"):
        print(s.get("Type"), s.get("Codec"), s.get("Profile"), "level", s.get("Level"))
PY

# Prefer media playlist with explicit AAC (master.m3u8 may inject AudioCodec=m3u8 on JF 10.11).
HLS_PATH="/Videos/${ITEM_ID}/main.m3u8?MediaSourceId=${ITEM_ID}&api_key=${JELLYFIN_API_KEY}&AudioCodec=aac"
HLS="${BASE}${HLS_PATH}"
VLC_URL="${PUBLIC_BASE}${HLS_PATH}"
STATIC="${BASE}/Videos/${ITEM_ID}/stream.mp4?Static=true&api_key=${JELLYFIN_API_KEY}"

echo "== HLS media playlist =="
echo "VLC_URL=$VLC_URL"
code="$(curl -sS -o "$TMP/main.m3u8" -w "%{http_code}" "$HLS")"
echo "HTTP $code (probed via $BASE)"
head -12 "$TMP/main.m3u8"
[[ "$code" == "200" ]] || exit 2

echo "== ffprobe HLS (expect h264+aac, format hls) =="
"$FFPROBE" -v error \
  -show_entries stream=codec_name,profile,width,height \
  -show_entries format=format_name,duration \
  -of default=nw=1 "$HLS"

echo "== Static MP4 still available =="
curl -sS -o /dev/null -w "Static HEAD %{http_code}\n" -I "$STATIC" || true

echo "SMOKE_OK — open VLC_URL in VLC: Media → Open Network Stream"
echo "Remux note: with AudioCodec=aac, Jellyfin ffmpeg should use -codec:v copy -codec:a copy"
echo "(journalctl -u jellyfin -n 30 | grep ffmpeg)."
