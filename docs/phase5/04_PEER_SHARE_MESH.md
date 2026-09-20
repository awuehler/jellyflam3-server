# 04 — Peer share mesh leftovers (furnace, not Ventuno)

## Boundary

Phase 4 / 02 **mesh introduce A/B/C is closed** (Owner OK 2026-09-19). Opt In can create the local Syncthing folder; `mesh-join` can add peers and refresh Tailscale `tcp://100.x:22000` addresses. That is **inbox transport**, not a complete share product.

This guide is the **parked** summation of work still required so “share” means a genome actually **lands on another furnace**. It lives on **deployment A** (Pi furnaces + Syncthing). Deployment **B** (Ventuno) must **not** Opt In or run Syncthing ([01](01_VENTUNO_Q_HOST.md#tailscale-flock-tailnet)).

**Status:** Parked until Owner opens this slice. Do not implement on Phase 4. Auto-promote stays **cancelled** ([../phase4/01_PEER_SHARE_PATH.md](../phase4/01_PEER_SHARE_PATH.md)).

## What Phase 4 already ships (do not reopen)

| Piece | State |
|---|---|
| Opt In / Out, Tailscale tag, Syncthing unit, `.stignore` allowlist | Shipped ([../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md)) |
| Folder `jellyflam3-peers-inbox` sendreceive on `genomes/peers/inbox` | Shipped (`ensure-mesh-local`) |
| `mesh-join --peers-file` (skip self, positional `add-json`, refresh address/introducer) | Shipped; **closed** 2026-09-19 |
| Gated `promote --apply` (verify → tax → worker inbox or quarantine) | **Locked** — not a silent drain |
| `publish` / `share_votes` → `peers/share-out` | Shipped **stage only** (no Syncthing folder) |
| Ed25519 / SHA-256 integrity on publish/promote | Shipped ([../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md)) |

Treat Syncthing today as: **operator-placed files in `peers/inbox` among Opt-In furnaces**. Vote cron and `publish` do not complete that hop.

## Bottom line (locked problem statement)

1. **Share-out never enters the mesh.** The only Syncthing folder is the inbox. `peering publish` and `cron_share_votes.sh` stop at `genomes/peers/share-out`. Receivers never see those files unless an operator also copies them into **inbox**.
2. **Sendreceive inbox + promote-as-move.** `promote --apply` **moves** the `.flam3` out of inbox. On a shared sendreceive folder that deletion **replicates**. One host promoting can remove the land file from the other furnaces before they promote.

Until both are designed, do not document vote-to-peer as an automatic pipeline.

## Work when Owner opens

Pick **one** send path and **one** receive path. Do not keep sendreceive-on-inbox plus move-on-promote.

### A — Share hop (share-out → other hosts)

Options (Owner picks one):

| Option | Idea | Notes |
|---|---|---|
| **A1** | Second Syncthing folder on `peers/share-out` (sendonly on publisher, recvonly or sendreceive on a dedicated land dir) | Clearest split; two folder IDs; still no auto-promote |
| **A2** | After successful `publish` / `share_votes --apply`, **copy** (not move) into **this host’s** `peers/inbox` so existing sendreceive replicates | Simpler; publisher’s inbox also holds outbound copies; disk growth |
| **A3** | Change `publish` dest to inbox (drop share-out as the sync root) | share-out can remain a local quarantine/stage; document the rename |

**Must keep:** tax + integrity **before** anything hits a Syncthing path. Receivers still `promote --apply`. B never gets a folder.

### B — Promote vs cluster delete

Options (Owner picks one; pairs with A):

| Option | Idea | Notes |
|---|---|---|
| **B1** | Promote **copies** to `genomes/inbox` and leaves the land file (or a `.promoted` marker ignored by `.stignore`) | Avoids remote delete; inbox can accumulate; needs hygiene |
| **B2** | Recvonly inbox per host + sendonly share-out (classic Syncthing send/recv split) | Promote-move is local-only; matches A1 |
| **B3** | Ignore deletes on the inbox folder (`ignoreDelete`) | Fragile; still confusing for operators |

Do **not** solve this with auto-promote.

### C — Maintenance (same slice or follow-on)

These made the lab look “share live” while peers were disconnected:

| Item | Why |
|---|---|
| Healthcheck / `peering status` should fail or WARN when Syncthing **connections** ≠ N−1 (not only unit + Tailscale) | `share_live` can lie |
| Re-run `mesh-join` (or equivalent) when Tailscale IPs move — watchdog does not rewrite device addresses | Discovery/relays stay **off** |
| Optional generator for `peering-peers.json` from `tailscale status` + `syncthing --device-id` | Still gitignore the file |
| Confirm `/opt/jellyflam3-server` and the GitHub clone inbox are the **same directory** on each furnace | Split trees desync pull vs Syncthing |
| `trust-key` exchange runbook (or copy pubs) so inbound promote does not quarantine | Separate from Syncthing device trust |
| `share_pedigree_only_eventually` remains a **policy flag** until origin tagging exists — do not pretend it filters Syncthing | Honest docs |

Mesh admin UI and committing device IDs stay **non-goals**.

## Non-goals

- Auto-promote / silent `peers/inbox` drain
- Syncthing or peering Opt In on the Ventuno
- Re-opening global discovery / relays for flock share
- Remote wipe of peer copies
- Vote-driven auto-queue of a render (votes still only bias share-out **staging** and idle-breed weights until A ships)

## Exit criteria (when opened)

- [ ] Owner-picked A + B implemented and documented
- [ ] `share_votes --apply` / `publish --apply` on furnace X → file appears in furnace Y `peers/inbox` without a manual copy
- [ ] Promote on Y does **not** delete the land copy on Z before Z can promote (or Y/Z split folders make delete local)
- [ ] `peering status` / healthcheck reflect actual Syncthing connections
- [ ] Docs: runbook example 6 pass criterion matches the hop; Phase 2 / 4 no longer imply share-out is the mesh
- [ ] Auto-promote still absent
- [ ] B still has no Syncthing

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [../phase4/02_MESH_INTRODUCE_SCRIPTING.md](../phase4/02_MESH_INTRODUCE_SCRIPTING.md) · [../phase4/01_PEER_SHARE_PATH.md](../phase4/01_PEER_SHARE_PATH.md) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [../../deploy/peering/README.md](../../deploy/peering/README.md)
