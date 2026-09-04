# Phase 3 overview

## Boundary

Phase 3 scope lock, reading order, and definition of done — **complete** (Owner OK 2026-08-23 @ `f37758a`). Guides **01–10** signed off; git tag **`v0.3.0` at public launch**. Phase 2 is **complete** (Owner OK 2026-08-08).

## Status

| Item | State |
|---|---|
| Phase 3 | **Complete** — Owner OK 2026-08-23 @ `f37758a`; tag **`v0.3.0` at public launch** |
| Active execution order | — (Phase 3 closed) |
| Guide 06 (git pedigree) | **Complete** — Owner OK 2026-08-14 |
| Guide 08 (Jellyfin ID dump) | **Complete** — Owner OK 2026-08-14 |
| Guide 03 (Sheep Shears) | **Complete** — Owner OK 2026-08-16 |
| Guide 05 (shared sheep security) | **Complete** — Owner OK 2026-08-16 |
| Guide 01 (stills / Roku Screensaver) | **Complete** — Owner OK 2026-08-16 |
| Guide 07 (Hammer) | **Complete** — Owner OK 2026-08-17 |
| Guide 02 (Kodi ES screensaver) | **Complete** — Owner OK 2026-08-21 (loops-only; loop→edge→loop post-launch) |
| Guide 09 (sheep refactor) | **Complete** — Owner OK 2026-08-21 |
| Guide 04 (edges + watermark) | **Post-launch** — not in v0.3.0 ([../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md)) |
| Guide 10 (testing / acceptance / RC) | **Complete** — Owner OK 2026-08-23 @ `f37758a` |
| Peering path + mesh scripting revisits | **Post-launch** — [../phase4/00_OVERVIEW.md](../phase4/00_OVERVIEW.md) |

## Execution order

1. ~~**[06_GIT_PEDIGREE_SHEEP.md](06_GIT_PEDIGREE_SHEEP.md)**~~ — **complete** (Owner OK 2026-08-14)
2. ~~**[08_JELLYFIN_ID_DUMP.md](08_JELLYFIN_ID_DUMP.md)**~~ — **complete** (Owner OK 2026-08-14)
3. ~~**[03_SHEEP_SHEARS.md](03_SHEEP_SHEARS.md)**~~ — **complete** (Owner OK 2026-08-16)
4. ~~**[05_SHARED_SHEEP_SECURITY.md](05_SHARED_SHEEP_SECURITY.md)**~~ — **complete** (Owner OK 2026-08-16)
5. ~~**[01_SCREENSAVERS_AND_STILLS.md](01_SCREENSAVERS_AND_STILLS.md)**~~ — **complete** (Owner OK 2026-08-16)
6. ~~**[07_JELLYFLAM3_HAMMER.md](07_JELLYFLAM3_HAMMER.md)**~~ — **complete** (Owner OK 2026-08-17)
7. ~~**[02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)**~~ — **complete** (Owner OK 2026-08-21; loop→edge→loop post-launch)
8. ~~**[09_SHEEP_REFACTOR.md](09_SHEEP_REFACTOR.md)**~~ — **complete** (Owner OK 2026-08-21)
9. ~~**[10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md)**~~ — **complete** (Owner OK 2026-08-23; `v0.3.0` at public launch)

Phase 3 is **closed**. Post-launch roadmap: [../phase4/00_OVERVIEW.md](../phase4/00_OVERVIEW.md).

## In scope

1. [01_SCREENSAVERS_AND_STILLS.md](01_SCREENSAVERS_AND_STILLS.md) — stills extraction; **Roku** Screensaver/Backdrop only — **complete** (Owner OK 2026-08-16)
2. [02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) — **Kodi** screensaver (Electric Sheep dogma; separate from Roku; loops-only) — **complete** (Owner OK 2026-08-21; loop→edge→loop post-launch)
3. [03_SHEEP_SHEARS.md](03_SHEEP_SHEARS.md) — add/modify/delete `.flam3` + downstream artifacts — **complete** (Owner OK 2026-08-16)
4. ~~[04_EDGES_AND_WATERMARK.md](04_EDGES_AND_WATERMARK.md)~~ — **post-launch** ([../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md))
5. [05_SHARED_SHEEP_SECURITY.md](05_SHARED_SHEEP_SECURITY.md) — pre/post share integrity against bad actors — **complete** (Owner OK 2026-08-16)
6. [06_GIT_PEDIGREE_SHEEP.md](06_GIT_PEDIGREE_SHEEP.md) — git-stored pedigree sheep for smoke/examples — **complete** (Owner OK 2026-08-14)
7. [07_JELLYFLAM3_HAMMER.md](07_JELLYFLAM3_HAMMER.md) — **JellyFlam3 Hammer**: purge history, reset worker env, wipe render inputs/outputs — **complete** (Owner OK 2026-08-17)
8. [08_JELLYFIN_ID_DUMP.md](08_JELLYFIN_ID_DUMP.md) — Jellyfin ID dump for JellyFlam3 Roku Settings — **complete** (Owner OK 2026-08-14)
9. [09_SHEEP_REFACTOR.md](09_SHEEP_REFACTOR.md) — refactor tool for sub-standard sheep (quality / palette / encode; Jellyfin-visible preview) — **complete** (Owner OK 2026-08-21)
10. [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md) — testing, acceptance, and **release candidate** — **complete** (Owner OK 2026-08-23)

Also named (not numbered guides): LLM-assisted pedigree; aspirational DeepDream/AI backends, broader social flock (household vote → share/breed bias — post-launch [../phase4/08_VIEWER_FEEDBACK_LOOP.md](../phase4/08_VIEWER_FEEDBACK_LOOP.md)). Channel Store / private publish of Roku VoD + screensaver → post-launch [../phase4/04_ROKU_PUBLISH.md](../phase4/04_ROKU_PUBLISH.md).

## Definition of done

Phase 3 is complete for a given **RC scope** when:

- [x] In-scope guides from 01–09 for that RC have exit criteria met (Owner OK 2026-08-14 … 2026-08-21; guide 04 post-launch)
- [x] [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md) regression checklist green — **OK** 2026-08-23 (`04a` fleet regression + Owner OK idle-gate / ambient loop)
- [x] Owner OK on guide 10 sign-off — **OK** 2026-08-23 (git tag **`v0.3.0` at public launch**)

## Prerequisites

Phase 1 complete · Phase 2 DoD (posters, peering, sheep tax, HLS, stable Ids) preferred before Shears / screensavers / share security / Hammer / sheep refactor.

**Kodi** ([02](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)) **complete** for Phase 3 loops-only; loop→edge→loop journeys are post-launch when edges exist ([../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md)).

**Sheep refactor** ([09](09_SHEEP_REFACTOR.md)) **complete** (Owner OK 2026-08-21). **Phase 3** closed via [10](10_TESTING_AND_ACCEPTANCE.md) (Owner OK 2026-08-23). Benefits from Phase 2 sheep tax, TV-port/OkLCh, dynamic duration, and Shears-stable Ids so remediation can re-furnace and replace catalog artifacts safely.

**Git pedigree sheep** ([06](06_GIT_PEDIGREE_SHEEP.md)) prefer Phase 2 pedigree + sheep tax so smoke/examples are `local_pedigree` genomes, not archive Free Sheep copies. **Samples layout cleanup done**; **`genomes/pedigree/` smoke seed landed**; **demo seed retired**; archive Free Sheep under `genomes/samples/` remain furnace feedstock only.

**Hammer** ([07](07_JELLYFLAM3_HAMMER.md)) is the nuclear alternative to Shears ([03](03_SHEEP_SHEARS.md)): full local factory reset, not per-sheep cascade.

## Post-launch parking

Deferred from Phase 3 (not v0.3.0 scope). Details under `docs/phase4/`:

- [../phase4/00_OVERVIEW.md](../phase4/00_OVERVIEW.md)
- [../phase4/01_PEER_SHARE_PATH.md](../phase4/01_PEER_SHARE_PATH.md)
- [../phase4/02_MESH_INTRODUCE_SCRIPTING.md](../phase4/02_MESH_INTRODUCE_SCRIPTING.md)
- [../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md) — edges + watermark (was Phase 3 / 04)
- [../phase4/04_ROKU_PUBLISH.md](../phase4/04_ROKU_PUBLISH.md) — publish VoD + screensaver (assets, settings, Store/private)
- [../phase4/05_END_USER_GUIDE.md](../phase4/05_END_USER_GUIDE.md) — end-user tasks / examples / triage (**baseline complete** 2026-09-03)
- [../phase4/06_LIBRARY_DISK_ROTATE.md](../phase4/06_LIBRARY_DISK_ROTATE.md) — sheep library disk check (**slice shipped**) + auto-purge / rotate (parked)
- [../phase4/07_CONCURRENT_CLIENTS.md](../phase4/07_CONCURRENT_CLIENTS.md) — concurrent clients / link-capacity estimate (**estimator shipped**)
- [../phase4/08_VIEWER_FEEDBACK_LOOP.md](../phase4/08_VIEWER_FEEDBACK_LOOP.md) — Roku vote overlay → share cron + weighted idle breed
- [../phase4/09_SHEEP_NAMING.md](../phase4/09_SHEEP_NAMING.md) — auto aliases (keys reserved; RNG parked)

## Artifacts

Rollup of Phase 3 deliverables (planned unless noted). Per-guide tables are authoritative.

| Artifact | Kind | Role |
|---|---|---|
| Stills pipeline + flock `stills/` | pipeline | Frame extract for Roku Screensaver ([01](01_SCREENSAVERS_AND_STILLS.md)) |
| `roku-screensaver/` (sideload) | channel | Roku Screensaver / Backdrop ([01](01_SCREENSAVERS_AND_STILLS.md)) |
| `kodi-screensaver/` / `screensaver.jellyflam3` | add-on | Kodi ES-dogma screensaver (**complete** loops-only, [02](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)) |
| `pipeline/shears.py` | pipeline | Add / modify / delete / audit / sweep (**complete**, [03](03_SHEEP_SHEARS.md)) |
| Share integrity sidecars + verify hooks | pipeline | Pre/post peer share gates (**complete**, [05](05_SHARED_SHEEP_SECURITY.md)) |
| `genomes/pedigree/` | genome | Curated git pedigree smoke/examples (**landed**, [06](06_GIT_PEDIGREE_SHEEP.md)) |
| `pipeline/hammer.py` | pipeline | Local factory reset ([07](07_JELLYFLAM3_HAMMER.md)) |
| `scripts/jellyfin_id_dump.py` | script | Roku Settings ID helper + `--smoke-item-id` for HLS smoke (**complete**, [08](08_JELLYFIN_ID_DUMP.md)) |
| `scripts/client_pack_presets.py` | script | Furnace-built Roku/Kodi zip Jellyfin presets ([08](08_JELLYFIN_ID_DUMP.md)) |
| `roku-channel/` / `roku-screensaver/` `RegistryPresets.brs` | channel | Apply packaged `jellyflam3-presets.json` on first launch |
| `pipeline/refactor.py` | pipeline | Sub-standard sheep quality repair (**complete**, [09](09_SHEEP_REFACTOR.md)) |
| RC tag / GitHub Release + acceptance run | release | **`v0.3.0` at public launch** — closeout complete ([10](10_TESTING_AND_ACCEPTANCE.md)) |

## See also

[Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md) (Phase 3 tables) · [../phase2/00_OVERVIEW.md](../phase2/00_OVERVIEW.md) · [../phase4/00_OVERVIEW.md](../phase4/00_OVERVIEW.md) · [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md)
