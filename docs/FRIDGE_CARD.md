# JellyFlam3 — fridge card

Print this page. Fill the blanks in pencil. **Do not write API keys here.**

Full guide: [USER_GUIDE_AND_RUNBOOK.md](USER_GUIDE_AND_RUNBOOK.md) (Layer 1).

| This house | Write here |
|---|---|
| Jellyfin on the Pi (LAN) | `http://____________________:8096` |
| Furnace Pi name | ________________________________ |
| Screensaver wait | ________ minutes |

Never use `127.0.0.1` or `localhost` on a TV — those are the Pi talking to itself.

---

## Watch

| Device | Everyday |
|---|---|
| **Roku VoD** | Launch **JellyFlam3** → pick a sheep. Loop plays. |
| **Roku screensaver** | **Settings → Theme → Screensavers → JellyFlam3**. Images only (not video). Install **VoD first** on this Roku and save Settings, then sideload the screensaver zip. |
| **Kodi** | **Settings → Interface → Screensaver → JellyFlam3 Dreams**. Leave idle. Any key exits. |

**One Roku sideload slot:** installing screensaver **replaces** VoD until you re-sideload VoD. Settings survive the swap.

---

## Gate (why new sheep pause)

| On the TV | Furnace |
|---|---|
| Roku **VoD Playing** | **Stops** rendering until the TV has been idle several minutes |
| Roku or Kodi **screensaver** | Rendering **continues** (gate stays open) |
| New MP4s | **Hours to days** each. Empty days can be normal. |

---

## First-time Settings (paste **on the TV only**)

Operator runs `python3 scripts/jellyfin_id_dump.py` on the furnace Pi, then you type on the remote:

| Field | Value |
|---|---|
| **baseUrl** / Jellyfin URL | `http://<Pi_LAN_IP>:8096` |
| **apiKey**, **userId**, **libraryId** | From the dump — never email, chat, or this card |

Furnace-built zips often pre-fill these. If the flock is empty, open VoD **Settings**, save once, confirm Wi‑Fi.

---

## If nothing plays

| Symptom | Try this |
|---|---|
| Empty flock / blank screensaver | Re-open VoD Settings; save; same Wi‑Fi as the Pi |
| “Cannot connect” | URL must be the Pi’s **LAN IP**, not `127.0.0.1` |
| Screensaver replaced VoD | Re-sideload the VoD zip |
| Kodi black / hint on black | Add-on **Configure** → furnace LAN URL |
| Nothing new for days | Often normal. Ask the operator if the TV was left on VoD |

---

## Operator strip (Pi terminal)

```bash
cd /opt/jellyflam3-server && ./scripts/healthcheck.sh    # exit 0 = healthy
python3 -m json.tool /var/lib/jellyflam3/idle_gate_status.json
# gate: open = rendering allowed; closed = a TV is Playing
```

Layer 2 runbook: [USER_GUIDE_AND_RUNBOOK.md](USER_GUIDE_AND_RUNBOOK.md#layer-2--operator-runbook).
