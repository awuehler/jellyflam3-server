# 03 — Sheep Shears

## Boundary

Phase 3 guide 03 — curator **add / modify / delete** of `.flam3` genomes **and** cascade to downstream artifacts.

**Status: complete** — Owner OK 2026-08-16 (unit tests; lab dry-run on `04a` / `08a`; live cascade delete on `16a`; audit/sweep + peering hygiene landed).

## Intent

Safe flock editing so operators can cull, replace, or inject genomes without orphaning MP4s, sidecars, Jellyfin items, or peer copies.

## Operations

| Action | Behavior |
|---|---|
| **Add** | Stage `.flam3` into inbox (`shears add`); **copy by default** (leave original); `--move` relocates |
| **Modify** | Re-stage into inbox for re-queue; posters via `backfill_posters` after render |
| **Delete** | Dry-run report by default; `--confirm DELETE` applies cascade |
| **Audit / sweep** | Report catalog orphans + peer junk; optional cull with `--confirm DELETE` |

## Commands

```bash
cd /opt/jellyflam3-server   # or repo root

# Delete — always dry-run first
python3 -m pipeline.shears delete electricsheep.247.00505
python3 -m pipeline.shears delete electricsheep.247.00505 --json
python3 -m pipeline.shears delete electricsheep.247.00505 --confirm DELETE

# Audit / sweep — catalog orphans + peer MP4 junk
python3 -m pipeline.shears audit
python3 -m pipeline.shears sweep --orphans-only
python3 -m pipeline.shears sweep --orphans-only --peer-junk --confirm DELETE
python3 -m pipeline.peering hygiene            # list unexpected peer *.mp4
python3 -m pipeline.peering hygiene --apply    # remove them

# Add — copy into genomes_inbox by default (leaves source); --move to relocate
python3 -m pipeline.shears add genomes/samples/electricsheep.247.00505.flam3
python3 -m pipeline.shears add path/to/sheep.flam3 --force
python3 -m pipeline.shears add path/to/sheep.flam3 --move

# Modify — re-stage for worker re-furnace
python3 -m pipeline.shears modify genomes/done/electricsheep.247.00505.flam3
# After worker finishes, refresh posters if needed:
python3 -m pipeline.backfill_posters --config configs/jellyflam3.yaml
```

## Downstream cascade (any/all as applicable)

- Inbox / quarantine / done copies (+ companion sidecars / posters beside genomes)
- In-repo ``genomes/samples/`` and ``genomes/pedigree/`` (recursive; smoke/examples trees)
- Job dirs + frame scratch (matched by job `src` stem)
- Catalog MP4 + `*.jellyflam3.json` + `*-poster.jpg`
- Edge / transition MP4s that reference the sheep as parent ([Phase 4 / 03](../phase4/03_EDGES_AND_WATERMARK.md)) — best-effort name/sidecar match when present
- Jellyfin item delete + library refresh (soft-fail if API unavailable)
- Stills strips (Phase 3 screensaver assets) — best-effort when layout exists
- Syncthing peer copies under local `peers/inbox`, `share-out`, `quarantine` (**only if Opt In**)
- Pedigree child/parent link notes (warn; do **not** auto-delete living children)

## Guidelines

- CLI first; optional small ops UI later.
- Stable genome Ids from Phase 2 pedigree/archive naming make cascade reliable.
- Never delete secrets or Syncthing device config via Shears.
- For wiping **all** local render I/O + history, use [JellyFlam3 Hammer](07_JELLYFLAM3_HAMMER.md) instead.
- Delete confirm token is exactly `DELETE` (not the sheep id).

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/shears.py` (`python -m pipeline.shears`) | pipeline | Add / modify / delete / audit / sweep CLI |
| Dry-run cascade report | ops | Lists inbox, jobs, MP4, sidecars, edges, Jellyfin, stills, peers |
| `--confirm DELETE` | ops | Removes cascade set after explicit confirm |
| `shears audit` / `shears sweep --orphans-only` | ops | Catalog-without-genome + poster/sidecar-only cull |
| `pipeline.peering hygiene` | ops | Unexpected peer `*.mp4` list/remove |
| Pedigree orphan warnings | ops | Surface living children before parent delete |
| `pipeline/jellyfin_client.JellyfinClient.delete_item` | pipeline | Optional Items DELETE during cascade |
| This guide (commands above) | docs | Add / modify / delete / audit runbook |

## Exit criteria

- [x] CLI dry-run delete lists all artifact paths — unit tests + lab dry-run on `04a` / `08a`
- [x] Delete confirm removes cascade set — unit tests + live Shears-delete on `16a` (catalog orphans)
- [x] Add/modify paths documented and tested (`shears add` / `shears modify`)
- [x] Pedigree orphans warned (unit-tested; lab observed on `08a` / `16a`)
- [x] Lab smoke: dry-run `04a`/`08a` + live `16a` (Owner: sufficient 2026-08-16)
- [x] Owner OK

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-16 | [x] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [07_JELLYFLAM3_HAMMER.md](07_JELLYFLAM3_HAMMER.md) · [09_SHEEP_REFACTOR.md](09_SHEEP_REFACTOR.md) (quality remediation — not CRUD) · Phase 2 posters/pedigree guides · [`pipeline/shears.py`](../../pipeline/shears.py)
