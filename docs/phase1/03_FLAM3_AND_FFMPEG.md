# 03 — flam3 and ffmpeg

## Boundary

Toolchain install + smoke render only — **stop before** Jellyfin ingest or job queue.

## apt dependencies (Pi OS)

```bash
sudo apt update
sudo apt install -y build-essential automake autoconf libtool pkg-config \
  libxml2-dev libpng-dev libjpeg-dev zlib1g-dev git ffmpeg
```

## Build flam3

```bash
# Full wrapper (apt + build + verify). Skip apt if already done:
./scripts/install_flam3.sh --skip-apt

# Optional: verify only, or build then smoke:
./scripts/install_flam3.sh --verify
./scripts/install_flam3.sh --skip-apt --smoke
```

Manual equivalent:

```bash
git clone https://github.com/scottdraves/flam3.git ~/src/flam3
cd ~/src/flam3
./configure && make -j"$(nproc)" && sudo make install
sudo ldconfig
which flam3-animate flam3-genome ffmpeg ffprobe
```

Or use helper: `./scripts/install_flam3.sh`
## Smoke render

```bash
export JELLYFLAM3_SMOKE=1
./scripts/smoke_render.sh
# default seed: genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3
```

Uses `smoke_duration_sec` / `smoke_nframes` (default **13 s → 312** at 24 fps) with `configs/templates/electricsheep.smoke.480p.flam3` (light quality; **never** the full 1080p TV template). Scratch defaults to `/var/cache/jellyflam3/smoke` when writable. **Never publish smoke outputs** to the catalog.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `scripts/install_flam3.sh` | script | apt deps + build + verify (+ optional smoke) |
| `scripts/smoke_render.sh` | script | End-to-end smoke MP4 under scratch |
| `flam3-animate` | binary | Frame-sequence renderer |
| `flam3-genome` | binary | Genome generate / sequence helper |
| `ffmpeg` / `ffprobe` | binary | H.264 encode + codec/duration probe |
| `configs/templates/electricsheep.smoke.480p.flam3` | config | Light smoke genome (not TV template) |

## Exit criteria

- [x] `flam3-genome`, `flam3-animate`, `ffmpeg`, `ffprobe` on `PATH`
- [x] `scripts/smoke_render.sh` completes with an MP4 under scratch
- [x] `ffprobe` shows h264
