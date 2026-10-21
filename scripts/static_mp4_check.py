#!/usr/bin/env python3

"""Purpose: Negative check that Static MP4 still plays when legacy HLS auth is rejected.

The Roku Video node cannot be driven from pytest. This checks the two URLs that
node would use. ``api_key`` on ``main.m3u8`` must be rejected. The same item's
``stream.mp4?Static=true`` must return an MP4 ``ftyp`` box.

Requirements: python3; secrets.env with JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_USER_ID.

Usage (on a furnace, from the repo root):
  python3 scripts/static_mp4_check.py
  STATIC_MP4_ITEM=<id> python3 scripts/static_mp4_check.py

When to run: After a Jellyfin upgrade, or when an HLS client falls back to Static MP4.
Success: prints ``STATIC_MP4_OK`` and exits 0.
Fail: Jellyfin accepts api_key on the playlist, or the Static MP4 response is not a playable MP4.
The item id and API key are not printed.
Docs: docs/phase2/03_HLS_CLIENT_STREAMING.md
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pipeline.config import load_dotenv  # noqa: E402

import jellyfin_id_dump as jfd  # noqa: E402


def legacy_hls_rejected(status: int) -> bool:
    """Jellyfin 12 rejects the legacy ``api_key`` query on the HLS playlist."""
    return status == 401


def static_mp4_playable(status: int, content_type: str, body: bytes) -> bool:
    """A Static MP4 response is playable when it is an MP4 file, not an error page."""
    if status not in (200, 206):
        return False
    if not (content_type or "").lower().startswith("video/mp4"):
        return False
    return b"ftyp" in body[:64]


def failure_reason(
    hls_status: int, mp4_status: int, content_type: str, body: bytes
) -> str:
    """Empty when both sides of the negative check pass."""
    if not legacy_hls_rejected(hls_status):
        return f"legacy HLS api_key returned {hls_status}, expected 401"
    if not static_mp4_playable(mp4_status, content_type, body):
        return (
            f"static MP4 returned {mp4_status} {content_type or 'unknown'} "
            f"({len(body)} bytes)"
        )
    return ""


def _fetch(url: str, headers: dict[str, str] | None = None) -> tuple[int, str, bytes]:
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.headers.get_content_type(), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, "", exc.read()


def _item_name(base: str, user_id: str, api_key: str, item_id: str) -> str:
    url = f"{base}/Users/{user_id}/Items/{item_id}"
    status, _ctype, body = _fetch(
        url, {"Authorization": f'MediaBrowser Token="{api_key}"'}
    )
    if status != 200:
        return ""
    import json

    try:
        return str(json.loads(body.decode("utf-8")).get("Name") or "")
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return ""


def main() -> int:
    load_dotenv(ROOT / "secrets.env")
    base = (os.environ.get("JELLYFIN_URL") or "").rstrip("/")
    api_key = (os.environ.get("JELLYFIN_API_KEY") or "").strip()
    user_id = (os.environ.get("JELLYFIN_USER_ID") or "").strip()
    if not base or not api_key or not user_id:
        print("JELLYFIN_URL, JELLYFIN_API_KEY, and JELLYFIN_USER_ID are required", file=sys.stderr)
        return 1

    item_id = (os.environ.get("STATIC_MP4_ITEM") or "").strip()
    if not item_id:
        item_id = jfd.resolve_smoke_item_id(ROOT / "configs" / "jellyflam3.yaml")
    if not item_id:
        print("no flock item found", file=sys.stderr)
        return 1

    name = _item_name(base, user_id, api_key, item_id)
    quoted = urllib.parse.quote(api_key, safe="")
    hls_url = (
        f"{base}/Videos/{item_id}/main.m3u8?MediaSourceId={item_id}"
        f"&api_key={quoted}&AudioCodec=aac"
    )
    mp4_url = f"{base}/Videos/{item_id}/stream.mp4?Static=true"
    hls_status, _hls_type, _hls_body = _fetch(hls_url)
    mp4_status, mp4_type, mp4_body = _fetch(mp4_url, {"Range": "bytes=0-63"})
    reason = failure_reason(hls_status, mp4_status, mp4_type, mp4_body)
    label = name or "catalog item"
    print(f"item {label}")
    print(f"legacy_hls {hls_status}")
    print(f"static_mp4 {mp4_status} {mp4_type or 'unknown'} {len(mp4_body)} bytes")
    if reason:
        print(reason, file=sys.stderr)
        return 1
    print("STATIC_MP4_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
