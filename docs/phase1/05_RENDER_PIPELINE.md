# 05 — Render pipeline

## Boundary

Job queue worker: genome → gated MP4 on disk + Jellyfin refresh — **stop before** idle-gate process ownership.

## Job states

`queued → rendering → encoding → gating → ingested → failed`

Terminal recoveries: `orphaned` (re-queued or sample dropped) · `superseded` (catalog MP4 already exists). See `python -m pipeline.job_recovery`.

## Commands

```bash
set -a; source secrets.env; set +a
python3 -m pipeline.worker --config configs/jellyflam3.yaml
python3 -m pipeline.worker --config configs/jellyflam3.yaml --once genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3
```

### Seed inbox (feedstock for the worker)

Stage `.flam3` into `paths.genomes_inbox` so the running worker can ingest. Full Phase 2 archive guide: [../phase2/01_ARCHIVE_SEED_LIBRARY.md](../phase2/01_ARCHIVE_SEED_LIBRARY.md).

```bash
# Curated repo samples (random N, or all)
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --samples --count 1
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --all-samples

# Electric Sheep archive (gens 247–165 best 1.html/2.html/3.html): random fetch + TV-port
# Default fetch count is random 3–7 (override with --count / --fetch-count).
# --skip-catalog is on by default (skip genomes that already have a catalog MP4).
# Daily idle-breed + ~10-day archive fill keep the furnace busy; --no-skip-catalog to re-render.
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --archive
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --archive --fetch-count 3
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --archive --no-skip-catalog
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --refresh-manifest

# Local files / flam3-genome random / mutate
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml path/to/seed.flam3
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --generate 2
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --mutate genomes/samples/electricsheep.247.00505.flam3 --count 3
```

`--archive` loads `configs/archive_seed_manifest.json` (or scrapes with `--refresh-manifest`), downloads `.flam3`, then **TV-ports**: 16:9 **1920×1080**, **Gold Sheep Lite** quality (3-core), and ambient **OkLCh** complementary palette. The worker re-applies the same optimize before sequence/encode/ingest.

## Steps

1. Take `.flam3` from inbox or `--once`
2. TV-optimize: 16:9 + Gold Sheep Lite quality + OkLCh palette
3. Choose duration / nframes (fixed **23 s** default → **552** frames @ 24 fps)
4. `flam3-genome sequence=` with `configs/templates/electricsheep.tv.1080p.flam3` template
5. `flam3-animate` → scratch frames
6. `ffmpeg` H.264 High 4.2 + silent AAC
7. `ffprobe` duration + codec gates
8. Move to library; Jellyfin refresh + tags / sidecar (incl. palette + edition)
9. Cleanup scratch; on success **archive** inbox `.flam3` → `paths.genomes_done` (pedigree parent pool); quarantine failures

Smoke: `JELLYFLAM3_SMOKE=1` uses `smoke_duration_sec: 13` (312 frames @ 24 fps).

## CPU headroom

Default `render.max_cpus: 3` (leave 1 of 4 Pi cores free): `flam3-animate` `nthreads`, `ffmpeg -threads`, and `taskset -c 0-2` when available. systemd unit also sets `CPUQuota=300%` / `AllowedCPUs=0-2`.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/worker.py` | pipeline | Job queue: tax → TV-optimize → sequence → animate → encode → ingest |
| `pipeline/seed_inbox.py` | pipeline | Feed inbox (samples / archive / mutate / generate) |
| `pipeline/job_recovery.py` | pipeline | Reclaim orphaned / superseded in-flight jobs |
| `pipeline/tv_optimize.py` / `resize_genome.py` / `choose_duration.py` | pipeline | Size, Gold Sheep Lite, duration / nframes |
| `pipeline/cpu_limit.py` | pipeline | `max_cpus` / `taskset` pinning helpers |
| `configs/jellyflam3.yaml` (`render`, `vod`, `encode`) | config | CPU cap, duration band, H.264 profile |
| `configs/templates/electricsheep.tv.1080p.flam3` | config | TV sequence template |
| `flam3-genome` / `flam3-animate` | binary | Sequence + frame render |
| `ffmpeg` / `ffprobe` | binary | H.264+AAC encode + duration/codec gates |
| `taskset` | binary | Pin render/encode cores when available |

## Exit criteria

- [x] Seed produces catalog MP4 in **7–37 s** (non-smoke) — proof ~23.0s h264 High
- [x] Jellyfin lists the item after refresh
- [x] Re-run is idempotent (same output path overwritten)
- [x] Bad genome → `genomes/quarantine/` (worker path + directory present)
- [x] Successful inbox render → archive `.flam3` to `paths.genomes_done` (pedigree parent pool)
