# 08 — Dynamic duration

## Boundary

Choose VoD length from **flam3 XML signals**, with soft-max bypass and a hard ceiling — **stop before** Pi-from-scratch guide ([09](09_PI_FROM_SCRATCH.md)).

Loop lengths are **period-aware**: rotation, color-speed, and animated weight periods snap `nframes` so each catalog loop **closes cleanly**.

## Locked band

| Knob | Value |
|---|---|
| Min | **7 s** |
| Soft max | **37 s** (Phase 1 band / default clamp) |
| Hard max | **120 s** (`max_duration_sec_hard`) |
| Bypass | `allow_bypass_max: true` → signals may exceed soft max, never hard max |
| Smoke | **13 s** unchanged; never publish |

## Implementation

| Piece | Location |
|---|---|
| Signal extractor | `pipeline/genome_signals.py` |
| Duration chooser + period snap | `pipeline/choose_duration.py` |
| Worker wiring | `pipeline/worker.py` (signals → nframes → sidecar) |
| Config | `vod.duration_mode` / `vod.dynamic` in `jellyflam3.yaml.example` |
| Tests | `tests/test_choose_duration.py` |

### Periodic loop closure

Detected periods (seconds) from genome XML:

| Source | Model |
|---|---|
| **Rotation** (`rotate=`) | Periods for integer flame-turn closure (`360/\|rotate\|`) |
| **Color shifts** (`color_speed`) | `period = 1/speed` (cycles/sec model) |
| **Animated weights** | Reciprocal of normalized xform weights when `animate≠0` |

`snap_to_periods: true` (default) LCM-snaps `nframes` to those periods inside the effective band so the VoD lands on a seamless loop boundary. Camera orbit from `flam3-genome sequence=` remains one 360° pass over `nframes`.

**Frozen orbit:** when every non-final xform is stationary (`is_orbit_frozen` — explicit `animate=0` or deprecated `symmetry>0`), `period_candidates_sec` is empty. Do **not** treat flame `rotate=` as a loop period (that snapped `electricsheep.245.09797` to a false 0.27 s fundamental). Duration stays on the normal dynamic band; the worker still-loops one Lite still for that length instead of hundreds of identical animate frames.

### Warning — period-snap LCM blow-up

When several period candidates are present, `lcm_many` can produce a **fundamental frame count near the soft max**, so a modest dynamic target (e.g. ~19–31 s) snaps to the **full soft-max length** (e.g. **43 s / 1032 frames**). Observed on pedigree mutates of `electricsheep.247.14181` where candidates included `43.0` s: target ≈ 19–31 s → snapped `duration_sec: 43.0`.

**Impact:** Gold Sheep Lite × soft-max nframes is many hours on 3 cores and uses far more scratch/catalog disk than the pre-snap center.

**Operator toggle** (`configs/jellyflam3.yaml`):

```yaml
vod:
  dynamic:
    snap_to_periods: false   # keep dynamic base_sec ± weights; skip LCM snap
```

Leave **`true` (locked fleet default)** for seamless loop closure across all HW profiles. Soft-max cost when LCM blows up is accepted; do not treat disabling snap as pre–Phase 3 debt. Set `false` only for a one-off lab/debug render if needed.

## Guidelines

1. Parse genome XML into `job["signals"]` (xform count, animate count, multi-flame risk, complexity, periods).
2. Wire worker → `choose_duration` / `choose_nframes` with those signals; default config uses `duration_mode: dynamic`.
3. `assert_duration_in_band` / ffprobe gate use **hard** max when bypass is on; soft max when not.
4. Record chosen duration + signals + period-snap meta in sidecar / job.json.
5. Document thermal cost: Gold Sheep Lite × long nframes can take many hours on 3 cores — bias shorter under queue pressure.
6. Profile class **rpi-jellyflam3-04** (`render.hw_profile`; hosts `…-04a`/`…-04b`/…) applies `profile_04_short_bias` (default 4 s). Quality stays Lite/`compact` — bias shortens loops for disk, not quality.
7. **HW-scaled VoD bands** live in `configs/profiles/rpi-jellyflam3-{16,08,04}.yaml` (soft/hard max + `dynamic.base_sec` grow with sheep-disk / RAM class). Apply with `python3 -m pipeline.hw_profile apply 08a`. See [09](09_PI_FROM_SCRATCH.md).

## Config sketch

```yaml
vod:
  duration_mode: dynamic
  min_duration_sec: 11
  max_duration_sec: 37            # profile overlay may set 43 / 37 / 31
  max_duration_sec_hard: 90       # profile overlay may set 113 / 90 / 60
  allow_bypass_max: true
  dynamic:
    base_sec: 23                  # profiles: 43 (-16) / 31 (-08) / 23 (-04)
    snap_to_periods: true         # locked fleet default (seamless loops); see LCM warning above
    profile_04_short_bias: 4
    weights:
      complexity: 0.35
      queue_pressure: -0.25
      jitter_sec: 0
```

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/genome_signals.py` | pipeline | Extract XML complexity / period signals |
| `pipeline/choose_duration.py` | pipeline | Dynamic duration + period-aware nframes snap |
| `pipeline/worker.py` | pipeline | Wire signals → nframes → sidecar / ffprobe gate |
| `configs/jellyflam3.yaml` (`vod.duration_mode`, `vod.dynamic`) | config | Soft/hard max, snap, `-04` short bias |
| `ffprobe` | binary | Assert catalog duration in effective band |

## Exit criteria

- [x] XML signal extractor implemented and unit-tested
- [x] Dynamic mode selects duration from signals
- [x] Soft bypass cannot exceed 120 s hard max
- [x] ffprobe gate matches config (`assert_duration_in_band` uses effective max)
- [x] Sidecar/job records duration + signals (+ period snap meta)
- [x] `tests/test_choose_duration.py` covers bypass + period-closure cases
- [x] Period-aware snap for rotate / color_speed / animated weights
- [x] Pi verify — `rpi-jellyflam3-08a` `electricsheep.247.47501`: `duration_mode=dynamic`, ffprobe **27.708 s** (≤ soft 37 / hard 120), sidecar `signals` + `duration_meta.period_snap.snapped=true` (2026-08-08)

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-08 | [x] |

Guide 08 complete. Next: [09_PI_FROM_SCRATCH.md](09_PI_FROM_SCRATCH.md) (already Owner OK) · [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md).

## See also

[Pi5_Flam3_VoD_Pipeline.md — VoD duration](../Pi5_Flam3_VoD_Pipeline.md#vod-duration-target-phase-1-band--phase-2-dynamic)
