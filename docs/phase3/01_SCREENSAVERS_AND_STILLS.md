# 01 — Stills and Roku Screensaver / Backdrop

## Boundary

Phase 3 guide 01 — extract stills from rendered sheep; standalone **Roku** Screensaver/Backdrop.

**Kodi** is a **separate** Phase 3 feature (Electric Sheep–dogma video screensaver) — see [02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md). Do not implement Kodi work in this guide.

**Status: complete** — Owner OK 2026-08-16 (extract + sideload). Poster-pipeline Backdrop merge + screensaver 1.0.7 (skip tuple, always rotate, `commercialMode`) 2026-09-08. Mid-session 404 re-poll in screensaver **1.0.8** (2026-09-09).

## Stills extraction

1. From each **non-tuple** catalog sheep, sample N JPEG frames with ffmpeg from the MP4 (poster ingest / `backfill_posters`; operator `python3 -m pipeline.stills`).
2. Store under flock (`by-generation/{gen}/stills/{stem}/frame_XX.jpg` beside `{stem}-poster.jpg`) **and** upload as Jellyfin Backdrop images on the same item as the Primary poster. `stills/.ignore` hides that folder from the Jellyfin library scan.
3. Tag `screensaver_safe` in the sidecar; idle-gate must not treat still fetches as render load. Never extract from `by-generation/tuple/` (watermarked edge mid-file).

Stills serve **Roku** (image-only screensaver). Kodi plays video loops and does not need this path.

## Roku Screensaver / Backdrop

- Standalone package: `RunScreenSaver()` only; **no** Video node; no deep links.
- Cycle Primary posters **and** Backdrop stills via HTTP from all library folders except `tuple`; **depends on** a **current or previously installed** VoD channel (`roku-channel/`) to write registry section `JellyFlam3` (`baseUrl`, `apiKey`, `userId`, `libraryId`). Screensaver Settings does **not** create those keys. Always rotates (does not read VoD `shuffleFlock`). Honors `commercialMode` like VoD.
- Platform rules: [Roku Screensavers](https://developer.roku.com/docs/developer-program/media-playback/screensavers.md).

## Work items (implementation)

1. ~~**Stills pipeline**~~ — `pipeline/stills.py` → `by-generation/{gen}/stills/{stem}/frame_XX.jpg` (also called from poster ingest / `backfill_posters`)
2. ~~**Jellyfin image hook**~~ — screensaver cycles Primary **and** Backdrop stills; extract + Backdrop upload is part of the poster pipeline (never tuples)
3. ~~**`screensaver-safe` + idle-gate**~~ — sidecar tag + `idle_gate.ignore_client_patterns` for `JellyFlam3-Screensaver`
4. ~~**`roku-screensaver/` package**~~ — `RunScreenSaver()` + settings stub; no Video / playback reports
5. ~~**Shared registry**~~ — same `JellyFlam3` keys as VoD
6. ~~**Stills cycle UX**~~ — timed Primary + Backdrop cycle + crossfade; empty/error labels; SS Settings fade/dwell (Owner OK fade controls 2026-08-16; 1.0.7 Backdrop + tuple skip; 1.0.8 404 re-poll)
7. ~~**Package / sideload**~~ — `scripts/package_roku_screensaver.{ps1,sh}` on a furnace Pi → `dist/jellyflam3-screensaver.zip` (includes Jellyfin presets when `secrets.env` is present)
8. ~~**Docs / SoT**~~ — guide + README; watermark stills → Phase 4; Roku publish → Phase 4 / 04
9. ~~**Lab smoke**~~ — Pi stills + idle-gate + Roku Theme/SS + fade controls (Owner OK 2026-08-16)

## LLM-assisted pedigree

Optional AI guidance for parent selection / aesthetic briefs atop Phase 2 `flam3-genome` mutate/cross — **Phase 5** ([../phase5/02_LLM_INTEGRATION.md](../phase5/02_LLM_INTEGRATION.md)). **Not** required for this Roku screensaver track. Out of MVP scope for guide 01 exit.

## Guidelines

1. Screensaver is a **separate** channel from VoD — never embed screensaver in the streaming app (Roku policy: streaming apps may not ship `RunScreenSaver` / `screensaver_title`).
2. Images only on Roku SceneGraph screensaver path — no H.264 `Video` node.
3. Prefer existing flock Primaries / posters when stills are not yet backfilled; extract + Backdrop upload is the durable screensaver path (never from tuples).
4. Reuse Jellyfin auth/library contract from guide 08; do not invent a second secrets scheme. **Locked:** screensaver **depends on** VoD having been installed **on that same Roku** (now or earlier) and Settings saved. Registry is per-device; SS Settings is fade/dwell only.
5. Watermark bake on stills (if any) waits on [Phase 4 edges/watermark](../phase4/03_EDGES_AND_WATERMARK.md) unless a minimal unwatermarked MVP is accepted.
6. **Lab sideload:** developer mode holds **one** custom package. Sideloading the screensaver **replaces** VoD on that Roku; restore by re-sideloading `jellyflam3-roku.zip`. Registry keys **survive** the zip swap. On the Roku, pick the SS only under **Settings → Theme → Screensavers** (nothing named idle-gate appears there). Idle-gate confirmation is a **Pi** check (`idle_gate_status.json` stays `open` while SS runs). For both packages installed at once, use a private channel for one.

## Non-goals

- Kodi add-on (guide [02](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md))
- Video / edge playback inside the Roku screensaver
- Channel Store / private-channel publish of VoD + screensaver → [Phase 4 / 04](../phase4/04_ROKU_PUBLISH.md)
- Mid-session flock **re-poll on 404** when a sheep is quarantined while SS is cycling Primaries → **shipped** screensaver **1.0.8** (drop dead URL, 30s rate-limited StillsTask re-poll, continue). Overnight long-interval re-fetch stays parked.
- Long-running screensaver **session re-fetch** (Limit 200, hours / wrap so ~daily ingest appears without exit) → [Phase 4 client polish](../phase4/00_OVERVIEW.md#client-polish-parked--not-numbered)
- LLM pedigree MVP → [Phase 5 / 02](../phase5/02_LLM_INTEGRATION.md)

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| Stills extract path (ffmpeg) | pipeline | Poster ingest / `backfill_posters`; operator `python3 -m pipeline.stills` |
| `/media/sheep/by-generation/.../stills/{stem}/` | media | Poster + screensaver-safe stills (`stills/.ignore`) |
| `roku-screensaver/` sideload package | channel | `RunScreenSaver()` Backdrop / stills cycle |
| Shared `JellyFlam3` registry keys | config | Written by VoD Settings; screensaver reads them (SS Settings cannot create credentials) |
| `screensaver-safe` tag / idle-gate exemption | runtime | Sidecar + `ignore_client_patterns` |
| `scripts/package_roku_screensaver.*` | script | Lab sideload zip |

## Exit criteria

- [x] Stills pipeline documented and producing assets (`pipeline/stills.py`; merged into poster ingest)
- [x] Roku screensaver package cycles Primary + Backdrop stills (lab sideload Owner OK; 1.0.7 skips tuples, always rotates)
- [x] Shared registry / library contract with VoD channel
- [x] Idle-gate ignores screensaver client pattern
- [x] Explicit non-goal: Kodi tracked only in [02](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)
- [x] Lab smoke Pi stills extract (08a: 2 sheep × 4 JPEG + sidecar `screensaver_safe`)
- [x] Lab smoke idle-gate ignore (`JellyFlam3-Screensaver`)
- [x] Lab smoke Roku: Theme → Screensavers selects JellyFlam3; Pi `idle_gate_status.json` stays `open` while SS runs
- [x] Owner OK 2026-08-16

### Lab smoke log (2026-08-16)

| Check | Host | Result |
|---|---|---|
| Deploy stills + idle_gate (scp; tip still `79a7a6d`) | 16a, 08a | landed |
| `python3 -m pipeline.stills --dry-run --limit 3` | 16a | PASS (gate closed for live extract — TV active) |
| `python3 -m pipeline.stills --limit 2` | 08a | PASS — `244.01807`, `247.47501`; 1920×1080 JPEG; sidecar stills block |
| idle-gate ignore (unit / synthetic client) | 08a | PASS |
| Package zip | operator | `dist/jellyflam3-screensaver.zip` (~50KB) |
| Roku Theme → Screensavers lists JellyFlam3 | Owner | PASS (SS selectable there; replaces VoD sideload — expected) |
| Screensaver Settings Back exits | Owner | PASS (1.0.2 — Scene focus) |
| Pi gate stays open under live SS | 16a | **PASS** — `gate=open` / `reason=idle`; Jellyfin Sessions=0 (SS not reporting playback) |
| Crossfade + Settings (fade/dwell/fade-sec) | Owner | **PASS** — 1.0.3 sideload; controls work as expected |

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-16 | [x] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) · [08_JELLYFIN_ID_DUMP.md](08_JELLYFIN_ID_DUMP.md) · [Pi5_Flam3_VoD_Pipeline.md — screensaver section](../Pi5_Flam3_VoD_Pipeline.md#b-shipped-standalone-jellyflam3-screensaver-phase-3-guide-01) · VoD channel [`roku-channel/`](../../roku-channel/) · Phase 4 publish [../phase4/04_ROKU_PUBLISH.md](../phase4/04_ROKU_PUBLISH.md)
