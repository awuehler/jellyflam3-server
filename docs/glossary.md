# JellyFlam3 glossary

Terms, keywords, and phrases used across the **jellyflam3-server** project — docs, scripts, configs, and collateral (Electric Sheep, flam3, Jellyfin, Roku, Kodi). Intended for operators, contributors, and the Phase 4 end-user guide / runbook.

**See also:** [README.md](README.md) (guide index) · [Pi5_Flam3_VoD_Pipeline.md](Pi5_Flam3_VoD_Pipeline.md) (architecture source of truth)

---

## Quick index (A–Z)

| | | | |
|---|---|---|---|
| [Archive seed](#archive-seed) | [Direct Play](#direct-play) | [Idle gate](#idle-gate) | [Pedigree](#pedigree) |
| [BrightScript](#brightscript) | [Direct Stream](#direct-stream) | [Inbox](#inbox) | [Peering](#peering) |
| [Brood](#brood) | [Display profile sink](#display-profile-sink) | [JellyFlam3 Hammer](#jellyflam3-hammer) | [Promote (peering)](#promote-peering) |
| [Catalog](#catalog) | [Edge](#edge) | [Jellyfin flock](#jellyfin-flock) | [Quarantine](#quarantine) |
| [Closed loop](#closed-loop) | [Electric Sheep](#electric-sheep) | [Land (peers)](#land-peers) | [Release candidate (RC)](#release-candidate-rc) |
| [Commercial mode](#commercial-mode) | [Flock](#flock) | [Loop (VoD)](#loop-vod) | [Sheep Shears](#sheep-shears) |
| [ContentNode](#contentnode) | [flam3](#flam3) | [OkLCh palette](#oklch-palette) | [Sheep tax](#sheep-tax) |
| [Cron wrappers](#cron-wrappers) | [Free Sheep](#free-sheep) | [Opt In / Opt Out](#opt-in--opt-out) | [Sidecar](#sidecar) |
| [Deep link](#deep-link) | [Furnace](#furnace) | [Path 1 / Path 2](#path-1--path-2) | [Stills](#stills) |
| [Display probe](#display-probe) | [Genome](#genome) | [Period snap](#period-snap) | [Syncthing](#syncthing) |
| [Dynamic duration](#dynamic-duration) | [Gold Sheep Lite](#gold-sheep-lite) | [PlaybackInfo](#playbackinfo) | [Tailscale](#tailscale) |
| [ECP](#ecp-external-control-protocol) | [HLS](#hls) | [Poster / Primary](#poster--primary) | [TV-port](#tv-port) |
| [Edition (render)](#edition-render) | [HW profile](#hw-profile) | [Pre-share / post-share](#pre-share--post-share) | [Viewer feedback](#viewer-feedback--sheep-vote) |
| [`.flam3`](#flam3-file) | [Idle breed](#idle-breed) | [RC](#release-candidate-rc) | [Sheep naming / alias](#sheep-naming--alias) |
| [N_max](#n_max-link-capacity) | [Library disk check](#library-disk-check) | [VoD](#vod) | [Worker](#worker) |

---

## Project & phases

### JellyFlam3 / JellyFlam3 Server

Self-hosted generative media server: render **flam3**-style flame fractals, encode to H.264, organize as a **flock** in **Jellyfin**, stream to **Roku** / **Kodi** and similar clients. Product layer around generate → encode → flock → stream. Repo: `jellyflam3-server`.

### Furnace

Informal name for the render factory on a Pi — **worker** + **flam3-animate** + **ffmpeg** + scratch I/O. “Keep the furnace busy” = maintain inbox feedstock (archive cron + **idle breed**). Clients are the **pasture** (consume finished loops; do not render).

### Phase 1 / 2 / 3 / 4

Delivery phases in `docs/phaseN/`. **Phase 1** (complete): toolchain, worker, Jellyfin, Roku channel, idle gate. **Phase 2** (complete): archive seed, flock UX, HLS, peering, sheep tax, pedigree, dynamic duration. **Phase 3** (complete — Owner OK 2026-08-23): stills, Kodi screensaver, Shears, share security, git pedigree, Hammer, ID dump, refactor, furnace client presets, acceptance. **Phase 4** (synopsis): peer path, mesh scripting, edges/watermark, Roku publish, end-user guide, library rotate, concurrent clients, viewer feedback, sheep naming.

### Release candidate (RC)

Tagged git revision that passes regression + feature checklists in [phase3/10_TESTING_AND_ACCEPTANCE.md](phase3/10_TESTING_AND_ACCEPTANCE.md) before Owner sign-off.

### Source of truth (SoT)

Canonical architecture doc: [Pi5_Flam3_VoD_Pipeline.md](Pi5_Flam3_VoD_Pipeline.md). Per-topic guides under `docs/phaseN/` are discrete task boundaries.

### Owner OK

Guide exit sign-off recorded in phase docs (name + date). Marks a guide complete for that phase.

---

## Electric Sheep & flam3 ecosystem

Collateral: [electricsheep.org](https://electricsheep.org/) · [electricsheep.com/archives](https://electricsheep.com/archives/) · [scottdraves/flam3](https://github.com/scottdraves/flam3) · [scottdraves/electricsheep](https://github.com/scottdraves/electricsheep) · [electricsheep.org/license](https://electricsheep.org/license/)

### Electric Sheep (ES)

Distributed screensaver / flock-evolution project (Scott Draves). JellyFlam3 uses ES **Free Sheep** `.flam3` **archives** as feedstock and ES **dogma** (continuous morph, living canvas) as product inspiration — but does **not** run the classic ES P2P network.

### Free Sheep

CC-licensed genomes from the public [Electric Sheep archives](https://electricsheep.com/archives/) (generations 247, 245, …). Distinct from **Gold Sheep** / paid Spotworks content (do not ingest).

### Gold Sheep

Paid / non-CC Electric Sheep masters (HiFi Dreams, Spotworks). **Out of scope** for the furnace — personal viewing only per [ES terms](https://electricsheep.org/termsofservice/).

### flam3

Open-source flame-fractal renderer and genome toolkit ([flam3.com](https://flam3.com/)). JellyFlam3 uses **`flam3-genome`**, **`flam3-animate`**, **`flam3-render`** locally — no live ES servers required.

### `.flam3` file

XML genome describing one or more **flames** (variation sets). Input to TV-port, sequence, animate, and breed. Filename convention: `electricsheep.{kind}.{id}.flam3` — see [phase1/07_LICENSE_AND_METADATA.md](phase1/07_LICENSE_AND_METADATA.md).

### flam3-genome

Genome factory binary: random, **mutate**, **cross**, **interpolate**, **sequence** (edges), rotate. Used by **breed**, **seed_inbox**, and (Phase 4) edge generation.

### flam3-animate

Renders a sequenced genome to a frame sequence (PNG/JPG scratch). CPU-heavy; capped by **idle gate** and `render.max_cpus`.

### flam3-render

Poster / still extraction from genomes (optional companion to animate).

### Genome

A single `.flam3` file (sheep DNA). May contain multiple **flames**; catalog policy usually **strip_to_first** for one closed loop per VoD.

### Human / brood

ES license provenance: **human** = designer-uploaded sheep (often CC BY); **brood** / algorithm = robot-evolved (often CC BY-NC). Robot remix of human → NC stays NC.

### Generation

Electric Sheep flock epoch (e.g. **247**). Archive URLs: `…/generation-{N}/best/page/{1,2,3}.html`. Tag: `generation-NNN`.

---

## JellyFlam3 pipeline & data flow

### Worker

`pipeline/worker.py` / `jellyflam3-worker.service`. Polls **`genomes/inbox`**, runs tax → TV-optimize → animate → ffmpeg → ingest to **catalog**, writes **sidecar**, optional Jellyfin poster/metadata.

### Inbox

`paths.genomes_inbox` — staging queue for genomes awaiting render. Sources: archive seed, **idle breed**, **Shears** add/modify, manual seed, **peering promote** (after gate).

### Quarantine

`paths.genomes_quarantine` — failed sheep tax, bad peer integrity, or unrecoverable genomes. Not auto-rendered.

### genomes_done

Post-render parent pool (`paths.genomes_done`, default `genomes/done`). Successful inbox renders archive here for **pedigree** parent selection.

### Catalog

Finished VoD on disk: `/media/sheep/by-generation/{gen}/electricsheep.{gen}.{id}.mp4` (+ poster, sidecar). Live Jellyfin **Sheep** library points at `/media/sheep/by-generation` (not the mount root).

### by-generation

Catalog folder layout under `media_library`: one directory per ES generation (e.g. `247/`).

### Sidecar

JSON metadata beside catalog MP4: `{stem}.jellyflam3.json`. **Sole metadata source of truth** for that sheep: license/tags, duration, signals, poster/stills **index**, pedigree hints, (Phase 4 reserved) `type` / `watermark` / `viewer_feedback` / `alias`. Schema: [phase1/07](phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Jellyfin Items Tags/Overview are derived caches only. Not a substitute for the `.mp4` bytes, `.flam3` genome, or poster/stills files. See also [phase4/03](phase4/03_EDGES_AND_WATERMARK.md), [phase4/08](phase4/08_VIEWER_FEEDBACK_LOOP.md), and [phase4/09](phase4/09_SHEEP_NAMING.md).

### Smoke render

Short non-catalog test via `scripts/smoke_render.sh` (`JELLYFLAM3_SMOKE=1`, ~13 s). Uses pedigree smoke seed; prints `SMOKE_RENDER_OK`.

### Job recovery / orphan

`pipeline/job_recovery.py` — reclaims crashed mid-render jobs (no live `flam3-animate`/`ffmpeg`), drops frames, re-queues inbox genomes when needed. States: `orphaned`, `superseded`.

### Cron wrappers

`scripts/cron_archive_seed.sh` (~10-day staggered archive fill) and `scripts/cron_breed_idle.sh` (daily **05:11** idle breed). Both prepend `/usr/local/bin` to `PATH` for **flam3-genome**. Phase 4 adds a planned **share-votes** cron ([phase4/08](phase4/08_VIEWER_FEEDBACK_LOOP.md)) for liked sheep → peer share-out.

### Idle breed

`pipeline/breed_idle.py` / daily cron. When inbox empty + gate open + not near archive cron: breed **one** pedigree child (mutate/cross/blend/interpolate). History: `breed_idle_history.json`. Per-host archive cron for the `archive_cron_imminent` skip is merged from `configs/profiles/rpi-jellyflam3-{16,08,04}.yaml` via `hw_profile apply`. JSON `--evaluate` output includes `hours_until_archive` (rounded) and `next_archive_at`. Phase 4 may weight parent selection from catalog sidecar `viewer_feedback` ([phase4/08](phase4/08_VIEWER_FEEDBACK_LOOP.md)).

### Viewer feedback / sheep vote

Phase 4 design ([phase4/08](phase4/08_VIEWER_FEEDBACK_LOOP.md)): Roku VoD transient overlay near end of each sheep invites like/love/vote **without stopping playback**. Tallies live on the catalog **sidecar** (`viewer_feedback`); re-votes allowed. Share cron and idle-breed bias read that sidecar only.

### Sheep naming / alias

Phase 4 design ([phase4/09](phase4/09_SHEEP_NAMING.md)): furnace auto-generates a short memorable **alias** (`adjective_surname`, e.g. `frosty_swirles`) on the catalog sidecar; human override sticky; optional later LLM-from-poster. Peer clients may toggle **filename vs alias** display. Not the same as flam3 XML **`nick`** (designer credit for license).

### flam3-genome maximum attempts warning

Benign stderr from **flam3-genome** (not JellyFlam3): `warning: reached maximum attempts, giving up.` during mutate/cross when the upstream optimizer exhausts retries. Safe to ignore when cron ends `DONE action=breed` and a child lands in inbox.

### Archive seed

`pipeline/seed_inbox --archive` — random pick from `archive_seed_manifest.json`, fetch `.flam3`, **TV-port**, stage inbox. Default **`--skip-catalog`** skips sheep that already have catalog MP4.

### `--skip-catalog`

Default on: do not re-stage archive picks that already have a catalog MP4. Keeps furnace on new work between archive fills. Opt out: `--no-skip-catalog`.

### Backlog gate

`cron_archive_seed.sh` math: skip fetch if inbox cannot drain before next cron (`max_clearable` vs `inbox_count`).

---

## Render, encode & quality

### TV-port

Resize/rewrite genome for TV: **1920×1080**, scale, **Gold Sheep Lite** quality attrs, **OkLCh** palette. `pipeline/tv_optimize.py` + `palette_harmony.py`.

### Gold Sheep Lite

Locked render **edition** for Pi fleet: quality ≈900, temporal_samples 450, supersample 2, **3 cores** (`max_cpus: 3`). H.264 High **L4.2** + AAC for Jellyfin remux.

### Edition (render)

Named quality preset in config (`gold_sheep_lite`, `compact` on **-04** profile — same Lite knobs, shorter duration bias).

### OkLCh palette

Perceptual color harmony: complementary (default) or split-complementary dual-pole rewrite of 256 flam3 colors, chroma-capped for ambient TV. Baked into masters (not client LUT).

### VoD

Video-on-demand sheep clip — one seamless **loop** MP4 in catalog (not cinema-length features).

### Loop (VoD)

Single-genome **360° closed orbit** — first and last frames match for seamless repeat. Roku `Video.loop = true`.

### Closed loop

Same as loop — one full rotation over `nframes` at chosen fps; period-aware **snap** may extend length for seamless closure.

### Edge

Phase 4: **transition** clip between two loops via `flam3-genome sequence=` — morph A→B, not a standalone closed loop. Kodi ES dogma: loop → edge → loop.

### Dynamic duration

`pipeline/choose_duration.py` — VoD length from XML **signals** (complexity, queue pressure, periods). Soft max (profile-dependent) vs hard max **120 s**; smoke fixed ~13 s.

### Period snap

`snap_to_periods: true` (fleet default): LCM-align `nframes` to rotation/color/animate periods for seamless loops. May blow up toward soft max (accepted cost).

### nframes

Frame count for animate = `round(duration_sec × fps)`. Drives render time and scratch size.

### HW profile

`pipeline/hw_profile.py` — overlays for **rpi-jellyflam3-16 / 08 / 04** (RAM/disk class): VoD bands, `dynamic.base_sec`, edition `compact` on -04.

### Direct Play

Client plays the static MP4 bytes without re-encode. URL pattern: `…/Videos/{id}/stream.mp4?Static=true`. Preferred for ambient **loop** on Roku (shorter gap than HLS re-loop).

### N_max (link capacity)

Integer estimate of concurrent **video** sessions one JellyFlam3-server can carry on a LAN hop: `floor(usable_bps × (1 − headroom) / session_bps)`. CLI: `python3 -m pipeline.link_capacity`. Not a Jellyfin connection cap. Guide: [phase4/07_CONCURRENT_CLIENTS.md](phase4/07_CONCURRENT_CLIENTS.md).

### Library disk check

Operator check of the sheep mount (`paths.media_library`) used % / free GiB. CLI: `python3 -m pipeline.library_disk check`. Healthcheck WARN (exit 0) vs BAD (exit 1). Auto-purge / rotate still parked. Guide: [phase4/06_LIBRARY_DISK_ROTATE.md](phase4/06_LIBRARY_DISK_ROTATE.md).

### Direct Stream

Jellyfin **remux**es H.264+AAC master into HLS segments (copy codecs, no full transcode). Preferred HLS path for Gold Sheep Lite masters.

### HLS

HTTP Live Streaming via Jellyfin: `main.m3u8?MediaSourceId={id}&AudioCodec=aac`. Phase 2 first-class delivery; long sessions may hit remux lifecycle limits — MP4 fallback documented.

### PlaybackInfo

Jellyfin `POST /Items/{id}/PlaybackInfo` — reports DirectPlay / DirectStream / Transcode capabilities.

### Stills

Phase 3: JPEG frames extracted from catalog MP4s (`pipeline/stills.py`) under `by-generation/…/stills/{stem}/` for **Roku Screensaver** (no video in screensaver package).

---

## Jellyfin & library

### Jellyfin flock

The Sheep **library** in Jellyfin — curated MP4s, posters, metadata, tags. Single stream origin for clients.

### Path 1 / Path 2

**Path 1:** official [jellyfin-roku](https://github.com/jellyfin/jellyfin-roku) app. **Path 2:** custom **JellyFlam3** Roku channel (`roku-channel/`) against same Items + stream APIs.

### Poster / Primary

Mid-loop JPEG beside MP4 and/or Jellyfin **Primary** image via Images API. Phase 2 flock UX (`pipeline/flock_artwork.py`, `backfill_posters.py`).

### Commercial mode

`license.commercial_mode` + channel `commercialMode` — filter out `cc-by-nc` items when enabled. Default off for private lab.

### Library refresh

Jellyfin scan after ingest or Hammer/Shears — `Library/Refresh` API.

### Display profile sink

`pipeline/display_profile_sink` on port **8791** — LAN HTTP upsert of per-screen TV profiles (Roku **display probe**). Optional token auth.

### Display probe

Roku channel POSTs video mode / display summary after “Fetch TV display”; stored under `display_profiles/`.

---

## Clients (Roku & Kodi)

Collateral: [developer.roku.com](https://developer.roku.com/) · [Roku media specs](https://developer.roku.com/docs/specs/media.htm) · [Kodi add-on docs](https://kodi.wiki/)

### BrightScript

Roku scripting language (`.brs`). JellyFlam3 VoD channel + Screensaver logic.

### SceneGraph

Roku UI framework (XML + BrightScript). **VoD channel** uses `Video` node; **Screensaver** must not use video per platform rules.

### ContentNode

SceneGraph media descriptor — `url`, `streamFormat` (`hls` | `mp4`), `title`, `length`, Jellyfin item id.

### Sideload

Install dev channel zip via Roku Developer Application Installer (`package_roku_*.sh` → `dist/*.zip`). On a **furnace Pi**, zips include `registry/jellyflam3-presets.json` (Jellyfin URL, API key, user/library ids for that host). One sideload slot per device (VoD vs Screensaver alternate).

### Deep link

Launch VoD channel with `contentId` (Jellyfin item id) — ECP / `roInputEvent`. Screensaver package cannot deep link.

### ECP (External Control Protocol)

Roku HTTP control on port **8060** — launch, query player (`/launch/dev`, `/query/media-player`).

### RunScreenSaver()

Roku screensaver entry point only — separate package from VoD `Main()`. JellyFlam3 Screensaver: stills/slideshow (Phase 3 guide 01).

### Kodi ES screensaver

Phase 3 `screensaver.jellyflam3` — Electric Sheep **dogma** (video loops; loop→edge→loop post-launch). **Complete** loops-only (Owner OK 2026-08-21). Example pasture host: `rpi-kodi-08a` (LibreELEC). Separate from Roku stills track.

### JSON-RPC (Kodi)

Local control API (lab port 9090) — activity wakes screensaver; distinct from Jellyfin HTTP.

---

## Peering, security & sharing

Collateral: [syncthing.net](https://syncthing.net/) · [tailscale.com](https://tailscale.com/)

### Peering

Private **JellyFlam3 ↔ JellyFlam3** genome sharing: Syncthing over Tailscale. Default **Opt Out**.

### Opt In / Opt Out

User-facing peering switch via `python3 -m pipeline.peering opt-in|opt-out`. Starts/stops Syncthing + Tailscale flock enrollment; writes `peering_status.json`.

### Tailscale

WireGuard-based **tailnet** underlay for peer Syncthing — no public discovery. Tag example: `tag:jellyflam3`.

### Syncthing

Folder sync for allowed globs only (`*.flam3`, optional `*-poster.jpg`, integrity sidecars). Managed config; `.stignore` enforces allowlist.

### Land (peers)

Files arrive in `genomes/peers/inbox/` via Syncthing — **not** worker-visible until **promote**.

### Promote (peering)

`peering promote --apply` — verify **share security** → **sheep tax** → move to `genomes/inbox/`. Fail → **quarantine**.

### Gated promote

Locked model: peer inbox never auto-drains; operator (or future automation) must promote explicitly.

### Pre-share / post-share

**Pre-share:** `peering publish` — tax, sign/hash, stage `peers/share-out`. **Post-share:** verify integrity before tax on inbound promote.

### Share security

Phase 3 integrity: **Ed25519** detached sig (`.flam3.jellyflam3.sig`) preferred; **SHA-256** sidecar (`.flam3.sha256`) fallback. Trust store in `trusted_keys_dir`.

### Sheep tax

XML/vocab **scan and repair** before trust (`pipeline/sheep_tax.py`). Every sheep pays the “tax” before furnace or share. Distinct from cryptographic share security.

---

## Pedigree & curation tools

### Pedigree

Locally bred sheep via mutate/cross/interpolate with lineage **sidecar** (`origin: local_pedigree`, `parents[]`). Names: `electricsheep.pedigree.*`.

### Mutate / cross / blend / interpolate

**Mutate:** one parent, random variation. **Cross/blend:** two parents, `method=alternate|union`. **Interpolate:** two parents, `method=interpolate` (explicit, not alias for blend).

### Git pedigree sheep

Curated `genomes/pedigree/` in repo (smoke + examples). Distinct from archive `genomes/samples/` feedstock (**2 sheep per gen** for `247…242`: one CC BY + one CC BY-NC for commercial-mode lab checks — [phase1/07](phase1/07_LICENSE_AND_METADATA.md#lab-check--commercial-mode-toggle)).

### Sheep Shears

`pipeline/shears.py` — curator **add / modify / delete** with cascade to MP4, sidecars, Jellyfin, jobs, peers, stills. Confirm token: `DELETE`.

### JellyFlam3 Hammer

`pipeline/hammer.py` — **nuclear local reset**: jobs, frames, inbox, catalog, done pool (tiers). Confirm: `HAMMER`. Not per-sheep — use Shears for that.

### Sheep refactor

Phase 3 guide [09](phase3/09_SHEEP_REFACTOR.md) (**complete** — Owner OK 2026-08-21) — remediate sub-standard sheep (quality / palette / encode) via re-furnace. Pathways: scan/report (includes complementary palette; **hard-quarantine** `genome_linear_only` and `genome_singularity_cloned`), optional palette override + Jellyfin-visible poster preview under `/media/sheep/_refactor-preview/`, apply/replace, quarantine, batch. Not Shears (CRUD) and not Hammer (wipe).

---

## Ops, hosts & paths

### Furnace Pi / lab fleet

Hosts `rpi-jellyflam3-16a`, `08a`, `04a` — render + Jellyfin. Install path: `/opt/jellyflam3-server` (symlink to clone). User: `jellyflam3`.

### HW classes (-16 / -08 / -04)

Pi 5 tiers by RAM/NVMe/sheep disk — see [phase2/09_PI_FROM_SCRATCH.md](phase2/09_PI_FROM_SCRATCH.md).

### `/media/sheep`

USB/NVMe **mount** for catalog. Jellyfin libraries are hard-separated under it: live **Sheep** → `/media/sheep/by-generation`; refactor previews → `/media/sheep/_refactor-preview/` (see [phase3/09](phase3/09_SHEEP_REFACTOR.md)). Pipeline `paths.media_library` remains the mount root (`/media/sheep`); code appends `by-generation/`.

### `/var/cache/jellyflam3`

Scratch: frames, transcodes, images, smoke. Jellyfin CachePath.

### `/var/lib/jellyflam3`

State: jobs, logs, idle gate status, display profiles, breed history, peering status.

### secrets.env

Local credentials (Jellyfin URL/key, Tailscale auth, display sink token). Never commit.

### healthcheck.sh / status_report.sh

Ops scripts: pass/fail health vs informational snapshot (inbox, thermals, gate).

### systemd units

`jellyflam3-worker`, `jellyflam3-idlegate`, `jellyflam3-display-sink`, optional `jellyflam3-syncthing`.

---

## Idle gate & playback coexistence

### Idle gate

Supervisor (`pipeline/idle_gate.py`) polling Jellyfin **Sessions**. Closes **gate** when TV-class client is **Playing** or transcoding; worker pauses new renders until `idle_delay_sec` clear.

### Gate open / gate closed

Status in `/var/lib/jellyflam3/idle_gate_status.json`. Worker checks before starting jobs.

### Playing API

JellyFlam3 Roku channel POSTs session heartbeats so Direct Play/HLS counts as active TV playback for the gate.

### block_on_any_transcode

When true, any Jellyfin transcode session closes the gate (protects Pi CPU during heavy transcodes).

---

## Licensing & metadata tags

| Tag | Meaning |
|---|---|
| `cc-by` | Attribution OK; allowed when commercial mode on |
| `cc-by-nc` | Non-commercial only; excluded when commercial mode on |
| `generation-NNN` | Archive generation |
| `sheep-ID` | Serial from filename |
| `human` / `brood` | Designer vs algorithm provenance |
| `screensaver-safe` | Stills approved for Roku screensaver strip |
| `local_pedigree` | Sidecar origin — bred on this host |
| `archive` | Archive feedstock (implicit for Free Sheep picks) |

### Infinidream

Separate ES cloud/app product — not Phase 1 feedstock.

---

## External collateral (connected vocabulary)

Terms you will see in upstream docs and community material:

| Term | Source | Relevance to JellyFlam3 |
|---|---|---|
| **Fractal flame** | flam3 / Apophysis lineage | What `.flam3` describes |
| **IFS / variation** | flam3 wiki | Genome structure (`xform`, `coefs`) |
| **Sheepserver** | ES infrastructure | Historical `.flam3` download host (archive fetch tries multiple URLs) |
| **OkLab / OkLCh** | color science | Palette harmony implementation space |
| **Rec.709 / yuv420p** | video standards | Encode target for Direct Stream |
| **fMP4 / MPEG-TS** | HLS packaging | Jellyfin remux segment formats |
| **MediaBrowser Token** | Jellyfin auth header | API key / session auth in clients |
| **roUrlTransfer / Task node** | Roku SceneGraph | Off-UI-thread HTTP in channel |
| **roRegistrySection** | Roku storage | Channel settings persistence |
| **Addon (Kodi)** | Kodi extension | `screensaver.jellyflam3` install-from-zip |
| **LibreELEC / CoreELEC** | Kodi distros | Target Kodi lab platforms |
| **STUN / discovery** | Syncthing | Disabled for flock — use Tailscale only |
| **Ed25519** | cryptography | Share-security signatures |
| **CC BY / BY-NC** | Creative Commons | Free Sheep license classes |

---

## Abbreviations

| Abbr | Expansion |
|---|---|
| **AAC** | Advanced Audio Codec (silent stereo track on masters) |
| **API** | Application programming interface (Jellyfin REST) |
| **BY / BY-NC** | Creative Commons Attribution / NonCommercial |
| **DOM** | Day-of-month (cron stagger for archive seed) |
| **ECP** | Roku External Control Protocol |
| **ES** | Electric Sheep |
| **HLS** | HTTP Live Streaming |
| **HW** | Hardware (profile class) |
| **ID** | Jellyfin item Guid or sheep serial |
| **JPEG** | Stills / poster format |
| **LAN** | Local area network (Jellyfin base URL for clients) |
| **LCM** | Least common multiple (period snap) |
| **MP4** | Catalog container format |
| **NC** | Non-commercial (license) |
| **NVMe** | Preferred Pi scratch/sheep storage |
| **OSD** | On-screen display (absent in screensaver save path) |
| **PATH** | Shell executable search path (`/usr/local/bin` for flam3) |
| **RC** | Release candidate |
| **SoT** | Source of truth |
| **SSH** | Remote admin to fleet Pis |
| **VoD** | Video on demand (sheep clip, not feature film) |
| **XML** | Genome file format inside `.flam3` |

---

*Last expanded: 2026-08-20 — adds sheep naming / alias; aligns with docs through Phase 4 synopsis and RC test contracts.*
