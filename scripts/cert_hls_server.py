#!/usr/bin/env python3

"""Purpose: Build and serve a pre-cut HLS stand-in for Roku App Behavior Analysis.

The lab cannot reach Jellyfin on the LAN, and a live remux of these sheep misses
the 8 second first-frame budget. This tool encodes a few catalog MP4s into short
HLS segments, checks that Tailscale Funnel is aimed at this process, and answers
the Jellyfin URLs the channel already requests. Household playback stays on
Jellyfin port 8096. Funnel is never changed.

Requirements: python3, PyYAML, ffmpeg, ffprobe, tailscale. secrets.env for the
API key and user id. A filled configs/cert_hls.yaml (see the example).

Usage (on a furnace, from the repo root):
  python3 scripts/cert_hls_server.py --config configs/cert_hls.yaml
  python3 scripts/cert_hls_server.py setup --config configs/cert_hls.yaml
  python3 scripts/cert_hls_server.py check --config configs/cert_hls.yaml
  python3 scripts/cert_hls_server.py serve --config configs/cert_hls.yaml

The bare command encodes, checks Funnel, and serves. setup stops after the
check. serve uses segments setup already wrote. check only reads Funnel.

Success: setup prints HLS_READY and FUNNEL_OK. A Funnel miss prints FUNNEL_MISMATCH
and exits 2 without listening. The access log records method, redacted path, and
status. The API key and user id are not written there.
Fail: missing source MP4, ffmpeg failure, Funnel off or pointed at another port.
Docs: configs/cert_hls.yaml.example
"""

from __future__ import annotations

import argparse
import hmac
import json
import logging
import os
import posixpath
import re
import shutil
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.config import load_dotenv  # noqa: E402

LOG = logging.getLogger("jellyflam3.cert_hls")
CATALOG_NAME = "catalog.json"
JELLYFIN_PORT = 8096
SHEEP_NAME = re.compile(r"^electricsheep\.(\d+)\.([0-9A-Za-z_-]+)$")
CONTENT_ID = re.compile(r"^[A-Za-z0-9_-]+$")
SEGMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+\.ts$")
SECRET_QUERY = {"apikey", "api_key", "token"}
Run = Callable[..., subprocess.CompletedProcess[str]]


def configure_logging(path: Path) -> None:
    """Append access lines to ``path`` and echo them on stderr."""
    LOG.setLevel(logging.INFO)
    LOG.handlers.clear()
    LOG.propagate = False
    path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%dT%H:%M:%S%z")
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    LOG.addHandler(file_handler)
    LOG.addHandler(stream)


def redact_query(query: str) -> str:
    """Hide token query values. Other parameters stay so a miss is diagnosable."""
    kept: list[str] = []
    for part in query.split("&"):
        if not part:
            continue
        key, sep, _value = part.partition("=")
        if sep and key.lower() in SECRET_QUERY:
            kept.append(f"{key}=REDACTED")
        else:
            kept.append(part)
    return "&".join(kept)


def redact_target(raw_path: str) -> str:
    """Drop the user id and any token from a request target."""
    path, sep, query = raw_path.partition("?")
    parts = path.split("/")
    if len(parts) > 2 and parts[1] == "Users":
        parts[2] = "{user}"
    shown = "/".join(parts)
    if sep:
        shown = f"{shown}?{redact_query(query)}"
    return shown


def load_settings(path: Path) -> dict[str, Any]:
    """Load the stand-in YAML. Environment names are read later, not values here."""
    load_dotenv(ROOT / "secrets.env")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SystemExit(f"config must be a mapping: {path}")
    return raw


def _required_text(cfg: Mapping[str, Any], key: str) -> str:
    value = str(cfg.get(key) or "").strip()
    if not value:
        raise SystemExit(f"config missing {key}")
    return value


def sheep_entries(cfg: Mapping[str, Any]) -> list[dict[str, str]]:
    """Normalize the sheep list. ``contentID`` is accepted as an alias."""
    rows = cfg.get("sheep") or []
    if not isinstance(rows, list) or not rows:
        raise SystemExit("config sheep must list at least one genome")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise SystemExit("each sheep entry must be a mapping")
        stem = str(row.get("sheep") or row.get("name") or "").strip()
        content_id = str(row.get("content_id") or row.get("contentID") or "").strip()
        source = str(row.get("source") or "").strip()
        if not SHEEP_NAME.fullmatch(stem):
            raise SystemExit(f"sheep must look like electricsheep.GEN.ID, got {stem!r}")
        if not CONTENT_ID.fullmatch(content_id):
            raise SystemExit(f"content_id must be a single token, got {content_id!r}")
        if content_id in seen:
            raise SystemExit(f"duplicate content_id {content_id}")
        seen.add(content_id)
        out.append({"sheep": stem, "content_id": content_id, "source": source})
    return out


def listen_port(cfg: Mapping[str, Any]) -> int:
    try:
        port = int(cfg.get("port"))
    except (TypeError, ValueError):
        raise SystemExit("config port must be an integer") from None
    if port == JELLYFIN_PORT:
        raise SystemExit("port 8096 belongs to Jellyfin; choose another port")
    if not 1 <= port <= 65535:
        raise SystemExit(f"port out of range: {port}")
    return port


def document_root(cfg: Mapping[str, Any]) -> Path:
    raw = _required_text(cfg, "document_root")
    path = Path(raw)
    if not path.is_absolute():
        raise SystemExit(f"document_root must be absolute: {raw}")
    return path


def env_value(cfg: Mapping[str, Any], name_key: str) -> str:
    """Return the secret named by ``name_key`` without logging it."""
    env_name = str(cfg.get(name_key) or "").strip()
    if not env_name:
        raise SystemExit(f"config missing {name_key}")
    return os.environ.get(env_name, "").strip()


def encode_options(cfg: Mapping[str, Any]) -> dict[str, Any]:
    raw = cfg.get("encode") or {}
    if not isinstance(raw, dict):
        raise SystemExit("encode must be a mapping")
    fps = int(raw.get("fps") or 24)
    hls_time = int(raw.get("hls_time") or 3)
    if fps < 1 or hls_time < 1:
        raise SystemExit("encode fps and hls_time must be positive")
    return {
        "width": int(raw.get("width") or 1280),
        "height": int(raw.get("height") or 720),
        "video_bitrate": str(raw.get("video_bitrate") or "1500k"),
        "audio_bitrate": str(raw.get("audio_bitrate") or "128k"),
        "hls_time": hls_time,
        "fps": fps,
        "preset": str(raw.get("preset") or "veryfast"),
        "timeout_sec": int(raw.get("timeout_sec") or 1800),
    }


def tool_path(cfg: Mapping[str, Any], name: str) -> str:
    """Prefer config, then jellyfin-ffmpeg, then PATH."""
    tools = cfg.get("tools") or {}
    configured = str(tools.get(name) or "").strip() if isinstance(tools, dict) else ""
    if configured:
        return configured
    bundled = Path("/usr/lib/jellyfin-ffmpeg") / name
    if bundled.is_file() and os.access(bundled, os.X_OK):
        return str(bundled)
    found = shutil.which(name)
    if not found:
        raise SystemExit(f"{name} not found")
    return found


def source_for(entry: Mapping[str, str], media_library: Path) -> Path:
    """Catalog MP4 for a stem, or the configured source file."""
    explicit = entry.get("source") or ""
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = ROOT / path
        return path
    match = SHEEP_NAME.fullmatch(entry["sheep"])
    assert match is not None
    return media_library / "by-generation" / match.group(1) / f"{entry['sheep']}.mp4"


def ffmpeg_argv(
    ffmpeg: str,
    source: Path,
    options: Mapping[str, Any],
    *,
    with_audio: bool,
) -> list[str]:
    """720p HLS with a keyframe at every segment boundary."""
    width = int(options["width"])
    height = int(options["height"])
    gop = int(options["fps"]) * int(options["hls_time"])
    scale = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    )
    argv = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-vf",
        scale,
        "-c:v",
        "libx264",
        "-preset",
        str(options["preset"]),
        "-b:v",
        str(options["video_bitrate"]),
        "-maxrate",
        str(options["video_bitrate"]),
        "-bufsize",
        str(int(str(options["video_bitrate"]).rstrip("kK") or "1500") * 2) + "k"
        if str(options["video_bitrate"]).lower().endswith("k")
        else str(options["video_bitrate"]),
        "-g",
        str(gop),
        "-keyint_min",
        str(gop),
        "-sc_threshold",
        "0",
        "-pix_fmt",
        "yuv420p",
    ]
    if with_audio:
        argv.extend(["-map", "0:a:0", "-c:a", "aac", "-b:a", str(options["audio_bitrate"]), "-ac", "2"])
    else:
        argv.append("-an")
    argv.extend(
        [
            "-hls_time",
            str(options["hls_time"]),
            "-hls_playlist_type",
            "vod",
            "-hls_flags",
            "independent_segments",
            "-hls_segment_filename",
            "seg_%03d.ts",
            "main.m3u8",
        ]
    )
    return argv


def _run(argv: list[str], run: Run, *, cwd: Path | None, timeout: int) -> subprocess.CompletedProcess[str]:
    return run(argv, cwd=cwd, check=False, capture_output=True, text=True, timeout=timeout)


def probe_duration(ffprobe: str, source: Path, run: Run, timeout: int) -> float:
    proc = _run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(source)],
        run,
        cwd=None,
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise SystemExit(f"ffprobe failed for {source.name}")
    try:
        return float((proc.stdout or "").strip())
    except ValueError as exc:
        raise SystemExit(f"ffprobe duration unreadable for {source.name}") from exc


def probe_audio(ffprobe: str, source: Path, run: Run, timeout: int) -> bool:
    proc = _run(
        [ffprobe, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(source)],
        run,
        cwd=None,
        timeout=timeout,
    )
    return proc.returncode == 0 and bool((proc.stdout or "").strip())


def encode_entry(
    entry: Mapping[str, str],
    source: Path,
    dest: Path,
    options: Mapping[str, Any],
    ffmpeg: str,
    run: Run,
) -> None:
    """Replace ``dest`` with a VOD playlist and segments."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with_audio = bool(options.get("with_audio"))
    proc = _run(
        ffmpeg_argv(ffmpeg, source, options, with_audio=with_audio),
        run,
        cwd=dest,
        timeout=int(options["timeout_sec"]),
    )
    playlist = dest / "main.m3u8"
    segments = list(dest.glob("seg_*.ts"))
    if proc.returncode != 0 or not playlist.is_file() or not segments:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail = tail[-1] if tail else f"exit {proc.returncode}"
        raise SystemExit(f"ffmpeg failed for {entry['sheep']}: {detail}")


def write_catalog(root: Path, items: list[dict[str, Any]]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    dest = root / CATALOG_NAME
    payload = {"sheep": items}
    tmp = dest.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(dest)
    return dest


def load_catalog(root: Path) -> list[dict[str, Any]]:
    path = root / CATALOG_NAME
    if not path.is_file():
        raise SystemExit(f"missing {path}; run setup first")
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("sheep") if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise SystemExit(f"catalog has no sheep: {path}")
    return rows


def parse_funnel_status(raw: str, *, port: int, backend_host: str, expected_host: str) -> dict[str, Any]:
    """Read `tailscale funnel status` text or JSON. Does not change Funnel."""
    proxies: list[str] = []
    hosts: list[str] = []
    funnel_on = False
    text = raw or ""
    stripped = text.strip()
    parsed: Any = None
    if stripped.startswith("{"):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            parsed = None
    if isinstance(parsed, dict):
        allow = parsed.get("AllowFunnel") or {}
        if isinstance(allow, dict):
            funnel_on = any(bool(value) for value in allow.values())
            hosts.extend(str(key).split(":")[0] for key in allow)
        web = parsed.get("Web") or {}
        if isinstance(web, dict):
            for key, site in web.items():
                hosts.append(str(key).split(":")[0])
                handlers = site.get("Handlers") if isinstance(site, dict) else None
                if not isinstance(handlers, dict):
                    continue
                for handler in handlers.values():
                    proxy = handler.get("Proxy") if isinstance(handler, dict) else None
                    if isinstance(proxy, str):
                        proxies.append(proxy)
    else:
        funnel_on = "Funnel on" in text
        for match in re.finditer(r"https://([^/\s:]+)", text):
            hosts.append(match.group(1))
        proxies.extend(re.findall(r"https?://[^\s]+", text))
        proxies = [item for item in proxies if "ts.net" not in item]

    backend = backend_host.lower()
    local_names = {backend}
    if backend in {"127.0.0.1", "localhost"}:
        local_names.update({"127.0.0.1", "localhost"})
    matched = False
    for proxy in proxies:
        url = urllib.parse.urlparse(proxy)
        host = (url.hostname or "").lower()
        if host in local_names and url.port == port:
            matched = True
            break
    host_ok = True
    if expected_host:
        host_ok = any(expected_host.lower() == item.lower() for item in hosts)
    ok = funnel_on and matched and host_ok
    if ok:
        detail = f"FUNNEL_OK port={port}"
    elif not funnel_on:
        detail = "FUNNEL_OFF"
    elif not matched:
        shown = ",".join(proxies) if proxies else "none"
        detail = f"FUNNEL_MISMATCH proxy={shown} want={backend_host}:{port}"
    else:
        detail = f"FUNNEL_HOST_MISMATCH want={expected_host}"
    return {"ok": ok, "funnel_on": funnel_on, "proxies": proxies, "detail": detail}


def read_funnel_status(run: Run, timeout: int = 15) -> str:
    """Return Funnel status JSON when tailscale provides it, else the text form."""
    json_proc = _run(["tailscale", "funnel", "status", "--json"], run, cwd=None, timeout=timeout)
    if json_proc.returncode == 0 and (json_proc.stdout or "").strip().startswith("{"):
        return json_proc.stdout
    text_proc = _run(["tailscale", "funnel", "status"], run, cwd=None, timeout=timeout)
    if text_proc.returncode != 0 and json_proc.returncode != 0:
        raise SystemExit("tailscale funnel status failed")
    return text_proc.stdout or json_proc.stdout or ""


def funnel_settings(cfg: Mapping[str, Any]) -> tuple[str, str]:
    raw = cfg.get("funnel") or {}
    if not isinstance(raw, dict):
        raise SystemExit("funnel must be a mapping")
    return str(raw.get("backend_host") or "127.0.0.1").strip(), str(raw.get("expected_host") or "").strip()


def build_hls(cfg: Mapping[str, Any], run: Run) -> Path:
    """Encode every configured sheep into the document root and write the catalog."""
    root = document_root(cfg)
    options = encode_options(cfg)
    media = Path(str(cfg.get("media_library") or "/media/sheep"))
    ffmpeg = tool_path(cfg, "ffmpeg")
    ffprobe = tool_path(cfg, "ffprobe")
    items: list[dict[str, Any]] = []
    for entry in sheep_entries(cfg):
        source = source_for(entry, media)
        if not source.is_file():
            raise SystemExit(f"source missing for {entry['sheep']}: {source}")
        duration = probe_duration(ffprobe, source, run, int(options["timeout_sec"]))
        audio = probe_audio(ffprobe, source, run, int(options["timeout_sec"]))
        dest = root / entry["content_id"]
        encode_entry(
            entry,
            source,
            dest,
            {**options, "with_audio": audio},
            ffmpeg,
            run,
        )
        items.append(
            {
                "sheep": entry["sheep"],
                "content_id": entry["content_id"],
                "run_time_ticks": int(round(duration * 10_000_000)),
                "playlist": "main.m3u8",
            }
        )
        LOG.info("encoded %s segments=%s", entry["sheep"], len(list(dest.glob('seg_*.ts'))))
    catalog = write_catalog(root, items)
    LOG.info("HLS_READY sheep=%s root=%s", len(items), root)
    return catalog


def check_funnel(cfg: Mapping[str, Any], run: Run) -> dict[str, Any]:
    backend, expected = funnel_settings(cfg)
    try:
        raw = read_funnel_status(run)
    except (OSError, subprocess.TimeoutExpired) as exc:
        report = {"ok": False, "funnel_on": False, "proxies": [], "detail": f"FUNNEL_UNAVAILABLE {exc.__class__.__name__}"}
        LOG.info("%s", report["detail"])
        return report
    report = parse_funnel_status(raw, port=listen_port(cfg), backend_host=backend, expected_host=expected)
    LOG.info("%s", report["detail"])
    return report


def presented_token(query: Mapping[str, list[str]], headers: Mapping[str, str]) -> str:
    for key in ("ApiKey", "api_key", "apiKey"):
        values = query.get(key)
        if values and values[0]:
            return values[0]
    for header in ("Authorization", "X-Emby-Authorization"):
        match = re.search(r'Token="([^"]*)"', headers.get(header, ""))
        if match and match.group(1):
            return match.group(1)
    return headers.get("X-Emby-Token", "")


def token_ok(presented: str, expected: str) -> bool:
    if not expected or not presented:
        return False
    return hmac.compare_digest(presented, expected)


def item_json(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "Id": row["content_id"],
        "Name": row["sheep"],
        "Type": "Movie",
        "MediaType": "Video",
        "Overview": "",
        "RunTimeTicks": int(row.get("run_time_ticks") or 0),
        "Tags": [],
        "ImageTags": {},
        "Path": row["sheep"] + ".mp4",
    }


def dispatch(
    method: str,
    target: str,
    headers: Mapping[str, str],
    catalog: list[dict[str, Any]],
    root: Path,
    *,
    api_key: str,
    user_id: str,
) -> tuple[int, str, bytes]:
    """Answer one channel request. Segment files do not require a token.

    The Roku Video node requests the playlist URL, which carries ApiKey, then
    requests each relative ``seg_NNN.ts`` with no header and no query.
    """
    parsed = urllib.parse.urlsplit(target)
    path = posixpath.normpath(urllib.parse.unquote(parsed.path))
    if path == ".":
        path = "/"
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    by_id = {str(row["content_id"]): row for row in catalog}

    if method == "GET" and path == "/System/Info/Public":
        body = {"ServerName": "jellyflam3-cert-hls", "Version": "1.0", "StartupWizardCompleted": True}
        return 200, "application/json", json.dumps(body).encode("utf-8")

    parts = [part for part in path.split("/") if part]
    segment = len(parts) == 3 and parts[0] == "Videos" and SEGMENT_NAME.fullmatch(parts[2])
    playlist = len(parts) == 3 and parts[0] == "Videos" and parts[2] == "main.m3u8"
    if segment or playlist:
        row = by_id.get(parts[1])
        if row is None:
            return 404, "application/json", b'{"error":"unknown item"}'
        filename = parts[2]
        file_path = (root / parts[1] / filename).resolve()
        try:
            file_path.relative_to((root / parts[1]).resolve())
        except ValueError:
            return 404, "application/json", b'{"error":"bad path"}'
        if playlist and not token_ok(presented_token(query, headers), api_key):
            return 401, "application/json", b'{"error":"unauthorized"}'
        if not file_path.is_file():
            return 404, "application/json", b'{"error":"missing segment"}'
        media = "application/vnd.apple.mpegurl" if playlist else "video/mp2t"
        return 200, media, file_path.read_bytes()

    if not token_ok(presented_token(query, headers), api_key):
        return 401, "application/json", b'{"error":"unauthorized"}'

    if method == "POST" and parts and parts[0] == "Sessions":
        return 204, "application/json", b""

    if method == "GET" and len(parts) >= 3 and parts[0] == "Users" and parts[2] == "Items":
        if user_id and parts[1] != user_id:
            return 404, "application/json", b'{"error":"unknown user"}'
        include = ",".join(query.get("IncludeItemTypes", []))
        if "Folder" in include and "Video" not in include and "Movie" not in include:
            body = {"Items": [], "TotalRecordCount": 0}
            return 200, "application/json", json.dumps(body).encode("utf-8")
        if len(parts) == 4:
            row = by_id.get(parts[3])
            if row is None:
                return 404, "application/json", b'{"error":"unknown item"}'
            return 200, "application/json", json.dumps(item_json(row)).encode("utf-8")
        items = [item_json(row) for row in catalog]
        body = {"Items": items, "TotalRecordCount": len(items)}
        return 200, "application/json", json.dumps(body).encode("utf-8")

    return 404, "application/json", b'{"error":"not found"}'


class CertHlsHandler(BaseHTTPRequestHandler):
    """Serve the catalog. Settings live on the server object."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _read_body(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 0:
            self.rfile.read(length)

    def _reply(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)
        self._log(status, len(body))

    def _log(self, status: int, size: int) -> None:
        LOG.info(
            "%s %s %s %s %s",
            self.client_address[0],
            self.command,
            redact_target(self.path),
            status,
            size,
        )

    def _handle(self) -> None:
        server = self.server
        assert isinstance(server, CertHlsServer)
        if self.command == "POST":
            self._read_body()
        status, content_type, body = dispatch(
            self.command,
            self.path,
            {key: value for key, value in self.headers.items()},
            server.catalog,
            server.document_root,
            api_key=server.api_key,
            user_id=server.user_id,
        )
        self._reply(status, content_type, body)

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_POST(self) -> None:  # noqa: N802
        self._handle()

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle()


class CertHlsServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        catalog: list[dict[str, Any]],
        root: Path,
        api_key: str,
        user_id: str,
    ) -> None:
        self.catalog = catalog
        self.document_root = root
        self.api_key = api_key
        self.user_id = user_id
        super().__init__(address, CertHlsHandler)


def serve_forever(cfg: Mapping[str, Any], *, server: CertHlsServer | None = None) -> int:
    root = document_root(cfg)
    catalog = load_catalog(root)
    api_key = env_value(cfg, "api_key_env")
    user_id = env_value(cfg, "user_id_env")
    if not api_key or not user_id:
        raise SystemExit("API key and user id environment variables must be set before serve")
    host = str(cfg.get("listen_host") or "127.0.0.1").strip()
    port = listen_port(cfg)
    owned = server is None
    httpd = server or CertHlsServer((host, port), catalog, root, api_key, user_id)
    LOG.info("listening %s:%s sheep=%s", host, port, len(catalog))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        LOG.info("stopped")
    finally:
        if owned:
            httpd.server_close()
    return 0


def require_secrets(cfg: Mapping[str, Any]) -> None:
    if not env_value(cfg, "api_key_env") or not env_value(cfg, "user_id_env"):
        raise SystemExit("API key and user id environment variables must be set")


def command_setup(cfg: Mapping[str, Any], run: Run) -> int:
    require_secrets(cfg)
    listen_port(cfg)
    build_hls(cfg, run)
    report = check_funnel(cfg, run)
    return 0 if report["ok"] else 2


def command_run(cfg: Mapping[str, Any], run: Run) -> int:
    code = command_setup(cfg, run)
    if code != 0:
        LOG.info("not listening; Funnel check failed")
        return code
    return serve_forever(cfg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-cut HLS stand-in for Roku lab playback")
    parser.add_argument("--config", required=True, type=Path)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("setup", help="Encode sheep and check Funnel")
    sub.add_parser("check", help="Check Funnel only")
    sub.add_parser("serve", help="Serve an existing document root")
    sub.add_parser("run", help="Encode, check Funnel, then serve")
    args = parser.parse_args(argv)
    cfg = load_settings(args.config)
    configure_logging(Path(_required_text(cfg, "log_file")))
    command = args.cmd or "run"
    if command == "check":
        require_secrets(cfg)
        report = check_funnel(cfg, subprocess.run)
        return 0 if report["ok"] else 2
    if command == "serve":
        return serve_forever(cfg)
    if command == "setup":
        return command_setup(cfg, subprocess.run)
    return command_run(cfg, subprocess.run)


if __name__ == "__main__":
    sys.exit(main())
