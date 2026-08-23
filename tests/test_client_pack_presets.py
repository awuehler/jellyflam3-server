"""Furnace packaging presets for Roku/Kodi client zips."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _import_presets():
    import sys

    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import client_pack_presets as cpp

    return cpp


def test_is_furnace_host_false_without_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cpp = _import_presets()
    monkeypatch.chdir(tmp_path)
    assert cpp.is_furnace_host(tmp_path) is False


def test_is_furnace_host_true_with_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cpp = _import_presets()
    (tmp_path / "secrets.env").write_text(
        "JELLYFIN_URL=http://192.168.1.100:8096\nJELLYFIN_API_KEY=abc123\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert cpp.is_furnace_host(tmp_path) is True


def test_apply_kodi_settings_sets_defaults(tmp_path: Path):
    cpp = _import_presets()
    settings = tmp_path / "settings.xml"
    settings.write_text(
        """<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<settings>
  <setting id="server_url" type="text" label="Jellyfin URL" default=""/>
  <setting id="api_key" type="text" label="API key" default=""/>
  <setting id="user_id" type="text" label="User id" default=""/>
  <setting id="library_id" type="text" label="Library id" default=""/>
</settings>
""",
        encoding="utf-8",
    )
    cpp.apply_kodi_settings(
        settings,
        {
            "baseUrl": "http://192.168.1.100:8096",
            "apiKey": "secret-key",
            "userId": "user-guid",
            "libraryId": "lib-guid",
        },
    )
    text = settings.read_text(encoding="utf-8")
    assert 'id="server_url"' in text and 'default="http://192.168.1.100:8096"' in text
    assert 'default="secret-key"' in text
    assert 'default="user-guid"' in text
    assert 'default="lib-guid"' in text


def test_write_roku_registry_dir(tmp_path: Path):
    cpp = _import_presets()
    out = cpp.write_roku_registry_dir(
        tmp_path / "registry",
        {
            "baseUrl": "http://example:8096",
            "apiKey": "k",
            "userId": "u",
            "libraryId": "l",
            "commercialMode": "false",
            "streamMode": "mp4",
            "shuffleFlock": "false",
        },
    )
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["baseUrl"] == "http://example:8096"
    assert data["apiKey"] == "k"


def test_prepare_packaging_skips_without_furnace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cpp = _import_presets()
    monkeypatch.chdir(tmp_path)
    assert (
        cpp.prepare_packaging(
            config=tmp_path / "configs" / "jellyflam3.yaml",
            root=tmp_path,
            roku_registry=tmp_path / "registry",
        )
        is False
    )


def test_prepare_packaging_writes_targets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cpp = _import_presets()
    (tmp_path / "secrets.env").write_text(
        "JELLYFIN_URL=http://192.168.1.100:8096\nJELLYFIN_API_KEY=abc123\n",
        encoding="utf-8",
    )
    settings = tmp_path / "settings.xml"
    settings.write_text(
        '<?xml version="1.0"?><settings><setting id="server_url" default=""/></settings>',
        encoding="utf-8",
    )
    fake = {
        "baseUrl": "http://192.168.1.100:8096",
        "apiKey": "abc123",
        "userId": "u1",
        "libraryId": "l1",
        "commercialMode": "false",
        "streamMode": "mp4",
        "shuffleFlock": "false",
    }
    with patch.object(cpp, "fetch_roku_settings", return_value=fake):
        ok = cpp.prepare_packaging(
            config=tmp_path / "configs" / "jellyflam3.yaml",
            root=tmp_path,
            roku_registry=tmp_path / "registry",
            kodi_settings=settings,
        )
    assert ok is True
    assert (tmp_path / "registry" / "jellyflam3-presets.json").is_file()
    assert 'default="http://192.168.1.100:8096"' in settings.read_text(encoding="utf-8")


def test_roku_packages_include_registry_presets_helper():
    vod = (ROOT / "roku-channel" / "components" / "RegistryPresets.brs").read_text(encoding="utf-8")
    ss = (ROOT / "roku-screensaver" / "components" / "RegistryPresets.brs").read_text(encoding="utf-8")
    assert "applyJellyFlam3PackPresets" in vod
    assert vod.strip() == ss.strip()
