# 06 — Sheep tax (genome scan & repair)

## Boundary

**Sheep tax:** a proper **scan and repair** pass over each `.flam3` for well-formed XML, required/known key–values, and flam3 **vocabulary** — **stop before** pedigree breeding ([07](07_PEDIGREE_BREEDING.md)). Runs as feedstock hygiene for archive seeds, inbox genomes, peer landings, and Shears modify paths (later).

Name: the “tax” every sheep pays before it is trusted in the furnace or shared onward.

## Intent

Archive and hand genomes often drift: broken XML, unknown attributes, obsolete `version=` strings, multi-root concatenation quirks, missing `size`/`scale`, illegal palette indices, etc. Sheep tax **detects** and, where safe, **repairs** so TV-port / sequence / animate see a consistent dialect.

## Implementation

| Piece | Location |
|---|---|
| Module + CLI | `pipeline/sheep_tax.py` (`python -m pipeline.sheep_tax scan\|batch`) |
| Config | `sheep_tax:` in `configs/jellyflam3.yaml.example` |
| Archive | `materialize_sheep` — tax **before** TV-port when `on_archive_fetch` |
| Peer promote | `pipeline.peering.promote` → `scan_file` (quarantine on fail). Runs only on explicit promote — Syncthing land in `genomes/peers/inbox` does **not** tax or enqueue the worker by itself. |
| Worker ingest | tax copy → then TV-optimize when `on_worker_ingest` |
| Tests | `tests/test_sheep_tax.py`, peering tax cases in `tests/test_peering.py` |

### Checks & repair policy

| Check | Behavior |
|---|---|
| **XML well-formed** | Parse (wrap multi-root in `<flames>` if needed); failure → `quarantined` |
| **Structure** | `multi_flame: strip_to_first` (default) or `reject` |
| **Vocabulary** | Known flame attrs / child tags logged; optional `strip_unknown_elements` |
| **Key–values** | Default `size`/`scale`; clamp color `index` 0–255 and `rgb` channels |
| **Idempotent repair** | Clean file → `status=ok`, no rewrite |
| **Report** | `{ok, status, issues[], flame_count, repaired_at?}` |

### Order

**Tax → TV-port** (OkLCh / Gold Sheep Lite size). Tax does not fight TV-optimize rewrites.

### CLI

```bash
python -m pipeline.sheep_tax scan path/to/a.flam3 --json
python -m pipeline.sheep_tax scan path/to/a.flam3 --no-repair
python -m pipeline.sheep_tax batch genomes/inbox --quarantine
```

### Non-goals

- Changing artistic genetics beyond structural/vocab fixups
- Full flam3 schema certification against every historical Electric Sheep generation
- Repair of binary/non-XML payloads
- License heuristics ([../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md))

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/sheep_tax.py` | pipeline | Scan / repair CLI (`scan` / `batch`) |
| `configs/jellyflam3.yaml` (`sheep_tax`) | config | on_archive_fetch / on_peer_promote / on_worker_ingest |
| `pipeline/seed_inbox.py` / `archive_seed.py` | pipeline | Tax before TV-port on archive materialize |
| `pipeline/peering.py` | pipeline | Tax on gated promote |
| `pipeline/worker.py` | pipeline | Tax on ingest when enabled |

## Exit criteria

- [x] Scanner covers well-formed XML + vocabulary/key–value checks (documented allow lists in module)
- [x] Safe repair path + quarantine path both tested
- [x] Wired for archive fetch, peer promote, and worker ingest
- [x] CLI/batch backfill documented
- [x] Unit tests with fixtures; `pytest` green

## See also

[01_ARCHIVE_SEED_LIBRARY.md](01_ARCHIVE_SEED_LIBRARY.md) · [05_SYNCTHING_GENOME_PEERING.md](05_SYNCTHING_GENOME_PEERING.md) · [07_PEDIGREE_BREEDING.md](07_PEDIGREE_BREEDING.md) · Phase 3 share integrity [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md) · encode [../phase1/05_RENDER_PIPELINE.md](../phase1/05_RENDER_PIPELINE.md)
