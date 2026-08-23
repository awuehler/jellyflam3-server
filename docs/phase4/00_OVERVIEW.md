# Phase 4 overview

## Boundary

Phase 4 scope lock — **synopsis / future**. Not open for implementation until Owner opens the phase. Holds work deferred from Phase 3 (peering path, mesh introduce scripting, **edges + watermark**) plus room for later aspirational tracks (including **viewer feedback → share + breed bias** and **sheep naming / aliases**).

## Status

| Item | State |
|---|---|
| Phase 4 | **Synopsis** — not open for implementation (parked 2026-08-16) |
| Peer share path revisit | Parked — [01](01_PEER_SHARE_PATH.md) |
| Mesh introduce scripting | Parked — [02](02_MESH_INTRODUCE_SCRIPTING.md) |
| Edges + watermark | Parked — [03](03_EDGES_AND_WATERMARK.md) (moved from Phase 3 / 04 on 2026-08-16; includes Kodi loop→edge→loop deferred from Phase 3 guide 02) |
| Roku VoD + screensaver publish | Parked — [04](04_ROKU_PUBLISH.md) (multi-Roku household; added 2026-08-16) |
| End-user guide (tasks / examples / triage) | Parked — [05](05_END_USER_GUIDE.md) (added 2026-08-16); **baseline shipped early** as [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) — Phase 4 05 tracks expansion (fridge card, viewer feedback hooks, naming) |
| Sheep library disk check + auto-purge / rotate | Parked — [06](06_LIBRARY_DISK_ROTATE.md) (added 2026-08-18) |
| Concurrent clients / link-capacity estimate | Parked — [07](07_CONCURRENT_CLIENTS.md) (added 2026-08-18) |
| Viewer feedback loop (vote → share + breed bias) | Parked — [08](08_VIEWER_FEEDBACK_LOOP.md) (added 2026-08-19) |
| Sheep naming (auto-generated aliases) | Parked — [09](09_SHEEP_NAMING.md) (added 2026-08-20) |

## In scope (parked)

1. [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) — keep vs change **stage → `peers/inbox` → gated `promote --apply`** (land ≠ worker ingest)
2. [02_MESH_INTRODUCE_SCRIPTING.md](02_MESH_INTRODUCE_SCRIPTING.md) — options A–D for first-time Syncthing mesh introduce (or stay manual)
3. [03_EDGES_AND_WATERMARK.md](03_EDGES_AND_WATERMARK.md) — edge / transition crossfades + sheep watermark
4. [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) — publish existing Roku VoD + screensaver (assets, settings UX, private/Store, **multi-Roku on one server**)
5. [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) — household end-user guide: common tasks, examples, triage
6. [06_LIBRARY_DISK_ROTATE.md](06_LIBRARY_DISK_ROTATE.md) — filesystem full check + auto-purge / rotate of the sheep library
7. [07_CONCURRENT_CLIENTS.md](07_CONCURRENT_CLIENTS.md) — concurrent Jellyfin clients; WiFi/Ethernet capacity estimate (`N_max`)
8. [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) — Roku like/love/vote overlay → share cron + weighted idle breed
9. [09_SHEEP_NAMING.md](09_SHEEP_NAMING.md) — auto `adjective_surname` aliases (+ human override; optional LLM-from-poster; client filename/alias toggle)

Also named (aspirational / TBD): broader social flock, DeepDream/AI backends, LLM-assisted pedigree polish — may gain numbered guides when Phase 4 opens. Guide [08](08_VIEWER_FEEDBACK_LOOP.md) is the household feedback slice of social flock evolution; [09](09_SHEEP_NAMING.md) covers memorable aliases (RNG first; LLM naming later).

## Out of scope

- Phase 3 feature guides still owned under [`docs/phase3/`](../phase3/00_OVERVIEW.md) (01–03, 05–10; stub at former 04)
- Changing the locked Phase 2 peering contract **before** this phase opens

## Prerequisites

Phase 3 RC (or Owner waiver) preferred before opening Phase 4, so Shears, share-security, and screensaver baselines are stable inputs for edges / watermark / peering revisits / Roku publish / end-user guide / library rotate / concurrent-client estimates / viewer feedback loop / sheep naming.

## See also

[../phase3/00_OVERVIEW.md](../phase3/00_OVERVIEW.md) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [`deploy/peering/README.md`](../../deploy/peering/README.md)
