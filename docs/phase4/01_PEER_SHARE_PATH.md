# 01 — Peer share path revisit

## Boundary

Phase 4 synopsis — decide whether to **keep or change** the locked Phase 2 receive path:

**stage → `genomes/peers/inbox` → gated `promote --apply`** (land ≠ worker ingest).

**Status:** **Locked Wave 3 (2026-09-13)** — keep gated `promote --apply` (land ≠ worker ingest). Auto-promote stays parked. Share-out of voted sheep is `python3 -m pipeline.share_votes` / `scripts/cron_share_votes.sh` → `peers/share-out` only. Household receive + vote/share recipes: [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md#worked-examples).

## Locked today (Phase 2)

Contract: [phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md#pi--pi-receive-path-locked).

## Wave 3 lock

| Question | Decision |
|---|---|
| Path into `genomes/inbox` | **Gated `promote --apply` only** (Phase 2 contract) |
| Auto-promote after tax + share-security | **Parked** — own Owner OK if ever opened |
| Folder IDs / layout | Unchanged |
| Votes → share | Cron **copies** liked `.flam3` to `peers/share-out`; receivers still `promote --apply` |

## Sidecar reservation (pre-open)

Share-out automation (when built) reads **`viewer_feedback.share_candidate`** on `{stem}.jellyflam3.json`. That block is reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) with the rest of `viewer_feedback`. Guide 01 does **not** add its own top-level key.

Vote sink (Wave 2) sets `share_candidate` on like/love/vote. Share cron (Wave 3) reads that block and stages **share-out** only. Worker ingest copies reserved sidecar keys (`viewer_feedback` included) across re-encode. Auto-promote stays parked.

## Non-goals (until opened)

- Silent drain of peers/inbox into the furnace without an explicit gate
- Remote wipe of peer copies

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [02_MESH_INTRODUCE_SCRIPTING.md](02_MESH_INTRODUCE_SCRIPTING.md) · [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) · [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) · [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md)
