# 06 — Sheep library disk check and auto-purge / rotate

## Boundary

Keep the **on-disk Sheep library** from filling the media mount: periodic **filesystem free-space check**, then (later) **auto-purge / rotate** catalog sheep with a Shears-grade cascade.

**Status:** Check **slice shipped** 2026-09-03 (healthcheck WARN/BAD). Auto-purge, worker refuse, and rotate cron stay **parked**.

Complements (does not replace):

- [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) — per-sheep delete cascade (operator-driven)
- [../phase3/07_JELLYFLAM3_HAMMER.md](../phase3/07_JELLYFLAM3_HAMMER.md) — nuclear wipe of local factory state
- Archive `--skip-catalog` (default on) — skip **re-rendering** existing catalog MP4s; rotate **removes** old catalog to reclaim bytes
- [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md) — health / disk notes

Poison-genome quarantine remains a worker/tax concern; this guide is **capacity**, not XML hygiene.

## Intent

| Need | Why |
|---|---|
| **Free-space check** | Detect the media library (and optionally scratch) approaching full **before** encode/ingest fails mid-job |
| **Auto-purge / rotate** | Reclaim space by retiring oldest catalog sheep with a **Shears-grade cascade** — **not this slice** |
| **Keep furnace 24×7** | Daily idle-breed + ~10-day archive fill assume room on `/media/sheep` |

## Slice (shipped) vs parked

| Piece | State |
|---|---|
| Measure free space on `paths.media_library` (+ scratch if another device) | **Shipped** — `python3 -m pipeline.library_disk check` |
| Config warn / bad thresholds | **Shipped** — `library_disk.*` |
| `healthcheck.sh` WARN (exit 0) / BAD (exit 1) | **Shipped** |
| `status_report.sh` bytes / % / level | **Shipped** |
| Worker refuse new renders | **Parked** — scratch floor remains `render.free_space_gb_min` only |
| Auto-rotate / cron / Shears cascade | **Parked** |

## Work items

### A — Check (shipped)

```bash
cd /opt/jellyflam3-server
python3 -m pipeline.library_disk check
python3 -m pipeline.library_disk check --json
./scripts/healthcheck.sh          # WARN does not fail; BAD does
./scripts/status_report.sh        # == library disk ==
```

Thresholds (`configs/jellyflam3.yaml.example`):

| Knob | Default | Meaning |
|---|---:|---|
| `warn_used_pct` | 80 | WARN when used % ≥ this |
| `bad_used_pct` | 95 | BAD (healthcheck exit 1) when used % ≥ this |
| `warn_free_gb` | 16 | WARN when free GiB below this |
| `bad_free_gb` | 4 | BAD when free GiB below this |
| `check_scratch` | true | Also check `frames_scratch` if it is a **different** device |

Python `shutil.disk_usage` (same as status_report) — not `df` Use% (reserved blocks differ).

Worker encode preflight is still **scratch-only** (`render.free_space_gb_min`, 8 GiB / 4 GiB on `-04`). This slice does **not** stop ingest on a full sheep disk.

### B — Rotate policy (paper; not implemented)

When Phase 4 opens rotate:

1. Keep **N GiB free** (or drop below warn); purge until under threshold or a **floor** of retained sheep.
2. **Default candidate order (locked on paper):** oldest catalog MP4 **mtime** (ingest age). LRU last-played and oldest-generation are later options; commercial-safe vs NC is a filter, not a DoD blocker.
3. Never delete the only remaining playable loop (**floor ≥ 1**).
4. Same cascade as Shears delete (no orphan Jellyfin rows, no leftover stills/posters).
5. Dry-run first; `--apply` / cron apply; log every retired sheep id.

### C — Hook points (parked)

1. Worker preflight on the **sheep** mount (clear error, no half-written job).
2. `scripts/cron_library_rotate.sh` after archive seed / idle-breed.
3. Pause archive seed when rotate cannot free enough space.

## Lab (2026-09-03)

All three furnaces **OK** (far below warn). Sheep is a separate USB/SATA volume; cache+lib share NVMe.

| Host | Sheep total | Sheep used | Sheep free | Scratch used |
|---|---:|---:|---:|---:|
| 16a | 879.1 G | 0.2 G (0.0%) | 834.2 G | 0.4% of 916 G |
| 08a | 439.0 G | 0.2 G (0.1%) | 416.4 G | 0.2% of 468 G |
| 04a | 219.0 G | 0.1 G (0.0%) | 207.7 G | 0.3% of 234 G |

No BAD/WARN in lab. Do not fill living-room disks as a soak test.

## Guidelines

1. Rotate (when built) is **not** Hammer and **not** the human Shears CLI — an automated valve that **reuses** Shears cascade code.
2. Prefer deleting **catalog outputs** the furnace can re-create.
3. Git pedigree / samples under the repo are **not** rotation targets.
4. Test rotate on a lab Pi with a tiny floor + fake threshold before fleet cron.

## Non-goals (this slice)

- Auto-purge / Shears cascade from cron
- Worker refuse on `media_library`
- Filling the disk on purpose as a soak test
- Cross-host “mesh rotate”
- Using Hammer `--apply` as rotate

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/library_disk.py` | pipeline | Classify + CLI |
| `library_disk.*` in yaml example | config | Warn / bad thresholds |
| `healthcheck.sh` / `status_report.sh` | ops | Surface free space + level |
| This guide | docs | Slice vs parked rotate |

## Exit criteria

- [x] Configurable free-space check on the sheep library mount (slice)
- [ ] Auto-rotate dry-run + apply reclaims space without orphaning Jellyfin/catalog artifacts
- [ ] Worker refuses new renders when below stop-ingest threshold (sheep mount)
- [x] Health/status shows disk free (level; last rotate N/A until rotate ships)
- [ ] Owner OK

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | _TBD_ | [ ] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) · [../phase3/07_JELLYFLAM3_HAMMER.md](../phase3/07_JELLYFLAM3_HAMMER.md) · [../phase2/01_ARCHIVE_SEED_LIBRARY.md](../phase2/01_ARCHIVE_SEED_LIBRARY.md) · [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md) · [../USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md)
