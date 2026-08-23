# 10 — Testing and acceptance

## Boundary

Verification and Phase 1 sign-off — **no new features**.

```bash
python3 -m pytest tests/ -q
# Pi (after deps): cd /opt/jellyflam3-server && python3 -m pytest tests/ -q
```

## Owner gap analysis (2026-07-28) — Phase 1 achievements

**Status:** Phase 1 technical DoD is **met** for the stated product intent (self-hosted flam3 → ffmpeg → Jellyfin → Roku ambient VoD, private-first). **Owner signed off 2026-07-28**, accepting the conscious deferrals and risks below. No blocking engineering gaps remain inside Phase 1 scope.

### What Phase 1 delivered

| Capability | Achieved |
|---|---|
| Pi 5 furnace host | USB SSD flock (`/media/sheep`) + NVMe scratch/state; cooler; SSH; cold reboot recovers worker / idle-gate / Jellyfin |
| Genome → VoD | flam3 + ffmpeg; catalog MP4 **~23 s**, **h264 High**, 1080p; duration band 7–37 s; smoke path |
| Jellyfin library | Sheep library on LAN; API key; Direct Play Path 1 |
| Render worker | systemd `jellyflam3-worker`; CPU capped (3/4 cores); inbox → ingest; quarantine path |
| Idle gate | systemd `jellyflam3-idlegate`; closes on TV Playing (`JellyFlam3` / Roku); delay resume unit-tested |
| Custom Roku channel | Sideload JellyFlam3 **1.0.12**: list, loop play, Back, deep-link ECP, Sessions Playing |
| Ops | `/opt` symlink deploy; backup tarball; healthcheck + perf (FAIL=0) |
| License posture | Free Sheep heuristics; **sidecar SoT**; commercial filter **default off** (private-first) |
| Tests | `24` unit tests passing (incl. idle-gate checkin) |

### Conscious deferrals (not Phase 1 blockers)

| Item | Why deferred |
|---|---|
| Jellyfin Items API `Tags` populated | Private-first: sidecar `*.jellyflam3.json` is SoT; API tags optional polish |
| BrightScript `commercialMode=true` useful filtering | Needs Items Tags; venue use uncommon; leave `false` |
| Skip-if-exists idempotency | Re-run **overwrites** same catalog path (deterministic enough) |
| Channel Store / certification | Explicit Phase 1 non-goal |
| Roku screensaver package | Phase 3 |
| Archive seed random picker (gens 247–165) | Baseline shipped (Phase 2 guide 01) |
| Dynamic duration weighting | Phase 2 guide 06 |
| Sheep Shears / LLM pedigree / edges + watermark / share security / git pedigree sheep | Phase 3 ([../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md), [../phase3/06_GIT_PEDIGREE_SHEEP.md](../phase3/06_GIT_PEDIGREE_SHEEP.md)) |
| Kodi ES screensaver (separate) | Phase 3 ([../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)) |
| Full power-cut “cold” vs soft reboot | Soft reboot validated; sticky throttle cleared |

### Risks Owner should acknowledge

1. **Single-Pi / LAN-only** — no HA; Roku must reach Jellyfin on LAN (no AP isolation).
2. **License heuristics** — archive page beats filename/XML guesses; Gold/Infinidream stay out of feedstock.
3. **Long renders** — still CPU-heavy; idle-gate protects TV playback but overnight jobs need free space + thermal headroom (perf checks OK on current hardware).
4. **Pi git vs GitHub** — keep `/opt/jellyflam3-server` clone pulled when deploying unit/script changes.

### Guide rollup

| Area | Status | Evidence / residual |
|---|---|---|
| 01 Hardware/OS | **PASS** | Sheep USB SSD + NVMe scratch/state; cooler; SSH; reboot recovered |
| 02 Repo/config | **PASS** | Repo on Pi; yaml + secrets local/gitignored; `/opt` → GitHub symlink |
| 03 flam3/ffmpeg | **PASS** | Tools on PATH; smoke; healthcheck OK |
| 04 Jellyfin | **PASS** | Sheep → `/media/sheep/by-generation`; API; Sessions; Path 1 Direct Play |
| 05 Render pipeline | **PASS** | ~23 s h264 High ingested; quarantine dir; overwrite idempotency |
| 06 Idle gate | **PASS** | Playing → `gate=closed`; Roku 1.0.12 NowPlaying |
| 07 License/metadata | **PASS** | Sidecar SoT; commercial filter default off; Items Tags deferred |
| 08 Roku channel | **PASS** | List/play/deep-link/Playing (1.0.12) |
| 09 Runtime/ops | **PASS** | Backup, healthcheck, perf FAIL=0, cold reboot |
| 10 Acceptance | **PASS** | Owner signed 2026-07-28; Phase 1 complete |

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `python3 -m pytest tests/` | test | Phase 1 unit suite / sign-off runner |
| `scripts/healthcheck.sh` | script | Runtime health for acceptance |
| `scripts/smoke_render.sh` | script | Toolchain acceptance smoke |
| `scripts/perf_healthcheck.sh` | script | Perf FAIL=0 acceptance on Pi |
| `scripts/status_report.sh` | script | Ops snapshot during e2e checks |
| `ffprobe` | binary | Catalog duration / codec band proof |

## Checklist

- [x] Unit tests pass (`24 passed` locally 2026-07-28; idle-gate includes checkin cases)
- [x] smoke_render OK (Phase 1 Step 03; tools still healthy on Pi)
- [x] Worker catalog MP4; ffprobe duration in [7,37]; h264 high (`23.000000` / `h264` / `High`)
- [x] Idle-gate e2e (Playing → `gate=closed reason=active_tv_client`; delay resume unit-tested)
- [x] jellyfin-roku Direct Play (Path 1) — Step 04
- [x] BrightScript loop + Back + deep link — Step 08 (build 1.0.12)

## Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Implementer | Auto (technical) | 2026-07-28 | [x] |
| Owner | Project owner | 2026-07-28 | [x] |

Owner accepted the conscious deferrals and risks above. DoD ticked in [00_OVERVIEW.md](00_OVERVIEW.md).

Phase 1 DoD from [00_OVERVIEW.md](00_OVERVIEW.md) satisfied: [x] **Phase 1 complete** (2026-07-28)

### Post–Phase 1 backlog (optional)

1. Harden Jellyfin Items `Tags` write + backfill (only if UI / `commercialMode` needs it).
2. Phase 2 archive seed library / screensaver tracks per `docs/phase2/`.
