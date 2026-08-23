# 09 — Pi from scratch

## Boundary

End-user guide to build a **new** Raspberry Pi JellyFlam3 system from zero — also the **2nd-system exit criteria**. Consolidates Phase 1 install paths; links to Phase 1 deep-dives as appendix. **Stop before** acceptance sign-off ([10](10_TESTING_AND_ACCEPTANCE.md)).

## Hardware profiles (choose one)

| Profile class | Hostname examples | RAM | microSD | PCIe NVMe | USB SSD | Tier | Render preset |
|---|---|---|---|---|---|---|---|
| **rpi-jellyflam3-16** | `rpi-jellyflam3-16a`, `16b`, … | RPi 5 **16 GB** | **128 GB** | **1 TB** | **1 TB** | $$$ | Gold Sheep Lite |
| **rpi-jellyflam3-08** | `rpi-jellyflam3-08a`, `08b`, … | RPi 5 **8 GB** | **64 GB** | **500 GB** | **500 GB** | $$ | Gold Sheep Lite |
| **rpi-jellyflam3-04** | `rpi-jellyflam3-04a`, `04b`, … | RPi 5 **4 GB** | **32 GB** | **250 GB** | **250 GB** | $ | **Compact** (same quality; shorter loops) |

**Roles:** microSD = OS · PCIe NVMe = scratch + `/var/lib/jellyflam3` · USB SSD = `/media/sheep` flock.

Hostnames always use a letter suffix (`…-16a`, `…-08a`, `…-04b`, …). Apply the matching class overlay with `python3 -m pipeline.hw_profile apply 08a` (or `16b` / `04a`).

### Render presets (locked)

| Knob | `-16` | `-08` | `-04` (compact) |
|---|---|---|---|
| `render.edition` | `gold_sheep_lite` | `gold_sheep_lite` | `compact` |
| `quality` / `temporal_samples` / `supersample` | 900 / 450 / 2 | same | **same** |
| `max_cpus` | 3 | 3 | 3 |
| Soft / hard VoD max (s) | **43 / 113** | **37 / 90** | **31 / 60** |
| `dynamic.base_sec` / target | **43** | **31** | **23** / target **19** |
| Dynamic short bias | — | — | `profile_04_short_bias` **4 s** (→ ~19 s center) |
| Encode bitrate | 4M / max 6M | 4M / max 6M | **3M / max 4M** |
| `free_space_gb_min` | 8 | 8 | **4** |

VoD **soft/hard bands and `base_sec` scale with Pi class** (filesystem / RAM headroom for longer masters). Overlays: `configs/profiles/rpi-jellyflam3-{16,08,04}.yaml`. Quality stays Lite on all classes; `-04` is shorter + leaner encode for disk, not a quality cut.

**Period-snap note:** with `vod.dynamic.snap_to_periods: true` (**locked fleet default** on all HW profiles), LCM snap can jump toward soft max — see [08_DYNAMIC_DURATION.md](08_DYNAMIC_DURATION.md#warning--period-snap-lcm-blow-up). That cost is accepted; do not disable snap as part of normal bring-up.

```bash
python3 -m pipeline.hw_profile list
python3 -m pipeline.hw_profile show 04a
# After copying jellyflam3.yaml.example → jellyflam3.yaml:
python3 -m pipeline.hw_profile apply 08a --config configs/jellyflam3.yaml
# Dry-run merge only:
python3 -m pipeline.hw_profile apply 04a --dry-run
```

`apply` deep-merges the overlay and **rewrites** the yaml (comments in the target are lost — start from the example copy). Restart the worker after apply.

---

## Guidelines — build sequence

Use **`./scripts/bringup_check.sh`** after each major stage (identity → mounts → repo → toolchain → units → health). It is read-only and prints OK / WARN / FAIL. Re-run after Jellyfin install so CachePath / MetadataPath permissions are verified.

### 1. Flash OS + hostname + cooler + SSH key

1. Flash **Raspberry Pi OS 64-bit** (Bookworm or newer); enable SSH in imager; create user **`jellyflam3`**.
2. First boot: set hostname with a letter suffix (`rpi-jellyflam3-16a` / `08a` / `04a`, or `…b`, …).
   Ensure local resolve works (avoids `sudo: unable to resolve host`):

   ```bash
   HOST="$(hostname -s)"
   # Persist across cloud-init regenerations when manage_etc_hosts=true:
   echo "127.0.1.1 $HOST" | sudo tee /etc/cloud/templates/hosts.debian.tmpl
   echo -e "127.0.0.1 localhost\n127.0.1.1 $HOST" | sudo tee /etc/hosts
   getent hosts "$HOST"
   ```
3. Install Active Cooler; attach NVMe HAT+ and USB SSD.
4. **Install your SSH public key before continuing** (password auth alone is brittle for ops):

```bash
# From your workstation (example):
ssh-copy-id jellyflam3@rpi-jellyflam3-04a
# or paste into ~/.ssh/authorized_keys on the Pi, mode 600
ssh jellyflam3@rpi-jellyflam3-04a 'hostname; free -h | head -2'
```

Appendix: [../phase1/01_HARDWARE_AND_OS.md](../phase1/01_HARDWARE_AND_OS.md).

### 2. Disks and mounts

| Mount | Disk | Contents |
|---|---|---|
| `/` (root) | microSD | OS only — **not** media or frame scratch |
| `/var/cache/jellyflam3` | PCIe NVMe | **Jellyfin CachePath** + render frames + (via bind) state |
| `/var/lib/jellyflam3` | bind → `…/cache/…/lib` | **Jellyfin MetadataPath** + jobs, logs, display_profiles |
| `/media/sheep` | USB SSD | Catalog mount; Jellyfin **Sheep** → `by-generation/…`; previews → `_refactor-preview/` |

**Note:** Successfully rendered genomes archive to **repo** `genomes/done/` (`paths.genomes_done`), not under `/var/cache/…/genomes/done`.

Suggested partition labels (adjust UUIDs in `fstab`):

```bash
# After formatting NVMe + USB SSD (example — use your device nodes):
sudo mkdir -p /media/sheep /var/cache/jellyflam3
# Add UUID=… lines to /etc/fstab, then:
sudo mount -a
# Clone is not required yet if you only need dirs — once repo exists:
cd /opt/jellyflam3-server   # or repo checkout
./scripts/bootstrap_pi.sh
df -h /media/sheep /var/cache/jellyflam3 /var/lib/jellyflam3
findmnt /media/sheep /var/cache/jellyflam3 /var/lib/jellyflam3
./scripts/bringup_check.sh
```

`bootstrap_pi.sh` creates the directory tree, bind-mounts `lib` → `/var/lib/jellyflam3` when NVMe is at cache, sets **775** on cache/lib, **2775** on sheep, and (if `jellyfin` exists) group membership + `transcodes` / `library` ownership so Dashboard path changes do not Axios-fail on temp files.

On **`-04` (32 GB microSD):** enable journald vacuum early (step 12).

### 3. Clone repo + config

```bash
sudo mkdir -p /home/jellyflam3/GitHub
sudo chown "$USER:$USER" /home/jellyflam3/GitHub
cd /home/jellyflam3/GitHub
git clone https://github.com/awuehler/jellyflam3-server.git
cd jellyflam3-server
sudo ln -sfn "$(pwd)" /opt/jellyflam3-server

# Shell PATH / PYTHONPATH for interactive jellyflam3 sessions (idempotent):
grep -q 'JellyFlam3: Development' ~/.bashrc 2>/dev/null || cat >> ~/.bashrc <<'EOF'

# JellyFlam3: Development
export PATH="$PATH:/usr/local/bin:/home/jellyflam3/GitHub/jellyflam3-server/scripts:."
export PYTHONPATH="/home/jellyflam3/GitHub/jellyflam3-server"
EOF
# shellcheck disable=SC1090
source ~/.bashrc 2>/dev/null || true

python3 -m venv .venv  # optional; system python3 + apt/pip deps is fine
sudo apt install -y python3-pytest python3-yaml   # pytest via apt (PEP 668 blocks pip --user)
pip3 install -r requirements.txt --user 2>/dev/null || pip3 install -r requirements.txt --break-system-packages

cp configs/jellyflam3.yaml.example configs/jellyflam3.yaml
cp secrets.env.example secrets.env
# Never commit secrets.env or a filled jellyflam3.yaml with LAN secrets.
python3 -m pipeline.hw_profile apply 04a   # or 08a / 16a — MUST match hostname class
# Edit secrets.env after Jellyfin wizard (step 5)
./scripts/bootstrap_pi.sh                  # safe to re-run after clone
./scripts/bringup_check.sh
ls /opt/jellyflam3-server/secrets.env /opt/jellyflam3-server/configs/jellyflam3.yaml
```

Appendix: [../phase1/02_REPO_AND_CONFIG.md](../phase1/02_REPO_AND_CONFIG.md).

### 4. flam3 + ffmpeg + smoke

```bash
./scripts/install_flam3.sh          # apt deps + build + verify
export JELLYFLAM3_SMOKE=1
./scripts/smoke_render.sh           # 13 s / nframes=312 — never publish
./scripts/bringup_check.sh
```

Appendix: [../phase1/03_FLAM3_AND_FFMPEG.md](../phase1/03_FLAM3_AND_FFMPEG.md).

### 5. Jellyfin + Sheep library + API key

**Do permissions and paths first** — wrong CachePath/MetadataPath ownership causes Axios errors and “permission denied” creating temporary files in Jellyfin logs.

```bash
./scripts/install_jellyfin.sh       # full notes: perms, paths, ParentId, V4L2, setup wizard
# Follow printed steps:
#   0) permission prep (or re-run bootstrap_pi.sh after jellyfin package install)
#   1) https://jellyfin.org/docs/general/post-install/setup-wizard
#   2) Cache path=/var/cache/jellyflam3  Metadata path=/var/lib/jellyflam3
#   3) library Sheep → /media/sheep/by-generation (+ Rework Poster → _refactor-preview); API key; ParentId via jellyfin_id_dump.py
#   4) Playback → Transcoding → Hardware acceleration → Video4Linux2 (V4L2)
python3 scripts/jellyfin_id_dump.py
./scripts/bootstrap_pi.sh           # refresh jellyfin group + transcodes/library ownership
./scripts/bringup_check.sh
```

Catalog perms (trickplay):

```bash
python3 -m pipeline.media_layout --config configs/jellyflam3.yaml
```

Appendix: [../phase1/04_JELLYFIN_LIBRARY.md](../phase1/04_JELLYFIN_LIBRARY.md).

### 6. Systemd worker + idle-gate (+ display sink)

```bash
sudo cp /opt/jellyflam3-server/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo mkdir -p /var/lib/jellyflam3/display_profiles
sudo chown jellyflam3:jellyflam3 /var/lib/jellyflam3/display_profiles   # or "$USER"
sudo systemctl enable --now jellyflam3-idlegate jellyflam3-worker jellyflam3-display-sink
systemctl is-active jellyflam3-worker jellyflam3-idlegate jellyflam3-display-sink jellyfin
```

Units assume **`WorkingDirectory=/opt/jellyflam3-server`** and user/group **`jellyflam3`**. If your login user differs, edit the unit `User=`/`Group=` or create that account.

Appendix: [../phase1/09_RUNTIME_AND_OPS.md](../phase1/09_RUNTIME_AND_OPS.md) · idle-gate [../phase1/06_IDLE_GATE.md](../phase1/06_IDLE_GATE.md).

### 7. Confirm HW profile preset

```bash
python3 -c "from pipeline.config import load_config; c=load_config('configs/jellyflam3.yaml'); r=c['render']; print(r.get('hw_profile'), r.get('edition'), r.get('quality'), r.get('max_cpus'))"
# Expect e.g. rpi-jellyflam3-08 gold_sheep_lite 900 3
#        or  rpi-jellyflam3-04 compact 900 3
sudo systemctl restart jellyflam3-worker
```

### 8. First archive seed

```bash
cd /opt/jellyflam3-server
python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml --archive --fetch-count 1
# Wait for idle-gate + worker; then:
./scripts/status_report.sh
```

Sheep tax runs on archive fetch when enabled (default). Guide: [01](01_ARCHIVE_SEED_LIBRARY.md).

### 9. Posters, HLS, JellyFlam3 channel

Already shipped on the lab flock path — verify on the **new** Pi:

| Check | Command / action |
|---|---|
| Primary poster | Jellyfin web + filesystem `*-poster.jpg` beside MP4 ([02](02_JELLYFIN_FLOCK_UX.md)) |
| HLS smoke | `./scripts/hls_smoke.sh` ([03](03_HLS_CLIENT_STREAMING.md)) |
| JellyFlam3 sideload | Package on **this** furnace Pi + sideload; furnace zip pre-fills Jellyfin IDs; play one item ([04](04_ROKU_CHANNEL_POLISH.md), [08](../phase3/08_JELLYFIN_ID_DUMP.md)) |

```bash
./scripts/package_roku_channel.sh          # dist/jellyflam3-roku.zip (presets from secrets.env)
./scripts/package_roku_screensaver.sh    # dist/jellyflam3-screensaver.zip
./scripts/package_kodi_screensaver.sh    # dist/screensaver.jellyflam3.zip (needs python3-pil)
# Windows packaging host: same script names with .ps1 — no presets without secrets.env
```

### 10. Peering stays Opt Out (default)

Do **not** enable Syncthing until host-service Opt In.

```bash
# Install packages only (units copied in step 6; leave syncthing disabled)
curl -fsSL https://tailscale.com/install.sh | sh
sudo apt-get install -y syncthing
python3 -m pipeline.peering status    # expect share_opt_in=false
# Optional later: set TS_AUTHKEY in secrets.env, ACL from deploy/peering/, then:
# python3 -m pipeline.peering opt-in
# After Opt In, one-time Syncthing folder + peer introduce is still required
# before genomes land — see deploy/peering/README.md (first-time mesh introduce).
```

Guide: [05](05_SYNCTHING_GENOME_PEERING.md) · runbook: [`deploy/peering/README.md`](../../deploy/peering/README.md#syncthing-first-time-mesh-introduce-lab-runbook).

### 11. Health + status

```bash
./scripts/bringup_check.sh --strict
./scripts/healthcheck.sh
./scripts/status_report.sh
./scripts/perf_healthcheck.sh --quick
```

### 12. `-04` only — journald / microSD hygiene

32 GB microSD fills quickly with journals:

```bash
sudo mkdir -p /etc/systemd/journald.conf.d
sudo tee /etc/systemd/journald.conf.d/jellyflam3-04.conf >/dev/null <<'EOF'
[Journal]
SystemMaxUse=200M
RuntimeMaxUse=50M
MaxFileSec=7day
EOF
sudo systemctl restart systemd-journald
journalctl --disk-usage
```

Optional: zram on 4 GB boards (see Phase 1 hardware guide).

---

## Dry-run (no second Pi)

When hardware is not ready, validate the **guide + presets** on the lab host or a laptop:

```bash
python3 -m pipeline.hw_profile list
python3 -m pipeline.hw_profile apply 04 --config configs/jellyflam3.yaml.example --dry-run
python3 -m pytest tests/test_hw_profile.py tests/test_tv_optimize.py tests/test_choose_duration.py -q
```

Mark dry-run in the 2nd-system checklist notes; a full Owner OK still wants a real second board or an intentional lab reprovision.

---

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/hw_profile.py` | pipeline | List / show / apply 16 / 08 / 04 overlays |
| `configs/profiles/rpi-jellyflam3-{16,08,04}.yaml` | config | Hardware-class render / encode presets |
| `scripts/bootstrap_pi.sh` | script | Dir tree + NVMe bind + Jellyfin-ready perms |
| `scripts/bringup_check.sh` | script | Staged OK/WARN/FAIL bring-up checklist |
| `scripts/install_flam3.sh` / `smoke_render.sh` | script | Toolchain install + smoke |
| `scripts/install_jellyfin.sh` | script | Jellyfin paths, perms, ParentId, V4L2, wizard |
| `scripts/jellyfin_id_dump.py` | script | Capture library / user IDs into secrets |
| `deploy/systemd/*.service` | deploy | Worker, idle-gate, display-sink (+ peering) |
| `pipeline/seed_inbox.py` (`--archive`) | pipeline | First archive seed on a new Pi |
| `pipeline/media_layout.py` | pipeline | Catalog perms after Jellyfin library create |
| `pipeline/peering.py` | pipeline | Confirm Opt Out default / optional Opt In |
| `scripts/hls_smoke.sh` / `package_roku_channel.sh` | script | HLS + channel verify on 2nd system |
| `scripts/healthcheck.sh` / `status_report.sh` / `perf_healthcheck.sh` | script | Post-build health surface |

## 2nd-system exit criteria

Using **only** this guide (plus linked appendix guides), a second Pi reaches:

- [x] Units `jellyflam3-worker`, `jellyflam3-idlegate`, `jellyfin` **active** — `rpi-jellyflam3-08a` 2026-08-08
- [x] At least one ingested sheep with **Primary** poster — `electricsheep.247.47501` (+ FS poster + sidecar) on 08a
- [x] JellyFlam3 channel lists the item (with poster) — Owner OK 2026-08-08
- [x] Peering still Opt Out unless host-service Opt In — 08a `share_opt_in=false`, syncthing inactive
- [x] `status_report.sh` runs cleanly — 08a (gate open; units active)
- [x] `render.hw_profile` matches hostname class — 08a `rpi-jellyflam3-08` / `gold_sheep_lite`; 16a stamped `rpi-jellyflam3-16`
- [ ] **`-04` compact board** exercised end-to-end (hostname `rpi-jellyflam3-04a`, compact preset, journald vacuum, one archive seed → ingest) — Owner pending

## Exit criteria (this guide)

- [x] Guide covers all three HW profiles and compact `-04` preset (`configs/profiles/` + `pipeline.hw_profile`)
- [x] Mount / symlink / systemd steps match current repo (`bootstrap_pi.sh`, `/opt/jellyflam3-server`, deploy units)
- [x] 2nd-system checklist above exercised on a real Pi (`rpi-jellyflam3-08a`) — Owner OK 2026-08-08
- [x] Phase 2 DoD item for this guide signed in [00_OVERVIEW.md](00_OVERVIEW.md) / [10](10_TESTING_AND_ACCEPTANCE.md)
- [x] Bring-up friction addressed: SSH key step, Jellyfin Cache/Metadata prep, `bringup_check.sh`, genomes_done path note

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-08 | [x] (08a path) |

Next Owner exercise: bring up **`rpi-jellyflam3-04a`** with this revised sequence, then tick the `-04` checklist row above.

## See also

[../phase1/](../phase1/) · [00_OVERVIEW.md](00_OVERVIEW.md) · presets `configs/profiles/` · `python3 -m pipeline.hw_profile`
