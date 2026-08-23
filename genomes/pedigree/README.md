# Git pedigree sheep

Curated **`origin: local_pedigree`** genomes for smoke tests, docs examples, and onboarding.
See [docs/phase3/06_GIT_PEDIGREE_SHEEP.md](../../docs/phase3/06_GIT_PEDIGREE_SHEEP.md).

## Layout

| Path | Role |
|---|---|
| `smoke/` | Default smoke seed(s) — keep **tiny** and TV-portable |
| `examples/` | Extra pedigree examples (mutate/cross demos) |

Encode templates stay under `configs/templates/` (not here). Archive Free Sheep copies may remain under `genomes/samples/` until fully replaced.

## Add / replace a sheep

1. Breed or promote on a lab Pi (`python3 -m pipeline.breed …`); archive to `genomes/done` after a successful render when possible.
2. Sheep-tax clean: `python3 -m pipeline.sheep_tax path/to/child.flam3` (or worker path) — **must pass** before merge.
3. Copy `.flam3` (+ optional `.jellyflam3.json` lineage sidecar) into `smoke/` or `examples/`.
4. Prefer `electricsheep.pedigree.*` Ids; sidecar must include `origin: local_pedigree`, `method`, `parents`, license tags.
5. **Do not** commit MP4s, posters, frames, or secrets.
6. Keep the set small (handful of sheep). Prefer short genomes so smoke stays fast.

## License

Robot remix of human parents → **CC BY-NC** (brood). Do not flip license via mutation %. See [docs/phase1/07_LICENSE_AND_METADATA.md](../../docs/phase1/07_LICENSE_AND_METADATA.md).

## Smoke default

`scripts/smoke_render.sh` defaults to:

`genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3`

Override with `SMOKE_SEED=…` if needed. Fallback (if smoke seed missing): `genomes/pedigree/examples/electricsheep.pedigree.mutate.9334119d.flam3`. Legacy `electricsheep.demo.seed.flam3` was **removed**.
