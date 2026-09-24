# Phase 4 overview

## Boundary

Phase 4 **products are implemented** as of **v0.3.2** (2026-09-23). Shipped: **tuples (guide 03)** 2026-09-05, **09 RNG aliases** 2026-09-09, **08 overlay + sidecar vote sink** and **04 private-channel path** 2026-09-11, **Wave 3** (01 gated promote lock + 08 share cron / idle-breed weights + 05 vote recipes) 2026-09-13, **Wave 4 slices 1–2** (06 library rotate + 02 mesh introduce A/B/C) 2026-09-13 (**02 closed** Owner OK 2026-09-19), **09 C Roku VoD titleMode** 2026-09-13, **09 Kodi/Roku screensaver captions** 2026-09-19, and **04 VoD Channel Store submission** 2026-09-23 (pending Roku review). **Leftovers (not blocking close):** JellyFlam3 Dreams Store listing (screensaver package is not cert-clean); optional Jellyfin OriginalTitle / SortName-as-alias. **Cancelled 2026-09-13:** standalone edge files / loop-stills watermark / Kodi edge sequencer (tuples close 03); **Roku** screensaver voting (best practices — VoD overlay only; **Kodi screensaver votes** → [../phase5/05_KODI_SCREENSAVER_VOTES.md](../phase5/05_KODI_SCREENSAVER_VOTES.md)); enforcing `N_max` as a Jellyfin cap and an Ethernet control lab (07 — this fleet is WiFi STA, `eth0 DOWN`); **auto-promote** (01 — gated `promote --apply` is the receive path). **Cancelled 2026-09-19:** furnace polish leftover that is **not drain** — checkpoint/resume inside `flam3-animate` and SIGSTOP of a live animate as “pause” (`flam3-animate` has no resume protocol). Drain stays shipped.

**Pre-open slices** already shipped (docs + operator CLIs; not those products): end-user baseline, sheep-disk check, concurrent-client estimator, and catalog sidecar key names. **Opened 2026-09-09:** worker preserves reserved sidecar keys on re-ingest. **Opened 2026-09-09:** pasture clients re-poll the flock on mid-session 404 (quarantine / Shears). **Opened 2026-09-10:** wrap-once flock re-fetch + 313 session cap. **Opened 2026-09-10:** worker drain (finish current job, pause claiming until cancel). **Opened 2026-09-09:** 07 estimator Owner OK; 09 RNG aliases (ingest + backfill + override).

## Status

| Item | State |
|---|---|
| Phase 4 products | **Implemented** 2026-09-23 (`v0.3.2`) — tuples (03), 09 RNG + VoD `titleMode` + Kodi/Roku SS captions, 08 overlay + Wave 3 share/breed, 04 private-channel path + **VoD Store submitted** (pending review), **06 rotate closed**, **02 mesh closed**; gated promote **locked** (auto-promote **cancelled**). Leftovers: Dreams Store listing; optional Jellyfin OriginalTitle / SortName |
| Peer share path revisit | **Locked** — gated `promote --apply` ([01](01_PEER_SHARE_PATH.md)); share cron stages `peers/share-out` only (no Syncthing folder). **Auto-promote cancelled** 2026-09-13. Inbox hop → [../phase5/04](../phase5/04_PEER_SHARE_MESH.md) |
| Mesh introduce scripting | **Closed** 2026-09-19 (Owner OK) — [02](02_MESH_INTRODUCE_SCRIPTING.md) A/B/C; manual add-json still valid. Share-out hop / promote-vs-sendreceive → [../phase5/04](../phase5/04_PEER_SHARE_MESH.md) |
| Edges + watermark | **Tuple slice shipped** 2026-09-05 — [03](03_EDGES_AND_WATERMARK.md). Standalone `type: edge` files, loop/stills watermark, and Kodi edge sequencer **cancelled** 2026-09-13 (tuples cover the journey) |
| Roku VoD + screensaver publish | **VoD Store submitted** 2026-09-23 (pending review) — [04](04_ROKU_PUBLISH.md). Private-channel path shipped 2026-09-11 (SS Settings writes Jellyfin creds in **1.0.10**). **Dreams Store listing leftover** (screensaver not cert-clean) |
| End-user guide (tasks / examples / triage) | **Baseline + vote/share recipe** — [05](05_END_USER_GUIDE.md); [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) (examples 6–7); fridge card [FRIDGE_CARD.md](../FRIDGE_CARD.md) |
| Sheep library disk check + auto-purge / rotate | **Closed** 2026-09-19 — [06](06_LIBRARY_DISK_ROTATE.md); healthcheck WARN/BAD; worker refuse on sheep BAD; daily cron optional ([Activate daily rotate](06_LIBRARY_DISK_ROTATE.md#activate-daily-rotate)) |
| Concurrent clients / link-capacity estimate | **Estimator shipped** 2026-09-03 — [07](07_CONCURRENT_CLIENTS.md); `wifi-pi` lab (`eth0 DOWN`); **Owner OK 2026-09-09**. Jellyfin cap / Ethernet lab **cancelled** |
| Viewer feedback loop (vote → share + breed bias) | **Wave 2+3 shipped** — [08](08_VIEWER_FEEDBACK_LOOP.md); VoD **1.0.32** overlay; share cron; idle-breed weights. **Roku screensaver voting** and **auto-promote cancelled** 2026-09-13. **Kodi SS votes** [../phase5/05](../phase5/05_KODI_SCREENSAVER_VOTES.md) |
| Sheep naming (auto-generated aliases) | **RNG + VoD + screensaver captions shipped** — [09](09_SHEEP_NAMING.md); VoD **1.0.33** `titleMode`; Kodi **0.2.12**; Roku SS **1.0.11**. Optional Jellyfin OriginalTitle/SortName parked; LLM poster naming → Phase 5 |

## Pre-open shipped (2026-09-03)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Household guide + fridge card | [05](05_END_USER_GUIDE.md) | [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) Layer 1 + worked examples (incl. vote/share); [FRIDGE_CARD.md](../FRIDGE_CARD.md) | Optional Jellyfin OriginalTitle / SortName-as-alias |
| Sheep disk WARN/BAD | [06](06_LIBRARY_DISK_ROTATE.md) | `python3 -m pipeline.library_disk check`; healthcheck | Rotate + worker refuse (opened 2026-09-13; **closed** 2026-09-19) |
| Concurrent-client `N_max` | [07](07_CONCURRENT_CLIENTS.md) | `python3 -m pipeline.link_capacity`; WiFi-STA lab (`eth0 DOWN`); **Owner OK 2026-09-09** | **Cancelled** 2026-09-13: Jellyfin cap; Ethernet control lab |
| Sidecar key names | [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) | `type`, `watermark`, `viewer_feedback`, `alias` (+ companions) | Optional Jellyfin OriginalTitle / SortName-as-alias |
| Tuples (loop A + edge + loop B) | [03](03_EDGES_AND_WATERMARK.md) | One MP4 under `by-generation/tuple/`; edge-only watermark; idle-cron mode; Roku shuffle `tuple`+`pedigree` | **Cancelled** 2026-09-13: standalone edge files; watermark on loops/stills; Kodi edge sequencer |

## Opened (2026-09-09)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Sidecar preserve | [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) | Worker copies reserved keys on re-ingest; tuples still write `type` / `from_id` / `to_id` / `watermark` from this encode | — |
| 404 mid-session re-poll | clients | Drop dead Jellyfin id, rate-limited re-poll, continue session: VoD **1.0.29**, Roku SS **1.0.8**, Kodi SS **0.2.7** | — |
| Wrap-once flock re-fetch + 313 cap | clients | Once per full shuffle wrap (one random permutation; next item is not last-played), re-fetch Jellyfin and regenerate the in-memory list (skip if a fetch is already in flight; no 30s 404 gate). HTTP Limit 5000 then randomly prune to **313**. VoD **1.0.31**, Roku SS **1.0.9**, Kodi SS **0.2.9** | Hours-scale timer (not needed for ~daily ingest) |
| 07 estimator Owner OK | [07](07_CONCURRENT_CLIENTS.md) | Sign-off 2026-09-09; `N_max` remains an estimate (not a Jellyfin cap); lab hop is WiFi STA | — |
| 09 RNG aliases | [09](09_SHEEP_NAMING.md) | Hash-seed `adjective_surname` on ingest/backfill; `set-alias` / `clear-alias` | Roku VoD `titleMode` (opened 2026-09-13); Kodi/SS captions (opened 2026-09-19); LLM poster naming → [../phase5/02](../phase5/02_LLM_INTEGRATION.md) |
| Worker drain / idle-before-restart | furnace polish | Finish current inbox job, then do not claim; `python3 -m pipeline.worker_drain` (`request`, `wait`, `cancel`). Flag persists until cancel. | **Cancelled** 2026-09-19: checkpoint/resume inside `flam3-animate`; SIGSTOP live animate |

## Opened (2026-09-11)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Viewer overlay + sidecar sink | [08](08_VIEWER_FEEDBACK_LOOP.md) | VoD **1.0.32** overlay; **1.0.40** last **7 s**, one-line 55% banner; **1.0.41** same bar as loading-next. **1.0.38** two-tier **OK** love / **Right** like / **Down** dismiss / **Up-Back** exit. `POST /v1/sheep-votes` on `jellyflam3-display-sink` (:8791) increments `{stem}.jellyflam3.json` `viewer_feedback` and sets `share_candidate`. CLI `python3 -m pipeline.sheep_votes` (`apply` / `show` / `top` / `sweep --confirm SWEEP`). Unlimited re-vote. **Roku** screensaver voting **cancelled**. Kodi SS **0.2.13+**: [../phase5/05](../phase5/05_KODI_SCREENSAVER_VOTES.md). | — |
| Private-channel path | [04](04_ROKU_PUBLISH.md) | In-repo runbook: VoD as unpublished/private channel so the one sideload slot can hold screensaver. Roku SS **1.0.10** Settings writes Jellyfin creds (registry is per channel ID once packages coexist). **VoD Store submitted** 2026-09-23 (pending review). | Dreams Store listing; optional friendly screen name |

## Opened (2026-09-13)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Gated promote lock | [01](01_PEER_SHARE_PATH.md) | Keep `peers/inbox` → `promote --apply` → `genomes/inbox`. Votes never skip that gate. | **Cancelled** 2026-09-13: auto-promote after tax + verify |
| Share cron + idle-breed weights | [08](08_VIEWER_FEEDBACK_LOOP.md) | `python3 -m pipeline.share_votes` + `scripts/cron_share_votes.sh` copy liked `.flam3` to `peers/share-out` (local stage; **not** a Syncthing folder). Idle-breed parent weight ∝ sidecar `votes`. | Inbox hop → [../phase5/04](../phase5/04_PEER_SHARE_MESH.md) |
| Vote / share household recipe | [05](05_END_USER_GUIDE.md) | Runbook example 6: OK love / Right like; LAN-only; love vs share; receiver still promotes. Example 8: `sheep_votes top`. | Optional Jellyfin OriginalTitle / SortName-as-alias |

## Opened (2026-09-13, Wave 4 slices 1–2)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Library rotate | [06](06_LIBRARY_DISK_ROTATE.md) | Oldest-mtime Shears cascade; `library_disk rotate [--apply]`; `cron_library_rotate.sh` optional ([Activate daily rotate](06_LIBRARY_DISK_ROTATE.md#activate-daily-rotate)); archive seed skips fetch if sheep still BAD; worker refuse on sheep **BAD**. **Closed** 2026-09-19 (Owner OK). | LRU / soak-fill stay non-goals |
| Mesh introduce | [02](02_MESH_INTRODUCE_SCRIPTING.md) | `ensure-mesh-local`; gitignored `mesh-join` (skip self; refresh address/introducer; positional `add-json`); 16a introducer. **Closed** 2026-09-19 (Owner OK). | Mesh admin UI; committing device IDs (non-goals). Share-out hop / promote-move → [../phase5/04](../phase5/04_PEER_SHARE_MESH.md) |

## Opened (2026-09-13, 09 C)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| VoD filename vs alias | [09](09_SHEEP_NAMING.md) | VoD **1.0.33** Settings `titleMode` (`filename` default / `alias`); **1.0.39** OK-toggle + immediate flush + Save & Reload. Overview `Alias:` line from ingest + `sheep_naming` push. `Name` stays the stem. | Optional Jellyfin OriginalTitle / SortName-as-alias |

## Opened (2026-09-19, 09 screensaver captions)

| Slice | Guide | What landed | Still parked |
|---|---|---|---|
| Kodi + Roku SS captions | [09](09_SHEEP_NAMING.md) | Kodi **0.2.12** `title_mode` + caption 101; Roku SS **1.0.11** Settings `titleMode` + stills caption. Overview `Alias:`; filename default; missing alias falls back. | Optional Jellyfin OriginalTitle / SortName-as-alias |

## Guides (implemented)

1. [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) — **gated `promote --apply` is the product**; auto-promote **cancelled** 2026-09-13
2. [02_MESH_INTRODUCE_SCRIPTING.md](02_MESH_INTRODUCE_SCRIPTING.md) — **closed** 2026-09-19 (Owner OK); share-out/promote leftovers → [../phase5/04_PEER_SHARE_MESH.md](../phase5/04_PEER_SHARE_MESH.md)
3. [03_EDGES_AND_WATERMARK.md](03_EDGES_AND_WATERMARK.md) — **tuples shipped**; standalone edges / extra watermark / Kodi sequencer **cancelled** 2026-09-13
4. [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) — **private-channel path shipped**; **VoD Channel Store submitted** 2026-09-23 (pending review). Leftover: Dreams Store listing
5. [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) — baseline + vote/share recipe shipped; VoD alias titles in 09 C
6. [06_LIBRARY_DISK_ROTATE.md](06_LIBRARY_DISK_ROTATE.md) — **closed** 2026-09-19 (Owner OK); daily cron is optional ops, not remaining product
7. [07_CONCURRENT_CLIENTS.md](07_CONCURRENT_CLIENTS.md) — **Owner OK 2026-09-09**; estimator closed (no Jellyfin cap; no Ethernet lab on this `eth0 DOWN` fleet)
8. [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) — overlay + share cron + breed weights shipped; auto-promote **cancelled**; **Roku** screensaver voting **cancelled**; Kodi SS votes → [../phase5/05](../phase5/05_KODI_SCREENSAVER_VOTES.md)
9. [09_SHEEP_NAMING.md](09_SHEEP_NAMING.md) — **RNG + VoD `titleMode` + Kodi/Roku SS captions shipped**; optional Jellyfin OriginalTitle / SortName-as-alias parked. LLM-from-poster → [../phase5/02_LLM_INTEGRATION.md](../phase5/02_LLM_INTEGRATION.md)

Also named (aspirational / TBD): broader social flock, DeepDream/AI backends. **LLM-assisted pedigree** and **LLM poster naming** moved to **Phase 5** ([../phase5/00_OVERVIEW.md](../phase5/00_OVERVIEW.md)): a **separate** Ventuno LLM Agent Platform talking to the Pi furnace — not models on the furnace and not Ventuno-as-16a. Guide [08](08_VIEWER_FEEDBACK_LOOP.md) overlay + share cron + breed weights shipped (auto-promote **cancelled**); [09](09_SHEEP_NAMING.md) RNG aliases stay here (LLM path in Phase 5).

Sidecar key names for [01](01_PEER_SHARE_PATH.md) / [03](03_EDGES_AND_WATERMARK.md) / [08](08_VIEWER_FEEDBACK_LOOP.md) / [09](09_SHEEP_NAMING.md) are reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Worker copies reserved keys on re-ingest; tuple ingest writes `type` / `from_id` / `to_id` / `watermark` from this encode. Vote sink writes `viewer_feedback` on the catalog sidecar. Roku VoD, Kodi screensaver, and Roku screensaver can show aliases. Optional Jellyfin OriginalTitle / SortName-as-alias stays parked.

### Client polish (shipped wrap-once refresh)

| Item | Notes |
|---|---|
| **Wrap-once flock refresh** | **Shipped** VoD **1.0.31**, Roku screensaver **1.0.9**, Kodi screensaver **0.2.9**. A wrap is one random permutation of the in-memory list (each item once). Fetch Jellyfin with Limit **5000**, then randomly prune to **313** (VoD/Kodi: sheep items; Roku SS: Primary+Backdrop URLs — Primaries only until Backdrop tags exist). Kick a re-fetch at wrap and replace the list when it arrives — do not stall the current clip/still. Rotate so the first item of the new mix is not the last-played id (Roku SS applies that rotate when the wrap fetch returns). Skip wrap fetch if one is already in flight. 404 re-poll keeps its **30s** gate and is separate. Single-item lists do not wrap-refetch. Hours-scale timer stays unneeded for ~daily ingest. Household wording: [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md#flock-mix-shuffle-wrap). |

**Shipped (not parked):** **Quarantine / 404 mid-session re-poll** — VoD 1.0.29, Roku screensaver 1.0.8, Kodi screensaver 0.2.7. On file-not-found / stream open fail / missing Primary or Backdrop, clients drop the dead id, re-poll Jellyfin (rate-limited to 30s), and continue the session. Does not stop playback chrome, does not invent a Sessions Playing client for the miss.

### Furnace polish (shipped drain)

| Item | Notes |
|---|---|
| **Worker drain / idle-before-restart** | **Shipped** `python3 -m pipeline.worker_drain`. Finish the current inbox job, then do not claim the next genome. Worker keeps watching inbox (seed/breed may refill; files wait). Flag file `/var/lib/jellyflam3/worker_drain.json` persists across restart until `cancel` / `resume` / `undrain` (no restart required to resume). `request --wait` blocks until no in-flight job.json (`queued`/`rendering`/`encoding`/`gating`) — then `systemctl restart jellyflam3-worker` does not orphan a live `flam3-animate`. Distinct from the **idle-gate** (TV Playing) and from an **empty inbox**. Per host. Household recipe: [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md#5--pause-the-furnace-drain). Tracked in [../phase1/05_RENDER_PIPELINE.md](../phase1/05_RENDER_PIPELINE.md), [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md), `pipeline.job_recovery`. |

Drain is **pause before the next inbox render**, not mid-frame. Killing the current job on purpose is still today’s restart-without-drain (orphan + `job_recovery` drops scratch). The first pull of drain still needs one worker restart to load the poll check — do that between jobs if you can.

**Cancelled 2026-09-19 (not drain):** checkpoint/resume inside `flam3-animate`, and SIGSTOP of a live animate as a product pause. `flam3-animate` writes sequential frames with **no documented checkpoint**; partial scratch is not a resume state (`job_recovery` already drops frames and re-queues). Freeze (`SIGSTOP`) is not a renderer protocol — it holds RAM/CPU/open files without serializing progress, and a later `SIGCONT` is not a supported animate restart. Worker and idle-gate stay at **stage boundaries** (`freeze_worker: false`). There is no later Phase 4 slice for mid-animate pause.

### Furnace polish (pre-wave 3 — idle-gate **shipped**)

P1 + remaining races **shipped** (Owner OK 2026-09-13). Guide [06](../phase1/06_IDLE_GATE.md).

| Item | Status |
|---|---|
| Supervisor-only SoT writer | Readers never write. Missing file = closed. Hammer unlinks status (no fake `open`) |
| Restore `idle_delay` after idlegate restart | Hydrate `_seen_block` / `_clear_since` from `idle_clear_since` when `reason=idle_delay` |
| Stale `updated_at` | `open` older than **3×** `poll_interval_sec` (60 s at default 20 s poll) is closed |
| `wait_for_gate` vs `seconds_until_resume` | Sleep `min(15, max(1, eta))` when eta > 0; else 15 s |
| `freeze_worker` vs drain | Keep `freeze_worker: false`. `worker_drain wait` errors if the unit is frozen |
| Mid-animate CPU | **Locked:** Playing does not pause `flam3-animate`; gate is stage boundaries only. Checkpoint / SIGSTOP pause **cancelled** 2026-09-19 (see drain section) |

## Out of scope

- Phase 3 feature guides still owned under [`docs/phase3/`](../phase3/00_OVERVIEW.md) (01–03, 05–10; stub at former 04)
- Changing the locked Phase 2 peering contract **before** this phase opens

## Prerequisites

Phase 3 RC (or Owner waiver) preferred before opening Phase 4 products, so Shears, share-security, and screensaver baselines stay stable inputs for edges / watermark / peering revisits / Roku publish / rotate / viewer feedback / sheep naming.

## See also

[../phase3/00_OVERVIEW.md](../phase3/00_OVERVIEW.md) · [../phase5/00_OVERVIEW.md](../phase5/00_OVERVIEW.md) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [`deploy/peering/README.md`](../../deploy/peering/README.md)
