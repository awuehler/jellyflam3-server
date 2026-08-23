# 07 — Pedigree breeding

## Boundary

Generate wholly new sheep via **mutate / cross / blend / interpolate** with lineage sidecars — **stop before** dynamic duration ([08](08_DYNAMIC_DURATION.md)). Deterministic `flam3-genome` only. Comes after sheep tax ([06](06_SHEEP_TAX.md)).

## Non-goals (Phase 3)

**LLM-assisted pedigree** (suggest parents, aesthetic briefs, guided mutate/cross) is **Phase 3** — do not add network model stubs in Phase 2.

**Git pedigree sheep** (curated in-repo flock for smoke/examples; dual sample dirs collapsed; smoke uses `genomes/pedigree/`) is **Phase 3** — [../phase3/06_GIT_PEDIGREE_SHEEP.md](../phase3/06_GIT_PEDIGREE_SHEEP.md).

## Guidelines (locked)

| Mode | Meaning | flam3 envars (Pi-verified) |
|---|---|---|
| **mutate** | Random variation of **one** parent (extends `seed_inbox --mutate`) | `mutate=` |
| **cross / blend** | Genetic **cross** of **two** parents; default blend ≈ `method=alternate` | `cross0=` + `cross1=` + `method=` |
| **interpolate** | Explicit two-parent mix — **not** aliased as “blend” | `cross0=` + `cross1=` + `method=interpolate` |

Cross `method` values from flam3: `alternate` | `interpolate` | `union`.

- Output names: `electricsheep.pedigree.*` (stable Ids for future Sheep Shears).
- Sidecar lineage: `parents[]`, `method`, local brood `generation`, license inheritance, **`origin: local_pedigree`** (vs archive feedstock) so peering can eventually share only server-unique sheep ([05](05_SYNCTHING_GENOME_PEERING.md)). Sidecars are **host-local** — they do not sync; promote does not recreate lineage on receivers (no cross-host pedigree inheritance).
- Prefer sheep tax ([06](06_SHEEP_TAX.md)) on parents before mutate/cross (`breed.tax_parents`, default true).
- License: robot remix of human → **NC** per [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md); do not flip via mutation %.
- **Multi-flame / edge parents:** default **strip_to_first**; optional **reject** via `breed.multi_flame` — catalog stays single-sheep closed loops.
- Stage into worker inbox; smoke `--once` before bulk.
- **After successful render:** worker **archives** the inbox `.flam3` to `paths.genomes_done` (default `genomes/done`) — pedigree parent pool. Failures still go to `genomes_quarantine`. Do not delete rendered parents.

## Implementation

| Piece | Location |
|---|---|
| Module + CLI | `pipeline/breed.py` (`python -m pipeline.breed`) |
| Idle daily cron | `pipeline/breed_idle.py` + `scripts/cron_breed_idle.sh` |
| Config | `breed:` + `breed.idle_breed:` in `configs/jellyflam3.yaml.example` |
| Tests | `tests/test_breed.py`, `tests/test_breed_idle.py` |
| Parent pool | Prefer `paths.genomes_done`; also `genomes/samples` + `genomes/pedigree` for idle breed |

## Mode examples

### Mutate — one parent

Nearby sibling of a single taxed sheep.

```bash
# Legacy lab helper (electricsheep.mutate.*)
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml \
  --mutate genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3 --count 1

# Pedigree breed (electricsheep.pedigree.mutate.*)
python3 -m pipeline.breed --config configs/jellyflam3.yaml \
  --mutate genomes/done/parent.flam3 --count 3
```

Under the hood:

```bash
env mutate=/path/parent.flam3 flam3-genome > electricsheep.pedigree.mutate.<id>.flam3
```

Sidecar: `method: mutate`, `parents: [parent]`, `origin: local_pedigree`.

### Cross / blend — two parents

Hybrid genetics. Default “blend” maps to flam3 `method=alternate`; `union` is also a cross method.

| Cross method | Role |
|---|---|
| `alternate` | Classic blend — alternate structure from each parent |
| `union` | Combine variation sets from both |
| `interpolate` | Prefer the dedicated **interpolate** mode below (do not call this “blend”) |

```bash
cd /opt/jellyflam3-server

python3 -m pipeline.breed --config configs/jellyflam3.yaml \
  --cross \
  /var/lib/jellyflam3/genomes/done/parent_a.flam3 \
  /var/lib/jellyflam3/genomes/done/parent_b.flam3

python3 -m pipeline.breed --config configs/jellyflam3.yaml \
  --cross genomes/done/a.flam3 genomes/done/b.flam3 --method alternate

python3 -m pipeline.breed --config configs/jellyflam3.yaml \
  --cross genomes/done/a.flam3 genomes/done/b.flam3 --method union
```

Under the hood:

```bash
env cross0=a.flam3 cross1=b.flam3 method=alternate flam3-genome \
  > electricsheep.pedigree.cross.<id>.flam3
```

Sidecar: `method: cross`, `cross_method: alternate|union`, `parents: [a, b]`, `origin: local_pedigree`.

### Interpolate — explicit two-parent mix

Same plumbing as cross, locked to `method=interpolate` so operators do not confuse it with blend. **Shipped** as `--interpolate`.

```bash
python3 -m pipeline.breed --config configs/jellyflam3.yaml \
  --interpolate parent_a.flam3 parent_b.flam3
```

Under the hood:

```bash
env cross0=a.flam3 cross1=b.flam3 method=interpolate flam3-genome \
  > electricsheep.pedigree.interpolate.<id>.flam3
```

Sidecar: `method: interpolate`, `cross_method: interpolate`, `parents: [a, b]`, `origin: local_pedigree`.

### Contrast

| Mode | Parents | flam3 | Typical child |
|---|---|---|---|
| **mutate** | 1 | `mutate=` | Nearby variant of one sheep |
| **cross / blend** | 2 | `cross0=` `cross1=` `method=alternate` (or `union`) | Hybrid / combined genetics |
| **interpolate** | 2 | `cross0=` `cross1=` `method=interpolate` | Midpoint-ish parameter mix |

**Not Phase 2 pedigree modes** (related, different guides):

- `animate=` — time interpolation along flames already in one file
- `sequence=` — rotation loops + transitions → Phase 4 **edge** clips ([../phase4/03_EDGES_AND_WATERMARK.md](../phase4/03_EDGES_AND_WATERMARK.md)), not closed-loop catalog sheep

## Commands (shipped)

```bash
python3 -m pipeline.breed --config configs/jellyflam3.yaml --mutate path/to/parent.flam3 --count 1
python3 -m pipeline.breed --config configs/jellyflam3.yaml --cross parent_a.flam3 parent_b.flam3
python3 -m pipeline.breed --config configs/jellyflam3.yaml --cross a.flam3 b.flam3 --method union
python3 -m pipeline.breed --config configs/jellyflam3.yaml --interpolate parent_a.flam3 parent_b.flam3
python3 -m pipeline.breed --config configs/jellyflam3.yaml --mutate path/to/parent.flam3 --dry-run
```

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/breed.py` | pipeline | Mutate / cross / interpolate CLI + sidecars |
| `flam3-genome` | binary | Genetic mutate / cross engines |
| `pipeline/sheep_tax.py` | pipeline | Tax parents before breed |
| `pipeline/sheep_names.py` | pipeline | `electricsheep.pedigree.*` child naming |
| `pipeline/seed_inbox.py` (`--mutate`) | pipeline | Legacy lab mutate helper |
| `configs/jellyflam3.yaml` (`breed` + `idle_breed`) | config | Multi-flame policy, tax_parents, archive-cron skip window |
| `pipeline/breed_idle.py` | pipeline | Empty-inbox idle breed (one child) |
| `scripts/cron_breed_idle.sh` | script | Daily cron wrapper (`PATH` + flock) |
| `paths.genomes_done` | config | Post-render parent pool for pedigree |

## Exit criteria

- [x] `pipeline.breed` **mutate** + **cross** CLIs implemented (`--interpolate` shipped); Pi verify — Owner OK 2026-08-04
- [x] Outputs named `electricsheep.pedigree.*`; pedigree sidecar written beside staged `.flam3` with `parents[]`, `method` (and `cross_method`), license inheritance, **`origin: local_pedigree`**
- [x] Parents sheep-taxed + multi-flame **strip_to_first** by default (prefer `genomes_done` as parent pool)
- [x] Unit tests cover naming, NC license inheritance, multi-flame policy, and sidecar `origin`
- [x] Pi smoke: breed → worker inbox → `worker --once` succeeds — Owner OK 2026-08-04
- [x] `configs/jellyflam3.yaml.example` has `breed:` keys; Commands section matches shipped CLI
- [x] Phase 3 LLM note present in [00_OVERVIEW.md](00_OVERVIEW.md) (pre-met; keep as guard)

## Downstream (channel)

Once pedigree VoDs land in the catalog, JellyFlam3 continuous shuffle may later include those **genomic VoD variations** (not only the nine archive generation folders) — see [04 — Future improvements](04_ROKU_CHANNEL_POLISH.md#include-genomic-vod-variations-later).

## Daily idle breed cron

When the inbox is **empty**, the worker is **idle** (gate open, no live render), and the next archive-seed cron is not imminent, a daily cron breeds **exactly one** pedigree sheep so the furnace keeps working between archive fills.

```bash
# Dry-run gates + plan
python3 -m pipeline.breed_idle --config configs/jellyflam3.yaml --dry-run --json

# Cron wrapper — lab fleet is 05:11 local daily
./scripts/cron_breed_idle.sh
```

Lab crontab (user `jellyflam3`, all of 16a / 08a / 04a):

```cron
11 5 * * *  /opt/jellyflam3-server/scripts/cron_breed_idle.sh \
    >>/var/log/jellyflam3/breed_idle.log 2>&1
```

The wrapper prepends `/usr/local/bin` to `PATH`. Cron’s default `PATH` is often `/usr/bin:/bin`, which misses `flam3-genome` after `make install` (`FileNotFoundError: flam3-genome`).

**Benign stderr:** `flam3-genome` may print `warning: reached maximum attempts, giving up.` to stderr during **mutate** / **cross** when its internal optimizer exhausts retries. That message is **not** from JellyFlam3 Python. If the cron log ends with `DONE action=breed` and JSON shows a staged child, the run succeeded — ignore the warning. Persistent failures (no staged file, non-zero exit) are real errors.

Behavior:

- Random **mutate** / **cross** (`method=union`) / **blend** (`method=alternate`) / **interpolate** from `genomes_done` + `genomes/samples` + `genomes/pedigree`. **One child per cron run.**
- Dedup fingerprint vs the last **1** outcome when the parent pool is small (≤ `small_flock_threshold`); last **2** when larger. Re-roll up to `max_rerolls`, then accept a repeat if unavoidable.
- History: `breed.idle_breed.history_file` (default `/var/lib/jellyflam3/breed_idle_history.json`).
- Skip `archive_cron_imminent` uses `breed.idle_breed.archive_cron_*` — **must match this host’s archive crontab**. Per-host values live in `configs/profiles/rpi-jellyflam3-{16,08,04}.yaml`; merge with `python3 -m pipeline.hw_profile apply 16a|08a|04a`. JSON includes `hours_until_archive` (2 decimal places) and `next_archive_at` (ISO local). See [01](01_ARCHIVE_SEED_LIBRARY.md).
- **Phase 4 (parked):** viewer like/love/vote weights may bias parent selection — [../phase4/08_VIEWER_FEEDBACK_LOOP.md](../phase4/08_VIEWER_FEEDBACK_LOOP.md).

## See also

[`pipeline/breed.py`](../../pipeline/breed.py) · [`pipeline/seed_inbox.py`](../../pipeline/seed_inbox.py) (`--mutate` legacy helper). · [04_ROKU_CHANNEL_POLISH.md](04_ROKU_CHANNEL_POLISH.md) · [../phase4/08_VIEWER_FEEDBACK_LOOP.md](../phase4/08_VIEWER_FEEDBACK_LOOP.md) · flam3 envars via `flam3-render` bogus-arg docs dump on Pi
