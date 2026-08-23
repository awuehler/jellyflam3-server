# 03 — HLS client streaming

## Boundary

First-class **HLS** delivery from Jellyfin to media endpoints (JellyFlam3 Roku channel, jellyfin-roku, VLC, and similar) — **stop before** JellyFlam3 channel UX polish ([04](04_ROKU_CHANNEL_POLISH.md)). Depends on a working Jellyfin library from Phase 1 / [02](02_JELLYFIN_FLOCK_UX.md) posters preferred but not required for stream smoke.

**Status: complete** — Owner OK 2026-08-01 (pieces A–H).

Catalog posters remain [02](02_JELLYFIN_FLOCK_UX.md). SceneGraph chrome / TV probe: [04](04_ROKU_CHANNEL_POLISH.md) (**complete** Owner OK 2026-08-02).

## Intent

Phase 1 optimized masters for **Direct Play** (static MP4) to save Pi CPU. Phase 2 elevates **HLS** as a supported, documented path between Jellyfin and clients so:

- Roku (custom + jellyfin-roku), VLC, and other HLS-capable players share one origin model
- Remux / Direct Stream HLS is preferred when the H.264/AAC master already matches (no re-encode)
- Full HLS **transcode** stays a fallback under idle-gate rules (must not fight `flam3-animate`)

## Locked decisions

1. **Origin:** Jellyfin is the only stream origin (no separate nginx-rtmp / custom packager in Phase 2).
2. **Preferred path:** Jellyfin **HLS** playlist for multi-client playback; use **Direct Stream / remux** (copy video/audio into fMP4 or TS segments) when codecs already match Gold Sheep Lite masters.
3. **Direct Play MP4:** remains allowed where a client benefits (looping ambient on Roku; avoiding long-session HLS remux `.ts` lifecycle WRNs); channel may offer HLS as default with MP4 fallback, or settings toggle — document the chosen default in exit criteria.
4. **Transcode HLS:** allowed only when remux is impossible; respect idle-gate (block or defer while furnace is rendering if Sessions show active TV playback… existing gate semantics).
5. **Auth:** same API key / user token on playlist and segment URLs; no open anonymous HLS directory on LAN WAN edge.
6. **Clients in scope for DoD:** JellyFlam3 Roku channel, VLC (desktop/mobile), and jellyfin-roku Path 1 smoke. Others (Infuse, web) nice-to-have.

## Implementation pieces

| Piece | Status | Notes |
|---|---|---|
| **A** Jellyfin Playback / remux policy | Done (lab 2026-08-01) | Gold Sheep Lite = H.264 **High @ L4.2** + **AAC LC**; PlaybackInfo `SupportsDirectPlay` + `SupportsDirectStream` |
| **B** PlaybackInfo + HLS URL smoke | Done (retest 2026-08-01) | `scripts/hls_smoke.sh` → `SMOKE_OK`; prefer **`main.m3u8` + `MediaSourceId` + `AudioCodec=aac`** |
| **C** VLC / ffprobe acceptance | Done (lab headless; retest 2026-08-01) | ffprobe h264/aac, duration OK; **LAN** curl/ffprobe on public IP also 200; owner may confirm VLC UI once |
| **D** JellyFlam3 `streamFormat=hls` | Done (Owner OK 2026-08-01) | Channel 1.0.13: `main.m3u8` + `AudioCodec=aac`; sideload + HLS play + remux `FFmpeg exited with code 0` confirmed |
| **E** Loop HLS vs MP4 decision | Done (Owner OK 2026-08-01) | Ambient **MP4** + seek-reloop (1.0.15); both gap on Roku VOD; **MP4 hitch shorter** than HLS. Gapless → Phase 4 edges |
| **F** jellyfin-roku Path 1 | Done (Owner OK 2026-08-01) | Stock jellyfin-roku plays Sheep flock; long-session `.ts` WRNs documented (known limitation) |
| **G** Remux/transcode + idle-gate policy write-up | Done (Owner OK 2026-08-01) | Formal policy below; long-session HLS limitation included |
| **H** Lab sign-off | Done (Owner OK 2026-08-01) | Guide 03 exit criteria met |

### Retest log (A–C)

| Date | Result |
|---|---|
| 2026-08-01 | `HLS_SMOKE_ITEM=ce6bb166…` → `SMOKE_OK` (PlaybackInfo DirectPlay+DirectStream; HTTP 200; ffprobe hls/h264/aac ~23s; Static HEAD 200) |
| 2026-08-01 | LAN host `http://192.168.X.Y:8096/.../main.m3u8?...&AudioCodec=aac` → curl 200 + ffprobe `format_name=hls` |

## Jellyfin endpoints (operator cheat sheet)

Lab Jellyfin **10.11.11**. Prefer PlaybackInfo negotiation for apps; for VLC/manual smoke use the **media playlist** URL below.

| Mode | Typical client use |
|---|---|
| **PlaybackInfo** | `POST /Items/{id}/PlaybackInfo?UserId=…` — reports DirectPlay / DirectStream / Transcode |
| **HLS (preferred smoke)** | `…/Videos/{id}/main.m3u8?MediaSourceId={id}&api_key=…&AudioCodec=aac` |
| **HLS master** | `…/Videos/{id}/master.m3u8?MediaSourceId={id}&api_key=…` — on 10.11.11 may embed broken `AudioCodec=m3u8` in the variant line; **do not rely on it** for DoD |
| **Static MP4** | `…/Videos/{id}/stream.mp4?Static=true&api_key=…` (Phase 1 Direct Play; keep for ambient loop) |

### Playback policy (piece A — locked for Gold Sheep Lite)

No encoding.xml change required for remux when masters match:

- Video: H.264 High, level **4.2**, yuv420p, 1920×1080 @ 24 fps  
- Audio: AAC LC stereo  
- Jellyfin HLS remux (observed): `-codec:v:0 copy -bsf:v h264_mp4toannexb` + `-codec:a:0 copy` into MPEG-TS segments under `/var/cache/jellyflam3/transcodes/`  
- Full audio/video re-encode is fallback only (idle-gate must still apply)

Dashboard sanity (Playback / Transcoding): allow Direct Stream / remux for H.264+AAC; HW encode (`v4l2m2m` on lab) is optional and unused on the remux path.

### Lab quirk (document for B/C)

`master.m3u8` without `MediaSourceId` → **400**. With `MediaSourceId` but default audio param, variant URI can set `AudioCodec=m3u8`, and Jellyfin then runs ffmpeg with `-codec:a:0 m3u8` → **exit 8**. Always pass **`AudioCodec=aac`** (or use `main.m3u8` with that query).

## Client guidelines

### JellyFlam3 Roku channel (pieces D–E — 1.0.13 / 1.0.14)

| Concern | Policy |
|---|---|
| **HLS remux path (D)** | `{base}/Videos/{id}/main.m3u8?MediaSourceId={id}&api_key=…&AudioCodec=aac` — lab-verified; not `master.m3u8` |
| **Ambient default (E)** | **`streamMode=mp4`** → Static Direct Play (lighter rebuffer than HLS remux on each cycle) |
| **Reloop mechanic (E)** | **Seek-to-0** near EOF (`position` ≥ duration−0.4s) + `finished` backup; **`Video.loop=false`** (native loop still gaps and fights seek) |
| **Lab finding** | Owner OK 2026-08-01: both gap on Roku VOD; **MP4 seek-reloop hitch shorter** than HLS (keep ambient default = mp4) |
| **HLS compare** | `streamMode=hls` — same seek-reloop; usually a longer gap (playlist/segments) |
| **Error fallback** | Cross-try the other format once (HLS↔MP4) |
| **Sessions** | `PlayMethod=DirectPlay` on MP4; `DirectStream` on HLS |
| **Idle-gate** | `/Sessions/Playing` (+ progress/stopped); Client `JellyFlam3` / Device `Roku` |

**Locked decision (E):** Keep ambient default = MP4 + seek-reloop (minimize gap; do not pretend gapless). Accept residual hitch on Roku VOD. Gapless / crossfade belongs to Phase 4 [edges](../phase4/03_EDGES_AND_WATERMARK.md). Hours-long continuous / live HLS from shuffled flock MP4s is **not** a Phase 3 deliverable (randomizer dropped). HLS remains first-class for VLC / jellyfin-roku / lab remux (A–D).

**Jellyfin server:** no `encoding.xml` change required for Gold Sheep Lite remux (A–C already confirmed `-codec:v copy -codec:a copy`). Ensure `/var/cache/jellyflam3/transcodes/` is writable by `jellyfin` (existing lab layout).

### jellyfin-roku (Path 1) — Owner OK 2026-08-01

- Point at Pi Jellyfin; confirm sheep play via server-chosen method (often HLS/Direct Stream).
- No custom channel code required; used as interoperability baseline.
- **Lab:** Path 1 plays the Sheep flock after HLS work (piece F).
- **Long continue-play / loop:** Path 1 commonly uses Jellyfin HLS remux. After many minutes the server may tear down the remux job while the client still requests `.ts` segments — see [Known limitations](#known-limitation-long-running-hls-vod-sessions). Observed in lab; does not fail Path 1 smoke.

### VLC

```text
# Preferred (lab-verified remux) — replace host, itemId, api_key
# Use the Pi LAN (or Tailscale) IP — not 127.0.0.1 — from a desktop player.
http://JELLYFIN_LAN:8096/Videos/{itemId}/main.m3u8?MediaSourceId={itemId}&api_key=YOUR_KEY&AudioCodec=aac
```

- On the Pi, `./scripts/hls_smoke.sh` prints `VLC_URL` with a **client-facing** host (`JELLYFIN_PUBLIC_URL` / `JELLYFIN_LAN_HOST` / auto-detect). API probes may still use `JELLYFIN_URL=http://127.0.0.1:8096`.
- VLC: **Media → Open Network Stream** → paste that `VLC_URL`.
- Verify start; Pi should stay near idle (video+audio **copy**, not full transcode).
- Optional: same path over HTTPS / Tailscale when leaving pure LAN.
- Headless lab check: `ffprobe`/`ffmpeg` against loopback **and** LAN URL (both verified on lab).

## Ops / furnace interaction

- HLS remux is light; HLS **transcode** competes with flam3 — idle-gate + `max_cpus` remain mandatory.
- Segment cache on lab: `/var/cache/jellyflam3/transcodes/` (must be writable by `jellyfin`).
- `status_report.sh` / Sessions: confirm Client device during HLS play for gate matching.

## Piece G — Remux / transcode + idle-gate policy (locked)

Formal ops policy for Phase 2 guide 03. Complements Phase 1 [06_IDLE_GATE.md](../phase1/06_IDLE_GATE.md).

### Delivery modes (preference order)

| Rank | Mode | Jellyfin / ffmpeg | When | Furnace impact |
|---|---|---|---|---|
| **1** | **Direct Play** (Static MP4) | No remux job; `stream.mp4?Static=true` | JellyFlam3 ambient default (`streamMode=mp4`); clients that accept progressive MP4 | Negligible CPU; preferred for long dream sessions |
| **2** | **Direct Stream / HLS remux** | `-codec:v copy` + `-codec:a copy` → MPEG-TS under `/var/cache/jellyflam3/transcodes/` | Gold Sheep Lite H.264 High@L4.2 + AAC; VLC / jellyfin-roku / channel `streamMode=hls` | Light (mux/copy only); OK while TV plays; does **not** require closing the idle-gate by itself |
| **3** | **HLS transcode** (re-encode) | Full video/audio encode (`TranscodingInfo` present) | Only when remux/Direct Play impossible (odd codec/device) | **Heavy** — competes with `flam3-animate`; must not be the default for flock masters |

**Do not** “fix” remux or long-session `.ts` WRNs by forcing full transcode.

### Gold Sheep Lite → remux (lab truth)

- Masters: H.264 High, level ≤ 4.2, yuv420p, AAC LC stereo, `+faststart` MP4.
- PlaybackInfo: `SupportsDirectPlay` + `SupportsDirectStream` = true on lab.
- Remux logs: `FFmpeg.Remux-*.log` with stream mapping **copy→copy**; exit 0.
- Prefer URL: `main.m3u8?MediaSourceId=…&AudioCodec=aac` (avoid `master.m3u8` / `AudioCodec=m3u8` quirk on 10.11.11).
- No `encoding.xml` change required for remux; HW encode (`v4l2m2m`) unused on the remux path.

### Idle-gate interaction

Gate polls `GET /Sessions?activeWithinSeconds=…` (default patterns include Roku / JellyFlam3 / jellyfin-roku).

| Signal | Config / behavior | Effect on furnace |
|---|---|---|
| TV-class client with `NowPlayingItem` or recent `LastPlaybackCheckIn` | `tv_client_patterns` | **Block** renders (`active_tv_client`) |
| Any session with `TranscodingInfo` | `block_on_any_transcode: true` (default) | **Block** — full re-encode or jobs Jellyfin reports as transcoding |
| Direct Play / Direct Stream remux without `TranscodingInfo` | Normal Path 1 / channel HLS remux | Gate still blocks on **TV NowPlaying**; remux alone is not a reason to skip the gate when a TV is watching |
| Resume | `idle_delay_sec` (lab 600) after clear | Worker may start new jobs only when gate open |

**Phase 2 invariant:** Default flock playback (MP4 Direct Play or HLS remux of Gold Sheep Lite) must **not** require defeating the idle-gate. If a client forces full transcode, the gate correctly pauses the furnace — that is desired, not a bug.

**Client reporting (keep working):**

- JellyFlam3: `Client=JellyFlam3`, `Device=Roku`; POST `/Sessions/Playing` (+ progress/stopped) with `PlayMethod=DirectPlay` (MP4) or `DirectStream` (HLS).
- jellyfin-roku / VLC: rely on Jellyfin’s own session rows; patterns already match Roku / jellyfin-roku.

### Client defaults vs multi-client HLS

| Client | Default path | Rationale vs furnace / ops |
|---|---|---|
| **JellyFlam3** | Ambient **MP4** + seek-reloop | Shortest re-loop hitch; no remux `.ts` lifecycle; Sessions DirectPlay |
| **jellyfin-roku / VLC** | Server-chosen; usually **HLS remux** | Interop baseline; remux OK; long-session `.ts` WRNs accepted (known limitation) |
| **Odd devices** | Transcode fallback | Gate blocks furnace while `TranscodingInfo` active |

### Operator verification (piece G checklist)

```bash
# During JellyFlam3 ambient (mp4): expect DirectPlay, no FFmpeg.Transcode-*
curl -sS -H "Authorization: MediaBrowser Token=$JELLYFIN_API_KEY" \
  "${JELLYFIN_URL%/}/Sessions" | python3 -m json.tool | head -80

# During HLS remux smoke: FFmpeg.Remux-* with -codec:v copy -codec:a copy
ls -lt /var/log/jellyfin/FFmpeg.Remux-* | head
grep -E "codec:v:0 copy|codec:a:0 copy|TranscodingInfo" /var/log/jellyfin/FFmpeg.Remux-* | head

# Idle-gate sees TV play
python3 -m pipeline.idle_gate --config configs/jellyflam3.yaml --once   # if supported
cat /var/lib/jellyflam3/idle_gate_status.json
./scripts/status_report.sh
```

Expect: gate **closed** (or delaying resume) while Roku/JellyFlam3/jellyfin-roku is actively playing; **no** need to disable `block_on_any_transcode` for normal remux.

### Related known limitation

Long-running HLS VoD remux sessions may log `no transcode is running` for missing `.ts` — see [Known limitations](#known-limitation-long-running-hls-vod-sessions). Stance: accept for Path 1; prefer MP4 for JellyFlam3 ambient; never “fix” with full transcode.

## Known limitation: long-running HLS VoD sessions

**Lab confirmed 2026-08-01** on Jellyfin **10.11.11** (`/var/log/jellyfin/jellyfin20260801.log`).

### Symptom

After **continued HLS play for many minutes** (Path 1 jellyfin-roku observed; any long-lived HLS client can hit this), Jellyfin logs warnings such as:

```text
[WRN] cannot serve "/var/cache/jellyflam3/transcodes/<jobId><n>.ts"
      as it doesn't exist and no transcode is running
```

Example afternoon cluster: remux for `…/jellyflam3.ES_gen_247__electricsheep.247.00505.mp4` wrote segments at **11:56–11:57**; client segment requests at **12:35–12:39** (~38 minutes later) produced **16** WRNs for job `10491a858d9d9630821a5875b93eced7` (segments `0.ts`–`3.ts`). Day total for this message: **22** (includes an earlier morning cluster from the broken `AudioCodec=m3u8` smoke path).

### What it is / is not

| | |
|---|---|
| **Is** | Jellyfin dynamic HLS **remux job lifecycle**: ffmpeg finishes (or the play session is cleaned up); the client still requests playlist segments; server has **no active remux** and cannot serve the expected `.ts` path → WRN |
| **Is not** | A Gold Sheep Lite encode defect, missing `encoding.xml` remux support, or idle-gate failure |
| **Lab encoding.xml** | `EnableSegmentDeletion=false`, `EnableThrottling=false` — WRNs still occur when the **job** is gone even if some cache files linger or are later rewritten |

### Impact

- May cause brief Path 1 stall / rebuffer / failed segment fetch until the client renegotiates PlaybackInfo / starts a **new** remux.
- Repeats on ambient-style “watch the same short sheep for a long time” over **HLS** (loop or continue).
- **JellyFlam3 ambient default (`streamMode=mp4`)** avoids this path entirely (Static Direct Play; no remux `.ts` cache).
- VLC / short smoke (`hls_smoke.sh`) rarely hit the multi-tens-of-minutes window.

### Operator checks

```bash
# Count today's WRNs
grep -c "no transcode is running" /var/log/jellyfin/jellyfin$(date +%Y%m%d).log

# Recent examples
grep "no transcode is running" /var/log/jellyfin/jellyfin$(date +%Y%m%d).log | tail -20

# Correlate with remux jobs / cache
ls -lt /var/cache/jellyflam3/transcodes/ | head
ls -lt /var/log/jellyfin/FFmpeg.Remux-* | head
```

### Mitigations / product stance (Phase 2)

1. **Ambient JellyFlam3:** keep **`streamMode=mp4`** (piece E) for long dream sessions.  
2. **Path 1 / multi-client HLS:** accept as a **known Jellyfin VoD remux limitation** for long sessions; remux copy path remains correct for short/normal plays.  
3. **Do not** “fix” by enabling full HLS transcode — that fights the furnace.  
4. **Future (out of Phase 2 guide 03):** longer-lived playlists, sticky remux sessions, or Phase 4 [edge packaging](../phase4/03_EDGES_AND_WATERMARK.md) if product needs smoother multi-sheep journeys.

Covered by pieces **F** (lab observation) and **G** (ops policy above).

## Commands

```bash
# On Pi — full A–C smoke (PlaybackInfo + HLS remux + print VLC_URL)
cd /opt/jellyflam3-server
chmod +x scripts/hls_smoke.sh   # once after pull if needed
./scripts/hls_smoke.sh
# or pin a sheep:
# HLS_SMOKE_ITEM=ce6bb166f8514b442f42fee072e3fb68 ./scripts/hls_smoke.sh
# Optional: force client host if auto-detect is wrong:
# JELLYFIN_PUBLIC_URL=http://192.168.x.x:8096 ./scripts/hls_smoke.sh

# VLC on a desktop: open the printed VLC_URL (LAN/public IP, not 127.0.0.1)

# Package / sideload JellyFlam3 (D–E):
./scripts/package_roku_channel.ps1   # → dist/jellyflam3-roku.zip (1.0.15+)
# Default streamMode=mp4 → seek-reloop; expect possible micro-gap (Roku VOD)
# streamMode=hls → same mechanic; usually longer gap
./scripts/status_report.sh
```

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `scripts/hls_smoke.sh` | script | PlaybackInfo + `main.m3u8` remux + `VLC_URL` |
| `jellyfin` | binary | HLS remux / Direct Stream origin |
| `ffmpeg` / `ffprobe` | binary | Remux path verification |
| `roku-channel/` (`streamMode` hls/mp4) | channel | Client HLS + ambient MP4 seek-reloop |
| `scripts/package_roku_channel.{sh,ps1}` | script | Sideload builds for HLS / loop policy |
| `pipeline/idle_gate.py` | pipeline | Block furnace on TV play / full transcode |
| `scripts/status_report.sh` | script | Session / furnace interaction checks |
| `jellyfin-roku` | channel | Path 1 HLS interop baseline |

## Exit criteria

- [x] Jellyfin Playback / HLS Direct Stream documented for Gold Sheep Lite masters (piece A)
- [x] VLC / HLS URL path verified (piece C — `main.m3u8` + `AudioCodec=aac`; ffprobe remux OK; owner VLC optional)
- [x] JellyFlam3 channel plays via `streamFormat=hls` (`main.m3u8` + AAC; build 1.0.13+) — Owner OK 2026-08-01 (sideload, Buffering (hls), remux exit 0)
- [x] Loop policy locked: ambient = MP4 + seek-reloop; both gap on Roku VOD; MP4 hitch shorter — Owner OK 2026-08-01 (build 1.0.15+); gapless → Phase 4 edges
- [x] jellyfin-roku Path 1 still plays the flock — Owner OK 2026-08-01
- [x] Remux-vs-transcode policy written; idle-gate not defeated by default HLS/Direct Play — piece G Owner OK 2026-08-01
- [x] Lab sign-off (piece H) — Owner OK 2026-08-01

## See also

[Pi5_Flam3_VoD_Pipeline.md — Jellyfin role / HLS](../Pi5_Flam3_VoD_Pipeline.md#jellyfins-role-curated-flock--vod-origin) · [04_ROKU_CHANNEL_POLISH.md](04_ROKU_CHANNEL_POLISH.md) · [../phase1/06_IDLE_GATE.md](../phase1/06_IDLE_GATE.md) · [../phase1/08_ROKU_BRIGHTSCRIPT.md](../phase1/08_ROKU_BRIGHTSCRIPT.md)
