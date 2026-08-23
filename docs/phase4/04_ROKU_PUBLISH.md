# 04 — Publish Roku VoD + Screensaver (Channel Store / private)

## Boundary

Phase 4 synopsis — take the **existing** JellyFlam3 Roku packages from lab sideload to **publishable** distribution: VoD player (`roku-channel/`) and standalone screensaver (`roku-screensaver/`). Includes Store/private-channel packaging, brand assets, settings UX / input polish, Roku publishing best-practices, and **multi-Roku households on a single JellyFlam3-server**.

**Status:** Parked. Do not implement until Phase 4 opens.

Depends on Phase 2 VoD polish ([../phase2/04_ROKU_CHANNEL_POLISH.md](../phase2/04_ROKU_CHANNEL_POLISH.md)) and Phase 3 screensaver MVP ([../phase3/01_SCREENSAVERS_AND_STILLS.md](../phase3/01_SCREENSAVERS_AND_STILLS.md)). Does **not** replace those guides; this is the publish + productization + multi-TV track.

## Intent

| Package / capability | Today (lab) | Phase 4 target |
|---|---|---|
| **VoD player** | `dist/jellyflam3-roku.zip` sideload; one developer slot | Signed / private or Channel Store channel; coexistence with screensaver |
| **Screensaver** | `dist/jellyflam3-screensaver.zip` sideload; Theme → Screensavers | Standalone screensaver listing; same publish path family; shared registry contract preserved |
| **Multi-Roku household** | Phase 2 per-screen `display_profiles/` sink (hints); ad-hoc multi-device lab | First-class: **N Roku TVs / sticks** against **one** JellyFlam3-server (one Jellyfin + one furnace) |

Lab constraint (one sideload at a time **per device**) is **not** a product bug — publishing (private channel and/or Store) is how VoD + screensaver stay installed together, and how every living-room Roku gets the same apps without juggling developer zips.

## Work items (when Phase 4 opens)

### A — Brand & storefront assets

1. **Icons / logos** — replace placeholder `mm_icon_focus_*`, splash, and any Store poster / screenshot set for **both** packages (distinct VoD vs Dreams screensaver identity).
2. Manifest **title** / **screensaver_title** / subtitle copy pass; version scheme aligned with Store builds (not only sideload `1.0.x` bumps).
3. Optional FHD/SD asset matrix per [Roku channel packaging](https://developer.roku.com/docs/developer-program/getting-started/developer-setup.md) / Store checklist.

### B — Settings layout & user input

1. **VoD Settings** — clearer layout (sections, focus rings, safe margins); keyboard / paste-friendly Jellyfin URL + API key + user/library IDs; validation and error copy; keep display probe + Pi sink behavior from Phase 2.
2. **Screensaver Settings** — first-class editors for Jellyfin credentials **and** `ssFade` / `ssDwellSec` / `ssFadeSec` (not status-only); Back / focus already required; match VoD visual language where sensible. **Today (Phase 3):** SS **depends on** a current or previously installed VoD channel on **that** Roku to populate `JellyFlam3`; SS Settings cannot create credentials.
3. Shared `JellyFlam3` registry contract documented as the single secrets surface; no second ad-hoc store for Store builds.
4. Optional **friendly screen name** (e.g. `Living Room`) stored in registry + echoed into display-profile JSON for operator lists.

### C — Roku / SceneGraph best-practices

1. Focus, Back stack, empty/loading/error states, deep link regression (VoD); screensaver remains **image-only** (no `Video`, no Sessions/Playing).
2. Client / DeviceName strings stable for idle-gate (`JellyFlam3` VoD vs `JellyFlam3-Screensaver`); DeviceId / screen identity unique **per physical Roku**.
3. Debug ports: VoD **8085**, screensaver context **8087**; package scripts keep POSIX zip paths.
4. Do **not** embed `RunScreenSaver` / `screensaver_title` inside the VoD streaming app (Roku policy — packages stay separate).

### D — Publish path

1. Developer account, package signing / rekey, **private channel** (lab households) and/or **Channel Store** submission for VoD and screensaver as appropriate.
2. Store listing: descriptions, screenshots, categories, age rating, privacy / network disclosure (Jellyfin LAN URL + API key).
3. Coexistence runbook: private VoD + sideload SS (or both private) so Theme screensavers and Home VoD tile both remain available.
4. Update operator docs (`roku-channel/README.md`, `roku-screensaver/README.md`, packaging scripts) for signed builds vs sideload zips.
5. Household install: same published channel/screensaver on **every** Roku (no per-TV sideload chore once private/Store is live).

### E — Multi-Roku from a single JellyFlam3-server

Extend Phase 2’s per-screen display-profile sink into a durable **one server → many TVs** product story.

| Concern | Approach |
|---|---|
| **Topology** | One Pi (or fleet tip) runs Jellyfin + idle-gate + furnace; many Rokus on the LAN (or Tailscale) point at the same `baseUrl` / library |
| **Identity** | Stable per-device id (Roku client/device id) → one `display_profiles/{client}-{deviceId}.json` per screen ([Phase 2 / 04](../phase2/04_ROKU_CHANNEL_POLISH.md) piece F); optional human label |
| **VoD concurrency** | Multiple Rokus may play at once; idle-gate already closes on any matching TV Playing/transcode — confirm behavior is intentional for households (furnace pauses while *any* TV watches). **How many** sessions the LAN/WiFi can carry without stalls: [07](07_CONCURRENT_CLIENTS.md) |
| **Screensaver concurrency** | Image-only SS on several TVs must **not** close the gate; Client=`JellyFlam3-Screensaver` + ignore patterns remain required |
| **Per-screen prefs** | Registry is already per-device; document / polish which keys are per-TV (streamMode, shuffle, ssFade/dwell, commercialMode) vs shared secrets |
| **Ops** | `python3 -m pipeline.display_profiles list` (+ optional status UI later) shows all known screens; sink `:8791` remains multi-upsert safe |
| **Discovery** | Settings copy + README: enter **this** household’s Jellyfin URL once per Roku; same API key/user/library is normal |
| **Deep link / ECP** | Optional: document launching a sheep on a **named** Roku (`ROKU_IP`) for ops; not required for Store MVP |

Baseline already shipped: two live Roku profiles on one Pi (Phase 2 Owner OK). Phase 4 makes the household path explicit, documented, and publish-friendly — not a second server per TV.

## Guidelines

1. Screensaver stays a **separate** package from VoD — never merge for Store convenience.
2. Prefer private-channel publish first for fleet lab; Store certification is optional until Owner chooses public distribution.
3. Reuse Phase 2/3 behavior (MP4 ambient, stills Primaries, crossfade options); this guide is polish + distribution + multi-TV ops, not a rewrite of playback.
4. Watermarked stills/masters (if required for public Store art) follow [03_EDGES_AND_WATERMARK.md](03_EDGES_AND_WATERMARK.md).
5. **One JellyFlam3-server serves many Rokus** — do not require a Pi per TV; scale is client count + Jellyfin sessions, not one furnace each.

## Non-goals

- Reworking Jellyfin server core (beyond documenting multi-session / idle-gate household semantics)
- Kodi screensaver publish ([../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)) — multi-Kodi may reuse display_profiles but is out of this guide’s Roku publish exit
- Merging VoD + screensaver into one sideload zip to dodge the one-dev-slot limit
- Per-TV encode retarget / 4K auto-furnace (display profiles remain **hints** unless a later Owner decision)
- DeepDream / social flock (separate aspirational tracks)

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| Updated `roku-channel/` + `roku-screensaver/` assets | brand | Icons, splash, Store posters |
| Settings UX (VoD + SS) | channel | Layout, keyboard input, validation; optional screen name |
| Signed `.pkg` / private-channel builds | release | Coexistence beyond single sideload; same apps on every household Roku |
| Store / private listing copy | docs | Descriptions, screenshots, privacy |
| Operator publish + multi-TV runbook | docs | Rekey, upload, version, rollback; N Rokus → one server |
| `display_profiles/` + sink `:8791` | ops | Per-screen identity (extend Phase 2; friendly labels) |

## Exit criteria (when Phase 4 opens)

- [ ] VoD and screensaver brand assets replaced (icons/logos/splash at minimum)
- [ ] VoD Settings: improved layout + reliable text input for Jellyfin fields
- [ ] Screensaver Settings: credential + fade/dwell/fade-duration editors; Back exits
- [ ] Both packages build via existing (or extended) package scripts; signed/private path documented
- [ ] At least one publish path exercised (private channel **or** Store) for each package, or Owner waiver for Store
- [ ] Idle-gate still open under published screensaver; VoD still reports Playing as today
- [ ] **Multi-Roku:** ≥2 physical Rokus against one JellyFlam3-server — each has its own display profile; concurrent SS does not close gate; concurrent VoD closes gate as designed; operator can list screens
- [ ] Owner OK

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | _TBD_ | [ ] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [08_VIEWER_FEEDBACK_LOOP.md](08_VIEWER_FEEDBACK_LOOP.md) · [../phase2/04_ROKU_CHANNEL_POLISH.md](../phase2/04_ROKU_CHANNEL_POLISH.md) · [../phase3/01_SCREENSAVERS_AND_STILLS.md](../phase3/01_SCREENSAVERS_AND_STILLS.md) · [../phase1/06_IDLE_GATE.md](../phase1/06_IDLE_GATE.md) · [../phase1/08_ROKU_BRIGHTSCRIPT.md](../phase1/08_ROKU_BRIGHTSCRIPT.md) · [Roku Screensavers](https://developer.roku.com/docs/developer-program/media-playback/screensavers.md) · [Channel packaging](https://developer.roku.com/docs/developer-program/getting-started/developer-setup.md)
