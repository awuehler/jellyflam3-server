# 05 — End-user guide (tasks, examples, triage)

## Boundary

Phase 4 synopsis — author a **household / end-user** guide for day-to-day JellyFlam3 operation: common tasks, worked examples, and problem triage. Audience is the person running one or more Pis + Roku(s), not the Phase 1–3 implementer reading feature guides.

**Status:** Baseline complete (Owner OK 2026-09-03). Day-to-day use: **[../USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md)** (Layer 1 + [worked examples](../USER_GUIDE_AND_RUNBOOK.md#worked-examples) + Layer 2 triage). Fridge card: **[../FRIDGE_CARD.md](../FRIDGE_CARD.md)**. Remaining expansion (vote/rename recipes) waits on [08](08_VIEWER_FEEDBACK_LOOP.md) / [09](09_SHEEP_NAMING.md).

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
| Play on Roku VoD | Settings IDs via `jellyfin_id_dump.py`; launch / deep link notes |
| Enable screensaver | **VoD Settings first** on that Roku (writes `JellyFlam3` registry); then SS zip; Theme → Screensavers; fade/dwell only in SS Settings ([04](04_ROKU_PUBLISH.md)) |
| Extract stills | `python3 -m pipeline.stills --dry-run` / `--limit N` |
| Breed / seed | Manual `pipeline.breed` (mutate / cross / blend / interpolate) or daily `cron_breed_idle.sh` when inbox empty → wait for worker (Phase 2 pedigree); Phase 4 may weight parents by viewer votes ([08](08_VIEWER_FEEDBACK_LOOP.md)) |
| Promote peer share | Opt In status; `promote --apply` gated path (Phase 2/4 peering); Phase 4 share-votes cron may auto-stage liked sheep ([08](08_VIEWER_FEEDBACK_LOOP.md)) |
| Vote / like a sheep | Roku VoD overlay near end of clip (Phase 4 — [08](08_VIEWER_FEEDBACK_LOOP.md)); playback continues; re-votes allowed |
| Rename / alias a sheep | Phase 4 sheep naming ([09](09_SHEEP_NAMING.md)): auto `adjective_surname` or human override; clients may show alias vs filename |
| Delete a sheep | Shears dry-run → apply (Phase 3 / 03) |
| Multi-Roku | Same Jellyfin URL on each TV; `display_profiles list` |
| Update fleet | `git pull` on each Pi; when to restart units |

### C — Worked examples

Shipped in [USER_GUIDE_AND_RUNBOOK.md — Worked examples](../USER_GUIDE_AND_RUNBOOK.md#worked-examples) (Owner OK 2026-09-03):

1. First evening after install: dump IDs → VoD Settings → play one sheep → confirm gate closes → stop play → gate opens.
2. Screensaver evening: sideload SS → Theme select → confirm gate stays open.
3. Two Rokus, one Pi: Fetch TV display on both → two profile files → independent prefs.
4. Peer receive: land in `peers/inbox` → verify → promote → furnace picks up.

### D — Triage cookbook

Symptom-oriented table (extend as lab learns):

| Symptom | Checks | Likely fix |
|---|---|---|
| No new sheep appearing | Worker active? inbox count? gate open? | Open gate / fix worker / seed inbox |
| Gate stuck closed | Jellyfin Sessions; VoD still Playing? | Stop playback; wait `idle_delay_sec` |
| Blank screensaver | Empty `JellyFlam3` registry (SS never configured VoD on this box) | Sideload VoD → save Settings → re-sideload SS; then id dump / Primaries |
| Kodi SS missing brand-new sheep | Jellyfin shows item, but **same** screensaver session still running | Exit screensaver / start a new idle session (flock is fetched once per run). Phase 4 polish: long-interval re-fetch ([00](00_OVERVIEW.md#client-polish-parked--not-numbered)) |
| Screensaver replaced VoD | One sideload slot | Re-sideload VoD or use private/Store ([04](04_ROKU_PUBLISH.md)) |
| Peering empty | Opt In? Syncthing? trust keys? | Peering README; share-security verify |
| Healthcheck mount fail | USB/NVMe | Phase 2 from-scratch mounts |
| Sheep disk WARN / BAD | `library_disk check`; `df` | Shears delete (no auto-rotate yet) ([06](06_LIBRARY_DISK_ROTATE.md)) |
| Transcode hammering Pi / several TVs stutter | streamMode / `link_capacity estimate` | Prefer DirectPlay MP4; Ethernet for WiFi STA Pi; stay at/under N_max ([07](07_CONCURRENT_CLIENTS.md)) |

### E — Remaining (waits on 08 / 09)

Vote / like and rename / alias recipes in the user guide when [08](08_VIEWER_FEEDBACK_LOOP.md) / [09](09_SHEEP_NAMING.md) ship. Fridge card and refactor/Hammer/Kodi triage are already in the baseline.

## Guidelines

1. Prefer links into existing guides over duplicating SoT architecture.
2. Every recipe should name **which host** (16a vs living-room Pi) when fleet matters.
3. Triage entries need a verification command, not only advice.
4. End-user guide is **not** Channel Store listing copy ([04](04_ROKU_PUBLISH.md)) and **not** Pi-from-scratch install.

## Non-goals

- Rewriting Phase 1–3 feature specs
- Full Syncthing mesh introduce automation ([02](02_MESH_INTRODUCE_SCRIPTING.md))
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
