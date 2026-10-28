"""Cert HLS stand-in: encode plan, Funnel check, and the channel's URLs."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "cert_hls_server.py"


def _load():
    spec = importlib.util.spec_from_file_location("cert_hls_server", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cert_hls_server"] = module
    spec.loader.exec_module(module)
    return module


hls = _load()

FUNNEL_OK = json.dumps(
    {
        "Web": {
            "lab.tailnet.ts.net:443": {
                "Handlers": {"/": {"Proxy": "http://127.0.0.1:8097"}}
            }
        },
        "AllowFunnel": {"lab.tailnet.ts.net:443": True},
    }
)


def _cfg(tmp_path: Path, *, port: int = 8097) -> dict:
    source = tmp_path / "electricsheep.169.00000.mp4"
    source.write_bytes(b"not-a-real-mp4")
    return {
        "listen_host": "127.0.0.1",
        "port": port,
        "document_root": str(tmp_path / "hls"),
        "log_file": str(tmp_path / "cert-hls.log"),
        "media_library": str(tmp_path / "media"),
        "api_key_env": "JELLYFLAM3_CERT_API_KEY",
        "user_id_env": "JELLYFLAM3_CERT_USER_ID",
        "encode": {
            "width": 1280,
            "height": 720,
            "video_bitrate": "1500k",
            "hls_time": 3,
            "fps": 24,
        },
        "funnel": {"backend_host": "127.0.0.1", "expected_host": "lab.tailnet.ts.net"},
        "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
        "sheep": [
            {
                "sheep": "electricsheep.169.00000",
                "content_id": "item-one",
                "source": str(source),
            }
        ],
    }


def _fake_run(argv, cwd=None, check=False, capture_output=True, text=True, timeout=None, funnel=FUNNEL_OK):
    name = Path(argv[0]).name
    if name == "ffprobe":
        if "-select_streams" in argv:
            return subprocess.CompletedProcess(argv, 0, "0\n", "")
        return subprocess.CompletedProcess(argv, 0, "12.0\n", "")
    if name == "ffmpeg":
        out = Path(cwd)
        out.mkdir(parents=True, exist_ok=True)
        (out / "main.m3u8").write_text("#EXTM3U\n#EXTINF:3.0,\nseg_000.ts\n#EXT-X-ENDLIST\n", encoding="utf-8")
        (out / "seg_000.ts").write_bytes(b"\x47" * 188)
        return subprocess.CompletedProcess(argv, 0, "", "")
    if argv[:4] == ["tailscale", "funnel", "status", "--json"]:
        return subprocess.CompletedProcess(argv, 0, funnel, "")
    return subprocess.CompletedProcess(argv, 1, "", "unused")


def test_ffmpeg_argv_cuts_independent_three_second_segments(tmp_path: Path):
    source = tmp_path / "clip.mp4"
    argv = hls.ffmpeg_argv(
        "ffmpeg",
        source,
        {
            "width": 1280,
            "height": 720,
            "video_bitrate": "1500k",
            "audio_bitrate": "128k",
            "hls_time": 3,
            "fps": 24,
            "preset": "veryfast",
        },
        with_audio=True,
    )
    assert argv[argv.index("-g") + 1] == "72"
    assert "independent_segments" in argv
    assert argv[-1] == "main.m3u8"
    assert "seg_%03d.ts" in argv


def test_port_8096_is_refused():
    with pytest.raises(SystemExit, match="8096"):
        hls.listen_port({"port": 8096})


def test_funnel_json_matches_backend_port():
    report = hls.parse_funnel_status(
        FUNNEL_OK, port=8097, backend_host="127.0.0.1", expected_host="lab.tailnet.ts.net"
    )
    assert report["ok"] is True
    assert report["detail"].startswith("FUNNEL_OK")


def test_funnel_text_mismatch_names_the_other_port():
    text = "https://lab.tailnet.ts.net (Funnel on)\n|-- / proxy http://127.0.0.1:8096\n"
    report = hls.parse_funnel_status(text, port=8097, backend_host="127.0.0.1", expected_host="")
    assert report["ok"] is False
    assert "8096" in report["detail"]
    assert "8097" in report["detail"]


def test_funnel_off_when_status_is_empty():
    report = hls.parse_funnel_status("No serve config\n", port=8097, backend_host="127.0.0.1", expected_host="")
    assert report["detail"] == "FUNNEL_OFF"


def test_redact_hides_token_and_user_id():
    shown = hls.redact_target("/Users/user-1/Items/item-one?ApiKey=lab-token&AudioCodec=aac")
    assert "lab-token" not in shown
    assert "user-1" not in shown
    assert "REDACTED" in shown
    assert "{user}" in shown
    assert "AudioCodec=aac" in shown


def test_setup_encodes_and_rejects_a_funnel_pointed_at_jellyfin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JELLYFLAM3_CERT_API_KEY", "lab-token")
    monkeypatch.setenv("JELLYFLAM3_CERT_USER_ID", "user-1")
    cfg = _cfg(tmp_path)
    hls.configure_logging(Path(cfg["log_file"]))
    wrong = FUNNEL_OK.replace("8097", "8096")

    def run(*args, **kwargs):
        return _fake_run(*args, funnel=wrong, **kwargs)

    assert hls.command_setup(cfg, run) == 2
    catalog = json.loads((tmp_path / "hls" / "catalog.json").read_text(encoding="utf-8"))
    assert catalog["sheep"][0]["content_id"] == "item-one"
    assert catalog["sheep"][0]["run_time_ticks"] == 120_000_000
    assert (tmp_path / "hls" / "item-one" / "seg_000.ts").is_file()
    log_text = Path(cfg["log_file"]).read_text(encoding="utf-8")
    assert "FUNNEL_MISMATCH" in log_text
    assert "lab-token" not in log_text


def test_server_answers_channel_urls_and_redacts_the_log(tmp_path: Path):
    root = tmp_path / "hls"
    item = root / "item-one"
    item.mkdir(parents=True)
    (item / "main.m3u8").write_text("#EXTM3U\nseg_000.ts\n", encoding="utf-8")
    (item / "seg_000.ts").write_bytes(b"\x47" * 188)
    hls.write_catalog(
        root,
        [
            {
                "sheep": "electricsheep.169.00000",
                "content_id": "item-one",
                "run_time_ticks": 120_000_000,
                "playlist": "main.m3u8",
            }
        ],
    )
    hls.configure_logging(tmp_path / "cert-hls.log")
    catalog = hls.load_catalog(root)
    server = hls.CertHlsServer(("127.0.0.1", 0), catalog, root, "lab-token", "user-1")
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    try:
        public = urllib.request.urlopen(base + "/System/Info/Public", timeout=5)
        assert public.status == 200
        playlist = urllib.request.urlopen(
            base + "/Videos/item-one/main.m3u8?ApiKey=lab-token&AudioCodec=aac", timeout=5
        )
        assert b"#EXTM3U" in playlist.read()
        segment = urllib.request.urlopen(base + "/Videos/item-one/seg_000.ts", timeout=5)
        assert segment.status == 200
        assert segment.read(1) == b"\x47"
        items = urllib.request.Request(
            base + "/Users/user-1/Items?IncludeItemTypes=Movie,Video",
            headers={"Authorization": 'MediaBrowser Token="lab-token"'},
        )
        body = json.loads(urllib.request.urlopen(items, timeout=5).read())
        assert body["Items"][0]["Name"] == "electricsheep.169.00000"
        one = urllib.request.Request(
            base + "/Users/user-1/Items/item-one",
            headers={"Authorization": 'MediaBrowser Token="lab-token"'},
        )
        assert json.loads(urllib.request.urlopen(one, timeout=5).read())["RunTimeTicks"] == 120_000_000
        progress = urllib.request.Request(
            base + "/Sessions/Playing/Progress",
            data=b"{}",
            headers={
                "Authorization": 'MediaBrowser Token="lab-token"',
                "Content-Type": "application/json",
            },
            method="POST",
        )
        assert urllib.request.urlopen(progress, timeout=5).status == 204
        with pytest.raises(urllib.error.HTTPError) as denied:
            urllib.request.urlopen(base + "/Videos/item-one/main.m3u8", timeout=5)
        assert denied.value.code == 401
    finally:
        server.shutdown()
        server.server_close()
    log_text = (tmp_path / "cert-hls.log").read_text(encoding="utf-8")
    assert "lab-token" not in log_text
    assert "user-1" not in log_text
    assert "REDACTED" in log_text
    assert "GET /Videos/item-one/main.m3u8" in log_text
