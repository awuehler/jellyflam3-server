# 07 — License and metadata

## Boundary

Provenance/license tagging and commercial filtering — **not** playback UI.

Canonical Free Sheep policy: [electricsheep.org/license](https://electricsheep.org/license/).  
Implementation: `pipeline/license_filter.py` (`infer_tags_from_genome`, `is_commercial_allowed`).  
Project attributions: [NOTICE](../../NOTICE).

> Practical ops guidance for JellyFlam3 — **not legal advice**. When archive page license and heuristics disagree, prefer the archive (human / brood / edge links).

## Free Sheep vs out-of-scope content

| Source | Role in the furnace |
|---|---|
| **Free Electric Sheep** `.flam3` (archives) | Allowed seeds — tag BY vs BY-NC |
| **Your own** genomes | Allowed — tag as you intend; still attribute flam3/ES inspiration where appropriate |
| **Gold Sheep** / HiFi Dreams / paid Spotworks masters | **Do not ingest** — not CC; personal viewing only ([terms](https://electricsheep.org/termsofservice/)) |
| **Infinidream** (app/cloud platform) | Separate product; not Phase 1 feedstock |

## Attribution

Free Sheep reuse requires credit, e.g. *“Artwork by Scott Draves and the Electric Sheep”* (plus designer `nick` when human).

- Prefer stable IDs in filenames: `electricsheep.{generation}.{id}.mp4`
- Keep `generation-N` + `sheep-ID` in the **sidecar** (and Jellyfin tags when present) so each VoD points back to the genome
- Auto-download/repost: link exact source or at least generation + serial ([ES reuse rules](https://electricsheep.org/license/))

## Phase 1 metadata policy (private-first)

Long-term furnace use is a **wide Free Sheep / own-genome collection**, with **&gt;90% private viewing**; commercial venue use is unlikely.

| Concern | Phase 1 approach |
|---|---|
| License / provenance SoT | **Sidecar-only** — `{basename}.jellyflam3.json` next to the MP4 (`tags`, `license`, `duration_sec`, …) |
| Commercial-safe filtering | Implemented (`license.commercial_mode`, BrightScript `commercialMode`); **default off** |
| Jellyfin Items API `Tags` | **Best-effort / deferred** — soft-fail leaves `Tags: []`; not required for private Path 1 |
| When to push Items API tags | Later ops polish (harden `POST /Items/{id}/Tags` or item update + backfill) if Jellyfin UI / `commercialMode` browsing needs them |

```text
ingest → infer_tags_from_genome → write sidecar (required)
                              └→ add_tags via Jellyfin API (optional; soft-fail OK)
```

## Tag scheme

| Tag | Meaning |
|---|---|
| `cc-by` | Attribution OK — commercial filter **allows** |
| `cc-by-nc` | Non-commercial only — commercial filter **excludes** |
| `generation-NNN` | Flock generation (from filename) |
| `sheep-ID` | Sheep serial (from filename) |
| `human` / `brood` | Provenance (designer vs algorithm) |

When `license.commercial_mode: true`, exclude `cc-by-nc` (and any `exclude_tags`). BrightScript honors the same contract.

## `.flam3` filename convention

Canonical form (implemented in `pipeline/sheep_names.py`):

```text
electricsheep.<kind>.<id>[.<more>].flam3
```

| kind | Example | Role |
|---|---|---|
| `{gen}` (digits) | `electricsheep.247.00505.flam3` | Archive Free Sheep |
| `smoke` / `tv` | `electricsheep.smoke.480p.flam3`, `electricsheep.tv.1080p.flam3` | Encode templates (not flock sheep) |
| `pedigree` | `electricsheep.pedigree.smoke.0001.flam3`, `electricsheep.pedigree.mutate.<id>.flam3` | Git pedigree smoke/examples + local breed children |
| `random` / `mutate` / `reclaim` | `electricsheep.random.*`, `.mutate.*`, `.reclaim.*` | Lab / recovery mints |

Inbox staging normalizes legacy `jellyflam3.*` stems to `electricsheep.*`. Catalog MP4 / sidecar basenames follow the same stem. Sidecars remain `{stem}.jellyflam3.json` (product brand, not genome prefix).

## Reading a source `.flam3`

### Generation / identity

Filename `electricsheep.{gen}.{id}.flam3` → tags `generation-{gen}`, `sheep-{id}`.

### Provenance signals in XML

| Signal | Tag | Typical Free Sheep license |
|---|---|---|
| `nick="Designer"` (not `brood`) | `human` | **CC BY** |
| `nick="brood"`, `notes="brooding"`, `action="clone brood"`, “brood” in edits | `brood` | **CC BY-NC** |
| Ambiguous / missing | — | **Conservative → `cc-by-nc`** |

`<edit …>` lineage is **genealogy + credit history**, not a license upgrade for children.

### Decision tree (ingest)

```text
1. Parse filename → generation-N, sheep-ID
2. Scan XML for nick / brood / edit lineage
3. If human designer nick (≠ brood) → human + cc-by
   Else → brood (if seen) + cc-by-nc   ← default when unsure
4. Write **sidecar** (required); try Jellyfin Items tags (optional)
5. If commercial_mode: drop items with exclude_tags (cc-by-nc)
```

## Genomic inheritance and commercial licensing

Electric Sheep classifies Free Sheep by **how the sheep was created**, not by visual/genetic distance from parents ([license](https://electricsheep.org/license/); algorithm sheep are BY-NC “and have a lineage”; human uploads are BY).

| Situation | Practical license posture |
|---|---|
| Unchanged **human** archive genome | **CC BY** (+ attribution) |
| Unchanged **brood** / algorithm archive genome | **CC BY-NC** |
| **Server/robot** mutate or cross of a human parent (ES flock offspring) | Treat as **algorithm sheep → CC BY-NC** (human ancestor in lineage does **not** make the child BY) |
| Local `flam3-genome` mutate/cross of a **CC BY** human seed | Derivative of BY — remix generally allowed **including commercial**, with **attribution** |
| Local mutate/cross of a **CC BY-NC** seed | Stays in **NC** commercial bucket |
| Mix BY + NC parents | **Conservative: NC** |
| **Percent / magnitude of mutation** | **Does not** flip NC → BY |

```text
Human CC BY parent
  └─ ES server/robot mutate or cross  →  usually CC BY-NC child

% parameter or visual change?
  → does not commercialize an NC (or algorithm) sheep
```

### Commercial filter rule

```text
Algorithm/brood / cc-by-nc (or mixed/unclear)?
  → commercial_mode: EXCLUDE

Clear human CC BY (or BY-legal local derivative of BY-only parents)?
  → allow if attributed

Gold / Infinidream / paid masters?
  → do not put in the furnace
```

## Config

```yaml
license:
  commercial_mode: false    # default: private flock shows BY + BY-NC
                            # true → exclude cc-by-nc from commercial-safe paths
  exclude_tags:
    - cc-by-nc
  default_tags: []
```

- **Sidecar** (`{stem}.jellyflam3.json` beside the catalog MP4) is the **sole metadata source of truth** for that sheep (license/tags in Phase 1; stills index, pedigree hints, viewer votes, aliases). Jellyfin Items Tags/Overview are derived caches for clients. Schema below.
- **Commercial filter** stays in code for the uncommon venue case; leave `license.commercial_mode: false` / client `commercialMode=false` unless you need it.
- **Client contract (Roku VoD + Kodi SS):** filter is **client-side on Jellyfin Items `Tags` only** (never send `Tags=` query params — that emptied the lab flock). When commercial-safe is **on**:
  - **Keep** items that carry a safe tag (`cc-by`, `cc-by-sa`, `cc0`, `public-domain`, `pd`) and **do not** carry `by-nc` / `cc-by-nc`.
  - **Hide** NC items and items with **empty / missing** Tags (empty Tags ≠ “show everything”).
  - Overview `License:` lines feed browse metadata (`metaLine`) but **do not** drive the commercial allow/deny decision.
- Optional later: Jellyfin **commercial-safe** collection excluding NC.

## Catalog sidecar schema

File: `{stem}.jellyflam3.json` next to the catalog MP4. Code list: `pipeline.stills.SIDECAR_RESERVED_KEYS`.

**Readers keep extra keys.** `load_sidecar` / `write_sidecar` (stills, stills-style backfill, refactor history) load–mutate–write and do not strip unknown JSON.

**Worker ingest rebuilds.** `pipeline/worker.py` writes a new dict of known fields and only merges `refactor[]`. A full re-encode **drops** reserved Phase 4 keys until Phase 4 adds a preserve-on-ingest hook. Do not treat a re-ingest as a merge.

### Shipped fields (worker / stills write today)

| Key | Writer | Role |
|---|---|---|
| `id` | worker | Catalog stem |
| `license` | worker | `cc-by` / `cc-by-nc` / `unknown` |
| `tags` | worker | `cc-by`, `generation-N`, `sheep-ID`, `human` / `brood`, … |
| `nframes`, `fps`, `duration_sec`, `duration_target_sec` | worker | Encode timing |
| `edition` | worker | e.g. `gold_sheep_lite` |
| `signals`, `duration_meta` | worker | Dynamic duration (Phase 2). Nested: `signals.orbit_frozen`, `signals.effective_animate_count`; `duration_meta.still_loop` when the worker skipped animate |
| `palette` | worker | Optional OkLCh harmony |
| `jellyfin_image` | flock artwork | Poster / Items image status |
| `refactor` | worker merge / refactor | Pathway history array |
| `screensaver_safe`, stills index | stills | Screensaver frames |

### Reserved Phase 4 keys (names locked; writers parked)

| Key | Guide | Shape | Notes |
|---|---|---|---|
| `type` | [03](../phase4/03_EDGES_AND_WATERMARK.md) | `"loop"` (default when omitted) or `"edge"` | Guide 01 does not add its own top-level key |
| `from_id`, `to_id` | [03](../phase4/03_EDGES_AND_WATERMARK.md) | string or `null` | Companions of `type: edge` |
| `watermark` | [03](../phase4/03_EDGES_AND_WATERMARK.md) | `{ enabled, style, text }` | Provenance mark; do not falsify flam3 XML |
| `viewer_feedback` | [08](../phase4/08_VIEWER_FEEDBACK_LOOP.md); [01](../phase4/01_PEER_SHARE_PATH.md) reads `share_candidate` | `{ likes, loves, votes, last_voted_at, share_candidate }` | Integers / bool / ISO timestamp or `null` |
| `alias` | [09](../phase4/09_SHEEP_NAMING.md) | `adjective_surname` | Display name; filename stays canonical |
| `alias_source` | [09](../phase4/09_SHEEP_NAMING.md) | `auto` \| `human` \| `llm` | Companion of `alias` |

Do **not** implement edge encode, watermark burn-in, vote overlay/sink, or naming RNG until Phase 4 opens those products. Reserving the names here so later writers do not collide.

```json
{
  "type": "loop",
  "from_id": null,
  "to_id": null,
  "watermark": { "enabled": false, "style": "corner", "text": "" },
  "viewer_feedback": {
    "likes": 0,
    "loves": 0,
    "votes": 0,
    "last_voted_at": null,
    "share_candidate": false
  },
  "alias": "frosty_swirles",
  "alias_source": "auto"
}
```

## Lab check — commercial-mode toggle

Use the balanced archive feedstock under `genomes/samples/` (commit `6898720+`): **one CC BY + one CC BY-NC** for gens `247, 245, 244, 243, 242`.

| Gen | CC (expect visible when commercial on) | NC (expect hidden when commercial on) |
|---|---|---|
| 247 | `electricsheep.247.16653` | `electricsheep.247.34067` |
| 245 | `electricsheep.245.07903` | `electricsheep.245.08693` |
| 244 | `electricsheep.244.74503` | `electricsheep.244.51566` |
| 243 | `electricsheep.243.13770` | `electricsheep.243.17332` |
| 242 | `electricsheep.242.00483` | `electricsheep.242.02652` |

**Prerequisites**

1. Samples rendered and ingested on the furnace under test (`*.mp4` + sidecar with `"license": "cc-by"` / `"cc-by-nc"`).
2. Jellyfin Items **Tags** include those license strings (worker enrich / `apply_flock_artwork`). If Tags are empty, commercial-on shows an **empty flock** — fix enrich before judging the client toggle.
3. Clients point at that furnace’s library (`libraryId` / ParentId).

**Roku VoD (`roku-channel`)**

1. Settings → `commercialMode=false` → flock lists **both** CC and NC samples (plus other catalog sheep).
2. Settings → `commercialMode=true` → CC samples remain; NC samples **absent**; detail `metaLine` on survivors shows `cc-by` (not NC).
3. Toggle back to `false` → NC samples reappear without re-sideload.

**Kodi screensaver (`kodi-screensaver`)**

1. Configure → **Commercial-safe (skip NC)** off → screensaver can play NC sample titles.
2. Toggle **Commercial-safe** on → only CC-safe Tags play; NC sample ids never selected.
3. Confirm idle-gate still ignores `JellyFlam3-Screensaver` (gate stays open).

**Quick server-side tag sanity** (on the furnace, after ingest — does not print secrets):

```bash
python3 scripts/jellyfin_id_dump.py --items --limit 50
# Spot-check that CC/NC sample stems show Tags containing cc-by vs cc-by-nc
```


## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/license_filter.py` | pipeline | Infer tags; commercial allow / exclude |
| `pipeline/sheep_names.py` | pipeline | Canonical `electricsheep.<kind>.<id>.flam3` naming |
| `{stem}.jellyflam3.json` sidecars | config | **Sole metadata SoT** beside catalog MP4 (license / provenance; stills; reserved Phase 4 keys) |
| `pipeline.stills.SIDECAR_RESERVED_KEYS` | pipeline | Locked names for `type` / `watermark` / `viewer_feedback` / `alias` (+ companions) |
| `configs/jellyflam3.yaml` (`license`) | config | `commercial_mode`, `exclude_tags` |
| `NOTICE` | config | Third-party / project attributions |

## Exit criteria

- [x] NC genomes tagged `cc-by-nc` (heuristics → **sidecar**; unit-tested)
- [x] Commercial filter excludes NC when enabled (unit-tested; BrightScript contract retained, default off)
- [x] Tags persisted for ops — **sidecar-only** Phase 1 (`*.jellyflam3.json`); Items API tags deferred
- [x] Phase 4 sidecar key names reserved (`type`, `watermark`, `viewer_feedback`, `alias`) — writers parked; readers keep unknown JSON
