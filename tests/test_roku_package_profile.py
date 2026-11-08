"""Office Settings package-profile capture and literal packaging helpers."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from pipeline.display_profile_sink import STATE, Handler
from pipeline.roku_package_profile import (
    load_package_profile,
    normalize_package_profile,
    save_package_profile,
    status_payload,
)


def _serve(tmp_path: Path, token: str) -> ThreadingHTTPServer:
    STATE.profiles_dir = tmp_path / "profiles"
    STATE.profiles_dir.mkdir(parents=True, exist_ok=True)
    STATE.package_profile_path = tmp_path / "roku-package-profile.json"
    STATE.token = token
    STATE.jellyfin_api_key = ""
    STATE.allow_unauthenticated = False
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


def _url(httpd: ThreadingHTTPServer, path: str) -> str:
    return f"http://127.0.0.1:{httpd.server_address[1]}{path}"


def _reset() -> None:
    STATE.token = ""
    STATE.jellyfin_api_key = ""
    STATE.allow_unauthenticated = False


def test_normalize_requires_connection_fields():
    with pytest.raises(ValueError, match="missing apiKey"):
        normalize_package_profile(
            {"baseUrl": "https://rpi-jellyflam3-16a.tail801167.ts.net", "userId": "u1"}
        )


def test_save_and_status_hide_secrets(tmp_path: Path):
    path = tmp_path / "roku-package-profile.json"
    save_package_profile(
        path,
        {
            "baseUrl": "https://rpi-jellyflam3-16a.tail801167.ts.net",
            "apiKey": "secret-key-value",
            "userId": "user-guid",
            "libraryId": "lib-guid",
            "streamMode": "hls",
            "mp4Fallback": "false",
            "channelVersion": "1.0.68",
        },
    )
    loaded = load_package_profile(path)
    assert loaded["streamMode"] == "hls"
    assert loaded["apiKey"] == "secret-key-value"
    status = status_payload(path)
    assert status["ok"] is True
    assert status["baseUrlKind"] == "funnel"
    assert status["streamMode"] == "hls"
    assert status["hasApiKey"] is True
    assert "secret-key-value" not in json.dumps(status)
    assert "user-guid" not in json.dumps(status)


def test_sink_stores_package_profile(tmp_path: Path):
    httpd = _serve(tmp_path, token="sekrit")
    try:
        body = json.dumps(
            {
                "baseUrl": "https://rpi-jellyflam3-16a.tail801167.ts.net",
                "apiKey": "secret-key-value",
                "userId": "user-guid",
                "streamMode": "hls",
                "mp4Fallback": "false",
            }
        ).encode("utf-8")
        req = Request(
            _url(httpd, "/v1/roku-package-profile"),
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-JellyFlam3-Token": "sekrit",
            },
            method="POST",
        )
        with urlopen(req, timeout=5) as resp:
            out = json.loads(resp.read().decode("utf-8"))
        assert out["ok"] is True
        assert out["baseUrlKind"] == "funnel"
        assert "secret-key-value" not in json.dumps(out)
        loaded = load_package_profile(STATE.package_profile_path)
        assert loaded["baseUrl"].endswith("ts.net")
        assert loaded["streamMode"] == "hls"

        with urlopen(
            Request(
                _url(httpd, "/v1/roku-package-profile"),
                headers={"X-JellyFlam3-Token": "sekrit"},
            ),
            timeout=5,
        ) as resp:
            status = json.loads(resp.read().decode("utf-8"))
        assert status["exists"] is True
        assert status["streamMode"] == "hls"
    finally:
        httpd.shutdown()
        _reset()


def test_sink_rejects_package_profile_without_token(tmp_path: Path):
    httpd = _serve(tmp_path, token="sekrit")
    try:
        body = json.dumps(
            {
                "baseUrl": "https://example.ts.net",
                "apiKey": "k",
                "userId": "u",
            }
        ).encode("utf-8")
        try:
            urlopen(
                Request(
                    _url(httpd, "/v1/roku-package-profile"),
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=5,
            )
            raise AssertionError("expected 401")
        except HTTPError as err:
            assert err.code == 401
    finally:
        httpd.shutdown()
        _reset()
