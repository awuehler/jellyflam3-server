# 06 — Idle gate

## Boundary

CPU isolation supervisor only — **does not** own encode logic.

## Behavior

- Poll `GET /Sessions?activeWithinSeconds=…`
- Block when TV-class client has `NowPlayingItem` **or** recent `LastPlaybackCheckIn`, or any `TranscodingInfo`
- Resume only after `idle_delay_sec` (**600** default) clear (hold is restored from status JSON if idlegate restarts mid-delay; `reason=idle_delay`)
- JellyFlam3 **VoD** on the flock Home grid can still look active (`LastPlaybackCheckIn`) without a sheep playing; image screensaver is ignored
- Worker checks status **before** claiming and at stage boundaries (sequence / animate / encode). Playing does **not** pause a live `flam3-animate`
- Operator CLIs that extract (`python3 -m pipeline.backfill_posters`) call the same `wait_for_gate` — no `--skip-gate`
- Only `jellyflam3-idlegate` writes `/var/lib/jellyflam3/idle_gate_status.json`. Missing or stale `open` (`updated_at` older than 3× `poll_interval_sec`) is **closed**
- `wait_for_gate` logs `idle-gate closed; waiting 15s before backfill continues` — **15 s** is the sleep cap (`seconds_until_resume` max 15), not the remaining `idle_delay_sec` hold. Read the status JSON.
- Keep `freeze_worker: false`. Drain wait errors if the worker unit is frozen
- JellyFlam3 Roku channel (build **1.0.9+**) POSTs `/Sessions/Playing` (+ progress/stopped) so Direct Play / Direct Stream is visible to the gate
- Phase 2 HLS remux of Gold Sheep Lite is light; full transcode still trips `block_on_any_transcode` — see [../phase2/03_HLS_CLIENT_STREAMING.md](../phase2/03_HLS_CLIENT_STREAMING.md#piece-g--remux--transcode--idle-gate-policy-locked)

```bash
python3 -m pipeline.idle_gate --config configs/jellyflam3.yaml
```

Status: `/var/lib/jellyflam3/idle_gate_status.json` (`gate`, `reason`, `seconds_until_resume`, `idle_clear_since`, `updated_at`). Writes are temp + `os.replace`. Corrupt, unreadable, **missing**, or stale JSON is **closed**. Hammer deletes the status file (does not write a fake `open`).

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
