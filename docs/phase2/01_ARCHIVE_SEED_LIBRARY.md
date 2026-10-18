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
```

### Request specific sheep

`--sheep` and `--from-file` fetch the ids you name and append them to the inbox FIFO, behind genomes already waiting. The random `--archive` cron is unchanged. The worker claims the new files when drain is off.

A token is `generation.sheep`. The `electricsheep.` prefix and leading zeros are optional: `247.505` and `electricsheep.247.00505` are the same sheep. `--sheep` is a comma-separated list. `--from-file` is one sheep per line; blank lines and `#` comments are ignored, and a line may contain commas. When both are set, the `--sheep` list is queued first.

A sheep already in the catalog or already in the inbox is skipped and named. `--force` replaces an inbox file. A bad id or a failed download is reported, the rest of the list still runs, and the command exits non-zero. `--dry-run` prints the queue and does not fetch.

```bash
cd /opt/jellyflam3-server
python3 -m pipeline.seed_inbox --sheep 247.00505,245.61
python3 -m pipeline.seed_inbox --sheep electricsheep.247.505.flam3 --dry-run
python3 -m pipeline.seed_inbox --from-file sheep.txt
python3 -m pipeline.seed_inbox --sheep 247.00505 --from-file more.txt
```

`sheep.txt`:

```text
# night batch
245.00061
243.16930, 242.100
```

That file alone queues `electricsheep.245.00061.flam3`, then `electricsheep.243.16930.flam3`, then `electricsheep.242.00100.flam3`. Combined with `--sheep 247.00505`, the 247 sheep is first among the new files. None of them pass a genome that was already in the ledger.

```bash
# Cron-friendly wrapper (backlog gate + flock); see script header for crontab
./scripts/cron_archive_seed.sh
./scripts/cron_archive_seed.sh --dry-run
ARCHIVE_EST_HOURS_PER_SHEEP=18 ./scripts/cron_archive_seed.sh --fetch-count 3
```

### Scheduled inbox fill

[`scripts/cron_archive_seed.sh`](../../scripts/cron_archive_seed.sh) wraps `--archive` for cron:

1. Counts `*.flam3` / `*.flame` in `paths.genomes_inbox`
2. Computes `max_clearable = floor((interval_days × 24) / est_hours_per_sheep)`  
   Unset env falls back to **11 days** / **12 h/sheep**. The lab day-of-month list steps by **10**, so the crontab sets `ARCHIVE_CRON_INTERVAL_DAYS=10`. Trial hours (2026-10-17, re-evaluate): **16a 43**, **08a 33**, **04a 23**, ceilings **5 / 7 / 10**.
3. **Skips** when `inbox_count >= max_clearable` (backlog cannot drain to zero before the next cron)
4. Otherwise fetches `min(desired_fetch, max_clearable − inbox_count)`
5. Passes **`--skip-catalog`** by default (`ARCHIVE_SKIP_CATALOG=0` or `--no-skip-catalog` to overwrite catalog sheep)

The wrapper prepends `/usr/local/bin` to `PATH` (cron is often `/usr/bin:/bin`; flam3 is not required for fetch, but the same pattern as idle-breed avoids surprises).

Lab fleet crontab (user `jellyflam3`, staggered so hosts do not all fetch at once):

| Host | Crontab | Local time | `ARCHIVE_EST_HOURS_PER_SHEEP` | Ceiling at 10 days |
|---|---|---|---|---|
| 16a | `27 7 7,17,27 * *` | 07:27 on days 7, 17, 27 | 43 | 5 |
| 08a | `19 5 1,11,21 * *` | 05:19 on days 1, 11, 21 | 33 | 7 |
| 04a | `17 3 3,13,23 * *` | 03:17 on days 3, 13, 23 | 23 | 10 |

```cron
# Example — 04a. Copy the row for this host from the table above.
17 3 3,13,23 * *  ARCHIVE_CRON_INTERVAL_DAYS=10 ARCHIVE_EST_HOURS_PER_SHEEP=23 \
    /opt/jellyflam3-server/scripts/cron_archive_seed.sh \
    >>/var/log/jellyflam3/archive_seed.log 2>&1
```

`breed.idle_breed.archive_cron_*` in `jellyflam3.yaml` **must match this host’s archive crontab** so idle-breed can skip when the next archive fill is imminent. The yaml.example values are the **04a** row.

## Source archive

- Index: https://electricsheep.com/archives/
- Per-generation pages: `…/generation-{N}/best/page/1.html`, `2.html`, and `3.html` (404s skipped — e.g. gen **242** has no `3.html`)
- Generations: `247`, `245`, `244`, `243`, `242`, `198`, `191`, `169`, `165`
- Manifest: [`configs/archive_seed_manifest.json`](../../configs/archive_seed_manifest.json) (**6380** IDs as of 2026-07-31). Random-pick pool for `--archive` and `scripts/cron_archive_seed.sh`. Each entry is a generation and a sheep id from the best pages above. The file holds no genome XML and no license. `--sheep` and `--from-file` do not read it. `--refresh-manifest` replaces the sheep list from the live archive and keeps the file’s `_comment`.

## Pipeline (implemented)

1. Discover IDs → manifest (`--refresh-manifest`)
2. Random pick N (default **3–7**)
3. Fetch `.flam3`. The named archive file is first. When it is missing, the `spex` link on `generation-{N}/sheep/{id}/genome.html` is the genome (generation 165 uses `old/{id}/spex`). Sheepserver mirrors are last.
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
| `pipeline/seed_inbox.py` (`--archive`, `--sheep`, `--from-file`) | pipeline | Manifest pick or named ids → fetch → TV-port → inbox FIFO |
| `pipeline/archive_seed.py` | pipeline | Manifest scrape, fetch, materialize helpers |
| `scripts/cron_archive_seed.sh` | script | Cron wrapper with backlog gate |
| `configs/archive_seed_manifest.json` | config | `--archive` / archive-cron id pool (generation + sheep id). No genomes or license. Named `--sheep` / `--from-file` skip this file. Refresh keeps `_comment` |
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
