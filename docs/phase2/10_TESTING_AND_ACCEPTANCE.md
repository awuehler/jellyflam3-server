# 10 — Testing and acceptance

## Boundary

Verification and Phase 2 sign-off — **no new features**. **Started 2026-08-08.**

```bash
python3 -m pytest tests/ -q
# Pi: cd /opt/jellyflam3-server && python3 -m pytest tests/ -q
./scripts/healthcheck.sh
./scripts/status_report.sh
```

### Acceptance run log (2026-08-08)

| Check | Result |
|---|---|
| Local `pytest tests/ -q` | **151 passed**, 3 skipped |
| `rpi-jellyflam3-16a` pytest | **154 passed**; healthcheck exit 0; gate open; catalog 11 MP4 |
| `rpi-jellyflam3-08a` pytest | **154 passed**; healthcheck exit 0; gate open; catalog 1 MP4 |
| Guide 05 fixture promote | **OK** on 08a (tax + stage; cleaned after) |
| Guide 08 Pi duration | **OK** on 08a — 27.708 s dynamic + period snap in sidecar |

## Guide rollup

| Guide | Status | Notes |
|---|---|---|
| 01 Archive seed | **Complete** | Baseline verified on Pi (Owner OK 2026-07-30); optional denylist/timer deferred |
| 02 Jellyfin flock UX | **Complete** | Primary posters confirmed web + jellyfin-roku + JellyFlam3 + FS (Owner OK 2026-07-31) |
| 03 HLS client streaming | **Complete** | Owner OK 2026-08-01 (A–H) |
| 04 Roku channel polish | **Complete** | Owner OK 2026-08-02 (A–F; 1.0.23; two live Roku display profiles) |
| 05 Syncthing peering | **Complete** | Owner OK 2026-08-08 — fixture promote + tax; **3-Pi mesh** land + promote 2026-08-11 |
| 06 Sheep tax | **Complete** | `pipeline.sheep_tax`; archive / promote / worker wired; tests green |
| 07 Pedigree breeding | **Complete** | Owner OK 2026-08-04 (CLI + Pi smoke / verify) |
| 08 Dynamic duration | **Complete** | Owner OK 2026-08-08 — Pi verify on 08a (`electricsheep.247.47501` 27.708 s, period snap) |
| 09 Pi from scratch | **Complete** | Owner OK 2026-08-08 — 2nd system `rpi-jellyflam3-08a` (units, first sheep+poster, Opt Out, `hw_profile`) |
| 10 Acceptance | **Complete** | Owner OK 2026-08-08 — Phase 2 DoD signed |

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `python3 -m pytest tests/` | test | Phase 2 unit suite / sign-off runner |
| `scripts/healthcheck.sh` | script | Runtime health for acceptance |
| `scripts/status_report.sh` | script | Flock / inbox / thermals snapshot for DoD |
| `scripts/hls_smoke.sh` | script | HLS remux acceptance path |
| `scripts/perf_healthcheck.sh` | script | Optional Pi perf FAIL check |
| `pipeline/hw_profile.py` | pipeline | Preset / dry-run verify for guide 09 |

## Checklist

- [x] Unit tests pass (including new Phase 2 modules) — local 151 passed / 3 skipped; 16a+08a 154 passed (2026-08-08)
- [x] Archive `--archive --fetch-count 1` still works
- [x] New ingest / catalog shows Primary in Jellyfin web + jellyfin-roku (+ JellyFlam3)
- [x] Lab HLS remux path verified (`main.m3u8` + `AudioCodec=aac`; Direct Stream; see [03](03_HLS_CLIENT_STREAMING.md) retest log) — owner VLC UI optional
- [x] JellyFlam3 channel HLS remux path (`main.m3u8` + `AudioCodec=aac`, build 1.0.13+) — Owner OK 2026-08-01
- [x] Ambient loop policy: MP4 + seek-reloop (build 1.0.15+) — Owner OK 2026-08-01 (MP4 hitch shorter than HLS); gapless → Phase 4 edges
- [x] jellyfin-roku Path 1 smoke OK — Owner OK 2026-08-01 (long HLS `.ts` WRNs = known limitation; see [03](03_HLS_CLIENT_STREAMING.md#known-limitation-long-running-hls-vod-sessions))
- [x] JellyFlam3 sideload: posters, metadata, TV settings fetch + per-screen Pi sink — Owner OK 2026-08-02 (1.0.23; two Roku profiles)
- [x] Peering docs: Opt Out default; host-service Opt In/Out; sync `*.flam3` + optional `*-poster.jpg`; land in `peers/inbox` then gated promote (not auto worker pickup); **3-Pi mesh** smoked 2026-08-11 ([05](05_SYNCTHING_GENOME_PEERING.md)) — Owner OK 2026-08-08
- [x] Sheep tax scan/repair + fixtures/tests ([06](06_SHEEP_TAX.md))
- [x] Breed mutate + cross → `electricsheep.pedigree.*` inbox genomes + sidecar (`origin: local_pedigree`); Pi `--once` smoke ([07](07_PEDIGREE_BREEDING.md)) — Owner OK 2026-08-04
- [x] Dynamic duration respects hard max 120 s; period-aware loop snap; tests cover bypass ([08](08_DYNAMIC_DURATION.md)) — Owner OK 2026-08-08 (Pi verify)
- [x] Pi-from-scratch guide reviewed against a real 2nd system ([09](09_PI_FROM_SCRATCH.md); `rpi-jellyflam3-08a`; `hw_profile` apply) — Owner OK 2026-08-08
- [x] Architecture SoT phase labels still match [00_OVERVIEW.md](00_OVERVIEW.md) — Phase 2 **complete** (Owner OK 2026-08-08)

## Conscious deferrals (Phase 3)

| Item | Notes |
|---|---|
| Roku Screensaver / Backdrop | Stills + `RunScreenSaver` — [../phase3/01_SCREENSAVERS_AND_STILLS.md](../phase3/01_SCREENSAVERS_AND_STILLS.md) |
| Kodi ES screensaver | Separate add-on; Electric Sheep dogma (loops-only in Phase 3; loop→edge→loop → Phase 4) — [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) |
| LLM-assisted pedigree | On top of flam3-genome tooling |
| Sheep Shears | CRUD `.flam3` + downstream cascade — [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) |
| Edge crossfades + sheep watermark | [../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md) |
| Sheep refactor | Scan/score/repair sub-standard sheep (palette report/override, Jellyfin `_refactor-preview`, encode) — [../phase3/09_SHEEP_REFACTOR.md](../phase3/09_SHEEP_REFACTOR.md) |
| Shared sheep security | [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md) |
| Git pedigree sheep | Smoke/examples flock in git; collapse dual samples + replace demo/archive seeds — [../phase3/06_GIT_PEDIGREE_SHEEP.md](../phase3/06_GIT_PEDIGREE_SHEEP.md) |
| JellyFlam3 Hammer | Purge history / reset worker / wipe render I/O — [../phase3/07_JELLYFLAM3_HAMMER.md](../phase3/07_JELLYFLAM3_HAMMER.md) |

## Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Implementer | Auto (acceptance run) | 2026-08-08 | [x] |
| Owner | Project owner | 2026-08-08 | [x] |

Phase 2 DoD from [00_OVERVIEW.md](00_OVERVIEW.md) satisfied: [x]

**Phase 2 complete** (Owner OK 2026-08-08). Next: [../phase3/00_OVERVIEW.md](../phase3/00_OVERVIEW.md).

## See also

[../phase1/10_TESTING_AND_ACCEPTANCE.md](../phase1/10_TESTING_AND_ACCEPTANCE.md) · [../phase3/00_OVERVIEW.md](../phase3/00_OVERVIEW.md)
