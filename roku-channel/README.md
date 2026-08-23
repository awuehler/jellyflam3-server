# JellyFlam3 Roku channel

Sideloadable SceneGraph channel that lists sheep from Jellyfin with **poster tiles** (`FlockItem`). **Ambient loop** defaults to Static MP4; HLS remux remains available for lab compare.

## Playback

| `streamMode` (registry) | URL | `streamFormat` | Sessions | Notes |
|------|-----|----------------|----------|-------|
| **`mp4` (default)** | `/Videos/{id}/stream.mp4?Static=true&api_key=…` | `mp4` | `DirectPlay` | Ambient default; seek-to-0 reloop |
| **`hls`** | `/Videos/{id}/main.m3u8?MediaSourceId={id}&api_key=…&AudioCodec=aac` | `hls` | `DirectStream` | Remux compare; usually longer reloop gap |

Roku VOD **cannot gapless-loop** HTTP MP4/HLS with the Video node (`Video.loop` still rebuffers). Channel uses seek-before-EOF; residual hitch is accepted for now. Do **not** use `master.m3u8` on Jellyfin 10.11.

## Settings version

Settings shows **Version X.Y.Z** from `roAppInfo.GetVersion()` (manifest `major_version` / `minor_version` / `build_version`). Sideload builds append `(sideload)`. Keep Jellyfin auth `Version=` in sync with the manifest on each package.

## Registry settings

Section `JellyFlam3` (edit in-channel via **Settings** button, **\* Options**, or auto-prompt when credentials are empty):

| Key | Example |
|-----|---------|
| `baseUrl` | `http://<RPi_IP_Address>:8096` |
| `apiKey` | Jellyfin API key |
| `userId` | Jellyfin user id (required) |
| `libraryId` | Sheep library ParentId (recommended) |
| `commercialMode` | `true` / `false` — client-side filter: keep CC BY / CC0 / PD; hide NC (do not use Jellyfin `Tags=` query) |
| `streamMode` | `mp4` (ambient loop default) or `hls` (remux compare) |
| `shuffleFlock` | `true` / `false` — when true, play archive gens (`247…165`) in random order at EOF (skips `misc`/`test`); when false, seek-reloop one sheep |
| `displayWidth` / `displayHeight` | From Settings **Fetch TV display** (`roDeviceInfo`) |
| `uiResolution` / `uiWidth` / `uiHeight` | UI resolution name + pixels |
| `videoMode` | e.g. `1080p`, `2160p60` |
| `hdr10` / `hdr10Plus` / `hlg` / `dolbyVision` / `hdrSeamless` | Display HDR capability flags |
| `displayInternal` | `true` if built-in panel (Roku TV) |
| `deviceModel` / `deviceModelName` | Roku model strings |
| `capturedAt` / `displaySummary` | Probe timestamp + one-line summary |

Display keys are **hints only**. **Fetch TV display** also POSTs to `http://{baseUrl-host}:8791/v1/display-profiles` (**one JSON file per screen**). Roku `FormatJson` lowercases AA keys; the Pi sink accepts case-insensitive field names. Override with registry `displaySinkUrl`; optional `displaySinkToken`. Kodi/other clients: `python3 -m pipeline.display_profiles upsert --client Kodi --device-id …`.

## Flock item metadata

Each list item carries browse metadata:

| Field | Source |
|-------|--------|
| `durationLabel` | `RunTimeTicks` → e.g. `23s` |
| `generation` | Tag `generation-N` or `electricsheep.N.*` name/path |
| `license` | Tags `cc-by` / `cc-by-nc` / … or Overview `License:` line |
| `pedigree` | Tags `pedigree` / `local_pedigree` / `human` / `brood` |
| `metaLine` | Joined one-liner, e.g. `23s · gen 247 · cc-by-nc` |

Focus updates the **detail panel** (title, meta, chips, overview snippet) and the tile subtitle.

## Jellyfin IDs for Settings

On a **furnace Pi** (with `secrets.env`), packaging pre-fills credentials — see **Furnace packaging** below. For manual paste or verification:

```bash
python3 scripts/jellyfin_id_dump.py
python3 scripts/jellyfin_id_dump.py --items --limit 50
```

Prints `baseUrl` / `apiKey` / `userId` / `libraryId` (and optional item Guids). See [docs/phase3/08_JELLYFIN_ID_DUMP.md](../docs/phase3/08_JELLYFIN_ID_DUMP.md).

## Build + sideload

**Furnace packaging (recommended):** on a Pi with `secrets.env`, `package_roku_channel.*` runs `client_pack_presets.py` and includes `registry/jellyflam3-presets.json` in the zip. On first launch, `applyJellyFlam3PackPresets()` writes empty `JellyFlam3` registry keys from that file. Each furnace host (`16a` / `08a` / `04a`) produces a zip for **its** Jellyfin URL.

```bash
cd /opt/jellyflam3-server
./scripts/package_roku_channel.sh
# → dist/jellyflam3-roku.zip
```

**Windows / non-furnace:** presets are skipped; paste Settings manually after sideload.

```powershell
.\scripts\package_roku_channel.ps1
# Upload dist/jellyflam3-roku.zip at http://<roku-ip>/ (Developer installer)
```

Developer mode holds **one** sideloaded package. Installing the Phase 3 screensaver zip replaces this VoD channel on that box; re-sideload this zip to restore.

**Screensaver depends on VoD registry keys** (`baseUrl` / `apiKey` / `userId` / `libraryId`). The VoD channel’s Settings UI is the usual way to populate them. **Furnace-built zips** also ship `registry/jellyflam3-presets.json`; on first launch the screensaver applies those values when registry keys are empty (no VoD sideload required on a new Roku when using a zip built on that furnace Pi). See [`roku-channel/README.md`](../roku-channel/README.md) and [docs/phase3/08_JELLYFIN_ID_DUMP.md](../docs/phase3/08_JELLYFIN_ID_DUMP.md).

See [docs/phase1/08_ROKU_BRIGHTSCRIPT.md](../docs/phase1/08_ROKU_BRIGHTSCRIPT.md) and [docs/phase2/03_HLS_CLIENT_STREAMING.md](../docs/phase2/03_HLS_CLIENT_STREAMING.md).

## Deep link

`contentId` = Jellyfin item id → opens HLS stream URL with loop.

Roku allows one `Video` instance only — the channel stops any existing player before starting another (needed for reliable deep link / re-play).
