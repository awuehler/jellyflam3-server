# Changelog

All notable changes to this project are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- Fleet log hygiene: persistent journald (class-sized) + 72h `jellyflam3-logrotate.timer`; compress file-log backups after 11 days; purge after 23 days (`scripts/enable_log_hygiene.sh`).
- Opt-In watchdog LAN heal: ping default gateway; rate-limited Wi‑Fi bounce (`nmcli`) before Tailscale re-auth (`peering.watchdog.*`).
- Sheep refactor Pathway A: `catalog_desaturated` + `palette_washed_out` heuristics for grey/muddy catalog sheep.
- Sheep refactor Pathway A: `genome_orbit_frozen` candidate (score 25) when `flam3-genome sequence=` cannot 360°-orbit; worker still-loops one Lite still (`render.still_loop_if_orbit_frozen`, default on). Duration does not snap frozen `rotate=` as a loop period.
- Printable Layer 1 fridge card (`docs/FRIDGE_CARD.md`) — watch / gate / Settings / triage; no API keys.
- Phase 4 guide 05 baseline complete: four worked examples in the user guide (first evening, screensaver, two Rokus, peer receive); Owner OK 2026-09-03.
- Concurrent-client estimator (`python3 -m pipeline.link_capacity`): integer `N_max` from usable hop × headroom ÷ session bps; WiFi-STA lab note in guide 07. **Owner OK 2026-09-09**.
- Sheep-library disk check slice (`python3 -m pipeline.library_disk`): healthcheck WARN/BAD on mount used % / free GiB; no auto-purge, no worker refuse.
- Catalog sidecar schema: Phase 4 keys `type`, `watermark`, `viewer_feedback`, `alias` reserved in [phase1/07](docs/phase1/07_LICENSE_AND_METADATA.md); `pipeline.stills.SIDECAR_RESERVED_KEYS`. Tuple ingest writes `type` / `from_id` / `to_id` / `watermark`. Worker copies reserved keys on re-ingest so votes and aliases survive Shears-modify.
- Phase 4 tuples: one MP4 (loop A + watermarked edge A→B + loop B) under `by-generation/tuple/`; idle-cron mode; Roku shuffle includes `pedigree` and `tuple` (channel 1.0.28). Edge mark: Cesari PNG on private furnaces (`license.commercial_mode: false`); ES attribution sentence (no logo) when commercial_mode is on. Look/feel: [phase4/03](docs/phase4/03_EDGES_AND_WATERMARK.md#look-and-feel-what-the-viewer-sees).
- Phase 4 client polish: wrap-once flock re-fetch + 313 session cap — Roku VoD **1.0.31**, Roku screensaver **1.0.9**, Kodi screensaver **0.2.9**. After a full shuffle wrap (one random permutation of the in-memory list), clients re-fetch Jellyfin and rebuild the list. The new permutation is rotated so the first item is not the last-played id (no wrap-seam back-to-back). Skip if a fetch is already in flight; no 30s 404 gate. HTTP Limit is 5000; if more than 313 artifacts remain after filters, randomly prune to 313. Single-item lists do not wrap-refetch.
- Phase 4 client polish: mid-session 404 / quarantine re-poll — Roku VoD **1.0.29**, Roku screensaver **1.0.8**, Kodi screensaver **0.2.7**. Drop the dead Jellyfin id, re-poll Items (30s rate limit), continue the session. Does not invent a Playing session for the miss.
- Phase 4 sheep naming RNG: `python3 -m pipeline.sheep_naming` hash-seeds `adjective_surname` on ingest/backfill; `set-alias` / `clear-alias` sticky human override. Pasture filename/alias toggle stays parked. LLM naming moved to Phase 5.
- Phase 5 synopsis (parked): two deployments — **A** JellyFlam3 Furnace (Pi 5, existing playbook) and **B** LLM Agent Platform (Arduino Ventuno Q). Not interchangeable, not overlapping. BOM + agent bring-up + furnace contracts + platform gaps — [docs/phase5/](docs/phase5/00_OVERVIEW.md).

### Fixed

- Jellyfin 10.11 Images API: POST Primary/Backdrop as **base64** (`encode_image_upload_body`). Raw JPEG bytes 500 (`GetFromBase64Stream` / `FormatException`). VoD tiles need `ImageTags.Primary`; Roku SS Backdrops need `BackdropImageTags` — disk JPEGs under `stills/.ignore` are neither.
- `backfill_posters.needs_backfill`: sidecar `local_primary` is not a live Primary; extracted stills without `jellyfin_stills` `uploaded` are not live Backdrops.
- Roku screensaver 1.0.9 wrap re-fetch: rotate the **new** URL mix past the still on screen (`rotateUrlsPast` on apply), matching VoD / Kodi seam rule.
- LibreELEC BusyBox `unzip` can write NUL-padded `default.py` / binary `settings.xml` for the Kodi screensaver; install-from-zip or Python `zipfile` instead.
- Ed25519 trust enrollment flake: do not `.strip()` exact 32-byte raw public keys (whitespace bytes are valid key material; broke `test_trust_key_enrolls_peer` intermittently on CI).
- Redact `--auth-key=` values in `pipeline.peering` command logs.
- Client sheep rotate stays **on**: Roku VoD **1.0.30** always writes `shuffleFlock=true` on launch (heals leftover `false` across sideload). Furnace presets no longer copy package shuffle onto the device. Kodi **0.2.8** heals persisted `shuffle=false` and always rotates. Roku screensaver still ignores `shuffleFlock`.
- `pipeline.backfill_posters` / `pipeline.stills` no longer extract frames from `_refactor-quarantine/` or `_refactor-preview/` MP4s (those would rewrite live `by-generation/{gen}/stills/{stem}/` for unpublished sheep).
- Restore Kodi `resources/icon.png` (was committed as `icon-.png`, which failed CI package checks).

### Changed

- Catalog posters live with screensaver frames under `by-generation/{gen}/stills/{stem}/{stem}-poster.jpg`. Jellyfin skips that tree via `stills/.ignore` so the library console lists MP4s (and sidecars) without extra JPEG items. Backfill relocates leftover sibling `{stem}-poster.jpg` next to the MP4. Unpublished quarantine/preview trees keep a sibling poster. Clients still use Jellyfin Images Primary/Backdrop APIs (no Roku/Kodi version bump).

- Phase 4 overview: tuples (03) shipped; pytest **366** passed + 6 skipped.
- Commercial-safe furnaces skip the Cesari Electric Sheep logo on tuple edges and burn the ES attribution sentence instead (`license.commercial_mode: true`). Private flock may still overlay the PNG pending permission.
- NOTICE / LICENSE carve-out for Cesari watermark assets; Layer 2 operator warning; furnace `commercial_mode` no longer documented as culling NC at render.
- User guide: full private → public and public → private furnace sequences (yaml, worker, tags, tuple re-furnace, client toggles).
- Operator PNG (`watermark.image`) overlays on private mixed **and** commercial-safe furnaces; Cesari filenames stay public-blocked.
- Ingest posters default to `jellyfin.attach_posters: auto` — skip on a standalone furnace; create when 2+ furnaces are live on Tailscale/Syncthing. `true` / `false` override; `backfill_posters` always extracts.
- Screensaver stills merge into the poster pipeline: ingest / `backfill_posters` extract frames and upload Jellyfin Backdrops (never from tuples). Roku screensaver 1.0.7 cycles Primary + Backdrop from all folders except `tuple`, always rotates, honors `commercialMode`.
- Corner watermark is a **sheepcloud** (docs, yaml, tests); not a “bug.”
- Kodi / Roku client icon and splash PNGs replaced (numbered `-00`/`-01` kept as source; packages ship the unnumbered files).

## [v0.3.1] — 2026-08-23

Post-launch maintenance — OSS hygiene, CI hardening, and share-security fix.

### Added

- GitHub issue templates (bug / question), PR template, Dependabot, `CODEOWNERS`, [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
- Tag-triggered [release workflow](.github/workflows/release.yml) with pytest gate before publishing client zips.

### Fixed

- Ed25519 peer trust enrollment when `.pub` is missing or corrupt — heal from sibling `.pem` (`share_security`).

### Changed

- DeepWiki hints (`.devin/wiki.json`) and doc test counts aligned to public launch (`v0.3.0`+).
- CI: **303** tests on Linux (1 skipped); **299** passed + 5 skipped on Windows.

---

## [v0.3.0] — 2026-08-23

First public release — Phase 3 complete.

### Added

- **Roku VoD channel** (manifest 1.0.26) — Jellyfin flock browser, ambient MP4 loop, idle-gate session reporting, HLS option, commercial filter; optional furnace preset zips when packaged on a Pi.
- **Roku screensaver** (1.0.6) — stills/posters from Jellyfin Primaries; shared `JellyFlam3` registry with VoD.
- **Kodi screensaver** (0.2.6) — Electric Sheep–dogma video loops from Jellyfin flock; LibreELEC install-from-zip.
- **Pipeline:** Sheep Shears, JellyFlam3 Hammer, sheep refactor (pathways A/P/B/C/D), share security (Ed25519 + SHA-256), stills extract, `jellyfin_id_dump` + `client_pack_presets`.
- **Peering:** Syncthing over Tailscale for `*.flam3` genomes; Opt In/Out; gated promote.
- **Docs:** Phases 1–3 guides, layered [USER_GUIDE_AND_RUNBOOK.md](docs/USER_GUIDE_AND_RUNBOOK.md), glossary, architecture SoT.
- **CI:** GitHub Actions pytest + executable-bit check (~303 tests on Linux).

### Fixed

- Jellyfin nested-library flock query — clients now merge child-folder results (partial flat `ParentId` hits no longer block full flock).
- Ed25519 verify when `.pub` is missing but private key exists (`share_security`).

### Release assets

Generic client zips (no baked-in Jellyfin credentials — configure in channel/add-on Settings, or rebuild on a furnace Pi with `secrets.env`):

- `jellyflam3-roku.zip` — Roku VoD channel
- `jellyflam3-screensaver.zip` — Roku screensaver / Backdrop
- `screensaver.jellyflam3.zip` — Kodi screensaver add-on

### Demo media

- Poster still: [docs/media/demo/](media/demo/) (`electricsheep.242.03322`, CC BY, from 04a catalog) — README / release preview image only.

### Known limitations

- Roku **developer sideload** only — no Channel Store package in v0.3.0.
- One Roku sideload slot (VoD ↔ screensaver alternate).
- Loops-only screensavers (no edge crossfades / watermark yet).
- No library disk auto-rotate; peering mesh introduce is manual.
- Render time: hours per sheep; months for a large flock.

### Post-launch roadmap (not in v0.3.0)

Edges + watermark, Roku Channel Store publish, viewer feedback, sheep naming, mesh scripting, library rotate, concurrent-client estimates — tracked under `docs/phase4/` for future work.

---

## History

Pre-v0.3.0 development is captured in phase guide sign-off tables under `docs/phase1/`–`docs/phase3/`.
