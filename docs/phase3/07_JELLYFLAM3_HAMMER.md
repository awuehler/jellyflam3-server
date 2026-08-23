# 07 — JellyFlam3 Hammer

## Boundary

Phase 3 guide 07 — **nuclear local reset** of render history and furnace I/O on one JellyFlam3 host.

Distinct from [Sheep Shears](03_SHEEP_SHEARS.md) (per-sheep add/modify/delete + cascade). Hammer is **factory-reset the local flock factory**, not surgical cull.

**Status:** **Complete** — Owner OK 2026-08-17 (lab dry-run + `--all` apply on `rpi-jellyflam3-04a`; post-reboot healthcheck exit 0).

## Intent

Give operators a single, guarded tool to:

1. **Purge existing history** — worker/job logs, idle-gate status, recover/orphan state, and other local run history under the JellyFlam3 data dirs  
2. **Reset the local worker environment** — stop the worker cleanly; clear job dirs and frame scratch so the next start is a cold boot  
3. **Remove any/all existing rendering input and output** — inbox / quarantine genomes staged for render, and catalog masters (MP4, posters, sidecars) under the media library

After Hammer, the host can re-seed (archive / pedigree / peers) and rebuild the flock from empty queues.

## Locked decisions

1. **Local host only** — does not revoke Tailscale, wipe Syncthing device config, or push deletes to Opt-In peers (peer copies are out of scope unless a later “remote hammer” is specified).  
2. **Never touch** `secrets.env`, `configs/jellyflam3.yaml`, API keys, git checkout, OS packages, `genomes/samples/`, `genomes/pedigree/`, `configs/templates/`, `display_profiles/`, or backups.  
3. **Dry-run first** — always list paths + approximate sizes; require `--confirm HAMMER` (or this hostname) before delete.  
4. **Stop before smash** — stop `jellyflam3-worker` before deleting job/frame trees. Refuse apply while the unit is active unless `--force-stop` succeeded. Do not pkill Jellyfin’s ffmpeg.  
5. **Jellyfin** — empty on-disk library content under `media_library` (`by-generation/`); then trigger `Library/Refresh` (do not uninstall Jellyfin).  
6. **Shears remains** the tool for deleting one sheep; Hammer is all-or-nothing (or scoped tiers below).

## Commands

```bash
cd /opt/jellyflam3-server

# Always dry-run first (default if no --confirm)
python3 -m pipeline.hammer --dry-run
python3 -m pipeline.hammer --json            # plan as JSON
python3 -m pipeline.hammer --worker          # jobs/frames/logs only (still dry-run)
python3 -m pipeline.hammer --inputs
python3 -m pipeline.hammer --outputs

# Apply (destructive) — worker must be stopped or pass --force-stop
python3 -m pipeline.hammer --worker --force-stop --confirm HAMMER
python3 -m pipeline.hammer --all --force-stop --confirm HAMMER
python3 -m pipeline.hammer --all --peers-inbox --force-stop --confirm HAMMER
```

Confirm token is `HAMMER` or this host’s hostname. Wrong token → exit 2, no deletes.

## Purge map (lab defaults from config)

| Class | Typical paths | Hammer action |
|---|---|---|
| **Render input** | `genomes/inbox`, `genomes/quarantine` | Delete contents (keep empty dirs + `.gitkeep`) |
| **Peer land (local)** | `genomes/peers/inbox` | Optional `--peers-inbox` — local staging only; keep `.stignore` / `OPT_IN` |
| **Worker / jobs** | `paths.jobs_dir` → `/var/lib/jellyflam3/jobs` | Delete job trees |
| **Frame scratch** | `paths.frames_scratch` → `/var/cache/jellyflam3/frames` | Delete |
| **HLS/transcode cache** | `/var/cache/jellyflam3/transcodes`, `live-hls/` | `--all` if present, or `--transcode-cache` |
| **Render output** | `paths.media_library` → `/media/sheep/by-generation/` | Delete flock tree (keep mount root); recreate `by-generation/` |
| **Done archive** | `paths.genomes_done` | Empty on `--outputs` / `--all` (not git samples) |
| **History / state** | `paths.log_dir`, `paths.status_file` | Truncate/delete; rewrite idle-gate `gate=open` reason `hammer` |
| **Jellyfin DB items** | Sheep library Items pointing at removed files | `Library/Refresh` after disk wipe |

### Tiers

| Tier | Flag | Scope |
|---|---|---|
| **1** | `--worker` | Jobs + frames + logs/status (keep inbox + media) |
| **2** | `--inputs` | Tier 1 + inbox/quarantine (+ optional `--peers-inbox`) |
| **3** | `--outputs` | Tier 1 + `genomes/done` + media flock + Jellyfin refresh |
| **4** | `--all` (default plan) | Inputs + outputs + optional transcode cache |

`--all` is the default plan when no tier flag is passed. Apply still requires `--confirm`.

## Work items (implementation)

1. ~~**CLI + plan**~~ — `pipeline/hammer.py`; dry-run path/size report; `--json`
2. ~~**Confirm gate**~~ — `--confirm HAMMER` / hostname; `--force-stop` if worker active
3. ~~**Tiers**~~ — `--worker` / `--inputs` / `--outputs` / `--all`
4. ~~**Unit tests**~~ — `tests/test_hammer.py`
5. **Lab dry-run** — `--dry-run --all --json` on a Pi (prefer `04a`)
6. **Lab apply** — Owner-gated `--all` or `--worker` on one host; verify secrets/git/Syncthing intact
7. **Docs / Owner OK** — runbook + sign-off

## Guidelines

- CLI first: `python -m pipeline.hammer --dry-run` / `--confirm HAMMER`.
- Refuse to run if worker unit is still active unless `--force-stop` succeeded.
- Print a short post-Hammer checklist: start worker, seed inbox, library scan, healthcheck / channel play.
- Archive feedstock caches and in-repo sample/template trees are **not** deleted.
- Name in UX/docs: **JellyFlam3 Hammer** (destructive; no soft synonym that sounds like Shears).

## Operator runbook

1. `./scripts/healthcheck.sh` and `python3 -m pipeline.hammer --dry-run --json` — review path list.
2. Stop playback / wait for idle-gate if you care about TV (Hammer does not wait on the gate).
3. `python3 -m pipeline.hammer --all --force-stop --confirm HAMMER`
4. `sudo systemctl start jellyflam3-worker`
5. Re-seed: `python3 -m pipeline.seed_inbox` and/or `python3 -m pipeline.shears add …`
6. Confirm Jellyfin scan; play or `./scripts/healthcheck.sh`

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/hammer.py` (`python -m pipeline.hammer`) | pipeline | Nuclear local reset CLI |
| Tier flags (`--worker` / `--inputs` / `--outputs` / `--all`) | CLI | Scoped smash vs full Hammer |
| Dry-run path/size report | ops | Lists every purge class before delete |
| Confirm gate (`--confirm HAMMER` / hostname) | ops | Blocks accidental runs |
| Post-Hammer checklist (start → seed → scan → smoke) | docs | Operator runbook after wipe |
| Untouched: `secrets.env`, config, git, Tailscale/Syncthing identity | boundary | Never deleted by Hammer |

## Exit criteria

- [x] Dry-run lists every path class above with counts/sizes  
- [x] Confirm gate blocks accidental runs  
- [x] `--all` leaves worker able to cold-start; inbox empty; media flock empty; Jellyfin library scan shows no orphan sheep (04a lab 2026-08-17)
- [x] Secrets, config, git, Tailscale/Syncthing device identity intact (code + unit tests)  
- [x] Documented distinction from Sheep Shears  
- [x] Operator runbook: stop → hammer → re-seed → verify  
- [x] Lab smoke + Owner OK (04a 2026-08-17)

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-17 | [x] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [03_SHEEP_SHEARS.md](03_SHEEP_SHEARS.md) · [09_SHEEP_REFACTOR.md](09_SHEEP_REFACTOR.md) (per-sheep quality — not wipe) · Phase 1 [05_RENDER_PIPELINE.md](../phase1/05_RENDER_PIPELINE.md) · Phase 1 [09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md)
