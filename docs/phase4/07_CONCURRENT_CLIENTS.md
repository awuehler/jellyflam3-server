# 07 — Concurrent clients and link-capacity estimate

## Boundary

How many endpoint devices (Roku, Kodi, VLC, etc.) a single JellyFlam3-server can serve **at once** over the **local** link without saturating it: estimate from measured per-session Jellyfin bandwidth and usable WiFi or Ethernet capacity, with headroom so clients do not spin-wait, buffer, or glitch.

**Status: complete** (estimator + lab note — Owner OK pending). `N_max` is an **estimate**, not a Jellyfin connection cap.

Most important when the Pi’s path to TVs is **WiFi** (airtime, uplink of a WiFi-connected RPi, or a busy household AP). Gigabit Ethernet is usually not the first bottleneck; the calculator still has an `eth-gigabit` profile so operators can compare.

Complements [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) § E (multi-Roku **product** story). This guide is **network capacity**, not Channel Store / display-profiles.

Depends on Phase 2 Direct Play vs HLS ([../phase2/03_HLS_CLIENT_STREAMING.md](../phase2/03_HLS_CLIENT_STREAMING.md)): transcode inflates Pi CPU **and** often the bit-rate vs ambient MP4 Direct Play.

## Intent

| Need | Why |
|---|---|
| **Concurrent clients** | Households run several Rokus / Kodi / phones against **one** Jellyfin + furnace |
| **Capacity estimate** | Operators need a number: *N* endpoints given this LAN, not “try until it stutters” |
| **WiFi-first** | WiFi-attached Raspberry Pi (or congested AP) saturates earlier than Ethernet; glitches show up as buffering / spin-wait, not only “slow” |

## Formula

```
N_max = floor( (usable_link_bps × (1 − headroom)) / bps_per_active_session )
```

| Input | Default | Source |
|---|---|---|
| `usable_link_bps` | Profile table below, or `--usable-mbps` after `bench-recv` | iperf-class TCP goodput, **not** PHY rate |
| `headroom` | **0.30** (20–40% band) | Leave unused so WiFi retries and bursts do not stall players |
| `bps_per_active_session` | Direct Play: `encode.video_bitrate` or `probe` p90; transcode: **8 Mbps** profiled | Lab ffprobe, not a second guess locked in yaml |

Prints **integer N** plus codec / resolution / headroom / link kind. Warns when `N_max < 1`.

## Work items

### A — Per-session demand

- [x] Direct Play catalog loop bit-rate — lab `ffprobe` 2026-09-03 (below)
- [x] HLS remux ≈ Direct Play × **1.05** mux; full transcode **8 Mbps** profiled (worse CPU + airtime)
- [x] Screensaver vs VoD: **image SS is out of video-N**; **Kodi video SS** and VoD **Playing** are full sessions
- [x] Audio: Gold Sheep Lite `aac_silent` is negligible vs video; leave mute/on out of the formula

### B — Usable link capacity

- [x] Bottleneck hop identified: this lab’s furnaces are **WiFi STA** (`eth0 DOWN`)
- [x] TCP goodput measured 16a→08a **35.3 Mbps**, 16a→04a **47.1 Mbps** (64 MiB); `wifi-pi` uses the slower hop
- [x] Headroom **30%**; WiFi-uplinked Pi is the tight case — prefer Ethernet when N > 1–2 video sessions

### C — Estimate CLI

```bash
cd /opt/jellyflam3-server
python3 -m pipeline.link_capacity estimate --profile wifi-pi --mode directplay
python3 -m pipeline.link_capacity estimate --profile eth-gigabit --mode directplay
python3 -m pipeline.link_capacity estimate --mode transcode
python3 -m pipeline.link_capacity probe
python3 -m pipeline.link_capacity profiles
# Measure YOUR hop (server Pi, then a client host):
python3 -m pipeline.link_capacity bench-serve --port 18791 --mib 64
python3 -m pipeline.link_capacity bench-recv --host <Pi_LAN_IP> --port 18791
python3 -m pipeline.link_capacity estimate --usable-mbps <printed>
```

Optional yaml (`configs/jellyflam3.yaml.example` → `link_capacity.*`): `default_profile`, `headroom`, `usable_mbps`. Direct Play session bps still comes from `encode.video_bitrate` or `probe`.

### D — Lab check (2026-09-03)

Fleet: three Pi 5 furnaces, all **wlan0 STA**, **eth0 DOWN**. No Ethernet control on this hardware — `eth-gigabit` stays **profiled**.

**Catalog Direct Play (ffprobe format bit_rate):**

| Host | MP4s | mean | p50 | p90 | min–max |
|---|---:|---:|---:|---:|---|
| 16a (`4M` encode) | 8 | 3.982 | 3.982 | 4.003 | 3.955–4.006 |
| 08a (`4M` encode) | 12 | 3.876 | 3.997 | 4.010 | 2.570–4.055 |
| 04a (`3M` compact) | 12 | 2.985 | 2.985 | 3.033 | 2.917–3.035 |

**TCP goodput (64 MiB, python socket; STA→AP→STA):**

| Path | Mbps |
|---|---:|
| 16a → 08a | 35.33 |
| 16a → 04a | 47.09 |

**Concurrent HTTP pull of one 11.4 MB / 23 s clip** (16a `http.server` → 08a; burstier than 64 MiB TCP):

| Parallel N | Wall s | Aggregate Mbps | Slowest s vs 23 s clip |
|---:|---:|---:|---|
| 1 | 1.15 | 79.3 | well ahead |
| 6 | 8.21 | 66.8 | well ahead (matches `N_max=6`) |
| 12 | 20.18 | 54.3 | 20 s ≈ clip length — stall risk if buffers are empty |

No on-TV stall log this pass (HTTP proxy, not Roku VoD). Idle-gate was not exercised (no Jellyfin Playing). Pi CPU was not the limiter on bulk TCP.

**Calculator at defaults (4 Mbps Direct Play, 30% headroom):**

| Profile | Usable Mbps | N_max Direct Play | N_max transcode (8 Mbps) |
|---|---:|---:|---:|
| `wifi-pi` (lab) | 35 | **6** | **3** |
| `wifi-ap-gigabit-backhaul` (profiled) | 80 | 14 | 7 |
| `eth-gigabit` (profiled) | 900 | 157 | 78 |

04a compact 3 Mbps on `wifi-pi` → `N_max=8`.

## Guidelines

1. Prefer **Direct Play MP4** for ambient TV; transcode both heats the Pi and burns more of the link.
2. Screensaver image clients are out of the video-N count; **Kodi ES screensaver** is in the video-N count when it plays loops.
3. Idle-gate still pauses the **furnace** while any matching TV is Playing — concurrency here is **playback**, not simultaneous render + play.
4. Estimates are **LAN**. Tailscale / WAN is a different (usually worse) budget; mention but do not DoD on it.
5. A **WiFi-uplinked Pi as Jellyfin server** is the tight case. Plug **Ethernet** when several TVs play at once.

## Non-goals

- Rewriting Jellyfin streaming core or adding a custom CDN
- Per-TV 4K encode retarget
- Guaranteeing glitch-free WiFi on a saturated 2.4 GHz AP
- Merging this into Roku Store listing copy ([04](04_ROKU_PUBLISH.md))
- Enforcing `N_max` as a Jellyfin connection cap

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| [USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md) Layer 2 | docs | Ethernet vs WiFi; Direct Play vs transcode |
| `pipeline/link_capacity.py` | pipeline | `N_max` CLI + catalog probe + hop bench |
| `configs/jellyflam3.yaml.example` `link_capacity.*` | config | Profile / headroom; session bps stays encode/`probe` |
| This guide § D | docs | WiFi lab vs Ethernet profile; concurrent HTTP vs `N_max` |

## Exit criteria

- [x] Documented formula + measured (or profiled) per-session bps for Direct Play ambient loops
- [x] Calculator outputs integer N_max with explicit headroom and link kind
- [x] Lab note: WiFi vs Ethernet concurrent playback vs estimated N (stalls / no stalls)
- [x] Operator docs warn that a WiFi-uplinked Pi is the tight case
- [ ] Owner OK

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | _TBD_ | [ ] |

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [04_ROKU_PUBLISH.md](04_ROKU_PUBLISH.md) · [../phase2/03_HLS_CLIENT_STREAMING.md](../phase2/03_HLS_CLIENT_STREAMING.md) · [../phase1/06_IDLE_GATE.md](../phase1/06_IDLE_GATE.md) · [../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md](../phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md) · [../USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md)
