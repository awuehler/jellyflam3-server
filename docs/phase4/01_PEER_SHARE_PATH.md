# 01 — Peer share path (gated promote)

## Boundary

Phase 2 receive path stays:

**stage → `genomes/peers/inbox` → gated `promote --apply`** (land ≠ worker ingest).

**Status:** **Locked Wave 3 (2026-09-13).** **Auto-promote cancelled** as a goal 2026-09-13 (same class as `N_max` / screensaver voting): there will not be a silent drain of `peers/inbox` into the furnace. Share-out of voted sheep is `python3 -m pipeline.share_votes` / `scripts/cron_share_votes.sh` → `peers/share-out` only. Receivers still `promote --apply`. Household recipes: [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md#worked-examples).

Contract: [phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md#pi--pi-receive-path-locked).

## Product (locked)

| Question | Decision |
|---|---|
| Path into `genomes/inbox` | **Gated `promote --apply` only** |
| Auto-promote after tax + share-security | **Cancelled** 2026-09-13 — tax/verify still run **inside** `promote --apply`; no cron without `--apply` |
| Folder IDs / layout | Unchanged |
| Votes → share | Cron **copies** liked `.flam3` to `peers/share-out`; receivers still `promote --apply` |

`promote --apply` is the operator gate: share-security → sheep tax → `genomes/inbox` or quarantine. Listing without `--apply` stays the dry view.

## Sidecar

Share-out reads **`viewer_feedback.share_candidate`** on `{stem}.jellyflam3.json` ([phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema)). Vote sink sets it; share cron stages **share-out** only. Worker ingest copies reserved sidecar keys across re-encode. That does **not** skip promote.

## Non-goals (cancelled / out of product)

- Silent drain of `peers/inbox` into the furnace without an explicit `promote --apply`
- Remote wipe of peer copies
- Vote-driven auto-queue of a render (votes bias **share-out** and **idle-breed weights** only)

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [02_MESH_INTRODUCE_SCRIPTING.md](02_MESH_INTRODUCE_SCRIPTING.md) · [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) · [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) · [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md)
