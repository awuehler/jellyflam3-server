# JellyFlam3 — User Guide & Operator Runbook

One document, **three layers**. Pick your layer and stay there — you should not need to read the whole file.

| Layer | Audience | You want to… |
|---|---|---|
| **[Layer 1 — End user](#layer-1--end-user)** | Household / viewer | Watch ambient loops, use Roku or Kodi screensaver, fix “nothing plays” without SSH |
| **[Worked examples](#worked-examples)** | Viewer + operator | Four first-evening stories (VoD gate, screensaver, two Rokus, peer receive) |
| **[Layer 2 — Operator](#layer-2--operator-runbook)** | Pi owner / homelab operator | Keep the flock healthy, seed/breed/delete sheep, peering, health gates, fleet updates, **private ↔ public** |
| **[Layer 3 — Contributor](#layer-3--contributor)** | Developer / maintainer | Run tests, change pipeline code, CI, deploy conventions |

**Terms:** [glossary.md](glossary.md) · **Architecture (SoT):** [Pi5_Flam3_VoD_Pipeline.md](Pi5_Flam3_VoD_Pipeline.md) · **Install from zero:** [phase2/09_PI_FROM_SCRATCH.md](phase2/09_PI_FROM_SCRATCH.md)

---

## Layer 1 — End user

### What you have

JellyFlam3 is a **home dream engine**: a Raspberry Pi renders flame-fractal “sheep” into MP4 loops, stores them in a **Jellyfin** library, and your **Roku** or **Kodi** device plays them when the TV is idle. Rendering is slow (hours per sheep on a Pi); playback is fast.

You do **not** need the Pi terminal for normal viewing. Printable one-pager: [FRIDGE_CARD.md](FRIDGE_CARD.md).

### Watch on Roku (VoD channel)

**First time on a Roku (one-time setup per TV):**

1. Sideload the JellyFlam3 VoD channel zip (e.g. `dist/jellyflam3-roku.zip` from `scripts/package_roku_channel.*` on a furnace Pi).
2. **Furnace-built zips are pre-configured:** when packaged on a Pi with `secrets.env`, the zip includes that furnace’s Jellyfin URL, API key, user id, and library id. Launch the channel — credentials apply on first run if the registry is empty; the flock list should load without manual paste.
3. **Otherwise** (Windows packaging host or empty registry): open the channel → **Settings** → enter Jellyfin connection values. An operator runs `python3 scripts/jellyfin_id_dump.py` on the Pi and gives you `baseUrl`, `apiKey`, `userId`, `libraryId` (never share the API key in chat/email — paste on the TV only) → save Settings.

**Everyday use:** launch JellyFlam3 → pick a sheep → ambient loop plays. With **shuffle** on (channel 1.0.28+), the mix includes archive gens plus **pedigree** and **tuple** folders. A **tuple** is one longer clip: sheep A, then a morph into sheep B. During that middle morph only, a quiet mark sits in the lower-right corner (the Electric Sheep logo PNG on the default private furnace; your own PNG if the operator set one; or the credit “artwork by Scott Draves and the Electric Sheep” on a commercial-safe furnace that still uses the Cesari file). Loops A and B have no mark. That mark is **not** a license to post the clip as official Electric Sheep — operators, see [Private vs public furnace](#private-vs-public-furnace) and [Use your own PNG](#use-your-own-png-private-and-public). When you press **Play**, the Pi **stops rendering** new sheep until the TV has been idle for several minutes (see [idle gate](#idle-gate-behavior) below).

**Deep link smoke (optional):** after an operator dumps item Guids (`jellyfin_id_dump.py --items`), a specific sheep can be launched with `contentId=<Guid>` via the Roku ECP port (developer mode).

### Roku Screensaver / Backdrop

The screensaver is a **separate sideload package** (`jellyflam3-screensaver.zip`). It shows **Jellyfin Primary posters and Backdrop stills** from every library folder except `tuple` — no video node (Roku policy). It always rotates (ignores VoD `shuffleFlock`) and honors the same `commercialMode` Tag filter as VoD.

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

**Everyday use:** leave Kodi idle; any keypress exits the screensaver (Kodi default). When flock is configured, sheep MP4s shuffle; if Jellyfin is unreachable, you see a short hint on black (no test-pattern video). The flock list is loaded **once per screensaver session** — after a new sheep lands in Jellyfin, exit idle and let the screensaver start again (or wait for the next natural idle). Optional mid-session **long-interval** refresh (hours / wrap) is still Phase 4 polish. If a sheep is **quarantined** while idle is running, 0.2.7 drops that id, re-polls Jellyfin (rate-limited), and continues with a remaining loop.

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
| Playback stutters / buffers | Prefer Direct Play (H.264 MP4); avoid forcing transcode in client | Persistent transcode hammering Pi, or several TVs on a WiFi Pi (`link_capacity`) |
| Screensaver blank | VoD was never configured on **this** Roku | After VoD Settings saved, still blank |
| Screensaver “replaced” VoD | Re-sideload VoD channel zip | — |
| Kodi screensaver black / hint text | Open add-on **Configure**; confirm Jellyfin URL is furnace **LAN IP**, not `127.0.0.1` | Settings correct but no sheep play |
| Nothing new for days | Normal if gate was closed or inbox empty | Gate open + inbox empty for a week |

Copy-paste evenings (VoD + gate, screensaver, two Rokus, peer receive): [Worked examples](#worked-examples).

---

## Worked examples

Copy-paste stories for a typical one-Pi (or two-Pi) home. Assume Phase 2/3 install is already done. Fill `http://<Pi_LAN_IP>:8096` — never `127.0.0.1` on a TV. Do not paste API keys into chat or the [fridge card](FRIDGE_CARD.md).

Run Pi commands from `/opt/jellyflam3-server` unless noted.

### 1 — First evening (VoD + idle gate)

**Host:** furnace Pi + one Roku on the same LAN.

1. On the Pi, dump Jellyfin IDs (operator keeps the API key off shared notes):

   ```bash
   cd /opt/jellyflam3-server
   python3 scripts/jellyfin_id_dump.py
   ```

2. Sideload `dist/jellyflam3-roku.zip` (furnace-built zip pre-fills Settings). Otherwise open **JellyFlam3 → Settings**, enter `baseUrl` / `apiKey` / `userId` / `libraryId`, save.
3. Launch JellyFlam3 → pick one sheep → **Play**. Confirm the loop is running.
4. On the Pi, confirm the furnace paused:

   ```bash
   python3 -m json.tool /var/lib/jellyflam3/idle_gate_status.json
   # Expect: "gate": "closed" (Playing / transcode)
   ```

5. Stop playback on the Roku (Home / Back out of the player). Wait `idle_delay_sec` (default **600** s). Re-check the JSON — `"gate": "open"`.

**Pass:** flock listed, one sheep played, gate closed then opened. **Fail:** empty flock or `"Cannot connect"` → Layer 1 triage (`baseUrl` is LAN IP).

### 2 — Screensaver evening (stills, gate stays open)

**Host:** same furnace Pi + the **same** Roku as example 1 (VoD Settings already saved on this box).

1. Sideload `dist/jellyflam3-screensaver.zip`. Developer mode has **one** sideload slot — this **replaces** VoD until you re-sideload VoD; registry keys survive.
2. Roku **Settings → Theme → Screensavers → JellyFlam3**. Optional: screensaver Settings for fade/dwell only (no credential editors).
3. Idle the TV (or use the Theme screensaver preview). You should see **posters and stills** (Jellyfin Primary + Backdrop), never tuple frames, always rotating. Not video.
4. On the Pi, while the screensaver is up:

   ```bash
   python3 -m json.tool /var/lib/jellyflam3/idle_gate_status.json
   # Expect: "gate": "open"  (Client JellyFlam3-Screensaver is ignored)
   ```

**Pass:** images on the TV and gate still open (rendering may continue). **Fail:** blank SS → VoD was never configured on **this** Roku (example 1 step 2). Re-sideload VoD when you want the channel tile back.

### 3 — Two Rokus, one Pi

**Host:** one furnace Pi (`jellyflam3-display-sink` active) + two Roku devices. Same Jellyfin URL on both.

1. Confirm the sink:

   ```bash
   systemctl is-active jellyflam3-display-sink   # expect: active
   ```

2. On **Roku A**: VoD Settings (same `baseUrl` as the Pi LAN) → **Fetch TV display**. Channel should report **Pi OK** and a `*.json` name.
3. Repeat **Fetch TV display** on **Roku B**.
4. On the Pi:

   ```bash
   python3 -m pipeline.display_profiles list
   ```

   Expect **two** files under `/var/lib/jellyflam3/display_profiles/` (`JellyFlam3-<deviceId>.json`). Prefs (streamMode, shuffle, fade) stay **per Roku** in that device’s registry.

**Pass:** `list` shows two screens; concurrent **screensaver** on both must not close the gate; **VoD Playing** on either closes it. Profiles are hints only — the furnace does not retarget 4K.

### 4 — Peer receive (second Pi)

**Hosts:** publisher Pi and receiver Pi, both **Opt In** with **share live** (Syncthing + Tailscale). See [`deploy/peering/README.md`](../deploy/peering/README.md). Trust keys exchanged (`peering gen-keys`, `trust-key`).

1. On both Pis: `python3 -m pipeline.peering status` → `share_opt_in: true`, `share_live: true`.
2. Publisher (already-taxed genome in `genomes/done` or similar):

   ```bash
   python3 -m pipeline.peering publish path/to/sheep.flam3 --apply
   ```

3. Wait for Syncthing. On the **receiver**:

   ```bash
   ls genomes/peers/inbox/*.flam3
   python3 -m pipeline.peering promote --apply
   ```

   Integrity runs **before** sheep tax; mismatch → quarantine, not inbox.
4. Receiver worker picks up `genomes/inbox`. Confirm with `./scripts/status_report.sh` (inbox count) or a later catalog MP4 on that host.

**Pass:** file left `peers/inbox`, `promote --apply` moved a `.flam3` to worker inbox (or quarantine if verify failed). **Fail:** `share_live: false` → healthcheck peering section; do not skip the promote gate.

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
./scripts/healthcheck.sh                # exit 0 = healthy; library-disk WARN allowed, BAD fails
python3 -m pipeline.library_disk check  # sheep/scratch used % + free GiB
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

### Catalog posters (after render)

Default is `jellyfin.attach_posters: auto` in the example yaml. Live `configs/jellyflam3.yaml` is gitignored — `git pull` does **not** change it. Older yaml with `attach_posters: true` always creates posters until you edit it.

| Setup | Default after encode | Why |
|---|---|---|
| **Standalone** furnace (Opt Out, or Opt In with no other furnace online) | **No** poster | Mesh size 1 |
| **2+ furnaces** Opt In, Syncthing active, Tailscale online, ≥1 other `jellyflam3` peer | **Yes** — `{stem}-poster.jpg` + Jellyfin Primary, plus stills frames + Backdrops (non-tuple) | Mesh size ≥ 2 |

Screensaver stills (JPEG frames + Jellyfin Backdrops) ride the **same ingest switch**. When posters extract, non-tuple sheep also get `by-generation/{gen}/stills/{stem}/frame_XX.jpg` uploaded as Backdrops. Tuples never generate stills (watermarked edge mid-file is not screensaver-safe). Peering still shares only `*.flam3` + optional `*-poster.jpg` — not stills JPEGs.

`python3 -m pipeline.backfill_posters` always extracts posters **and** stills (operator one-shot). It does not follow ingest auto/never, and it does **not** walk `_refactor-quarantine/` or `_refactor-preview/` (stills always land under live `by-generation/{gen}/stills/{stem}/`). `python3 -m pipeline.stills` remains an operator re-extract CLI for disk frames only.

Check what this furnace will do on the **next** ingest (no worker restart needed for the check):

```bash
python3 -m pipeline.peering status
# posters.mode / posters.ingest_enabled / posters.mesh_size
```

#### Standalone — turn posters **on**

1. Edit live yaml (`nano /opt/jellyflam3-server/configs/jellyflam3.yaml`):
   ```yaml
   jellyfin:
     attach_posters: true
   ```
2. Restart the worker:
   ```bash
   sudo systemctl restart jellyflam3-worker
   systemctl is-active jellyflam3-worker
   ```
3. New renders get a poster **and** stills (non-tuple). Existing catalog MP4s do not — backfill them:
   ```bash
   python3 -m pipeline.backfill_posters --config configs/jellyflam3.yaml
   ```

To return to the default: `attach_posters: auto`, restart the worker.

#### Standalone — keep posters **off** (default)

Leave `attach_posters: auto` (or set `false`). Confirm `peering status` shows `ingest_enabled: false`. Do not run backfill unless you want FS posters anyway.

#### Mesh (2+ furnaces) — keep posters **on** (default)

Leave `attach_posters: auto`. After Opt In + another furnace online, `mesh_size` ≥ 2 and new renders get posters. Restart the worker once after you first Opt In (or after changing yaml) so the running process reloads config.

#### Mesh — turn posters **off**

1. Edit live yaml:
   ```yaml
   jellyfin:
     attach_posters: false
   ```
2. Restart the worker. New renders skip extract/upload. Existing `{stem}-poster.jpg` files stay on disk (Shears delete still removes them with the sheep).

Do **not** run `hw_profile apply` just to flip this flag (it rewrites the whole yaml).

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

### Curator: sheep aliases (memorable names)

Filename stays `electricsheep.{gen}.{id}`. Sidecar `alias` is `adjective_surname` (hash-stable on re-ingest). Human override is sticky.

```bash
python3 -m pipeline.sheep_naming backfill --dry-run
python3 -m pipeline.sheep_naming backfill
python3 -m pipeline.sheep_naming set-alias --stem electricsheep.247.00505 --alias frosty_swirles
python3 -m pipeline.sheep_naming clear-alias --stem electricsheep.247.00505
python3 -m pipeline.sheep_naming resolve frosty_swirles
```

Pasture filename vs alias display toggle is not in this slice (Roku/Kodi still show Jellyfin titles).

Cascade removes catalog MP4/sidecar/poster, jobs, edges (best-effort), Jellyfin item (soft-fail), peer copies when Opt In. Does **not** touch secrets or Syncthing device config.

### Quality repair: Sheep refactor

For sub-standard renders (palette clash, bad encode, **linear-only / `singularity="cloned"` voids**) — **not** delete/recreate genetics.

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

**Fleet watchdog (recommended on Opt-In hosts):** `scripts/cron_tailscale_watch.sh` every ~5 minutes polls live Tailscale + Syncthing and heals when share is not live. If the **LAN gateway** is unreachable, or the gateway pings but **WAN** (default `1.1.1.1`) does not, it rate-limits a **Wi‑Fi reconnect** (`nmcli` disconnect/connect, 15 min cooldown) and will not `tailscale up` while WAN is still down. Opt Out is a no-op. Manual check:

```bash
python3 -m pipeline.tailscale_watch --json
# or dry-run:
./scripts/cron_tailscale_watch.sh --dry-run
```

**Log hygiene (fleet):** persistent journald + 72h file-log rollover. Apply once per Pi after pull:

```bash
sudo ./scripts/enable_log_hygiene.sh
sudo ./scripts/enable_log_hygiene.sh --check
```

Policy: rotate `/var/log/jellyflam3/*.log` every **72h**; **gzip** backups after **11 days**; **purge** after **23 days** (same ages for Jellyfin dated logs). Details: [phase2/09_PI_FROM_SCRATCH.md](phase2/09_PI_FROM_SCRATCH.md) step 12.

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

The packaging script runs `build_kodi_screensaver_assets.py` automatically. Optional: `--fetch-fleet` on that script pulls three `*-poster.jpg` files from fleet Pis 16a/08a/04a into store art. Package on a Pi (or run `strip-cr`) so `addon.xml` is LF — Kodi TinyXML fails install-from-zip on Windows CRLF (`Error reading end tag`).

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

Alternative (Kodi stopped): do **not** use LibreELEC BusyBox `unzip` (it can corrupt `default.py` / `settings.xml` with NUL bytes). Extract with Python:

```bash
python3 -c 'import zipfile; zipfile.ZipFile("/storage/downloads/screensaver.jellyflam3.zip").extractall("/storage/.kodi/addons")'
```

Folder name must stay `screensaver.jellyflam3`.

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

### Private vs public furnace

Default install is a **private mixed** flock (BY + BY-NC, household). **Public** here means the **commercial-safe / venue / published-playback** path — not Roku Channel Store (still parked). JellyFlam3 is not affiliated with Spotworks LLC.

These knobs are **independent**. `git pull` does **not** flip them (`configs/jellyflam3.yaml` is gitignored).

| Surface | Private mixed (default) | Public / commercial-safe |
|---|---|---|
| Furnace `license.commercial_mode` | `false` | `true` |
| New **tuple** edge mark | Cesari PNG, **or** your PNG if `watermark.image` points at it | **Never** the Cesari logo. **Your PNG still overlays.** Else `artwork by Scott Draves and the Electric Sheep` |
| Already-catalogued tuples | Keep whatever was burned in | Keep the Cesari PNG until you **re-furnace** those stems |
| Worker render of NC genomes | Renders | **Still renders** — yaml does not cull NC |
| On-disk NC MP4s | In `/media/sheep/by-generation/` | **Stay on disk** |
| Roku VoD `commercialMode` | `false` | `true` (hides NC **in this channel only**) |
| Kodi SS `commercial_mode` | off | on (hides NC **in this add-on only**) |
| Jellyfin web / jellyfin-roku | Shows the whole library | **Still shows NC** unless you lock the library down yourself |

Cesari PNG files are **not** MIT and **not** Free Sheep CC ([NOTICE](../NOTICE), [watermark README](media/watermark/README.md)). Do not republish Cesari-marked MP4s as official Electric Sheep, and do not use those PNGs as a channel icon. Peering shares `.flam3` only; copying `by-generation/tuple/*.mp4` **does** export the mark.

#### Use your own PNG (private and public)

This replaces the Cesari default on **both** flock modes. The public Cesari skip still applies if `watermark.image` points at `Electric-Sheep-Icon*` / `Electric-Sheep-Logo*`.

1. Make an RGBA PNG you have rights to (~**180×180**, transparent padding). ffmpeg burns it at **native size** — do not use a 1024-px file.
2. Copy it onto the furnace, outside git. Suggested: `/var/lib/jellyflam3/watermark.png` (survives `git pull`). `configs/*.png` is also gitignored.
   ```bash
   sudo install -m 644 /path/to/your-sheepcloud.png /var/lib/jellyflam3/watermark.png
   ```
3. Edit live yaml (`configs/jellyflam3.yaml`, not the example):
   ```yaml
   watermark:
     enabled: true
     style: image
     image: /var/lib/jellyflam3/watermark.png
   ```
   Leave `license.commercial_mode` as you already run it (private `false` or public `true`).
4. Restart the worker:
   ```bash
   sudo systemctl restart jellyflam3-worker
   systemctl is-active jellyflam3-worker
   ```
5. **Re-furnace tuples** so catalog files pick up the new sheepcloud. Confirm the sidecar `"style": "image"` and `"image"` is your path.
   ```bash
   ls genomes/done/electricsheep.tuple.*.flam3
   for f in genomes/done/electricsheep.tuple.*.flam3; do
     [ -f "$f" ] || continue
     python3 -m pipeline.shears modify "$f"
   done
   ```
   Each restage is a full 3-stage encode. Gate must be **open**. Worker rotates the old MP4 to `*.mp4.prev`.

Disable the overlay entirely with `watermark.enabled: false` or `tuple.watermark_on_edge: false`.

#### Take a private furnace public

Do this **in order**. Skipping tags or the client toggles is how you get an empty flock or Cesari-marked CC clips on a “public” TV.

1. **Decide you are actually going public.** Venue, guest TVs, or packing files for others. Household-only → stay on the private defaults.
2. **Confirm Jellyfin Items Tags exist** (commercial-safe clients hide untagged items, which looks like an empty flock):
   ```bash
   python3 scripts/jellyfin_id_dump.py --items --limit 50
   ```
   Spot-check `cc-by` vs `cc-by-nc` on Tags. If Tags are empty, enrich then re-check:
   ```bash
   python3 -m pipeline.backfill_posters --config configs/jellyflam3.yaml
   ```
   Lab CC/NC sample ids: [phase1/07](phase1/07_LICENSE_AND_METADATA.md#lab-check--commercial-mode-toggle).
3. **Edit live yaml** (not the example; not a git commit):
   ```bash
   nano /opt/jellyflam3-server/configs/jellyflam3.yaml
   ```
   Set `license.commercial_mode: true`. If `watermark.image` is still the Cesari file, the worker skips it and burns the attribution sentence. If you already pointed `image` at **your** PNG, that overlay **stays**. Do **not** run `hw_profile apply` unless you intend to rewrite the whole yaml.
4. **Restart the worker** so it reloads yaml (idle-gate can stay up):
   ```bash
   sudo systemctl restart jellyflam3-worker
   systemctl is-active jellyflam3-worker
   ```
5. **Re-furnace existing tuples** if any Cesari-marked MP4 must not appear on the public path. New tuples after step 4 use the attribution sentence **or** your operator PNG; old files do not change.
   ```bash
   ls genomes/done/electricsheep.tuple.*.flam3
   for f in genomes/done/electricsheep.tuple.*.flam3; do
     [ -f "$f" ] || continue
     python3 -m pipeline.shears modify "$f"
   done
   ```
   Each restage is a full 3-stage encode (hours). Gate must be **open**. Worker rotates the old MP4 to `*.mp4.prev`. Confirm the sidecar: Cesari path → `"style": "text"` and the Scott Draves sentence; operator PNG → `"style": "image"` and your path.
6. **Turn commercial-safe on at every pasture client** (furnace yaml does not do this). Existing Roku registry survives sideload; furnace-built zips still preset `commercialMode=false`.
   - **Roku VoD:** Settings → `commercialMode` → **true** → save. Repeat on each stick.
   - **Kodi:** Add-ons → JellyFlam3 Dreams → Configure → **Commercial-safe (skip NC)** on.
   - **Roku screensaver:** same registry `commercialMode` as VoD — NC stills are skipped; tuple folders are never shown.
7. **Do not expose Jellyfin as the public player.** Guests on `:8096` or jellyfin-roku still see NC. Restrict the library (LAN-only, auth, or do not share the URL).
8. **Verify on the TV:** CC samples remain; NC samples gone; a **new** tuple (or a restamped one) shows the attribution sentence **or** your PNG, not the Cesari sheep. Toggle Roku `commercialMode` back to false in a test if you need to prove NC files are still on disk — then set it true again.

Optional: stop packing Cesari-marked `tuple/` MP4s off-box (`scrape_fleet_sheep.ps1`, USB). Gold Sheep / HiFi still stay out of the furnace.

#### Take a public furnace private

Playback of NC returns as soon as **clients** turn commercial-safe off. The Cesari PNG returns on **new** tuples only after yaml + worker restart **and** `watermark.image` is still a Cesari file (and on old tuples only if you re-furnace them). An operator PNG is unchanged by this cutover.

1. **Edit live yaml:** `license.commercial_mode: false`.
2. **Restart the worker:**
   ```bash
   sudo systemctl restart jellyflam3-worker
   systemctl is-active jellyflam3-worker
   ```
3. **Turn commercial-safe off on every client:**
   - Roku VoD Settings → `commercialMode` → **false** → save (each stick).
   - Kodi Configure → **Commercial-safe (skip NC)** off.
4. **Verify:** NC titles reappear in VoD / Kodi shuffle (they were never deleted). A **new** tuple may show the Cesari PNG again (unless you still have an operator PNG).
5. **Optional — restamp tuples encoded while public:** same `shears modify` loop as step 5 above. Until you do, those files keep the attribution sentence (fine for household). Skip this if `watermark.image` is already your PNG — those new encodes already carry it.

#### Lab check (CC vs NC playback only)

After Tags exist, confirm the **client** filter — this does not flip furnace yaml:

| Client | Toggle off | Toggle on |
|---|---|---|
| Roku VoD `commercialMode` | CC + NC in flock | NC gone; CC remain |
| Roku screensaver `commercialMode` | CC + NC stills (no tuples) | NC gone; CC remain |
| Kodi SS `commercial_mode` | May play NC | Only CC-safe Tags |

Expected sample ids: [phase1/07](phase1/07_LICENSE_AND_METADATA.md#lab-check--commercial-mode-toggle). Empty flock with commercial-on → fix enrich (step 2), not the channel.

### Stills (screensaver feedstock)

Covered by [Catalog posters](#catalog-posters-after-render): ingest / `backfill_posters` extract frames and upload Jellyfin Backdrops (`stills.enabled: true` on the fleet yaml). Tuples never generate stills. `python3 -m pipeline.stills` is only an operator re-extract of disk JPEGs; run `backfill_posters` afterward if Backdrops must be replaced.

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

### Pull catalog MP4s to a Windows workstation

Copy flock loops from each furnace (catalog `by-generation` only — not `_refactor-preview`). Tuple MP4s may carry a Cesari edge mark (household-only) or an operator PNG; see [Private vs public furnace](#private-vs-public-furnace).

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/scrape_fleet_sheep.ps1
# Default dest: %USERPROFILE%\Downloads\jellyflam3-sheep\<host>\...
```

Override furnace IPs with `JELLYFLAM3_FLEET_IP_16A` / `_08A` / `_04A` if they are not the lab defaults. `-DryRun` lists; `-Force` overwrites.

### How many TVs at once (link capacity)

Several Rokus / Kodi boxes against **one** Pi is a **LAN** problem. A **WiFi-uplinked furnace** is the tight case — plug the Pi into Ethernet when more than one or two TVs play video at once. Roku **image** screensaver does **not** count; **Kodi video** screensaver and VoD **Playing** do.

```bash
python3 -m pipeline.link_capacity estimate --profile wifi-pi --mode directplay
python3 -m pipeline.link_capacity estimate --profile eth-gigabit --mode directplay
python3 -m pipeline.link_capacity probe     # catalog MP4 bit-rate (p50 / p90)
```

`N_max` is an **estimate**, not a Jellyfin cap. Formula and lab numbers: [phase4/07_CONCURRENT_CLIENTS.md](phase4/07_CONCURRENT_CLIENTS.md). Prefer Direct Play MP4 (`streamMode=mp4`); transcode uses more of the link **and** the Pi CPU.

To measure **your** hop: `bench-serve` on the furnace, `bench-recv` on another host, then `estimate --usable-mbps <printed>`.

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
| healthcheck exit 1 | Read script sections (units, tools, status file, **peering share_live**, **library disk BAD**) | See [offline peering](#opt-in-vs-share-live-do-not-confuse-them); `opt-in` or `opt-out`; free space on `/media/sheep` |
| Sheep disk WARN / BAD | `python3 -m pipeline.library_disk check`; `df -h /media/sheep` | Delete with Shears (no auto-rotate yet); do not Hammer unless wiping the factory |
| Empty flock with commercial-safe on | Items Tags missing | `jellyfin_id_dump.py --items`; [private vs public](#private-vs-public-furnace) step 2 |
| Blank Roku SS | VoD Settings ever saved on this device? | Sideload VoD → Settings → re-sideload SS |
| Kodi SS hint / no video | `server_url` uses LAN IP? flock empty on Jellyfin? | `jellyfin_id_dump.py --items`; re-install zip after client fix |
| Kodi zip push fails | SMB `\\<Kodi_IP>\Downloads` vs SSH key | Use LibreELEC SMB; or install SSH key for `root@<Kodi_IP_Address>` |
| Offline peering (Opt In, no sync) | `healthcheck`: `BAD share not live`; `peering status` → `share_live: false` | `opt-in` with `TS_AUTHKEY` + Syncthing up, or `opt-out` |
| Peering stuck (live mesh) | `peering status`; inbox under `peers/inbox` | `promote --apply`; trust keys; share-security verify |
| Bad palette / encode | `refactor scan` | preview → apply pathway |
| Black / error after quarantine | Item gone from disk/Jellyfin; client still has old flock list | VoD 1.0.29 / Roku SS 1.0.8 / Kodi SS 0.2.7 drop the dead id and re-poll (30s rate limit). Sideload/install those packages; overnight new-sheep pickup still needs a new session ([phase4/00](phase4/00_OVERVIEW.md#client-polish-parked--not-numbered)) |
| Playback stutters / several TVs | `python3 -m pipeline.link_capacity estimate`; WiFi STA furnace? | Ethernet for the Pi; Direct Play; stay at/under `N_max` |
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
| `tests/` | Fast pytest suite (~372 tests collected; ~3s local) |
| `configs/` | Example YAML; live config is gitignored |
| `docs/phaseN/` | Feature guides (implementer SoT per topic) |
| `deploy/systemd/` | Unit files |
| `.github/workflows/tests.yml` | CI: pytest + exec bits on push/PR |
| `.github/workflows/release.yml` | Tag push: pytest → generic client zips → GitHub Release |

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
python3 -m pipeline.breed_idle      # daily idle breed (incl. tuple mode)
python3 -m pipeline.sheep_tuple     # stage loop A + edge + loop B genome
python3 -m pipeline.shears          # add/modify/delete/audit/sweep
python3 -m pipeline.hammer         # nuclear local reset
python3 -m pipeline.refactor        # quality scan/preview/apply/quarantine/batch
python3 -m pipeline.peering         # opt-in/out, publish, promote, keys
python3 -m pipeline.stills          # operator re-extract of screensaver frames
python3 -m pipeline.backfill_posters  # posters + stills + Jellyfin images
python3 -m pipeline.media_layout    # catalog dir modes 2775/664
python3 -m pipeline.job_recovery    # orphan job reclaim
python3 -m pipeline.hw_profile      # apply 16a/08a/04a profile
python3 -m pipeline.link_capacity   # concurrent-client N_max estimate
python3 -m pipeline.library_disk    # sheep-mount WARN/BAD
python3 -m pipeline.sheep_naming    # alias backfill / set / clear / resolve
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
| Link capacity / N_max | `pipeline/link_capacity.py`, `docs/phase4/07_CONCURRENT_CLIENTS.md` |
| Library disk check | `pipeline/library_disk.py`, `docs/phase4/06_LIBRARY_DISK_ROTATE.md` |
| Sheep aliases | `pipeline/sheep_naming.py`, `docs/phase4/09_SHEEP_NAMING.md` (LLM: [phase5/02](phase5/02_LLM_INTEGRATION.md) on agent platform) |
| License / Cesari watermark | [NOTICE](../NOTICE), [phase1/07](phase1/07_LICENSE_AND_METADATA.md), [watermark README](media/watermark/README.md), [Private vs public](#private-vs-public-furnace), [Use your own PNG](#use-your-own-png-private-and-public) |
| Catalog posters / stills | [Catalog posters](#catalog-posters-after-render) — `jellyfin.attach_posters` + `stills.enabled`; Roku SS Primary + Backdrop |
| Roku screensaver | `roku-screensaver/`, [phase3/01](phase3/01_SCREENSAVERS_AND_STILLS.md) |
| Roku client | `roku-channel/`, `docs/phase1/08_ROKU_BRIGHTSCRIPT.md` |
| Kodi screensaver | `kodi-screensaver/`, [phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) |
| Architecture | `docs/Pi5_Flam3_VoD_Pipeline.md` |

---

## Appendix A — Key paths (lab defaults)

| Path | Purpose |
|---|---|
| `/media/sheep/by-generation/` | Catalog MP4 + sidecar + poster + `stills/{stem}/` |
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
| Concurrent clients / N_max | [phase4/07_CONCURRENT_CLIENTS.md](phase4/07_CONCURRENT_CLIENTS.md) |
| Library disk check | [phase4/06_LIBRARY_DISK_ROTATE.md](phase4/06_LIBRARY_DISK_ROTATE.md) |
| Sheep aliases | [phase4/09_SHEEP_NAMING.md](phase4/09_SHEEP_NAMING.md) |
| LLM Agent Platform / Phase 5 | [phase5/00_OVERVIEW.md](phase5/00_OVERVIEW.md) (parked; not a furnace) |
| Peering | [phase2/05_SYNCTHING_GENOME_PEERING.md](phase2/05_SYNCTHING_GENOME_PEERING.md) |
| Phase 3 feature guides | [phase3/00_OVERVIEW.md](phase3/00_OVERVIEW.md) |
| Kodi screensaver (detail) | [kodi-screensaver/README.md](../kodi-screensaver/README.md) · [phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) |
| RC / acceptance | [phase3/10_TESTING_AND_ACCEPTANCE.md](phase3/10_TESTING_AND_ACCEPTANCE.md) |

---

*Document version: 2026-08-23 — Public launch (`v0.3.0`); fleet tip `2fca790` (post-launch OSS hygiene + share-security trust-key fix in `v0.3.1`).*
