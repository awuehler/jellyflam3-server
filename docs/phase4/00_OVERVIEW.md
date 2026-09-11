# Phase 4 overview

## Boundary

Phase 4 **products** stay parked until Owner opens them, except **tuples (guide 03)** which shipped 2026-09-05 and **09 RNG aliases** which shipped 2026-09-09: peer auto-promote, mesh introduce scripting, Roku Store/private publish, library **rotate**, vote overlay / share cron / breed bias, and pasture filename-vs-alias toggle.

**Pre-open slices** already shipped (docs + operator CLIs; not those products): end-user baseline, sheep-disk check, concurrent-client estimator, and catalog sidecar key names. **Opened 2026-09-09:** worker preserves reserved sidecar keys on re-ingest. **Opened 2026-09-09:** pasture clients re-poll the flock on mid-session 404 (quarantine / Shears). **Opened 2026-09-10:** wrap-once flock re-fetch + 313 session cap. **Opened 2026-09-09:** 07 estimator Owner OK; 09 RNG aliases (ingest + backfill + override).

## Status

| Item | State |
|---|---|
| Phase 4 products | **Mostly parked** (2026-08-16) — tuples (03) shipped 2026-09-05; 09 RNG shipped 2026-09-09; do not implement auto-promote / overlay / rotate until Owner opens those slices |
| Peer share path revisit | Parked — [01](01_PEER_SHARE_PATH.md); reads reserved `viewer_feedback.share_candidate` |
| Mesh introduce scripting | Parked — [02](02_MESH_INTRODUCE_SCRIPTING.md) |
| Edges + watermark | **Tuple slice shipped** 2026-09-05 — [03](03_EDGES_AND_WATERMARK.md); catalog `by-generation/tuple/`; idle-cron mode; Roku shuffle includes `tuple` + `pedigree`. Standalone `type: edge` files + loop/stills watermark still parked |
| Roku VoD + screensaver publish | Parked — [04](04_ROKU_PUBLISH.md) (multi-Roku household; added 2026-08-16) |
| End-user guide (tasks / examples / triage) | **Baseline complete** (Owner OK 2026-09-03) — [05](05_END_USER_GUIDE.md); [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md); fridge card [FRIDGE_CARD.md](../FRIDGE_CARD.md). Remaining 05 expansion (vote recipes) waits on [08](08_VIEWER_FEEDBACK_LOOP.md); alias CLI is in the runbook |
| Sheep library disk check + auto-purge / rotate | **Check slice shipped** 2026-09-03 — [06](06_LIBRARY_DISK_ROTATE.md); healthcheck WARN/BAD; auto-purge / worker refuse parked |
| Concurrent clients / link-capacity estimate | **Estimator shipped** 2026-09-03 — [07](07_CONCURRENT_CLIENTS.md); `python3 -m pipeline.link_capacity`; **Owner OK 2026-09-09** |
| Viewer feedback loop (vote → share + breed bias) | Parked — [08](08_VIEWER_FEEDBACK_LOOP.md) (added 2026-08-19); `viewer_feedback` key reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) |
| Sheep naming (auto-generated aliases) | **RNG slice shipped** 2026-09-09 — [09](09_SHEEP_NAMING.md); `python3 -m pipeline.sheep_naming`; client filename/alias toggle parked |

## Pre-open shipped (2026-09-03)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Household guide + fridge card | [05](05_END_USER_GUIDE.md) | [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) Layer 1 + four worked examples; [FRIDGE_CARD.md](../FRIDGE_CARD.md) | Vote recipes (need 08); alias CLI is in the runbook |
| Sheep disk WARN/BAD | [06](06_LIBRARY_DISK_ROTATE.md) | `python3 -m pipeline.library_disk check`; healthcheck | Auto-purge, worker refuse on sheep mount, rotate cron |
| Concurrent-client `N_max` | [07](07_CONCURRENT_CLIENTS.md) | `python3 -m pipeline.link_capacity`; WiFi-STA lab note; **Owner OK 2026-09-09** | Enforcing `N_max` as a Jellyfin cap; Ethernet lab (eth0 DOWN) |
| Sidecar key names | [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) | `type`, `watermark`, `viewer_feedback`, `alias` (+ companions) | Vote sink; client alias toggle |
| Tuples (loop A + edge + loop B) | [03](03_EDGES_AND_WATERMARK.md) | One MP4 under `by-generation/tuple/`; edge-only watermark; idle-cron mode; Roku shuffle `tuple`+`pedigree` | Standalone edge files; watermark on loops/stills; Kodi edge sequencer |

## Opened (2026-09-09)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Sidecar preserve | [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) | Worker copies reserved keys on re-ingest; tuples still write `type` / `from_id` / `to_id` / `watermark` from this encode | Vote sink |
| 404 mid-session re-poll | clients | Drop dead Jellyfin id, rate-limited re-poll, continue session: VoD **1.0.29**, Roku SS **1.0.8**, Kodi SS **0.2.7** | — |
| Wrap-once flock re-fetch + 313 cap | clients | Once per full shuffle wrap, re-fetch Jellyfin and regenerate the in-memory list (skip if a fetch is already in flight; no 30s 404 gate). HTTP Limit 5000 then randomly prune to **313**. VoD **1.0.31**, Roku SS **1.0.9**, Kodi SS **0.2.9** | Hours-scale timer (not needed for ~daily ingest) |
| 07 estimator Owner OK | [07](07_CONCURRENT_CLIENTS.md) | Sign-off 2026-09-09; `N_max` remains an estimate | Enforcing `N_max` as a Jellyfin cap |
| 09 RNG aliases | [09](09_SHEEP_NAMING.md) | Hash-seed `adjective_surname` on ingest/backfill; `set-alias` / `clear-alias` | Roku/Kodi filename vs alias toggle; LLM poster naming → [../phase5/02](../phase5/02_LLM_INTEGRATION.md) |

## In scope (parked products)

1. [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) — keep vs change **stage → `peers/inbox` → gated `promote --apply`** (land ≠ worker ingest)
2. [02_MESH_INTRODUCE_SCRIPTING.md](02_MESH_INTRODUCE_SCRIPTING.md) — options A–D for first-time Syncthing mesh introduce (or stay manual)
3. [03_EDGES_AND_WATERMARK.md](03_EDGES_AND_WATERMARK.md) — **tuples shipped**; remaining: standalone edges, loop/stills watermark, Kodi edge sequencer
4. [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) — publish existing Roku VoD + screensaver (assets, settings UX, private/Store, **multi-Roku on one server**)
5. [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) — remaining **vote** recipes (baseline complete; alias CLI is in the runbook)
6. [06_LIBRARY_DISK_ROTATE.md](06_LIBRARY_DISK_ROTATE.md) — auto-purge / rotate / worker refuse (check slice already shipped)
7. [07_CONCURRENT_CLIENTS.md](07_CONCURRENT_CLIENTS.md) — **Owner OK 2026-09-09** on the shipped estimator (enforcing `N_max` as a Jellyfin cap stays parked)
8. [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) — Roku like/love/vote overlay → share cron + weighted idle breed (shuffle already includes pedigree + tuple as of 1.0.28)
9. [09_SHEEP_NAMING.md](09_SHEEP_NAMING.md) — **RNG slice shipped**; remaining: client filename/alias toggle. LLM-from-poster → [../phase5/02_LLM_INTEGRATION.md](../phase5/02_LLM_INTEGRATION.md)

Also named (aspirational / TBD): broader social flock, DeepDream/AI backends. **LLM-assisted pedigree** and **LLM poster naming** moved to **Phase 5** ([../phase5/00_OVERVIEW.md](../phase5/00_OVERVIEW.md)): a **separate** Ventuno LLM Agent Platform talking to the Pi furnace — not models on the furnace and not Ventuno-as-16a. Guide [08](08_VIEWER_FEEDBACK_LOOP.md) remains the household vote → share/breed-bias slice; [09](09_SHEEP_NAMING.md) RNG aliases stay here (LLM path in Phase 5).

Sidecar key names for [01](01_PEER_SHARE_PATH.md) / [03](03_EDGES_AND_WATERMARK.md) / [08](08_VIEWER_FEEDBACK_LOOP.md) / [09](09_SHEEP_NAMING.md) are reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Worker copies reserved keys on re-ingest; tuple ingest writes `type` / `from_id` / `to_id` / `watermark` from this encode. Vote sink and pasture alias display stay parked.

### Client polish (shipped wrap-once refresh)

| Item | Notes |
|---|---|
| **Wrap-once flock refresh** | **Shipped** VoD **1.0.31**, Roku screensaver **1.0.9**, Kodi screensaver **0.2.9**. Fetch Jellyfin with Limit **5000**, then randomly prune the in-memory cycle list to **313** (VoD/Kodi: sheep items; Roku SS: Primary+Backdrop URLs). After a **full shuffle wrap**, kick a re-fetch and replace the list when it arrives — do not stall the current clip/still. Skip wrap fetch if one is already in flight. 404 re-poll keeps its **30s** gate and is separate. Single-item lists do not wrap-refetch. Hours-scale timer stays unneeded for ~daily ingest. |

**Shipped (not parked):** **Quarantine / 404 mid-session re-poll** — VoD 1.0.29, Roku screensaver 1.0.8, Kodi screensaver 0.2.7. On file-not-found / stream open fail / missing Primary or Backdrop, clients drop the dead id, re-poll Jellyfin (rate-limited to 30s), and continue the session. Does not stop playback chrome, does not invent a Sessions Playing client for the miss.

### Furnace polish (parked — not numbered)

Parked so a numbered product guide is not required yet. Do **not** implement until Owner opens this slice.

| Item | Notes |
|---|---|
| **Worker drain / idle-before-restart** | Operator command that lets a furnace **finish the current inbox job**, then **not claim the next** genome, so the worker reaches a true idle (watching inbox, nothing in-flight). After that, `systemctl restart jellyflam3-worker` does not orphan a live `flam3-animate`. Today a restart always treats in-flight work as an orphan: frames are discarded (`flam3-animate` cannot resume partial nframes), the genome is re-queued, and render restarts at frame 0 — hours to days lost on a long sheep. Distinct from the **idle-gate** (TV Playing pauses render) and from an **empty inbox** (archive seed / idle-breed can refill). Per host; fleet drain is one command per furnace. Undrain / cancel should resume claiming inbox without requiring a restart. Track against [../phase1/05_RENDER_PIPELINE.md](../phase1/05_RENDER_PIPELINE.md), [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md), `pipeline.job_recovery`. |

**Not this slice:** checkpoint/resume inside `flam3-animate`; SIGSTOP of a live animate as “pause”; killing the current job on purpose (that is today’s restart). Drain is **pause before the next inbox render**, not mid-frame.

## Out of scope

- Phase 3 feature guides still owned under [`docs/phase3/`](../phase3/00_OVERVIEW.md) (01–03, 05–10; stub at former 04)
- Changing the locked Phase 2 peering contract **before** this phase opens

## Prerequisites

Phase 3 RC (or Owner waiver) preferred before opening Phase 4 products, so Shears, share-security, and screensaver baselines stay stable inputs for edges / watermark / peering revisits / Roku publish / rotate / viewer feedback / sheep naming.

## See also

[../phase3/00_OVERVIEW.md](../phase3/00_OVERVIEW.md) · [../phase5/00_OVERVIEW.md](../phase5/00_OVERVIEW.md) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [`deploy/peering/README.md`](../../deploy/peering/README.md)
