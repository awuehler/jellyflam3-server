# 03 — Tuples (loop → edge → loop) + edge watermark

## Boundary

Phase 4 — generate a **tuple**: one catalog MP4 that plays **loop A → edge(A→B) → loop B** with a seamless genetic morph, and bake the Electric Sheep watermark **only on the edge stage**.

**Status: shipped** (2026-09-05). Standalone `type: edge` clips, client-side loop→edge→loop sequencers, and watermark-on-loops/stills stay parked.

This guide is the **single home** for tuple encode, edge-stage watermark, and catalog layout under `/media/sheep/by-generation/tuple/`.

## Intent

| Feature | Why |
|---|---|
| **Tuple** | Classic Electric Sheep continuous morph as **one file**: Electric Sheep A + Edge A→B + Electric Sheep B. Clients shuffle/play a tuple like any other sheep. |
| **Seamless stages** | Render via one `flam3-genome sequence=` of two control points (rotate A, morph A→B, rotate B) — not concat of independently encoded catalog MP4s. |
| **Watermark on edge only** | Attribution on the transition without marking the loop stages. |
| **A→B and B→A** | Distinct valid combinations (two edges, two tuples). |

## Product model

- **Loop** — one genome, 360° rotation, periodic → seamless repeat (Phase 1–2 catalog). Unchanged.
- **Tuple** — two single-flame parents; flam3 `sequence=` with **nframes per stage**; two flames ⇒ three stages (loop A, edge, loop B); catalog `type: tuple`.
- **Edge (parked as its own file)** — sidecar `type: edge` remains reserved; this slice does **not** emit standalone edge MP4s under `by-generation/*/edges/`.

### Guidelines

| Topic | Approach |
|---|---|
| **Parents** | Two single-flame, orbitable, non-linear-only genomes; reject parents that are themselves tuples; skip if dest MP4 already exists |
| **Generation** | `flam3-genome sequence=` of both flames; worker passes **stage** `nframes` (not full-loop nframes). Catalog duration is **3× stage** |
| **Duration** | `tuple.stage_duration_sec` default **13**; clamp so `3 × stage` stays at or under the host **hard** max (04a 60 s; never above 120 s) |
| **Catalog layout** | `/media/sheep/by-generation/tuple/electricsheep.tuple.{from}_to_{to}.mp4` |
| **Sidecar** | `type: tuple`, `from_id`, `to_id`, `watermark`, `segments` (loop_a / edge / loop_b times) |
| **Watermark** | Edge stage only. **Private furnace** (`license.commercial_mode: false`, default) may overlay the Cesari PNG when `style: image`. **Commercial-safe / public furnace** (`commercial_mode: true`) never burns that logo pending Spotworks / Draves / Cesari permission — it draws **“artwork by Scott Draves and the Electric Sheep”**. Missing PNG or `style: text` → drawtext. |
| **Playback** | Roku `shuffleFlock` allowlists **`tuple`** and **`pedigree`** (plus archive gens). Kodi already walks all `by-generation/` children |
| **Shears** | Deleting a parent cascades matching tuple MP4s, sidecars, stills, and inbox/done genomes |
| **Idle cron** | `pipeline.breed_idle` may pick **`tuple`** as a random mode beside mutate / cross / blend / interpolate |

### Non-goals (this slice)

- Concat of catalog A.mp4 + edge + B.mp4
- Standalone `type: edge` MP4s or client-side loop→edge→loop sequencers
- Watermark on loop masters or stills
- Auto-thaw frozen `animate=0` parents; linear-only / frozen parents are skipped
- Vote overlay on the edge stage ([08](08_VIEWER_FEEDBACK_LOOP.md))

## Commands

```bash
python3 -m pipeline.sheep_tuple --config configs/jellyflam3.yaml \
  --from genomes/done/electricsheep.247.00505.flam3 \
  --to genomes/done/electricsheep.245.09797.flam3

python3 -m pipeline.breed_idle --config configs/jellyflam3.yaml --dry-run --json
```

Daily idle cron is unchanged (`scripts/cron_breed_idle.sh`); when it draws **tuple**, it stages `electricsheep.tuple.*` into the inbox for the worker.

## Look and feel (what the viewer sees)

A tuple is **one MP4** (~39 s when each stage is 13 s). The morph between stages is seamless. The watermark is not: it **cuts on** when the edge starts and **cuts off** when loop B starts. There is no fade, crawl, or motion of the mark itself. It is **burned into the file**, so Roku, Kodi, and Jellyfin all show the same thing.

| Stage | Duration (default) | Picture |
|---|---|---|
| **Loop A** | ~13 s | Sheep A orbits. **No mark.** |
| **Edge A→B** | ~13 s | A genetically morphs into B. **Mark on** (lower right, ~45% opacity). |
| **Loop B** | ~13 s | Sheep B orbits. **No mark.** |

Placement is the lower-right corner, inset **48 px** from the right and **36 px** from the bottom.

### Private furnace — PNG logo (`license.commercial_mode: false` + `watermark.style: image`)

Household / mixed flock only. Provisional until Spotworks, Scott Draves, or Laura Cesari say otherwise. Asset: [`docs/media/watermark/Electric-Sheep-Icon-7A8B99.png`](../media/watermark/Electric-Sheep-Icon-7A8B99.png) (180×180 RGBA).

- White Electric Sheep silhouette; former black spiral/gaps filled **`#7A8B99`** (cool slate) so the swirl still reads on dark fractals without punching a black hole on bright ones.
- Canvas around the glyph is **transparent** (not a black plate).
- ffmpeg overlays the PNG at **45% opacity**. At 1920×1080 the bug is about 17% of frame height — a corner mark, not a title card.
- If the PNG is missing on the furnace, the worker logs a warning and falls back to the text string (below).

### Commercial-safe / public furnace — attribution text

When `license.commercial_mode: true` (venue / CC-only / published path) the Cesari mascot is **never** burned in, even if `style: image` and the PNG is on disk. Also used when `style: text`, or when the PNG is missing on a private furnace.

- Commercial-safe copy: **`artwork by Scott Draves and the Electric Sheep`** (ES’s prescribed credit; used when yaml left the short default).
- Private fallback / explicit `style: text`: **`Electric Sheep`**
- White, 28 px, DejaVu / Liberation / FreeSans if present; **45% opacity**; same lower-right inset.
- Same edge-only window and hard cut. No font → no text overlay (tuple still catalogs, unmarked).

Disable entirely with `watermark.enabled: false` or `tuple.watermark_on_edge: false`.

## Config

See `tuple:` and `watermark:` in [`configs/jellyflam3.yaml.example`](../../configs/jellyflam3.yaml.example). Disable with `tuple.enabled: false` (idle cron then omits the mode).

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/sheep_tuple.py` | pipeline | Naming, combine genomes, duration, watermark filter, inbox stage |
| `docs/media/watermark/Electric-Sheep-Icon-7A8B99.png` | media | Private-flock edge-stage logo (180×180, white + `#7A8B99`; not used when commercial_mode) |
| `pipeline/worker.py` | pipeline | 3-stage sequence, edge watermark, sidecar `type: tuple` |
| `/media/sheep/by-generation/tuple/` | media | Catalog folder (`catalog_generation` → `tuple`) |
| `*.jellyflam3.json` (`type: tuple`, `from_id`, `to_id`) | sidecar | Parent linkage for playback + Shears |
| `scripts/cron_breed_idle.sh` | ops | Random tuple mode alongside pedigree breeding |
| Roku `archiveGenerationAllowlist` | client | `pedigree` + `tuple` eligible for continuous shuffle |

## Exit criteria

### Tuples

- [x] CLI/pipeline can stage a two-flame tuple genome from two parents
- [x] Worker renders three sequence stages into one MP4 under `by-generation/tuple/`
- [x] Sidecar records `type: tuple` + parent IDs + edge watermark metadata
- [x] A→B and B→A are distinct catalog stems
- [x] Duration respects host hard max; idle-gate honored during render
- [x] Roku shuffle indexes `tuple` and `pedigree`; Kodi recursive flock walk already includes them
- [x] Shears cascade tuples that name a deleted parent
- [ ] **Kodi** dedicated loop→edge→loop sequencer for *standalone* edges — still parked (tuples play as one item)

### Watermark

- [x] Config knobs (`watermark.enabled`, text/font/image, opacity, corner)
- [x] New tuple ingests burn watermark on the **edge stage only**
- [x] Sidecar records watermark metadata
- [x] Disable via `watermark.enabled` / `tuple.watermark_on_edge` (skip overlay)
- [x] Commercial-safe flock (`commercial_mode: true`) skips Cesari logo PNG → ES attribution sentence
- [ ] Watermark on loop MP4s and stills — parked

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) · [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) · encode [../phase1/05_RENDER_PIPELINE.md](../phase1/05_RENDER_PIPELINE.md) · idle breed [../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md)
