# 06 — Sheep library disk check and auto-purge / rotate

## Boundary

Phase 4 synopsis — keep the **on-disk Sheep library** from filling the media mount: periodic **filesystem free-space check**, then **auto-purge / rotate** catalog sheep (and cascaded artifacts) so the furnace can keep ingesting without operator Hammer.

**Status:** Parked. Do not implement until Phase 4 opens.

Complements (does not replace):

- [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) — per-sheep delete cascade (operator-driven)
- [../phase3/07_JELLYFLAM3_HAMMER.md](../phase3/07_JELLYFLAM3_HAMMER.md) — nuclear wipe of local factory state
- Archive `--skip-catalog` (default on) — skip **re-rendering** existing catalog MP4s; this guide **removes** old catalog to reclaim bytes
- [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md) — health / disk notes

Poison-genome quarantine remains a worker/tax concern; this guide is **capacity**, not XML hygiene.

## Intent

| Need | Why |
|---|---|
| **Free-space check** | Detect the media library (and optionally scratch) approaching full **before** encode/ingest fails mid-job |
| **Auto-purge / rotate** | Reclaim space by retiring oldest / least-needed catalog sheep with a **Shears-grade cascade** (MP4, sidecars, stills, Jellyfin item, inbox/done as applicable) |
| **Keep furnace 24×7** | Daily idle-breed + ~10-day archive fill assume room on `/media/sheep`; a full disk stops the pipeline |

## Work items (when Phase 4 opens)

### A — Check

1. Measure free space on `paths.media_library` mount (and optionally `scratch` / `/var/cache/jellyflam3`).
2. Config thresholds: **warn** (healthcheck / log), **stop ingest** (worker preflight), **rotate** (cron or worker hook).
3. Surface in `healthcheck.sh` / `status_report.sh` (bytes free, % used, last rotate).

### B — Rotate policy

1. Default policy sketch: keep **N GiB free** (or % free); purge until under threshold or a **floor** of retained sheep.
2. Candidate order: oldest ingest / LRU play (if Jellyfin last-played is available) / oldest generation — **document and lock** one default; commercial-safe vs NC is a later filter, not a DoD blocker.
3. Never delete the only remaining playable loop if that would empty the living-room flock (configurable floor ≥ 1).
4. Invoke the same cascade as Shears delete (no orphan Jellyfin rows, no leftover stills/posters).
5. Dry-run first; `--apply` / cron apply; log every retired sheep id.

### C — Hook points

1. **Worker preflight** — refuse new render if below stop-ingest threshold (clear error, no half-written job).
2. **Cron** — e.g. `scripts/cron_library_rotate.sh` after archive seed / idle-breed, or a dedicated daily slot.
3. Optional: pause archive seed when rotate cannot free enough space (inbox gate already exists; add a disk gate).

## Guidelines

1. Rotate is **not** Hammer and **not** Shears CLI for humans — it is an automated capacity valve that **reuses** Shears cascade code.
2. Prefer deleting **catalog outputs** the furnace can re-create (archive skip-catalog means a purged sheep may return later as a **new** fetch, not an overwrite).
3. Git pedigree / samples under the repo are **not** rotation targets.
4. Test on a lab Pi with a tiny floor + fake full disk (`--threshold`) before enabling fleet cron.

## Non-goals

- Filling the disk on purpose as a soak test on living-room Pis
- Cross-host “mesh rotate” (each furnace owns its `media_library`)
- Rewriting Jellyfin library vacuum beyond refresh after Shears-style delete
- Using Hammer `--apply` as the rotate implementation

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| Free-space preflight + thresholds | config / pipeline | Warn / stop ingest / trigger rotate |
| Rotate / purge runner (Shears cascade) | pipeline | Retire catalog sheep until free-space floor |
| Cron wrapper + health fields | ops | Unattended capacity valve |
| Guide notes (this file + healthcheck) | docs | Thresholds, floor, dry-run |

## Exit criteria (when Phase 4 opens)

- [ ] Configurable free-space check on the sheep library mount
- [ ] Auto-rotate dry-run + apply reclaims space without orphaning Jellyfin/catalog artifacts
- [ ] Worker refuses new renders when below stop-ingest threshold
- [ ] Health/status shows disk free + last rotate
- [ ] Owner OK

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | _TBD_ | [ ] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) · [../phase3/07_JELLYFLAM3_HAMMER.md](../phase3/07_JELLYFLAM3_HAMMER.md) · [../phase2/01_ARCHIVE_SEED_LIBRARY.md](../phase2/01_ARCHIVE_SEED_LIBRARY.md) · [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md)
