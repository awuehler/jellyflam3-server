# 06 — Idle gate

## Boundary

CPU isolation supervisor only — **does not** own encode logic.

## Behavior

- Poll `GET /Sessions?activeWithinSeconds=…`
- Block when TV-class client has `NowPlayingItem` **or** recent `LastPlaybackCheckIn`, or any `TranscodingInfo`
- Resume only after `idle_delay_sec` clear
- Worker checks status before starting jobs
- JellyFlam3 Roku channel (build **1.0.9+**) POSTs `/Sessions/Playing` (+ progress/stopped) so Direct Play / Direct Stream is visible to the gate
- Phase 2 HLS remux of Gold Sheep Lite is light; full transcode still trips `block_on_any_transcode` — see [../phase2/03_HLS_CLIENT_STREAMING.md](../phase2/03_HLS_CLIENT_STREAMING.md#piece-g--remux--transcode--idle-gate-policy-locked)

```bash
python3 -m pipeline.idle_gate --config configs/jellyflam3.yaml
```

Status: `/var/lib/jellyflam3/idle_gate_status.json` (`gate`, `reason`, `seconds_until_resume`).

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/idle_gate.py` | pipeline | Poll Sessions; close / open furnace gate |
| `deploy/systemd/jellyflam3-idlegate.service` | deploy | Always-on supervisor unit |
| `configs/jellyflam3.yaml` (`idle_gate`) | config | Poll interval, idle delay, TV client patterns |
| `/var/lib/jellyflam3/idle_gate_status.json` | config | Gate status SoT for worker / ops |
| `jellyfin` Sessions API | binary | Playing / TranscodingInfo signals |

## Exit criteria

- [x] `pytest tests/` idle-gate cases pass
- [x] e2e pause/resume with Roku playback — Playing API closes gate (`active_tv_client`); delay resume unit-tested; sideload build 1.0.9 for live BrightScript reporting
- [x] systemd unit ready (guide 09)
