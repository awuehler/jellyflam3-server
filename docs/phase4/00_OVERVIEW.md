# Phase 4 overview

## Boundary

Phase 4 **products** stay parked until Owner opens the phase: peer auto-promote, mesh introduce scripting, **edges + watermark encode**, Roku Store/private publish, library **rotate**, vote overlay / share cron / breed bias, and sheep-naming RNG.

**Pre-open slices** already shipped (docs + operator CLIs; not those products): end-user baseline, sheep-disk check, concurrent-client estimator, and catalog sidecar key names.

## Status

| Item | State |
|---|---|
| Phase 4 products | **Parked** (2026-08-16) — do not implement encode / overlay / RNG / rotate / auto-promote until Owner opens the phase |
| Peer share path revisit | Parked — [01](01_PEER_SHARE_PATH.md); reads reserved `viewer_feedback.share_candidate` |
| Mesh introduce scripting | Parked — [02](02_MESH_INTRODUCE_SCRIPTING.md) |
| Edges + watermark | Parked — [03](03_EDGES_AND_WATERMARK.md) (moved from Phase 3 / 04 on 2026-08-16; includes Kodi loop→edge→loop deferred from Phase 3 guide 02); `type` / `watermark` reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) |
| Roku VoD + screensaver publish | Parked — [04](04_ROKU_PUBLISH.md) (multi-Roku household; added 2026-08-16) |
| End-user guide (tasks / examples / triage) | **Baseline complete** (Owner OK 2026-09-03) — [05](05_END_USER_GUIDE.md); [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md); fridge card [FRIDGE_CARD.md](../FRIDGE_CARD.md). Remaining 05 expansion (vote/rename recipes) waits on [08](08_VIEWER_FEEDBACK_LOOP.md) / [09](09_SHEEP_NAMING.md) |
| Sheep library disk check + auto-purge / rotate | **Check slice shipped** 2026-09-03 — [06](06_LIBRARY_DISK_ROTATE.md); healthcheck WARN/BAD; auto-purge / worker refuse parked |
| Concurrent clients / link-capacity estimate | **Estimator shipped** 2026-09-03 — [07](07_CONCURRENT_CLIENTS.md); `python3 -m pipeline.link_capacity`; Owner OK pending |
| Viewer feedback loop (vote → share + breed bias) | Parked — [08](08_VIEWER_FEEDBACK_LOOP.md) (added 2026-08-19); `viewer_feedback` key reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) |
| Sheep naming (auto-generated aliases) | Parked — [09](09_SHEEP_NAMING.md) (added 2026-08-20); `alias` / `alias_source` reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) |

## Pre-open shipped (2026-09-03)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Household guide + fridge card | [05](05_END_USER_GUIDE.md) | [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) Layer 1 + four worked examples; [FRIDGE_CARD.md](../FRIDGE_CARD.md) | Vote / rename recipes (need 08 / 09) |
| Sheep disk WARN/BAD | [06](06_LIBRARY_DISK_ROTATE.md) | `python3 -m pipeline.library_disk check`; healthcheck | Auto-purge, worker refuse on sheep mount, rotate cron |
| Concurrent-client `N_max` | [07](07_CONCURRENT_CLIENTS.md) | `python3 -m pipeline.link_capacity`; WiFi-STA lab note | Enforcing `N_max` as a Jellyfin cap; Ethernet lab (eth0 DOWN) |
| Sidecar key names | [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) | `type`, `watermark`, `viewer_feedback`, `alias` (+ companions) | Edge encode, watermark burn-in, vote sink, naming RNG; worker ingest still rebuilds known fields only |

## In scope (parked products)

1. [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) — keep vs change **stage → `peers/inbox` → gated `promote --apply`** (land ≠ worker ingest)
2. [02_MESH_INTRODUCE_SCRIPTING.md](02_MESH_INTRODUCE_SCRIPTING.md) — options A–D for first-time Syncthing mesh introduce (or stay manual)
3. [03_EDGES_AND_WATERMARK.md](03_EDGES_AND_WATERMARK.md) — edge / transition crossfades + sheep watermark (**core** pipeline + Roku/Kodi playback changes, not docs-only)
4. [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) — publish existing Roku VoD + screensaver (assets, settings UX, private/Store, **multi-Roku on one server**)
5. [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) — remaining vote/rename recipes (baseline already complete)
6. [06_LIBRARY_DISK_ROTATE.md](06_LIBRARY_DISK_ROTATE.md) — auto-purge / rotate / worker refuse (check slice already shipped)
7. [07_CONCURRENT_CLIENTS.md](07_CONCURRENT_CLIENTS.md) — Owner OK on the shipped estimator
8. [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) — Roku like/love/vote overlay → share cron + weighted idle breed (**requires shuffle to include pedigree** for voting; Phase 3 archive-only allowlist is temporary)
9. [09_SHEEP_NAMING.md](09_SHEEP_NAMING.md) — auto `adjective_surname` aliases (+ human override; optional LLM-from-poster; client filename/alias toggle)

Also named (aspirational / TBD): broader social flock, DeepDream/AI backends, LLM-assisted pedigree polish — may gain numbered guides when Phase 4 opens. Guide [08](08_VIEWER_FEEDBACK_LOOP.md) is the household feedback slice of social flock evolution; [09](09_SHEEP_NAMING.md) covers memorable aliases (RNG first; LLM naming later).

Sidecar key names for [01](01_PEER_SHARE_PATH.md) / [03](03_EDGES_AND_WATERMARK.md) / [08](08_VIEWER_FEEDBACK_LOOP.md) / [09](09_SHEEP_NAMING.md) are reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Encode, vote sink, and naming RNG stay parked.

### Client polish (parked — not numbered)

| Item | Notes |
|---|---|
| **Long-interval flock refresh** | Kodi screensaver (and optionally Roku VoD ambient) fetch Jellyfin once per idle/session and reshuffle that in-memory list until exit. New catalog sheep (e.g. daily archive/breed under a new `by-generation/{gen}/` folder) appear only after the next session. **Phase 4 polish:** optional **long poll / refresh period** (hours-scale, or once per full shuffle wrap) to re-`fetch_flock` between clips so overnight continuous idle picks up ~daily ingest without exit/restart. Not a tight poll — default stays session-scoped. Track against [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) (+ Roku VoD if desired). |
| **Quarantine / 404 mid-session re-poll** | Operator may **quarantine** (or Shears-delete) a sheep while a pasture session is already running. The in-memory flock still holds that Jellyfin item id; the next play/still request then **file-not-found** (HTTP 404, stream open fail, missing Primary). **Phase 4 polish — all JellyFlam3 client endpoints:** on that error, drop the dead id, **re-poll** Jellyfin (`fetch_flock` / equivalent) to refresh the index, and continue the session with a remaining sheep. Do not stop playback chrome, do not treat the miss as a furnace Sessions client, and rate-limit re-polls so a shrinking library cannot hammer the Pi. Same contract on **Roku VoD** (MP4 and HLS `streamMode`), **Roku screensaver** (Primary / stills URLs), and **Kodi screensaver** (loop URLs). Track: [../phase3/09_SHEEP_REFACTOR.md](../phase3/09_SHEEP_REFACTOR.md) Pathway C, [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md), [../phase3/01_SCREENSAVERS_AND_STILLS.md](../phase3/01_SCREENSAVERS_AND_STILLS.md), [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md), [../phase2/04_ROKU_CHANNEL_POLISH.md](../phase2/04_ROKU_CHANNEL_POLISH.md). |

## Out of scope

- Phase 3 feature guides still owned under [`docs/phase3/`](../phase3/00_OVERVIEW.md) (01–03, 05–10; stub at former 04)
- Changing the locked Phase 2 peering contract **before** this phase opens

## Prerequisites

Phase 3 RC (or Owner waiver) preferred before opening Phase 4 products, so Shears, share-security, and screensaver baselines stay stable inputs for edges / watermark / peering revisits / Roku publish / rotate / viewer feedback / sheep naming.

## See also

[../phase3/00_OVERVIEW.md](../phase3/00_OVERVIEW.md) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [`deploy/peering/README.md`](../../deploy/peering/README.md)
