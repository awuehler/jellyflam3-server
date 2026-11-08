"""Purpose: Capture and load a Roku Settings package profile for furnace packaging.

Requirements: Writable path under ``/var/lib/jellyflam3`` (or cfg paths).

Usage:
  save_package_profile(path, payload)  # from display_profile_sink
  load_package_profile(path)           # for client_pack_presets / packaging
  python3 -m pipeline.roku_package_profile status

Assumptions: The profile holds the Office TV's JellyFlam3 registry values so a
  sideload zip can embed them literally. The file is host-local and must never
  be committed. Empty optional keys are dropped; baseUrl, apiKey, and userId
  are required.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PROFILE_PATH = Path("/var/lib/jellyflam3/roku-package-profile.json")

# Settings keys the channel posts and packaging embeds. Order is stable for diffs.
PROFILE_KEYS = (
    "baseUrl",
    "apiKey",
    "userId",
    "libraryId",
    "commercialMode",
    "streamMode",
    "mp4Fallback",
    "shuffleFlock",
    "titleMode",
    "sortMode",
    "displaySinkToken",
)

_REQUIRED = ("baseUrl", "apiKey", "userId")


def default_profile_path() -> Path:
    """Host-local capture path (never under the git tree)."""
    return DEFAULT_PROFILE_PATH


def profile_path_from_cfg(cfg: dict[str, Any] | None) -> Path:
    """Resolve ``paths.roku_package_profile`` when set, else the default path."""
    if cfg:
        paths = cfg.get("paths") or {}
        raw = paths.get("roku_package_profile")
        if raw:
            return Path(str(raw))
    return default_profile_path()


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def normalize_package_profile(raw: dict[str, Any]) -> dict[str, str]:
    """Copy known Settings keys as strings. Reject missing connection fields."""
    if not isinstance(raw, dict):
        raise ValueError("JSON object required")
    out: dict[str, str] = {}
    for key in PROFILE_KEYS:
        text = _as_str(raw.get(key))
        if text:
            out[key] = text
    for key in _REQUIRED:
        if not out.get(key):
            raise ValueError(f"missing {key}")
    base = out["baseUrl"]
    if not (base.startswith("http://") or base.startswith("https://")):
        raise ValueError("baseUrl must start with http:// or https://")
    if base.endswith("/"):
        raise ValueError("baseUrl must not end with a slash")
    mode = (out.get("streamMode") or "").lower()
    if mode and mode not in ("mp4", "hls"):
        raise ValueError("streamMode must be mp4 or hls")
    if mode:
        out["streamMode"] = mode
    return out


def save_package_profile(path: Path, raw: dict[str, Any]) -> Path:
    """Write the captured Settings profile with mode 0600."""
    settings = normalize_package_profile(raw)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rokuRegistrySection": "JellyFlam3",
        "source": "roku_settings_capture",
        "capturedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        **settings,
    }
    device_id = _as_str(raw.get("deviceId") or raw.get("channelDeviceId"))
    if device_id:
        payload["deviceId"] = device_id
    channel_version = _as_str(raw.get("channelVersion"))
    if channel_version:
        payload["channelVersion"] = channel_version
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def load_package_profile(path: Path) -> dict[str, str]:
    """Load and re-validate a previously captured profile."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"package profile missing: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("package profile must be a JSON object")
    return normalize_package_profile(data)


def status_payload(path: Path) -> dict[str, Any]:
    """Operator-safe status: no apiKey, userId, libraryId, or sink token."""
    path = Path(path)
    if not path.is_file():
        return {"ok": False, "exists": False, "path": str(path)}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = normalize_package_profile(data if isinstance(data, dict) else {})
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "exists": True, "path": str(path), "error": str(exc)}
    base = settings.get("baseUrl") or ""
    if "ts.net" in base:
        base_kind = "funnel"
    elif base.startswith("http://192.168.") or base.startswith("http://10.") or "127.0.0.1" in base:
        base_kind = "lan"
    else:
        base_kind = "other"
    return {
        "ok": True,
        "exists": True,
        "path": str(path),
        "capturedAt": data.get("capturedAt") if isinstance(data, dict) else None,
        "channelVersion": data.get("channelVersion") if isinstance(data, dict) else None,
        "baseUrlKind": base_kind,
        "streamMode": settings.get("streamMode") or "",
        "mp4Fallback": settings.get("mp4Fallback") or "",
        "commercialMode": settings.get("commercialMode") or "",
        "shuffleFlock": settings.get("shuffleFlock") or "",
        "titleMode": settings.get("titleMode") or "",
        "sortMode": settings.get("sortMode") or "",
        "hasApiKey": bool(settings.get("apiKey")),
        "hasUserId": bool(settings.get("userId")),
        "hasLibraryId": bool(settings.get("libraryId")),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI: print redacted package-profile status."""
    ap = argparse.ArgumentParser(description="Roku package-profile capture status")
    ap.add_argument("--path", type=Path, default=DEFAULT_PROFILE_PATH)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status", help="Print redacted profile status as JSON")
    args = ap.parse_args(argv)
    cmd = args.cmd or "status"
    if cmd == "status":
        print(json.dumps(status_payload(args.path), indent=2))
        return 0
    raise SystemExit(f"unknown command: {cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
