# 05 — End-user guide (tasks, examples, triage)

## Boundary

Phase 4 synopsis — author a **household / end-user** guide for day-to-day JellyFlam3 operation: common tasks, worked examples, and problem triage. Audience is the person running one or more Pis + Roku(s), not the Phase 1–3 implementer reading feature guides.

**Status:** Baseline complete (Owner OK 2026-09-03). Day-to-day use: **[../USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md)** (Layer 1 + [worked examples](../USER_GUIDE_AND_RUNBOOK.md#worked-examples) + Layer 2 triage). Fridge card: **[../FRIDGE_CARD.md](../FRIDGE_CARD.md)**. Overlay button map + vote/share recipe: VoD **1.0.32** and [worked example 6](../USER_GUIDE_AND_RUNBOOK.md#6--vote-then-share). Filename vs alias on VoD **1.0.33** Settings `titleMode` ([09](09_SHEEP_NAMING.md)).

Complements (does not replace):

- Build/install: [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md)
- Architecture SoT: [../Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md)
- Peering lab runbook: [`deploy/peering/README.md`](../../deploy/peering/README.md)
- Feature guides under `docs/phase1–3/` (developers)

## Intent

| Need | Why |
|---|---|
| **Common tasks** | Short “how do I…?” recipes without hunting across phase guides |
| **Examples** | Copy-pasteable commands and Settings values for a typical one-Pi / multi-Roku home |
| **Triage** | Symptom → check → fix for idle-gate stuck, empty flock, screensaver blank, peering stuck, worker quiet |

## Work items

### A — Guide shape (shipped)

1. Primary doc is [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) (not a separate `docs/end-user/` tree), linked from project README + Phase 4 overview.
2. Tone: operator-facing; assume Phase 2/3 baselines already installed.
3. Secrets stay out of examples (`secrets.env` / live yaml never pasted); placeholders only.

### B — Common tasks (minimum set)

| Task | Sketch |
|---|---|
| Check health | `./scripts/healthcheck.sh`; services; tip `git rev-parse` |
| See idle-gate | `cat /var/lib/jellyflam3/idle_gate_status.json` |
| Pause new renders | `python3 -m pipeline.worker_drain request --wait` then `cancel` to resume |
| Play on Roku VoD | Settings IDs via `jellyfin_id_dump.py`; launch / deep link notes |
| Enable screensaver | SS Settings **1.0.10** writes Jellyfin creds, or furnace zip, or VoD Settings while sharing the developer slot; Theme → Screensavers; fade/dwell. SS always rotates (ignores `shuffleFlock`); Primary + Backdrop; no tuples; **1.0.9** wrap-refetch. Private-channel path: [04](04_ROKU_PUBLISH.md#private-channel-path-wave-2) |
| Extract stills | Poster ingest / `backfill_posters`; operator `python3 -m pipeline.stills --dry-run` / `--limit N` |
| Breed / seed | Manual `pipeline.breed` or daily `cron_breed_idle.sh` when inbox empty; idle-breed **weights parents by sidecar votes** when present ([08](08_VIEWER_FEEDBACK_LOOP.md)) |
| Promote peer share | Opt In; **gated** `promote --apply` on receive. Liked sheep: `cron_share_votes.sh` copies to `peers/share-out` (local; not Syncthing) ([08](08_VIEWER_FEEDBACK_LOOP.md)); inbox hop → [../phase5/04](../phase5/04_PEER_SHARE_MESH.md); auto-promote **cancelled** ([01](01_PEER_SHARE_PATH.md)) |
| Vote / like a sheep | Roku VoD overlay last **7 s** ([08](08_VIEWER_FEEDBACK_LOOP.md)); Kodi SS **0.2.13** ([../phase5/05](../phase5/05_KODI_SCREENSAVER_VOTES.md)); LAN-only POST; re-votes allowed; love is a stronger tally, not a different share path |
| See most-voted sheep | `python3 -m pipeline.sheep_votes top` / `top -n 5` ([example 8](../USER_GUIDE_AND_RUNBOOK.md#8--list-top-voted-sheep)) |
| Clear household votes | `python3 -m pipeline.sheep_votes sweep` then `--confirm SWEEP` ([example 7](../USER_GUIDE_AND_RUNBOOK.md#7--sweep-votes-fresh-start-on-this-furnace)); does not unshare `peers/share-out` |
| Rename / alias a sheep | [09](09_SHEEP_NAMING.md): auto `adjective_surname` or human override; VoD / Kodi SS / Roku SS `titleMode` filename vs alias |
| Delete a sheep | Shears dry-run → apply (Phase 3 / 03) |
| Multi-Roku | Same Jellyfin URL on each TV; `display_profiles list` |
| Update fleet | `git pull` on each Pi; when to restart units |

### C — Worked examples

Shipped in [USER_GUIDE_AND_RUNBOOK.md — Worked examples](../USER_GUIDE_AND_RUNBOOK.md#worked-examples) (Owner OK 2026-09-03):

1. First evening after install: dump IDs → VoD Settings → play one sheep → confirm gate closes → stop play → gate opens.
2. Screensaver evening: sideload SS → Theme select → confirm gate stays open.
3. Two Rokus, one Pi: Fetch TV display on both → two profile files → independent prefs.
4. Peer receive: land in `peers/inbox` → verify → promote → furnace picks up.
5. Pause the furnace: drain request --wait → optional restart → cancel.
6. Vote then share: overlay OK love / Right like / Down dismiss / Up-Back exit → sidecar `share_candidate` → `share_votes` / cron copies **local** `share-out` → operator copy to inbox (or Phase 5 hop) → receiver `promote --apply`. Tuples skip the overlay.
7. Sweep votes: `sheep_votes sweep` dry-run → `--confirm SWEEP` zeros live-catalog `viewer_feedback`; share-out copies and aliases stay.
8. List top voted: `sheep_votes top` / `top -n 5` ranks live-catalog `votes` (then loves, likes).

### D — Triage cookbook

Symptom-oriented table (extend as lab learns):

| Symptom | Checks | Likely fix |
|---|---|---|
| No new sheep appearing | Worker active? inbox count? gate open? drain off? | Open gate / `worker_drain cancel` / fix worker / seed inbox |
| Gate stuck closed | Status JSON `reason`; VoD open even on Home? | Stop VoD / wait `idle_delay_sec` (**600**). CLI `waiting 15s` is the retry cap ([runbook](../USER_GUIDE_AND_RUNBOOK.md#idle-gate-behavior)) |
| Blank screensaver | Empty `JellyFlam3` registry (SS never configured VoD on this box) | Sideload VoD → save Settings → re-sideload SS; then id dump / Primary+Backdrop |
| VoD **No poster** tiles | No `ImageTags.Primary` (`stills/` JPEGs are ignored) | Images API Primary upload (base64); relaunch VoD |
| Roku SS posters only | No `BackdropImageTags` | `backfill_posters` until `jellyfin_stills` uploaded |
| Kodi SS missing brand-new sheep | Jellyfin shows item, but screensaver has not wrapped the shuffle yet | Wait for a full pass (0.2.9 wrap re-fetch) or exit screensaver / start a new idle session. Same wrap-once contract on VoD 1.0.31 and Roku SS 1.0.9 ([USER_GUIDE flock mix](../USER_GUIDE_AND_RUNBOOK.md#flock-mix-shuffle-wrap)) |
| Playback 404 after quarantine | Client still playing; operator just quarantined/Shears-deleted that sheep | VoD 1.0.29 / Roku SS 1.0.8 / Kodi SS 0.2.7 drop the dead id, re-poll Jellyfin (30s rate limit), and continue. Sideload/install the new packages. Overnight new-sheep refresh is wrap-once (VoD 1.0.31 / SS 1.0.9 / Kodi 0.2.9) |
| Screensaver replaced VoD | One sideload slot | Re-sideload VoD or use private/Store ([04](04_ROKU_PUBLISH.md)) |
| Peering empty | Opt In? Syncthing? trust keys? | Peering README; share-security verify |
| Healthcheck mount fail | USB/NVMe | Phase 2 from-scratch mounts |
| Sheep disk WARN / BAD | `library_disk check`; `df` | `library_disk rotate --apply`; [Activate daily rotate](06_LIBRARY_DISK_ROTATE.md#activate-daily-rotate); Shears for one sheep ([06](06_LIBRARY_DISK_ROTATE.md)) |
| Transcode hammering Pi / several TVs stutter | streamMode / `link_capacity estimate` | Prefer DirectPlay MP4; this lab is WiFi STA (`eth0` DOWN) — stay at/under `N_max` (ops, not a Jellyfin cap) ([07](07_CONCURRENT_CLIENTS.md)) |

### E — Remaining

Vote / like recipes shipped with [08](08_VIEWER_FEEDBACK_LOOP.md) (runbook example 6). Filename vs alias: VoD + Kodi/Roku screensaver `titleMode` ([09](09_SHEEP_NAMING.md)); optional Jellyfin OriginalTitle parked. Fridge card and refactor/Hammer/Kodi triage are in the baseline.

## Guidelines

1. Prefer links into existing guides over duplicating SoT architecture.
2. Every recipe should name **which host** (16a vs living-room Pi) when fleet matters.
3. Triage entries need a verification command, not only advice.
4. End-user guide is **not** Channel Store listing copy ([04](04_ROKU_PUBLISH.md)) and **not** Pi-from-scratch install.

## Non-goals

- Rewriting Phase 1–3 feature specs
- Mesh admin UI ([02](02_MESH_INTRODUCE_SCRIPTING.md) is CLI A/B/C only)
- Video tutorials / marketing site
- Embedding secrets or live lab IPs as canonical examples

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| End-user guide markdown | docs | Tasks + examples + triage |
| Links from README / Phase 4 overview | docs | Discoverability |
| [FRIDGE_CARD.md](../FRIDGE_CARD.md) | docs | Printable Layer 1 cheat sheet (shipped) |

## Exit criteria

- [x] End-user guide published in-repo with tasks, ≥3 worked examples, triage table — [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) + [FRIDGE_CARD.md](../FRIDGE_CARD.md)
- [x] Linked from project README (or docs README) and Phase 4 overview
- [x] Lab smoke: a second operator (or Owner) completes “first evening” example from the guide alone
- [x] Owner OK

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-09-03 | [x] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) · [06_LIBRARY_DISK_ROTATE.md](06_LIBRARY_DISK_ROTATE.md) · [07_CONCURRENT_CLIENTS.md](07_CONCURRENT_CLIENTS.md) · [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md) · [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md) · [`deploy/peering/README.md`](../../deploy/peering/README.md)
