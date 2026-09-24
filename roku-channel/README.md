# JellyFlam3 Roku channel

Sideloadable SceneGraph channel that lists sheep from Jellyfin with **poster tiles** (`FlockItem`). Tiles use `ImageTags.Primary` only — empty tag shows the **No poster** placeholder (`stills/.ignore` JPEGs are not Primaries). **Ambient loop** defaults to Static MP4; HLS remux remains available for lab compare.

**1.0.51:** `AppLaunchComplete` fires from `HomeScene` at a fully rendered, operable screen (flock, actionable empty/error state, or deep-link playback) instead of at `screen.Show()`; a 5 s guard covers an unreachable furnace and defers while a pre-home Settings dialog is open. **1.0.50:** playback fallback is one-way to Static MP4 — `hls → mp4` still recovers, `mp4 → hls` no longer does. Jellyfin returns these keyframe-sparse loops as a single HLS segment (whole clip behind `#EXTINF:6.0`), which blows past Roku cert **3.6**'s 8 s start budget. **1.0.49:** HD-only splash/icon (`splash_screen_hd`, `mm_icon_focus_hd`); no SD manifest keys. **1.0.48 cert 5.2:** `m.input = CreateObject("roInput")` stays alive; `roInputEvent` requires `DoesExist("mediatype")` and `DoesExist("contentid")` (Roku sample strings). **1.0.47 public-app compliance:** `roInput` uses documented casing (`SetMessagePort` / `IsInput` / `GetInfo`); pre-home dialog beacons cover every Settings screen opened before the flock renders. Store static analysis scans the **uploaded package**, so re-package the `.pkg` on a Roku from this sideload before re-submitting. **1.0.46:** first-run credential Settings fire `AppDialogInitiate` / `AppDialogComplete`; text fields use `StandardKeyboardDialog` (not `KeyboardDialog`). **1.0.45:** `supports_input_launch=1` + `roInputEvent`; `rsg_version=1.3`; no deprecated manifest `subtitle`; `roAppMemoryMonitor` plus `EnableLowGeneralMemoryEvent` fallback. **1.0.44** added `AppLaunchComplete` after Scene show and excluded numbered source-art PNGs (under Roku's 4 MB limit).

## Playback

| `streamMode` (registry) | URL | `streamFormat` | Sessions | Notes |
|------|-----|----------------|----------|-------|
| **`mp4` (default)** | `/Videos/{id}/stream.mp4?Static=true&api_key=…` | `mp4` | `DirectPlay` | Ambient default; seek-to-0 reloop |
| **`hls`** | `/Videos/{id}/main.m3u8?MediaSourceId={id}&api_key=…&AudioCodec=aac` | `hls` | `DirectStream` | Remux compare; usually longer reloop gap |

Roku VOD **cannot gapless-loop** HTTP MP4/HLS with the Video node (`Video.loop` still rebuffers). Channel uses seek-before-EOF; residual hitch is accepted for now. Do **not** use `master.m3u8` on Jellyfin 10.11.

If a sheep is quarantined or Shears-deleted while a clip is queued, **1.0.29+** drops that id after HLS↔MP4 fallback fails, re-polls the flock (30s rate limit), and continues. A failed open does not POST Playing. **1.0.30** always persists `shuffleFlock=true` so an upgrade cannot leave the TV looping one sheep. **1.0.31** treats a wrap as one random permutation of the in-memory list, then re-fetches Jellyfin (HTTP Limit 5000, randomly prune to 313). The new mix is rotated so the first item is not the clip that just finished. Overnight ingest appears without exiting ambient.

The **1.0.36** flock browser wraps every six posters into vertically scrollable rows (three rows visible at once; 270×152 tiles leave a right gutter so column 6 is not clipped). Home copy is **Ambient Dreams** and **N sheep in flock**. Tile metadata is duration / generation / full `cc-*` license (including `cc-by-sa` and `cc-by-nc-sa`). Pedigree tags stay on the detail chip so they do not clip the license on 270px tiles. While the next MP4 connects, the lower-left status shows `{alias}(MP4)` when available.

**1.0.37 settings and controls:** keyboard **OK** validates and persists that field immediately; Back returns without discarding accepted edits. Boolean/title reads are canonicalized. The home status reports effective commercial filtering and alias/fallback counts. NC tags always override safe tags, including conflicting-tag data and deep links. PlayerScreen owns focus so Roku Video cannot swallow vote keys. **1.0.39** replaces Done with **Save & Reload**.

**1.0.38 vote map:** two-tier only — **OK** love, **Right** like, **Down** dismiss overlay, **Up / Back** exit playback. No plain `vote` POST from the channel. Same arrows as a keyboard (Enter / Right / Down / Up-Esc) so a later Kodi overlay can match.

**1.0.43 unreachable furnace:** list fetch failures that look like a timeout stay on a waiting screen (Retry + 30s auto-retry). A clip that fails because the Pi is down does **not** skip through the whole flock into “empty library.” Session Capabilities POST is fire-and-forget so cold-fail is one 15s wait, not two.

**1.0.42 settings toggles:** highlight `commercialMode`, `streamMode`, `shuffleFlock`, or `titleMode` and press **OK** to cycle the two values; each press writes and flushes immediately. **Save & Reload** refreshes the flock. Text credentials still use the keyboard.

**1.0.39 title mode:** highlight `titleMode` and press **OK** to toggle `filename` ↔ `alias`; the value is written and flushed immediately. **Save & Reload** replaces **Done** and fetches the flock with the effective mode. Sheep without an `Alias:` Overview line still show their filename.

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
| `commercialMode` | `true` / `false` — **OK** toggles in Settings (**1.0.42**). Client-side filter on Items **Tags** only: keep `cc-by` / `cc0` / PD / `cc-by-sa`; hide NC and untagged items. NC overrides safe tags regardless of order. Do **not** use Jellyfin `Tags=` query params. Overview `License:` is display-only |
| `streamMode` | `mp4` (ambient loop default) or `hls` (remux compare) — **OK** toggles in Settings (**1.0.42**) |
| `shuffleFlock` | `true` / `false` — **OK** toggles in Settings (**1.0.42**). `true` rotates archive gens (`247…165`) plus pedigree/tuple at EOF (skips `misc`/`test`). Channel **1.0.30** still rewrites `true` on launch so a leftover `false` cannot survive a cold start. |
| `titleMode` | `filename` (default) or `alias` — flock rows + player chrome (**1.0.33**). **OK** toggles in Settings (**1.0.39** / **1.0.42**). Alias is Overview `Alias:`; missing alias falls back to `Name`. Roku screensaver **1.0.11+** has its own Settings toggle for the same key (same registry section only while sharing the developer slot). |
| `displayWidth` / `displayHeight` | From Settings **Fetch TV display** (`roDeviceInfo`) |
| `uiResolution` / `uiWidth` / `uiHeight` | UI resolution name + pixels |
| `videoMode` | e.g. `1080p`, `2160p60` |
| `hdr10` / `hdr10Plus` / `hlg` / `dolbyVision` / `hdrSeamless` | Display HDR capability flags |
| `displayInternal` | `true` if built-in panel (Roku TV) |
| `deviceModel` / `deviceModelName` | Roku model strings |
| `capturedAt` / `displaySummary` | Probe timestamp + one-line summary |

Display keys are **hints only**. **Fetch TV display** also POSTs to `http://{baseUrl-host}:8791/v1/display-profiles` (**one JSON file per screen**). Roku `FormatJson` lowercases AA keys; the Pi sink accepts case-insensitive field names. Override with registry `displaySinkUrl`. Furnace systemd sink **requires** `DISPLAY_SINK_TOKEN` in that Pi’s `secrets.env`; set Roku `displaySinkToken` to match (header `X-JellyFlam3-Token`). Kodi/other clients: `python3 -m pipeline.display_profiles upsert --client Kodi --device-id …`.

## Flock item metadata

Each list item carries browse metadata:

| Field | Source |
|-------|--------|
| `durationLabel` | `RunTimeTicks` → e.g. `23s` |
| `generation` | Tag `generation-N` or `electricsheep.N.*` name/path |
| `license` | Tags `cc-by` / `cc-by-nc` / … or Overview `License:` line |
| `alias` | Overview `Alias:` (sidecar display name) |
| `title` | `Name` or `alias` according to `titleMode` |
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

Developer mode holds **one** sideloaded package. Installing the screensaver zip replaces this VoD channel on that box; re-sideload this zip to restore. To keep **both** installed, publish VoD as a private/unpublished channel ([docs/phase4/04](../docs/phase4/04_ROKU_PUBLISH.md#private-channel-path-wave-2)).

**1.0.41 player chrome:** loading-next (`{alias}(MP4)` / Loading…) and the vote overlay use the same 55% bar and SmallSystemFont line at the bottom of the picture.

**Vote overlay (1.0.32, polish 1.0.40 / chrome 1.0.41):** in the last **7 s** of each non-tuple clip a one-line banner appears without pausing. Left is Settings `titleMode` filename or alias only (no “Like this sheep:” prefix); **OK love · RIGHT like · DOWN dismiss · UP/BACK exit** is right-justified. The name ellipsizes so it cannot overlap the keys. Banner fill and foreground type are **55%** opaque (`0x0A0A128C` / `0xE8E8F08C`). Tuples skip the overlay. The channel POSTs to `http://{Jellyfin-host}:8791/v1/sheep-votes` (same token as display profiles). Playback / Sessions / wrap-once behavior is unchanged.

**Title mode (1.0.33):** Settings `titleMode=alias` shows the memorable `adjective_surname` on flock tiles and player status. Default remains the filename. Sideload this package and, for sheep ingested before this slice, run `python3 -m pipeline.sheep_naming backfill --push-jellyfin` so Overview has `Alias:` lines.

**Screensaver depends on Jellyfin registry keys** (`baseUrl` / `apiKey` / `userId` / `libraryId`). While both packages share the developer slot, VoD Settings populate them and the zip swap keeps them. Private-channel VoD does **not** share registry with sideload SS — use SS Settings **1.0.10** or a furnace-built SS zip. See [`roku-screensaver/README.md`](../roku-screensaver/README.md) and [docs/phase3/08_JELLYFIN_ID_DUMP.md](../docs/phase3/08_JELLYFIN_ID_DUMP.md).

See [docs/phase1/08_ROKU_BRIGHTSCRIPT.md](../docs/phase1/08_ROKU_BRIGHTSCRIPT.md) and [docs/phase2/03_HLS_CLIENT_STREAMING.md](../docs/phase2/03_HLS_CLIENT_STREAMING.md). Splash / Home icon prompts: [docs/CLIENT_CHANNEL_ART.md](../docs/CLIENT_CHANNEL_ART.md).

## Deep link

`contentId` = Jellyfin item id → opens HLS stream URL with loop.

Roku allows one `Video` instance only — the channel stops any existing player before starting another (needed for reliable deep link / re-play).
