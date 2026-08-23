# 08 — Roku BrightScript channel

## Boundary

Custom JellyFlam3 channel only — not jellyfin-roku, not screensaver.

## Package

`roku-channel/` — sideload via Developer Mode. Client name **JellyFlam3** for idle-gate matching.

| Path | Role |
|---|---|
| `manifest` | Channel metadata + splash/icon |
| `source/main.brs` | `roSGScreen` + deep link / `roInput` |
| `components/HomeScene.*` | RowList flock browser + Options→settings |
| `components/FlockRowList.*` | RowList that forwards `*` / Options to settings |
| `components/PlayerScreen.*` | Single `Video` (`loop=true`); default `streamFormat=hls`; stop before restart |
| `components/JellyfinTask.*` | Jellyfin Items + HLS/`main.m3u8` stream URLs (off UI thread) |
| `components/SettingsScreen.*` / `SettingRow.*` | Registry editor for credentials |
| `images/` | `mm_icon_focus_hd.png` (290×218), `splash-screen.png` |

Settings registry section `JellyFlam3`: `baseUrl`, `apiKey`, `userId`, `libraryId`, `commercialMode`.

Deep link: `contentId` = Jellyfin item id → dedicated item Task → `PlayerScreen` with `loop=true`.  
Roku allows only **one** `Video` play instance: HomeScene always `stopPlayer()` before starting another stream (build 8+). List refresh never autoplays while a deep link is in flight.

## Build zip

```powershell
# Windows
.\scripts\package_roku_channel.ps1
# → dist/jellyflam3-roku.zip
```

```bash
# Linux / Pi / macOS
./scripts/package_roku_channel.sh
```

## Sideload (Developer Mode)

1. On the Roku: **Settings → System → Advanced system settings → Developer options** — enable installer; note IP + password.
2. On a PC on the same LAN, open `http://<roku-ip>` → log in → **Upload** `dist/jellyflam3-roku.zip` → **Install**.
3. Launch **JellyFlam3** from the home row (dev channel).
4. Settings opens automatically when `apiKey` / `userId` are empty. Otherwise use the on-screen **Settings** button, or **\*** / **Options** / **Info** (RowList no longer swallows `*`).
5. In settings: **Up/Down** between field buttons, **OK** opens the keyboard for that field, **Save** writes registry, **Cancel** / **Back** exits.
   - `baseUrl` — e.g. `http://192.168.X.Y:8096` (Pi Jellyfin LAN IP; no trailing slash)
   - `apiKey` — JellyFlam3 API key from `secrets.env`
   - `userId` — Jellyfin user id (required)
   - `libraryId` — Sheep library id (recommended)
   - `commercialMode` — `false` unless filtering NC
   - Tip: dump IDs with `python3 scripts/jellyfin_id_dump.py` ([phase3/08](../phase3/08_JELLYFIN_ID_DUMP.md))
6. After save → flock RowList should populate; select a dream → looped playback; **Back** returns to list.

## Deep link ECP smoke

```bash
# Replace ROKU_IP and ITEM_ID (Jellyfin item Guid)
curl -d '' "http://ROKU_IP:8060/launch/dev?contentId=ITEM_ID"
```

Confirm on device / ECP:

```bash
curl -s "http://ROKU_IP:8060/query/active-app"     # JellyFlam3 (dev), version 1.0.8+
curl -s "http://ROKU_IP:8060/query/media-player"   # state=play, error=false, position advancing
```

Validated on a LAN Roku with build **1.0.8**: deep link started 1080p Direct Play without `only one playing instance supported`. Build **1.0.9** adds `/Sessions/Playing` reporting for idle-gate. Build **1.0.13** adds Jellyfin **HLS** remux (`main.m3u8` + `AudioCodec=aac`). Build **1.0.14+** ambient default = Static MP4 (`streamMode=mp4`); **1.0.15** seek-to-0 reloop (native `Video.loop` gaps on both MP4 and HLS) — see Phase 2 [03_HLS_CLIENT_STREAMING.md](../phase2/03_HLS_CLIENT_STREAMING.md).

## Idle-gate session identity

HTTP calls send `Client="JellyFlam3"`, `Device="Roku"`, `DeviceId="jellyflam3-roku"` and POST `/Sessions/Capabilities/Full` so `GET /Sessions` matches `idle_gate.tv_client_patterns`.

Note: build **1.0.9+** reports `/Sessions/Playing` (and progress/stopped) from `PlayerScreen` so idle-gate can see Direct Play. Identity alone (`Capabilities/Full`) is not enough for `NowPlayingItem`.

## Networking notes

- `baseUrl` must be reachable **from the Roku** (same LAN; no AP/client isolation). Example: `http://192.168.X.Y:8096`.
- Jellyfin Task uses a **15s HTTP timeout** and returns the failure reason on screen if the TV cannot connect.
- Confirm from a phone/PC on the same Wi‑Fi as the Roku: `http://<pi>:8096/System/Info/Public`.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `roku-channel/` | channel | JellyFlam3 SceneGraph channel source |
| `scripts/package_roku_channel.{sh,ps1}` | script | Produce `dist/jellyflam3-roku.zip` |
| `dist/jellyflam3-roku.zip` | channel | Sideload artifact |
| `scripts/jellyfin_id_dump.py` | script | Dump userId / libraryId for channel Settings |
| Roku ECP (`:8060`) | binary | Deep-link / active-app / media-player smoke |

## Exit criteria

- [x] Sideload succeeds; RowList shows items
- [x] Playback loops; Back works
- [x] Deep link ECP smoke (`launch/dev?contentId=…`)
- [x] Session visible as JellyFlam3/Roku (`DeviceId=jellyflam3-roku`)
