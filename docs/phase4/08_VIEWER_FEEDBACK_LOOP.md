# 08 — Viewer feedback loop (Roku vote → share + breed bias)

## Boundary

Phase 4 synopsis — close the **end-user → furnace** feedback loop: during VoD playback the Roku channel shows a **transient overlay** near the end of each sheep MP4 that invites a remote **like / love / vote** without stopping playback. Captured votes on the furnace drive (a) **share promotion** of the corresponding `.flam3` into the Tailscale / Syncthing peer path, and (b) **weighted bias** in daily idle pedigree breeding so well-liked sheep are more likely parents. Complements the existing **~10-day archive-seed** and **daily idle-breed** crons with **one additional cron** that detects shareable (voted) sheep, and enhances the daily breed job with viewer weights.

**Status:** Parked. Do not implement until Phase 4 opens.

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

## Work items (when Phase 4 opens)

### A — Roku VoD overlay

1. **Timing** — show overlay when remaining duration ≤ configurable threshold (e.g. 8–15 s before end / before seek-reloop); hide on timeout, vote, or Back.
2. **UI** — transient SceneGraph group over Video (dim banner or corner chip); copy for like / love / vote; focusable remote affordances without taking exclusive focus away from Back/exit.
3. **Mapping** — document which remote buttons mean like vs love vs cancel (e.g. `options` / colored keys / OK on focused button); keep shuffle / streamMode keys from colliding.
4. **Identity** — include Jellyfin item id + catalog stem / generation tags so furnace can resolve `.flam3` and MP4 sidecar.
5. **Multi-Roku** — per-device DeviceId optional on the event; household votes aggregate on the furnace (see [04](04_ROKU_PUBLISH.md)).

### B — Furnace vote capture

1. **API / sink** — e.g. `POST /v1/sheep-votes` on an existing or new LAN service (pattern after display-profile sink); auth via shared secret or Jellyfin API key policy TBD.
2. **Store** — atomic rewrite of that sheep’s `{stem}.jellyflam3.json` `viewer_feedback` block (likes / loves / votes / last_voted_at / share_candidate). That sidecar is the **only** place share cron and idle-breed read weights.
3. **Unlimited re-vote** — each event increments sidecar counts; optional decay / window for breed weights vs raw share threshold (still computed from sidecar).
4. **Resolve genome** — map voted catalog item → sidecar stem → `.flam3` in `genomes/done` / pedigree for share and breed.

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

- [ ] Overlay appears before end of sheep playback without stopping Video
- [ ] Remote vote records on that sheep’s catalog sidecar; same sheep can be re-voted freely
- [ ] Share cron and idle breed read **only** sidecar `viewer_feedback` (no competing store)
- [ ] Share cron publishes or stages liked `.flam3` for Tailscale/Syncthing path (Opt In + share-security honored)
- [ ] Daily idle breed uses vote weights when available; uniform fallback when not
- [ ] Docs: button map, cron examples, privacy / LAN scope; linked from Phase 4 overview + end-user guide
- [ ] Idle-gate / Sessions behavior verified (vote traffic does not close the furnace)

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [01_PEER_SHARE_PATH.md](01_PEER_SHARE_PATH.md) · [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) · [05_END_USER_GUIDE.md](05_END_USER_GUIDE.md) · [../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md) · [../phase3/05_SHARED_SHEEP_SECURITY.md](../phase3/05_SHARED_SHEEP_SECURITY.md)
