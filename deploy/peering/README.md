# JellyFlam3 peering deploy templates (Phase 2 guide 05)

## Locked choices (lab DoD)

| Decision | Choice |
|---|---|
| User surface | CLI: `python3 -m pipeline.peering {status\|opt-in\|opt-out\|publish\|promote\|gen-keys\|trust-key}` |
| Tailscale auth | **Pre-auth key** in `secrets.env` as `TS_AUTHKEY` (never commit) |
| Tag | `tag:jellyflam3` (see `tailscale-acl.example.json`) |
| Syncthing share | Folder root = `genomes/peers/inbox` (config `peering.peers_inbox`); `.stignore` = this directory’s `stignore` |
| Sync glob | `*.flam3` + optional `*-poster.jpg` + integrity sidecars (`*.flam3.sha256`, `*.flam3.jellyflam3.sig`) |
| Share security | Ed25519 preferred; SHA-256 fallback — see [phase3/05](../../docs/phase3/05_SHARED_SHEEP_SECURITY.md) |
| Default | **Opt Out** — Syncthing unit disabled; no Tailscale flock enroll |

## Install packages (Raspberry Pi OS)

```bash
# Tailscale — https://tailscale.com/download/linux
curl -fsSL https://tailscale.com/install.sh | sh

# Syncthing
sudo apt-get update
sudo apt-get install -y syncthing
```

## One-time unit install

```bash
sudo mkdir -p /var/lib/jellyflam3/syncthing
sudo chown -R jellyflam3:jellyflam3 /var/lib/jellyflam3/syncthing

sudo cp /opt/jellyflam3-server/deploy/systemd/jellyflam3-syncthing.service /etc/systemd/system/
sudo cp /opt/jellyflam3-server/deploy/systemd/jellyflam3-peering.service /etc/systemd/system/
sudo systemctl daemon-reload
# Do NOT enable syncthing until Opt In — default Opt Out
```

## Operator flow

```bash
# Admin: create tagged pre-auth key in Tailscale console; put in secrets.env:
#   TS_AUTHKEY=tskey-auth-...
# Apply ACL fragment from tailscale-acl.example.json

cd /opt/jellyflam3-server
python3 -m pipeline.peering status --config configs/jellyflam3.yaml
python3 -m pipeline.peering opt-in --config configs/jellyflam3.yaml
python3 -m pipeline.peering status --config configs/jellyflam3.yaml

# Optional fleet watchdog (every 5 min) — heal Tailscale/Syncthing when Opt In but not live:
#   */5 * * * *  /opt/jellyflam3-server/scripts/cron_tailscale_watch.sh \
#       >>/var/log/jellyflam3/tailscale_watch.log 2>&1
# Manual: python3 -m pipeline.tailscale_watch --json

# One-time (per host / new peer): Syncthing folder + device introduce
# — see “Syncthing first-time mesh introduce” below. Opt In alone does not mesh.

# Peer land: Syncthing writes into genomes/peers/inbox only.
# The render worker does NOT watch that folder — promote is required.
# Promote verifies share-security sidecars (then sheep tax) before move.
python3 -m pipeline.peering gen-keys --config configs/jellyflam3.yaml
python3 -m pipeline.peering publish /path/to/sheep.flam3 --config configs/jellyflam3.yaml --apply
python3 -m pipeline.peering promote --config configs/jellyflam3.yaml   # dry listing
python3 -m pipeline.peering promote --config configs/jellyflam3.yaml --apply
# After --apply: genomes/inbox (worker may pick up) or genomes/quarantine (security/tax fail)
# Peer pubs: python3 -m pipeline.peering trust-key /path/to/peer.pub --name peer08a

# Lab smoke (Phase 3 guide 05) — pedigree throwaways; fleet matrix from Windows:
#   powershell -NoProfile -File scripts/lab_smoke05_fleet.ps1
# On-Pi helper (sys.path auto-fixed; optional PYTHONPATH=/opt/jellyflam3-server):
#   python3 scripts/lab_smoke05_local.py setup

python3 -m pipeline.peering opt-out --config configs/jellyflam3.yaml
```

### Receive path (Pi → Pi)

| Stage | Location | Auto? |
|---|---|---|
| Syncthing land | `genomes/peers/inbox` | Yes (when Opt In + mesh) |
| Sheep tax + promote | → `genomes/inbox` or `genomes/quarantine` | **No** — `promote --apply` |
| Render | worker polls `genomes/inbox` | Yes (after promote) |

See [guide 05 — Pi → Pi receive path](../../docs/phase2/05_SYNCTHING_GENOME_PEERING.md#pi--pi-receive-path-locked).

## What Opt In does *not* configure

`python3 -m pipeline.peering opt-in` enrolls Tailscale, writes managed `.stignore`, and
starts `jellyflam3-syncthing`. It does **not**:

- create the Syncthing folder
- add peer devices / addresses
- mark an introducer
- disable public discovery / relays / NAT announce

Those are a **one-time mesh introduce** per host (or per new peer). Day-to-day Opt
In / Opt Out only start/stop units; they do not re-paste device IDs when the mesh
config already exists under `HOME=/var/lib/jellyflam3/syncthing`.

## Syncthing first-time mesh introduce (lab runbook)

Always set Syncthing’s managed HOME before any `syncthing` / `syncthing cli` call:

```bash
export HOME=/var/lib/jellyflam3/syncthing
# Config: $HOME/.local/state/syncthing/config.xml (Syncthing ≥1.27 layout)
# GUI (loopback only): http://127.0.0.1:8384
```

### Locked folder contract

| Field | Value |
|---|---|
| Folder id | `jellyflam3-peers-inbox` |
| Label | `jellyflam3-peers-inbox` (any label OK) |
| Path | **absolute** peers inbox — lab: `/home/jellyflam3/GitHub/jellyflam3-server/genomes/peers/inbox` (same tree as `/opt/jellyflam3-server` via symlink) |
| Type | Send & Receive |
| Ignore | managed `genomes/peers/inbox/.stignore` (from `deploy/peering/stignore`) |

### Hardening (Tailscale underlay)

Prefer explicit Tailscale dial addresses; do **not** rely on public Syncthing discovery:

```bash
export HOME=/var/lib/jellyflam3/syncthing
syncthing cli config options global-ann-enabled set false
syncthing cli config options relays-enabled set false
syncthing cli config options natenabled set false
# optional: local-ann-enabled false if every peer has an explicit tcp://100.x:22000
```

### Collect device IDs + Tailscale IPs (each host)

```bash
export HOME=/var/lib/jellyflam3/syncthing
syncthing --device-id
tailscale ip -4
hostname
```

Keep the flock table **host-local** (notes / operator file). Do **not** commit device
IDs or Tailscale IPs to git.

### Add devices + shared folder (`add-json` preferred)

Syncthing’s `config devices add --addresses …` has been flaky in lab; use **`add-json`**.

On **each** host (example placeholders — substitute real IDs/IPs):

```bash
export HOME=/var/lib/jellyflam3/syncthing
FOLDER_ID=jellyflam3-peers-inbox
FOLDER_PATH=/home/jellyflam3/GitHub/jellyflam3-server/genomes/peers/inbox
MY_ID=$(syncthing --device-id)

# For each *other* peer:
syncthing cli config devices add-json <<EOF
{
  "deviceID": "PEER_DEVICE_ID",
  "name": "rpi-jellyflam3-XXa",
  "addresses": ["tcp://100.x.y.z:22000"],
  "introducer": false
}
EOF

# Create folder once (share with all peer device IDs):
syncthing cli config folders add-json <<EOF
{
  "id": "$FOLDER_ID",
  "label": "$FOLDER_ID",
  "path": "$FOLDER_PATH",
  "type": "sendreceive",
  "devices": [
    {"deviceID": "$MY_ID"},
    {"deviceID": "PEER_A_DEVICE_ID"},
    {"deviceID": "PEER_B_DEVICE_ID"}
  ]
}
EOF
```

**Introducer (recommended):** mark **one** stable host (lab: `16a`) with
`"introducer": true` on the device entries *other* peers have for it. New Opt-In
hosts then learn the rest of the flock from the introducer after a single mutual
introduce with that host — still a one-time accept, not zero-touch.

### Verify mesh

```bash
export HOME=/var/lib/jellyflam3/syncthing
syncthing cli config folders list
syncthing cli config devices list
syncthing cli show connections
# expect connected peers == N-1 for an N-host flock
```

Drop a test `*.flam3` into peers inbox on one host; confirm it **lands** on others
under `genomes/peers/inbox` and is **not** in `genomes/inbox` until `promote --apply`.

GUI alternative: SSH tunnel to `127.0.0.1:8384` and add the same folder/devices
(still prefer Tailscale `tcp://100.x:22000` addresses).

## Scripting options (deferred — Phase 4)

**Do not implement during Phase 3 feature work.** Revisit when Phase 4 opens — see [docs/phase4/02_MESH_INTRODUCE_SCRIPTING.md](../../docs/phase4/02_MESH_INTRODUCE_SCRIPTING.md) and [docs/phase4/00_OVERVIEW.md](../../docs/phase4/00_OVERVIEW.md). Until then, use the manual runbook above.

| Option | What it would do | Notes |
|---|---|---|
| **A. Local folder ensure** | Extend `opt-in` (or `peering ensure-mesh-local`) to create folder `jellyflam3-peers-inbox`, write `.stignore`, apply discovery harden flags via `syncthing cli` | Safe automation; no cross-host secrets |
| **B. Peer list file** | Host-local JSON/YAML of `{name, deviceID, tailscaleIP}` (gitignored); CLI `mesh-join --peers-file=…` runs `add-json` for devices + folder shares | Best lab DX; never commit the file |
| **C. Introducer-assisted join** | New host only introduces to one introducer device ID; Syncthing propagates the rest | Still needs one mutual introduce + folder accept |
| **D. Stay manual** | Keep this runbook; Opt In/Out remain lifecycle only | **Current stance** through Phase 3; revisit in Phase 4 |

Also deferred with the same revisit: whether gated promote (land ≠ worker ingest) should stay explicit or change (e.g. auto-promote / timer).

**Non-goals (still):** mesh admin UI; committing device IDs; re-opening global discovery/relays for flock share.

## Smoke test (fixture)

See [docs/phase2/05_SYNCTHING_GENOME_PEERING.md](../../docs/phase2/05_SYNCTHING_GENOME_PEERING.md#smoke-test).
