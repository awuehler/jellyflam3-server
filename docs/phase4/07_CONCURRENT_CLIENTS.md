# 07 — Concurrent clients and link-capacity estimate

## Boundary

Phase 4 synopsis — **how many endpoint devices** (Roku, Kodi, VLC, etc.) a single JellyFlam3-server can serve **at once** over the **local** link without saturating it: estimate (calculation) from measured/assumed **per-session Jellyfin bandwidth** and **usable WiFi or Ethernet capacity**, with headroom so clients do not spin-wait, buffer, or glitch.

**Status:** Parked. Do not implement until Phase 4 opens.

Most important when the Pi’s path to TVs is **WiFi** (airtime, uplink of a WiFi-connected RPi, or a busy household AP). Gigabit Ethernet is usually not the first bottleneck; document it anyway so operators can compare.

Complements [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) § E (multi-Roku **product** story). This guide is **network capacity**, not Channel Store / display-profiles.

Depends on Phase 2 Direct Play vs HLS ([../phase2/03_HLS_CLIENT_STREAMING.md](../phase2/03_HLS_CLIENT_STREAMING.md)): transcode inflates Pi CPU **and** often the bit-rate vs ambient MP4 Direct Play.

## Intent

| Need | Why |
|---|---|
| **Concurrent clients** | Households run several Rokus / Kodi / phones against **one** Jellyfin + furnace |
| **Capacity estimate** | Operators need a number (or a small calculator): *N* endpoints given this LAN, not “try until it stutters” |
| **WiFi-first** | WiFi-attached Raspberry Pi (or congested AP) saturates earlier than Ethernet; glitches show up as buffering / spin-wait, not only “slow” |

## Work items (when Phase 4 opens)

### A — Per-session demand

1. Measure typical **Direct Play** catalog loop bit-rate (1080p H.264 ambient masters) — lab `ffprobe` / Jellyfin playback stats, not a guess locked in yaml.
2. Measure **HLS / transcode** session bit-rate when Direct Play is not used (worse case for both CPU and airtime).
3. Screensaver vs VoD: image SS is cheap; **Kodi video SS** and VoD **Playing** are full video sessions (idle-gate already treats Playing as furnace-off).
4. Document audio-on vs mute if it changes mux size (usually small vs video).

### B — Usable link capacity

1. Identify the bottleneck hop: Pi Ethernet, Pi **WiFi STA**, household AP backhaul, or client WiFi.
2. Measure **usable** throughput (iperf3 or similar) on that hop — not marketing PHY rate. Apply a **headroom** factor (e.g. leave 20–40% unused) so bursts and WiFi retries do not stall players.
3. Call out **WiFi-connected Pi as Jellyfin server**: uplink contention + CPU; prefer Ethernet for the furnace Pi when N > 1–2 video sessions.

### C — Estimate

1. Ship a documented formula and a small CLI (e.g. `python3 -m pipeline.link_capacity` or a script) roughly:

   `N_max ≈ floor( (usable_link_bps × (1 − headroom)) / bps_per_active_session )`

   with inputs: link kind (wifi/eth), measured or profiled usable bps, session mode (Direct Play vs transcode), headroom.
2. Print **integer N** plus assumptions (codec, resolution, headroom %). Warn when N < 1.
3. Optional profiles: `wifi-pi`, `wifi-ap-gigabit-backhaul`, `eth-gigabit`.
4. Do **not** treat N as a hard Jellyfin connection cap unless Owner later wants an enforce hook; Phase 4 DoD is **estimate + docs + lab check**.

### D — Lab check

1. On a WiFi-served Pi (or WiFi clients), raise concurrent Direct Play sessions toward N_max and record: stall events, buffer waits, idle-gate, Pi CPU.
2. Repeat on Ethernet as the control.
3. Capture results in this guide or the end-user triage ([05](05_END_USER_GUIDE.md)).

## Guidelines

1. Prefer **Direct Play MP4** for ambient TV; transcode both heats the Pi and burns more of the link.
2. Screensaver image clients are out of the video-N count; **Kodi ES screensaver** is in the video-N count when it plays loops.
3. Idle-gate still pauses the **furnace** while any matching TV is Playing — concurrency here is **playback**, not simultaneous render + play.
4. Estimates are **LAN**. Tailscale / WAN is a different (usually worse) budget; mention but do not DoD on it.

## Non-goals

- Rewriting Jellyfin streaming core or adding a custom CDN
- Per-TV 4K encode retarget
- Guaranteeing glitch-free WiFi on a saturated 2.4 GHz AP
- Merging this into Roku Store listing copy ([04](04_ROKU_PUBLISH.md))

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| Bit-rate + usable-link measurement notes | docs / lab | Inputs to N_max |
| Calculator CLI or script | pipeline / scripts | `N_max` from link + session bps + headroom |
| Operator copy (README / end-user) | docs | Ethernet vs WiFi; Direct Play vs transcode |
| Lab concurrency log | docs | WiFi vs Ethernet smoke |

## Exit criteria (when Phase 4 opens)

- [ ] Documented formula + measured (or profiled) per-session bps for Direct Play ambient loops
- [ ] Calculator outputs integer N_max with explicit headroom and link kind
- [ ] Lab note: WiFi vs Ethernet concurrent playback vs estimated N (stalls / no stalls)
- [ ] Operator docs warn that a WiFi-uplinked Pi is the tight case
- [ ] Owner OK

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | _TBD_ | [ ] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) · [../phase2/03_HLS_CLIENT_STREAMING.md](../phase2/03_HLS_CLIENT_STREAMING.md) · [../phase1/06_IDLE_GATE.md](../phase1/06_IDLE_GATE.md) · [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md)
