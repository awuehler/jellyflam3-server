# 10 — Testing, acceptance, and release candidate

## Boundary

Verification, Phase 3 sign-off, and **release candidate (RC)** packaging — **no new features**. Run only after guides **01–09** exit criteria that are in-scope for this release are met (or consciously deferred with Owner note).

```bash
python3 -m pytest tests/ -q
# Pi: cd /opt/jellyflam3-server && python3 -m pytest tests/ -q
# Pi deps: sudo apt install -y python3-pytest python3-yaml  (PEP 668 blocks pip --user on Pi OS)
./scripts/healthcheck.sh
./scripts/status_report.sh
./scripts/smoke_render.sh configs/jellyflam3.yaml   # pedigree smoke seed
```

## Automated test pyramid

| Layer | Where | Role |
|---|---|---|
| **Unit / fast** | `python3 -m pytest tests/ -q` (~3s) | Happy + negative paths; tmp_path fixtures; no live Jellyfin/flam3 |
| **Integration / edge** | Same suite (HTTP sink, package zips, gate exit contracts) | Boundary regressions; `media_layout` POSIX modes run on Linux CI only |
| **Smoke / e2e** | Pi / lab scripts (not pytest) | Real furnace, HLS, fleet share matrix |

**CI:** `.github/workflows/tests.yml` runs pytest + `ensure_exec_bits.sh --check` on every push/PR (Ubuntu). Optional `smoke-render` job runs `scripts/smoke_render.sh` only when `flam3-genome` and `ffmpeg` are on the runner (typically **skip** on GitHub-hosted; run on a furnace Pi for `SMOKE_RENDER_OK`).

**Fleet pytest deps:** On Raspberry Pi OS, install **`python3-pytest`** (and **`python3-yaml`**) via **`apt`** — `pip install -r requirements.txt --user` is blocked by PEP 668. Bring-up: [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md) step 3.

**Owner-OK gates (manual, not CI):**

| Gate | Command | Notes |
|---|---|---|
| Pedigree furnace smoke | `./scripts/smoke_render.sh` | Never publishes to catalog; exit ≠0 on missing tools |
| HLS stream smoke | `./scripts/hls_smoke.sh` | Live Jellyfin + secrets; auto-picks first flock item via `jellyfin_id_dump --smoke-item-id` (folder-aware) |
| Share security fleet | `powershell -File scripts/lab_smoke05_fleet.ps1` | 3-Pi × pathways A–D; exit 1 on any FAIL; unit coverage in `tests/test_peering.py` |
| Fleet health | `./scripts/healthcheck.sh` | Per-Pi RC sample |

**Status:** **Complete** — Owner OK 2026-08-23. Public launch **`v0.3.0`** (2026-08-23); post-launch maintenance **`v0.3.1`** — see [CHANGELOG.md](../../CHANGELOG.md).

## Acceptance run log

| Check | Result |
|---|---|
| Local `pytest tests/ -q` | **OK** 2026-08-23 — **303 passed**, 1 skipped @ `2fca790` (Linux CI); **299**+5 skip Windows |
| Fleet pytest (`16a` / `08a` / `04a`) | **OK** 2026-08-22 — 284 passed, 1 skipped each @ `c14bdb4` (~6s); `python3-pytest` via apt |
| Fleet `healthcheck.sh` | **OK** 2026-08-22 — exit 0 on 16a / 08a / 04a @ `b7e81ea`; post-launch fleet @ `2fca790` |
| Pedigree smoke (`SMOKE_RENDER_OK`) | **OK** 2026-08-23 — `04a` idle furnace @ `97be7e2` (`SMOKE_RENDER_OK`, ~5 min; scratch under `/var/cache/jellyflam3/smoke`) |
| Open regression (Step 10 checklist) | **OK** 2026-08-23 — `04a` automated + Owner OK: idle-gate open/closed (HLS active → gate closed), ambient MP4 loop acceptable on lab Roku |
| Guide 06 Owner OK | **OK** 2026-08-14 |
| Guide 08 lab dump + Roku Settings paste | **OK** 2026-08-14 (fleet; flock in Jellyfin + Roku) |
| Guide 02 Kodi ES screensaver (loops-only) | **OK** 2026-08-21 (loop→edge→loop post-launch) |
| Guide 09 Sheep refactor | **OK** 2026-08-21 — pathways A / P / B / C / D + sidecar history; 16a lab smoke |
| Guide 10 Owner OK (Step 10 / Phase 3 closeout) | **OK** 2026-08-23 — regression + feature checklists; SoT synced; `v0.3.0` at public launch |
| Other Phase 3 guides in this RC | 01–10 complete; guide 04 (edges) post-launch |

## Guide rollup

| Guide | Status | Notes |
|---|---|---|
| 01 Roku stills / Screensaver | **Complete** | Owner OK 2026-08-16 — [01](01_SCREENSAVERS_AND_STILLS.md) |
| 02 Kodi ES screensaver | **Complete** | Owner OK 2026-08-21 — loops-only; loop→edge→loop post-launch — [02](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) |
| 03 Sheep Shears | **Complete** | Owner OK 2026-08-16 — [03](03_SHEEP_SHEARS.md) |
| 04 Edges + watermark | **Post-launch** | Not in v0.3.0 |
| 05 Shared sheep security | **Complete** | Owner OK 2026-08-16 — [05](05_SHARED_SHEEP_SECURITY.md) |
| 06 Git pedigree sheep | **Complete** | Owner OK 2026-08-14 — [06](06_GIT_PEDIGREE_SHEEP.md) |
| 07 JellyFlam3 Hammer | **Complete** | Owner OK 2026-08-17 — 04a lab dry-run + apply — [07](07_JELLYFLAM3_HAMMER.md) |
| 08 Jellyfin ID dump | **Complete** | Owner OK 2026-08-14 — [08](08_JELLYFIN_ID_DUMP.md) |
| 09 Sheep refactor | **Complete** | Owner OK 2026-08-21 — pathways A / P / B / C / D + sidecar history; 16a lab — [09](09_SHEEP_REFACTOR.md) |
| 10 Testing / acceptance / RC | **Complete** | Owner OK 2026-08-23; public launch `v0.3.0`; maintenance `v0.3.1` |

Update statuses as each guide ships; RC may ship a **subset** of 01–09 if Owner defers the rest to a later RC.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `python3 -m pytest tests/` | test | Unit suite / sign-off runner |
| `scripts/healthcheck.sh` | script | Runtime health |
| `scripts/status_report.sh` | script | Flock / inbox / thermals snapshot |
| `scripts/smoke_render.sh` | script | Pedigree smoke (never publish) |
| `scripts/hls_smoke.sh` | script | HLS remux regression |
| `scripts/jellyfin_id_dump.py` | script | Guide 08 Settings helper |
| `scripts/client_pack_presets.py` | script | Pre-fill Roku/Kodi zips from furnace `secrets.env` (guide 08) |
| `scripts/package_roku_channel.{sh,ps1}` | script | Channel build for RC sideload |
| `scripts/package_roku_screensaver.{sh,ps1}` | script | Roku Screensaver zip (guide 01) |
| `scripts/package_kodi_screensaver.{sh,ps1}` | script | Kodi screensaver zip (guide 02) |
| `scripts/cron_archive_seed.sh` / `cron_breed_idle.sh` | script | Scheduled feedstock; both prepend `/usr/local/bin` for flam3 |
| `tests/test_ops_scripts.py` | test | Script/doc crontab + PATH + skip-catalog contracts |
| `tests/test_gate_script_exits.py` | test | Gate exit contracts (healthcheck queue, bringup FAIL/STRICT, smoke without flam3) |
| `tests/test_tool_lookup.py` | test | Shared `pipeline.tool_lookup.tool` resolver |
| `tests/test_refactor_modules.py` | test | Direct imports for split refactor pathway modules |
| `.github/workflows/tests.yml` | CI | Pytest + exec bits on push/PR; optional smoke_render when tools present |
| `tests/test_config.py` | test | YAML load, `${ENV}` expand, path resolve |
| `tests/test_roku_packages.py` | test | Roku VoD + Screensaver zip layout |
| `tests/test_display_profile_sink.py` | test | LAN `/healthz` + token upsert |
| `CONTRIBUTING.md` / `SECURITY.md` / `CHANGELOG.md` | docs | OSS housekeeping; `v0.3.0` release notes draft |
| `docs/media/demo/electricsheep.242.03322-poster.jpg` | media | README / release demo still (CC BY; from 04a catalog) |
| Git tag / GitHub Release | release | **`v0.3.0`** — [CHANGELOG.md](../../CHANGELOG.md); client zips attached |

## Regression checklist (Phase 1–2 must stay green)

- [x] Unit tests pass (local + CI on Ubuntu; at least one lab Pi for fleet parity) — **OK** 2026-08-23 (`2fca790`: Linux CI **303**+1 skip; fleet 16a/08a/04a 284+1 skip @ `c14bdb4`)
- [x] `healthcheck.sh` exit 0 on fleet sample (`16a` / `08a` / `04a` as available); flam3 on PATH (`/usr/local/bin`) — **OK** 2026-08-22 (`b7e81ea`: all three exit 0; Opt In + `share_live` on lab fleet)
- [x] Idle-gate open when idle; closes on active HLS / JellyFlam3 playback — **OK** 2026-08-23 (`04a`: open when idle; Owner OK gate **closed** with active HLS stream connected to furnace Pi)
- [x] Worker can still furnace a pedigree smoke or inbox genome — **OK** 2026-08-23 (`04a`: `jellyflam3-worker` active; `./scripts/smoke_render.sh` → `SMOKE_RENDER_OK`)
- [x] Daily idle-breed + ~10-day archive cron still skip/run as designed (`--skip-catalog` default on) — **OK** 2026-08-23 (`04a`: crontab `cron_breed_idle` + `cron_archive_seed`; `--dry-run` → `action=breed`, archive `fetch_count=5`)
- [x] Jellyfin Sheep library + Path 1 / JellyFlam3 flock list still works — **OK** 2026-08-23 (`04a`: `jellyfin_id_dump` Sheep `libraryId`; flock items e.g. gen 242)
- [x] Peering: Opt In status + Syncthing mesh (or documented Opt Out lab) — **OK** 2026-08-23 (`04a`: `share_opt_in` + `share_live`; Syncthing + Tailscale Running)
- [x] HLS smoke and ambient MP4 loop acceptable on lab Roku — **OK** 2026-08-23 (`04a`: `./scripts/hls_smoke.sh` → `SMOKE_OK`; Owner OK ambient MP4 loop on lab Roku)
- [x] Sideload zips build: Roku VoD, Roku Screensaver, Kodi screensaver (Kodi chrome still needs a live TV) — **OK** 2026-08-22 (fleet `16a` / `08a` / `04a`; furnace builds include Jellyfin presets via `client_pack_presets.py`; Kodi needs Pillow via `pip install -r requirements.txt` or `python3-pil`)

## Phase 3 feature checklist

Tick only what this RC includes:

- [x] 01 Stills + Roku Screensaver / Backdrop exit met (Owner OK 2026-08-16)
- [x] 02 Kodi ES screensaver exit met (Owner OK 2026-08-21; loop→edge→loop post-launch)
- [x] 03 Shears exit met (Owner OK 2026-08-16)
- [x] 04 Edges + watermark — **post-launch** (not v0.3.0)
- [x] 05 Share security exit met (or deferred)
- [x] 06 Git pedigree Owner OK (2026-08-14)
- [x] 07 Hammer exit met (Owner OK 2026-08-17)
- [x] 08 Jellyfin ID dump exit met (Owner OK 2026-08-14)
- [x] 09 Sheep refactor exit met (Owner OK 2026-08-21)
- [x] Architecture SoT + `docs/phase3/00_OVERVIEW.md` labels match shipped set — **OK** 2026-08-23 (`Pi5_Flam3_VoD_Pipeline.md`, `docs/README.md`, `glossary.md`)
- [x] Peer share-path / mesh scripting revisits post-launch (not v0.3.0 RC scope)

## Release candidate

### RC definition

A Phase 3 **release candidate** is a git revision that:

1. Passes the regression checklist above
2. Passes the Phase 3 feature checklist for the **declared RC scope**
3. Is tagged and published as GitHub release **`v0.3.0`** at public launch (Owner OK 2026-08-23)

### RC procedure

```bash
# 1) Clean tree on master (or release branch); fleet pulled to tip
git status -sb
git log -1 --oneline

# 2) Acceptance run — fill “Acceptance run log” + checklists above

# 3) Tag at public launch (v0.3.0)
# git tag -a v0.3.0 -m "Phase 3 — guides 01–09 + acceptance"
# git push origin v0.3.0

# 4) GitHub release (not prerelease)
# gh release create v0.3.0 --title "v0.3.0" --notes-file CHANGELOG.md

# 5) Pi pull (all) to the tagged tip; re-run healthcheck
```

### RC exit criteria

- [ ] Tag pushed; notes list **in** / **post-launch** items — apply at public launch (`v0.3.0`; [CHANGELOG.md](../../CHANGELOG.md))
- [x] Fleet on release tip — **OK** 2026-08-23 (`16a` / `08a` / `04a` @ `2fca790`; tag `v0.3.1` when applied)
- [x] Owner OK on sign-off table below — **OK** 2026-08-23
- [x] No secrets in release notes or committed dumps (`--show-secrets` output)

## Conscious deferrals (post-launch)

| Item | Notes |
|---|---|
| LLM-assisted pedigree | Beyond flam3-genome tooling |
| DeepDream / AI backends | Aspirational |
| Channel Store / Roku publish (VoD + screensaver) | Post-launch |
| Sheep library disk rotate | Post-launch |
| Concurrent clients / link capacity | Estimator shipped 2026-09-03 (`pipeline.link_capacity`); Owner OK pending |
| Full social flock network | Aspirational |
| Continuous / live HLS from shuffled MP4s | Dropped |
| Peer share path + mesh introduce scripting | Post-launch |
| Edges + watermark | Post-launch |

## Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Implementer | — | — | [ ] (optional) |
| Owner | Project owner | 2026-08-23 | [x] |

Phase 3 DoD from [00_OVERVIEW.md](00_OVERVIEW.md) satisfied for this RC scope: [x]

**RC id:** tag **`v0.3.1`** (public launch `v0.3.0` 2026-08-23)

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [../phase2/10_TESTING_AND_ACCEPTANCE.md](../phase2/10_TESTING_AND_ACCEPTANCE.md) · [../phase1/10_TESTING_AND_ACCEPTANCE.md](../phase1/10_TESTING_AND_ACCEPTANCE.md) · [Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md)
