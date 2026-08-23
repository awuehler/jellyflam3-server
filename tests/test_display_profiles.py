import json
from pathlib import Path

import pytest

from pipeline.display_profiles import (
    list_profiles,
    normalize_profile,
    profile_filename,
    sanitize_id,
    upsert_profile,
)


def test_sanitize_and_filename():
    assert sanitize_id("abc/def") == "abc_def"
    assert profile_filename("JellyFlam3", "dev-1!") == "JellyFlam3-dev-1.json"


def test_upsert_separate_screens(tmp_path: Path):
    a = upsert_profile(
        tmp_path,
        {
            "client": "JellyFlam3",
            "deviceId": "roku-a",
            "videoMode": "1080p",
            "displaySummary": "tv-a",
        },
    )
    b = upsert_profile(
        tmp_path,
        {
            "client": "JellyFlam3",
            "deviceId": "roku-b",
            "videoMode": "2160p30",
            "displaySummary": "tv-b",
        },
    )
    kodi = upsert_profile(
        tmp_path,
        {
            "client": "Kodi",
            "deviceId": "living-room",
            "platform": "linux",
            "displaySummary": "kodi lr",
        },
    )
    assert a.name != b.name
    assert "Kodi" in kodi.name
    items = list_profiles(tmp_path)
    assert len(items) == 3
    # Re-probe same Roku upserts, does not add a fourth file
    upsert_profile(
        tmp_path,
        {
            "client": "JellyFlam3",
            "deviceId": "roku-a",
            "videoMode": "1080p60",
            "displaySummary": "tv-a-updated",
        },
    )
    assert len(list_profiles(tmp_path)) == 3
    data = json.loads(a.read_text(encoding="utf-8"))
    assert data["videoMode"] == "1080p60"
    assert data["displaySummary"] == "tv-a-updated"


def test_normalize_requires_ids():
    with pytest.raises(ValueError):
        normalize_profile({"client": "JellyFlam3"})
    with pytest.raises(ValueError):
        normalize_profile({"deviceId": "x"})


def test_normalize_roku_formatjson_lowercase_keys():
    """Roku FormatJson emits lowercase AA keys (deviceid, not deviceId)."""
    out = normalize_profile(
        {
            "client": "JellyFlam3",
            "deviceid": "abc-channel-client-id",
            "devicemodel": "8000X",
            "videomode": "1080p",
            "displaysummary": "1920x1080 mode=1080p",
            "channelversion": "1.0.23",
            "schemaversion": 1,
        }
    )
    assert out["deviceId"] == "abc-channel-client-id"
    assert out["deviceModel"] == "8000X"
    assert out["videoMode"] == "1080p"
    assert out["displaySummary"] == "1920x1080 mode=1080p"
    assert out["channelVersion"] == "1.0.23"
    assert out["schemaVersion"] == 1
