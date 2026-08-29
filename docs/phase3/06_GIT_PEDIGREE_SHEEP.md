# 06 — Git pedigree sheep (smoke & examples)

## Boundary

Phase 3 guide 06 — keep a **curated set of shared pedigree `.flam3` genomes in git** for smoke tests, docs examples, and developer onboarding. **Eventually replace** archive Free Sheep copies under `genomes/samples/` with that pedigree flock (longer-term; not required for this guide’s MVP exit).

This is **versioned project feedstock**, not Syncthing peer share ([05](05_SHARED_SHEEP_SECURITY.md)) and not live flock media on the Pi.

**Status: complete** — Owner OK 2026-08-14 (MVP exit met; smoke path + demo retirement + Pi verify 2026-08-13). Next: [08](08_JELLYFIN_ID_DUMP.md).

## Layout (samples collapse — done)

| Path | Role |
|---|---|
| `genomes/samples/*.flam3` | Archive / bootstrap flock seeds (`sample_pool()` / `--samples`) — **2 per gen** for `247/245/244/243/242` (**one CC BY + one CC BY-NC**) so commercial-mode client toggles can be lab-checked once rendered |
| `genomes/pedigree/` | **Curated git pedigree** — smoke + examples (`origin: local_pedigree`) |
| `configs/templates/electricsheep.{smoke.480p,tv.1080p}.flam3` | Encode / sequence **templates** (`paths.template`, `smoke_render.sh`) |
| `configs/samples/` | **Removed** — do not reintroduce a second sheep pool |

Wire-up already landed:

1. Non-template sheep live under `genomes/samples/` (archive bootstrap) and `genomes/pedigree/` (curated).
2. Templates under `configs/templates/`; `paths.template` + smoke script point there.
3. `sample_pool()` reads `genomes/samples/` only; smoke default is `genomes/pedigree/smoke/…`.
4. Docs / tests updated off `configs/samples`.
5. Curation policy: `genomes/pedigree/README.md`.

Templates must **never** enter the `--samples` / flock seed pool (`is_template_genome`).
## Why pedigree-in-git next

`genomes/samples/` still holds **archive Free Sheep feedstock** (`--samples` / bootstrap) — useful furnace input, but not JellyFlam3 pedigree sheep (`origin: local_pedigree` from Phase 2 [07](../phase2/07_PEDIGREE_BREEDING.md)). The curated set is **ten genomes**: one human (CC BY) and one brood/empty-nick (CC BY-NC) for each of gens `247, 245, 244, 243, 242`. Smoke and docs examples use `genomes/pedigree/` so CI/onboarding exercise the same class of genomes operators breed and peer. Client commercial-mode checks: [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md#lab-check--commercial-mode-toggle).

## Locked intent

1. **One sheep-sample root** — `genomes/samples/` (then `genomes/pedigree/`); templates under `configs/templates/`.
2. **Repo home for pedigree** — e.g. `genomes/pedigree/` checked into git; small, curated, reviewable diffs.
3. **Pedigree only** — genomes produced (or explicitly promoted) via mutate/cross with lineage sidecar; prefer `electricsheep.pedigree.*` + `origin: local_pedigree`.
4. **Smoke & examples first** — `scripts/smoke_render.sh`, docs, and fixtures point at the git pedigree set.
5. **Replace legacy smoke seeds** — smoke/docs use `genomes/pedigree/`; archive Free Sheep may remain under `genomes/samples/` as furnace feedstock only.
6. **Sheep tax clean** — every committed sheep must pass Phase 2 sheep tax ([06](../phase2/06_SHEEP_TAX.md)) before merge; optional checksum sidecar per [05](05_SHARED_SHEEP_SECURITY.md) if useful for CI.

## Out of scope (stay config, not flock samples)

| Keep | Why |
|---|---|
| `configs/templates/electricsheep.tv.1080p.flam3`, `configs/templates/electricsheep.smoke.480p.flam3` | Encode / sequence **templates**, not flock sheep |
| Live `/media/sheep/...` catalog on Pi | Runtime flock; not a git mirror of every MP4 |
| Syncthing peer inbox | Different trust domain; see [05](05_SHARED_SHEEP_SECURITY.md) |

Archive seeder (`--archive`) remains a **furnace feedstock** path; it does not need to disappear.

## Suggested pedigree layout

```text
genomes/pedigree/
  README.md                 # curation policy, license, how to add
  smoke/
    electricsheep.pedigree.smoke.0001.flam3
    electricsheep.pedigree.smoke.0001.jellyflam3.json
  examples/
    electricsheep.pedigree.example.*.flam3
```

Keep the set **tiny** (handful of sheep): enough for smoke duration + one mutate/cross example + one “pretty” docs seed. Prefer short, TV-portable genomes so smoke stays fast.

## Remaining migration

1. ~~Breed/promote smoke seed~~ — `genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3` (from 04a `ccd9218c`).
2. ~~Point `SMOKE_SEED` default at pedigree smoke~~ — done in `scripts/smoke_render.sh`.
3. ~~Update smoke/docs/CLI examples off archive Free Sheep / `demo.seed`~~ — guide 05 fixture + breed mutate example + license kind table; smoke fallback → pedigree `examples/`.
4. ~~Remove legacy `electricsheep.demo.seed.flam3`~~ — deleted; archive Free Sheep under `genomes/samples/` remain as **furnace feedstock** (`--samples` / archive seeder), not smoke seeds.
5. ~~Pi smoke against pedigree seed~~ — `rpi-jellyflam3-04a` 2026-08-13: `SMOKE_RENDER_OK` (`electricsheep.pedigree.smoke.0001`, 640×360 / 13.0s).

## Non-goals

- Committing rendered MP4s, frames, or Jellyfin images
- Mirroring the entire living flock in git
- Replacing archive download for bulk furnace seeding
- Auto-pushing every peer-received sheep into the repo

## Dependencies

- Phase 2 pedigree breeding ([07](../phase2/07_PEDIGREE_BREEDING.md)) and sheep tax ([06](../phase2/06_SHEEP_TAX.md))
- Smoke path: [../phase1/03_FLAM3_AND_FFMPEG.md](../phase1/03_FLAM3_AND_FFMPEG.md) / `scripts/smoke_render.sh`
- Optional: share-security checksum conventions ([05](05_SHARED_SHEEP_SECURITY.md))

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `genomes/pedigree/` | genome | Curated git pedigree root (`origin: local_pedigree`) |
| `genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3` (+ sidecar) | genome | Default smoke seed |
| `genomes/pedigree/examples/` | genome | Docs / mutate–cross example seeds |
| `genomes/pedigree/README.md` | docs | Curation policy, sheep tax gate, license notes |
| `scripts/smoke_render.sh` (`SMOKE_SEED` → pedigree smoke) | script | Toolchain smoke against git pedigree |
| `configs/templates/electricsheep.{smoke.480p,tv.1080p}.flam3` | template | Encode templates (not flock samples) |
| `genomes/samples/*.flam3` | genome | Archive Free Sheep furnace feedstock only |

## Exit criteria

- [x] Single sheep-sample root: flock seeds only under `genomes/samples/`; templates under `configs/templates/`; `configs/samples/` gone
- [x] `sample_pool()` / `--samples` / docs no longer union two sample directories
- [x] `genomes/pedigree/` exists with curated smoke + example sheep
- [x] Default smoke seed uses a git pedigree sheep (`scripts/smoke_render.sh` → `genomes/pedigree/smoke/…`)
- [x] Docs / CLI smoke examples use git pedigree paths (not `electricsheep.demo.seed` / archive Free Sheep for smoke)
- [x] Legacy `electricsheep.demo.seed.flam3` removed; dual-tree already gone; archive `genomes/samples/` kept as furnace feedstock
- [x] Curation README: add/replace policy, sheep tax gate, license notes (`genomes/pedigree/README.md`)
- [x] Local / Pi smoke green against pedigree seed — `rpi-jellyflam3-04a` 2026-08-13 (`SMOKE_RENDER_OK`)

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-14 | [x] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [08_JELLYFIN_ID_DUMP.md](08_JELLYFIN_ID_DUMP.md) · [../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md) · [../phase2/06_SHEEP_TAX.md](../phase2/06_SHEEP_TAX.md) · [05_SHARED_SHEEP_SECURITY.md](05_SHARED_SHEEP_SECURITY.md) · [03_SHEEP_SHEARS.md](03_SHEEP_SHEARS.md)
