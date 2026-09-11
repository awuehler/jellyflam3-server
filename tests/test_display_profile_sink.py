"""HTTP tests for pipeline.display_profile_sink (LAN profile upsert)."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from pipeline.display_profile_sink import STATE, Handler


def _serve(
    tmp_path: Path,
    token: str,
    *,
    allow_unauthenticated: bool = False,
    media_root: Path | None = None,
) -> ThreadingHTTPServer:
    STATE.profiles_dir = tmp_path
    STATE.token = token
    STATE.allow_unauthenticated = allow_unauthenticated
    if media_root is not None:
        STATE.media_root = media_root
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def _url(httpd: ThreadingHTTPServer, path: str) -> str:
    return f"http://127.0.0.1:{httpd.server_address[1]}{path}"


def _reset_state() -> None:
    STATE.token = ""
    STATE.allow_unauthenticated = False
    STATE.media_root = Path("/media/sheep")


def test_healthz_unauthenticated(tmp_path: Path):
    httpd = _serve(tmp_path, token="sekrit")
    try:
        with urlopen(_url(httpd, "/healthz"), timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["ok"] is True
        assert body["service"] == "display_profile_sink"
    finally:
        httpd.shutdown()
        _reset_state()


def test_empty_token_denies_api_without_lab_flag(tmp_path: Path):
    httpd = _serve(tmp_path, token="", allow_unauthenticated=False)
    try:
        try:
            urlopen(_url(httpd, "/v1/display-profiles"), timeout=5)
            raise AssertionError("expected 401 when token unset and auth fail-closed")
        except HTTPError as err:
            assert err.code == 401
    finally:
        httpd.shutdown()
        _reset_state()


def test_list_requires_token_then_upsert(tmp_path: Path):
    httpd = _serve(tmp_path, token="sekrit")
    try:
        try:
            urlopen(_url(httpd, "/v1/display-profiles"), timeout=5)
            raise AssertionError("expected 401 without token")
        except HTTPError as err:
            assert err.code == 401

        payload = json.dumps(
            {
                "client": "JellyFlam3",
                "deviceId": "roku-lab",
                "videoMode": "1080p",
                "displaySummary": "lab tv",
            }
        ).encode("utf-8")
        req = Request(
            _url(httpd, "/v1/display-profiles"),
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-JellyFlam3-Token": "sekrit",
            },
        )
        with urlopen(req, timeout=5) as resp:
            posted = json.loads(resp.read().decode("utf-8"))
        assert posted["ok"] is True
        assert posted["deviceId"] == "roku-lab"

        list_req = Request(
            _url(httpd, "/v1/display-profiles"),
            headers={"X-JellyFlam3-Token": "sekrit"},
        )
        with urlopen(list_req, timeout=5) as resp:
            listed = json.loads(resp.read().decode("utf-8"))
        assert listed["ok"] is True
        assert len(listed["profiles"]) == 1
    finally:
        httpd.shutdown()
        _reset_state()


def test_main_refuses_non_loopback_without_token(tmp_path: Path, monkeypatch):
    from pipeline.display_profile_sink import main

    monkeypatch.delenv("DISPLAY_SINK_TOKEN", raising=False)
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("paths: {}\n", encoding="utf-8")
    rc = main(
        [
            "--config",
            str(cfg),
            "--host",
            "0.0.0.0",
            "--port",
            "8799",
        ]
    )
    assert rc == 2
    _reset_state()


def _catalog(tmp_path: Path) -> Path:
    media = tmp_path / "media"
    gen = media / "by-generation" / "247"
    gen.mkdir(parents=True)
    stem = "electricsheep.247.00505"
    (gen / f"{stem}.mp4").write_bytes(b"x")
    (gen / f"{stem}.jellyflam3.json").write_text(
        json.dumps({"id": stem, "alias": "frosty_swirles", "type": "loop"}) + "\n",
        encoding="utf-8",
    )
    return media


def test_sheep_votes_require_token_then_increment(tmp_path: Path):
    media = _catalog(tmp_path)
    httpd = _serve(tmp_path / "profiles", token="sekrit", media_root=media)
    try:
        payload = json.dumps({"stem": "electricsheep.247.00505", "kind": "like"}).encode(
            "utf-8"
        )
        try:
            urlopen(
                Request(
                    _url(httpd, "/v1/sheep-votes"),
                    data=payload,
                    method="POST",
                    headers={"Content-Type": "application/json"},
                ),
                timeout=5,
            )
            raise AssertionError("expected 401 without token")
        except HTTPError as err:
            assert err.code == 401

        req = Request(
            _url(httpd, "/v1/sheep-votes"),
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-JellyFlam3-Token": "sekrit",
            },
        )
        with urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        assert body["ok"] is True
        assert body["viewer_feedback"]["likes"] == 1
        assert body["viewer_feedback"]["share_candidate"] is True
        sidecar = json.loads(
            (
                media
                / "by-generation"
                / "247"
                / "electricsheep.247.00505.jellyflam3.json"
            ).read_text(encoding="utf-8")
        )
        assert sidecar["alias"] == "frosty_swirles"
        assert sidecar["viewer_feedback"]["votes"] == 1
    finally:
        httpd.shutdown()
        _reset_state()


def test_sheep_votes_unknown_stem_404(tmp_path: Path):
    media = _catalog(tmp_path)
    httpd = _serve(tmp_path / "profiles", token="sekrit", media_root=media)
    try:
        req = Request(
            _url(httpd, "/v1/sheep-votes"),
            data=json.dumps({"stem": "missing.sheep", "kind": "vote"}).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-JellyFlam3-Token": "sekrit",
            },
        )
        try:
            urlopen(req, timeout=5)
            raise AssertionError("expected 404")
        except HTTPError as err:
            assert err.code == 404
            body = json.loads(err.read().decode("utf-8"))
            assert body["ok"] is False
    finally:
        httpd.shutdown()
        _reset_state()
