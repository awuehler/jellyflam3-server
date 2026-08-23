"""Package checks for screensaver.jellyflam3 (Phase 3 guide 02, tasks 1-4)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "kodi-screensaver" / "screensaver.jellyflam3"
ADDON_XML = ADDON / "addon.xml"


def test_addon_xml_screensaver_entry():
    tree = ET.parse(ADDON_XML)
    root = tree.getroot()
    assert root.attrib["id"] == "screensaver.jellyflam3"
    assert root.attrib["version"]
    req = root.find("requires/import")
    assert req is not None
    assert req.attrib["addon"] == "xbmc.python"
    assert req.attrib["version"] == "3.0.1"
    ext = root.find("extension[@point='xbmc.ui.screensaver']")
    assert ext is not None
    assert ext.attrib["library"] == "default.py"


def test_screensaver_entry_files_exist():
    assert (ADDON / "default.py").is_file()
    text = (ADDON / "default.py").read_text(encoding="utf-8")
    assert "CancelAlarm" in text
    assert "sssssscreensaver" in text
    assert "Player.SetRepeat" in text
    assert "RepeatOne" in text
    assert "onAction" in text
    assert "play(url, listitem, True)" in text or "windowed=True" in text
    assert "doModal" in text
    assert "jellyfin_flock" in text
    assert "def onPlayBackEnded" in text  # signals advance only
    assert "Action(Fullscreen)" not in text
    skin = (ADDON / "resources" / "skins" / "default" / "1080i" / "fallback.xml").read_text(
        encoding="utf-8"
    )
    assert "videowindow" in skin
    assert 'id="90"' in skin  # focus sink (videowindow cannot focus)
    # videowindow must be last so windowed Player is not covered
    assert skin.rfind("videowindow") > skin.rfind('id="90"')
    assert (ADDON / "resources" / "icon.png").is_file()
    assert (ADDON / "resources" / "fanart.jpg").is_file()
    for n in ("screenshot-01.jpg", "screenshot-02.jpg", "screenshot-03.jpg"):
        assert (ADDON / "resources" / n).is_file()
    assert "placeholder.mp4" not in text
    assert "testsrc" not in text


def test_addon_xml_lists_fanart_and_screenshots():
    tree = ET.parse(ADDON_XML)
    assets = tree.getroot().find("extension[@point='xbmc.addon.metadata']/assets")
    assert assets is not None
    assert assets.find("fanart") is not None
    shots = assets.findall("screenshot")
    assert len(shots) == 3


def _package_skip(path: Path) -> bool:
    if path.name in {".gitkeep", ".DS_Store"}:
        return True
    if path.suffix == ".pyc":
        return True
    if "__pycache__" in path.parts:
        return True
    if "posters" in path.parts:
        return True
    return False


def test_package_zip_has_addon_root(tmp_path: Path):
    """Zip layout is screensaver.jellyflam3/... as Kodi install-from-zip expects."""
    out = tmp_path / "screensaver.jellyflam3.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
        for p in ADDON.rglob("*"):
            if p.is_file() and not _package_skip(p):
                zf.write(p, (Path("screensaver.jellyflam3") / p.relative_to(ADDON)).as_posix())
    names = zipfile.ZipFile(out).namelist()
    assert "screensaver.jellyflam3/addon.xml" in names
    assert "screensaver.jellyflam3/default.py" in names
    assert "screensaver.jellyflam3/resources/icon.png" in names
    assert "screensaver.jellyflam3/resources/fanart.jpg" in names
    assert "screensaver.jellyflam3/resources/screenshot-01.jpg" in names
    assert not any(n.startswith("addon.xml") for n in names)
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    assert not any("/posters/" in n for n in names)
    info = zipfile.ZipFile(out).getinfo("screensaver.jellyflam3/addon.xml")
    assert info.compress_type == zipfile.ZIP_STORED


def test_package_script_excludes_pycache(tmp_path: Path):
    """Regression: dev artifacts in zip break Kodi install-from-zip."""
    pyc_dir = ADDON / "resources" / "lib" / "__pycache__"
    pyc_dir.mkdir(parents=True, exist_ok=True)
    pyc = pyc_dir / "jellyfin_flock.cpython-313.pyc"
    pyc.write_bytes(b"fake")
    try:
        out = tmp_path / "screensaver.jellyflam3.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
            for p in ADDON.rglob("*"):
                if p.is_file() and not _package_skip(p):
                    zf.write(p, (Path("screensaver.jellyflam3") / p.relative_to(ADDON)).as_posix())
        names = zipfile.ZipFile(out).namelist()
        assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
    finally:
        shutil.rmtree(pyc_dir, ignore_errors=True)
