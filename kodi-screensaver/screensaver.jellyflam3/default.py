"""JellyFlam3 Kodi screensaver entry (Phase 3 guide 02).

Fullscreen idle player inside the screensaver window (videowindow), no OSD
chrome. Draws from the Jellyfin Sheep library (Static MP4). When settings or
flock are unavailable, shows a short on-screen hint on black — no bundled test
pattern video.

Critical Kodi Omega behavior (ApplicationPowerHandling::WakeUpScreenSaver):
Player.play() wakes the screensaver and arms alarm ``sssssscreensaver`` which
runs StopScript() after **15 seconds** (SCRIPT_TIMEOUT). We CancelAlarm that
name after play (and on a keepalive thread) so idle video is not killed.
"""

from __future__ import annotations

import json
import os
import sys
import threading

import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo("path")
ADDON_ID = "screensaver.jellyflam3"
# Must match Kodi ApplicationPowerHandling.cpp SCRIPT_ALARM
SCRIPT_ALARM = "sssssscreensaver"

_LIB = os.path.join(ADDON_PATH, "resources", "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import jellyfin_flock  # noqa: E402


def _jsonrpc(payload):
    try:
        return json.loads(xbmc.executeJSONRPC(json.dumps(payload)))
    except Exception as exc:
        xbmc.log("%s: jsonrpc failed: %s" % (ADDON_ID, exc), xbmc.LOGERROR)
        return {}


def _cancel_stop_script_alarm():
    xbmc.executebuiltin("CancelAlarm(%s,true)" % SCRIPT_ALARM)


def _dismiss_busy():
    xbmc.executebuiltin("Dialog.Close(busydialog,true)")
    xbmc.executebuiltin("Dialog.Close(busydialognocancel,true)")


def _set_repeat(mode: str):
    """mode: off | one | all"""
    active = _jsonrpc(
        {"jsonrpc": "2.0", "id": 1, "method": "Player.GetActivePlayers", "params": {}}
    )
    players = active.get("result") or []
    playerid = 1
    if players:
        playerid = int(players[0].get("playerid", 1))
    _jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "Player.SetRepeat",
            "params": {"playerid": playerid, "repeat": mode},
        }
    )
    builtin = {"off": "RepeatOff", "one": "RepeatOne", "all": "RepeatAll"}.get(
        mode, "RepeatOff"
    )
    xbmc.executebuiltin("PlayerControl(%s)" % builtin)


def _load_flock():
    """Fetch + shuffle Jellyfin items; return list of {id,title,url} or []."""
    base = (ADDON.getSetting("server_url") or "").strip()
    key = (ADDON.getSetting("api_key") or "").strip()
    user = (ADDON.getSetting("user_id") or "").strip()
    library = (ADDON.getSetting("library_id") or "").strip()
    commercial = (ADDON.getSetting("commercial_mode") or "false").lower() in (
        "true",
        "1",
        "yes",
    )
    try:
        limit = int(ADDON.getSetting("flock_limit") or "200")
    except ValueError:
        limit = 200

    if not (base and key and user):
        xbmc.log(
            "%s: Jellyfin settings incomplete — flock unavailable" % ADDON_ID,
            xbmc.LOGWARNING,
        )
        return []

    try:
        items = jellyfin_flock.fetch_flock(
            base_url=base,
            api_key=key,
            user_id=user,
            library_id=library,
            commercial_mode=commercial,
            limit=limit,
        )
    except Exception as exc:
        xbmc.log("%s: flock fetch failed: %s" % (ADDON_ID, exc), xbmc.LOGERROR)
        return []

    items = jellyfin_flock.shuffle_copy(items)
    xbmc.log(
        "%s: flock loaded %s item(s)" % (ADDON_ID, len(items)),
        xbmc.LOGINFO,
    )
    return items


class LoopPlayer(xbmc.Player):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    def onAVStarted(self):
        _dismiss_busy()
        _cancel_stop_script_alarm()
        if self._owner._flock_mode:
            _set_repeat("off")

    def onPlayBackStarted(self):
        _dismiss_busy()
        _cancel_stop_script_alarm()

    def onPlayBackEnded(self):
        # Signal watchdog — never call play() on the player thread.
        self._owner._advance = True


class JellyFlam3Screensaver(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._exiting = False
        self._player = LoopPlayer(self)
        self._monitor = xbmc.Monitor()
        self._keepalive = None
        self._flock: list[dict] = []
        self._index = 0
        self._flock_mode = False
        self._advance = False

    def onInit(self):
        label = self.getControl(100)
        label.setVisible(False)

        xbmcgui.Window(10000).setProperty("PseudoTVRunning", "True")
        xbmcgui.Window(10000).setProperty("%s.Running" % ADDON_ID, "True")
        _dismiss_busy()
        _cancel_stop_script_alarm()

        self._flock = _load_flock()
        self._flock_mode = bool(self._flock)
        self._index = 0

        if not self._play_current():
            label.setLabel(
                "JellyFlam3 — configure Jellyfin in add-on settings, then retry"
            )
            label.setVisible(True)
            xbmc.log("%s: flock empty or settings incomplete" % ADDON_ID, xbmc.LOGWARNING)
            return

        self._keepalive = threading.Thread(
            target=self._watch_loop, name="jf3-ss-watch", daemon=True
        )
        self._keepalive.start()
        xbmc.log("%s: idle player running" % ADDON_ID, xbmc.LOGINFO)

    def _play_current(self) -> bool:
        if not self._flock_mode or not self._flock:
            return False
        url = self._flock[self._index % len(self._flock)]["url"]
        item = self._flock[self._index % len(self._flock)]
        title = item.get("title") or "JellyFlam3"
        xbmc.log(
            "%s: play %s (%s/%s)"
            % (ADDON_ID, title, (self._index % len(self._flock)) + 1, len(self._flock)),
            xbmc.LOGINFO,
        )
        listitem = xbmcgui.ListItem(label=title, path=url)
        listitem.setPath(url)
        listitem.setMimeType("video/mp4")
        listitem.setContentLookup(False)
        _dismiss_busy()
        self._player.play(url, listitem, True)  # windowed
        xbmc.sleep(150)
        _dismiss_busy()
        _cancel_stop_script_alarm()
        _set_repeat("off")
        return True

    def _next_sheep(self):
        if not self._flock_mode or not self._flock:
            return
        self._index += 1
        if self._index >= len(self._flock):
            self._flock = jellyfin_flock.shuffle_copy(self._flock)
            self._index = 0
            xbmc.log("%s: flock reshuffled" % ADDON_ID, xbmc.LOGINFO)
        self._play_current()

    def _watch_loop(self):
        idle_ticks = 0
        while not self._exiting:
            _cancel_stop_script_alarm()
            if self._advance:
                self._advance = False
                idle_ticks = 0
                self._next_sheep()
            else:
                playing = False
                try:
                    playing = self._player.isPlayingVideo() or self._player.isPlaying()
                except Exception:
                    playing = False
                if self._flock_mode and not playing:
                    idle_ticks += 1
                    # ~1.5s not playing → advance (covers missed Ended callback)
                    if idle_ticks >= 3:
                        idle_ticks = 0
                        self._next_sheep()
                else:
                    idle_ticks = 0
            if self._monitor.waitForAbort(0.5):
                break

    def onAction(self, action):
        self._shutdown("action_%s" % action.getId())

    def _shutdown(self, reason="action"):
        if self._exiting:
            return
        self._exiting = True
        xbmc.log("%s: stop (%s)" % (ADDON_ID, reason), xbmc.LOGINFO)
        xbmcgui.Window(10000).clearProperty("PseudoTVRunning")
        xbmcgui.Window(10000).clearProperty("%s.Running" % ADDON_ID)
        try:
            _set_repeat("off")
        except Exception:
            pass
        try:
            if self._player.isPlaying():
                self._player.stop()
        except Exception:
            pass
        self.close()


def run():
    ui = JellyFlam3Screensaver("fallback.xml", ADDON_PATH, "default", "1080i")
    ui.doModal()
    del ui


if __name__ == "__main__":
    run()
