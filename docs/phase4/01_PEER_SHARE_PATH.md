# 01 — Peer share path revisit

## Boundary

Phase 4 synopsis — decide whether to **keep or change** the locked Phase 2 receive path:

**stage → `genomes/peers/inbox` → gated `promote --apply`** (land ≠ worker ingest).

**Status:** Parked (moved from end-of-Phase-3 deferral 2026-08-16). Do not implement until Phase 4 opens.

## Locked today (Phase 2)

Contract: [phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md#pi--pi-receive-path-locked).

## Questions for Phase 4

- Keep gated promote as the only path into `genomes/inbox`?
- Allow auto-promote after sheep tax + share-security verify (Phase 3 guide 05)?
- Change folder layout / Syncthing folder IDs?
- Operator UX: CLI only vs host-service action?
- How do **viewer votes** ([08](08_VIEWER_FEEDBACK_LOOP.md)) auto-stage share-out without silent drain into the furnace inbox?

## Non-goals (until opened)

- Silent drain of peers/inbox into the furnace without an explicit gate
- Remote wipe of peer copies

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [02_MESH_INTRODUCE_SCRIPTING.md](02_MESH_INTRODUCE_SCRIPTING.md) · [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) · [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md)
