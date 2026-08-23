# 01 — Hardware and OS

## Boundary

Physical Raspberry Pi 5 + OS only — **stop before** git clone / package builds.

## BOM

| Item | Notes |
|---|---|
| Raspberry Pi 5 | **8 GB** preferred (4 GB workable with zram) |
| Active Cooler | Required for sustained flam3 + NVMe |
| 5 V / 5 A PSU | Official or equivalent |
| NVMe via M.2 HAT+ | 2230/2242, 512 GB–2 TB — **recommended** |
| *or* USB 3 SSD | UASP enclosure — budget alternative |
| microSD | Rescue / OS-only if media on SSD |

See architecture hardware section in [Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md).

## Tasks

1. Flash **Raspberry Pi OS 64-bit** (Bookworm or newer); enable SSH.
2. Set hostname (e.g. `jellyflam3`).
3. Install cooler; attach NVMe HAT+ or USB SSD; boot.
4. Create and mount:
   - `/media/sheep` — catalog mount (Jellyfin **Sheep** → `by-generation/`; previews → `_refactor-preview/`)
   - `/var/cache/jellyflam3/frames` — render scratch
   - `/var/lib/jellyflam3/{jobs,logs,genomes}` — queue + state
5. Add mounts to `/etc/fstab`; enable NTP.
   - If one NVMe volume is mounted at `/var/cache/jellyflam3`, keep state on that disk via bind mount:
     `/var/cache/jellyflam3/lib` → `/var/lib/jellyflam3` (`none bind`).
6. Optional: zram on 4 GB boards.

Helper (run on Pi): `scripts/bootstrap_pi.sh` (creates directories + optional NVMe bind; does not flash OS).

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `scripts/bootstrap_pi.sh` | script | Create media/scratch/state dirs + optional NVMe bind |
| `/etc/fstab` | config | Persist `/media/sheep`, scratch, and bind mounts |
| Raspberry Pi OS (64-bit) | binary | Host OS (Bookworm+) |
| NVMe / USB SSD mounts | config | Media library + frame-scratch layout |

## Exit criteria

- [x] Can SSH into the Pi
- [x] NVMe or USB SSD mounted; `df -h` shows space for `/media/sheep` and scratch
- [x] Active Cooler present/running
- [x] microSD is **not** used for media library or frame scratch
