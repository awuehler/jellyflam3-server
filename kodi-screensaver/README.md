# JellyFlam3 Kodi screensaver (`screensaver.jellyflam3`)

Phase 3 [guide 02](../docs/phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) — Electric Sheep–dogma **video** screensaver for Kodi. Separate from [`roku-screensaver/`](../roku-screensaver/).

**Example host:** `rpi-kodi-08a` (`<Kodi_IP_Address>`), LibreELEC 12.2.1 / Kodi 21.3 Omega. SSH `root@<Kodi_IP_Address>`.

## Status (0.2.2) — Phase 3 complete

Tasks **1–4** done; **Jellyfin flock client + commercial filter + shuffle sequencer** in **0.2.0+**. Guide 02 Owner OK 2026-08-21 (loops-only).

- Add-on settings: Jellyfin URL, API key, user id, library id, commercial-safe, max items
- Fetches `/Users/{userId}/Items` → Static MP4 (`/Videos/{id}/stream.mp4?Static=true`); shuffles; advances on EOF
- Commercial-safe filters Items **client-side** (0.2.1 — Jellyfin `Tags=` query returned an empty flock)
- Client `JellyFlam3-Screensaver` matches furnace `idle_gate.ignore_client_patterns`
- When settings or flock are unavailable, shows a short on-screen hint on black (no bundled test-pattern video)
- Cancels Kodi’s 15s StopScript alarm (`sssssscreensaver`) so idle video is not killed

**Post-launch:** loop→edge→loop sequencer (edges + watermark) is not in v0.3.0.

## Configure Jellyfin (flock)

**Furnace-built zip:** when `package_kodi_screensaver.*` runs on a Pi with `secrets.env`, `client_pack_presets.py` sets default values in the packaged `settings.xml` (`server_url`, `api_key`, `user_id`, `library_id` for **that** furnace’s Jellyfin). After install-from-zip, open **Configure** once to confirm — no paste required on first install.

**Manual configure:** **Add-ons → My add-ons → Screensaver → JellyFlam3 Dreams → Configure**, or edit:

`/storage/.kodi/userdata/addon_data/screensaver.jellyflam3/settings.xml`

| Add-on setting | Setting id | Jellyfin value |
|---|---|---|
| **Jellyfin URL** | `server_url` | LAN base URL the **Kodi box** can reach (e.g. `http://<RPi_IP_Address>:8096`). Never `127.0.0.1` / `localhost` — those are the furnace’s loopback, not Kodi’s. |
| **API key** | `api_key` | Jellyfin API key string (Dashboard → API Keys, or furnace `JELLYFIN_API_KEY`). |
| **User id** | `user_id` | User **Guid** for `/Users/{id}/Items` (not the login name). |
| **Library (Parent) id** | `library_id` | Sheep library / view **Guid** (`ParentId`). Recommended. Empty = all Movie/Video items the user can see. |
| **Commercial-safe (skip NC)** | `commercial_mode` | Client-side tag filter only: keep `cc-by` / `cc0` / `public-domain` / `pd` / `cc-by-sa`; hide NC. Does **not** send Jellyfin `Tags=` query params. |
| **Max items to fetch** | `flock_limit` | Cap before shuffle (default `200`). |

Do **not** commit API keys or filled `settings.xml` into git.

### Collect each ID (preferred: dump script)

On a furnace Pi (`/opt/jellyflam3-server`, with `secrets.env`):

```bash
cd /opt/jellyflam3-server
python3 scripts/jellyfin_id_dump.py
python3 scripts/jellyfin_id_dump.py --show-secrets   # full apiKey once; careful
python3 scripts/jellyfin_id_dump.py --items --limit 20     # optional item Guids (smoke only)
```

Map dump output → add-on settings:

| Dump field | Paste into |
|---|---|
| `baseUrl` (from `JELLYFIN_PUBLIC_URL` / LAN URL) | **Jellyfin URL** |
| `apiKey` | **API key** |
| `userId` | **User id** |
| `libraryId` | **Library (Parent) id** |

The dump also lists **Users** and **Views / libraries** so you can pick Guids if `secrets.env` is incomplete. Prefer a LAN `baseUrl` (`JELLYFIN_PUBLIC_URL=http://<furnace-lan-ip>:8096`), not `127.0.0.1`.

Full ops notes: [docs/phase3/08_JELLYFIN_ID_DUMP.md](../docs/phase3/08_JELLYFIN_ID_DUMP.md).

### Collect each ID (manual / Dashboard)

| Setting | Manual source |
|---|---|
| **Jellyfin URL** | Furnace LAN IP + port `8096`. From a browser on the same LAN as Kodi, open that URL to confirm reachability. |
| **API key** | Jellyfin Dashboard → **API Keys** → New; or copy `JELLYFIN_API_KEY` from furnace `secrets.env` (never commit). |
| **User id** | Dashboard → Users → open the user; Guid is in the URL (`…/user?userId=…`), or use the dump’s Users list. |
| **Library id** | Dashboard → Libraries → Sheep library; Guid from library URL/settings, or the dump’s Views row for that library name. Same value as furnace `JELLYFIN_LIBRARY_ID` when set. |

The same four values feed the [Roku channel](../roku-channel/README.md) registry (`baseUrl` / `apiKey` / `userId` / `libraryId`).

## Package

**On a furnace Pi** (recommended — pre-configured zip):

```bash
cd /opt/jellyflam3-server
./scripts/package_kodi_screensaver.sh
# → dist/screensaver.jellyflam3.zip (Jellyfin defaults from secrets.env)
```

Requires **Pillow** (`python3-pil` or `pip install -r requirements.txt`). The script runs `build_kodi_screensaver_assets.py` and `client_pack_presets.py` automatically.

Windows (no furnace presets):

```powershell
.\scripts\package_kodi_screensaver.ps1
```

Regenerate store art from live flock posters (preferred) or splash fallback:

```bash
python3 scripts/build_kodi_screensaver_assets.py --fetch-fleet   # SCP posters from 16a/08a/04a
python3 scripts/build_kodi_screensaver_assets.py                 # use cached resources/posters/
python3 scripts/build_kodi_screensaver_assets.py --splash-fallback
```

Cached sources: `resources/posters/fleet-{16a,08a,04a}-gen*.jpg` (gen 243 / 244 / 242).

## Install (lab — LibreELEC)

1. Copy `dist/screensaver.jellyflam3.zip` to the box (e.g. `/storage/downloads/`).
2. Kodi → **Add-ons → Install from zip file** (enable unknown sources if prompted), **or** unzip into `/storage/.kodi/addons/` (folder name must be `screensaver.jellyflam3`).
3. Enable the add-on if needed, then **Settings → Interface → Screensaver** → **JellyFlam3 Dreams**.
4. Configure Jellyfin flock settings (above), set wait time (lab uses **1 minute**), then wait — or **Activate screensaver** / `kodi-send --action='ActivateScreensaver'`.

Stop Kodi before editing `/storage/.kodi/userdata/guisettings.xml` or `Database/Addons33.db` by hand — a running instance will overwrite settings on exit.

Any remote/keypress (and JSON-RPC) exits the screensaver (Kodi default).

**Flock refresh:** the add-on loads the Jellyfin flock once when a screensaver session starts and only reshuffles that list until exit. New catalog sheep (after Jellyfin has indexed them) appear on the **next** session. Optional mid-session long-interval re-fetch is Phase 4 polish — see [docs/phase4/00_OVERVIEW.md](../docs/phase4/00_OVERVIEW.md#client-polish-parked--not-numbered).

## Layout

```
kodi-screensaver/screensaver.jellyflam3/
  addon.xml
  default.py
  resources/settings.xml
  resources/lib/jellyfin_flock.py
  resources/icon.png
  resources/posters/          # fleet *-poster.jpg sources (16a/08a/04a)
  resources/fanart.jpg
  resources/screenshot-01.jpg … screenshot-03.jpg
  resources/skins/default/1080i/fallback.xml
```

## See also

[Guide 02](../docs/phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) · [Jellyfin ID dump](../docs/phase3/08_JELLYFIN_ID_DUMP.md) · [Roku channel Settings](../roku-channel/README.md)
