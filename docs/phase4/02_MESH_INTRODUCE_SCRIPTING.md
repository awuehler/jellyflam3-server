# 02 — Mesh introduce scripting

## Boundary

Reduce one-time Syncthing mesh introduce toil (options A–C). Manual add-json (option D) remains valid.

**Status:** **Closed** 2026-09-19 (Owner OK) — A/B/C shipped 2026-09-13; `mesh-join` skip-self, address upsert, positional `add-json` (2026-09-19). Manual add-json (D) remains valid. No mesh admin UI. Gated `promote --apply` unchanged.

Share **product** leftovers (share-out never hits Syncthing; promote-move on sendreceive inbox) are **not** this slice — [../phase5/04_PEER_SHARE_MESH.md](../phase5/04_PEER_SHARE_MESH.md).

## Options

| Option | What | State |
|---|---|---|
| **A. Local folder ensure** | `python3 -m pipeline.peering ensure-mesh-local` — dirs, `.stignore`, discovery harden (`global-ann-enabled` / `relays-enabled` / `natenabled` false), folder id `jellyflam3-peers-inbox` at the absolute inbox path, type sendreceive. Soft-fail if `syncthing` is missing. **`opt-in` calls this best-effort** after units start. | Shipped |
| **B. Peer list file** | Host-local `configs/peering-peers.json` (**gitignored**). `python3 -m pipeline.peering mesh-join --peers-file …` runs `devices add-json` with the JSON as a **positional argument** (`tcp://IP:22000`), skips this host, shares the folder, and **refreshes** name/address/introducer when the device already exists. Copy [configs/peering-peers.json.example](../../configs/peering-peers.json.example); never commit real device IDs. | Shipped |
| **C. Introducer** | Set `"introducer": true` on the stable host row (lab: **16a**) in the same peers file. Still one mutual introduce; not zero-touch. | Shipped (flag on B) |
| **D. Stay manual** | [deploy/peering/README.md](../../deploy/peering/README.md#syncthing-first-time-mesh-introduce-lab-runbook) add-json | Still valid |

`HOME` for `syncthing cli` is `peering.syncthing.home` (default `/var/lib/jellyflam3/syncthing`).

```bash
python3 -m pipeline.peering ensure-mesh-local --config configs/jellyflam3.yaml
cp configs/peering-peers.json.example configs/peering-peers.json
# edit real deviceID + tailscaleIP; 16a introducer: true
python3 -m pipeline.peering mesh-join --config configs/jellyflam3.yaml \
    --peers-file configs/peering-peers.json
```

Placeholder `REPLACE_…` device IDs and `100.x…` IPs are skipped so an unedited example is a no-op. `mesh-join` skips this host’s own device ID. If a peer is already in Syncthing, it **refreshes** name, `tcp://<tailscaleIP>:22000`, and introducer (lab Tailscale IPs move).

## Non-goals

- Full mesh admin UI
- Committing real Syncthing device IDs
- Re-opening global discovery / relays for the flock share
- Share-out → other hosts (inbox hop) — [../phase5/04_PEER_SHARE_MESH.md](../phase5/04_PEER_SHARE_MESH.md)
- Promote-move deleting land copies on sendreceive inbox — same Phase 5 guide
- Auto-promote (cancelled — [01](01_PEER_SHARE_PATH.md) gated `promote --apply`)

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [../../deploy/peering/README.md](../../deploy/peering/README.md) · [../phase5/04_PEER_SHARE_MESH.md](../phase5/04_PEER_SHARE_MESH.md)
