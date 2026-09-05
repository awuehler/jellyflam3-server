# 02 — Kodi Electric Sheep screensaver

## Boundary

Phase 3 **standalone** development guide — a **Kodi screensaver add-on / extension** that follows **core Electric Sheep dogma**, not a thin slideshow wrapper around Jellyfin posters. **Fully separate** from the Roku stills/Backdrop track ([01](01_SCREENSAVERS_AND_STILLS.md)). **Do not implement in Phase 2.**

This is its own product surface: idle screen → living flock, in the spirit of the classic distributed screensaver — not “play MP4s until someone presses a key” alone.

## Why separate from Roku guide 01

| Track | Constraint / dogma |
|---|---|
| **Roku** ([01](01_SCREENSAVERS_AND_STILLS.md)) | Platform forbids video in SceneGraph screensavers → stills / posters only |
| **Kodi** (this guide) | Can play **video loops + edge transitions** → much closer to classic Electric Sheep continuous morph |

Do not conflate packages, release cadence, or DoD with the Roku screensaver.

## Electric Sheep dogma (locked intent)

The extension should feel like Electric Sheep’s idle canvas, not a VoD browser:

1. **Continuous ambient motion** — sheep play as seamless loops; silence / no UI chrome while saving.
2. **Journey, not playlist shuffle alone** — prefer **loop → edge → loop** morph sequences when edge MP4s exist ([Phase 4 / 03](../phase4/03_EDGES_AND_WATERMARK.md)); fall back to next-loop only when no edge is available.
3. **Flock as living set** — draw from the JellyFlam3 / Jellyfin Sheep library (and optional local cache); respect license tags (skip NC when “commercial-safe” mode is on).
4. **Server is the furnace, client is the pasture** — Kodi does **not** run `flam3-animate`; it consumes already-rendered loops/edges (HLS or Direct Play per Phase 2). Idle-gate on the Pi stays authoritative.
5. **Social DNA (aspirational within Phase 3)** — optional later: weight toward peered / pedigree-shared genomes; never require the old public Electric Sheep network.
6. **No interactive editing while saving** — any substantial UI belongs in a separate Kodi program/settings screen, not the screensaver render path.

## Architecture sketch

```text
  JellyFlam3 Pi (furnace + Jellyfin)
       │  HLS / Direct Play / optional NFS
       ▼
  Kodi (LibreELEC / CoreELEC / desktop)
       │
       └─ screensaver.jellyflam3 (add-on)
            ├─ settings: server URL, API key, library, license filter
            ├─ sequencer: pick next loop (+ edge when present)
            └─ player: fullscreen, loop-aware, no OSD while active
```

## Deliverables (when built)

| Piece | Notes |
|---|---|
| **Add-on package** | `screensaver.jellyflam3` (or equivalent) for current Kodi Matrix/Nexus+; install via zip / repo |
| **Screensaver entry** | Registers as a system screensaver; starts on idle per Kodi settings |
| **Sequencer** | ES-dogma loop/edge logic; configurable dwell / cut behavior |
| **Library client** | Jellyfin Items API and/or local path to flock; reuse Phase 2 auth patterns |
| **Settings** | Host, credentials, commercial-safe filter, prefer-edges toggle |
| **Docs** | Install on a Kodi pasture box; point at a furnace Pi; troubleshooting |

## Non-goals

- Reimplementing flam3 render inside Kodi
- Bundling with the Roku screensaver package
- Requiring Channel Store / official Kodi repo on day one (sideload zip OK for DoD)
- Full classic client P2P ratings network (may appear later under “social flock”)

## Dependencies

- Phase 2: Jellyfin flock + HLS/Direct Play path
- Phase 3 [01](01_SCREENSAVERS_AND_STILLS.md): stills optional for poster fallback only — **not** required for Kodi video path
- Phase 4 [03](../phase4/03_EDGES_AND_WATERMARK.md): edges strongly preferred for dogma-complete journeys (parked; loops-only OK in Phase 3)

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `kodi-screensaver/` / `screensaver.jellyflam3` | add-on | Installable Kodi screensaver package |
| Add-on settings (URL, API key, library, filters) | config | Point at lab Pi Jellyfin Sheep library |
| Sequencer (loop / edge / dwell) | code | ES-dogma journey; prefer edges from [Phase 4 / 03](../phase4/03_EDGES_AND_WATERMARK.md) when present |
| Library client (Jellyfin Items / local flock) | code | Consume rendered loops/edges only |
| `kodi-screensaver/README.md` (or guide install notes) | docs | Install + troubleshooting |

## Status

**Complete** for Phase 3 loops-only scope — Owner OK 2026-08-21.

**Deferred to Phase 4:** when edges exist, sequencer performs **loop→edge→loop** (documented config). Tracked under [../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md) (Kodi client path). Loops-only shuffle flock is the Phase 3 DoD.

**Deferred polish (Phase 4):** flock list is loaded once per screensaver session (`default.py` → `_load_flock`); mid-session wrap only reshuffles that list. New Jellyfin items (e.g. a new gen folder after daily seed) need a new idle session today. Optional **long-interval re-fetch** (hours / wrap) is parked under [../phase4/00_OVERVIEW.md](../phase4/00_OVERVIEW.md#client-polish-parked--not-numbered) — not required for ~daily ingest. Separate parked item: if a sheep is **quarantined** (or Shears-deleted) mid-session, a file-not-found / 404 on the next loop should **re-poll** the flock index and continue — same contract on Roku VoD and Roku SS.

## Exit criteria

- [x] Add-on installs and appears under Kodi Screensaver settings — Owner OK 2026-08-21
- [x] Idle start plays Sheep loops fullscreen without interactive chrome — Owner OK 2026-08-21
- [x] ~~When edges exist, sequencer performs loop→edge→loop~~ — **deferred to Phase 4** ([03_EDGES_AND_WATERMARK](../phase4/03_EDGES_AND_WATERMARK.md)); Owner OK 2026-08-21
- [x] License filter honored (e.g. hide NC in commercial-safe mode) — Owner OK 2026-08-21 (0.2.1 client-side filter)
- [x] Does not trigger Pi furnace renders (idle-gate / Sessions behavior verified) — Owner OK 2026-08-21
- [x] Install + dogma notes in this guide (or linked README under `kodi-screensaver/`) — README documents Jellyfin URL/API key/user/library IDs + dump/manual collection

## Implementation status (2026-08-21)

Tasks **1–4** (package / screensaver entry / fullscreen player / zip) and **Jellyfin flock client + license filter + shuffle sequencer** are in tree (**0.2.1**). Commercial-safe empty-flock bug fixed (drop Jellyfin `Tags=` query; filter client-side). Loop→edge sequencer is Phase 4 work after edges exist.

| Piece | Location |
|---|---|
| Add-on | [`kodi-screensaver/screensaver.jellyflam3/`](../../kodi-screensaver/screensaver.jellyflam3/) |
| Flock client | [`resources/lib/jellyfin_flock.py`](../../kodi-screensaver/screensaver.jellyflam3/resources/lib/jellyfin_flock.py) |
| Install notes | [`kodi-screensaver/README.md`](../../kodi-screensaver/README.md) |
| Zip | `./scripts/package_kodi_screensaver.sh` on a **furnace Pi** (or `.ps1` on Windows) → `dist/screensaver.jellyflam3.zip`; furnace build pre-fills Jellyfin settings via `client_pack_presets.py` |

Lab smoke (2026-08-20/21, **`rpi-kodi-08a`** LibreELEC): **0.1.5** placeholder hold OK; **0.2.0** Jellyfin Static MP4 flock (Client=`JellyFlam3-Screensaver`, idle-gate ignored); **0.2.1** commercial-safe flock (4 `cc-by` items). Phase 3 guide closed; edge journeys → Phase 4.

Prior smoke (2026-08-18, Debian `rpi-kodi-01a`): placeholder played; host retired for LibreELEC rebuild.

## Example Kodi host

Reference Kodi pasture box (separate from the JellyFlam3 furnace fleet):

| | |
|---|---|
| Hostname | e.g. `rpi-kodi-08a` |
| LAN | `<Kodi_IP_Address>` |
| SSH | `root@<Kodi_IP_Address>` (LibreELEC default password; prefer key) |
| Board | Raspberry Pi 5 Model B Rev 1.1 (~16 GB) |
| OS | **LibreELEC 12.2.1** (`RPi5.aarch64`) |
| Kodi | **21.3 Omega** (LibreELEC bundled) |
| Add-on path | `/storage/.kodi/addons/screensaver.jellyflam3` |
| Zip drop | `/storage/downloads/screensaver.jellyflam3.zip` |

Furnace / Jellyfin remains on the render fleet (`rpi-jellyflam3-16a`, `-08a`, `-04a` at their LAN IPs). This host is pasture only — it does not run `jellyflam3-worker`.

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [01_SCREENSAVERS_AND_STILLS.md](01_SCREENSAVERS_AND_STILLS.md) (Roku/stills only) · [../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md) · classic client [electricsheep](https://github.com/scottdraves/electricsheep) · architecture [Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md)
