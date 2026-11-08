#!/usr/bin/env python3

"""Purpose: Pre-fill client package Jellyfin settings when packaging on a furnace host.

On Pis with ``secrets.env`` (local Jellyfin), runs ``jellyfin_id_dump`` logic and writes:
- ``registry/jellyflam3-presets.json`` for Roku VoD + Screensaver zips
- Kodi ``settings.xml`` default values for server_url / api_key / user_id / library_id / vote sink

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
import urllib.parse
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
    "mp4Fallback",
    "shuffleFlock",
    "displaySinkUrl",
)
KODI_MAP = {
    "server_url": "baseUrl",
    "api_key": "apiKey",
    "user_id": "userId",
    "library_id": "libraryId",
}


def _host_is_funnel(host: str) -> bool:
    h = (host or "").strip().lower()
    return h.endswith(".ts.net")


def _host_is_loopback(host: str) -> bool:
    h = (host or "").strip().lower()
    return h in ("127.0.0.1", "localhost", "::1")


def _sink_url_from_base(base_url: str, port: int = 8791) -> str:
    """HTTP vote/profile sink on the Jellyfin host. Skip Funnel and loopback hosts."""
    raw = (base_url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urllib.parse.urlparse(raw)
    host = parsed.hostname or ""
    if not host or _host_is_funnel(host) or _host_is_loopback(host):
        return ""
    return "http://%s:%s" % (host, int(port))


def furnace_lan_ips() -> list[str]:
    """Non-loopback IPv4 addresses on this host (for Roku LAN displaySinkUrl)."""
    import subprocess

    try:
        text = subprocess.check_output(["hostname", "-I"], text=True, timeout=2)
    except (OSError, subprocess.SubprocessError):
        return []
    out: list[str] = []
    for tok in text.split():
        if not tok or ":" in tok or tok.startswith("127."):
            continue
        out.append(tok)
    return out


def furnace_lan_sink_url(port: int = 8791) -> str:
    """LAN ``http://IP:8791`` for Office Rokus when Jellyfin URL is loopback or Funnel.

    Prefer ``DISPLAY_SINK_URL``, then a non-loopback derive from ``JELLYFIN_URL``,
    then a local ``192.168.*`` address (wlan preferred when several).
    """
    explicit = (os.environ.get("DISPLAY_SINK_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    derived = _sink_url_from_base(os.environ.get("JELLYFIN_URL") or "", port=port)
    if derived:
        return derived
    ips = furnace_lan_ips()
    if not ips:
        return ""
    preferred = [ip for ip in ips if ip.startswith("192.168.")]
    # Household furnaces historically advertise the wlan address first to Office.
    pick = (preferred or ips)[0]
    for ip in preferred:
        if ip.endswith(".162"):
            pick = ip
            break
    return "http://%s:%s" % (pick, int(port))


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


def _preset_str(value: Any) -> str:
    """Stringify a preset value. JSON booleans must not become Python ``str(True)``."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def normalize_roku_settings(settings: dict[str, Any]) -> dict[str, str]:
    """Copy ROKU_KEYS; always persist shuffleFlock=true (household rotate policy).

    ``displaySinkToken`` is added only for a furnace sideload when
    ``DISPLAY_SINK_TOKEN`` is set (or the settings dict already has one).
    Channel Store packages use ``--no-presets`` and never write this file.
    """
    out = {k: _preset_str(settings.get(k)) for k in ROKU_KEYS}
    out["shuffleFlock"] = "true"
    env_mode = (os.environ.get("JELLYFIN_STREAM_MODE") or "").strip().lower()
    if env_mode in ("mp4", "hls"):
        out["streamMode"] = env_mode
    elif out.get("streamMode") not in ("mp4", "hls"):
        out["streamMode"] = "mp4"
    out["mp4Fallback"] = jfd.mp4_fallback_pref(out.get("streamMode") or "mp4")
    token = (os.environ.get("DISPLAY_SINK_TOKEN") or "").strip()
    if not token:
        token = _preset_str(settings.get("displaySinkToken"))
    if token:
        out["displaySinkToken"] = token
    sink = _preset_str(settings.get("displaySinkUrl") or settings.get("display_sink_url"))
    if not sink:
        # Prefer deriving from Jellyfin host when it is a real LAN/DNS name.
        sink = _sink_url_from_base(out.get("baseUrl") or "")
    if not sink:
        # Funnel (*.ts.net) or loopback Jellyfin URL — Roku needs the furnace LAN IP.
        sink = furnace_lan_sink_url()
    if sink:
        out["displaySinkUrl"] = sink.rstrip("/")
    elif "displaySinkUrl" in out and not out["displaySinkUrl"]:
        del out["displaySinkUrl"]
    return out


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
                return normalize_roku_settings(data)
        except (json.JSONDecodeError, OSError):
            pass
    creds = jfd.resolve_creds(config)
    report = jfd.build_report(creds, include_items=False, limit=1, show_secrets=True)
    settings = report.get("rokuSettings") or {}
    out = normalize_roku_settings(settings)
    payload = {
        "rokuRegistrySection": report.get("rokuRegistrySection") or "JellyFlam3",
        **out,
        "source": "jellyfin_id_dump",
    }
    cache.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def write_roku_registry_dir(
    registry_dir: Path,
    settings: dict[str, str],
    *,
    source: str = "jellyfin_id_dump",
    literal: bool = False,
) -> Path:
    """Write ``registry/jellyflam3-presets.json`` for Roku sideload packages.

    ``literal`` keeps Office-captured values as posted (no shuffle/stream defaults).
    """
    registry_dir.mkdir(parents=True, exist_ok=True)
    out = registry_dir / PRESET_NAME
    body = dict(settings) if literal else normalize_roku_settings(settings)
    payload = {
        "rokuRegistrySection": "JellyFlam3",
        **body,
        "source": source,
    }
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return out


def apply_kodi_settings(settings_path: Path, roku_settings: dict[str, str]) -> None:
    """Set Kodi add-on ``settings.xml`` default= attributes from rokuSettings."""
    tree = ET.parse(settings_path)
    root = tree.getroot()
    for node in root.iter("setting"):
        sid = node.get("id") or ""
        if sid == "shuffle":
            node.set("default", "true")
            continue
        if sid == "display_sink_url":
            derived = _sink_url_from_base(roku_settings.get("baseUrl") or "")
            if derived:
                node.set("default", derived)
            continue
        if sid == "display_sink_token":
            token = (os.environ.get("DISPLAY_SINK_TOKEN") or "").strip()
            if token:
                node.set("default", token)
            continue
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
    from_package_profile: bool = False,
    package_profile_path: Path | None = None,
) -> bool:
    """Fetch presets on furnace hosts and apply to requested package targets.

    ``from_package_profile`` embeds the Office-captured Settings literally and
    does not rewrite streamMode / mp4Fallback from the environment.
    """
    repo = root or ROOT
    if from_package_profile:
        from pipeline.roku_package_profile import (  # noqa: PLC0415
            default_profile_path,
            load_package_profile,
        )

        profile_path = package_profile_path or default_profile_path()
        try:
            settings = load_package_profile(profile_path)
        except (OSError, ValueError) as exc:
            print(f"client_pack_presets: package profile failed: {exc}", file=sys.stderr)
            return False
        # Funnel baseUrl cannot derive :8791; ensure a LAN sink is embedded for Office.
        if not (settings.get("displaySinkUrl") or "").strip():
            sink = furnace_lan_sink_url()
            if sink:
                settings = {**settings, "displaySinkUrl": sink}
        if roku_registry is not None:
            path = write_roku_registry_dir(
                roku_registry,
                settings,
                source="roku_settings_capture",
                literal=True,
            )
            print(f"client_pack_presets: roku registry -> {path} (from Office package profile)")
        if kodi_settings is not None:
            apply_kodi_settings(kodi_settings, settings)
            print(f"client_pack_presets: kodi settings -> {kodi_settings}")
        base = settings.get("baseUrl") or ""
        kind = "funnel" if "ts.net" in base else "lan" if base else "empty"
        has_sink = "yes" if (settings.get("displaySinkUrl") or "").strip() else "no"
        print(
            "client_pack_presets: source=roku_settings_capture "
            f"baseUrl_kind={kind} streamMode={settings.get('streamMode')} "
            f"mp4Fallback={settings.get('mp4Fallback')} displaySinkUrl={has_sink}"
        )
        return True

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
    if masked.get("displaySinkToken"):
        masked["displaySinkToken"] = "***"
    print(
        f"client_pack_presets: baseUrl={masked.get('baseUrl')} "
        f"userId={masked.get('userId')} libraryId={masked.get('libraryId')}"
    )
    return True


def _mask_api_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return key[:2] + "..." + key[-4:]


def strip_cr_bytes(data: bytes) -> bytes:
    """Normalize newlines to LF. Kodi TinyXML rejects CRLF addon.xml."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def strip_cr_in_dir(root: Path, suffixes: tuple[str, ...] = (".xml", ".py")) -> int:
    """Rewrite text files under root that still contain CR. Returns files changed."""
    changed = 0
    if not root.is_dir():
        return 0
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in suffixes:
            continue
        raw = p.read_bytes()
        fixed = strip_cr_bytes(raw)
        if fixed != raw:
            p.write_bytes(fixed)
            changed += 1
    return changed


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
    prep.add_argument(
        "--from-package-profile",
        action="store_true",
        help="Embed /var/lib/jellyflam3/roku-package-profile.json literally (Office capture)",
    )
    prep.add_argument(
        "--package-profile",
        type=Path,
        default=None,
        help="Override path to the captured Office package profile JSON",
    )
    strip = sub.add_parser("strip-cr", help="Rewrite CR/CRLF to LF under a staged add-on tree")
    strip.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="Staged screensaver.jellyflam3 directory",
    )
    args = ap.parse_args()
    if args.cmd == "prepare":
        ok = prepare_packaging(
            config=Path(args.config),
            roku_registry=args.roku_registry,
            kodi_settings=args.kodi_settings,
            from_package_profile=bool(args.from_package_profile),
            package_profile_path=args.package_profile,
        )
        if args.from_package_profile:
            return 0 if ok else 1
        return 0 if ok or not is_furnace_host() else 1
    if args.cmd == "strip-cr":
        n = strip_cr_in_dir(args.dir)
        print(f"client_pack_presets: strip-cr {n} file(s) under {args.dir}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
