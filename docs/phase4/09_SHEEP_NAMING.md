# 09 — Sheep naming (auto-generated aliases)

## Boundary

Phase 4 synopsis — give every catalog sheep a short, **human-readable alias** (e.g. `frosty_swirles`, `angry_bardeen`) so operators and peer clients can remember and reference sheep without typing `electricsheep.247.00505` or pedigree hashes. Also known as a **random name generator** / **auto-generated names** pattern: typically an **adjective + surname** of a famous person, place, or thing.

**Status:** Parked. Do not implement RNG / ingest hook / client filename-vs-alias toggle until Phase 4 opens. Pre-open: `alias` / `alias_source` reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema); household guide [05](05_END_USER_GUIDE.md) baseline does not yet include rename recipes.

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
              └─► optional LLM re-suggest from poster (Phase 4+)
```

## Locked product rules (design)

1. **Sidecar is SoT** — alias lives on `{stem}.jellyflam3.json` next to the catalog MP4 (e.g. `alias`, `alias_source`: `auto` | `human` | `llm`). No parallel name DB under `/var/lib`.
2. **Filename stays canonical for files** — on-disk stems remain `electricsheep.{gen}.{id}` / `electricsheep.pedigree.*`; alias never renames the MP4/`.flam3` by default (avoids breakages for Syncthing, Jellyfin paths, idle-gate).
3. **Uniqueness** — auto-generated aliases must be unique within a host’s catalog (and ideally stable under re-ingest of the same stem). Collision → retry with another pair.
4. **Human override sticky** — once `alias_source=human`, automatic regenerators and LLM suggestions must not overwrite unless the operator explicitly “reset to auto.”
5. **Not flam3 `nick`** — do not write aliases into genome XML `nick=` as a substitute for designer credit; license inference keeps using true designer nicks / brood markers.
6. **Vocabulary** — ship a modest curated adjective list + surname/place/thing list in-repo (or config paths); keep offline-first so furnaces do not need network for MVP naming.
7. **Clients optional** — pasture apps default to today’s filename/title until the user enables “show aliases”; missing alias falls back to filename.
8. **LLM is aspirational** — vision→alias is a later work item; MVP is deterministic RNG (+ human override). LLM proposals still go through uniqueness + operator accept when `alias_source` would become `llm`.

## Sidecar reservation (pre-open)

Keys **`alias`** and **`alias_source`** (`auto` \| `human` \| `llm`) are reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). No RNG generator, ingest hook, backfill CLI, or client filename/alias toggle in this slice. Load–mutate–write readers keep unknown JSON; worker ingest rebuilds known fields only and would drop these keys on re-encode until Phase 4 preserves them.

## Work items (when Phase 4 opens)

### A — Furnace generator

1. **Word lists** — `adjectives` + `surnames` (scientists, artists, places, sheep-adjacent culture TBD); config under e.g. `naming.*`.
2. **`pipeline.sheep_naming` (name TBD)** — `generate_alias(stem, existing_aliases) → str`; stable hash-seed option vs pure random (document which is locked).
3. **Ingest hook** — worker writes `alias` / `alias_source=auto` when missing after encode/sidecar write.
4. **Backfill** — CLI to assign aliases for existing catalog rows without aliases.
5. **Override CLI** — `set-alias` / Shears field; `clear-alias` resets to auto and regenerates.

### B — Sidecar + Jellyfin

1. **Reserved 2026-09-03** — `alias` / `alias_source` documented in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Generator, uniqueness, and ingest hook still parked.
2. Best-effort Jellyfin Overview / custom tag or `SortName` refresh so browse UIs can show the alias without a separate client (optional; clients may read sidecar via furnace API later).
3. Ensure Shears delete/rename cascades do not leave orphan alias indexes.

### C — Peer clients

1. **Roku VoD** — Settings toggle: display **filename** vs **alias** on flock rows / player chrome; screensaver stills captions optional.
2. **Kodi screensaver** — log + optional on-screen label (only if chrome is allowed in a settings preview; idle path stays chrome-free) / JSON-RPC title from alias when configured.
3. **Pipeline UX** — accept alias in selected commands where stem is required today (resolve alias → stem via sidecar scan); keep stem always valid.

### D — LLM poster naming (later)

1. Input: catalog poster JPEG (or a still); output: proposed `adjective_surname`-shaped string or free phrase normalized to alias form.
2. Gate: operator accept, or auto-apply only when `alias_source=auto` and policy allows `llm`.
3. Privacy / offline: default off; no cloud calls unless configured.

### E — Ops & docs

1. End-user guide ([05](05_END_USER_GUIDE.md)): “what is an alias,” how to rename, client toggle.
2. Glossary entry; examples in breed / promote / Shears recipes.
3. Tests: uniqueness, override sticky, collision retry, resolve-by-alias.

## Non-goals

- Renaming on-disk MP4/`.flam3` as the primary identity
- Replacing Electric Sheep generation.ids for archive pedigree
- Crowdsourced public name registry (household / fleet local is enough)
- Using alias for license/credit instead of designer `nick`

## Exit criteria (when opened)

- [ ] New catalog sheep get a unique auto-alias on ingest
- [ ] Operator can override and reset; sticky against auto/LLM
- [ ] At least one peer client (Roku or Kodi) offers filename vs alias display toggle
- [ ] Docs + glossary; sidecar schema documented (key names reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema); generator still parked)
- [ ] LLM path documented as optional / off by default

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) · [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) · [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md) · [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) · [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)
