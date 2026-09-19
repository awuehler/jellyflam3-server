# 06 — Sheep library disk check and auto-purge / rotate

## Boundary

Keep the **on-disk Sheep library** from filling the media mount: periodic **filesystem free-space check**, then **auto-purge / rotate** catalog sheep with a Shears-grade cascade (not Hammer).

**Status: complete** (check + rotate + worker refuse — Owner OK 2026-09-19). Daily `cron_library_rotate.sh` is **not** in the lab crontab while sheep disks stay below WARN; [Activate daily rotate](#activate-daily-rotate) is the how-to when a host needs it. Archive seed (existing ~10-day job) still rotates before fetch and skips fetch if the sheep mount is still BAD. LRU / commercial-safe filters and soak-fill disks stay **non-goals**.

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
| **Auto-purge / rotate** | Reclaim space by retiring oldest catalog sheep with a **Shears-grade cascade** |
| **Keep furnace 24×7** | Daily idle-breed + ~10-day archive fill assume room on `/media/sheep` |

## Slice

| Piece | State |
|---|---|
| Measure free space on `paths.media_library` (+ scratch if another device) | **Shipped** — `python3 -m pipeline.library_disk check` |
| Config warn / bad thresholds | **Shipped** — `library_disk.*` |
| `healthcheck.sh` WARN (exit 0) / BAD (exit 1) | **Shipped** |
| `status_report.sh` bytes / % / level | **Shipped** |
| Worker refuse new renders | **Shipped** — sheep mount **BAD** only (`library_disk.worker_refuse_on_sheep_bad`, default on). Scratch floor remains `render.free_space_gb_min` |
| Auto-rotate / cron / Shears cascade | **Shipped** — CLI `library_disk rotate [--apply]`; wrapper `scripts/cron_library_rotate.sh` (install crontab only when needed — [Activate daily rotate](#activate-daily-rotate)) |

## Work items

### A — Check

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

### B — Rotate policy (implemented)

1. Keep space under threshold (`rotate_until: ok` purges while WARN/BAD; `warn` purges only while BAD).
2. **Candidate order:** oldest catalog MP4 **mtime** (ingest age). Unpublished / `_refactor-*` / edges skipped.
3. Never delete the only remaining playable loop (**floor ≥ 1**, `rotate_floor`).
4. Same cascade as Shears delete, then **drop git** `genomes/samples` and `genomes/pedigree`.
5. Plan by default; `--apply` / cron apply. `rotate_max_per_run` (default 8). Kill-switch `rotate_enabled`.

```bash
python3 -m pipeline.library_disk rotate           # plan
python3 -m pipeline.library_disk rotate --apply   # Shears deletes
./scripts/cron_library_rotate.sh                  # flock + --apply
./scripts/cron_library_rotate.sh --dry-run        # plan only
```

### Activate daily rotate

Lab 16a / 08a / 04a do **not** have this crontab. Archive seed already rotate-applies before fetch. Add the daily line on a host that is **WARN or BAD**, or that you expect to stay near the warn floor.

On that furnace, as user `jellyflam3`:

```bash
cd /opt/jellyflam3-server
# 1. Kill-switch must be on (default in yaml.example).
grep -n rotate_enabled configs/jellyflam3.yaml
# 2. Plan (no deletes).
python3 -m pipeline.library_disk rotate
# 3. One-shot apply when you accept the plan.
python3 -m pipeline.library_disk rotate --apply
# 4. Log dir for cron.
mkdir -p /var/log/jellyflam3
# 5. crontab -e — add the line below, save, then:
crontab -l | grep cron_library_rotate
```

Same line to paste in `crontab -e` (05:23 local, after 05:11 idle-breed):

```cron
23 5 * * *  /opt/jellyflam3-server/scripts/cron_library_rotate.sh \
    >>/var/log/jellyflam3/library_rotate.log 2>&1
```

**Pass:** `crontab -l` shows the wrapper; `library_disk.rotate_enabled: true`; a dry run of `./scripts/cron_library_rotate.sh --dry-run` exits 0. **Stop without uninstalling cron:** set `library_disk.rotate_enabled: false`. **Uninstall:** `crontab -e` and delete the `cron_library_rotate.sh` line.

Household copy: [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md#activate-library-rotate).

### C — Hook points

1. Worker preflight on the **sheep** mount: refuse ingest when BAD (`RuntimeError`); WARN still renders.
2. Daily wrapper is optional — install with [Activate daily rotate](#activate-daily-rotate). Run `./scripts/cron_library_rotate.sh` by hand when a host is WARN/BAD and you have not armed cron yet.
3. `cron_archive_seed.sh` runs rotate `--apply` then **skips fetch** if check still exits 2 (BAD).

## Lab (2026-09-03)

All three furnaces **OK** (far below warn). Sheep is a separate USB/SATA volume; cache+lib share NVMe. Do not fill living-room disks as a soak test. Rotate is tested with injected usage + tiny catalog trees in pytest.

## Guidelines

1. Rotate is **not** Hammer and **not** the human Shears CLI — an automated valve that **reuses** Shears cascade code.
2. Prefer deleting **catalog outputs** the furnace can re-create.
3. Git pedigree / samples under the repo are **not** rotation targets.
4. `library_disk.rotate_enabled: false` to stop cron apply without uninstalling crontab.

## Non-goals

- Filling the disk on purpose as a soak test
- Cross-host “mesh rotate”
- Using Hammer `--apply` as rotate
- LRU last-played / commercial-safe rotate filters (out of this guide)

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/library_disk.py` | pipeline | Classify + CLI `check` / `rotate` |
| `pipeline/library_rotate.py` | pipeline | Oldest-mtime Shears rotate |
| `scripts/cron_library_rotate.sh` | ops | Optional daily flock + `--apply` — [Activate daily rotate](#activate-daily-rotate) |
| `library_disk.*` in yaml example | config | Warn / bad / rotate / refuse |
| This guide | docs | Check + rotate |

## Exit criteria

- [x] Configurable free-space check on the sheep library mount
- [x] Auto-rotate dry-run + apply reclaims catalog without deleting git feedstock
- [x] Worker refuses new renders when sheep mount is BAD
- [x] Health/status shows disk free; rotate cron documented
- [x] Owner OK 2026-09-19

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-09-19 | [x] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) · [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) · [../phase3/07_JELLYFLAM3_HAMMER.md](../phase3/07_JELLYFLAM3_HAMMER.md) · [../phase2/01_ARCHIVE_SEED_LIBRARY.md](../phase2/01_ARCHIVE_SEED_LIBRARY.md) · [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md) · [../USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md)
