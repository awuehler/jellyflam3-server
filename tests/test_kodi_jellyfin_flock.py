"""Unit tests for Kodi screensaver Jellyfin flock helper (no xbmc)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIB = ROOT / "kodi-screensaver" / "screensaver.jellyflam3" / "resources" / "lib"
import sys

sys.path.insert(0, str(LIB))

import jellyfin_flock as jf  # noqa: E402


def test_mp4_stream_url():
    url = jf.mp4_stream_url("http://host:8096/", "abc", "key/1")
    assert url.startswith("http://host:8096/Videos/abc/stream.mp4?")
    assert "Static=true" in url
    assert "api_key=" in url


def test_commercial_filter():
    items = [
        {"Id": "1", "Tags": ["cc-by"]},
        {"Id": "2", "Tags": ["cc-by-nc"]},
        {"Id": "3", "Tags": []},
        {"Id": "4", "Tags": ["public-domain"]},
    ]
    assert [i["Id"] for i in jf.filter_commercial(items, False)] == ["1", "2", "3", "4"]
    assert [i["Id"] for i in jf.filter_commercial(items, True)] == ["1", "4"]


def test_fetch_flock_maps_mp4(monkeypatch):
    payload = {
        "Items": [
            {"Id": "aa", "Name": "electricsheep.247.001", "Tags": ["cc-by"]},
            {"Id": "bb", "Name": "nc-sheep", "Tags": ["cc-by-nc"]},
        ]
    }
    seen = {}

    def fake_get(url, api_key, timeout=20.0):
        seen["url"] = url
        assert "Users/u1/Items" in url
        if "IncludeItemTypes=Folder" in url:
            return {"Items": []}
        assert "ParentId=lib1" in url
        # Regression: Jellyfin Tags= comma filter emptied the lab flock.
        assert "Tags=" not in url
        return payload

    monkeypatch.setattr(jf, "http_get_json", fake_get)
    items = jf.fetch_flock(
        base_url="http://jf:8096",
        api_key="k",
        user_id="u1",
        library_id="lib1",
        commercial_mode=True,
    )
    assert len(items) == 1
    assert items[0]["id"] == "aa"
    assert "stream.mp4" in items[0]["url"]
    assert items[0]["title"] == "electricsheep.247.001"
    assert "Tags=" not in seen["url"]


def test_fetch_flock_expands_child_folders(monkeypatch):
    calls: list[str] = []

    def fake_get(url, api_key, timeout=20.0):
        calls.append(url)
        if "IncludeItemTypes=Folder" in url:
            return {"Items": [{"Id": "gen247", "Name": "247"}]}
        if "ParentId=gen247" in url:
            return {
                "Items": [
                    {"Id": "aa", "Name": "electricsheep.247.001", "Tags": ["cc-by"]},
                    {"Id": "bb", "Name": "electricsheep.247.002", "Tags": ["cc-by"]},
                ]
            }
        if "ParentId=lib1" in url and "IncludeItemTypes=Movie%2CVideo" in url:
            # Lab bug: flat ParentId returns a partial flock (1 of N).
            return {
                "Items": [
                    {"Id": "aa", "Name": "electricsheep.247.001", "Tags": ["cc-by"]},
                ]
            }
        raise AssertionError("unexpected url: %s" % url)

    monkeypatch.setattr(jf, "http_get_json", fake_get)
    items = jf.fetch_flock(
        base_url="http://jf:8096",
        api_key="k",
        user_id="u1",
        library_id="lib1",
    )
    assert [i["id"] for i in items] == ["aa", "bb"]
    assert any("IncludeItemTypes=Folder" in u for u in calls)


def test_fetch_flock_partial_flat_still_walks_folders(monkeypatch):
    """Regression: non-empty flat result must not skip nested by-generation/ sheep."""
    calls: list[str] = []

    def fake_get(url, api_key, timeout=20.0):
        calls.append(url)
        if "IncludeItemTypes=Folder" in url:
            return {
                "Items": [
                    {"Id": "gen242", "Name": "242"},
                    {"Id": "gen243", "Name": "243"},
                ]
            }
        if "ParentId=gen242" in url:
            return {"Items": [{"Id": "only242", "Name": "sheep-242", "Tags": []}]}
        if "ParentId=gen243" in url:
            return {"Items": [{"Id": "only243", "Name": "sheep-243", "Tags": []}]}
        if "ParentId=lib1" in url and "IncludeItemTypes=Movie%2CVideo" in url:
            return {"Items": [{"Id": "only242", "Name": "sheep-242", "Tags": []}]}
        raise AssertionError("unexpected url: %s" % url)

    monkeypatch.setattr(jf, "http_get_json", fake_get)
    items = jf.fetch_flock(
        base_url="http://jf:8096",
        api_key="k",
        user_id="u1",
        library_id="lib1",
    )
    assert [i["id"] for i in items] == ["only242", "only243"]
    assert sum(1 for u in calls if "IncludeItemTypes=Folder" in u) == 1


def test_cc_by_hyphen_is_commercial_safe():
    assert jf.is_commercial_safe(["cc-by"])
    assert jf.is_commercial_safe(["CC-BY"])
    assert not jf.is_commercial_safe(["cc-by-nc"])
    assert not jf.is_commercial_safe([])


def test_auth_header_screensaver_client():
    h = jf.auth_header("secret")
    assert 'Client="JellyFlam3-Screensaver"' in h
    assert "Token=\"secret\"" in h


def test_screensaver_package_mentions_flock():
    text = (
        ROOT / "kodi-screensaver" / "screensaver.jellyflam3" / "default.py"
    ).read_text(encoding="utf-8")
    assert "jellyfin_flock" in text
    assert "fetch_flock" in text or "_load_flock" in text
    settings = (
        ROOT / "kodi-screensaver" / "screensaver.jellyflam3" / "resources" / "settings.xml"
    ).read_text(encoding="utf-8")
    assert 'id="server_url"' in settings
    assert 'id="api_key"' in settings
