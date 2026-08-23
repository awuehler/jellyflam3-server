# Phase 2 overview

## Boundary

Phase 2 scope lock, reading order, and definition of done only — **no install steps**.

Architecture SoT: [Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md) (re-synced 2026-08-08). Phase 1 is **complete** ([../phase1/00_OVERVIEW.md](../phase1/00_OVERVIEW.md)). **Phase 2 is complete** (Owner OK 2026-08-08 — [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md)).

## Non-goals (deferred to Phase 3+)

- Standalone Roku Screensaver / Backdrop package (`RunScreenSaver`)
- Stills extraction + **Roku** Screensaver/Backdrop ([../phase3/01_SCREENSAVERS_AND_STILLS.md](../phase3/01_SCREENSAVERS_AND_STILLS.md))
- **Kodi** Electric Sheep–dogma screensaver extension ([../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)) — separate from Roku
- LLM-assisted pedigree breeding
- **Sheep Shears** (add/modify/delete `.flam3` + cascade downstream artifacts)
- **Edge / transition crossfades** + **sheep watermark** (see Phase 4 [03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md))
- **Shared sheep security** — pre/post share checksums/signatures ([../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md))
- **Git pedigree sheep** — curated in-repo pedigree `.flam3` for smoke/examples; replace legacy samples ([../phase3/06_GIT_PEDIGREE_SHEEP.md](../phase3/06_GIT_PEDIGREE_SHEEP.md))
- **JellyFlam3 Hammer** — purge history, reset worker env, wipe all render inputs/outputs ([../phase3/07_JELLYFLAM3_HAMMER.md](../phase3/07_JELLYFLAM3_HAMMER.md))
- **Sheep refactor** — sub-standard quality / palette / encode repair ([../phase3/09_SHEEP_REFACTOR.md](../phase3/09_SHEEP_REFACTOR.md))
- DeepDream / AI render backends, Channel Store certification, full social flock network
- First-class web player (may appear later; not required for Phase 2 DoD)
- Continuous / live HLS from shuffled flock MP4s (dropped from Phase 3)

## Baseline already shipped (do not rebuild)

Treat as prerequisites; polish only where guides say so:

- Archive seed picker (`python -m pipeline.seed_inbox --archive`)
- TV-port 16:9 + Gold Sheep Lite + OkLCh complementary tint
- `scripts/status_report.sh`

## Reading order

See [docs/README.md](../README.md). Execute guides **01 → 10** in order (01 is mostly verification of baseline).

| # | Guide | Focus |
|---|---|---|
| 00 | This file | Scope / DoD |
| 01 | [01_ARCHIVE_SEED_LIBRARY.md](01_ARCHIVE_SEED_LIBRARY.md) | Archive feedstock (baseline) — **complete** |
| 02 | [02_JELLYFIN_FLOCK_UX.md](02_JELLYFIN_FLOCK_UX.md) | Posters / metadata — **complete** |
| 03 | [03_HLS_CLIENT_STREAMING.md](03_HLS_CLIENT_STREAMING.md) | HLS from Jellyfin → Roku / VLC / etc. — **complete** |
| 04 | [04_ROKU_CHANNEL_POLISH.md](04_ROKU_CHANNEL_POLISH.md) | JellyFlam3 app UX + TV probe — **complete** |
| 05 | [05_SYNCTHING_GENOME_PEERING.md](05_SYNCTHING_GENOME_PEERING.md) | Tailscale + Syncthing (`*.flam3` + optional `*-poster.jpg`) — **complete** (Owner OK 2026-08-08; fixture promote) |
| 06 | [06_SHEEP_TAX.md](06_SHEEP_TAX.md) | Genome XML / vocab scan & repair — **complete** |
| 07 | [07_PEDIGREE_BREEDING.md](07_PEDIGREE_BREEDING.md) | Mutate / cross / blend — **complete** (Owner OK 2026-08-04) |
| 08 | [08_DYNAMIC_DURATION.md](08_DYNAMIC_DURATION.md) | XML signals + soft/hard max — **complete** (Owner OK 2026-08-08; Pi verify) |
| 09 | [09_PI_FROM_SCRATCH.md](09_PI_FROM_SCRATCH.md) | End-user Pi build / 2nd system — **complete** (Owner OK 2026-08-08; `rpi-jellyflam3-08a`) |
| 10 | [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md) | Sign-off — **complete** (Owner OK 2026-08-08) |

Parallel after **02**: `03` (HLS) can start before posters land; `04` needs Primary images. `05`–`08` largely independent of Roku polish. `09` consolidates prior phases; acceptance (`10`) last.

## Locked implementation decisions

1. **Posters:** filesystem beside MP4 **and** Jellyfin Images API with retry; mid-loop frame; backfill existing flock.
2. **HLS delivery:** Jellyfin is the stream origin; **HLS** is first-class for Roku, VLC, and similar clients; prefer **Direct Stream / remux** (no re-encode) for Gold Sheep Lite masters; full HLS transcode is fallback under idle-gate; Direct Play MP4 remains allowed for ambient loop when HLS loop is weak.
3. **Display probe:** Roku Settings fetch → registry + POST/drop on Pi; **no** auto-4K retarget in Phase 2.
4. **Duration:** HW profile overlays scale soft/hard VoD bands + `dynamic.base_sec` by Pi class (filesystem headroom); example defaults min **11 s**, soft **37 s**, hard **90 s** (see `configs/profiles/`). **`vod.dynamic.snap_to_periods: true` is the locked fleet default** on every profile (seamless loops). Period-snap LCM can still jump toward soft max — documented awareness in [08](08_DYNAMIC_DURATION.md), not an open config debt.
5. **Blend:** genetic **cross** of two parents; multi-flame parents strip-to-first or reject.
6. **Peering (Syncthing over Tailscale):** default **Opt Out**; **host service** is the only user-facing touch point (Opt In / Opt Out). Opt In enrolls Tailscale (auth → tags/ACLs) and starts Syncthing with managed config; Opt Out stops Syncthing, revokes/removes the tailnet node, cleans credentials, disables services. Sync = **`*.flam3` + optional `*-poster.jpg`**; **eventually** only pedigree-generated (server-unique) sheep — not archive Free Sheep re-shares. Syncthing **lands** in `genomes/peers/inbox` — **not** auto-ingested by the worker; gated **promote** (+ sheep tax) moves to `genomes/inbox` for render.
7. **Sheep tax:** scan/repair each `.flam3` for well-formed XML, key–values, and flam3 vocabulary before furnace trust / peer promote.
8. **HW profile `-04`:** same Gold Sheep Lite quality / `max_cpus: 3` as `-08`/`-16`; shorter dynamic duration + leaner encode for disk. Hostnames: `rpi-jellyflam3-{16,08,04}{a,b,…}`.

## Definition of done

Phase 2 is complete when guides 01–10 exit criteria pass, including:

- [x] Archive baseline verified on Pi (01) — Owner OK 2026-07-30
- [x] Primary posters in Jellyfin web + jellyfin-roku + JellyFlam3; backfill path documented (02) — Owner OK 2026-07-31
- [x] HLS play path verified on VLC + JellyFlam3 Roku (and jellyfin-roku smoke); remux-vs-transcode policy documented (03) — Owner OK 2026-08-01
- [x] JellyFlam3 channel shows posters + metadata; TV settings fetch works; sideload verified (04) — Owner OK 2026-08-02
- [x] Peering host-service model (Tailscale + Syncthing) Opt In/Out; `*.flam3` + optional `*-poster.jpg` sync; land in `peers/inbox` then gated promote (not auto worker pickup) — docs + templates (05) — Owner OK 2026-08-08; **3-Pi mesh** smoked 2026-08-11
- [x] Sheep tax scan/repair path + tests (06) — shipped `d538ec1`
- [x] Breed mutate/cross CLI + pedigree sidecar (`electricsheep.pedigree.*`, `origin: local_pedigree`); Pi smoke — Owner OK 2026-08-04 (07)
- [x] Dynamic duration from XML signals; soft bypass ≤ hard 120 s; period-aware snap; tests green (08) — Owner OK 2026-08-08 (Pi verify on 08a)
- [x] Pi-from-scratch guide covers profiles **16 / 08 / 04**; usable as 2nd-system path (09) — Owner OK 2026-08-08 (`rpi-jellyflam3-08a`)
- [x] Acceptance checklist signed in [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md) — Owner OK 2026-08-08

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/seed_inbox.py` (`--archive`) | pipeline | Archive feedstock CLI (baseline) |
| `pipeline/backfill_posters.py` | pipeline | Flock poster / metadata backfill |
| `scripts/hls_smoke.sh` | script | Jellyfin HLS remux / PlaybackInfo smoke |
| `scripts/package_roku_channel.{sh,ps1}` | script | Channel polish sideload builds |
| `pipeline/display_profile_sink.py` / `display_profiles.py` | pipeline | TV display-profile HTTP sink + CLI |
| `pipeline/peering.py` | pipeline | Tailscale + Syncthing Opt In/Out / promote |
| `pipeline/sheep_tax.py` | pipeline | Genome XML / vocab scan & repair |
| `pipeline/breed.py` | pipeline | Mutate / cross / interpolate pedigree CLI |
| `pipeline/breed_idle.py` | pipeline | Daily idle pedigree breed when inbox empty (one child) |
| `pipeline/hw_profile.py` | pipeline | Apply 16 / 08 / 04 Pi presets |
| `pipeline/choose_duration.py` / `genome_signals.py` | pipeline | Dynamic duration chooser |
| `scripts/cron_archive_seed.sh` | script | Backlog-gated scheduled archive fill |
| `scripts/cron_breed_idle.sh` | script | Daily idle pedigree breed (empty inbox) |
| `scripts/status_report.sh` | script | Phase 2 ops status surface |

## Exit criteria

- [x] Team agrees this DoD — Owner OK 2026-08-08
- [x] Links to guides 01–10 are valid
- [x] Architecture SoT phase labels match this overview — Phase 2 **complete**
