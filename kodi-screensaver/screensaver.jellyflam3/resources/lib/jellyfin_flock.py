"""Jellyfin flock client for screensaver.jellyflam3 (Phase 3 guide 02).

Mirrors Roku ``JellyfinTask.brs`` list + Static MP4 URLs. Stdlib only (urllib)
so it runs under Kodi's embedded Python without extra add-ons.

Idle-gate: use Client=JellyFlam3-Screensaver so furnace ``ignore_client_patterns``
keeps the gate open (image/video screensaver must not freeze renders).
"""

from __future__ import annotations

import json
import random
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Must match configs idle_gate.ignore_client_patterns / Roku screensaver intent.
CLIENT_NAME = "JellyFlam3-Screensaver"
CLIENT_DEVICE = "Kodi"
CLIENT_DEVICE_ID = "jellyflam3-kodi-ss"
CLIENT_VERSION = "0.2.6"


def trim_slash(url: str) -> str:
    return (url or "").strip().rstrip("/")


def auth_header(api_key: str) -> str:
    return (
        'MediaBrowser Client="%s", Device="%s", DeviceId="%s", Version="%s", Token="%s"'
        % (CLIENT_NAME, CLIENT_DEVICE, CLIENT_DEVICE_ID, CLIENT_VERSION, api_key)
    )


def mp4_stream_url(base: str, item_id: str, api_key: str) -> str:
    base = trim_slash(base)
    return (
        "%s/Videos/%s/stream.mp4?Static=true&api_key=%s"
        % (base, item_id, urllib.parse.quote(api_key, safe=""))
    )


def is_commercial_safe(tags: list[str] | None) -> bool:
    """Roku BrightScript contract: require a safe tag; reject by-nc family."""
    if not tags:
        return False
    saw_safe = False
    for t in tags:
        tl = (t or "").lower().replace("_", "-").strip()
        if tl in ("cc-by-nc", "cc-by-nc-sa") or "by-nc" in tl:
            return False
        if tl in ("cc-by", "cc0", "public-domain", "pd", "cc-by-sa"):
            saw_safe = True
    return saw_safe


def filter_commercial(items: list[dict[str, Any]], commercial_mode: bool) -> list[dict[str, Any]]:
    if not commercial_mode:
        return list(items)
    return [it for it in items if is_commercial_safe(it.get("Tags") or it.get("tags"))]


def http_get_json(url: str, api_key: str, timeout: float = 20.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": auth_header(api_key),
            "X-Emby-Authorization": auth_header(api_key),
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    return json.loads(body) if body else {}


def fetch_flock(
    *,
    base_url: str,
    api_key: str,
    user_id: str,
    library_id: str = "",
    commercial_mode: bool = False,
    limit: int = 200,
    timeout: float = 20.0,
) -> list[dict[str, str]]:
    """Return playable sheep dicts: id, title, url (Static MP4)."""
    base = trim_slash(base_url)
    if not base or not api_key or not user_id:
        raise ValueError("server_url, api_key, and user_id are required")

    q: dict[str, str] = {
        "IncludeItemTypes": "Movie,Video",
        "Recursive": "true",
        "Fields": "Overview,Tags,RunTimeTicks,Path,Name",
        "Limit": str(int(limit)),
    }
    if library_id:
        q["ParentId"] = library_id
    # Do NOT pass Tags= to Jellyfin — comma lists are treated as AND / unknown and
    # return an empty flock (lab: Tags=cc-by,public-domain,cc0 → 0 items while
    # four Items carry Tags=["cc-by", …]). Commercial filtering is client-side only.

    url = "%s/Users/%s/Items?%s" % (base, user_id, urllib.parse.urlencode(q))
    try:
        data = http_get_json(url, api_key, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("Items HTTP %s" % exc.code) from exc
    except Exception as exc:
        raise RuntimeError("Items failed: %s" % exc) from exc

    raw = data.get("Items") or []
    # Jellyfin 10.x: ParentId=library + Movie/Video&Recursive often returns a *partial*
    # flock when videos live under by-generation/ children. Always walk child folders
    # when library_id is set (empty-only fallback misses the lab "1 of N" case).
    if library_id:
        fq = {
            "IncludeItemTypes": "Folder",
            "Recursive": "false",
            "ParentId": library_id,
            "Limit": "50",
        }
        folders_url = "%s/Users/%s/Items?%s" % (base, user_id, urllib.parse.urlencode(fq))
        try:
            folders_data = http_get_json(folders_url, api_key, timeout=timeout)
        except RuntimeError:
            folders_data = {}
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for folder in folders_data.get("Items") or []:
            fid = folder.get("Id") or ""
            if not fid:
                continue
            remain = max(1, int(limit) - len(merged))
            cq = dict(q)
            cq["ParentId"] = fid
            cq["Limit"] = str(remain)
            child_url = "%s/Users/%s/Items?%s" % (base, user_id, urllib.parse.urlencode(cq))
            try:
                child_data = http_get_json(child_url, api_key, timeout=timeout)
            except RuntimeError:
                child_data = {}
            for it in child_data.get("Items") or []:
                iid = it.get("Id") or ""
                if not iid or iid in seen:
                    continue
                seen.add(iid)
                merged.append(it)
                if len(merged) >= int(limit):
                    break
            if len(merged) >= int(limit):
                break
        for it in raw:
            if len(merged) >= int(limit):
                break
            iid = it.get("Id") or ""
            if not iid or iid in seen:
                continue
            seen.add(iid)
            merged.append(it)
        raw = merged
    raw = filter_commercial(raw, commercial_mode)
    out: list[dict[str, str]] = []
    for it in raw:
        item_id = it.get("Id") or ""
        if not item_id:
            continue
        title = it.get("Name") or item_id
        out.append(
            {
                "id": item_id,
                "title": title,
                "url": mp4_stream_url(base, item_id, api_key),
            }
        )
    return out


def shuffle_copy(items: list[dict[str, str]], rng: random.Random | None = None) -> list[dict[str, str]]:
    bag = list(items)
    (rng or random).shuffle(bag)
    return bag
