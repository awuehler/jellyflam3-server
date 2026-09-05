# 09 — Sheep refactor (sub-standard flock repair)

## Boundary

Phase 3 guide — a **refactor tool workflow** that finds and repairs **sub-standard sheep** (poor render quality, bad / muddy palettes, weak TV presence, etc.) and re-queues them through the existing furnace. Complements Shears (CRUD cascade) and Hammer (nuclear wipe).

**Status: complete** — Owner OK 2026-08-21 (Pathways A+P+C+B+D + sidecar history; 16a lab smoke: preview + apply + `refactor[]` on `electricsheep.pedigree.mutate.3b682148`). Next: [10](10_TESTING_AND_ACCEPTANCE.md) RC.

Complements:

- Phase 2 [06](../phase2/06_SHEEP_TAX.md) — structural XML / vocab hygiene (not artistic quality)
- Phase 2 TV-port / OkLCh / Gold Sheep Lite — baseline visual policy the refactor re-applies
- Phase 3 [03](03_SHEEP_SHEARS.md) — curator add / modify / delete + cascade (Shears owns lifecycle; refactor owns **quality remediation**)
- Phase 3 [07](07_JELLYFLAM3_HAMMER.md) — nuclear wipe; not for selective quality fixes

## Intent

| Goal | Why |
|---|---|
| **Cull visual duds without deleting genetics** | Keep pedigree / archive parents; replace weak MP4s and sidecars |
| **Repeatable TV-grade pass** | Re-run TV-port, palette harmony, encode profile, posters |
| **Operator workflow** | Scan → score → **palette report / optional override → poster preview** → apply/replace |

Sub-standard examples (non-exhaustive): crushed blacks, neon clash on living-room TVs, near-empty frames, **linear-only / `singularity="cloned"` voids**, extreme vibrancy, broken aspect after bad hand edits, duration that fails band after dynamic snap, watermark-less masters when watermark policy is on (Phase 4 edges guide).

## Implementation pathways (enable set)

Build `pipeline/refactor.py` (`python3 -m pipeline.refactor`) by **composing existing modules** — do not invent a second furnace.

```text
  catalog MP4 + sidecar + source .flam3 (genomes/done or pedigree)
           │
           ▼
  pathway A — SCAN / SCORE / REPORT (includes complementary palette)
           │
           ├─ ok          → leave alone
           ├─ quarantine  → pathway C
           └─ candidate   → optional pathway P (override + poster preview)
                              │
                              └─ apply → pathway B
```

### Pathway A — Scan / score / report (read-only)

| Step | Reuse | Notes |
|---|---|---|
| Enumerate flock | `pipeline.media_layout`, catalog + `*.jellyflam3.json` sidecars | Same Id space as Shears / Jellyfin |
| Genome hygiene | `pipeline.sheep_tax` (`scan_file` / batch) | Fail → score hard / quarantine candidate |
| Palette / TV policy signals | `pipeline.palette_harmony`, `pipeline.tv_optimize` (inspect XML attrs; optional dry OkLCh pass) | Detect neon clash, missing Gold Sheep Lite knobs, non-16:9 |
| **Current complementary palette** | `pipeline.palette_harmony` (`sample_genome_accent`, `harmony_poles`, `HarmonyResult`) | Report **must** include current harmony: `mode`, `seed_hex`, `complement_hex` (optional pole / sample strip). Aligns with cfg `palette.mode: complementary \| split_complementary \| off` |
| Duration band | `pipeline.choose_duration` + sidecar `duration` / ffprobe | Outside soft/hard band → failing |
| Poster / artwork | `pipeline.poster`, `pipeline.backfill_posters`, `pipeline.flock_artwork` | Missing / black Primary → failing |
| Encode sanity | ffprobe on catalog MP4 (fps, pix_fmt, bitrate heuristics) | Wrong profile → re-encode candidate |
| **Desaturation / wash-out** | Poster mean channel-spread saturation + low-chroma harmony poles | `catalog_desaturated` (mean sat &lt; `refactor.desat_mean_max`, default **0.12**); `palette_washed_out` when both poles are dull |
| **Linear-only / singularities clone** | `pipeline.genome_signals.is_linear_only_genome` / `is_singularity_cloned` | `genome_linear_only` (every xform is implicit or explicit `linear` only — ES void / singularities); `genome_singularity_cloned` (`<flame singularity="cloned">`). Either reason is a **hard quarantine** (not remediable by palette apply). Config: `refactor.linear_only_score` / `singularity_cloned_score` (default **80**) |
| Emit report | JSON + human table (`scan` / `report`) | No catalog writes; palette block required per sheep |

**Report palette block (required fields):**

```json
"palette": {
  "mode": "complementary",
  "seed_hex": "#a1c4ff",
  "complement_hex": "#ffb38a",
  "source": "genome_accent"
}
```

### Pathway P — Palette override + poster preview (Jellyfin-visible, no catalog replace)

Operator gate **before** Pathway B. Reuses palette harmony + poster extract — **not** a second furnace.

Scratch-only JPEGs are **not** enough: the Jellyfin web console only shows items under a configured library path (and/or Images API attachments). Preview must land where Jellyfin can see it.

**MVP note:** Pathway P writes **both** preview kinds under `_refactor-preview/<id>/`:

1. **Sheep still** — `flam3-render` of the retinted `.flam3` → `-preview-still.jpg` / `-preview-poster.jpg`, plus a short `-preview.mp4` looped from that still (what Jellyfin shows as the item).
2. **Palette-pole proxy** — `-palette-preview.mp4` (seed vs complement color panels) so operators can confirm harmony poles without a full re-furnace.

Full flam3 orbit encode of the retint stays on Pathway B.

#### Locked preview location (console-visible)

| Path | Role |
|---|---|
| `/media/sheep/_refactor-preview/<sheep_id>/` | Preview folder under the Sheep volume (Jellyfin-readable) |
| `…/<sheep_id>.flam3` | Staged retinted genome (live catalog untouched) |
| `…/<sheep_id>-preview-still.jpg` | `flam3-render` still of the retinted genome |
| `…/<sheep_id>-preview-poster.jpg` | Same still (Jellyfin Primary sibling name) |
| `…/<sheep_id>-preview.mp4` | Short clip looped from the sheep still |
| `…/<sheep_id>-palette-preview.mp4` | Palette-pole color proxy (seed vs complement) |

Config: `paths.refactor_preview_root` optional; default `media_library/_refactor-preview` (must stay on the Sheep mount, not `/var/cache/…` alone).

**Jellyfin console setup (one-time ops) — hard separation:**

1. Live library **Sheep** → folder `/media/sheep/by-generation` only (never the `/media/sheep` mount root).
2. Dashboard → Libraries → Add library (e.g. **Rework Poster** / **Refactor previews**) → folder `/media/sheep/_refactor-preview`.
3. Flock clients must keep ParentId = live Sheep `library_id` only so `_refactor-preview` items are not ambient-played (already the Roku/Kodi pattern).

#### Pathway P steps

| Step | Reuse | Notes |
|---|---|---|
| Load source `.flam3` | catalog / done / pedigree | Same Id; staging copy only |
| Optional palette override | `pipeline.palette_harmony.apply_palette_harmony` + CLI flags | Override **mode** and/or **seed** without mutating live catalog yet |
| Stage preview genome + short encode | under `/media/sheep/_refactor-preview/<id>/` | Retinted `.flam3` + palette-pole proxy MP4; not live `by-generation/…` |
| Preview poster | `pipeline.poster.extract_mid_loop_poster` → `<id>-preview-poster.jpg` | Jellyfin-friendly sibling name beside preview MP4 |
| Library refresh | `pipeline.jellyfin_client.refresh_library` (or item refresh when Id known) | Required so console shows the new folder/item |
| Optional Images API | `upload_primary_image` on the **preview** item (not live sheep) | Belt-and-suspenders if filesystem poster scan lags |
| Report | JSON: `preview_dir`, `preview_mp4`, `preview_poster`, `jellyfin_item_id?`, `palette_after` | Live catalog Primary unchanged until Pathway B |

**Do not** temporarily overwrite the live sheep’s Primary for preview (confuses flock clients and loses prior art unless carefully backed up). Prefer the dedicated preview library.

**Override / preview flags (CLI):**

| Flag | Effect |
|---|---|
| `--palette-mode complementary\|split_complementary\|off` | Overrides cfg `palette.mode` for this sheep / preview / apply |
| `--palette-seed #RRGGBB` | Optional seed override (else `sample_genome_accent`) |
| `--preview-poster` | Run Pathway P; write preview genome+MP4+poster under `_refactor-preview/`; refresh Jellyfin; do not replace live catalog |
| `--discard` | Remove `_refactor-preview/<id>/` and soft-refresh Jellyfin |
| `--no-jellyfin-refresh` | Skip library refresh (unit tests / offline) |

**Cleanup:** `preview --discard` removes `/media/sheep/_refactor-preview/<id>/` and refreshes. Pathway B `apply` success should do the same once landed.

### Pathway B — Apply / replace (same Id)

Preferred when genetics are kept (after optional Pathway P preview).

**MVP:** `apply` TV-optimizes + palette-overrides the source `.flam3`, stages it into `genomes_inbox`, writes `{stem}.refactor.json` beside the inbox genome, appends `refactor:[]` on the live catalog sidecar when present, and discards `_refactor-preview/<id>/`. Encode / poster / live catalog replace remain **async** on the worker (idle-gate). On ingest the worker rebuilds the sidecar and **merges** prior catalog `refactor` + pending companion (same `ts` → last wins; pending `staged` → `ingested`).

| Step | Reuse | Notes |
|---|---|---|
| Stage genome | `pipeline.shears` **modify** / `pipeline.seed_inbox` | Stable Id retained |
| TV-port + palette | `pipeline.tv_optimize` / `pipeline.palette_harmony` | Same `--palette-mode` / `--palette-seed` as preview |
| Duration | `pipeline.choose_duration` | Worker snaps band on pickup |
| Furnace | `pipeline.worker` inbox → encode → catalog | Idle-gate; no parallel furnace; not awaited by `apply` |
| Poster | `pipeline.poster` / `pipeline.backfill_posters` | Worker / backfill after MP4 exists |
| Sidecar history | pending `{stem}.refactor.json` + catalog append; worker merge on ingest | `refactor: { reason[], score, before, after, palette }` |
| Jellyfin refresh | `pipeline.jellyfin_client` | Soft-fail OK |

```bash
python3 -m pipeline.refactor apply --id <sheep_id>
python3 -m pipeline.refactor apply --id <sheep_id> --confirm APPLY --palette-mode complementary
python3 -m pipeline.refactor apply --id <sheep_id> --confirm APPLY --palette-seed '#88aaff' --keep-preview
```

Mint `electricsheep.pedigree.refactor.*` **only** on the mutate path (genome itself changes via `pipeline.breed`).

### Pathway C — Quarantine (no delete)

Hard-fail gate: stage duds without destroying genetics. Default is **dry-run**; apply with `--confirm QUARANTINE`.

| Step | Reuse | Notes |
|---|---|---|
| Score gate | Pathway A `score_sheep` | Requires `verdict=quarantine` unless `--force` |
| Move genetics | `paths.genomes_quarantine` (+ integrity companions) | Shears-compatible; **no delete** |
| Optional unpublish | park MP4/sidecar/poster under `/media/sheep/_refactor-quarantine/<id>/` + soft Jellyfin `delete_item` | Holding area is not the live Sheep library path. Pasture clients that already cached the item id will **404** until they re-fetch — parked [Phase 4 client polish](../phase4/00_OVERVIEW.md#client-polish-parked--not-numbered) (re-poll on file-not-found, all endpoints). |
| Report | JSON: score, reasons, genome_src/dest, catalog_moved, jellyfin | Operator may later Shears delete |

```bash
python3 -m pipeline.refactor quarantine --id <sheep_id>
python3 -m pipeline.refactor quarantine --id <sheep_id> --confirm QUARANTINE --reason 'neon clash'
python3 -m pipeline.refactor quarantine --id <sheep_id> --confirm QUARANTINE --no-unpublish
```

### Pathway D — Batch

```bash
python3 -m pipeline.refactor scan --config configs/jellyflam3.yaml
python3 -m pipeline.refactor report --json
# Inspect complementary palette in report, then optional override + preview:
python3 -m pipeline.refactor preview --id <sheep_id> --preview-poster
python3 -m pipeline.refactor preview --id <sheep_id> \
  --palette-mode split_complementary --palette-seed '#88aaff' --preview-poster
python3 -m pipeline.refactor quarantine --id <sheep_id>
python3 -m pipeline.refactor quarantine --id <sheep_id> --confirm QUARANTINE
python3 -m pipeline.refactor apply --id <sheep_id> --dry-run
python3 -m pipeline.refactor apply --id <sheep_id> --palette-mode complementary
python3 -m pipeline.refactor batch --failing --limit 10 --dry-run
python3 -m pipeline.refactor batch --failing --limit 10
```

`batch` = Pathway A filter → Pathway B/C per item with `--limit`, always defaulting to dry-run until `--confirm` / explicit flag (match Shears safety). Batch may omit per-Id poster preview unless `--preview-poster` is explicitly set (expensive).

### Framework alignment

| Addition | Aligned? | Why |
|---|---|---|
| Report current complementary palette | **Yes** | `palette_harmony.HarmonyResult` already exposes `mode` / `seed_hex` / `complement_hex`; cfg defaults `palette.mode: complementary` |
| Override palette with an alternative | **Yes** | Same `apply_palette_harmony` path; CLI overrides cfg for one sheep. Modes already include `complementary` and `split_complementary` |
| Preview poster before apply/replace | **Yes** | Stage retinted `.flam3` + palette-pole proxy MP4 + sibling `-poster.jpg` under `/media/sheep/_refactor-preview/<id>/`, then Jellyfin library refresh so **Rework Poster** / **Refactor previews** shows it. Do **not** rely on `/var/cache` scratch alone, and do **not** overwrite live Primary for preview. |

### Enable order (suggested MVP)

1. **A** — `scan` + `report` (including palette block) + scoring fixtures/unit tests — **done**
2. **P** — `preview --preview-poster` (+ palette override flags); no catalog writes — **done** (palette-pole proxy MP4)
3. **C** — quarantine hook for hard fails — **done** (`--confirm QUARANTINE`; optional unpublish)
4. **B** — `apply` dry-run / `--confirm APPLY` stages TV-optimized retint into `genomes_inbox` (same override flags as preview); worker owns encode/poster — **done** (async furnace)
5. **D** — `batch --limit` wrapping B/C — **done** (`--confirm BATCH`; dry-run default)

## Refactor vs Shears vs Hammer

| Tool | Guide | Owns | Does not |
|---|---|---|---|
| **Sheep refactor** | [09](09_SHEEP_REFACTOR.md) | **Quality remediation** — score, palette preview, retint, re-furnace same Id, quarantine park | Lifecycle delete / cascade; nuclear wipe |
| **Sheep Shears** | [03](03_SHEEP_SHEARS.md) | **CRUD + cascade** — add / modify / delete `.flam3` and downstream catalog / Jellyfin artifacts | Artistic quality scoring; flock-wide reset |
| **JellyFlam3 Hammer** | [07](07_JELLYFLAM3_HAMMER.md) | **Nuclear local reset** — purge history, wipe furnace I/O on one host | Per-sheep quality fix; selective unpublish |

Refactor may call Shears **modify** to re-queue; it never replaces Shears delete. Hammer is never the answer for a muddy palette.

## Guidelines

1. Prefer **in-place replace** of catalog artifacts with the same stable Id when genetics are kept; mint refactor pedigree Ids only when the genome itself changes (mutate path).
2. Always **dry-run** before batch apply; never delete peers/share-out without Shears.
3. Reuse sheep tax → TV-optimize → worker path; do not invent a second furnace.
4. Log `refactor: { reason[], score, before, after, palette }` on the sidecar (include before/after harmony hex + mode).
5. Coordinate with commercial filter: NC offspring stay NC after refactor.
6. Quality remediation may feed Shears **modify** for cascade; refactor does not replace Shears delete.
7. Palette **report** is mandatory on `report`; palette **override** and **poster preview** are optional operator gates before `apply`.
8. Preview artifacts live under `/media/sheep/_refactor-preview/<id>/` (Jellyfin-visible, disposable); only Pathway B promotes to live catalog / Jellyfin Primary. Never use preview to overwrite live Primary.
9. Flock clients (Roku / Kodi) must keep `library_id` on the live Sheep library so `_refactor-preview` items are not ambient-played.

## Non-goals

- Manual Apophysis-style art direction UI
- Automatic “pretty” LLM aesthetics (that stays under LLM pedigree)
- Hammer-scale wipes
- Replacing Sheep Shears delete/cascade semantics
- Loop→edge client work (Phase 4; orthogonal to catalog quality repair)
- Interactive color-picker GUI (CLI hex / mode override is enough for Phase 3)
- Claiming that an existing-catalog frame extract previews a new palette (it cannot)

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/refactor.py` (`python -m pipeline.refactor`) | pipeline | `scan` / `report` / `preview` / `quarantine` / `apply` / `batch` CLI |
| Quality score report (`--json`) | ops | Palette (seed + complement) / encode / duration / poster / tax signals |
| Preview dir `/media/sheep/_refactor-preview/<id>/` + preview MP4/poster | ops | Jellyfin-console-visible gate before live replace |
| Jellyfin library **Refactor previews** → that folder | config | One-time Dashboard setup; separate from live Sheep `library_id` |
| `genomes/quarantine/` + `/media/sheep/_refactor-quarantine/<id>/` | ops | Genetics + parked catalog (no delete) |
| Re-TV-port / retint / re-encode apply path | pipeline | Reuse tax → worker furnace; replace same Id when genetics kept |
| Sidecar `refactor: { reason[], score, before, after, palette }` | sidecar | Remediation history |
| Scoring fixtures + unit tests | test | Bad palette / band fail / missing poster / override → new complement hex |

## Exit criteria

- [x] Scanner scores catalog (or done-pool) sheep with documented heuristics — Pathway A (`scan` / `report`)
- [x] `report` includes current complementary (or configured) palette: `mode`, `seed_hex`, `complement_hex`
- [x] CLI can override palette mode and/or seed for preview (`--palette-mode` / `--palette-seed`; apply reserved for Pathway B)
- [x] `preview --preview-poster` writes `/media/sheep/_refactor-preview/<id>/` (retinted `.flam3` + palette-pole proxy MP4 + `-poster.jpg`), soft-refreshes Jellyfin, without replacing live Primary
- [x] Live Sheep `library_id` / client queries exclude `_refactor-preview` (hard library separation)
- [x] Preview cleanup via `preview --discard` (apply-success cleanup deferred to Pathway B)
- [x] `quarantine` dry-run / `--confirm QUARANTINE` moves genetics to `genomes_quarantine` and can park catalog under `_refactor-quarantine/` (no delete)
- [x] `apply` dry-run / `--confirm APPLY` TV-optimizes + palette-overrides and stages into `genomes_inbox` (encode/poster via async worker; same palette flags as preview)
- [x] Batch mode with limit wrapping B/C (`batch --failing --limit N`; `--confirm BATCH`)
- [x] Sidecar records refactor history (including palette before/after)
- [x] Docs distinguish refactor (quality) vs Shears (CRUD) vs Hammer (wipe)
- [x] Unit tests for scoring fixtures (bad palette / band fail / missing poster) + palette override + preview/discard + quarantine + apply + batch
- [x] Lab smoke on at least one furnace Pi — 16a 2026-08-21 (preview + apply + sidecar history on `electricsheep.pedigree.mutate.3b682148`)
- [x] Owner OK 2026-08-21

## See also

[03_SHEEP_SHEARS.md](03_SHEEP_SHEARS.md) · [07_JELLYFLAM3_HAMMER.md](07_JELLYFLAM3_HAMMER.md) · [../phase2/06_SHEEP_TAX.md](../phase2/06_SHEEP_TAX.md) · [../phase2/08_DYNAMIC_DURATION.md](../phase2/08_DYNAMIC_DURATION.md) · [00_OVERVIEW.md](00_OVERVIEW.md) · [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md)
