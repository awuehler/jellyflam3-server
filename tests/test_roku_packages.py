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
    assert "supports_input_launch=1" in text
    assert "rsg_version=1.3" in text
    assert "subtitle=" not in text
    assert "splash_screen_hd=" in text
    assert "mm_icon_focus_hd=" in text
    assert "splash_screen_sd=" not in text
    assert "mm_icon_focus_sd=" not in text
    assert (VOD / "source" / "main.brs").is_file()
    main = (VOD / "source" / "main.brs").read_text(encoding="utf-8")
    assert 'CreateObject("roInput")' in main
    assert "m.input = CreateObject" in main
    assert "m.input.SetMessagePort(m.port)" in main
    assert 'type(msg) = "roInputEvent"' in main
    assert "msg.IsInput()" in main
    assert "msg.GetInfo()" in main
    assert 'info.DoesExist("mediatype")' in main
    assert 'info.DoesExist("contentid")' in main
    assert "mediaType = info.mediatype" in main
    assert "contentId = info.contentid" in main
    assert 'signalBeacon("AppLaunchComplete")' not in main
    settings = (VOD / "components" / "SettingsScreen.brs").read_text(encoding="utf-8")
    home = (VOD / "components" / "HomeScene.brs").read_text(encoding="utf-8")
    assert 'createObject("roSGNode", "KeyboardDialog")' not in settings
    assert 'createObject("roSGNode", "StandardKeyboardDialog")' in settings
    assert 'signalBeacon("AppDialogInitiate")' in home
    assert 'signalBeacon("AppDialogComplete")' in home
    assert "function handleDeepLink" in home
    assert "args.contentid" in home
    assert "args.mediatype" in home or "args.mediaType" in home
    assert 'if state = "ready" then m.homeReady = true' in home
    assert "if m.homeReady <> true and m.launchCredentialDialog <> true" in home
    assert 'CreateObject("roAppMemoryMonitor")' in main
    assert "EnableMemoryWarningEvent(true)" in main
    assert "GetMemoryLimitPercent()" in main
    assert "GetChannelMemoryLimit()" in main
    assert "GetChannelAvailableMemory()" in main
    assert "EnableLowGeneralMemoryEvent(true)" in main
    assert 'msgType = "roAppMemoryNotificationEvent"' in main
    assert 'msgType = "roDeviceInfoEvent"' in main
    assert (VOD / "components" / "HomeScene.xml").is_file()
    assert (VOD / "components" / "RegistryPresets.brs").is_file()


def test_roku_vod_launch_beacon_marks_an_operable_screen():
    """Roku measures AppLaunchComplete against the first render pass after it fires."""
    main = (VOD / "source" / "main.brs").read_text(encoding="utf-8")
    home = (VOD / "components" / "HomeScene.brs").read_text(encoding="utf-8")
    assert 'signalBeacon("AppLaunchComplete")' not in main
    assert "sub signalAppLaunchComplete()" in home
    assert 'm.top.signalBeacon("AppLaunchComplete")' in home
    assert "if m.launchBeaconFired = true then return" in home
    # Dialog time is excluded from launch time, so the beacon waits for the dialog.
    assert "if m.launchCredentialDialog = true then return" in home
    # A furnace that never answers still has to produce a beacon inside 15 s.
    assert "sub startLaunchBeaconGuard()" in home
    assert "sub onLaunchBeaconGuard()" in home
    assert 'if state = "ready" or state = "empty" or state = "error" or state = "unreachable"' in home


def test_roku_vod_stream_fallback_never_escalates_to_hls():
    """Cert 3.6: Jellyfin emits the whole keyframe-sparse clip as HLS segment 0."""
    player = (VOD / "components" / "PlayerScreen.brs").read_text(encoding="utf-8")
    assert 'if m.streamFormat = "hls" and m.mp4Url <> ""' in player
    assert 'else if m.streamFormat = "mp4" and m.hlsUrl <> ""' not in player
    assert 'altFmt = "hls"' not in player


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


def test_roku_packagers_exclude_all_numbered_source_art():
    ps1 = (ROOT / "scripts" / "package_roku_channel.ps1").read_text(encoding="utf-8")
    sh = (ROOT / "scripts" / "package_roku_channel.sh").read_text(encoding="utf-8")
    assert r"-\d{2}\.png$" in ps1
    assert "images/*-[0-9][0-9].png" in sh
    assert "p.stem[-2:].isdigit()" in sh


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
    assert "build_version=51" in (VOD / "manifest").read_text(encoding="utf-8")
    assert 'Version=""1.0.51""' in text
    home = (VOD / "components" / "HomeScene.brs").read_text(encoding="utf-8")
    assert '"pedigree": true' in home
    assert '"tuple": true' in home
    assert 'm.registry.write("shuffleFlock", "true")' in home
    assert "if sf.Trim() = \"\"" not in home
    assert 'return registryBoolEnabled("shuffleFlock", true)' in home
    assert "sub onPlaybackFailed()" in home
    assert "sub probeFurnaceReach()" in home
    assert "sub onReachResult()" in home
    assert "sub showUnreachableUi(raw as string)" in home
    assert "function isUnreachableError(raw as string)" in home
    assert "function reconnectIntervalSec() as integer" in home
    assert "sub startReconnectTimer()" in home
    assert "sub maybeRepollFlock()" in home
    assert "sub maybeWrapRefetchFlock()" in home
    assert "sub rotateQueuePast(lastId as string)" in home
    assert "sub startFlockRepoll(force as boolean)" in home
    assert "sub dropItemFromFlock(deadId as string)" in home
    assert "function flockRepollMinSec() as integer" in home
    assert "return 30" in home
    assert "function flockIndexCap() as integer" in text
    assert "return 313" in text
    assert "function flockFetchLimit() as integer" in text
    assert "return 5000" in text
    assert "function pruneToCap(src as object, cap as integer)" in text
    player = (VOD / "components" / "PlayerScreen.brs").read_text(encoding="utf-8")
    assert "sub signalPlaybackFailed()" in player
    assert "m.top.playbackFailed = true" in player
    assert "postPlayback(\"playing\")" in player
    assert "sub submitSheepVote(kind as string)" in player
    assert 'submitSheepVote("like")' in player
    assert 'submitSheepVote("love")' in player
    assert 'submitSheepVote("vote")' not in player
    assert 'key = "right"' in player
    assert 'key = "down"' in player
    assert "m.top.focusable = true" in player
    assert "m.top.setFocus(true)" in player
    assert "m.video.setFocus(true)" not in player
    assert 'command = "sheepVote"' in player
    assert "/v1/sheep-votes" in text
    assert "function postSheepVote() as object" in text
    assert "function probeReach() as object" in text
    assert "function httpRequestWait(" in text
    assert "m.sessionXfer = xfer" in text
    assert "/System/Info/Public" in text
    settings = (VOD / "components" / "SettingsScreen.brs").read_text(encoding="utf-8")
    assert "function shuffleFlockDefault() as boolean" in settings
    assert "return true" in settings
    assert 'if val = "" then shown = "true"' in settings
    assert "normalizeBool(val, true)" in settings
    assert "function normalizeTitleMode(raw as string) as string" in settings
    assert 'if v = "alias" then return "alias"' in settings
    assert "function applyEditedValue(name as string, text as string) as boolean" in settings
    assert "function isValidStreamMode(raw as string) as boolean" in settings
    assert "function isValidBoolToken(raw as string) as boolean" in settings
    assert "function isValidTitleMode(raw as string) as boolean" in settings
    assert "function isValidBaseUrl(raw as string) as boolean" in settings
    assert "function isHexDashId(raw as string) as boolean" in settings
    assert "function isValidApiKey(raw as string) as boolean" in settings
    assert "titleMode invalid (" in settings
    assert "streamMode invalid (" in settings
    assert "commercialMode invalid (" in settings
    assert "m.inputNotice" in settings
    assert "if accepted = true" in settings
    assert "m.registry.write(name, val)" in settings
    assert "m.registry.flush()" in settings
    assert "m.top.saved = true" in settings
    assert "function isOkToggleField(name as string) as boolean" in settings
    assert "sub toggleChoice(name as string)" in settings
    assert "function nextToggleValue(name as string) as string" in settings
    assert "saved as" not in settings
    assert "m.inputNotice = \"\"" in settings
    assert "isOkToggleField(name) <> true" in settings
    assert "if isOkToggleField(name)" in settings
    assert "sub toggleTitleMode()" not in settings
    assert 'streamMode: mp4 or hls' not in settings
    assert 'm.top.findNode("row_save").label = "Save & Reload"' in settings
    jf = (VOD / "components" / "JellyfinTask.brs").read_text(encoding="utf-8")
    assert "function hasNcLicense(it as object) as boolean" in jf
    assert "function hasSafeLicense(it as object) as boolean" in jf
    assert "if hasNcLicense(it) then return false" in jf
    assert 'error: "item excluded by commercialMode"' in jf
    assert "filteredCount: filteredCount" in jf
    assert "aliasCount: aliasCount" in jf
    assert "function overviewKeyedValue(ov as string, key as string)" in jf
    assert "function displayTitle(filename as string, alias as string)" in jf
    assert "Alias:" in jf
    home = (VOD / "components" / "HomeScene.brs").read_text(encoding="utf-8")
    assert "function titleModeValue() as string" in home
    assert "function registryBoolEnabled(name as string, defaultVal as boolean)" in home
    assert "function effectiveSettingsSummary(res as object) as string" in home
    assert "commercialModeEnabled()" in home
    assert "alias titles:" in home
    assert "t.titleMode = titleModeValue()" in home
    ss = (SS / "components" / "ScreenSaverScene.brs").read_text(encoding="utf-8")
    assert 'write("shuffleFlock"' not in ss
    assert "shuffleCopy" in ss
    assert "handleStillFailed" in ss
    assert "maybeRepollStills" in ss
    assert "maybeWrapRefetchStills" in ss
    assert "rotateUrlsPast" in ss
    assert "function currentStillUri() as string" in ss
    assert "m.awaitingNewMix" in ss
    assert "m.wrapRefetch" in ss
    assert "rotateUrlsPast(showing)" in ss
    assert "function flockRepollMinSec() as integer" in ss
    ss_reg = (SS / "components" / "RegistryPresets.brs").read_text(encoding="utf-8")
    assert 'reg.write("shuffleFlock"' not in ss_reg
    ss_set = (SS / "components" / "ScreenSaverSettings.brs").read_text(encoding="utf-8")
    assert 'm.credFields = ["baseUrl", "apiKey", "userId", "libraryId"]' in ss_set
    assert "sub editCred(name as string)" in ss_set


def test_roku_vod_wrapped_flock_layout_and_compact_metadata():
    scene = (VOD / "components" / "HomeScene.xml").read_text(encoding="utf-8")
    home = (VOD / "components" / "HomeScene.brs").read_text(encoding="utf-8")
    task = (VOD / "components" / "JellyfinTask.brs").read_text(encoding="utf-8")
    player = (VOD / "components" / "PlayerScreen.brs").read_text(encoding="utf-8")

    assert "Ambient Dreams - Press OK button to play / Settings - Press * to Open" in scene
    assert 'numRows="3"' in scene
    assert 'showRowLabel="[false]"' in scene
    assert 'drawFocusFeedback="false"' in scene
    assert 'rowFocusAnimationStyle="fixedFocus"' in scene
    assert 'translation="[80,316]"' in scene
    assert 'translation="[80,380]"' in scene
    assert "itemsPerRow = 6" in home
    assert 'rowItemSize="[[270,152]]"' in scene
    assert 'width="270"' in (VOD / "components" / "FlockItem.xml").read_text(encoding="utf-8")
    assert "sheep in flock" in home
    assert "column >= itemsPerRow" in home
    assert "bits.push(meta.pedigree)" not in task
    assert 'gen <> "pedigree"' in task
    assert 'license = tl' in task
    assert 'id="chipLicense"' in scene
    assert 'width="360"' in scene
    assert 'id="chipPedigree"' in scene
    assert 'translation="[860,98]"' in scene
    assert "alias: item.alias" in home
    assert "function displayNameForUi() as string" in player
    assert "function titleModeValue() as string" in player
    assert "shown = displayNameForUi()" in player


def test_roku_vod_vote_overlay_skips_tuples_and_softens_banner():
    player = (VOD / "components" / "PlayerScreen.brs").read_text(encoding="utf-8")
    xml = (VOD / "components" / "PlayerScreen.xml").read_text(encoding="utf-8")
    home = (VOD / "components" / "HomeScene.brs").read_text(encoding="utf-8")
    assert "function isTuplePlayback() as boolean" in player
    assert "if isTuplePlayback() then return" in player
    assert "if isTuplePlayback()" in player
    assert 'Instr(1, stem, ".tuple.")' in player
    assert 'id="playerChrome"' in xml
    assert 'translation="[80,920]"' in xml
    assert 'id="chromeBanner"' in xml
    assert 'color="0x0A0A128C"' in xml
    assert 'translation="[80,980]"' not in xml
    assert xml.count('font:SmallSystemFont') >= 3
    assert xml.count('color="0xE8E8F08C"') >= 3
    assert 'color="0xE8E8F0FF"' not in xml
    assert "sub showLoadChrome(msg as string)" in player
    assert "sub refreshPlayerChrome()" in player
    assert "sub hideLoadChrome()" in player
    assert "showLoadChrome(" in player
    assert 'horizAlign="left"' in xml
    assert 'horizAlign="right"' in xml
    assert "OK love · RIGHT like · DOWN dismiss · UP/BACK exit" in xml
    assert "function votePromptName() as string" in player
    assert "return displayNameForUi()" in player
    assert "if m.votePrompt <> invalid then m.votePrompt.text = votePromptName()" in player
    assert "return 7.0" in player
    assert "Like this sheep" not in player
    assert "Like this sheep" not in xml
    assert 'id="votePrompt"' in xml
    assert 'width="700"' in xml
    assert 'ellipsizeOnBoundary="true"' in xml
    assert 'translation="[760,8]"' in xml
    assert 'id="voteHideTimer"' in xml
    assert 'duration="7"' in xml
    assert "filename: item.filename" in home


def test_roku_screensaver_expands_nested_library_folders():
    text = (SS / "components" / "StillsTask.brs").read_text(encoding="utf-8")
    assert "fetchStillsViaChildFolders" in text
    assert "mergeStillsById" in text
    assert "isTupleFolder" in text
    assert "isTupleItem" in text
    assert "Images/Backdrop/" in text
    assert "Images/Primary" in text
    assert "isCommercialSafe" in text
    assert 'write("shuffleFlock"' not in text
    assert "shuffleCopy" in text
    assert "pruneToCap" in text
    assert "flockIndexCap" in text
    assert "flockFetchLimit" in text
    assert "build_version=11" in (SS / "manifest").read_text(encoding="utf-8")
    assert 'Version=""1.0.11""' in text
    assert "itemAlias" in text
    assert "overviewKeyedValue" in text
    scene = (SS / "components" / "ScreenSaverScene.brs").read_text(encoding="utf-8")
    assert "function titleModeValue() as string" in scene
    assert "function displayTitle(filename as string, alias as string)" in scene
    assert "setCaptionFor" in scene
    settings = (SS / "components" / "ScreenSaverSettings.brs").read_text(encoding="utf-8")
    assert "toggleTitleMode" in settings
    assert 'write("titleMode"' in settings
