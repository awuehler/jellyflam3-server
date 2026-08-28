# 05 — Syncthing genome peering (via Tailscale)

## Boundary

Private **JellyFlam3 ↔ JellyFlam3** genome sync: [Syncthing](https://syncthing.net/) over a [Tailscale](https://tailscale.com/) private network — **stop before** sheep tax ([06](06_SHEEP_TAX.md)) / pedigree ([07](07_PEDIGREE_BREEDING.md)).

Phase 2 delivers the **model, host-service contract, templates, and operator docs**. It does **not** require a full Channel Store–grade UX; a local CLI/systemd “host service” is enough for DoD.

**Status:** **complete** for Phase 2 DoD — fixture promote + sheep tax on `rpi-jellyflam3-08a` 2026-08-08. **Lab flock mesh** (`rpi-jellyflam3-16a` / `08a` / `04a`): Tailscale Opt In (`tag:jellyflam3`), Syncthing folder `jellyflam3-peers-inbox`, cross-host land + gated promote smoked 2026-08-11 (pedigree breed → peers inbox → promote on 04a 2026-08-11).

## Clean model (locked)

```text
  User / owner
       │  only touch point: Opt In / Opt Out
       ▼
  JellyFlam3 host service   ← complementary control plane on the Pi
       │
       ├─ Tailscale: auth path → enroll → tags/ACLs → bring-up / tear-down
       └─ Syncthing: managed config → start / stop → share folder = *.flam3 + optional *-poster.jpg
              │
              ▼
         genomes/peers/…  (land) → sheep tax → gated promote → worker inbox
```

| Layer | Role |
|---|---|
| **Host service** | **Only** user-facing touch point. Owns Opt In / Opt Out, Tailscale lifecycle, Syncthing lifecycle, credentials, and systemd enablement. |
| **Tailscale** | Private underlay (tailnet). No public Syncthing discovery/relays for flock peering. Policy via tags + ACLs. |
| **Syncthing** | Application sync of **`*.flam3`** plus optional companion **`*-poster.jpg`** among Opt-In peers on the tailnet. Config is **managed** (generated/written by the host service), not hand-edited day-to-day. |

**Day-to-day:** Opt In / Opt Out only — no peer-ID chores once the Syncthing mesh exists.  
**Setup / teardown:** Tailscale + Syncthing **lifecycle** via Opt In / Opt Out.  
**First flock mesh (one-time):** Syncthing folder + device introduce is still an **operator step** (CLI or GUI) — see [deploy/peering/README.md](../../deploy/peering/README.md#syncthing-first-time-mesh-introduce-lab-runbook). Opt In does **not** invent peers.  
**Access:** Tailscale ACLs + tags gate the underlay; Syncthing device trust is separate and explicit on first introduce.

### Initial trust (constraint)

The hard step remains **first enrollment trust** (who may join the flock tailnet). That step is **centralized in the host service** (and the complementary admin/control path it uses — e.g. pre-authorized auth key, OAuth device flow, or admin approval). The end user only experiences a simple **Opt In** / **Opt Out** action; they do not paste device IDs or edit ACL files.

### Locked auth path (Phase 2 DoD)

| Choice | Detail |
|---|---|
| **Method** | Tailscale **pre-auth key** in `secrets.env` as `TS_AUTHKEY` (never commit) |
| **Tag** | `tag:jellyflam3` — ACL example in [`deploy/peering/tailscale-acl.example.json`](../../deploy/peering/tailscale-acl.example.json) |
| **User surface** | CLI only: `python3 -m pipeline.peering status \| opt-in \| opt-out \| promote` |
| **Units** | `jellyflam3-syncthing.service`, `jellyflam3-peering.service` under [`deploy/systemd/`](../../deploy/systemd/) |

## What may be synced (locked)

| Tier | Rule |
|---|---|
| **Now (Phase 2 DoD)** | Peer sync is limited to **`*.flam3`** genomes and optional companion **`*-poster.jpg`** posters when present. No MP4, no scratch, no secrets, no Jellyfin DB, **no** `*.jellyflam3.json` / pedigree sidecars over Syncthing. |
| **Eventually** | Further restrict sharing to **pedigree-generated sheep** — genomes **uniquely generated on that JellyFlam3 server** (mutate / cross / random / local breed), **not** re-shares of Electric Sheep archive Free Sheep downloads. Origin metadata (sidecar local-only) marks `origin: local_pedigree` vs `origin: archive` **on the breeding host only**. |

**Locked — no cross-host lineage:** pedigree sidecars stay on the host that bred them. Gated promote moves `.flam3` (+ optional poster) only; it does **not** copy, recreate, or invent `*.jellyflam3.json` / parent lists / `origin` on the receiver. A peered sheep is furnace feedstock on the far side, not a continued pedigree child. Do not treat missing remote sidecars as a bug or Phase 2 debt.

`.stignore` (managed) must enforce that allowlist — template: [`deploy/peering/stignore`](../../deploy/peering/stignore). Use **include-first** Syncthing form (`!*.flam3`, `!*-poster.jpg`, then `*`); putting `*` above the includes leaves the folder empty. Eventual pedigree-only filter is host-service / folder selection policy (`genomes/peers/share-out` contains only eligible genomes when that policy is on).

Received peers still pass **sheep tax** ([06](06_SHEEP_TAX.md)) before gated promote.

**Phase 3:** pre/post share **integrity** — Ed25519 preferred, SHA-256 fallback — see [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md). Use `peering publish` / `promote` (verify before tax). Not required for Phase 2 DoD.

## Privacy — Opt Out by default

| Rule | Detail |
|---|---|
| Default | Sharing/peering **off** — Tailscale flock node inactive (or logged out), Syncthing **stopped/disabled**, `share_opt_in: false` |
| User action | **Opt In** or **Opt Out** via host service only (CLI) |
| Shared | **`*.flam3`** + optional **`*-poster.jpg`** (see tiers above) |
| Receive | Land in `genomes/peers/inbox`; **sheep tax** then **gated** promote to worker inbox (no auto-drain on first connect) |
| Transport | Tailscale tailnet only for peer Syncthing; do not rely on global discovery for flock share |
| Secrets | Never commit Tailscale auth keys, Syncthing API keys, or device IDs with private material |

Internal ack: `genomes/peers/OPT_IN` plus `/var/lib/jellyflam3/peering_status.json` after successful Opt In.

## Pi → Pi receive path (locked)

When Pi **A** drops an allowed file into its Syncthing share and Pi **B** is Opt-In on the same flock mesh:

| Stage | Path on receiving Pi (**B**) | Who acts |
|---|---|---|
| **1. Land** | `genomes/peers/inbox/` (`*.flam3`, optional `*-poster.jpg`) | Syncthing only |
| **2. Gate** | Still in `genomes/peers/inbox/` until operator runs promote | **No** automatic drain |
| **3. Promote** | Sheep tax → move to `genomes/inbox/` (companion `{stem}-poster.jpg` moves alongside when present); tax fail → `genomes/quarantine/` | `python3 -m pipeline.peering promote --apply` |
| **4. Render** | Worker polls **`genomes/inbox/` only** | `pipeline.worker` / `jellyflam3-worker` |

**Important:** a newly synced peer genome does **not** enter the render queue by itself. The worker never watches `genomes/peers/inbox`. Until gated promote `--apply`, files sit in the peers land folder with no furnace pickup.

```text
  Pi A: genomes/peers/inbox/foo.flam3
           │  Syncthing (Tailscale)
           ▼
  Pi B: genomes/peers/inbox/foo.flam3     ← land (idle for worker)
           │  promote --apply (+ sheep tax)
           ▼
  Pi B: genomes/inbox/foo.flam3           ← worker may render
```

## Commands

```bash
# One-time: install packages + copy units — see deploy/peering/README.md
cd /opt/jellyflam3-server
python3 -m pipeline.peering status --config configs/jellyflam3.yaml
python3 -m pipeline.peering opt-in --config configs/jellyflam3.yaml
python3 -m pipeline.peering opt-out --config configs/jellyflam3.yaml

# Gated promote (list only by default)
python3 -m pipeline.peering promote --config configs/jellyflam3.yaml
python3 -m pipeline.peering promote --config configs/jellyflam3.yaml --apply
# Lab only: bypass tax (not DoD sign-off)
python3 -m pipeline.peering promote --config configs/jellyflam3.yaml --apply --skip-tax
```

## Opt In (host service)

On **Opt In**, the host service SHALL:

1. **Create or obtain** the Tailscale auth path — **pre-auth key** `TS_AUTHKEY` (documented in `deploy/peering/`).
2. **Enroll** this device on the flock tailnet (`tailscale up --auth-key=… --advertise-tags=tag:jellyflam3`).
3. **Apply** the right **tags** and ensure **ACLs** allow Syncthing only among intended JellyFlam3 peers (`tag:jellyflam3`).
4. **Write** managed `.stignore` under `genomes/peers/inbox` (`*.flam3` + optional `*-poster.jpg`).
5. **Start** Syncthing (`jellyflam3-syncthing.service`) with HOME under `/var/lib/jellyflam3/syncthing`.
6. **Record** Opt-In ack + `peering_status.json`; surface in `status_report.sh` / `healthcheck.sh`.

**Out of scope for Opt In today:** creating folder id `jellyflam3-peers-inbox`, adding peer device IDs / Tailscale `tcp://100.x:22000` addresses, introducer flags, or discovery/relay hardening. Those are the one-time mesh introduce in [`deploy/peering/README.md`](../../deploy/peering/README.md#syncthing-first-time-mesh-introduce-lab-runbook).

## Opt Out (host service)

On **Opt Out**, the host service SHALL:

1. **Stop** Syncthing and **disable** `jellyflam3-syncthing` / `jellyflam3-peering`.
2. **Logout** Tailscale (`tailscale logout`, fallback `tailscale down`).
3. **Remove** Opt-In ack; refresh status file.
4. Leave genome **files** on disk (Opt Out ≠ Shears wipe).

## Gated promote + sheep-tax handoff

| Step | Behavior |
|---|---|
| Land | Syncthing writes `*.flam3` (and optional `*-poster.jpg`) into `genomes/peers/inbox` |
| Tax | [06](06_SHEEP_TAX.md) `pipeline.sheep_tax.scan_file` (`sheep_tax.on_peer_promote`) |
| Gate | `python3 -m pipeline.peering promote` **lists** only unless `--apply` |
| Fail | Quarantine under `genomes/quarantine` (when tax returns not ok) |
| Pass | Move genome into `genomes/inbox` for the render worker; move companion `{stem}-poster.jpg` alongside when present |
| Bypass | Lab-only `--skip-tax` (not DoD sign-off) |

**No silent queue flood** on Opt In or on Syncthing land — promote is always an explicit operator (or later timer) action. Syncthing land ≠ worker ingest.

**Deferred revisit (Phase 4):** whether the peer share path should stay **stage → `peers/inbox` → gated `promote --apply`**, or whether land may auto-promote / otherwise change. Until then, gated promote remains the locked Phase 2 contract — see [../phase4/01_PEER_SHARE_PATH.md](../phase4/01_PEER_SHARE_PATH.md).

## Smoke test

**Ready for lab:** fixture promote with tax → Opt In units → multi-host land + gated promote. Do not treat `--skip-tax` as DoD sign-off.

### A. Fixture (single host)

```bash
cd /opt/jellyflam3-server
python3 -m pipeline.peering ensure-layout --config configs/jellyflam3.yaml
# Prefer git pedigree smoke seed (not archive Free Sheep)
cp genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3 \
  genomes/peers/inbox/smoke_peer.flam3
# Confirm .stignore ignores a fake mp4:
touch genomes/peers/inbox/should_ignore.mp4
python3 -m pipeline.peering promote --config configs/jellyflam3.yaml   # list + tax status
python3 -m pipeline.peering promote --config configs/jellyflam3.yaml --apply
test -f genomes/inbox/smoke_peer.flam3 && echo SMOKE_PROMOTE_OK
# Optional: remove from worker inbox if you do not want an immediate render
# mv genomes/inbox/smoke_peer.flam3 /tmp/
```

### B. Multi-host flock mesh (lab)

Smoked on `16a` / `08a` / `04a` (2026-08-11):

1. Apply `deploy/peering/tailscale-acl.example.json` on the tailnet; create tagged pre-auth key(s) → `TS_AUTHKEY` per host (`secrets.env`, never commit).
2. On each Pi: install Tailscale + Syncthing units; `opt-in`.
3. **One-time Syncthing mesh introduce** (manual today) — full runbook: [`deploy/peering/README.md`](../../deploy/peering/README.md#syncthing-first-time-mesh-introduce-lab-runbook):
   - `export HOME=/var/lib/jellyflam3/syncthing`
   - Harden: `global-ann-enabled` / `relays-enabled` / `natenabled` → `false`
   - Collect `syncthing --device-id` + `tailscale ip -4` per host (host-local table; do not commit)
   - Folder id `jellyflam3-peers-inbox`, absolute peers-inbox path, Send & Receive
   - Add devices + folder via `syncthing cli config … add-json` with `tcp://100.x:22000` (prefer over GUI / flaky `--addresses`)
   - Optional: mark one host introducer (lab: `16a`) to ease later joins
4. Drop a `.flam3` (optional `*-poster.jpg`) on device A; confirm it **lands** on B/C under `genomes/peers/inbox` and is **not** yet in `genomes/inbox` / not claimed by the worker.
5. On a receiver: run gated `promote --apply`; confirm move to `genomes/inbox` (then worker may render if idle-gate allows).

## First-time mesh vs day-to-day (locked)

| Concern | Who | When |
|---|---|---|
| Tailscale enroll / logout | `pipeline.peering opt-in` / `opt-out` | Every Opt In / Out |
| `.stignore` write + Syncthing unit start/stop | host service | Every Opt In / Out |
| Tailscale / Syncthing stay-alive while Opt In | `pipeline.tailscale_watch` + `cron_tailscale_watch.sh` | Poll (~5 min); if LAN gateway unreachable, rate-limited Wi‑Fi bounce; then heal `tailscaled` + `tailscale up` + Syncthing unit |
| Folder create + peer introduce + discovery harden | **Operator** (CLI/GUI runbook) | **Once** per host / new peer |
| Gated promote | Operator (`promote --apply`) | Whenever land should enter the furnace |

Scripting options to shrink the one-time mesh introduce are listed in [`deploy/peering/README.md`](../../deploy/peering/README.md#scripting-options-deferred--phase-4) — **deferred to Phase 4** (not Phase 2/3 debt; no mesh admin UI now).

## Guidelines

1. Templates live under [`deploy/peering/`](../../deploy/peering/) + systemd units in [`deploy/systemd/`](../../deploy/systemd/).
2. Document Raspberry Pi OS install path for `tailscaled` + Syncthing in [09](09_PI_FROM_SCRATCH.md).
3. Host service stays small: Opt In / Opt Out / status / promote; no mesh admin UI in Phase 2. One-time mesh introduce stays an operator runbook (or optional later CLI) — not day-to-day UX.
4. License: private flock peering; not republication. Eventual pedigree-only share avoids redistributing archive Free Sheep as if they were local originals.
5. Idle-gate / furnace: peering sync is light; still avoid shipping secrets. Do not open Syncthing relays to the public Internet for this folder.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/peering.py` | pipeline | Host service: status / opt-in / opt-out / promote |
| `pipeline/tailscale_watch.py` | pipeline | Opt-In watchdog: LAN/Wi‑Fi heal + Tailscale / Syncthing restart when share not live |
| `scripts/cron_tailscale_watch.sh` | cron | Fleet crontab wrapper for the watchdog |
| `deploy/systemd/jellyflam3-peering.service` | deploy | Peering host-service unit |
| `deploy/systemd/jellyflam3-syncthing.service` | deploy | Managed Syncthing lifecycle |
| `deploy/peering/stignore` | config | `*.flam3` + `*-poster.jpg` share template |
| `deploy/peering/tailscale-acl.example.json` | config | `tag:jellyflam3` ACL example |
| `tailscale` | binary | Private underlay / Opt In enrollment |
| `syncthing` | binary | Application sync of peer genomes |
| `secrets.env` (`TS_AUTHKEY`) | config | Pre-auth key for Opt In |
| `pipeline/sheep_tax.py` | pipeline | Tax gate on promote (quarantine fails) |

## Exit criteria

- [x] Clean model documented (host service / Tailscale / Syncthing) — this guide
- [x] Opt In sequence specified: auth → enroll → tags/ACLs → managed Syncthing start
- [x] Opt Out sequence specified: stop Syncthing → revoke/remove tailnet node → clean credentials → disable services
- [x] Sync limited to **`*.flam3` + optional `*-poster.jpg`** in templates / `.stignore`
- [x] Eventual pedigree-only share policy documented (origin tagging; not required for first smoke)
- [x] `deploy/` templates (Tailscale ACL/tag notes + Syncthing managed config + `.stignore`) in repo
- [x] User-facing surface is **only** Opt In / Opt Out (+ status / gated promote); no day-to-day peer ID chores (first-time mesh introduce is a separate operator runbook)
- [x] Smoke test (device + folder fixture) — promote + sheep tax on `rpi-jellyflam3-08a` 2026-08-08; **3-Pi mesh** land + gated promote 2026-08-11 (`16a`/`08a`/`04a`)
- [x] Gated promote + sheep-tax handoff specified (no silent queue flood; land ≠ worker ingest)
- [x] First-time Syncthing folder/device introduce documented (`deploy/peering/README.md`) + scripting options noted (not required for DoD)
- [x] Config example keys in `jellyflam3.yaml.example`

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-08 | [x] |

Guide 05 complete for Phase 2 DoD. Lab flock mesh (3-Pi Opt In + Syncthing + gated promote) smoked 2026-08-11.

## See also

[06_SHEEP_TAX.md](06_SHEEP_TAX.md) · [07_PEDIGREE_BREEDING.md](07_PEDIGREE_BREEDING.md) · [`deploy/peering/README.md`](../../deploy/peering/README.md) · Architecture in [Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md).
