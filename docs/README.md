# JellyFlam3 Project Plan

| Doc | Purpose |
|---|---|
| **[USER_GUIDE_AND_RUNBOOK.md](USER_GUIDE_AND_RUNBOOK.md)** | **Layered user guide + operator runbook** for end users, operators, & contributors |
| [FRIDGE_CARD.md](FRIDGE_CARD.md) | One-page Layer 1 cheat sheet (print; no API keys) |
| [Pi5_Flam3_VoD_Pipeline.md](Pi5_Flam3_VoD_Pipeline.md) | Canonical architecture + design source of truth |
|||
| [phase1/00_OVERVIEW.md](phase1/00_OVERVIEW.md) | Phase 1 scope, reading order, definition of done — **complete** |
| [phase2/00_OVERVIEW.md](phase2/00_OVERVIEW.md) | Phase 2 scope, reading order, definition of done — **complete** |
| [phase3/00_OVERVIEW.md](phase3/00_OVERVIEW.md) | Phase 3 scope, reading order, definition of done — **complete** |
| [phase4/00_OVERVIEW.md](phase4/00_OVERVIEW.md) | Phase 4 synopsis — **implemented** (`v0.3.2`); leftovers noted |
| [phase5/00_OVERVIEW.md](phase5/00_OVERVIEW.md) | Phase 5 synopsis — 1..N furnaces (Pi) vs one LLM Agent Platform (Ventuno); Tailscale agent tag; one hot INT4 7–8B + small GPU VLM — **parked** |
|||
| [glossary.md](glossary.md) | Terms, keywords, and definitions for project + collateral vocabulary |
| [CLIENT_CHANNEL_ART.md](CLIENT_CHANNEL_ART.md) | Generative prompts for Roku/Kodi splash + icon (operator post-prod) |
| [media/README.md](media/README.md) | Hardware / demo / watermark file index |

## Phase 1 guides (execute in order of furnace setup) — complete

1. [01_HARDWARE_AND_OS.md](phase1/01_HARDWARE_AND_OS.md) — Pi hardware + OS mounts
2. [02_REPO_AND_CONFIG.md](phase1/02_REPO_AND_CONFIG.md) — repo + config
3. [03_FLAM3_AND_FFMPEG.md](phase1/03_FLAM3_AND_FFMPEG.md) — toolchain + smoke
4. [04_JELLYFIN_LIBRARY.md](phase1/04_JELLYFIN_LIBRARY.md) — Jellyfin + Path 1
5. [05_RENDER_PIPELINE.md](phase1/05_RENDER_PIPELINE.md) — worker
6. [06_IDLE_GATE.md](phase1/06_IDLE_GATE.md) — CPU isolation
7. [07_LICENSE_AND_METADATA.md](phase1/07_LICENSE_AND_METADATA.md) — tags / commercial / sidecar schema
8. [08_ROKU_BRIGHTSCRIPT.md](phase1/08_ROKU_BRIGHTSCRIPT.md) — custom channel
9. [09_RUNTIME_AND_OPS.md](phase1/09_RUNTIME_AND_OPS.md) — systemd / backup / health
10. [10_TESTING_AND_ACCEPTANCE.md](phase1/10_TESTING_AND_ACCEPTANCE.md) — sign-off

Parallel after guide 02: `03` ∥ `04`. Acceptance (`10`) is last.

## Phase 2 guides (execute in order of pipeline stages) — complete

1. [01_ARCHIVE_SEED_LIBRARY.md](phase2/01_ARCHIVE_SEED_LIBRARY.md) — archive feedstock
2. [02_JELLYFIN_FLOCK_UX.md](phase2/02_JELLYFIN_FLOCK_UX.md) — posters / metadata
3. [03_HLS_CLIENT_STREAMING.md](phase2/03_HLS_CLIENT_STREAMING.md) — HLS Jellyfin → Roku / VLC / etc.
4. [04_ROKU_CHANNEL_POLISH.md](phase2/04_ROKU_CHANNEL_POLISH.md) — JellyFlam3 UX + TV display probe
5. [05_SYNCTHING_GENOME_PEERING.md](phase2/05_SYNCTHING_GENOME_PEERING.md) — Syncthing over Tailscale (`*.flam3`; Opt In/Out)
6. [06_SHEEP_TAX.md](phase2/06_SHEEP_TAX.md) — genome XML / vocab scan & repair
7. [07_PEDIGREE_BREEDING.md](phase2/07_PEDIGREE_BREEDING.md) — mutate / cross / blend / interpolate (+ daily idle cron)
8. [08_DYNAMIC_DURATION.md](phase2/08_DYNAMIC_DURATION.md) — XML signals; profile soft/hard bands; `snap_to_periods` locked true; hard max 120
9. [09_PI_FROM_SCRATCH.md](phase2/09_PI_FROM_SCRATCH.md) — end-user Pi build (profiles 16/08/04; `pipeline.hw_profile`)
10. [10_TESTING_AND_ACCEPTANCE.md](phase2/10_TESTING_AND_ACCEPTANCE.md) — sign-off

Parallel after **02**: `03` (HLS) anytime; `04` once Primary images exist. `05`–`08` largely independent. Acceptance (`10`) last.

## Phase 3 guides (execute in order of increasing complexity) — complete

1. [01_SCREENSAVERS_AND_STILLS.md](phase3/01_SCREENSAVERS_AND_STILLS.md) — poster-pipeline stills; Roku Screensaver Primary + Backdrop
2. [02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) — Kodi ES-dogma screensaver
3. [03_SHEEP_SHEARS.md](phase3/03_SHEEP_SHEARS.md) — CRUD `.flam3` + downstream cascade
4. [05_SHARED_SHEEP_SECURITY.md](phase3/05_SHARED_SHEEP_SECURITY.md) — pre/post share integrity (anti-tamper)
5. [06_GIT_PEDIGREE_SHEEP.md](phase3/06_GIT_PEDIGREE_SHEEP.md) — git pedigree smoke/examples
6. [07_JELLYFLAM3_HAMMER.md](phase3/07_JELLYFLAM3_HAMMER.md) — JellyFlam3 Hammer (purge history / reset worker / wipe render I/O)
7. [08_JELLYFIN_ID_DUMP.md](phase3/08_JELLYFIN_ID_DUMP.md) — Jellyfin ID dump for JellyFlam3 Roku Settings
8. [09_SHEEP_REFACTOR.md](phase3/09_SHEEP_REFACTOR.md) — refactor tool (quality / palette / encode; Jellyfin-visible preview)
9. [10_TESTING_AND_ACCEPTANCE.md](phase3/10_TESTING_AND_ACCEPTANCE.md) — testing, acceptance, and first `release candidate`

**NOTE:** Tag **`v0.3.0`** at public launch — see [CHANGELOG.md](../CHANGELOG.md), and Phase 4 close-out is **`v0.3.2`**.

## Phase 4 guides (execute in order to Roku channel launch — leftovers noted) - complete

1. [01_PEER_SHARE_PATH.md](phase4/01_PEER_SHARE_PATH.md) — gated `promote --apply` (auto-promote **cancelled**)
2. [02_MESH_INTRODUCE_SCRIPTING.md](phase4/02_MESH_INTRODUCE_SCRIPTING.md) — share hop → [phase5/04](phase5/04_PEER_SHARE_MESH.md)
3. [03_EDGES_AND_WATERMARK.md](phase4/03_EDGES_AND_WATERMARK.md) — tuples (standalone edges / loop watermark **cancelled**)
4. [04_ROKU_PUBLISH.md](phase4/04_ROKU_PUBLISH.md) — VoD Channel Store **submitted** (pending review)
5. [05_END_USER_GUIDE.md](phase4/05_END_USER_GUIDE.md) — household guide
6. [06_LIBRARY_DISK_ROTATE.md](phase4/06_LIBRARY_DISK_ROTATE.md) — disk check + rotate CLI (daily cron optional)
7. [07_CONCURRENT_CLIENTS.md](phase4/07_CONCURRENT_CLIENTS.md) — `link_capacity` (no Jellyfin cap / Ethernet lab DoD)
8. [08_VIEWER_FEEDBACK_LOOP.md](phase4/08_VIEWER_FEEDBACK_LOOP.md) — vote overlay + sidecar sink + share cron + idle-breed weights (auto-promote & **Roku** screensaver voting **cancelled**)
9. [09_SHEEP_NAMING.md](phase4/09_SHEEP_NAMING.md) — RNG aliases + VoD / screensaver `titleMode` (optional Jellyfin OriginalTitle parked)

Overview: [phase4/00_OVERVIEW.md](phase4/00_OVERVIEW.md).

## Phase 5 guides (synopsis — Arduino SBC deployment)

1. [01_VENTUNO_Q_HOST.md](phase5/01_VENTUNO_Q_HOST.md) — LLM Agent Platform host (Ventuno Q BOM, INT4 storage math, Tailscale flock join, 1..N furnaces; **not** a furnace)
2. [02_LLM_INTEGRATION.md](phase5/02_LLM_INTEGRATION.md) — Instruct INT4; session switch; pixels → Instruct JSON; **VoD-as-camera** (single sheep)
3. [03_AI_PLATFORM_GAPS.md](phase5/03_AI_PLATFORM_GAPS.md) — NPU / RAM / conversion / Hexagon+Adreno H4 lab / TBD goals **on the agent platform**
4. [04_PEER_SHARE_MESH.md](phase5/04_PEER_SHARE_MESH.md) — furnace share-out → inbox + promote vs sendreceive (parked; **not** Ventuno)
5. [05_KODI_SCREENSAVER_VOTES.md](phase5/05_KODI_SCREENSAVER_VOTES.md) — Kodi screensaver like/love overlay = Roku VoD map (same furnace sink)

Overview: [phase5/00_OVERVIEW.md](phase5/00_OVERVIEW.md). Does not reopen Phase 4 (implemented in `v0.3.2`). Furnace playbook stays [phase2/09](phase2/09_PI_FROM_SCRATCH.md).
