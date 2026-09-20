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
CLIENT_VERSION = "0.2.13"
VOTE_REMAIN_SEC = 7.0
VOTE_SINK_PORT = 8791
VOTE_HINT = "OK love · RIGHT like · DOWN dismiss · UP/BACK exit"
FLOCK_REPOLL_MIN_SEC = 30.0
# In-memory session list after a random prune. HTTP fetch is larger so the
# sample is not Jellyfin's first-N sort.
FLOCK_INDEX_CAP = 313
FLOCK_FETCH_LIMIT = 5000


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


def classify_fetch_error(exc: BaseException) -> str:
    """Map a fetch failure to ``auth`` or ``unreachable`` (not empty flock)."""
    if isinstance(exc, urllib.error.HTTPError) and int(getattr(exc, "code", 0) or 0) in (401, 403):
        return "auth"
    return "unreachable"


def probe_jellyfin(base_url: str, timeout: float = 8.0) -> bool:
    """True when Jellyfin ``/System/Info/Public`` answers (no API key)."""
    url = trim_slash(base_url) + "/System/Info/Public"
    if not trim_slash(base_url):
        return False
    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode() or 0)
            return 200 <= code < 300
    except Exception:
        return False


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


def overview_keyed_value(overview: str, key: str) -> str:
    """First line value after ``Alias:`` / ``License:`` in Jellyfin Overview."""
    ov = overview or ""
    needle = key or ""
    if not ov or not needle:
        return ""
    idx = ov.find(needle)
    if idx < 0:
        idx = ov.lower().find(needle.lower())
    if idx < 0:
        return ""
    frag = ov[idx + len(needle) :].strip()
    nl = frag.find("\n")
    if nl >= 0:
        frag = frag[:nl]
    return frag.strip()


def item_alias(item: dict[str, Any]) -> str:
    return overview_keyed_value(str(item.get("Overview") or ""), "Alias:")


def stem_from_media_path(media_path: str) -> str:
    """Basename without ``.mp4`` (same contract as furnace ``sheep_votes``)."""
    raw = (media_path or "").replace("\\", "/").strip()
    name = raw.rstrip("/").split("/")[-1] if raw else ""
    lower = name.lower()
    if lower.endswith(".mp4"):
        name = name[:-4]
    return name


def is_tuple_sheep(path: str = "", stem: str = "") -> bool:
    blob = ((path or "") + " " + (stem or "")).replace("\\", "/").lower()
    if "/tuple/" in blob:
        return True
    st = (stem or "").lower()
    return ".tuple." in st or st.startswith("electricsheep.tuple.")


def sink_url_from_jellyfin(base_url: str, port: int = VOTE_SINK_PORT) -> str:
    """Roku VoD default: ``http://{jellyfin-host}:8791`` (sink is always HTTP)."""
    raw = (base_url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urllib.parse.urlparse(raw)
    host = parsed.hostname or ""
    if not host:
        return ""
    return "http://%s:%s" % (host, int(port))


def vote_overlay_due(
    remain_sec: float | None,
    *,
    dismissed: bool,
    is_tuple: bool,
    threshold: float = VOTE_REMAIN_SEC,
) -> bool:
    if dismissed or is_tuple:
        return False
    if remain_sec is None:
        return False
    try:
        remain = float(remain_sec)
    except (TypeError, ValueError):
        return False
    return 0.0 < remain <= float(threshold)


def post_sheep_vote(
    sink_url: str,
    token: str,
    payload: dict[str, Any],
    timeout: float = 8.0,
) -> dict[str, Any]:
    """POST ``/v1/sheep-votes`` (same sink as Roku VoD)."""
    base = trim_slash(sink_url)
    if not base:
        return {"ok": False, "error": "display_sink_url not set"}
    tok = (token or "").strip()
    if not tok:
        return {"ok": False, "error": "display_sink_token not set"}
    url = base + "/v1/sheep-votes"
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-JellyFlam3-Token": tok,
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = int(getattr(resp, "status", None) or resp.getcode() or 0)
    except urllib.error.HTTPError as exc:
        err_body = ""
        try:
            err_body = exc.read().decode("utf-8", errors="replace")[:120]
        except Exception:
            pass
        return {"ok": False, "error": "HTTP %s %s" % (exc.code, err_body)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    parsed: Any = {}
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw": raw}
    if not isinstance(parsed, dict):
        parsed = {"raw": parsed}
    parsed["ok"] = 200 <= code < 300
    return parsed


def display_title(filename: str, alias: str, title_mode: str) -> str:
    """filename (default) vs alias; missing alias falls back to filename."""
    mode = (title_mode or "filename").strip().lower()
    alias_s = (alias or "").strip()
    name_s = (filename or "").strip()
    if mode == "alias" and alias_s:
        return alias_s
    return name_s or alias_s


def fetch_flock(
    *,
    base_url: str,
    api_key: str,
    user_id: str,
    library_id: str = "",
    commercial_mode: bool = False,
    limit: int = FLOCK_INDEX_CAP,
    fetch_limit: int | None = None,
    timeout: float = 20.0,
) -> list[dict[str, str]]:
    """Return playable sheep dicts: id, title, url (Static MP4).

    ``fetch_limit`` is the Jellyfin Items cap (default 5000). After merge and
    commercial filter, randomly prune to ``limit`` (default 313).
    """
    base = trim_slash(base_url)
    if not base or not api_key or not user_id:
        raise ValueError("server_url, api_key, and user_id are required")
    http_limit = int(fetch_limit if fetch_limit is not None else FLOCK_FETCH_LIMIT)
    if http_limit < 1:
        http_limit = FLOCK_FETCH_LIMIT

    q: dict[str, str] = {
        "IncludeItemTypes": "Movie,Video",
        "Recursive": "true",
        "Fields": "Overview,Tags,RunTimeTicks,Path,Name",
        "Limit": str(http_limit),
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
            remain = max(1, http_limit - len(merged))
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
                if len(merged) >= http_limit:
                    break
            if len(merged) >= http_limit:
                break
        for it in raw:
            if len(merged) >= http_limit:
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
        path = str(it.get("Path") or "")
        stem = stem_from_media_path(path) or stem_from_media_path(str(title))
        ticks = it.get("RunTimeTicks")
        duration_sec = ""
        try:
            if ticks is not None:
                duration_sec = str(float(ticks) / 10_000_000.0)
        except (TypeError, ValueError):
            duration_sec = ""
        out.append(
            {
                "id": item_id,
                "title": title,
                "alias": item_alias(it),
                "url": mp4_stream_url(base, item_id, api_key),
                "path": path,
                "stem": stem,
                "duration_sec": duration_sec,
            }
        )
    return prune_to_cap(out, int(limit))


def prune_to_cap(
    items: list[dict[str, str]],
    cap: int = FLOCK_INDEX_CAP,
    rng: random.Random | None = None,
) -> list[dict[str, str]]:
    """Random sample down to ``cap`` when Jellyfin returned a larger flock."""
    bag = list(items)
    n = max(0, int(cap))
    if n <= 0 or len(bag) <= n:
        return bag
    (rng or random).shuffle(bag)
    return bag[:n]


def shuffle_copy(items: list[dict[str, str]], rng: random.Random | None = None) -> list[dict[str, str]]:
    bag = list(items)
    (rng or random).shuffle(bag)
    return bag


def rotate_past(items: list[dict[str, str]], item_id: str) -> list[dict[str, str]]:
    """Keep a full permutation; rotate so the last-played id is not first.

    Avoids a wrap-seam repeat without dropping the sheep from the new round.
    """
    bag = list(items)
    last = (item_id or "").strip()
    if not last or len(bag) < 2:
        return bag
    for _ in range(len(bag)):
        if (bag[0].get("id") or "") != last:
            return bag
        bag.append(bag.pop(0))
    return bag


def drop_item(items: list[dict[str, str]], item_id: str) -> list[dict[str, str]]:
    """Remove a Jellyfin id from an in-memory flock (quarantine / 404)."""
    dead = (item_id or "").strip()
    if not dead:
        return list(items)
    return [it for it in items if (it.get("id") or "") != dead]


def should_repoll_flock(
    last_monotonic: float | None,
    now: float,
    min_sec: float = FLOCK_REPOLL_MIN_SEC,
) -> bool:
    """Rate-limit mid-session Jellyfin re-fetch so a shrinking library cannot hammer the Pi."""
    if last_monotonic is None:
        return True
    return (now - last_monotonic) >= float(min_sec)
