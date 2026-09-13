# Hardware media

Cutouts and a stack photo for furnace bring-up ([phase2/09_PI_FROM_SCRATCH.md](../../phase2/09_PI_FROM_SCRATCH.md) BOM). Transparent / black-background PNGs (`*_nobg`) sit in table cells next to the part name.

Placeholder `furnace-prototype.svg` / `furnace-prototype.jpg` were replaced by the files below. Do not reintroduce those names.

## Current artifacts

| File | Role | Used in |
|---|---|---|
| `raspberry-pi-furnace_nobg.png` | Assembled lab furnace (`RPI-JELLYFLAM3-16A`): Pi 5 + Active Cooler + M.2 HAT + X-FAN40 + USB sheep disk + CanaKit 35 W USB-C | Guide 09 **Prototype (photo)** |
| `raspberry-pi-5-16gb_nobg.png` | Raspberry Pi 5 board (16 GB class pictured; 8 GB / 4 GB use the same overlay class) | Guide 09 BOM row — Pi 5 |
| `raspberry-pi-5-active-cooler_nobg.png` | Official Raspberry Pi **Active Cooler** (CPU airflow) | Guide 09 BOM row — cooler |
| `raspberry-pi-5-nvme-hat_nobg.png` | **M.2 HAT+** (NVMe scratch + `/var/lib/jellyflam3`) | Guide 09 BOM row — HAT |
| `raspberry-pi-5-X-FAN40_nobg.png` | Second fan board (lab: Geekworm **X-FAN40** PWM HAT over the M.2 stack) | Guide 09 BOM row — 2nd fan |

Not pictured (brand-agnostic in the BOM): NVMe SSD, USB 3 sheep SSD / enclosure, 35 W USB-C PSU, microSD (OS), spacers / acrylic.

## Shot notes

- **Stack:** three-quarter view; label hostname if present; SD / NVMe / USB roles should stay obvious vs the BOM (OS / scratch / sheep).
- **Parts:** product-style cutouts, no lifestyle background; keep filenames `raspberry-pi-5-<part>_nobg.png`.
- Clients (Roku / Kodi) are **not** this folder — pasture chrome is [CLIENT_CHANNEL_ART.md](../../CLIENT_CHANNEL_ART.md).
- Sibling media: [demo](../demo/README.md) (README still) · [watermark](../watermark/README.md) (tuple edge Cesari assets).
