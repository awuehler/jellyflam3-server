# Phase 1 overview

## Boundary

Phase 1 scope lock, reading order, and definition of done only — **no install steps**.

## Non-goals (deferred)

Historical Phase 1 deferrals (status after Phase 2 planning):

- Standalone Roku screensaver + stills → **Phase 3** ([../phase3/01_SCREENSAVERS_AND_STILLS.md](../phase3/01_SCREENSAVERS_AND_STILLS.md))
- Kodi Electric Sheep–dogma screensaver (separate feature) → **Phase 3** ([../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md))
- Dynamic duration weighting → **Phase 2** ([../phase2/08_DYNAMIC_DURATION.md](../phase2/08_DYNAMIC_DURATION.md))
- HLS client streaming (Jellyfin → Roku / VLC / etc.) → **Phase 2** ([../phase2/03_HLS_CLIENT_STREAMING.md](../phase2/03_HLS_CLIENT_STREAMING.md))
- Sheep tax (`.flam3` XML / vocab scan & repair) → **Phase 2** ([../phase2/06_SHEEP_TAX.md](../phase2/06_SHEEP_TAX.md))
- Web player, DeepDream backends, social flock network → later / Phase 3+
- Complementary ambient-TV palette tinting → **baseline shipped** (TV-optimize)
- Electric Sheep archive seed library → **baseline shipped** ([../phase2/01_ARCHIVE_SEED_LIBRARY.md](../phase2/01_ARCHIVE_SEED_LIBRARY.md))
- Channel Store certification package → deferred
- Sheep Shears / LLM pedigree / shared sheep security / git pedigree sheep / JellyFlam3 Hammer → **Phase 3** ([../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md), [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md), [../phase3/06_GIT_PEDIGREE_SHEEP.md](../phase3/06_GIT_PEDIGREE_SHEEP.md), [../phase3/07_JELLYFLAM3_HAMMER.md](../phase3/07_JELLYFLAM3_HAMMER.md)); edge crossfades + watermark → **Phase 4** ([../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md))

## Reading order

See [docs/README.md](../README.md). Architecture: [Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md).

## Definition of done

Phase 1 is complete when all exit criteria in guides 01–10 pass, including:

- [x] Pi boots with media/scratch on NVMe or USB SSD
- [x] flam3 + ffmpeg/ffprobe smoke render works
- [x] Jellyfin Sheep library + API key; Path 1 Direct Play
- [x] Worker produces 7–37 s H.264 MP4 and ingests to Jellyfin
- [x] Idle-gate pauses render during Roku TV playback (Playing API / build 1.0.12 reporting)
- [x] License tags + commercial-safe filtering documented and applied (sidecar SoT; commercial filter default off)
- [x] BrightScript channel lists and loops dreams
- [x] systemd runtime, backup, health checks
- [x] Acceptance checklist signed in [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md) — Owner OK 2026-07-28

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/worker.py` | pipeline | Furnace CLI — genome → catalog MP4 |
| `pipeline/seed_inbox.py` | pipeline | Stage `.flam3` feedstock into inbox |
| `pipeline/idle_gate.py` | pipeline | TV-playback CPU isolation supervisor |
| `pipeline/media_layout.py` | pipeline | Catalog dir/file perms for Jellyfin |
| `scripts/install_flam3.sh` | script | Build / install / verify flam3 + deps |
| `scripts/smoke_render.sh` | script | Toolchain smoke (never publish) |
| `scripts/package_roku_channel.{sh,ps1}` | script | Sideload zip for JellyFlam3 channel |
| `scripts/healthcheck.sh` / `backup.sh` | script | Ops health + backup |
| `deploy/systemd/jellyflam3-{worker,idlegate}.service` | deploy | Production worker + idle-gate units |
| `configs/jellyflam3.yaml` | config | Phase 1 runtime schema |
| `roku-channel/` | channel | BrightScript Path 2 client |
| `flam3-animate` / `ffmpeg` / `jellyfin` | binary | Render, encode, VoD origin stack |

## Exit criteria

- [x] Team agrees this DoD (technical checklist reconciled; Owner signed 2026-07-28 — **Phase 1 complete**)
- [x] Links to guides 01–10 are valid
