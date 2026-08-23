"""Package layout checks for Roku VoD + Screensaver zips (Phase 3 RC)."""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOD = ROOT / "roku-channel"
SS = ROOT / "roku-screensaver"


def _zip_tree(src: Path, out: Path) -> list[str]:
    skip = {".gitkeep", ".DS_Store"}
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(src / "manifest", "manifest")
        for folder in ("source", "components", "images"):
            d = src / folder
            if not d.is_dir():
                continue
            for p in d.rglob("*"):
                if p.is_file() and p.name not in skip:
                    zf.write(p, p.relative_to(src).as_posix())
    return zipfile.ZipFile(out).namelist()


def test_roku_vod_tree_has_manifest_and_entry():
    assert (VOD / "manifest").is_file()
    text = (VOD / "manifest").read_text(encoding="utf-8")
    assert "title=JellyFlam3" in text
    assert (VOD / "source" / "main.brs").is_file()
    assert (VOD / "components" / "HomeScene.xml").is_file()
    assert (VOD / "components" / "RegistryPresets.brs").is_file()


def test_roku_screensaver_tree_has_manifest_and_entry():
    assert (SS / "manifest").is_file()
    text = (SS / "manifest").read_text(encoding="utf-8")
    assert "Screensaver" in text
    assert (SS / "source" / "main.brs").is_file()
    assert (SS / "components" / "ScreenSaverScene.xml").is_file()
    assert (SS / "components" / "RegistryPresets.brs").is_file()


def test_roku_vod_zip_is_archive_root(tmp_path: Path):
    names = _zip_tree(VOD, tmp_path / "jellyflam3-roku.zip")
    assert "manifest" in names
    assert "source/main.brs" in names
    assert not any(n.startswith("roku-channel/") for n in names)
    assert all("\\" not in n for n in names)


def test_roku_screensaver_zip_is_archive_root(tmp_path: Path):
    names = _zip_tree(SS, tmp_path / "jellyflam3-screensaver.zip")
    assert "manifest" in names
    assert "source/main.brs" in names
    assert not any(n.startswith("roku-screensaver/") for n in names)
    assert all("\\" not in n for n in names)


def test_roku_commercial_mode_does_not_query_tags():
    """Regression: Jellyfin Tags= comma filter emptied the lab flock."""
    text = (VOD / "components" / "JellyfinTask.brs").read_text(encoding="utf-8")
    assert "Tags=cc-by,public-domain,cc0" not in text
    assert "isCommercialSafe" in text
    assert "fetchItemsViaChildFolders" in text
    assert "mergeItemsById" in text
    assert "build_version=26" in (VOD / "manifest").read_text(encoding="utf-8")
    assert 'Version=""1.0.26""' in text


def test_roku_screensaver_expands_nested_library_folders():
    text = (SS / "components" / "StillsTask.brs").read_text(encoding="utf-8")
    assert "fetchStillsViaChildFolders" in text
    assert "mergeStillsById" in text
    assert "build_version=6" in (SS / "manifest").read_text(encoding="utf-8")
    assert 'Version=""1.0.6""' in text
