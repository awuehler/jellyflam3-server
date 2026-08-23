#!/usr/bin/env python3
"""Purpose: Pre-fill client package Jellyfin settings when packaging on a furnace host.

On Pis with ``secrets.env`` (local Jellyfin), runs ``jellyfin_id_dump`` logic and writes:
- ``registry/jellyflam3-presets.json`` for Roku VoD + Screensaver zips
- Kodi ``settings.xml`` default values for server_url / api_key / user_id / library_id

Requirements: python3, pipeline.config, secrets.env with JELLYFIN_URL + JELLYFIN_API_KEY.
Usage:
  python3 scripts/client_pack_presets.py prepare --roku-registry roku-channel/registry
  python3 scripts/client_pack_presets.py prepare --kodi-settings path/to/settings.xml
When to run: Invoked by ``package_roku_*`` / ``package_kodi_screensaver`` on furnace Pis.
Success: Presets written; skipped with exit 0 when not a furnace host.
Docs: docs/phase3/08_JELLYFIN_ID_DUMP.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pipeline.config import load_dotenv  # noqa: E402

import jellyfin_id_dump as jfd  # noqa: E402

PRESET_NAME = "jellyflam3-presets.json"
CACHE_DIR = ROOT / "dist" / "client-presets"
ROKU_KEYS = (
    "baseUrl",
    "apiKey",
    "userId",
    "libraryId",
    "commercialMode",
    "streamMode",
    "shuffleFlock",
)
KODI_MAP = {
    "server_url": "baseUrl",
    "api_key": "apiKey",
    "user_id": "userId",
    "library_id": "libraryId",
}


def is_furnace_host(root: Path | None = None) -> bool:
    """True when secrets.env provides Jellyfin URL + API key (furnace packaging host)."""
    repo = root or ROOT
    secrets = repo / "secrets.env"
    if not secrets.is_file():
        return False
    load_dotenv(secrets)
    url = (os.environ.get("JELLYFIN_URL") or "").strip()
    key = (os.environ.get("JELLYFIN_API_KEY") or "").strip()
    return bool(url and key)


def fetch_roku_settings(
    config: Path,
    *,
    root: Path | None = None,
    use_cache: bool = True,
) -> dict[str, str] | None:
    """Resolve Jellyfin creds via jellyfin_id_dump; return rokuSettings or None."""
    if not is_furnace_host(root):
        return None
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / PRESET_NAME
    if use_cache and cache.is_file():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("baseUrl") and data.get("apiKey"):
                return {k: str(data.get(k) or "") for k in ROKU_KEYS}
        except (json.JSONDecodeError, OSError):
            pass
    creds = jfd.resolve_creds(config)
    report = jfd.build_report(creds, include_items=False, limit=1, show_secrets=True)
    settings = report.get("rokuSettings") or {}
    out = {k: str(settings.get(k) or "") for k in ROKU_KEYS}
    payload = {
        "rokuRegistrySection": report.get("rokuRegistrySection") or "JellyFlam3",
        **out,
        "source": "jellyfin_id_dump",
    }
    cache.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def write_roku_registry_dir(registry_dir: Path, settings: dict[str, str]) -> Path:
    """Write ``registry/jellyflam3-presets.json`` for Roku sideload packages."""
    registry_dir.mkdir(parents=True, exist_ok=True)
    out = registry_dir / PRESET_NAME
    payload = {"rokuRegistrySection": "JellyFlam3", **settings, "source": "jellyfin_id_dump"}
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def apply_kodi_settings(settings_path: Path, roku_settings: dict[str, str]) -> None:
    """Set Kodi add-on ``settings.xml`` default= attributes from rokuSettings."""
    tree = ET.parse(settings_path)
    root = tree.getroot()
    for node in root.iter("setting"):
        sid = node.get("id") or ""
        roku_key = KODI_MAP.get(sid)
        if not roku_key:
            continue
        val = (roku_settings.get(roku_key) or "").strip()
        if val:
            node.set("default", val)
    tree.write(
        settings_path,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=False,
    )


def prepare_packaging(
    *,
    config: Path,
    root: Path | None = None,
    roku_registry: Path | None = None,
    kodi_settings: Path | None = None,
) -> bool:
    """Fetch presets on furnace hosts and apply to requested package targets."""
    repo = root or ROOT
    if not is_furnace_host(repo):
        print("client_pack_presets: skip (no furnace secrets.env with Jellyfin URL + API key)")
        return False
    settings = fetch_roku_settings(config, root=repo)
    if not settings or not settings.get("baseUrl") or not settings.get("apiKey"):
        print("client_pack_presets: skip (jellyfin_id_dump returned no settings)", file=sys.stderr)
        return False
    if roku_registry is not None:
        path = write_roku_registry_dir(roku_registry, settings)
        print(f"client_pack_presets: roku registry -> {path}")
    if kodi_settings is not None:
        apply_kodi_settings(kodi_settings, settings)
        print(f"client_pack_presets: kodi settings -> {kodi_settings}")
    masked = {**settings, "apiKey": _mask_api_key(settings.get("apiKey", ""))}
    print(f"client_pack_presets: baseUrl={masked.get('baseUrl')} userId={masked.get('userId')} libraryId={masked.get('libraryId')}")
    return True


def _mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return key[:2] + "..." + key[-4:]


def main() -> int:
    ap = argparse.ArgumentParser(description="Pre-fill client packages from furnace Jellyfin")
    ap.add_argument(
        "--config",
        default=str(ROOT / "configs" / "jellyflam3.yaml"),
        help="JellyFlam3 config path (default: configs/jellyflam3.yaml)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    prep = sub.add_parser("prepare", help="Write presets for packaging (furnace hosts only)")
    prep.add_argument(
        "--roku-registry",
        type=Path,
        help="Roku package registry/ directory (writes jellyflam3-presets.json)",
    )
    prep.add_argument(
        "--kodi-settings",
        type=Path,
        help="Kodi screensaver resources/settings.xml to patch",
    )
    args = ap.parse_args()
    if args.cmd == "prepare":
        ok = prepare_packaging(
            config=Path(args.config),
            roku_registry=args.roku_registry,
            kodi_settings=args.kodi_settings,
        )
        return 0 if ok or not is_furnace_host() else 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
