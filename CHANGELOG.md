# Changelog

All notable changes to this project are documented here. Format loosely follows [Keep a Changelog](https://keepachangelog.com/).

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
