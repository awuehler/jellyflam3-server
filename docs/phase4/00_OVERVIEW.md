# Phase 4 overview

## Boundary

Phase 4 **products** stay parked until Owner opens them, except **tuples (guide 03)** which shipped 2026-09-05, **09 RNG aliases** which shipped 2026-09-09, **08 overlay + sidecar vote sink** and **04 private-channel path** which shipped 2026-09-11, and **Wave 3** (01 gated promote lock + 08 share cron / idle-breed weights + 05 vote recipes) which shipped 2026-09-13. Still parked: auto-promote, mesh introduce scripting, Roku Channel Store, library **rotate**, pasture filename-vs-alias toggle.

**Pre-open slices** already shipped (docs + operator CLIs; not those products): end-user baseline, sheep-disk check, concurrent-client estimator, and catalog sidecar key names. **Opened 2026-09-09:** worker preserves reserved sidecar keys on re-ingest. **Opened 2026-09-09:** pasture clients re-poll the flock on mid-session 404 (quarantine / Shears). **Opened 2026-09-10:** wrap-once flock re-fetch + 313 session cap. **Opened 2026-09-10:** worker drain (finish current job, pause claiming until cancel). **Opened 2026-09-09:** 07 estimator Owner OK; 09 RNG aliases (ingest + backfill + override).

## Status

| Item | State |
|---|---|
| Phase 4 products | **Mostly parked** (2026-08-16) — tuples (03), 09 RNG, 08 overlay + Wave 3 share/breed, 04 private-channel path shipped; do not implement auto-promote / Store / rotate until Owner opens those slices |
| Peer share path revisit | **Locked Wave 3** — keep gated `promote --apply` ([01](01_PEER_SHARE_PATH.md)); share cron stages `peers/share-out` only |
| Mesh introduce scripting | Parked — [02](02_MESH_INTRODUCE_SCRIPTING.md) |
| Edges + watermark | **Tuple slice shipped** 2026-09-05 — [03](03_EDGES_AND_WATERMARK.md); catalog `by-generation/tuple/`; idle-cron mode; Roku shuffle includes `tuple` + `pedigree`. Standalone `type: edge` files + loop/stills watermark still parked |
| Roku VoD + screensaver publish | **Private-channel path shipped** 2026-09-11 — [04](04_ROKU_PUBLISH.md) (VoD as unpublished channel + one sideload slot for SS; SS Settings writes Jellyfin creds in **1.0.10**). Channel Store / brand assets parked |
| End-user guide (tasks / examples / triage) | **Baseline + vote/share recipe** — [05](05_END_USER_GUIDE.md); [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) (example 6); fridge card [FRIDGE_CARD.md](../FRIDGE_CARD.md) |
| Sheep library disk check + auto-purge / rotate | **Check slice shipped** 2026-09-03 — [06](06_LIBRARY_DISK_ROTATE.md); healthcheck WARN/BAD; auto-purge / worker refuse parked |
| Concurrent clients / link-capacity estimate | **Estimator shipped** 2026-09-03 — [07](07_CONCURRENT_CLIENTS.md); `python3 -m pipeline.link_capacity`; **Owner OK 2026-09-09** |
| Viewer feedback loop (vote → share + breed bias) | **Wave 2+3 shipped** — [08](08_VIEWER_FEEDBACK_LOOP.md); VoD **1.0.32** overlay; share cron; idle-breed weights. Auto-promote parked |
| Sheep naming (auto-generated aliases) | **RNG slice shipped** 2026-09-09 — [09](09_SHEEP_NAMING.md); `python3 -m pipeline.sheep_naming`; client filename/alias toggle parked |

## Pre-open shipped (2026-09-03)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Household guide + fridge card | [05](05_END_USER_GUIDE.md) | [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) Layer 1 + worked examples (incl. vote/share); [FRIDGE_CARD.md](../FRIDGE_CARD.md) | Alias display toggle |
| Sheep disk WARN/BAD | [06](06_LIBRARY_DISK_ROTATE.md) | `python3 -m pipeline.library_disk check`; healthcheck | Auto-purge, worker refuse on sheep mount, rotate cron |
| Concurrent-client `N_max` | [07](07_CONCURRENT_CLIENTS.md) | `python3 -m pipeline.link_capacity`; WiFi-STA lab note; **Owner OK 2026-09-09** | Enforcing `N_max` as a Jellyfin cap; Ethernet lab (eth0 DOWN) |
| Sidecar key names | [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) | `type`, `watermark`, `viewer_feedback`, `alias` (+ companions) | Client alias toggle |
| Tuples (loop A + edge + loop B) | [03](03_EDGES_AND_WATERMARK.md) | One MP4 under `by-generation/tuple/`; edge-only watermark; idle-cron mode; Roku shuffle `tuple`+`pedigree` | Standalone edge files; watermark on loops/stills; Kodi edge sequencer |

## Opened (2026-09-09)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Sidecar preserve | [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) | Worker copies reserved keys on re-ingest; tuples still write `type` / `from_id` / `to_id` / `watermark` from this encode | — |
| 404 mid-session re-poll | clients | Drop dead Jellyfin id, rate-limited re-poll, continue session: VoD **1.0.29**, Roku SS **1.0.8**, Kodi SS **0.2.7** | — |
| Wrap-once flock re-fetch + 313 cap | clients | Once per full shuffle wrap (one random permutation; next item is not last-played), re-fetch Jellyfin and regenerate the in-memory list (skip if a fetch is already in flight; no 30s 404 gate). HTTP Limit 5000 then randomly prune to **313**. VoD **1.0.31**, Roku SS **1.0.9**, Kodi SS **0.2.9** | Hours-scale timer (not needed for ~daily ingest) |
| 07 estimator Owner OK | [07](07_CONCURRENT_CLIENTS.md) | Sign-off 2026-09-09; `N_max` remains an estimate | Enforcing `N_max` as a Jellyfin cap |
| 09 RNG aliases | [09](09_SHEEP_NAMING.md) | Hash-seed `adjective_surname` on ingest/backfill; `set-alias` / `clear-alias` | Roku/Kodi filename vs alias toggle; LLM poster naming → [../phase5/02](../phase5/02_LLM_INTEGRATION.md) |
| Worker drain / idle-before-restart | furnace polish | Finish current inbox job, then do not claim; `python3 -m pipeline.worker_drain` (`request`, `wait`, `cancel`). Flag persists until cancel. | Checkpoint/resume inside `flam3-animate`; SIGSTOP live animate |

## Opened (2026-09-11)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Viewer overlay + sidecar sink | [08](08_VIEWER_FEEDBACK_LOOP.md) | VoD **1.0.32** transient like/love/vote overlay (last 12 s, playback continues). `POST /v1/sheep-votes` on `jellyflam3-display-sink` (:8791) increments `{stem}.jellyflam3.json` `viewer_feedback` and sets `share_candidate`. CLI `python3 -m pipeline.sheep_votes`. Unlimited re-vote. No screensaver voting. | Auto-promote |
| Private-channel path | [04](04_ROKU_PUBLISH.md) | In-repo runbook: VoD as unpublished/private channel so the one sideload slot can hold screensaver. Roku SS **1.0.10** Settings writes Jellyfin creds (registry is per channel ID once packages coexist). | Channel Store listing; brand-asset refresh; VoD Settings layout polish; Owner dashboard publish |

## Opened (2026-09-13)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Gated promote lock | [01](01_PEER_SHARE_PATH.md) | Keep `peers/inbox` → `promote --apply` → `genomes/inbox`. Votes never skip that gate. | Auto-promote after tax + verify |
| Share cron + idle-breed weights | [08](08_VIEWER_FEEDBACK_LOOP.md) | `python3 -m pipeline.share_votes` + `scripts/cron_share_votes.sh` copy liked `.flam3` to `peers/share-out`. Idle-breed parent weight ∝ sidecar `votes`. | Screensaver voting; auto-promote |
| Vote / share household recipe | [05](05_END_USER_GUIDE.md) | Runbook example 6: OK/FF/Replay, LAN-only, love vs share, receiver still promotes | Pasture filename/alias toggle |

## In scope (parked products)

1. [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) — **gated promote locked**; auto-promote still parked
2. [02_MESH_INTRODUCE_SCRIPTING.md](02_MESH_INTRODUCE_SCRIPTING.md) — options A–D for first-time Syncthing mesh introduce (or stay manual)
3. [03_EDGES_AND_WATERMARK.md](03_EDGES_AND_WATERMARK.md) — **tuples shipped**; remaining: standalone edges, loop/stills watermark, Kodi edge sequencer
4. [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) — **private-channel path shipped**; remaining: Store listing, brand assets, VoD Settings layout, Owner dashboard publish
5. [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) — baseline + vote/share recipe shipped; remaining: alias display on pasture
6. [06_LIBRARY_DISK_ROTATE.md](06_LIBRARY_DISK_ROTATE.md) — auto-purge / rotate / worker refuse (check slice already shipped)
7. [07_CONCURRENT_CLIENTS.md](07_CONCURRENT_CLIENTS.md) — **Owner OK 2026-09-09** on the shipped estimator (enforcing `N_max` as a Jellyfin cap stays parked)
8. [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) — overlay + share cron + breed weights shipped; auto-promote parked
9. [09_SHEEP_NAMING.md](09_SHEEP_NAMING.md) — **RNG slice shipped**; remaining: client filename/alias toggle. LLM-from-poster → [../phase5/02_LLM_INTEGRATION.md](../phase5/02_LLM_INTEGRATION.md)

Also named (aspirational / TBD): broader social flock, DeepDream/AI backends. **LLM-assisted pedigree** and **LLM poster naming** moved to **Phase 5** ([../phase5/00_OVERVIEW.md](../phase5/00_OVERVIEW.md)): a **separate** Ventuno LLM Agent Platform talking to the Pi furnace — not models on the furnace and not Ventuno-as-16a. Guide [08](08_VIEWER_FEEDBACK_LOOP.md) overlay + share cron + breed weights shipped (auto-promote parked); [09](09_SHEEP_NAMING.md) RNG aliases stay here (LLM path in Phase 5).

Sidecar key names for [01](01_PEER_SHARE_PATH.md) / [03](03_EDGES_AND_WATERMARK.md) / [08](08_VIEWER_FEEDBACK_LOOP.md) / [09](09_SHEEP_NAMING.md) are reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Worker copies reserved keys on re-ingest; tuple ingest writes `type` / `from_id` / `to_id` / `watermark` from this encode. Vote sink writes `viewer_feedback` on the catalog sidecar. Pasture alias display stays parked.

### Client polish (shipped wrap-once refresh)

| Item | Notes |
|---|---|
| **Wrap-once flock refresh** | **Shipped** VoD **1.0.31**, Roku screensaver **1.0.9**, Kodi screensaver **0.2.9**. A wrap is one random permutation of the in-memory list (each item once). Fetch Jellyfin with Limit **5000**, then randomly prune to **313** (VoD/Kodi: sheep items; Roku SS: Primary+Backdrop URLs — Primaries only until Backdrop tags exist). Kick a re-fetch at wrap and replace the list when it arrives — do not stall the current clip/still. Rotate so the first item of the new mix is not the last-played id (Roku SS applies that rotate when the wrap fetch returns). Skip wrap fetch if one is already in flight. 404 re-poll keeps its **30s** gate and is separate. Single-item lists do not wrap-refetch. Hours-scale timer stays unneeded for ~daily ingest. Household wording: [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md#flock-mix-shuffle-wrap). |

**Shipped (not parked):** **Quarantine / 404 mid-session re-poll** — VoD 1.0.29, Roku screensaver 1.0.8, Kodi screensaver 0.2.7. On file-not-found / stream open fail / missing Primary or Backdrop, clients drop the dead id, re-poll Jellyfin (rate-limited to 30s), and continue the session. Does not stop playback chrome, does not invent a Sessions Playing client for the miss.

### Furnace polish (shipped drain)

| Item | Notes |
|---|---|
| **Worker drain / idle-before-restart** | **Shipped** `python3 -m pipeline.worker_drain`. Finish the current inbox job, then do not claim the next genome. Worker keeps watching inbox (seed/breed may refill; files wait). Flag file `/var/lib/jellyflam3/worker_drain.json` persists across restart until `cancel` / `resume` / `undrain` (no restart required to resume). `request --wait` blocks until no in-flight job.json (`queued`/`rendering`/`encoding`/`gating`) — then `systemctl restart jellyflam3-worker` does not orphan a live `flam3-animate`. Distinct from the **idle-gate** (TV Playing) and from an **empty inbox**. Per host. Household recipe: [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md#5--pause-the-furnace-drain). Tracked in [../phase1/05_RENDER_PIPELINE.md](../phase1/05_RENDER_PIPELINE.md), [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md), `pipeline.job_recovery`. |

**Not this slice:** checkpoint/resume inside `flam3-animate`; SIGSTOP of a live animate as “pause”; killing the current job on purpose (that is today’s restart without drain). Drain is **pause before the next inbox render**, not mid-frame. The first pull of this code still needs one worker restart to load the poll check — do that between jobs if you can.

### Furnace polish (pre-wave 3 — idle-gate **shipped**)

P1 + remaining races **shipped** (Owner OK 2026-09-13). Guide [06](../phase1/06_IDLE_GATE.md).

| Item | Status |
|---|---|
| Supervisor-only SoT writer | Readers never write. Missing file = closed. Hammer unlinks status (no fake `open`) |
| Restore `idle_delay` after idlegate restart | Hydrate `_seen_block` / `_clear_since` from `idle_clear_since` when `reason=idle_delay` |
| Stale `updated_at` | `open` older than **3×** `poll_interval_sec` (60 s at default 20 s poll) is closed |
| `wait_for_gate` vs `seconds_until_resume` | Sleep `min(15, max(1, eta))` when eta > 0; else 15 s |
| `freeze_worker` vs drain | Keep `freeze_worker: false`. `worker_drain wait` errors if the unit is frozen |
| Mid-animate CPU | **Locked:** Playing does not pause `flam3-animate`; gate is stage boundaries only |

## Out of scope

- Phase 3 feature guides still owned under [`docs/phase3/`](../phase3/00_OVERVIEW.md) (01–03, 05–10; stub at former 04)
- Changing the locked Phase 2 peering contract **before** this phase opens

## Prerequisites

Phase 3 RC (or Owner waiver) preferred before opening Phase 4 products, so Shears, share-security, and screensaver baselines stay stable inputs for edges / watermark / peering revisits / Roku publish / rotate / viewer feedback / sheep naming.

## See also

[../phase3/00_OVERVIEW.md](../phase3/00_OVERVIEW.md) · [../phase5/00_OVERVIEW.md](../phase5/00_OVERVIEW.md) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [`deploy/peering/README.md`](../../deploy/peering/README.md)
