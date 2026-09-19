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
import time

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


def _dismiss_playback_error():
    """Close Kodi's modal playback-failed dialog after a dead flock item."""
    xbmc.executebuiltin("Dialog.Close(okdialog,true)")


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


def _ensure_shuffle_on() -> None:
    """Heal persisted false from older add-on defaults after zip upgrade."""
    raw = (ADDON.getSetting("shuffle") or "").lower()
    if raw in ("true", "1", "yes"):
        return
    try:
        ADDON.setSetting("shuffle", "true")
    except Exception as exc:
        xbmc.log("%s: could not persist shuffle=true: %s" % (ADDON_ID, exc), xbmc.LOGWARNING)


def _shuffle_enabled() -> bool:
    """Household policy: always rotate. Heal leftover false, then return true."""
    _ensure_shuffle_on()
    return True


HINT_SETTINGS = "JellyFlam3 — add Jellyfin in screensaver settings"
HINT_UNREACHABLE = "JellyFlam3 — waiting for the furnace"
HINT_EMPTY = "JellyFlam3 — flock empty; exit screensaver"
HINT_AUTH = "JellyFlam3 — Jellyfin login failed; check settings"
# Watch loop ticks at 0.5s; 60 → 30s reconnect (same floor as flock re-poll).
RECONNECT_TICKS = 60


def _load_flock():
    """Fetch + shuffle Jellyfin items.

    Returns ``(items, status)`` where status is ``ok``, ``settings``,
    ``unreachable``, ``auth``, or ``empty``.
    """
    base = (ADDON.getSetting("server_url") or "").strip()
    key = (ADDON.getSetting("api_key") or "").strip()
    user = (ADDON.getSetting("user_id") or "").strip()
    library = (ADDON.getSetting("library_id") or "").strip()
    commercial = (ADDON.getSetting("commercial_mode") or "false").lower() in (
        "true",
        "1",
        "yes",
    )
    shuffle = _shuffle_enabled()
    try:
        limit = int(ADDON.getSetting("flock_limit") or str(jellyfin_flock.FLOCK_INDEX_CAP))
    except ValueError:
        limit = jellyfin_flock.FLOCK_INDEX_CAP
    if limit < 1:
        limit = jellyfin_flock.FLOCK_INDEX_CAP

    if not (base and key and user):
        xbmc.log(
            "%s: Jellyfin settings incomplete — flock unavailable" % ADDON_ID,
            xbmc.LOGWARNING,
        )
        return [], "settings"

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
        kind = jellyfin_flock.classify_fetch_error(exc)
        xbmc.log("%s: flock fetch failed (%s): %s" % (ADDON_ID, kind, exc), xbmc.LOGERROR)
        return [], kind

    if not items:
        xbmc.log("%s: flock empty (Jellyfin reachable)" % ADDON_ID, xbmc.LOGWARNING)
        return [], "empty"

    if shuffle:
        items = jellyfin_flock.shuffle_copy(items)
    xbmc.log(
        "%s: flock loaded %s item(s) shuffle=%s" % (ADDON_ID, len(items), shuffle),
        xbmc.LOGINFO,
    )
    return items, "ok"


class LoopPlayer(xbmc.Player):
    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    def onAVStarted(self):
        _dismiss_busy()
        _cancel_stop_script_alarm()
        self._owner._av_started = True
        if self._owner._flock_mode:
            _set_repeat("off")

    def onPlayBackStarted(self):
        _dismiss_busy()
        _cancel_stop_script_alarm()

    def onPlayBackEnded(self):
        # Signal watchdog — never call play() on the player thread.
        self._owner._advance = True

    def onPlayBackError(self):
        # 404 / stream open fail — drop this id and re-poll (watch thread).
        _dismiss_playback_error()
        self._owner._dead = True


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
        self._dead = False
        self._av_started = False
        self._last_repoll = None
        self._waiting = False
        self._reconnect_ticks = 0

    def onInit(self):
        label = self.getControl(100)
        label.setVisible(False)

        xbmcgui.Window(10000).setProperty("PseudoTVRunning", "True")
        xbmcgui.Window(10000).setProperty("%s.Running" % ADDON_ID, "True")
        _dismiss_busy()
        _cancel_stop_script_alarm()

        items, status = _load_flock()
        self._flock = items
        self._flock_mode = bool(items)
        self._index = 0

        if status == "ok" and self._play_current():
            self._start_watch()
            xbmc.log("%s: idle player running" % ADDON_ID, xbmc.LOGINFO)
            return

        if status == "settings":
            self._set_hint(HINT_SETTINGS)
            xbmc.log("%s: flock empty or settings incomplete" % ADDON_ID, xbmc.LOGWARNING)
            return
        if status == "auth":
            self._set_hint(HINT_AUTH)
            return
        if status == "empty":
            self._set_hint(HINT_EMPTY)
            return

        self._enter_wait()
        self._start_watch()

    def _start_watch(self):
        if self._keepalive is not None:
            return
        self._keepalive = threading.Thread(
            target=self._watch_loop, name="jf3-ss-watch", daemon=True
        )
        self._keepalive.start()

    def _set_hint(self, reason: str):
        try:
            label = self.getControl(100)
            label.setLabel(reason)
            label.setVisible(True)
        except Exception as exc:
            xbmc.log("%s: hint label failed: %s" % (ADDON_ID, exc), xbmc.LOGERROR)

    def _hide_hint(self):
        try:
            self.getControl(100).setVisible(False)
        except Exception:
            pass

    def _enter_wait(self):
        self._waiting = True
        self._reconnect_ticks = 0
        try:
            if self._player.isPlaying():
                self._player.stop()
        except Exception:
            pass
        self._set_hint(HINT_UNREACHABLE)
        xbmc.log("%s: furnace unreachable; waiting to reconnect" % ADDON_ID, xbmc.LOGWARNING)

    def _try_reconnect(self) -> bool:
        items, status = _load_flock()
        if status == "ok" and items:
            self._waiting = False
            self._flock = items
            self._flock_mode = True
            if self._index >= len(self._flock):
                self._index = 0
            self._hide_hint()
            xbmc.log("%s: furnace reachable; resume flock" % ADDON_ID, xbmc.LOGINFO)
            return self._play_current()
        if status == "empty":
            self._waiting = False
            self._show_flock_empty(HINT_EMPTY)
            return False
        if status == "auth":
            self._waiting = False
            self._set_hint(HINT_AUTH)
            return False
        return False

    def _play_current(self) -> bool:
        if not self._flock_mode or not self._flock:
            return False
        self._av_started = False
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

    def _show_flock_empty(self, reason: str):
        self._waiting = False
        self._flock_mode = False
        self._flock = []
        try:
            if self._player.isPlaying():
                self._player.stop()
        except Exception:
            pass
        try:
            label = self.getControl(100)
            label.setLabel(reason)
            label.setVisible(True)
        except Exception as exc:
            xbmc.log("%s: empty-flock label failed: %s" % (ADDON_ID, exc), xbmc.LOGERROR)

    def _handle_dead_sheep(self):
        # Kodi raises a modal okdialog for an unplayable URL. The player callback
        # can precede creation of that dialog, so close it again on the watch
        # thread before advancing to the refreshed flock.
        _dismiss_playback_error()
        if self._waiting:
            return
        base = (ADDON.getSetting("server_url") or "").strip()
        if not jellyfin_flock.probe_jellyfin(base):
            self._enter_wait()
            return
        if not self._flock_mode or not self._flock:
            self._show_flock_empty(HINT_EMPTY)
            return
        dead = self._flock[self._index % len(self._flock)]
        dead_id = dead.get("id") or ""
        xbmc.log(
            "%s: drop missing sheep %s and re-poll flock" % (ADDON_ID, dead_id),
            xbmc.LOGWARNING,
        )
        self._flock = jellyfin_flock.drop_item(self._flock, dead_id)
        now = time.monotonic()
        if jellyfin_flock.should_repoll_flock(self._last_repoll, now):
            self._last_repoll = now
            fresh, status = _load_flock()
            if status == "ok" and fresh:
                self._flock = jellyfin_flock.drop_item(fresh, dead_id)
            elif status == "unreachable":
                self._enter_wait()
                return
        if not self._flock:
            self._show_flock_empty(HINT_EMPTY)
            return
        if self._index >= len(self._flock):
            self._index = 0
        self._play_current()

    def _next_sheep(self):
        if self._waiting:
            return
        if not self._flock_mode or not self._flock:
            return
        self._index += 1
        if self._index >= len(self._flock):
            last_id = self._flock[-1].get("id") or ""
            if len(self._flock) > 1:
                fresh, status = _load_flock()
                if status == "ok" and fresh:
                    self._flock = fresh
                    xbmc.log("%s: flock wrap refetch (%s item(s))" % (ADDON_ID, len(fresh)), xbmc.LOGINFO)
                elif status == "unreachable":
                    self._enter_wait()
                    return
                elif _shuffle_enabled():
                    self._flock = jellyfin_flock.shuffle_copy(self._flock)
                    xbmc.log("%s: flock reshuffled (wrap refetch empty)" % ADDON_ID, xbmc.LOGINFO)
            elif _shuffle_enabled():
                self._flock = jellyfin_flock.shuffle_copy(self._flock)
                xbmc.log("%s: flock reshuffled" % ADDON_ID, xbmc.LOGINFO)
            self._flock = jellyfin_flock.rotate_past(self._flock, last_id)
            self._index = 0
        self._play_current()

    def _watch_loop(self):
        idle_ticks = 0
        while not self._exiting:
            _cancel_stop_script_alarm()
            if self._waiting:
                self._reconnect_ticks += 1
                if self._reconnect_ticks >= RECONNECT_TICKS:
                    self._reconnect_ticks = 0
                    self._try_reconnect()
                if self._monitor.waitForAbort(0.5):
                    break
                continue
            if self._dead:
                self._dead = False
                idle_ticks = 0
                self._handle_dead_sheep()
            elif self._advance:
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
                    if self._av_started:
                        # ~1.5s not playing → advance (covers missed Ended callback)
                        if idle_ticks >= 3:
                            idle_ticks = 0
                            self._next_sheep()
                    elif idle_ticks >= 10:
                        # ~5s never started → treat as 404 / stream open fail
                        idle_ticks = 0
                        self._handle_dead_sheep()
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
