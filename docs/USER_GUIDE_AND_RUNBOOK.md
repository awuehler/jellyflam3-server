# JellyFlam3 — User Guide & Operator Runbook

One document, **three layers**. Pick your layer and stay there — you should not need to read the whole file.

| Layer | Audience | You want to… |
|---|---|---|
| **[Layer 1 — End user](#layer-1--end-user)** | Household / viewer | Watch ambient loops, use Roku or Kodi screensaver, fix “nothing plays” without SSH |
| **[Layer 2 — Operator](#layer-2--operator-runbook)** | Pi owner / homelab operator | Keep the flock healthy, seed/breed/delete sheep, peering, health gates, fleet updates |
| **[Layer 3 — Contributor](#layer-3--contributor)** | Developer / maintainer | Run tests, change pipeline code, CI, deploy conventions |

**Terms:** [glossary.md](glossary.md) · **Architecture (SoT):** [Pi5_Flam3_VoD_Pipeline.md](Pi5_Flam3_VoD_Pipeline.md) · **Install from zero:** [phase2/09_PI_FROM_SCRATCH.md](phase2/09_PI_FROM_SCRATCH.md)

---

## Layer 1 — End user

### What you have

JellyFlam3 is a **home dream engine**: a Raspberry Pi renders flame-fractal “sheep” into MP4 loops, stores them in a **Jellyfin** library, and your **Roku** or **Kodi** device plays them when the TV is idle. Rendering is slow (hours per sheep on a Pi); playback is fast.

You do **not** need the Pi terminal for normal viewing.

### Watch on Roku (VoD channel)

**First time on a Roku (one-time setup per TV):**

1. Sideload the JellyFlam3 VoD channel zip (e.g. `dist/jellyflam3-roku.zip` from `scripts/package_roku_channel.*` on a furnace Pi).
2. **Furnace-built zips are pre-configured:** when packaged on a Pi with `secrets.env`, the zip includes that furnace’s Jellyfin URL, API key, user id, and library id. Launch the channel — credentials apply on first run if the registry is empty; the flock list should load without manual paste.
3. **Otherwise** (Windows packaging host or empty registry): open the channel → **Settings** → enter Jellyfin connection values. An operator runs `python3 scripts/jellyfin_id_dump.py` on the Pi and gives you `baseUrl`, `apiKey`, `userId`, `libraryId` (never share the API key in chat/email — paste on the TV only) → save Settings.

**Everyday use:** launch JellyFlam3 → pick a sheep → ambient loop plays. When you press **Play**, the Pi **stops rendering** new sheep until the TV has been idle for several minutes (see [idle gate](#idle-gate-behavior) below).

**Deep link smoke (optional):** after an operator dumps item Guids (`jellyfin_id_dump.py --items`), a specific sheep can be launched with `contentId=<Guid>` via the Roku ECP port (developer mode).

### Roku Screensaver / Backdrop

The screensaver is a **separate sideload package** (`jellyflam3-screensaver.zip`). It shows stills/posters — no video node (Roku policy).

**Credentials:** Screensaver **reads** the same `JellyFlam3` registry keys as VoD. A **furnace-built** screensaver zip also ships `registry/jellyflam3-presets.json` and applies the same Jellyfin values on first run when keys are empty. Otherwise install VoD on that Roku **first** and save Settings once (or paste manually in VoD Settings). Screensaver Settings only adjusts fade/dwell — it has no credential editors.

**Enable:** sideload screensaver zip → on Roku go to **Settings → Theme → Screensavers** → select JellyFlam3.

**Developer-mode note:** only **one** sideload slot. Installing screensaver **replaces** VoD until you re-sideload VoD. Registry keys survive the swap.

**While screensaver runs:** the Pi idle gate should stay **open** (rendering may continue). Operator verifies with `cat /var/lib/jellyflam3/idle_gate_status.json`.

### Kodi Electric Sheep screensaver (optional)

Video screensaver add-on **JellyFlam3 Dreams** (`screensaver.jellyflam3`) — plays Jellyfin flock MP4s when Kodi idles. Separate from Roku stills; loops-only MVP (edge journeys planned post-launch). Detail: [phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md).

**First time on the Kodi box:**

1. Operator packages and copies `dist/screensaver.jellyflam3.zip` to the Kodi Pi (see [Kodi screensaver upgrade](#kodi-screensaver-upgrade-operator)).
2. Kodi → **Add-ons → Install from zip file** → pick the zip from **Downloads** (LibreELEC) or wherever it was copied.
3. **Settings → Interface → Screensaver** → **JellyFlam3 Dreams**.
4. **Configure Jellyfin** — if the zip was built on a furnace Pi (`package_kodi_screensaver.*`), defaults are already in the add-on settings. Otherwise open **Add-ons → My add-ons → Screensaver → JellyFlam3 Dreams → Configure** and paste Jellyfin URL, API key, user id, library id (operator runs `jellyfin_id_dump.py` on the furnace Pi).
5. Set screensaver wait time (e.g. **1 minute** for testing), then wait or use **Activate screensaver**.

**Everyday use:** leave Kodi idle; any keypress exits the screensaver (Kodi default). When flock is configured, sheep MP4s shuffle; if Jellyfin is unreachable, you see a short hint on black (no test-pattern video).

**Upgrade (on the TV, no PC):** if the operator already dropped a new zip into Downloads, Kodi → **Add-ons → Install from zip file** → select the new `screensaver.jellyflam3.zip`. Jellyfin settings in add-on **Configure** are kept (`addon_data`).

**While screensaver runs:** furnace idle gate should stay **open** (Client=`JellyFlam3-Screensaver` is ignored). Operator verifies on the Pi: `cat /var/lib/jellyflam3/idle_gate_status.json`.

### What to expect

| Expectation | Reality |
|---|---|
| New sheep appear quickly | **No** — each MP4 can take hours to days on a Pi |
| Gate closes while you watch | **Yes** — by design; furnace waits for idle |
| Screensaver shows video | **No** on Roku SS — images only |
| Gold Sheep / paid ES masters | **Never** ingested — personal viewing only |

### End-user triage (no SSH)

| Symptom | What to try | Escalate to operator when… |
|---|---|---|
| VoD Settings blank / flock empty | Re-open VoD Settings; confirm Wi‑Fi; re-enter IDs from a fresh dump | IDs correct but list still empty |
| “Cannot connect” on Roku | Confirm `baseUrl` is the Pi’s **LAN IP** (`http://192.168.x.x:8096`), not `127.0.0.1` | Jellyfin down on Pi |
| Playback stutters / buffers | Prefer Direct Play (H.264 MP4); avoid forcing transcode in client | Persistent transcode hammering Pi |
| Screensaver blank | VoD was never configured on **this** Roku | After VoD Settings saved, still blank |
| Screensaver “replaced” VoD | Re-sideload VoD channel zip | — |
| Kodi screensaver black / hint text | Open add-on **Configure**; confirm Jellyfin URL is furnace **LAN IP**, not `127.0.0.1` | Settings correct but no sheep play |
| Nothing new for days | Normal if gate was closed or inbox empty | Gate open + inbox empty for a week |

---

## Layer 2 — Operator runbook

### Install path and hosts

| Item | Value |
|---|---|
| Canonical install | `/opt/jellyflam3-server` (symlink from clone) |
| Config | `configs/jellyflam3.yaml` + `secrets.env` (**never commit**) |
| Example fleet hosts | `rpi-jellyflam3-16a`, `-08a`, `-04a` — assign each a LAN IP (e.g. `192.168.X.Y`) |
| Kodi pasture host | e.g. `rpi-kodi-08a` at `<Kodi_IP_Address>` (LibreELEC; no furnace worker) |
| Hostname class | `rpi-jellyflam3-{16,08,04}a` — run `python3 -m pipeline.hw_profile apply {16a\|08a\|04a}` |

Full bring-up: [phase2/09_PI_FROM_SCRATCH.md](phase2/09_PI_FROM_SCRATCH.md) · staged checklist: `./scripts/bringup_check.sh` (FAIL → exit 1; `--strict` also fails on WARN).

### Daily health (5 minutes)

Run on each Pi (or spot-check one representative host):

```bash
cd /opt/jellyflam3-server
git log -1 --oneline                    # know what rev is live
./scripts/healthcheck.sh                # exit 0 = healthy; exit 1 = investigate
./scripts/status_report.sh              # flock/inbox/thermals snapshot
cat /var/lib/jellyflam3/idle_gate_status.json | python3 -m json.tool
```

**Gate scripts fail closed:** missing tools, bad units, missing idle-gate status, broken config, or **Opt In without live Syncthing + Tailscale** → non-zero exit. See [phase3/10_TESTING_AND_ACCEPTANCE.md](phase3/10_TESTING_AND_ACCEPTANCE.md).

Optional deeper checks:

```bash
./scripts/perf_healthcheck.sh           # thermals + disk microbench
./scripts/perf_healthcheck.sh --quick
python3 -m pytest tests/ -q             # ~3s unit suite on Pi
```

### Systemd services

```bash
systemctl is-active jellyflam3-worker jellyflam3-idlegate jellyfin
# Optional (guide 04 F): jellyflam3-display-sink
sudo systemctl enable --now jellyflam3-idlegate jellyflam3-worker
```

Units assume `WorkingDirectory=/opt/jellyflam3-server`. Missing symlink → `CHDIR` errors in journal.

### Idle gate behavior

- **Closes** when Jellyfin sees TV-class **Playing** or **Transcoding**.
- **Opens** after `idle_delay_sec` (default ~10 min) with no blockers.
- JellyFlam3 Roku **1.0.9+** reports playback via Jellyfin Sessions API so Direct Play closes the gate.
- Status file: `/var/lib/jellyflam3/idle_gate_status.json` — fields `gate`, `reason`, `seconds_until_resume`.

```bash
python3 -m pipeline.idle_gate --config configs/jellyflam3.yaml   # foreground debug
```

Screensaver client pattern `JellyFlam3-Screensaver` is **ignored** by the gate (by design).

### Feed the furnace

The **worker** polls `genomes/inbox` for `.flam3` files, renders to `/media/sheep/by-generation/`, and archives successful genomes to `genomes/done`.

**Manual seed (archive Free Sheep):**

```bash
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml \
  --archive --fetch-count 1
# Default skips sheep already in catalog (--skip-catalog); override with --no-skip-catalog
```

**Pedigree breed (local genetics):**

```bash
python3 -m pipeline.breed mutate --parent genomes/done/electricsheep.247.00505.flam3
python3 -m pipeline.breed cross --parent0 ... --parent1 ... --method alternate
python3 -m pipeline.worker --config configs/jellyflam3.yaml --once path/to/new.flam3
```

**Scheduled feedstock (cron on Pi):**

| Cron | Script | Role |
|---|---|---|
| `11 5 * * *` | `scripts/cron_breed_idle.sh` | Daily idle breed when inbox empty |
| Staggered DOM | `scripts/cron_archive_seed.sh` | ~10-day archive seed per host |

Both prepend `/usr/local/bin` for `flam3-*`. Missing real config → **exit 1** (no silent `.yaml.example` fallback).

**Smoke one pedigree sheep (never publishes to catalog):**

```bash
export JELLYFLAM3_SMOKE=1
./scripts/smoke_render.sh
# Success token: SMOKE_RENDER_OK
```

### Curator: Sheep Shears (per-sheep)

Always **dry-run first**. Confirm token is exactly `DELETE`.

```bash
python3 -m pipeline.shears delete electricsheep.247.00505
python3 -m pipeline.shears delete electricsheep.247.00505 --confirm DELETE

python3 -m pipeline.shears add path/to/sheep.flam3          # copy to inbox
python3 -m pipeline.shears modify genomes/done/sheep.flam3  # re-furnace

python3 -m pipeline.shears audit
python3 -m pipeline.shears sweep --orphans-only --confirm DELETE
```

Cascade removes catalog MP4/sidecar/poster, jobs, edges (best-effort), Jellyfin item (soft-fail), peer copies when Opt In. Does **not** touch secrets or Syncthing device config.

### Quality repair: Sheep refactor

For sub-standard renders (palette clash, bad encode) — **not** delete/recreate genetics.

```bash
python3 -m pipeline.refactor scan --config configs/jellyflam3.yaml
python3 -m pipeline.refactor report --id electricsheep.247.00505

python3 -m pipeline.refactor preview --id electricsheep.247.00505 --preview-poster
python3 -m pipeline.refactor apply --id electricsheep.247.00505              # dry-run
python3 -m pipeline.refactor apply --id electricsheep.247.00505 --confirm APPLY

python3 -m pipeline.refactor quarantine --id electricsheep.247.00505 --confirm QUARANTINE
python3 -m pipeline.refactor batch --failing --limit 10 --dry-run
```

Preview lands under `media_library/_refactor-preview/` (Jellyfin-visible). Apply stages retinted genome to inbox; worker finishes async. Sidecar `refactor[]` history merges on ingest.

Pathways split in code: `refactor_scan`, `refactor_preview`, `refactor_history`, `refactor_actions` — CLI facade: `pipeline.refactor`.

### Nuclear reset: JellyFlam3 Hammer

Wipes **local** render I/O and catalog — not one sheep. Never touches secrets, git pedigree, or samples.

```bash
python3 -m pipeline.hammer --dry-run
python3 -m pipeline.hammer --all --force-stop --confirm HAMMER
```

Confirm token: `HAMMER` or hostname. Wrong token → exit 2, no deletes.

### Peering (optional multi-Pi)

Default: **Opt Out** (Syncthing off, Tailscale logged out). See [`deploy/peering/README.md`](../deploy/peering/README.md) and [phase2/05_SYNCTHING_GENOME_PEERING.md](phase2/05_SYNCTHING_GENOME_PEERING.md).

```bash
python3 -m pipeline.peering status --config configs/jellyflam3.yaml
python3 -m pipeline.peering opt-in --config configs/jellyflam3.yaml
python3 -m pipeline.peering publish path/to/sheep.flam3 --apply
python3 -m pipeline.peering promote --apply          # peers/inbox → worker inbox or quarantine
python3 -m pipeline.peering opt-out --config configs/jellyflam3.yaml
```

**Receive path:** Syncthing → `peers/inbox` → **`promote --apply`** → `genomes/inbox` or quarantine → worker.

#### Opt In vs share live (do not confuse them)

| State | Meaning |
|---|---|
| **Opt Out** (default) | No `genomes/peers/OPT_IN`. Syncthing unit should be **inactive**. No mesh sync. |
| **Opt In (`share_opt_in`)** | Operator ran `opt-in` (or left `OPT_IN` on disk). **Intent** to share genomes on the mesh. |
| **Share live (`share_live`)** | Opt In **and** **`jellyflam3-syncthing` active** **and** Tailscale **`Running` + `online`**. Genomes can actually move between Pis. |

**When Opt In is true, background sharing is assumed to work** — both Syncthing and Tailscale must be up. If either is down, you have **offline peering**: the marker says “share,” but nothing syncs.

`healthcheck.sh` probes **live** unit + Tailscale state (not stale JSON). On Opt In without live share:

```text
share_opt_in= True
syncthing_unit= inactive (live)
tailscale= NeedsLogin online=False
BAD share not live — syncthing unit inactive (expected active)
BAD share not live — tailscale not connected (NeedsLogin)
FIX: python3 -m pipeline.peering opt-in ... or opt-out to disable sharing
```

→ **exit 1** (fail closed). This is intentional: exit 0 must not imply mesh sync works.

**Status file:** `/var/lib/jellyflam3/peering_status.json` is refreshed during healthcheck. Use **`share_live`** and **`share_issues`** — do not trust an old `units.jellyflam3-syncthing: "active"` line if healthcheck says otherwise.

#### Fix offline peering

**A — Bring sharing online (keep Opt In):**

1. Set **`TS_AUTHKEY`** in `secrets.env` (pre-auth key from Tailscale admin), or log in interactively: `sudo tailscale up`.
2. Re-run opt-in (rolls back `OPT_IN` automatically if services still cannot start):

```bash
cd /opt/jellyflam3-server
python3 -m pipeline.peering opt-in --config configs/jellyflam3.yaml
python3 -m pipeline.peering status --config configs/jellyflam3.yaml
# Expect: share_opt_in true, share_live true, syncthing_unit active, tailscale Running online=True
systemctl is-active jellyflam3-syncthing jellyflam3-worker
./scripts/healthcheck.sh    # exit 0, line: OK share live (Syncthing + Tailscale)
```

3. Exchange trust keys between Pis (`peering gen-keys`, `trust-key`) before publish/promote shared genomes — see guide 05.

**B — Stop claiming Opt In (single-Pi / no mesh):**

```bash
python3 -m pipeline.peering opt-out --config configs/jellyflam3.yaml
./scripts/healthcheck.sh    # OK peering Opt Out; OK jellyflam3-syncthing inactive
```

**Note:** `opt-in` without `TS_AUTHKEY` and without a running Syncthing unit **does not** leave a dangling `OPT_IN` — the CLI rolls back the ack if `share_live` is false after the attempt.

**Lab fleet share-security matrix (Owner OK gate):**

```powershell
powershell -NoProfile -File scripts/lab_smoke05_fleet.ps1
# Exit 1 if any pathway FAIL; unit coverage in tests/test_peering.py
```

### Roku / Kodi packaging

**Prefer building on a furnace Pi** (`/opt/jellyflam3-server` with `secrets.env`). Each `package_*` script runs `client_pack_presets.py` first:

| Package | Pre-fill on furnace host |
|---|---|
| Roku VoD / Screensaver | `registry/jellyflam3-presets.json` in the zip; first launch writes empty `JellyFlam3` registry keys |
| Kodi screensaver | `resources/settings.xml` default values in the staged zip |

Each furnace Pi produces zips pointed at **its own** Jellyfin (`http://<that-pi-lan-ip>:8096`). Do not commit preset JSON or distribute zips outside the household — they contain the API key.

Kodi packaging needs **Pillow** (`python3-pil` via apt or `pip install -r requirements.txt`).

```bash
./scripts/package_roku_channel.sh          # VoD sideload zip
./scripts/package_roku_screensaver.sh      # Screensaver zip
./scripts/package_kodi_screensaver.sh      # Kodi add-on zip → dist/screensaver.jellyflam3.zip
python3 scripts/build_kodi_screensaver_assets.py   # optional: fanart + screenshot JPGs (Kodi script runs this automatically)
python3 scripts/jellyfin_id_dump.py --items --limit 50   # manual paste / verify only
```

Windows (operator workstation — **no** furnace presets; manual Settings paste on device):

```powershell
.\scripts\package_roku_channel.ps1
.\scripts\package_roku_screensaver.ps1
.\scripts\package_kodi_screensaver.ps1
python scripts\build_kodi_screensaver_assets.py
```

### Kodi screensaver upgrade (operator)

Kodi pasture box (e.g. **`rpi-kodi-08a`** at `<Kodi_IP_Address>`, LibreELEC). Jellyfin stays on a furnace Pi (e.g. `http://<RPi_IP_Address>:8096`).

**1 — Build the zip** on a **furnace Pi** (pre-fills Jellyfin settings for that host):

```bash
cd /opt/jellyflam3-server
./scripts/package_kodi_screensaver.sh
# Output: dist/screensaver.jellyflam3.zip
# Windows (no presets): .\scripts\package_kodi_screensaver.ps1
```

The packaging script runs `build_kodi_screensaver_assets.py` automatically. Optional: `--fetch-fleet` on that script pulls three `*-poster.jpg` files from fleet Pis 16a/08a/04a into store art.

**2 — Copy zip to the Kodi Pi**

| Method | Command / path |
|---|---|
| **SMB (LibreELEC default)** | Copy to `\\<Kodi_IP_Address>\Downloads\screensaver.jellyflam3.zip` (LibreELEC credentials: `libreelec` / `libreelec` unless changed). On-box path: `/storage/downloads/screensaver.jellyflam3.zip`. |
| **SCP (if key installed)** | `scp dist/screensaver.jellyflam3.zip root@<Kodi_IP_Address>:/storage/downloads/` |

PowerShell SMB example:

```powershell
net use \\<Kodi_IP_Address>\Downloads /user:libreelec libreelec
Copy-Item -Force dist\screensaver.jellyflam3.zip \\<Kodi_IP_Address>\Downloads\
net use \\<Kodi_IP_Address>\Downloads /delete
```

**3 — Install on Kodi**

1. Kodi → **Add-ons → Install from zip file** → navigate to **Downloads** → `screensaver.jellyflam3.zip`.
2. Confirm **Settings → Interface → Screensaver** still shows **JellyFlam3 Dreams** (re-select if needed).
3. Jellyfin settings in **Configure** are preserved under `/storage/.kodi/userdata/addon_data/screensaver.jellyflam3/` — re-enter only if URL/keys changed.

Alternative (Kodi stopped): unzip into `/storage/.kodi/addons/screensaver.jellyflam3/` (folder name must match add-on id).

**4 — Smoke after upgrade**

| Check | How |
|---|---|
| Version | Add-ons → My add-ons → Screensaver → JellyFlam3 Dreams → **Information** (version in `addon.xml`, e.g. `0.2.2+`). |
| Playback | Set short wait time → **Activate screensaver** or wait; sheep MP4s should shuffle. |
| Idle gate | On furnace Pi: `cat /var/lib/jellyflam3/idle_gate_status.json` → `"gate": "open"` while Kodi SS runs. |
| Jellyfin IDs | On furnace: `python3 scripts/jellyfin_id_dump.py --items --limit 5` — item count should be > 0 when flock is seeded. |

**5 — Configure / refresh Jellyfin settings** (first install or after credential rotation)

Map [jellyfin_id_dump.py](../scripts/jellyfin_id_dump.py) output → add-on **Configure**:

| Dump field | Add-on setting |
|---|---|
| `baseUrl` | Jellyfin URL (`server_url`) — **LAN IP** reachable from Kodi, not `127.0.0.1` |
| `apiKey` | API key |
| `userId` | User id |
| `libraryId` | Library (Parent) id |

See [kodi-screensaver/README.md](../kodi-screensaver/README.md) for setting ids and commercial-safe filter notes.

**Do not** edit `guisettings.xml` or `Addons33.db` while Kodi is running — LibreELEC overwrites on exit.

### Stills (screensaver feedstock)

```bash
python3 -m pipeline.stills --config configs/jellyflam3.yaml --dry-run
python3 -m pipeline.stills --config configs/jellyflam3.yaml --limit 5
# Output: by-generation/{gen}/stills/{stem}/frame_XX.jpg
```

### Fleet update

```bash
cd /opt/jellyflam3-server
git pull --ff-only
git log -1 --oneline
./scripts/ensure_exec_bits.sh --check     # or ./scripts/ensure_exec_bits.sh if drift
# Restart if worker/idle_gate code changed:
sudo systemctl restart jellyflam3-idlegate jellyflam3-worker
./scripts/healthcheck.sh
```

Deploy via **`git pull` on the Pi** — not scp of a Windows working tree (LF + exec bits break).

### Backup

```bash
./scripts/backup.sh                 # config + secrets + genomes + flock tarball
./scripts/backup.sh --config-only
```

### Operator triage

| Symptom | Check | Fix |
|---|---|---|
| No new sheep | `healthcheck.sh`; `gate` in status JSON; inbox count | Open gate / fix worker / seed or breed |
| Gate stuck closed | Jellyfin Sessions; Roku still “Playing”? | Stop playback; wait `idle_delay_sec` |
| Worker quiet, gate open | `ls genomes/inbox/*.flam3`; journal `-u jellyflam3-worker` | Seed inbox; inspect quarantine |
| healthcheck exit 1 | Read script sections (units, tools, status file, **peering share_live**) | See [offline peering](#opt-in-vs-share-live-do-not-confuse-them); `opt-in` or `opt-out` |
| Blank Roku SS | VoD Settings ever saved on this device? | Sideload VoD → Settings → re-sideload SS |
| Kodi SS hint / no video | `server_url` uses LAN IP? flock empty on Jellyfin? | `jellyfin_id_dump.py --items`; re-install zip after client fix |
| Kodi zip push fails | SMB `\\<Kodi_IP>\Downloads` vs SSH key | Use LibreELEC SMB; or install SSH key for `root@<Kodi_IP_Address>` |
| Offline peering (Opt In, no sync) | `healthcheck`: `BAD share not live`; `peering status` → `share_live: false` | `opt-in` with `TS_AUTHKEY` + Syncthing up, or `opt-out` |
| Peering stuck (live mesh) | `peering status`; inbox under `peers/inbox` | `promote --apply`; trust keys; share-security verify |
| Bad palette / encode | `refactor scan` | preview → apply pathway |
| Wipe everything local | — | `hammer --dry-run` then `--confirm HAMMER` (not Shears) |

### Owner-OK acceptance gates (RC)

| Gate | Command |
|---|---|
| Unit tests | `python3 -m pytest tests/ -q` |
| CI | `.github/workflows/tests.yml` on push/PR |
| Health | `./scripts/healthcheck.sh` exit 0 |
| Furnace smoke | `./scripts/smoke_render.sh` → `SMOKE_RENDER_OK` |
| HLS | `./scripts/hls_smoke.sh` |
| Share fleet | `scripts/lab_smoke05_fleet.ps1` |

Checklist: [phase3/10_TESTING_AND_ACCEPTANCE.md](phase3/10_TESTING_AND_ACCEPTANCE.md).

---

## Layer 3 — Contributor

### Repository layout

| Path | Role |
|---|---|
| `pipeline/` | Furnace, curator, peering, refactor — Python CLIs (`python3 -m pipeline.*`) |
| `scripts/` | Ops shell/Python/PowerShell — health, cron, packaging, lab smoke |
| `tests/` | Fast pytest suite (~280 tests, ~3s) |
| `configs/` | Example YAML; live config is gitignored |
| `docs/phaseN/` | Feature guides (implementer SoT per topic) |
| `deploy/systemd/` | Unit files |
| `.github/workflows/tests.yml` | CI: pytest + exec bits |

### Development setup

```bash
git clone git@github.com:awuehler/jellyflam3-server.git
cd jellyflam3-server
pip install -r requirements.txt
# Pi: sudo apt install -y python3-pytest python3-yaml  (PEP 668; prefer apt for pytest)
python3 -m pytest tests/ -q
```

On Windows: use Git Bash for gate script tests; `media_layout` tests skip on `nt` (POSIX modes) — Linux CI covers them.

### Pipeline CLI index

```text
python3 -m pipeline.worker          # furnace (poll inbox or --once)
python3 -m pipeline.idle_gate       # gate supervisor
python3 -m pipeline.seed_inbox      # archive / random / mutate feedstock
python3 -m pipeline.breed           # pedigree mutate/cross/blend/interpolate
python3 -m pipeline.breed_idle      # daily idle breed logic
python3 -m pipeline.shears          # add/modify/delete/audit/sweep
python3 -m pipeline.hammer         # nuclear local reset
python3 -m pipeline.refactor        # quality scan/preview/apply/quarantine/batch
python3 -m pipeline.peering         # opt-in/out, publish, promote, keys
python3 -m pipeline.stills          # screensaver stills extract
python3 -m pipeline.backfill_posters
python3 -m pipeline.media_layout    # catalog dir modes 2775/664
python3 -m pipeline.job_recovery    # orphan job reclaim
python3 -m pipeline.hw_profile      # apply 16a/08a/04a profile
python3 -m pipeline.display_profiles
```

Bare `python3 -m pipeline` prints this list and exits 2.

### Testing pyramid

| Layer | Command | Notes |
|---|---|---|
| Unit / fast | `python3 -m pytest tests/ -q` | Default pre-push |
| Integration | same suite | HTTP sink, gate exits, package zips |
| Smoke / e2e | Pi scripts | `smoke_render`, `hls_smoke`, `lab_smoke05_fleet` |

Key test modules added for review hardening: `test_gate_script_exits.py`, `test_tool_lookup.py`, `test_refactor_modules.py`, `test_shears_id_match.py`, `test_worker_claim.py`.

### Conventions

- **Exec bits:** `scripts/*.{sh,py,ps1}` and `pipeline/*.py` are `100755` in git — `./scripts/ensure_exec_bits.sh`
- **Line endings:** `.gitattributes` enforces LF for `*.sh`, `*.py`, `*.ps1`
- **Tool lookup:** `pipeline.tool_lookup.tool(cfg, name)` — hyphen fallback for `flam3_animate` etc.
- **Confirm tokens:** Shears `DELETE`, Hammer `HAMMER`, refactor `APPLY` / `QUARANTINE` / `BATCH`
- **Secrets:** `${ENV}` in YAML; missing secrets fail closed outside smoke profiles (`tests/test_config.py`)

### Where to change what

| Change | Read first |
|---|---|
| Render duration bands | `pipeline/choose_duration.py`, `docs/phase2/08_DYNAMIC_DURATION.md` |
| TV-port / palette | `pipeline/tv_optimize.py`, `pipeline/palette_harmony.py` |
| Share security | `pipeline/share_security.py`, `docs/phase3/05_SHARED_SHEEP_SECURITY.md` |
| Roku client | `roku-channel/`, `docs/phase1/08_ROKU_BRIGHTSCRIPT.md` |
| Kodi screensaver | `kodi-screensaver/`, [phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) |
| Architecture | `docs/Pi5_Flam3_VoD_Pipeline.md` |

---

## Appendix A — Key paths (lab defaults)

| Path | Purpose |
|---|---|
| `/media/sheep/by-generation/` | Catalog MP4 + sidecar + poster |
| `/media/sheep/_refactor-preview/` | Refactor Jellyfin-visible previews |
| `/var/cache/jellyflam3/frames` | Render scratch |
| `/var/lib/jellyflam3/jobs` | In-flight job state |
| `/var/lib/jellyflam3/idle_gate_status.json` | Gate SoT |
| `genomes/inbox` | Worker input queue |
| `genomes/quarantine` | Failed genomes |
| `genomes/done` | Rendered parent pool (breeding) |
| `genomes/peers/inbox` | Syncthing land (promote required; no auto-furnace) |
| `/var/lib/jellyflam3/peering_status.json` | Opt In / **share_live** / Tailscale / Syncthing (live snapshot) |
| `/storage/downloads/` on Kodi Pi | Zip drop for **Install from zip** (LibreELEC SMB share **Downloads**) |
| `/storage/.kodi/addons/screensaver.jellyflam3` | Installed add-on files |
| `/storage/.kodi/userdata/addon_data/screensaver.jellyflam3/settings.xml` | Jellyfin URL / API key / user / library (persists across zip upgrades) |

## Appendix B — Further reading

| Topic | Doc |
|---|---|
| Full Pi install | [phase2/09_PI_FROM_SCRATCH.md](phase2/09_PI_FROM_SCRATCH.md) |
| Runtime / systemd | [phase1/09_RUNTIME_AND_OPS.md](phase1/09_RUNTIME_AND_OPS.md) |
| Worker pipeline | [phase1/05_RENDER_PIPELINE.md](phase1/05_RENDER_PIPELINE.md) |
| HLS streaming | [phase2/03_HLS_CLIENT_STREAMING.md](phase2/03_HLS_CLIENT_STREAMING.md) |
| Peering | [phase2/05_SYNCTHING_GENOME_PEERING.md](phase2/05_SYNCTHING_GENOME_PEERING.md) |
| Phase 3 feature guides | [phase3/00_OVERVIEW.md](phase3/00_OVERVIEW.md) |
| Kodi screensaver (detail) | [kodi-screensaver/README.md](../kodi-screensaver/README.md) · [phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) |
| RC / acceptance | [phase3/10_TESTING_AND_ACCEPTANCE.md](phase3/10_TESTING_AND_ACCEPTANCE.md) |

---

*Document version: 2026-08-22 — Kodi screensaver upgrade runbook (package → SMB → install from zip); aligns with fleet tip `b7e81ea` (share_live peering readiness, healthcheck fail-closed on offline Opt In).*
