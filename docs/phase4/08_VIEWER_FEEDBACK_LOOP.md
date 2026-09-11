# 08 — Viewer feedback loop (Roku vote → share + breed bias)

## Boundary

Phase 4 synopsis — close the **end-user → furnace** feedback loop: during VoD playback the Roku channel shows a **transient overlay** near the end of each sheep MP4 that invites a remote **like / love / vote** without stopping playback. Captured votes on the furnace drive (a) **share promotion** of the corresponding `.flam3` into the Tailscale / Syncthing peer path, and (b) **weighted bias** in daily idle pedigree breeding so well-liked sheep are more likely parents. Complements the existing **~10-day archive-seed** and **daily idle-breed** crons with **one additional cron** that detects shareable (voted) sheep, and enhances the daily breed job with viewer weights.

**Status:** Overlay + sidecar vote sink **shipped** 2026-09-11 (Wave 2). Share cron and idle-breed weights stay parked (Wave 3). Household guide [05](05_END_USER_GUIDE.md) has a short button map; full vote recipes wait on Wave 3.

Depends on Phase 1–2 Roku VoD playback ([../phase1/08_ROKU_BRIGHTSCRIPT.md](../phase1/08_ROKU_BRIGHTSCRIPT.md), [../phase2/04_ROKU_CHANNEL_POLISH.md](../phase2/04_ROKU_CHANNEL_POLISH.md)), pedigree idle breed ([../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md)), and Syncthing-over-Tailscale peering ([../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md)). Interacts with [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) (how votes trigger share-out / promote) and [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) (overlay UX polish for published builds). Does **not** replace archive seed or idle-breed — it **biases and extends** flock evolution with household interest.

## Intent

| Surface | Role |
|---|---|
| **Roku VoD overlay** | Near end-of-clip (e.g. last N seconds), show non-blocking prompt: like / love / vote via remote; playback continues; dismiss on timeout or key |
| **Vote ingest** | Channel POSTs (or queues) vote events to the furnace — identity = catalog sheep / genome stem, strength = like vs love (optional tiers), device / screen optional |
| **Unlimited re-vote** | Same end-user may vote the **same sheep again** without cooldown or unique-vote restriction; each event counts (or accumulates) for furnace weight |
| **Share path** | Votes mark sheep as **share candidates**; a dedicated cron promotes corresponding `.flam3` for fleet sharing (Tailscale + Syncthing Opt In path) |
| **Breed bias** | Daily `cron_breed_idle.sh` / `pipeline.breed_idle` picks parents with **weight ∝ viewer interest** instead of pure uniform random over the parent pool |
| **Flock evolution** | Archive fill + idle breed stay the mechanical cadence; viewer feedback steers **what** is shared and **who** becomes pedigree parents |

```text
  Roku VoD (PlayerScreen)
       │  transient overlay → remote like/love/vote (playback continues)
       ▼
  {stem}.jellyflam3.json  ← sole metadata SoT for this catalog MP4
       ├─► cron_share_votes (new) → share-out / peer publish of liked .flam3
       └─► cron_breed_idle (enhanced) → weighted parent selection
```

## Locked product rules (design)

1. **Overlay must not stop or pause** the Video node — prompt is decorative / input-only; seek/loop behavior unchanged.
2. **Any remote key that maps to vote** records feedback; other keys may dismiss the overlay without voting (Back) or leave playback controls as today.
3. **Re-votes are unrestricted** — no “one vote per sheep per device” gate in MVP; each event increments sidecar tallies.
4. **Screensaver package is out of scope** for this guide — votes happen in the **VoD channel** during MP4/HLS playback, not in `roku-screensaver/` (image-only, no interactive chrome while saving).
5. **Idle-gate** — vote HTTP must stay light (no Sessions Playing as a second client); prefer a small host-service / sink like display-profile upsert, not a fake playback session.
6. **License / commercial-safe** — share cron and breed bias still respect NC / commercial filters; a loved NC sheep does not bypass Opt Out or commercial Mode policy.
7. **Sidecar is the sole metadata SoT** for a catalog sheep — `{stem}.jellyflam3.json` beside the MP4. License, tags, duration/signals, poster/stills index, pedigree hints, **and viewer vote tallies** live there. **No parallel vote store** under `/var/lib/jellyflam3/` (no `sheep_vote_weights.json` as competing truth). Jellyfin Items Tags / Overview are derived caches only. Binary artifacts stay themselves: `.mp4` (video), `.flam3` (genome), poster/stills **files** (sidecar indexes them). Optional append-only log is debug-only and must not be read for share/breed decisions.
8. **VoD shuffle already includes pedigree and tuple** (channel 1.0.28+; skips `misc`/`test`). Roku screensaver ignores `shuffleFlock` and always rotates stills (no tuples). Vote overlay (when built) uses the VoD shuffle pool, not the screensaver.

## Sidecar + sink (shipped Wave 2)

Key **`viewer_feedback`** (likes / loves / votes / last_voted_at / share_candidate) is reserved in [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema). Guide [01](01_PEER_SHARE_PATH.md) reads `share_candidate` when share-out is built. Overlay and vote sink write that block on `{stem}.jellyflam3.json` only. Share cron and breed-weight hooks stay parked. Load–mutate–write readers keep unknown JSON; worker ingest copies this block across re-encode (tuples still rewrite `type` / watermark from this encode). Any vote sets `share_candidate: true`; gated `promote --apply` is unchanged.

### Remote map (VoD 1.0.32)

Overlay is visual-only (Video stays focused; playback does not pause). Shown when remaining duration ≤ 12 s.

| Key | Action |
|---|---|
| **OK** | like (`likes++`, `votes++`) |
| **Fast-forward** | love (`loves++`, `votes++`) |
| **Replay** | plain vote (`votes++` only) |
| **Back** (overlay visible) | dismiss overlay; do not exit playback |
| **Up** | exit playback (same trapdoor as before the overlay) |
| **\*** / Options / Info | Settings on Home (not consumed during overlay) |

`POST /v1/sheep-votes` on `jellyflam3-display-sink` (:8791, header `X-JellyFlam3-Token`). CLI: `python3 -m pipeline.sheep_votes apply --stem … --kind like\|love\|vote`. Restart **display-sink** (not the worker) to load the route.

## Work items (when Phase 4 opens)

### A — Roku VoD overlay (shipped 1.0.32)

1. **Timing** — overlay when remaining duration ≤ 12 s; hide on timeout (10 s), vote, Back, or clip advance.
2. **UI** — transient SceneGraph group over Video (bottom banner); copy for like / love / vote; no Button focus (Video stays focused).
3. **Mapping** — see Remote map above; shuffle / streamMode / Options keys are not stolen during playback.
4. **Identity** — stem from `mediaPath` basename (fallback `electricsheep.{generation}.{sheepId}`); Jellyfin item id + optional DeviceId on the event.
5. **Multi-Roku** — per-device DeviceId optional; household votes aggregate on the furnace sidecar.
6. **Shuffle pool (shipped 1.0.28)** — VoD `shuffleFlock` already includes **`pedigree`** and **`tuple`**.

### B — Furnace vote capture (shipped)

1. **API / sink** — `POST /v1/sheep-votes` on the existing display-profile sink (`pipeline.display_profile_sink`, port 8791); same `DISPLAY_SINK_TOKEN` / `X-JellyFlam3-Token`.
2. **Store** — atomic rewrite of that sheep’s `{stem}.jellyflam3.json` `viewer_feedback` (`pipeline.sheep_votes`). No `/var/lib` vote JSON.
3. **Unlimited re-vote** — each event increments sidecar counts.
4. **Resolve genome** — stem via catalog sidecar scan; else mediaPath basename under `paths.media_library`; 404 if no sidecar (never invent JSON).

### C — Share cron (new)

1. **`scripts/cron_share_votes.sh`** (name TBD) — periodic job (e.g. daily or several times per week, staggered from archive DOM) that:
   - Selects sheep meeting share threshold (count / love-tier / min votes).
   - Stages corresponding `.flam3` for **peering publish / share-out** (Tailscale + Syncthing Opt In).
   - Honors share-security (Phase 3 [05](../phase3/05_SHARED_SHEEP_SECURITY.md)) and Opt In state.
2. **Gate** — whether auto-publish is allowed vs “mark for operator promote” remains coupled to [01](01_PEER_SHARE_PATH.md); this guide assumes **automation is the goal**, with a config kill-switch.
3. **Log** — `/var/log/jellyflam3/share_votes.log`; flock-safe lock like other cron wrappers.

### D — Idle-breed weight bias (enhance daily cron)

1. Extend `pipeline.breed_idle` (and/or `pipeline.breed`) so parent pool selection uses **weights from each catalog sidecar** `viewer_feedback` when present; fall back to uniform when the block is missing or zero.
2. Config under `breed.idle_breed` (e.g. `vote_bias_enabled`, `vote_weight_power`, `min_votes_for_bias`).
3. Keep existing gates: empty inbox, idle gate, not imminent archive cron, dedup fingerprints.
4. Document that archive-seed cron stays **unbiased** feedstock fill; viewer bias applies to **pedigree idle breed** (and optionally manual breed CLI later).

### E — Ops & docs

1. Crontab example alongside archive + idle-breed; PATH / flock patterns match `cron_breed_idle.sh`.
2. End-user guide snippet ([05](05_END_USER_GUIDE.md)): “how to vote,” privacy (LAN-only), what love does.
3. Glossary + SoT cross-links; idle-gate ignore pattern if the vote client string appears in Sessions.

## Non-goals

- Stopping, pausing, or seeking playback as part of the vote UX
- Requiring unique votes / anti-ballot stuffing in MVP (household re-vote is a feature)
- Voting inside the Roku or Kodi **screensaver** packages
- Replacing archive-seed or removing uniform random entirely
- Public internet vote API or Electric Sheep P2P ratings network
- Auto-render of new sheep solely because of a vote (votes bias **selection** and **share**, not furnace kick without inbox)
- A second metadata store for votes (Jellyfin tags, central JSON under `/var/lib`, or genome XML) as source of truth

## Artifacts (when built)

| Artifact | Kind | Role |
|---|---|---|
| VoD overlay + key handler | `roku-channel/` | Transient like/love/vote UI |
| Vote ingest endpoint / sink | host service | Capture events from Roku(s) |
| `{stem}.jellyflam3.json` `viewer_feedback` | sidecar | Sole metadata SoT for vote tallies / share_candidate |
| `scripts/cron_share_votes.sh` | cron | Scan sidecars → peer share-out |
| Weighted `breed_idle` | pipeline | Viewer-biased parent picks |
| Config + docs | yaml / guides | Thresholds, button map, Opt In interaction |

## Exit criteria (when Phase 4 opens)

- [x] Vote-mode / feedback shuffle includes **pedigree** catalog sheep (not archive-gen allowlist only); misc/test still excluded
- [x] Overlay appears before end of sheep playback without stopping Video
- [x] Remote vote records on that sheep’s catalog sidecar; same sheep can be re-voted freely
- [ ] Share cron and idle breed read **only** sidecar `viewer_feedback` (no competing store) — sink writes sidecar only; cron/weights parked
- [ ] Share cron publishes or stages liked `.flam3` for Tailscale/Syncthing path (Opt In + share-security honored)
- [ ] Daily idle breed uses vote weights when available; uniform fallback when not
- [x] Docs: button map, privacy / LAN scope; linked from Phase 4 overview + end-user guide (cron examples wait on Wave 3)
- [x] Idle-gate / Sessions behavior: vote POST is display-sink, not a Playing client

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) · [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) · [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) · [../phase1/07_LICENSE_AND_METADATA.md](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md) · [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md)
