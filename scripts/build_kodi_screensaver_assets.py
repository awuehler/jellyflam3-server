#!/usr/bin/env python3
"""Purpose: Build Kodi addon fanart + screenshot JPGs from flock poster images.

Default: three sheep posters from the operator fleet (16a / 08a / 04a), resized for
Kodi add-on browser assets. Set JELLYFLAM3_FLEET_IP_16A / _08A / _04A env vars
(or edit FLEET_POSTERS below) before --fetch-fleet. Falls back to splash art when
fleet fetch fails and no cached posters exist under resources/posters/.

Requirements: python3, Pillow (requirements.txt).
Usage:
  python3 scripts/build_kodi_screensaver_assets.py
  python3 scripts/build_kodi_screensaver_assets.py --fetch-fleet

When to run: Before ``package_kodi_screensaver.*`` (also invoked by that script).
Success: ``resources/fanart.jpg`` + ``screenshot-0{1,2,3}.jpg`` under the add-on tree.
Docs: docs/phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SPLASH = ROOT / "roku-channel" / "images" / "splash-screen.png"
OUT = ROOT / "kodi-screensaver" / "screensaver.jellyflam3" / "resources"
POSTERS = OUT / "posters"


def _fleet_ssh(host_id: str) -> str:
    """SSH target for a furnace Pi; override via JELLYFLAM3_FLEET_IP_<HOST_ID>."""
    env_key = f"JELLYFLAM3_FLEET_IP_{host_id.upper()}"
    ip = os.environ.get(env_key, f"<RPi_IP_{host_id}>")
    return f"jellyflam3@{ip}"


# One poster per furnace Pi — diverse gens across the fleet catalog.
FLEET_POSTERS: tuple[tuple[str, str, str, str], ...] = (
    (
        _fleet_ssh("16a"),
        "/media/sheep/by-generation/243/electricsheep.243.14985-poster.jpg",
        "fleet-16a-gen243.jpg",
        "Gen 243 · 16a",
    ),
    (
        _fleet_ssh("08a"),
        "/media/sheep/by-generation/244/electricsheep.244.01807-poster.jpg",
        "fleet-08a-gen244.jpg",
        "Gen 244 · 08a",
    ),
    (
        _fleet_ssh("04a"),
        "/media/sheep/by-generation/242/electricsheep.242.03322-poster.jpg",
        "fleet-04a-gen242.jpg",
        "Gen 242 · 04a",
    ),
)

BG = (10, 10, 18)
# Kodi store art: keep JPGs small enough for install-from-zip on LibreELEC.
FANART_SIZE = (1280, 720)
SCREENSHOT_SIZE = (960, 540)
FANART_QUALITY = 82
SCREENSHOT_QUALITY = 80


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize with center crop to fill size."""
    tw, th = size
    src = img.convert("RGB")
    sw, sh = src.size
    scale = max(tw / sw, th / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - tw) // 2)
    top = max(0, (nh - th) // 2)
    return resized.crop((left, top, left + tw, top + th))


def _letterbox(img: Image.Image, size: tuple[int, int], fill: tuple[int, int, int] = BG) -> Image.Image:
    tw, th = size
    src = img.convert("RGB")
    sw, sh = src.size
    scale = min(tw / sw, th / sh)
    nw, nh = max(1, int(sw * scale)), max(1, int(sh * scale))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, fill)
    canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
    return canvas


def _caption(img: Image.Image, label: str) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((0, img.height - 72, img.width, img.height), fill=(*BG, 180))
    draw.text((36, img.height - 52), label, fill=(235, 235, 245, 255))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def fetch_fleet_posters(*, force: bool = False) -> list[Path]:
    """SCP flock *-poster.jpg from each lab Pi into resources/posters/."""
    POSTERS.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for host, remote, local_name, _label in FLEET_POSTERS:
        dest = POSTERS / local_name
        if dest.is_file() and not force:
            paths.append(dest)
            continue
        cmd = [
            "scp",
            "-o",
            "BatchMode=yes",
            f"{host}:{remote}",
            str(dest),
        ]
        print("fetch", host, remote)
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print("WARN: fleet fetch failed for", host, "—", exc, file=sys.stderr)
            if dest.is_file():
                paths.append(dest)
            continue
        paths.append(dest)
    return paths


def build_from_posters(posters: list[tuple[Path, str]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if len(posters) < 3:
        raise RuntimeError("need 3 fleet posters; run with --fetch-fleet on the LAN")

    # Fanart: letterbox the middle (08a gen 244) poster.
    fanart_src = Image.open(posters[1][0])
    _letterbox(fanart_src, FANART_SIZE).save(
        OUT / "fanart.jpg", quality=FANART_QUALITY, optimize=True
    )

    for i, (path, label) in enumerate(posters[:3], start=1):
        shot = _cover(Image.open(path), SCREENSHOT_SIZE)
        _caption(shot, label).save(
            OUT / f"screenshot-{i:02d}.jpg", quality=SCREENSHOT_QUALITY, optimize=True
        )

    print("Wrote fanart + 3 screenshots from fleet posters under", OUT)


def build_from_splash() -> None:
    splash = Image.open(SPLASH).convert("RGB")
    OUT.mkdir(parents=True, exist_ok=True)
    splash.resize(FANART_SIZE, Image.Resampling.LANCZOS).save(
        OUT / "fanart.jpg", quality=FANART_QUALITY, optimize=True
    )
    sw, sh = splash.size
    boxes = [
        (int(sw * 0.05), int(sh * 0.18), int(sw * 0.62), int(sh * 0.82)),
        (int(sw * 0.22), int(sh * 0.12), int(sw * 0.88), int(sh * 0.78)),
        (int(sw * 0.38), int(sh * 0.20), int(sw * 0.98), int(sh * 0.88)),
    ]
    for i, box in enumerate(boxes, start=1):
        crop = splash.crop(box).resize(SCREENSHOT_SIZE, Image.Resampling.LANCZOS)
        _caption(crop, f"Dream example {i}").save(
            OUT / f"screenshot-{i:02d}.jpg", quality=SCREENSHOT_QUALITY, optimize=True
        )
    print("Wrote fanart + 3 screenshots from splash fallback under", OUT)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Kodi screensaver store art JPGs")
    ap.add_argument(
        "--fetch-fleet",
        action="store_true",
        help="SCP poster JPGs from lab fleet Pis before building",
    )
    ap.add_argument(
        "--force-fetch",
        action="store_true",
        help="Re-download fleet posters even when cached locally",
    )
    ap.add_argument(
        "--splash-fallback",
        action="store_true",
        help="Use VoD splash art instead of flock posters",
    )
    args = ap.parse_args()

    if args.splash_fallback:
        build_from_splash()
        return 0

    if args.fetch_fleet or args.force_fetch:
        fetch_fleet_posters(force=args.force_fetch)

    posters: list[tuple[Path, str]] = []
    for _host, _remote, local_name, label in FLEET_POSTERS:
        path = POSTERS / local_name
        if path.is_file():
            posters.append((path, label))

    if len(posters) >= 3:
        build_from_posters(posters)
        return 0

    print("WARN: fewer than 3 cached fleet posters — trying fetch", file=sys.stderr)
    fetched = fetch_fleet_posters(force=True)
    posters = []
    for _host, _remote, local_name, label in FLEET_POSTERS:
        path = POSTERS / local_name
        if path.is_file():
            posters.append((path, label))
    if len(posters) >= 3:
        build_from_posters(posters)
        return 0

    print("WARN: fleet unavailable — splash fallback", file=sys.stderr)
    build_from_splash()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
