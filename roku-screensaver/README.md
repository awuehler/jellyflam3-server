# JellyFlam3 Roku Screensaver (Phase 3 guide 01)

Standalone **image-only** screensaver. Separate from the VoD channel (`roku-channel/`).

## Registry dependency

This package **does not ship a credential editor** in Settings. It **reads** registry section `JellyFlam3` on **this** Roku:

| Key | Written by | Screensaver |
|---|---|---|
| `baseUrl`, `apiKey`, `userId`, `libraryId` | **VoD channel** Settings, or **furnace zip** `registry/jellyflam3-presets.json` on first launch | Read only |
| `ssFade`, `ssDwellSec`, `ssFadeSec` | Screensaver Settings | Read + write |

**Furnace-built zip (recommended):** package on a Pi with `secrets.env` (`./scripts/package_roku_screensaver.sh` on `16a` / `08a` / `04a`). The zip includes `registry/jellyflam3-presets.json`; first run applies Jellyfin IDs when keys are empty.

**Manual path on a new device:**

1. Sideload **`roku-channel/`** (`dist/jellyflam3-roku.zip`) — currently installed, **or** previously configured on this same box.
2. Open the VoD channel → **Settings** → save Jellyfin URL, API key, user id, library id.
3. Sideload **`roku-screensaver/`**. Developer mode then **replaces** the VoD zip; **registry keys remain** on the device.
4. **Settings → Theme → Screensavers** → **JellyFlam3 Dreams**.

If neither VoD Settings nor a furnace preset was ever applied on this Roku, the screensaver shows “registry missing” until credentials exist. Credentials do **not** sync from other TVs or from the Pi automatically (except via furnace-built zip for that Pi’s Jellyfin).

**Post-launch:** credential editors inside Screensaver Settings may arrive later; until then use VoD Settings or a furnace-built zip.

## Platform rules

- Entry: `RunScreenSaver()` / optional `RunScreenSaverSettings()`
- **No** `Video` node, deep links, or Sessions/Playing reports (keeps idle-gate open)
- Screensaver options (same `JellyFlam3` section): `ssFade`, `ssDwellSec`, `ssFadeSec` — edit under **Change screensaver settings**

## Crossfade / dwell

Defaults: crossfade **On**, dwell **12 s**, fade **1.5 s**. In Screensaver Settings: Up/Down select · Left/Right or OK change · Back exit. Changes apply on the next screensaver run.

## Lab install

1. **Package on a furnace Pi** (pre-fills Jellyfin IDs) or configure VoD on this Roku first (see **Registry dependency**).
2. Package:
   ```bash
   cd /opt/jellyflam3-server
   ./scripts/package_roku_screensaver.sh
   ```
   or `.\scripts\package_roku_screensaver.ps1` (Windows — no presets without `secrets.env`)
3. Sideload `dist/jellyflam3-screensaver.zip` via Roku Developer Application Installer.
4. Pick **JellyFlam3 Dreams** (or the package `screensaver_title`) under **Settings → Theme → Screensavers**. That is the only Roku UI for choosing a screensaver — there is no “idle-gate” or smoke item on the box.

### Confirm idle-gate on a Pi (not on the Roku)

While the screensaver is the active Theme choice and has had time to fetch Primaries:

```bash
# On the Jellyfin/idle-gate Pi (often 16a):
cat /var/lib/jellyflam3/idle_gate_status.json
# Expect: "gate": "open"  (screensaver must not close the furnace)

# Optional live probe:
cd /opt/jellyflam3-server && PYTHONPATH=/opt/jellyflam3-server \
  python3 -m pipeline.idle_gate --once
```

PASS = gate stays **open** with screensaver running. FAIL = gate goes **closed** because of a Sessions/Playing report from the SS client.

### Sideload replaces VoD (expected)

Roku developer mode allows **only one sideloaded package** at a time. Installing the screensaver zip **replaces** `jellyflam3-roku.zip` on that box — not a shared app-id bug, and not something we can fix by renaming the zip.

| Goal | Approach |
|---|---|
| Smoke the screensaver | **VoD Settings already saved on this box**, then sideload SS zip; Theme → Screensavers |
| Restore VoD after SS smoke | Re-sideload `dist/jellyflam3-roku.zip` |
| Keep both installed long-term | Publish one as a **private/unpublished** channel; leave the other as the single sideload |

Roku also **forbids** embedding a screensaver in a streaming app (`screensaver_title` / `RunScreenSaver` are screensaver-only). VoD and screensaver must stay separate packages.

## Stills on the Pi

```bash
cd /opt/jellyflam3-server
python3 -m pipeline.stills --dry-run
python3 -m pipeline.stills --limit 5
```

MVP screensaver cycles **Jellyfin Primary** images. Extracted frames under
`/media/sheep/by-generation/{gen}/stills/{stem}/` are for future Backdrop/local
serving and Shears cascade; Primaries remain the first-pass feed.
