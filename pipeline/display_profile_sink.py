"""Purpose: LAN HTTP sink for display profiles and sidecar sheep votes.

Requirements: Writable display_profiles dir; catalog media_library for votes.
  A non-loopback bind (the systemd unit uses 0.0.0.0) needs DISPLAY_SINK_TOKEN
  or JELLYFIN_API_KEY in secrets.env. Both missing → exit 2; with
  Restart=on-failure that is a crash loop. --allow-unauthenticated is lab-only
  and is not in the unit file.

Usage:
  python3 -m pipeline.display_profile_sink --config configs/jellyflam3.yaml
  GET /healthz | GET/POST/PUT /v1/display-profiles | POST /v1/sheep-votes
  (header X-JellyFlam3-Token: DISPLAY_SINK_TOKEN or the furnace Jellyfin API key)

Assumptions: Profile POSTs upsert one file per client+deviceId. Vote POSTs rewrite
  that sheep's catalog sidecar ``viewer_feedback`` only (no /var/lib store).
  Auth is fail-closed: a protected route needs a matching sink token or Jellyfin
  API key unless --allow-unauthenticated. The Jellyfin key therefore also
  authorizes these writes. Vote traffic is not a Jellyfin Sessions client
  (idle-gate safe).
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

from pipeline.config import load_config, load_dotenv, resolve_path
from pipeline.display_profiles import (
    list_profiles,
    profiles_dir_from_cfg,
    upsert_profile,
)
from pipeline.sheep_votes import InvalidVote, StemNotFound, apply_vote

DEFAULT_PORT = 8791


class _State:
    profiles_dir: Path = Path("/var/lib/jellyflam3/display_profiles")
    media_root: Path = Path("/media/sheep")
    token: str = ""
    jellyfin_api_key: str = ""
    allow_unauthenticated: bool = False


STATE = _State()


def _secret_values() -> list[str]:
    """Non-empty sink token and Jellyfin API key configured for this process."""
    found: list[str] = []
    for raw in (STATE.token, STATE.jellyfin_api_key):
        text = (raw or "").strip()
        if text and text not in found:
            found.append(text)
    return found


def lan_bind_allowed(
    *,
    token: str,
    jellyfin_api_key: str,
    allow_unauthenticated: bool,
    host_local: bool,
) -> bool:
    """True when a non-loopback bind has at least one credential, or lab flags apply."""
    if host_local or allow_unauthenticated:
        return True
    return bool((token or "").strip() or (jellyfin_api_key or "").strip())


class Handler(BaseHTTPRequestHandler):
    server_version = "JellyFlam3DisplaySink/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _check_token(self) -> bool:
        """True when the header matches the sink token or the Jellyfin API key.

        No credential is configured: lab ``allow_unauthenticated`` is the only
        open path. An empty header never matches.
        """
        secrets = _secret_values()
        if not secrets:
            return bool(STATE.allow_unauthenticated)
        got = (self.headers.get("X-JellyFlam3-Token") or "").strip()
        if not got:
            return False
        return any(got == secret for secret in secrets)

    def _discard_body(self) -> None:
        """Read a rejected POST so the client can receive the status line."""
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            return
        remaining = max(0, min(length, 256_000))
        while remaining > 0:
            chunk = self.rfile.read(min(remaining, 65536))
            if not chunk:
                break
            remaining -= len(chunk)

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
                    "mediaRoot": str(STATE.media_root),
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
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/v1/sheep-votes":
            self._sheep_vote()
            return
        self._upsert()

    def do_PUT(self) -> None:  # noqa: N802
        self._upsert()

    def _sheep_vote(self) -> None:
        """POST handler: increment sidecar viewer_feedback (unlimited re-vote)."""
        if not self._check_token():
            self._discard_body()
            self._send(401, {"ok": False, "error": "unauthorized"})
            return
        try:
            raw = self._read_json()
            result = apply_vote(STATE.media_root, raw)
        except InvalidVote as e:
            self._send(400, {"ok": False, "error": str(e)})
            return
        except StemNotFound as e:
            self._send(404, {"ok": False, "error": str(e)})
            return
        except FileNotFoundError as e:
            self._send(404, {"ok": False, "error": str(e)})
            return
        except ValueError as e:
            self._send(400, {"ok": False, "error": str(e)})
            return
        except Exception as e:  # noqa: BLE001
            self._send(500, {"ok": False, "error": str(e)})
            return
        self._send(200, result)

    def _upsert(self) -> None:
        """POST/PUT handler: normalize and write one display profile file."""
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/v1/display-profiles":
            self._send(404, {"ok": False, "error": "not found"})
            return
        if not self._check_token():
            self._discard_body()
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
    ap = argparse.ArgumentParser(
        description="JellyFlam3 display-profile + sheep-vote HTTP sink"
    )
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
    STATE.jellyfin_api_key = os.environ.get("JELLYFIN_API_KEY") or ""
    STATE.allow_unauthenticated = bool(args.allow_unauthenticated)

    host_local = args.host in ("127.0.0.1", "localhost", "::1")
    if not lan_bind_allowed(
        token=STATE.token,
        jellyfin_api_key=STATE.jellyfin_api_key,
        allow_unauthenticated=STATE.allow_unauthenticated,
        host_local=host_local,
    ):
        print(
            "ERROR: DISPLAY_SINK_TOKEN or JELLYFIN_API_KEY required when binding "
            "a non-loopback host (set secrets.env or pass --allow-unauthenticated "
            "for lab-only open access)",
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
    try:
        STATE.media_root = resolve_path(cfg, "media_library") if cfg else Path("/media/sheep")
    except (KeyError, TypeError, ValueError):
        STATE.media_root = Path("/media/sheep")

    if _secret_values():
        auth = "on"
    elif STATE.allow_unauthenticated:
        auth = "off(allow-unauthenticated)"
    else:
        auth = "fail-closed(no credential)"

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
