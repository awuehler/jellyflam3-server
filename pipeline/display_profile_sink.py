"""Purpose: LAN HTTP sink for per-screen display profiles (guide 04 piece F).

Requirements: Writable display_profiles dir; DISPLAY_SINK_TOKEN in secrets.env for non-loopback binds
  (or pass --allow-unauthenticated for lab-only open access).

Usage:
  python3 -m pipeline.display_profile_sink --config configs/jellyflam3.yaml
  GET /healthz | GET/POST/PUT /v1/display-profiles (header X-JellyFlam3-Token when auth on)

Assumptions: Clients POST profile JSON; sink upserts one file per client+deviceId via display_profiles helpers.
  Auth is fail-closed: empty token denies API writes unless --allow-unauthenticated.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pipeline.config import load_config, load_dotenv
from pipeline.display_profiles import (
    list_profiles,
    profiles_dir_from_cfg,
    upsert_profile,
)

DEFAULT_PORT = 8791


class _State:
    profiles_dir: Path = Path("/var/lib/jellyflam3/display_profiles")
    token: str = ""
    allow_unauthenticated: bool = False


STATE = _State()


class Handler(BaseHTTPRequestHandler):
    server_version = "JellyFlam3DisplaySink/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _check_token(self) -> bool:
        """True when token matches, or lab ``allow_unauthenticated`` with no token set.

        Empty token without the lab flag denies protected routes (fail closed).
        """
        if not STATE.token:
            return bool(STATE.allow_unauthenticated)
        got = self.headers.get("X-JellyFlam3-Token") or ""
        return got == STATE.token

    def _send(self, code: int, body: dict[str, Any] | list[Any]) -> None:
        raw = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> dict[str, Any]:
        """Parse a JSON object body; reject empty or oversized payloads."""
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            raise ValueError("empty body")
        if length > 256_000:
            raise ValueError("body too large")
        data = self.rfile.read(length)
        parsed = json.loads(data.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("JSON object required")
        return parsed

    def do_GET(self) -> None:  # noqa: N802
        """Serve /healthz and authenticated profile listing."""
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/healthz":
            self._send(
                200,
                {
                    "ok": True,
                    "service": "display_profile_sink",
                    "profilesDir": str(STATE.profiles_dir),
                },
            )
            return
        if path == "/v1/display-profiles":
            if not self._check_token():
                self._send(401, {"ok": False, "error": "unauthorized"})
                return
            self._send(200, {"ok": True, "profiles": list_profiles(STATE.profiles_dir)})
            return
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        self._upsert()

    def do_PUT(self) -> None:  # noqa: N802
        self._upsert()

    def _upsert(self) -> None:
        """POST/PUT handler: normalize and write one display profile file."""
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/v1/display-profiles":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not self._check_token():
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        try:
            raw = self._read_json()
            out_path = upsert_profile(STATE.profiles_dir, raw)
            stored = json.loads(out_path.read_text(encoding="utf-8"))
        except ValueError as e:
            self._send(400, {"ok": False, "error": str(e)})
            return
        except Exception as e:  # noqa: BLE001
            self._send(500, {"ok": False, "error": str(e)})
            return
        self._send(
            200,
            {
                "ok": True,
                "file": out_path.name,
                "path": str(out_path),
                "client": stored.get("client"),
                "deviceId": stored.get("deviceId"),
            },
        )


def main(argv: list[str] | None = None) -> int:
    """CLI: serve the LAN HTTP sink for per-screen display profiles."""
    ap = argparse.ArgumentParser(description="JellyFlam3 display profile HTTP sink")
    ap.add_argument("--config", default="configs/jellyflam3.yaml")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument(
        "--allow-unauthenticated",
        action="store_true",
        help="Lab only: allow API access with no DISPLAY_SINK_TOKEN (default: fail closed)",
    )
    args = ap.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / "secrets.env")
    STATE.token = os.environ.get("DISPLAY_SINK_TOKEN") or ""
    STATE.allow_unauthenticated = bool(args.allow_unauthenticated)

    host_local = args.host in ("127.0.0.1", "localhost", "::1")
    if not STATE.token and not STATE.allow_unauthenticated and not host_local:
        print(
            "ERROR: DISPLAY_SINK_TOKEN required when binding a non-loopback host "
            "(set secrets.env or pass --allow-unauthenticated for lab-only open access)",
            file=sys.stderr,
            flush=True,
        )
        return 2

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = root / cfg_path
    cfg = (
        load_config(cfg_path, repo_root=root, strict_secrets=False)
        if cfg_path.is_file()
        else {}
    )
    STATE.profiles_dir = profiles_dir_from_cfg(cfg)
    STATE.profiles_dir.mkdir(parents=True, exist_ok=True)

    if STATE.token:
        auth = "on"
    elif STATE.allow_unauthenticated:
        auth = "off(allow-unauthenticated)"
    else:
        auth = "fail-closed(no token)"

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"display_profile_sink listening on http://{args.host}:{args.port} "
        f"dir={STATE.profiles_dir} auth={auth}",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("shutdown", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
