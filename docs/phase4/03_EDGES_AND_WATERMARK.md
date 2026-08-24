# 03 — Edge crossfades + sheep watermark

## Boundary

Phase 4 synopsis — generate **transition edge** (genetic crossfade) clips between sheep, and bake a **watermark** into sheep masters / edges / stills for attribution and provenance.

**Status:** Parked (moved from Phase 3 guide 04 on 2026-08-16). Do not implement until Phase 4 opens.

This guide is the **single home** for watermark scope (formerly a standalone watermark note) and for Electric Sheep–style edge generation.

## Intent

| Feature | Why |
|---|---|
| **Edge / transition crossfades** | Classic Electric Sheep continuous morph: loop A → edge(A→B) → loop B. Phase 1–2 flock stores **closed loop** masters only; Phase 4 adds optional **edge** MP4s (and genomes) for morph programming, screensaver journeys, and curated playlists. |
| **Watermark** | Visible/branding mark on catalog loops, edges, and stills so peers and public surfaces carry JellyFlam3 / license / generation identity without relying on filenames alone. |

## Edge crossfades (when built)

### Product model

- **Loop** — one genome, 360° rotation, periodic → seamless repeat (Phase 1–2 catalog).
- **Edge** — `flam3-genome` multi-seed **sequence** genetic crossfade between two (or more) sheep; **not** a closed loop by itself.

### Guidelines

| Topic | Approach |
|---|---|
| **Parents** | Two single-flame loop genomes (catalog IDs or inbox paths); reject or strip multi-flame parents as in Phase 2 pedigree rules |
| **Generation** | `flam3-genome` `sequence=` with both parents → render/encode like loops (TV-port, Gold Sheep Lite / profile, idle-gate) |
| **Duration** | Short edges (e.g. soft band or dedicated `edge_duration_sec`); never exceed Phase 2 hard max **120 s** |
| **Catalog layout** | e.g. `/media/sheep/by-generation/{gen}/edges/` or `electricsheep.{a}_to_{b}.mp4` + sidecar naming parents |
| **Sidecar** | `type: edge`, `from_id`, `to_id`, nframes/fps, watermark metadata |
| **Playback** | Jellyfin items or playlists that alternate loop → edge → loop; HLS path from Phase 2 guide 03; **Kodi** ES screensaver ([../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)); Roku stills track ([../phase3/01_SCREENSAVERS_AND_STILLS.md](../phase3/01_SCREENSAVERS_AND_STILLS.md)) |
| **Shears** | Deleting a loop sheep should cascade orphan edges ([../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md)) |
| **Core client / pipeline impact** | Edges + watermark are not sidecar-only: expect **encode path**, catalog layout, **Roku VoD** (journey / playlist awareness beyond single-loop seek-reloop), **Kodi** loop→edge→loop sequencer, stills/poster bake, Shears cascade, and possibly shuffle/eligibility rules once edges sit beside loops. Coordinate with [08](08_VIEWER_FEEDBACK_LOOP.md) if vote overlays must appear on edge segments vs loops only. |

### Non-goals (edges)

- Replacing all catalog loops with multi-sheep journeys in Phase 4 MVP
- Real-time GPU morph independent of flam3-genome sequence
- Hours-long live HLS from shuffled MP4s — **out of Phase 3/4 ambient scope** (continuous randomizer dropped; ambient remains Phase 2 MP4 + seek-reloop / per-item HLS)

## Watermark (when built)

All watermark notes for the project live here (not scattered across Phase 1/2/3 as open work).

| Surface | Approach |
|---|---|
| **Catalog loop MP4** | ffmpeg overlay (corner bug / subtle crawl) and/or burn-in during encode; config: enable, opacity, position, text/logo asset |
| **Edge MP4** | Same watermark policy as loops (edges are public-facing morphs too) |
| **Stills / posters** | Same mark on screensaver stills and Primary images for consistency |
| **Genome / sidecar** | Record `watermark: { enabled, style, text }` in `*.jellyflam3.json`; do not alter Free Sheep XML provenance falsely |
| **Opt-out** | Private-only flocks may disable watermark; default policy TBD when Phase 4 opens |

### Non-goals (watermark)

- DRM or forensic steganography as Phase 4 MVP (optional later)
- Watermarking third-party Jellyfin libraries unrelated to Sheep

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| Edge generate CLI / worker path (`flam3-genome` `sequence=`) | pipeline | Produce transition MP4 from two parents |
| `/media/sheep/by-generation/{gen}/edges/` (or named edge MP4s) | media | Catalog edge layout |
| `*.jellyflam3.json` (`type: edge`, `from_id`, `to_id`) | sidecar | Parent linkage for playback + Shears cascade |
| Loop→edge→loop playlist / client path | playback | Documented journey for Jellyfin / Kodi |
| `configs/jellyflam3.yaml` (`watermark.*`) | config | Enable, asset, opacity, corner, Opt-Out disable |
| Watermarked loop / edge / still encode | pipeline | Burn-in or ffmpeg overlay on public surfaces |
| Sidecar `watermark: { enabled, style, text }` | sidecar | Provenance without falsifying Free Sheep XML |

## Exit criteria (when Phase 4 opens)

### Edges

- [ ] CLI/pipeline can produce an edge MP4 from two catalog (or inbox) parents
- [ ] Sidecar records `type: edge` + parent IDs
- [ ] At least one loop→edge→loop playlist or client path documented
- [ ] **Kodi** screensaver sequencer performs loop→edge→loop when edges exist (deferred from Phase 3 [guide 02](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md); Owner OK 2026-08-21)
- [ ] **Roku VoD** documents how edges appear (playlist / deep-link / optional journey mode) vs today’s single-sheep ambient loop
- [ ] Duration respects hard max 120 s; idle-gate honored during render

### Watermark

- [ ] Config knobs documented (`watermark.enabled`, asset path, opacity, corner)
- [ ] New loop **and** edge ingests can emit watermarked MP4 + matching stills
- [ ] Sidecar records watermark metadata
- [ ] Disable path for private Opt-Out flocks verified

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) · transitions vs loops in [../Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md) · encode [../phase1/05_RENDER_PIPELINE.md](../phase1/05_RENDER_PIPELINE.md) · pedigree parents [../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md)
