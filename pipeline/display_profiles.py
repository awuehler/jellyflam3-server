"""Purpose: Per-screen display profile store for JellyFlam3 (guide 04 piece F).

Requirements: Writable ``paths.display_profiles`` directory (default /var/lib/jellyflam3/display_profiles/).

Usage:
  python -m pipeline.display_profiles list
  python -m pipeline.display_profiles upsert --file profile.json

Assumptions: One JSON file per client+deviceId; Roku may lowercase keys — normalize_profile accepts aliases.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path

SCHEMA_VERSION = 1
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def default_profiles_dir() -> Path:
    return Path("/var/lib/jellyflam3/display_profiles")


def profiles_dir_from_cfg(cfg: dict[str, Any] | None) -> Path:
    """Resolve display_profiles dir from config, or the default absolute path."""
    if not cfg:
        return default_profiles_dir()
    paths = cfg.get("paths") or {}
    raw = paths.get("display_profiles")
    if not raw:
        return default_profiles_dir()
    p = Path(raw)
    if not p.is_absolute():
        root = Path(cfg.get("_repo_root") or ".")
        p = root / p
    return p


def sanitize_id(value: str, *, fallback: str = "unknown") -> str:
    """Filesystem-safe id fragment (alnum/._-), truncated to 80 chars."""
    s = (value or "").strip()
    if not s:
        s = fallback
    s = _SAFE.sub("_", s)
    s = s.strip("._-") or fallback
    return s[:80]


def profile_filename(client: str, device_id: str) -> str:
    """``{client}-{deviceId}.json`` after sanitize_id on each part."""
    c = sanitize_id(client, fallback="client")
    d = sanitize_id(device_id, fallback="device")
    return f"{c}-{d}.json"


def _field(raw: dict[str, Any], *names: str, default: str = "") -> str:
    """Read a profile field; names are tried exact then case-insensitive.

    Roku FormatJson lowercases associative-array keys, so wire JSON often has
    ``deviceid`` instead of ``deviceId``.
    """
    for name in names:
        if name in raw and raw[name] is not None:
            s = str(raw[name]).strip()
            if s:
                return s
    lower_map = {str(k).lower(): v for k, v in raw.items()}
    for name in names:
        v = lower_map.get(name.lower())
        if v is not None:
            s = str(v).strip()
            if s:
                return s
    return default


def normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize wire JSON into the on-disk schema (requires client + deviceId)."""
    if not isinstance(raw, dict):
        raise ValueError("profile must be a JSON object")
    client = _field(raw, "client")
    device_id = _field(raw, "deviceId", "device_id")
    if not client:
        raise ValueError("client is required")
    if not device_id:
        raise ValueError("deviceId is required")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    schema_raw = _field(raw, "schemaVersion", "schema_version", default="")
    try:
        schema_version = int(schema_raw) if schema_raw else SCHEMA_VERSION
    except ValueError:
        schema_version = SCHEMA_VERSION

    out: dict[str, Any] = {
        "schemaVersion": schema_version,
        "client": client,
        "deviceId": device_id,
        "deviceModel": _field(raw, "deviceModel", "device_model"),
        "deviceModelName": _field(raw, "deviceModelName", "device_model_name"),
        "friendlyName": _field(raw, "friendlyName", "friendly_name"),
        "displayWidth": _field(raw, "displayWidth", "display_width"),
        "displayHeight": _field(raw, "displayHeight", "display_height"),
        "uiResolution": _field(raw, "uiResolution", "ui_resolution"),
        "uiWidth": _field(raw, "uiWidth", "ui_width"),
        "uiHeight": _field(raw, "uiHeight", "ui_height"),
        "videoMode": _field(raw, "videoMode", "video_mode"),
        "displayAspect": _field(raw, "displayAspect", "display_aspect"),
        "hdr10": _field(raw, "hdr10", default="false") or "false",
        "hdr10Plus": _field(raw, "hdr10Plus", "hdr10_plus", default="false") or "false",
        "hlg": _field(raw, "hlg", default="false") or "false",
        "dolbyVision": _field(raw, "dolbyVision", "dolby_vision", default="false")
        or "false",
        "hdrSeamless": _field(raw, "hdrSeamless", "hdr_seamless", default="false")
        or "false",
        "displayInternal": _field(
            raw, "displayInternal", "display_internal", default="false"
        )
        or "false",
        "capturedAt": _field(raw, "capturedAt", "captured_at", default=now) or now,
        "displaySummary": _field(raw, "displaySummary", "display_summary"),
        "receivedAt": now,
    }
    # Preserve optional extras without breaking schema (case-insensitive pick)
    for key in ("channelVersion", "notes", "platform"):
        val = _field(raw, key)
        if val:
            out[key] = val
        else:
            # keep non-string extras if present under exact key
            if key in raw and raw[key] is not None:
                out[key] = raw[key]
    return out


def upsert_profile(profiles_dir: Path, raw: dict[str, Any]) -> Path:
    """Normalize ``raw`` and write/overwrite the matching screen profile file."""
    profile = normalize_profile(raw)
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / profile_filename(profile["client"], profile["deviceId"])
    path.write_text(json.dumps(profile, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def list_profiles(profiles_dir: Path) -> list[dict[str, Any]]:
    """Summary rows for each ``*.json`` profile (skips unreadable files)."""
    if not profiles_dir.is_dir():
        return []
    items: list[dict[str, Any]] = []
    for path in sorted(profiles_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items.append(
            {
                "file": path.name,
                "client": data.get("client"),
                "deviceId": data.get("deviceId"),
                "displaySummary": data.get("displaySummary"),
                "capturedAt": data.get("capturedAt"),
                "receivedAt": data.get("receivedAt"),
                "videoMode": data.get("videoMode"),
            }
        )
    return items


def main(argv: list[str] | None = None) -> int:
    """CLI: list or upsert per-screen display profile JSON files."""
    ap = argparse.ArgumentParser(description="Upsert/list JellyFlam3 display profiles")
    ap.add_argument(
        "--config",
        default="configs/jellyflam3.yaml",
        help="Config path (for paths.display_profiles)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List stored screen profiles")
    p_list.add_argument("--json", action="store_true")

    p_up = sub.add_parser("upsert", help="Write/update one screen profile from JSON")
    p_up.add_argument("--file", help="Path to JSON file (default: stdin)")
    p_up.add_argument("--client", help="Override client")
    p_up.add_argument("--device-id", help="Override deviceId")

    args = ap.parse_args(argv)
    cfg_path = Path(args.config)
    cfg = load_config(cfg_path) if cfg_path.is_file() else {}
    root = Path(cfg.get("_repo_root") or Path.cwd())
    if cfg and "paths" in cfg and "display_profiles" in (cfg.get("paths") or {}):
        try:
            profiles_dir = resolve_path(cfg, "display_profiles")
        except Exception:
            profiles_dir = profiles_dir_from_cfg(cfg)
    else:
        profiles_dir = profiles_dir_from_cfg(cfg)
        if not profiles_dir.is_absolute():
            profiles_dir = root / profiles_dir

    if args.cmd == "list":
        items = list_profiles(profiles_dir)
        if args.json:
            print(json.dumps(items, indent=2))
        else:
            print(f"profiles_dir={profiles_dir} count={len(items)}")
            for it in items:
                print(
                    f"  {it.get('file')}  client={it.get('client')}  "
                    f"deviceId={it.get('deviceId')}  {it.get('displaySummary') or ''}"
                )
        return 0

    if args.cmd == "upsert":
        if args.file:
            raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
        else:
            raw = json.load(sys.stdin)
        if args.client:
            raw["client"] = args.client
        if args.device_id:
            raw["deviceId"] = args.device_id
        path = upsert_profile(profiles_dir, raw)
        print(f"OK wrote {path}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
