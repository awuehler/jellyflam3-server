# Changelog

All notable changes to this project are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added

- Roku Channel Store listing drafts: [privacy policy](docs/roku-store/PRIVACY_POLICY.md), [terms of use](docs/roku-store/TERMS_OF_USE.md), [support contact](docs/roku-store/SUPPORT.md) ([dashboard URL map](docs/roku-store/README.md)).
- `JELLYFIN_STREAM_MODE` presets the Roku ambient stream mode at pack time (`mp4` default, `hls` opt-in) so a Store/cert zip can ship HLS without changing the household default. Measured over the Funnel relay, HLS segment 0 is **1.4 MB / 0.7 s** for a clip with regular keyframes and **21.8 MB / 12.6 s** for a keyframe-sparse catalog sheep.
- Roku VoD **1.0.51** App Behavior Analysis: `AppLaunchComplete` moves from `main.brs` (fired at bare `screen.Show()`) into `HomeScene`, where it marks an operable screen — the rendered flock, an actionable empty/error/unreachable screen, or deep-link playback. Roku times the beacon against the **first render pass after it is signaled**, so signaling an empty Scene measured nothing. A 5 s guard timer fires it even when the furnace never answers, and re-arms while a pre-home Settings dialog is open so dialog time stays excluded.
- Roku VoD **1.0.50** cert **5.1** deep-link playback: stream fallback is one-way toward Static MP4. Jellyfin cannot segment keyframe-sparse sheep loops, so HLS segment 0 carries the whole clip (~21 MB behind an `#EXTINF:6.0` label, ~17 s over a Funnel relay) — escalating `mp4 → hls` after an error guaranteed a `startup / open / stop` with no play inside cert **3.6**'s 8 s budget. `hls → mp4` recovery is unchanged.
- Roku VoD **1.0.49** Store packaging: omit `splash_screen_sd` and `mm_icon_focus_sd` so analysis does not require 720×480 / 246×140 crops of the HD splash and icon. Keep `splash_screen_hd` (1280×720) and `mm_icon_focus_hd` (290×218) with `ui_resolutions=fhd`.
- Roku VoD **1.0.48** cert **5.2** deep link: keep `m.input` (`roInput`) alive; handle `roInputEvent` with Roku's sample `DoesExist("mediatype")` / `DoesExist("contentid")` plus `mediaType`/`contentId` on cold launch. Missing or empty ids still land on home (no crash).
- Roku VoD **1.0.47** public-app compliance: `roInput` handling uses the documented casing (`SetMessagePort`, `IsInput`, `GetInfo`) so Store static analysis recognizes it; `AppDialogInitiate` / `AppDialogComplete` now bracket **any** Settings dialog opened before the flock first renders, not only the empty-credential first run. **Static analysis reads the uploaded package** — re-package the `.pkg` on a Roku after sideloading this build before re-submitting.
- Roku VoD **1.0.46** public-app compliance: keep `supports_input_launch=1` and `roInputEvent`; fire `AppDialogInitiate` / `AppDialogComplete` around first-run credential Settings; replace `KeyboardDialog` with `StandardKeyboardDialog` (voice-safe).
- Roku VoD **1.0.45** public-app compliance: keep `supports_input_launch=1` and live `roInputEvent` handling; set `rsg_version=1.3`; drop deprecated manifest `subtitle`; subscribe `roAppMemoryMonitor` (`EnableMemoryWarningEvent`, `GetMemoryLimitPercent`, `GetChannelMemoryLimit`, `GetChannelAvailableMemory`) with `roDeviceInfo.EnableLowGeneralMemoryEvent` fallback.
- Roku VoD **1.0.44** public-app compliance: retain `supports_input_launch=1` plus live `roInputEvent` deep-link handling; emit the `AppLaunchComplete` beacon after the Scene is shown; exclude every numbered source-art PNG from packages so the public zip stays below Roku's **4 MB** limit.
- Operator flock vote leaderboard: `python3 -m pipeline.sheep_votes top` (default 10) / `top -n 5` ranks live-catalog sidecar `votes` (then loves, likes). Zeros omitted unless `--min-votes 0`. Unpublished trees are skipped.
- Phase 5 / 05 Kodi screensaver votes: **0.2.13** last-**7 s** like/love overlay (Enter love, Right like, Down dismiss, Up/Back exit) posts `POST /v1/sheep-votes` like Roku VoD **1.0.38**. Tuples skip. **Roku screensaver voting stays cancelled.** [docs/phase5/05_KODI_SCREENSAVER_VOTES.md](docs/phase5/05_KODI_SCREENSAVER_VOTES.md).
- Phase 4 / 09 screensaver captions: Kodi **0.2.12** Settings `title_mode` (filename default / alias) with a chrome-light overlay and ListItem title; Roku screensaver **1.0.11** Settings `titleMode` OK-toggle and stills caption. Both read Overview `Alias:` like VoD. Optional Jellyfin OriginalTitle / SortName-as-alias stays parked.
- Roku VoD **1.0.43**: waiting UI when Jellyfin is unreachable (not empty flock); 30s auto-retry; Capabilities POST no longer blocks the Items GET; mid-play host-down probes `/System/Info/Public` instead of draining the in-memory list.
- Kodi screensaver **0.2.11**: distinct hints for missing settings vs furnace down vs empty flock; reconnect every 30s while waiting; do not treat a dead Pi as quarantined sheep.
- Opt-In watchdog LAN heal: associated STA uses `nmcli connect` only (no disconnect); always tries connect if disconnect fails; brcmfmac reload on firmware wedge (`SCAN-FAILED -110` / no default route); opt-in `worker_drain request` + reboot after `lan_heal_reboot_after_sec`. USB Ethernet is documented insurance (`peering.watchdog.*`).
- Operator runbook: `worker_drain request` returns as soon as the flag is set (`phase=draining` while a job is in flight); `request --wait` keeps polling until `phase=idle`. `INFO waiting for drain idle (N in-flight job(s))` is expected; leftover inbox files do not keep the wait looping.
- Roku VoD **1.0.42**: Settings OK-toggle for `commercialMode`, `streamMode`, `shuffleFlock`, and `titleMode` (no keyboard); text fields still use the keyboard. Player chrome labels (loading-next and vote) use the same **55%** alpha as the bar (`0xE8E8F08C`).
- Roku VoD **1.0.41**: loading-next and vote banners share one 55% bar at `[80,920]` with the same SmallSystemFont line so they swap in place. Vote left side is filename/alias only (no “Like this sheep:”); the name is clipped so it cannot overlap the key hints.
- Roku VoD **1.0.40**: vote overlay is a single 55% banner in the last **7 s**; filename/alias left, **OK love · RIGHT like · DOWN dismiss · UP/BACK exit** right.
- Roku VoD **1.0.39**: `titleMode` is now an OK-toggle (`filename` ↔ `alias`) that writes and flushes the registry immediately; **Save & Reload** replaces ambiguous **Done** and refreshes the home flock using the effective mode.
- Roku VoD **1.0.38**: vote overlay is two-tier **love / like** only (**OK** love, **Right** like, **Down** dismiss, **Up/Back** exit). Matches a keyboard (Enter / Right / Down / Up-Esc) for a later Kodi overlay. Plain `vote` is no longer posted by the channel; furnace CLI/API still accepts it.
- Roku VoD **1.0.37**: accepted Settings edits persist immediately (Back no longer discards them); registry reads are normalized; home status shows commercial-filter and alias/fallback counts; NC always overrides safe tags and applies to deep links. Player focus stays above the Video node so **FF love** and **REPLAY vote** reach the overlay alongside existing OK/BACK handling.
- Roku VoD **1.0.36**: home copy is **Ambient Dreams** and **N sheep in flock**; poster grid is **six** columns (270×152 tiles so the last column stays inside the right gutter). Pedigree genomes keep the full `cc-*` license on the tile; pedigree tags move to the wider detail chip.
- Kodi screensaver **0.2.10** silently closes Kodi's native playback-failed `okdialog` while dropping and refreshing a quarantined sheep, preventing a recovered session from retaining a modal end-user prompt.
- Active worker quality intervention: reject linear-only, cloned-singularity, frozen single-flame, and washed-palette genomes before full animation; render a one-frame saturation preview before expensive CPU work; re-check the encoded midpoint before catalog/Jellyfin publication. Rejections persist reasons/metrics in job state and move the claimed genome to quarantine. `genome_orbit_frozen` is now a hard-quarantine reason (score **80**); legacy still-loop requires an explicit gate opt-out.
- Operator idle-gate note: CLI `idle-gate closed; waiting 15s…` is the retry cap; `idle_delay_sec` default **600** holds after VoD (including Home). Runbook [Idle gate behavior](docs/USER_GUIDE_AND_RUNBOOK.md#idle-gate-behavior).
- Roku VoD **1.0.35** vote overlay: skip tuples (no banner / no POST); banner fill **65%** opacity (`0x0A0A12A6`); prompt is **Like this sheep:** plus Settings `titleMode` (alias or filename); remote hints use **OK / FF / REPLAY / BACK**. Flock focus ring no longer covers the **N dreams in flock** line. Settings rejects typos (`mp4`/`hls`, `true`/`false`, `filename`/`alias`, URL/GUID/key).
- Kodi screensaver add-on description aligned with shipped flock (tuples as one clip, wrap cap 313, no votes, idle-gate ignored).
- Roku VoD **1.0.34** flock polish: five-column rows wrap the catalog into a vertically scrollable poster grid; tile metadata omits truncated `human` / `brood` pedigree labels; home instructions are clearer; inter-clip buffering shows `{alias}(MP4)` when an alias is available.
- Phase 4 09 C: Roku VoD **1.0.33** Settings `titleMode` (`filename` default / `alias`) on flock rows and player chrome. Jellyfin `Name` stays the stem; Overview `Alias:` line from ingest and `python3 -m pipeline.sheep_naming` (`set-alias` / `backfill --push-jellyfin`). Missing alias falls back to filename. Kodi / screensaver captions parked.
- Pasture channel-art prompt pack (hero splash + square mark) for Roku/Kodi chrome: [CLIENT_CHANNEL_ART.md](docs/CLIENT_CHANNEL_ART.md). External generator + operator crop; not catalog posters and not Cesari marks.
- Phase 4 Wave 4 slices 1–2: sheep library **rotate** (`python3 -m pipeline.library_disk rotate [--apply]`; `scripts/cron_library_rotate.sh` **inactive until needed**; archive seed skips fetch if sheep still BAD) and worker refuse on sheep **BAD**. Mesh introduce **A/B/C**: `ensure-mesh-local` (from opt-in), gitignored `mesh-join --peers-file`, `introducer` on the 16a example row. Channel Store stays parked.
- Phase 4 Wave 3: lock gated `promote --apply` ([01](docs/phase4/01_PEER_SHARE_PATH.md)). `python3 -m pipeline.share_votes` + `scripts/cron_share_votes.sh` (lab **06:41**) copy liked catalog `.flam3` to `peers/share-out`. Idle-breed weights parents by sidecar `viewer_feedback.votes`. Household recipe in the runbook (example 6). Auto-promote later **cancelled** (gated promote is the product).

- Phase 4 Wave 2: Roku VoD **1.0.32** like/love/vote overlay (last 12 s, playback continues). `POST /v1/sheep-votes` on `jellyflam3-display-sink` (:8791) writes catalog sidecar `viewer_feedback` only and sets `share_candidate`. CLI `python3 -m pipeline.sheep_votes`. Screensaver voting later **cancelled** (Roku best practices).
- Phase 4 Wave 2: private-channel coexistence path ([phase4/04](docs/phase4/04_ROKU_PUBLISH.md#private-channel-path-wave-2)). Roku screensaver **1.0.10** Settings writes Jellyfin credentials so VoD (private channel) and SS (sideload slot) can both stay installed. Channel Store parked.
- Fleet log hygiene: persistent journald (class-sized) + 72h `jellyflam3-logrotate.timer`; compress file-log backups after 11 days; purge after 23 days (`scripts/enable_log_hygiene.sh`).
- Sheep refactor Pathway A: `catalog_desaturated` + `palette_washed_out` heuristics for grey/muddy catalog sheep.
- Initial frozen-orbit handling detected when `flam3-genome sequence=` could not 360°-orbit and avoided false duration snapping; active quality intervention above supersedes its still-loop publication behavior.
- Printable Layer 1 fridge card (`docs/FRIDGE_CARD.md`) — watch / gate / Settings / triage; no API keys.
- Phase 4 guide 05 baseline complete: four worked examples in the user guide (first evening, screensaver, two Rokus, peer receive); Owner OK 2026-09-03.
- Concurrent-client estimator (`python3 -m pipeline.link_capacity`): integer `N_max` from usable hop × headroom ÷ session bps; WiFi-STA lab note in guide 07. **Owner OK 2026-09-09**.
- Sheep-library disk check slice (`python3 -m pipeline.library_disk`): healthcheck WARN/BAD on mount used % / free GiB (rotate + worker refuse shipped later in Wave 4).
- Catalog sidecar schema: Phase 4 keys `type`, `watermark`, `viewer_feedback`, `alias` reserved in [phase1/07](docs/phase1/07_LICENSE_AND_METADATA.md); `pipeline.stills.SIDECAR_RESERVED_KEYS`. Tuple ingest writes `type` / `from_id` / `to_id` / `watermark`. Worker copies reserved keys on re-ingest so votes and aliases survive Shears-modify.
- Phase 4 tuples: one MP4 (loop A + watermarked edge A→B + loop B) under `by-generation/tuple/`; idle-cron mode; Roku shuffle includes `pedigree` and `tuple` (channel 1.0.28). Edge mark: Cesari PNG on private furnaces (`license.commercial_mode: false`); ES attribution sentence (no logo) when commercial_mode is on. Look/feel: [phase4/03](docs/phase4/03_EDGES_AND_WATERMARK.md#look-and-feel-what-the-viewer-sees).
- Phase 4 client polish: wrap-once flock re-fetch + 313 session cap — Roku VoD **1.0.31**, Roku screensaver **1.0.9**, Kodi screensaver **0.2.9**. After a full shuffle wrap (one random permutation of the in-memory list), clients re-fetch Jellyfin and rebuild the list. The new permutation is rotated so the first item is not the last-played id (no wrap-seam back-to-back). Skip if a fetch is already in flight; no 30s 404 gate. HTTP Limit is 5000; if more than 313 artifacts remain after filters, randomly prune to 313. Single-item lists do not wrap-refetch.
- Phase 4 client polish: mid-session 404 / quarantine re-poll — Roku VoD **1.0.29**, Roku screensaver **1.0.8**, Kodi screensaver **0.2.7**. Drop the dead Jellyfin id, re-poll Items (30s rate limit), continue the session. Does not invent a Playing session for the miss.
- Phase 4 sheep naming RNG: `python3 -m pipeline.sheep_naming` hash-seeds `adjective_surname` on ingest/backfill; `set-alias` / `clear-alias` sticky human override. VoD `titleMode` later shipped in **1.0.33**. LLM naming moved to Phase 5.
- Phase 5 / 04 peer share mesh leftovers (parked): share-out → other furnaces; promote vs sendreceive delete; `share_live` vs real connections. Furnace-only, not Ventuno. [docs/phase5/04_PEER_SHARE_MESH.md](docs/phase5/04_PEER_SHARE_MESH.md).
- Phase 5 synopsis (parked): two deployments — **A** JellyFlam3 Furnace (Pi 5) and **B** LLM Agent Platform (Arduino Ventuno Q). Homelab BOM + INT4 storage math; Llama 3.1 8B / Qwen2.5 7B / Mistral 7B (INT4); **one hot Instruct**; **pixels → text → Instruct JSON** with a small GPU VLM; **Jellyfin VoD as camera** for **single-sheep** loops ([phase5/02](docs/phase5/02_LLM_INTEGRATION.md#vod-as-camera)). **One B → 1..N furnaces**; Tailscale `tag:jellyflam3-agent` when the Pi fleet shares sheep ([phase5/01](docs/phase5/01_VENTUNO_Q_HOST.md#tailscale-flock-tailnet)). [docs/phase5/](docs/phase5/00_OVERVIEW.md).

### Changed

- Phase 4 / 02 mesh introduce **closed** (Owner OK 2026-09-19). A/B/C + `mesh-join` upsert stay shipped. Share-out never hits Syncthing; promote-move on sendreceive inbox can delete land copies — parked as [phase5/04](docs/phase5/04_PEER_SHARE_MESH.md).
- Phase 4 / 02 mesh-join: skip this host’s device ID; if a peer already exists, refresh name, Tailscale `tcp://…:22000`, and introducer (stale IPs no longer stay disconnected).
- Phase 4 / 09 screensaver captions: Kodi **0.2.12** `title_mode` (filename default / alias) plus a chrome-light overlay; Roku screensaver **1.0.11** Settings `titleMode` plus stills caption. Both read Overview `Alias:` (same as VoD). Optional Jellyfin OriginalTitle / SortName-as-alias stays parked.
- Phase 4 / 06 library rotate **closed** (Owner OK 2026-09-19). Check + Shears rotate + worker refuse stay shipped; daily `cron_library_rotate.sh` remains off the lab crontab until a host is WARN/BAD. How-to: [Activate daily rotate](docs/phase4/06_LIBRARY_DISK_ROTATE.md#activate-daily-rotate) and [USER_GUIDE](docs/USER_GUIDE_AND_RUNBOOK.md#activate-library-rotate). LRU / soak-fill stay non-goals.
- Cancel Phase 4 leftovers: **standalone edges** / loop-stills watermark / Kodi edge sequencer (tuples already include loop→edge→loop). **Roku screensaver voting** (best practices / certification — VoD overlay only; Kodi SS votes are [phase5/05](docs/phase5/05_KODI_SCREENSAVER_VOTES.md)). **`N_max` as a Jellyfin cap** and an **Ethernet control lab** (guide 07 — this fleet is WiFi STA, `eth0 DOWN`; estimate stays ops guidance). **Auto-promote** (guide 01 — gated `promote --apply` is the receive path; no silent `peers/inbox` drain). **Furnace polish that is not drain** (2026-09-19): checkpoint/resume inside `flam3-animate` and SIGSTOP-as-pause — the binary has no resume protocol; drain (finish current job, then stop claiming) stays the pause product.

### Fixed

- Phase 4 / 02 `mesh-join`: Syncthing `add-json` takes the JSON document as a **positional argument**. Stdin/heredoc was ignored (`expected 1 arugment, got 0`), so new devices never applied.
- Healthcheck drain probe: `--config` is a parent argparse flag (`python3 -m pipeline.worker_drain --config … status`), so drain-on now WARNs with phase instead of “status unavailable”. Ops test expects that argv order.
- Phase 4 pre-wave 3 idle-gate: supervisor-only status SoT; restore `idle_delay` across idlegate restart; stale `open` fail-closed (3× poll); `wait_for_gate` honors `seconds_until_resume` (cap 15 s); drain wait errors if the worker is frozen. Playing still does not pause `flam3-animate`.
- Docs: how/where/when to **generate** `DISPLAY_SINK_TOKEN` (`python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`) into this Pi’s `secrets.env` before enabling the sink; same string → Roku `displaySinkToken`.
- Docs: `DISPLAY_SINK_TOKEN` is **required** for `jellyflam3-display-sink` (unit binds `0.0.0.0:8791`). Missing token exits 2 and crash-loops; unique per furnace.
- Worker catalog perm repair skips chmod on files it does not own (Jellyfin `folder.jpg` / stills posters at `644`). Only owner or root can chmod; those are no longer startup `file_errors`.
- Idle-gate status JSON: atomic temp + `os.replace`; `is_gate_open` treats corrupt/unreadable files as **closed** so the worker does not crash on a torn write.
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
