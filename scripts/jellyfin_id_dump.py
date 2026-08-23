#!/usr/bin/env python3

"""
Purpose: Dump Jellyfin users, libraries, and item IDs for JellyFlam3 Roku Settings.

Phase 3 ops helper — fills channel registry keys (baseUrl, apiKey, userId,
libraryId) and lists VoD item Guids for deep-link / shuffle smoke.

Requirements: python3, pipeline.config, secrets.env or config jellyfin.*
  (JELLYFIN_URL, JELLYFIN_API_KEY; optional USER_ID / LIBRARY_ID / PUBLIC_URL).

Usage: (on Pi or any host with secrets.env)
  cd /opt/jellyflam3-server   # or repo root
  python3 scripts/jellyfin_id_dump.py
  python3 scripts/jellyfin_id_dump.py --items --limit 50
  python3 scripts/jellyfin_id_dump.py --json > /tmp/jellyfin_ids.json

When to run: After Jellyfin library scan; when pasting Settings into the Roku channel
  (Phase 3 guide 08). Not a furnace cron.

Success: Prints users / libraries / IDs. --json for copy-paste. Does not mutate Jellyfin.

Assumptions: Jellyfin reachable at configured URL; apiKey has Users/Items access.
Docs: docs/phase3/08_JELLYFIN_ID_DUMP.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import load_config, load_dotenv  # noqa: E402


def _get(url: str, api_key: str) -> Any:
    """GET JSON from Jellyfin with MediaBrowser Token auth; raise on HTTP errors."""
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f'MediaBrowser Token="{api_key}"',
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET {url} → {e.code}: {detail}") from e


def _mask(secret: str, *, show: bool) -> str:
    """Return secret as-is when show, else a short masked preview."""
    if show or not secret:
        return secret
    if len(secret) <= 8:
        return "***"
    return secret[:2] + "..." + secret[-4:] + f" ({len(secret)} chars)"


def _generation_from_item(it: dict[str, Any]) -> str:
    """Best-effort generation id from Tags, by-generation path, or electricsheep name."""
    for t in it.get("Tags") or []:
        tl = str(t).lower()
        if tl.startswith("generation-"):
            return str(t)[len("generation-") :]
    path = (it.get("Path") or "").replace("\\", "/")
    marker = "/by-generation/"
    idx = path.lower().find(marker)
    if idx >= 0:
        rest = path[idx + len(marker) :]
        gen = rest.split("/", 1)[0]
        if gen:
            return gen
    name = it.get("Name") or ""
    # electricsheep.{gen}.{id}…
    parts = name.replace("__", ".").split(".")
    for i, p in enumerate(parts):
        if p.lower() == "electricsheep" and i + 1 < len(parts) and parts[i + 1].isdigit():
            return parts[i + 1]
    return ""


def resolve_creds(cfg_path: Path) -> dict[str, str]:
    """Load URL/api_key/user/library from env + config; exit if URL or key missing."""
    load_dotenv(ROOT / "secrets.env")
    cfg: dict[str, Any] = {}
    if cfg_path.is_file():
        cfg = load_config(cfg_path, repo_root=ROOT)
    jf = cfg.get("jellyfin") or {}
    url = (os.environ.get("JELLYFIN_URL") or jf.get("url") or "").rstrip("/")
    api_key = os.environ.get("JELLYFIN_API_KEY") or jf.get("api_key") or ""
    user_id = os.environ.get("JELLYFIN_USER_ID") or jf.get("user_id") or ""
    library_id = os.environ.get("JELLYFIN_LIBRARY_ID") or jf.get("library_id") or ""
    public = (os.environ.get("JELLYFIN_PUBLIC_URL") or "").rstrip("/")
    if not url or not api_key:
        raise SystemExit(
            "Need JELLYFIN_URL and JELLYFIN_API_KEY (secrets.env or config jellyfin.*)"
        )
    return {
        "url": url,
        "api_key": api_key,
        "user_id": user_id,
        "library_id": library_id,
        "public_url": public or url,
    }


def dump_users(base: str, api_key: str) -> list[dict[str, Any]]:
    """List Jellyfin users as {id, name, isAdmin, isDisabled}."""
    data = _get(f"{base}/Users", api_key)
    if not isinstance(data, list):
        return []
    out = []
    for u in data:
        out.append(
            {
                "id": u.get("Id") or "",
                "name": u.get("Name") or "",
                "isAdmin": bool((u.get("Policy") or {}).get("IsAdministrator")),
                "isDisabled": bool((u.get("Policy") or {}).get("IsDisabled")),
            }
        )
    return out


def dump_views(base: str, api_key: str, user_id: str) -> list[dict[str, Any]]:
    """User library views (ParentId candidates); empty if user_id unset."""
    if not user_id:
        return []
    data = _get(f"{base}/Users/{user_id}/Views", api_key) or {}
    items = data.get("Items") or []
    out = []
    for it in items:
        out.append(
            {
                "id": it.get("Id") or "",
                "name": it.get("Name") or "",
                "collectionType": it.get("CollectionType") or "",
                "path": it.get("Path") or "",
            }
        )
    return out


def dump_media_folders(base: str, api_key: str) -> list[dict[str, Any]]:
    """Virtual folders (library roots) — good ParentId candidates."""
    try:
        data = _get(f"{base}/Library/VirtualFolders", api_key)
    except RuntimeError:
        return []
    if not isinstance(data, list):
        return []
    out = []
    for vf in data:
        locs = vf.get("Locations") or []
        out.append(
            {
                "id": vf.get("ItemId") or vf.get("Guid") or "",
                "name": vf.get("Name") or "",
                "collectionType": vf.get("CollectionType") or "",
                "locations": locs,
            }
        )
    return out


def dump_items(
    base: str,
    api_key: str,
    user_id: str,
    *,
    library_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    """List Movie/Video items under library_id (optional ParentId), capped by limit."""
    if not user_id:
        return []
    q = {
        "IncludeItemTypes": "Movie,Video",
        "Recursive": "true",
        "Fields": "Path,Tags,RunTimeTicks,ImageTags",
        "Limit": str(max(1, limit)),
        "SortBy": "SortName",
        "SortOrder": "Ascending",
    }
    if library_id:
        q["ParentId"] = library_id
    url = f"{base}/Users/{user_id}/Items?{urllib.parse.urlencode(q)}"
    data = _get(url, api_key) or {}
    items = list(data.get("Items") or [])
    # Jellyfin 10.x: ParentId=library root + IncludeItemTypes=Video often returns a
    # *partial* flock when videos live under by-generation/ children. Always walk
    # child folders when library_id is set (empty-only fallback misses "1 of N").
    if library_id:
        fq = {
            "IncludeItemTypes": "Folder",
            "Recursive": "false",
            "ParentId": library_id,
            "Limit": "50",
        }
        folders_url = f"{base}/Users/{user_id}/Items?{urllib.parse.urlencode(fq)}"
        folders = (_get(folders_url, api_key) or {}).get("Items") or []
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for folder in folders:
            fid = folder.get("Id") or ""
            if not fid:
                continue
            remain = max(1, limit - len(merged))
            cq = dict(q)
            cq["ParentId"] = fid
            cq["Limit"] = str(remain)
            child_url = f"{base}/Users/{user_id}/Items?{urllib.parse.urlencode(cq)}"
            batch = (_get(child_url, api_key) or {}).get("Items") or []
            for it in batch:
                iid = it.get("Id") or ""
                if not iid or iid in seen:
                    continue
                seen.add(iid)
                merged.append(it)
                if len(merged) >= limit:
                    break
            if len(merged) >= limit:
                break
        for it in items:
            if len(merged) >= limit:
                break
            iid = it.get("Id") or ""
            if not iid or iid in seen:
                continue
            seen.add(iid)
            merged.append(it)
        items = merged
    out = []
    for it in items:
        ticks = it.get("RunTimeTicks") or 0
        length_sec = int(ticks / 10_000_000) if ticks else 0
        tags = it.get("ImageTags") or {}
        out.append(
            {
                "id": it.get("Id") or "",
                "name": it.get("Name") or "",
                "path": it.get("Path") or "",
                "generation": _generation_from_item(it),
                "lengthSec": length_sec,
                "hasPrimary": bool(tags.get("Primary")),
                "tags": list(it.get("Tags") or []),
            }
        )
    return out


def resolve_smoke_item_id(cfg_path: Path | None = None) -> str:
    """First Movie/Video item id for ``hls_smoke.sh`` (folder-aware library query)."""
    path = cfg_path or (ROOT / "configs" / "jellyflam3.yaml")
    creds = resolve_creds(path)
    items = dump_items(
        creds["url"],
        creds["api_key"],
        creds["user_id"],
        library_id=creds["library_id"],
        limit=1,
    )
    return items[0]["id"] if items else ""


def build_report(
    creds: dict[str, str],
    *,
    include_items: bool,
    limit: int,
    show_secrets: bool,
) -> dict[str, Any]:
    """Assemble users/views/folders/(items) plus masked rokuSettings registry keys."""
    base = creds["url"]
    key = creds["api_key"]
    users = dump_users(base, key)
    uid = creds["user_id"]
    if not uid and users:
        # Prefer first non-disabled user
        for u in users:
            if not u["isDisabled"]:
                uid = u["id"]
                break
        if not uid:
            uid = users[0]["id"]

    views = dump_views(base, key, uid)
    folders = dump_media_folders(base, key)
    lib = creds["library_id"]
    if not lib:
        for v in views:
            name = (v.get("name") or "").lower()
            if "sheep" in name or "flam" in name:
                lib = v["id"]
                break
        if not lib and views:
            lib = views[0]["id"]

    items: list[dict[str, Any]] = []
    if include_items:
        items = dump_items(base, key, uid, library_id=lib, limit=limit)

    roku_keys = {
        "baseUrl": creds["public_url"],
        "apiKey": _mask(key, show=show_secrets),
        "userId": uid,
        "libraryId": lib,
        "commercialMode": "false",
        "streamMode": "mp4",
        "shuffleFlock": "false",
    }

    notes = [
        "Paste rokuSettings values into JellyFlam3 Settings (Roku registry JellyFlam3).",
        "baseUrl must be reachable FROM the Roku (use publicUrl / LAN IP, not 127.0.0.1).",
        "item id → deep link: curl -d '' \"http://ROKU_IP:8060/launch/dev?contentId=ITEM_ID\"",
        "shuffleFlock eligible gens: 247,245,244,243,242,198,191,169,165 (skip misc/test).",
        "Hard separation: live Sheep library path should be /media/sheep/by-generation; "
        "Rework Poster / refactor previews → /media/sheep/_refactor-preview. "
        "Do not point Sheep at the /media/sheep mount root.",
    ]
    for vf in folders:
        for loc in vf.get("locations") or []:
            norm = str(loc).rstrip("/").replace("\\", "/")
            name = (vf.get("name") or "").lower()
            if norm == "/media/sheep" or (
                "sheep" in name and norm.endswith("/media/sheep")
            ):
                notes.append(
                    f"WARNING: library {vf.get('name')!r} points at mount root {loc!r}; "
                    "point Sheep at /media/sheep/by-generation for hard separation."
                )
            if "_refactor-preview" in norm and "sheep" in name and "rework" not in name and "refactor" not in name and "preview" not in name:
                notes.append(
                    f"WARNING: library {vf.get('name')!r} includes preview path {loc!r}."
                )

    return {
        "jellyfin": {
            "url": base,
            "publicUrl": creds["public_url"],
            "apiKey": _mask(key, show=show_secrets),
            "configuredUserId": creds["user_id"],
            "configuredLibraryId": creds["library_id"],
        },
        "rokuRegistrySection": "JellyFlam3",
        "rokuSettings": roku_keys,
        "users": users,
        "views": views,
        "virtualFolders": folders,
        "items": items,
        "itemCount": len(items),
        "notes": notes,
    }


def print_human(report: dict[str, Any]) -> None:
    """Print report sections for copy/paste into Roku Settings."""
    print("=== JellyFlam3 Roku Settings (registry JellyFlam3) ===")
    rs = report["rokuSettings"]
    for k in (
        "baseUrl",
        "apiKey",
        "userId",
        "libraryId",
        "commercialMode",
        "streamMode",
        "shuffleFlock",
    ):
        print(f"  {k}={rs.get(k, '')}")
    print()
    print("=== Users (userId candidates) ===")
    for u in report["users"]:
        flags = []
        if u["isAdmin"]:
            flags.append("admin")
        if u["isDisabled"]:
            flags.append("disabled")
        flag_s = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {u['id']}  {u['name']}{flag_s}")
    print()
    print("=== Views / libraries (libraryId = ParentId) ===")
    for v in report["views"]:
        print(f"  {v['id']}  {v['name']}  type={v['collectionType'] or '-'}  path={v['path'] or '-'}")
    if report["virtualFolders"]:
        print()
        print("=== VirtualFolders (library roots) ===")
        for vf in report["virtualFolders"]:
            locs = ", ".join(vf.get("locations") or []) or "-"
            print(f"  {vf['id']}  {vf['name']}  type={vf['collectionType'] or '-'}  locs={locs}")
    if report["items"]:
        print()
        print(f"=== Items ({report['itemCount']}) ===")
        print(f"  {'id':<36}  {'gen':<6}  {'sec':>4}  primary  name")
        for it in report["items"]:
            prim = "yes" if it["hasPrimary"] else "no"
            gen = it["generation"] or "-"
            print(
                f"  {it['id']:<36}  {gen:<6}  {it['lengthSec']:>4}  {prim:<7}  {it['name']}"
            )
    print()
    for n in report["notes"]:
        print(f"NOTE: {n}")


def main() -> int:
    """CLI entry: resolve creds, build report, print human or JSON."""
    ap = argparse.ArgumentParser(
        description="Dump Jellyfin IDs/keys for JellyFlam3 Roku Settings"
    )
    ap.add_argument(
        "--config",
        default=str(ROOT / "configs" / "jellyflam3.yaml"),
        help="Config path (default: configs/jellyflam3.yaml)",
    )
    ap.add_argument(
        "--items",
        action="store_true",
        help="Also list Movie/Video item Guids (for deep link / shuffle checks)",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max items when --items (default 200)",
    )
    ap.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of human-readable text",
    )
    ap.add_argument(
        "--show-secrets",
        action="store_true",
        help="Print full apiKey (default masks middle)",
    )
    ap.add_argument(
        "--smoke-item-id",
        action="store_true",
        help="Print one flock item Guid for hls_smoke.sh (folder-aware; no other output)",
    )
    args = ap.parse_args()

    if args.smoke_item_id:
        item_id = resolve_smoke_item_id(Path(args.config))
        if not item_id:
            raise SystemExit("no flock item found (check library_id / Jellyfin scan)")
        print(item_id)
        return 0

    creds = resolve_creds(Path(args.config))
    report = build_report(
        creds,
        include_items=args.items,
        limit=args.limit,
        show_secrets=args.show_secrets,
    )
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
