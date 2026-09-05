# 04 — JellyFlam3 Roku channel polish

## Boundary

BrightScript/SceneGraph UX for the **JellyFlam3** VoD channel: posters, metadata, layout/focus, and TV display probe — **stop before** Syncthing peering ([05](05_SYNCTHING_GENOME_PEERING.md)). Depends on Primary images from [02](02_JELLYFIN_FLOCK_UX.md) and HLS play path from [03](03_HLS_CLIENT_STREAMING.md).

**Status: complete** — Owner OK 2026-08-02 (pieces A–F; channel 1.0.23; two live Roku profiles on Pi).

## Intent

Path 2 channel is playable (list → play → settings; ambient MP4 / optional HLS). Phase 2 polish makes the flock **browsable and TV-aware**: real posters, focus metadata, solid empty/loading/error UX, and a display-settings probe that hints the furnace — **without** auto-retargeting encode resolution on the Pi.

## Locked decisions

1. **Playback:** carry [03](03_HLS_CLIENT_STREAMING.md) — ambient `streamMode=mp4`; optional HLS; keep `/Sessions` Playing reports.
2. **Display probe:** registry + Pi sink are **hints only** — furnace must **not** auto-retarget to 4K on lab/3-core class Pi in Phase 2.
3. **Version:** bump `manifest` + auth `Version=` together on each sideload for this guide.

## Implementation pieces (order)

| Piece | Status | Notes |
|---|---|---|
| **A** Poster RowList item UI | Done (Owner OK 2026-08-01) | Channel 1.0.16: `FlockItem` posters; Primary thumbnails + HLS/MP4 loops confirmed on sideload |
| **B** Metadata fields on items | Done (Owner OK 2026-08-02) | Channel 1.0.17: duration/generation/license/pedigree + status `metaLine` on focus |
| **C** Focus / detail chrome | Done (Owner OK 2026-08-02) | Channel 1.0.18: detail panel + tile meta; sideload focus confirmed |
| **D** Empty / loading / error UX | Done (Owner OK 2026-08-02) | Channel 1.0.19: Loading/empty/error + Retry; streamMode validate; Focus footer |
| **D2** Continuous random flock | Done (Owner OK 2026-08-02) | Channel 1.0.20: `shuffleFlock`; archive gens only; EOF advances |
| **E** TV display probe → registry | Done (Owner OK 2026-08-02) | Channel 1.0.21: Settings **Fetch TV display**; registry capture + recall confirmed |
| **F** Pi sink + version + sideload | Done (Owner OK 2026-08-02) | Channel 1.0.22–23: sink `:8791`; two live Roku POSTs (TV + SmartBar); FormatJson lowercase-key fix |

**Why this order:** posters first (visible win on existing Primary images) → data for chrome → chrome UI → resilience UX → probe (no Pi dependency) → Pi write path + package.

## Guidelines

### Playback (from guide 03)

- Ambient play path is Static **MP4** loop by default (`streamMode=mp4`); HLS remux via `streamMode=hls` per [03](03_HLS_CLIENT_STREAMING.md).
- Preserve `/Sessions` Playing reports so idle-gate still matches the Roku client during HLS.

### Catalog / layout

- Bind `hdPosterUrl` (already built in `JellyfinTask.mapItem`) into RowList/Poster markup; request image-related Fields as needed.
- Follow [Roku SceneGraph](https://developer.roku.com/docs/developer-program/core-concepts/scenegraph.md) practices: focus rings, safe margins, loading/error/empty states, Back stack.
- Metadata chrome: duration, generation, license tag, optional pedigree when present.
- Align channel `manifest` version with auth header Client Version string; bump for each sideload.

### TV display probe (locked)

- Settings action **Fetch TV display** (piece **E**, channel 1.0.21): capture via `roDeviceInfo` (display size, UI resolution, video mode, HDR flags, model) and persist in `roRegistrySection` `JellyFlam3`.
- Registry keys: `displayWidth`, `displayHeight`, `uiResolution`, `uiWidth`, `uiHeight`, `videoMode`, `displayAspect`, `hdr10`, `hdr10Plus`, `hlg`, `dolbyVision`, `hdrSeamless`, `displayInternal`, `deviceModel`, `deviceModelName`, `capturedAt`, `displaySummary`.
- Phase 2: **hint only** — furnace must **not** auto-retarget to 4K on 3-core Pi.
- Piece **F**: POST/drop JSON to the Pi under `/var/lib/jellyflam3/display_profiles/` (or small ops endpoint), keyed as **separate TV screens** (below).

### Piece F — multi-screen display profiles (locked for implementation)

Households will have **more than one** ambient screen. The Pi sink must **track each screen as its own profile**, not overwrite a single global blob.

| Screen class | Examples | Identity requirements |
|---|---|---|
| **Roku (+1 devices)** | Extra Roku Streaming Stick / Express / Ultra on HDMI | Stable per-device id (e.g. `roDeviceInfo` channel client id / model+serial-derived key) + display probe fields from piece E |
| **Roku TVs** | Hisense / TCL / etc. with built-in Roku | Same as above; `displayInternal=true` is a useful flag, not a unique key |
| **3rd screens (non-Roku)** | **Kodi** (Phase 3 ES screensaver and/or Jellyfin client), VLC, jellyfin-roku, future web | Client/platform tag + host- or installation-stable id; probe fields as available (may be partial vs Roku E) |

**Sink rules (piece F — implemented):**

1. **One file per screen** under `paths.display_profiles` (default `/var/lib/jellyflam3/display_profiles/`) named `{client}-{deviceId}.json`.
2. HTTP service: `python3 -m pipeline.display_profile_sink` (systemd `jellyflam3-display-sink.service`) on **port 8791**.
   - `POST/PUT /v1/display-profiles` — upsert JSON body
   - `GET /v1/display-profiles` — list summaries
   - `GET /healthz`
3. Channel **1.0.22+**: after **Fetch TV display**, POSTs profile with `client=JellyFlam3` and `deviceId` from `GetChannelClientId()`; sink URL defaults to `http://{baseUrl-host}:8791` (override registry `displaySinkUrl`). Roku `FormatJson` lowercases AA keys (`deviceid`); the sink accepts case-insensitive field names and stores camelCase.
4. Optional `DISPLAY_SINK_TOKEN` / registry `displaySinkToken` → header `X-JellyFlam3-Token`.
5. **Kodi / 3rd screens:** same schema via CLI (no Roku UI required):
   ```bash
   python3 -m pipeline.display_profiles upsert --client Kodi --device-id living-room --file profile.json
   ```
6. Still **hint only** for the furnace — no auto-4K retarget on 3-core Pi.

## Commands

```bash
# Package + sideload (from Windows/dev host)
./scripts/package_roku_channel.ps1
# Upload zip via Roku developer installer; Settings → Fetch TV display → expect "Pi OK …json"

# Pi: enable sink (once)
sudo mkdir -p /var/lib/jellyflam3/display_profiles
sudo chown jellyflam3:jellyflam3 /var/lib/jellyflam3/display_profiles
sudo cp /opt/jellyflam3-server/deploy/systemd/jellyflam3-display-sink.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jellyflam3-display-sink
curl -sS http://127.0.0.1:8791/healthz
python3 -m pipeline.display_profiles list
```

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `roku-channel/` | channel | Posters, metadata chrome, shuffle, TV probe |
| `scripts/package_roku_channel.{sh,ps1}` | script | Package sideload zip |
| `pipeline/display_profile_sink.py` | pipeline | HTTP upsert of per-screen profiles (:8791) |
| `pipeline/display_profiles.py` | pipeline | CLI list / upsert display profiles |
| `deploy/systemd/jellyflam3-display-sink.service` | deploy | Always-on sink service |
| `/var/lib/jellyflam3/display_profiles/` | config | One JSON file per screen identity |

## Exit criteria

- [x] Flock list shows posters when Jellyfin has Primary images — Owner OK 2026-08-01 (1.0.16)
- [x] Metadata row visible on focus/detail — Owner OK 2026-08-02 (1.0.18)
- [x] Empty / error / loading states acceptable per Roku practices — piece D (1.0.19); Owner OK 2026-08-02
- [x] Continuous shuffle (`shuffleFlock`) advances archive-gen sheep only — piece D2 (1.0.20); Owner OK 2026-08-02
- [x] Fetch TV display writes registry — piece E (1.0.21); Owner OK 2026-08-02
- [x] Pi `display_profiles/` sink updated — piece F (1.0.22–23); Owner OK 2026-08-02 (`Pi OK` + `display_profiles list`)
- [x] ≥2 screen identities retained on Pi — Owner OK 2026-08-02 (Roku TV + Roku Soundbar; distinct `deviceId`s)
- [x] Sideload verified on lab Roku; version bumped — Owner OK 2026-08-02 (channel **1.0.23**)

### Continuous random flock playback (piece D2 — channel 1.0.20)

Settings `shuffleFlock` (default `false`):

- **false:** ambient seek-reloop of the selected sheep (unchanged).
- **true:** at end-of-clip, advance to another sheep in **random order**. Eligible pool:
  - Only archive generations `[247, 245, 244, 243, 242, 198, 191, 169, 165]` via item `generation` or `Path` under `/by-generation/{N}/` (see [01](01_ARCHIVE_SEED_LIBRARY.md)).
  - **Ignore** `by-generation/misc`, `by-generation/test`, and other non-allowlisted locations.
  - Still respects `commercialMode` on the list fetch.
- Back exits player and clears the shuffle round.
- Mid-session **quarantine / Shears delete** can 404 the next shuffle pick; auto re-poll of the flock list is [Phase 4 client polish](../phase4/00_OVERVIEW.md#client-polish-parked--not-numbered) (all pasture endpoints).

## Future improvements (not pieces E–F)

### Include genomic VoD variations (later)

After pedigree / local breed paths produce catalog MP4s ([07](07_PEDIGREE_BREEDING.md)), widen continuous-shuffle (and optionally browse) eligibility beyond the nine archive folders to **genomic VoD variations**:

- VoDs whose genomes are JellyFlam3-produced (mutate / cross / blend / interpolate / local brood), typically tagged `origin: local_pedigree` (or equivalent path/name `electricsheep.pedigree.*`).
- Keep excluding `misc` / `test` and other non-flock scratch locations unless an operator explicitly opts in.
- License filter (`commercialMode`) still applies — NC pedigree offspring stay out when commercial mode is on.
- Optional Settings refinement later: “archive gens only” vs “archive + genomic variations” vs “genomic only”.

Depends on pedigree ingest being real on the Pi and stable item metadata the channel can filter on.

## See also

[../phase1/08_ROKU_BRIGHTSCRIPT.md](../phase1/08_ROKU_BRIGHTSCRIPT.md) · [`roku-channel/`](../../roku-channel/) · [03_HLS_CLIENT_STREAMING.md](03_HLS_CLIENT_STREAMING.md) · [07_PEDIGREE_BREEDING.md](07_PEDIGREE_BREEDING.md)
