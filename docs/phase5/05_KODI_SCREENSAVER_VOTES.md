# 05 — Kodi screensaver votes (Roku VoD equivalent)

## Boundary

Phase 5 **pasture** slice on **deployment A** clients: the Kodi video screensaver posts the same like/love events as Roku VoD. Furnace SoT stays `{stem}.jellyflam3.json` `viewer_feedback` via `POST /v1/sheep-votes` on `jellyflam3-display-sink` (:8791). Share cron and idle-breed weights already read that block ([../phase4/08_VIEWER_FEEDBACK_LOOP.md](../phase4/08_VIEWER_FEEDBACK_LOOP.md)).

This is **not** Ventuno / LLM work. This is **not** Roku screensaver voting.

**Status:** Shipped **2026-09-19** (Kodi screensaver **0.2.13**). Phase 4 cancelled **Roku** screensaver votes (certification / best practices) remains in force. Auto-promote stays cancelled.

## Why Phase 5 (not reopening Phase 4 / 08)

| Surface | Vote? | Why |
|---|---|---|
| Roku VoD | **Yes** (1.0.38+) | Interactive channel; overlay in last **7 s** |
| Roku screensaver | **No** | Image-only; Channel Store / screensaver best practices |
| Kodi screensaver | **Yes (this guide)** | Video idle player; no Roku Store rule. Same furnace sink as VoD |

Phase 4 / 08 non-goal “voting inside the Roku or Kodi screensaver” is **split**: Roku SS stays cancelled; Kodi SS is this slice.

## Product (locked to VoD)

| VoD behavior | Kodi screensaver **0.2.13** |
|---|---|
| Last **7 s** overlay; playback does not pause | Same (`Player.getTime` / `getTotalTime`, fallback `RunTimeTicks`) |
| **OK** / Enter = love | `ACTION_SELECT_ITEM` (7) |
| **Right** = like | `ACTION_MOVE_RIGHT` (2) |
| **Down** = dismiss overlay, keep playing | `ACTION_MOVE_DOWN` (4) |
| **Up** / **Back** / Esc = leave | Exit screensaver (`ACTION_MOVE_UP`, `PREVIOUS_MENU`, `NAV_BACK`, `STOP`) |
| Tuples skip overlay and POST | Path `/tuple/` or stem `electricsheep.tuple.*` |
| Unlimited re-vote | Same sidecar increments |
| `kind=vote` not posted by client | Like VoD; CLI/API still accept it |
| Identity | `stem` from Jellyfin `Path` basename (fallback `Name`); `itemId`; `deviceId=jellyflam3-kodi-ss` |
| Chrome | Caption **101** (filename/alias) + hint **102**: `OK love · RIGHT like · DOWN dismiss · UP/BACK exit` |
| Sink | Explicit `display_sink_url` or `http://{Jellyfin host}:8791`; header `X-JellyFlam3-Token` |

Keys **while the overlay is hidden** still **exit** the screensaver (Kodi wake). **Left** during overlay is consumed (no vote, no exit), matching VoD.

## Work (shipped)

1. **Overlay timing** — watch loop shows hint when remaining ≤ 7 s, not dismissed this clip, not a tuple.
2. **Key map** — as table; unmapped overlay keys still wake/exit.
3. **POST** — background thread, same JSON as VoD (`stem`, `kind`, `itemId`, `mediaPath`, `deviceId`). Missing token logs and skips.
4. **Settings** — `display_sink_url` (blank = derive), `display_sink_token`. Furnace pack fills token from `DISPLAY_SINK_TOKEN`.
5. **Idle-gate** — still Client=`JellyFlam3-Screensaver`; vote HTTP is not a Playing session.

## Non-goals

- Roku screensaver votes
- New furnace vote store or second sink port
- Pausing idle video to vote
- Unique-vote / anti-stuffing
- Auto-promote
- Ventuno involvement

## See also

[../phase4/08_VIEWER_FEEDBACK_LOOP.md](../phase4/08_VIEWER_FEEDBACK_LOOP.md) · [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) · [../../kodi-screensaver/README.md](../../kodi-screensaver/README.md) · [../USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md#8--list-top-voted-sheep) · [00_OVERVIEW.md](00_OVERVIEW.md)
