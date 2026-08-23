# 01 — Archive seed library

## Boundary

Electric Sheep Free Sheep feedstock into the worker inbox — **baseline shipped**. This guide verifies and lightly polishes; it does **not** rebuild the seeder. Stop before Jellyfin poster UX ([02](02_JELLYFIN_FLOCK_UX.md)).

## Commands

```bash
cd /opt/jellyflam3-server   # or repo root
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --archive
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --archive --fetch-count 3
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --refresh-manifest
./scripts/status_report.sh

# Cron-friendly wrapper (backlog gate + flock); see script header for crontab
./scripts/cron_archive_seed.sh
./scripts/cron_archive_seed.sh --dry-run
ARCHIVE_EST_HOURS_PER_SHEEP=18 ./scripts/cron_archive_seed.sh --fetch-count 3
```

### Scheduled inbox fill

[`scripts/cron_archive_seed.sh`](../../scripts/cron_archive_seed.sh) wraps `--archive` for cron:

1. Counts `*.flam3` / `*.flame` in `paths.genomes_inbox`
2. Computes `max_clearable = floor((interval_days × 24) / est_hours_per_sheep)`  
   Script default **11 days** / **12 h/sheep** wall-clock (Gold Sheep Lite + idle-gate). Lab fleet uses **~10-day** day-of-month lists (below); keep `ARCHIVE_CRON_INTERVAL_DAYS` close to the real gap so the backlog math stays conservative.
3. **Skips** when `inbox_count >= max_clearable` (backlog cannot drain to zero before the next cron)
4. Otherwise fetches `min(desired_fetch, max_clearable − inbox_count)`
5. Passes **`--skip-catalog`** by default (`ARCHIVE_SKIP_CATALOG=0` or `--no-skip-catalog` to overwrite catalog sheep)

The wrapper prepends `/usr/local/bin` to `PATH` (cron is often `/usr/bin:/bin`; flam3 is not required for fetch, but the same pattern as idle-breed avoids surprises).

Lab fleet crontab (user `jellyflam3`, staggered so hosts do not all fetch at once):

| Host | Crontab | Local time |
|---|---|---|
| 16a | `27 7 7,17,27 * *` | 07:27 on days 7, 17, 27 |
| 08a | `19 5 1,11,21 * *` | 05:19 on days 1, 11, 21 |
| 04a | `17 3 3,13,23 * *` | 03:17 on days 3, 13, 23 |

```cron
# Example — 04a. Copy the row for this host from the table above.
17 3 3,13,23 * *  /opt/jellyflam3-server/scripts/cron_archive_seed.sh \
    >>/var/log/jellyflam3/archive_seed.log 2>&1
```

`breed.idle_breed.archive_cron_*` in `jellyflam3.yaml` **must match this host’s archive crontab** so idle-breed can skip when the next archive fill is imminent. The yaml.example values are the **04a** row.

## Source archive

- Index: https://electricsheep.com/archives/
- Per-generation pages: `…/generation-{N}/best/page/1.html`, `2.html`, and `3.html` (404s skipped — e.g. gen **242** has no `3.html`)
- Generations: `247`, `245`, `244`, `243`, `242`, `198`, `191`, `169`, `165`
- Manifest: [`configs/archive_seed_manifest.json`](../../configs/archive_seed_manifest.json) (**6380** IDs as of 2026-07-31 refresh across those pages)

## Pipeline (implemented)

1. Discover IDs → manifest (`--refresh-manifest`)
2. Random pick N (default **3–7**)
3. Fetch `.flam3` (sheepserver + archives URL candidates; skip 404s)
4. TV-port: **1920×1080**, Gold Sheep Lite, OkLCh complementary palette
5. Stage `paths.genomes_inbox`; worker sequences / encodes / ingests
6. License via heuristics → sidecar (see [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md))

## Guidelines

- **`--skip-catalog` is the default:** skip archive picks that already have a catalog MP4. The ~10-day archive fill plus daily idle-breed ([07](07_PEDIGREE_BREEDING.md)) keep the furnace working 24×7 without overwrite churn. Use `--no-skip-catalog` only to re-stage / re-render existing catalog sheep.
- Expect multi-hour renders at Gold Sheep Lite; use `status_report.sh` for queue/thermals.
- Optional later polish (not DoD blockers): dead-ID denylist, weighted selection.
- **Scheduled fill:** `scripts/cron_archive_seed.sh` (backlog-aware; crontab example in script header).
- **Orphan jobs:** worker startup reclaims in-flight jobs with no live `flam3-animate`/`ffmpeg` (drops frames, marks `orphaned`/`superseded`, re-queues inbox genomes when still needed). Manual: `python3 -m pipeline.job_recovery --dry-run` then without `--dry-run`. `status_report.sh` labels live vs orphan.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/seed_inbox.py` (`--archive`) | pipeline | Manifest pick → fetch → TV-port → inbox |
| `pipeline/archive_seed.py` | pipeline | Manifest scrape, fetch, materialize helpers |
| `scripts/cron_archive_seed.sh` | script | Cron wrapper with backlog gate |
| `configs/archive_seed_manifest.json` | config | Generation / page sheep ID pool |
| `pipeline/job_recovery.py` | pipeline | Manual orphan reclaim for long renders |
| `scripts/status_report.sh` | script | Queue / thermals / live-vs-orphan labels |
| `configs/jellyflam3.yaml` (`seed_archive`, paths) | config | Inbox paths + TV-optimize settings |

## Exit criteria

- [x] `--archive` stages TV-ported `.flam3` into inbox
- [x] Manifest refresh works; pool ≫ hand-picked samples
- [x] Worker can ingest an archive-staged genome end-to-end (catalog MP4)
- [x] Cron wrapper `scripts/cron_archive_seed.sh` with backlog gate + ~10-day staggered lab crontab
- [ ] Optional: dead-ID denylist *(not implemented — deferred)*

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | | 2026-07-30 | [x] |

Guide 01 complete. Next: [02_JELLYFIN_FLOCK_UX.md](02_JELLYFIN_FLOCK_UX.md).

## See also

[Pi5_Flam3_VoD_Pipeline.md — archive seed library](../Pi5_Flam3_VoD_Pipeline.md#electric-sheep-archive-seed-library-phase-2-baseline--shipped)
