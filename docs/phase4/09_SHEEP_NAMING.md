# 09 — Sheep naming (auto-generated aliases)

## Boundary

Phase 4 synopsis — give every catalog sheep a short, **human-readable alias** (e.g. `frosty_swirles`, `angry_bardeen`) so operators and peer clients can remember and reference sheep without typing `electricsheep.247.00505` or pedigree hashes. Also known as a **random name generator** / **auto-generated names** pattern: typically an **adjective + surname** of a famous person, place, or thing.

**Status:** RNG + ingest + override shipped 2026-09-09. **Roku VoD filename vs alias toggle shipped 2026-09-13** (channel **1.0.33**). **Kodi screensaver 0.2.12** and **Roku screensaver 1.0.11** show chrome-light captions with the same `titleMode` (`filename` default / `alias`). Optional Jellyfin OriginalTitle / SortName-as-alias stays parked. **LLM poster naming** is Phase 5 ([../phase5/02_LLM_INTEGRATION.md](../phase5/02_LLM_INTEGRATION.md)). Keys `alias` / `alias_source` live in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Household vote recipes: [08](08_VIEWER_FEEDBACK_LOOP.md).

Depends on catalog **sidecar** as sole metadata SoT ([../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md), [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md)), worker ingest, and peer clients (Roku VoD, Kodi screensaver, Shears CLI). Optional later: LLM vision over poster/stills for a broader inferred vocabulary. Distinct from flam3 XML **`nick`** (designer attribution used by license inference) — aliases are **display / operator names**, not Creative Commons credit.

## Intent

| Surface | Role |
|---|---|
| **Furnace auto-alias** | On ingest (or backfill), generate a unique `adjective_surname` alias and store it on `{stem}.jellyflam3.json` |
| **Human override** | Operator / Shears / CLI may set or rename the alias; override wins over auto-generate |
| **Memorable form** | `snake_case` (or locked separator) of one adjective + one famous surname / place / thing — easy to speak and type in pipeline commands |
| **Client display toggle** | Roku, Kodi, and similar pasture UIs: show **filename** vs **alias** (user-selectable) |
| **LLM enrichment (later)** | Feed poster (or stills) through an LLM to propose an equivalent alias from a wider visual vocabulary; still written to the same sidecar field |

```text
  Worker ingest / backfill
       │  adjective × surname RNG (unique in flock)
       ▼
  {stem}.jellyflam3.json  ← alias (+ alias_source, optional override)
       │
       ├─► CLI / Shears / promote / breed logs (human-readable refs)
       └─► Roku / Kodi title line (toggle: filename | alias)
              └─► optional LLM re-suggest from poster (Phase 5)
```

## Locked product rules (design)

1. **Sidecar is SoT** — alias lives on `{stem}.jellyflam3.json` next to the catalog MP4 (e.g. `alias`, `alias_source`: `auto` | `human` | `llm`). No parallel name DB under `/var/lib`.
2. **Filename stays canonical for files** — on-disk stems remain `electricsheep.{gen}.{id}` / `electricsheep.pedigree.*`; alias never renames the MP4/`.flam3` by default (avoids breakages for Syncthing, Jellyfin paths, idle-gate).
3. **Uniqueness** — auto-generated aliases must be unique within a host’s catalog (and ideally stable under re-ingest of the same stem). Collision → retry with another pair.
4. **Human override sticky** — once `alias_source=human`, automatic regenerators and LLM suggestions must not overwrite unless the operator explicitly “reset to auto.”
5. **Not flam3 `nick`** — do not write aliases into genome XML `nick=` as a substitute for designer credit; license inference keeps using true designer nicks / brood markers.
6. **Vocabulary** — ship a modest curated adjective list + surname/place/thing list in-repo (or config paths); keep offline-first so furnaces do not need network for MVP naming.
7. **Clients optional** — pasture apps default to today’s filename/title until the user enables “show aliases”; missing alias falls back to filename.
8. **LLM is Phase 5** — vision→alias is [../phase5/02_LLM_INTEGRATION.md](../phase5/02_LLM_INTEGRATION.md); MVP here is deterministic RNG (+ human override). LLM proposals still go through uniqueness + operator accept when `alias_source` would become `llm`.

## Sidecar (shipped)

Keys **`alias`** and **`alias_source`** (`auto` \| `human` \| `llm`) are in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Worker ingest copies them on re-encode, then assigns `alias_source=auto` when missing. Human override stays sticky until `clear-alias`. Load–mutate–write readers keep unknown JSON.

## Work items (when Phase 4 opens)

### A — Furnace generator

1. ~~**Word lists**~~ — in-repo `ADJECTIVES` + `SURNAMES` in `pipeline.sheep_naming` (offline).
2. ~~**`pipeline.sheep_naming`**~~ — `generate_alias(stem, existing)` uses a SHA-256 seed from the stem (stable re-ingest); collision walks the pair grid.
3. ~~**Ingest hook**~~ — worker writes `alias` / `alias_source=auto` when missing after reserved-key merge.
4. ~~**Backfill**~~ — `python3 -m pipeline.sheep_naming backfill` (`--dry-run`, `--limit`).
5. ~~**Override CLI**~~ — `set-alias` / `clear-alias` / `resolve` / `show`.

### B — Sidecar + Jellyfin

1. ~~**Reserved + writer**~~ — keys documented; ingest/backfill write them. Generator uniqueness is in-process (catalog scan).
2. Best-effort Jellyfin Overview `Alias:` line (ingest + `set-alias` / `backfill --push-jellyfin`). `Name` / `SortName` stay the filename. Optional OriginalTitle / SortName-as-alias remains parked.
3. Shears delete already removes the sidecar (no parallel alias index).

### C — Peer clients

1. ~~**Roku VoD**~~ — Settings `titleMode` `filename` (default) vs `alias` on flock rows / player chrome. In **1.0.42+**, OK toggles `titleMode` (and `commercialMode` / `streamMode` / `shuffleFlock`) and flushes immediately; **Save & Reload** re-fetches the flock. Reads Overview `Alias:`; missing alias falls back to filename.
2. ~~**Kodi screensaver**~~ — **0.2.12** add-on setting `title_mode`; chrome-light caption (control 101) + JSON-RPC ListItem label. Idle video stays fullscreen. **0.2.13** last-7s vote overlay ([../phase5/05_KODI_SCREENSAVER_VOTES.md](../phase5/05_KODI_SCREENSAVER_VOTES.md)); keys while the overlay is hidden still exit.
3. ~~**Roku screensaver**~~ — **1.0.11** Settings OK-toggle `titleMode`; stills caption from Overview `Alias:` (same fallback). Image-only path; no Sessions/Playing.
4. ~~**Pipeline UX**~~ — `python3 -m pipeline.sheep_naming resolve` maps alias → stem; stem always valid. Shears/breed still take stems.

### D — LLM poster naming (Phase 5)

Moved: [../phase5/02_LLM_INTEGRATION.md](../phase5/02_LLM_INTEGRATION.md) § A and [vision pipeline](../phase5/02_LLM_INTEGRATION.md#vision-pipeline) (small GPU VLM **then** hot Instruct JSON on the **LLM Agent Platform**; sidecar write on the **furnace**; default off). This guide keeps `alias_source=llm` reserved/sticky so Phase 5 can write it **on A**.

1. Input: catalog poster JPEG (or a still) → B VLM caption → B Instruct JSON → proposed `adjective_surname`-shaped string (or free phrase normalized to alias form). Instruct does not consume pixels.
2. Gate: operator accept, or auto-apply only when `alias_source=auto` and policy allows `llm`.
3. Privacy / offline: default off; no cloud calls unless configured.

### E — Ops & docs

1. Operator rename CLI in [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md); VoD / Kodi SS / Roku SS `titleMode` shipped. Optional Jellyfin OriginalTitle / SortName-as-alias parked.
2. ~~Glossary~~ — alias vs flam3 `nick`.
3. ~~Tests~~ — uniqueness, override sticky, collision retry, backfill.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/sheep_naming.py` | pipeline | Hash-seed generator, ingest helper, backfill / set / clear / resolve CLI; `--push-jellyfin` |
| `roku-channel/` VoD **1.0.33** / toggle fix **1.0.39** | client | Settings `titleMode` filename \| alias; OK toggle + Save & Reload |
| `roku-screensaver/` **1.0.11** | client | Stills caption + Settings `titleMode` |
| `kodi-screensaver/` **0.2.12** | client | Caption + `title_mode` setting; ListItem label |
| `configs/jellyflam3.yaml.example` `naming.enabled` | config | Default on; set false to skip ingest assign |
| [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) | docs | Curator alias CLI + VoD / screensaver toggles |

## Non-goals

- Renaming on-disk MP4/`.flam3` as the primary identity
- Replacing Electric Sheep generation.ids for archive pedigree
- Crowdsourced public name registry (household / fleet local is enough)
- Using alias for license/credit instead of designer `nick`

## Exit criteria (when opened)

- [x] New catalog sheep get a unique auto-alias on ingest (worker hook; process restart required for running furnaces)
- [x] Operator can override and reset; sticky against auto/LLM
- [x] At least one peer client (Roku or Kodi) offers filename vs alias display toggle
- [x] Docs + glossary; sidecar schema documented; generator shipped (`pipeline.sheep_naming`)
- [x] LLM path documented as optional / off by default (implementation → [../phase5/02](../phase5/02_LLM_INTEGRATION.md))

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) · [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) · [../phase5/02_LLM_INTEGRATION.md](../phase5/02_LLM_INTEGRATION.md) · [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md) · [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) · [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)
