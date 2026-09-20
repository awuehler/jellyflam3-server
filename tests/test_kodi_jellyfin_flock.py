"""Unit tests for Kodi screensaver Jellyfin flock helper (no xbmc)."""

from __future__ import annotations

import json
import random
import urllib.error
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
            {
                "Id": "aa",
                "Name": "electricsheep.247.001",
                "Tags": ["cc-by"],
                "Overview": "License: cc-by\nAlias: frosty_swirles",
            },
            {"Id": "bb", "Name": "nc-sheep", "Tags": ["cc-by-nc"]},
        ]
    }
    seen = {"urls": []}

    def fake_get(url, api_key, timeout=20.0):
        seen["urls"].append(url)
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
    assert items[0]["alias"] == "frosty_swirles"
    video_urls = [u for u in seen["urls"] if "IncludeItemTypes=Movie" in u]
    assert video_urls
    assert all("Tags=" not in u for u in video_urls)
    assert all("Limit=5000" in u for u in video_urls)


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


def test_drop_item_and_repoll_rate_limit():
    items = [{"id": "aa", "title": "a", "url": "u"}, {"id": "bb", "title": "b", "url": "v"}]
    assert [i["id"] for i in jf.drop_item(items, "aa")] == ["bb"]
    assert jf.drop_item(items, "") == items
    assert jf.should_repoll_flock(None, 100.0) is True
    assert jf.should_repoll_flock(90.0, 100.0, min_sec=30.0) is False
    assert jf.should_repoll_flock(60.0, 100.0, min_sec=30.0) is True
    assert jf.FLOCK_REPOLL_MIN_SEC == 30.0
    assert jf.CLIENT_VERSION == "0.2.13"
    assert jf.FLOCK_INDEX_CAP == 313
    assert jf.FLOCK_FETCH_LIMIT == 5000
    h = jf.auth_header("secret")
    assert 'Client="JellyFlam3-Screensaver"' in h
    assert "Token=\"secret\"" in h


def test_screensaver_package_mentions_flock():
    text = (
        ROOT / "kodi-screensaver" / "screensaver.jellyflam3" / "default.py"
    ).read_text(encoding="utf-8")
    assert "jellyfin_flock" in text
    assert "fetch_flock" in text or "_load_flock" in text
    assert "_handle_dead_sheep" in text
    assert "should_repoll_flock" in text
    assert "onPlayBackError" in text
    settings = (
        ROOT / "kodi-screensaver" / "screensaver.jellyflam3" / "resources" / "settings.xml"
    ).read_text(encoding="utf-8")
    assert 'id="server_url"' in settings
    assert 'id="api_key"' in settings
    assert 'id="shuffle"' in settings
    assert 'default="true"' in settings
    assert 'id="title_mode"' in settings
    assert 'id="display_sink_url"' in settings
    assert 'id="display_sink_token"' in settings
    assert 'default="filename"' in settings
    assert 'id="flock_limit"' in settings
    assert 'default="313"' in settings
    assert "_title_mode" in text
    assert "_item_caption" in text
    assert "_show_caption" in text
    assert "_shuffle_enabled" in text
    assert "_ensure_shuffle_on" in text
    assert 'setSetting("shuffle", "true")' in text
    assert 'getSetting("shuffle")' in text
    assert "flock wrap refetch" in text
    assert "rotate_past" in text


def test_rotate_past_avoids_wrap_seam_repeat():
    items = [{"id": "aa"}, {"id": "bb"}, {"id": "cc"}]
    assert [i["id"] for i in jf.rotate_past(items, "zz")] == ["aa", "bb", "cc"]
    rotated = jf.rotate_past(items, "aa")
    assert rotated[0]["id"] != "aa"
    assert {i["id"] for i in rotated} == {"aa", "bb", "cc"}
    assert len(jf.rotate_past([{"id": "aa"}], "aa")) == 1


def test_display_title_filename_vs_alias():
    assert jf.overview_keyed_value("License: cc-by\nAlias: frosty_swirles", "Alias:") == "frosty_swirles"
    assert jf.overview_keyed_value("", "Alias:") == ""
    assert jf.display_title("electricsheep.247.001", "frosty_swirles", "filename") == "electricsheep.247.001"
    assert jf.display_title("electricsheep.247.001", "frosty_swirles", "alias") == "frosty_swirles"
    assert jf.display_title("electricsheep.247.001", "", "alias") == "electricsheep.247.001"
    assert jf.item_alias({"Overview": "Alias: angry_bardeen"}) == "angry_bardeen"


def test_prune_to_cap_keeps_small_lists():
    small = [{"id": "a"}, {"id": "b"}]
    assert jf.prune_to_cap(small, cap=313) == small
    assert jf.prune_to_cap([], cap=313) == []


def test_prune_to_cap_samples_down_to_313():
    items = [{"id": str(i)} for i in range(400)]
    rng = random.Random(7)
    out = jf.prune_to_cap(items, cap=313, rng=rng)
    assert len(out) == 313
    ids = {it["id"] for it in out}
    assert ids <= {str(i) for i in range(400)}
    again = jf.prune_to_cap(items, cap=313, rng=random.Random(7))
    assert [it["id"] for it in again] == [it["id"] for it in out]


def test_fetch_flock_prunes_after_merge(monkeypatch):
    payload = {
        "Items": [
            {"Id": str(i), "Name": "sheep-%s" % i, "Tags": []} for i in range(400)
        ]
    }

    def fake_get(url, api_key, timeout=20.0):
        if "IncludeItemTypes=Folder" in url:
            return {"Items": []}
        return payload

    monkeypatch.setattr(jf, "http_get_json", fake_get)
    items = jf.fetch_flock(
        base_url="http://jf:8096",
        api_key="k",
        user_id="u1",
        library_id="lib1",
    )
    assert len(items) == 313
    assert {it["id"] for it in items} <= {str(i) for i in range(400)}


def test_classify_fetch_error_and_probe(monkeypatch):
    auth = urllib.error.HTTPError("http://jf/x", 401, "no", hdrs=None, fp=None)
    forbidden = urllib.error.HTTPError("http://jf/x", 403, "no", hdrs=None, fp=None)
    boom = urllib.error.HTTPError("http://jf/x", 500, "no", hdrs=None, fp=None)
    assert jf.classify_fetch_error(auth) == "auth"
    assert jf.classify_fetch_error(forbidden) == "auth"
    assert jf.classify_fetch_error(boom) == "unreachable"
    assert jf.classify_fetch_error(urllib.error.URLError("timed out")) == "unreachable"

    class _Resp:
        status = 200

        def getcode(self):
            return 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(jf.urllib.request, "urlopen", lambda *a, **k: _Resp())
    assert jf.probe_jellyfin("http://jf:8096") is True
    assert jf.probe_jellyfin("") is False


def test_stem_tuple_sink_and_vote_due():
    assert jf.stem_from_media_path("/media/sheep/by-generation/247/electricsheep.247.00505.mp4") == (
        "electricsheep.247.00505"
    )
    assert jf.is_tuple_sheep("/media/sheep/by-generation/tuple/electricsheep.tuple.a_b.mp4", "") is True
    assert jf.is_tuple_sheep("", "electricsheep.tuple.aa_bb") is True
    assert jf.is_tuple_sheep("/media/sheep/by-generation/247/electricsheep.247.00505.mp4", "electricsheep.247.00505") is False
    assert jf.sink_url_from_jellyfin("http://192.168.156.162:8096/") == "http://192.168.156.162:8791"
    assert jf.sink_url_from_jellyfin("") == ""
    assert jf.vote_overlay_due(7.0, dismissed=False, is_tuple=False) is True
    assert jf.vote_overlay_due(7.1, dismissed=False, is_tuple=False) is False
    assert jf.vote_overlay_due(3.0, dismissed=True, is_tuple=False) is False
    assert jf.vote_overlay_due(3.0, dismissed=False, is_tuple=True) is False
    assert jf.vote_overlay_due(0.0, dismissed=False, is_tuple=False) is False
    assert jf.VOTE_REMAIN_SEC == 7.0


def test_post_sheep_vote_requires_sink_and_token():
    assert jf.post_sheep_vote("", "tok", {"kind": "love"})["ok"] is False
    assert jf.post_sheep_vote("http://pi:8791", "", {"kind": "love"})["ok"] is False
    seen = {}

    class _Resp:
        status = 200

        def getcode(self):
            return 200

        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_open(req, timeout=8.0):
        seen["url"] = req.full_url
        seen["token"] = req.headers.get("X-jellyflam3-token") or req.headers.get("X-JellyFlam3-Token")
        return _Resp()

    with patch.object(jf.urllib.request, "urlopen", fake_open):
        out = jf.post_sheep_vote("http://pi:8791/", "secret", {"stem": "electricsheep.247.001", "kind": "love"})
    assert out["ok"] is True
    assert seen["url"].endswith("/v1/sheep-votes")
    assert seen["token"] == "secret"

