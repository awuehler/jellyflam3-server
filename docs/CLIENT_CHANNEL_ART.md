# Pasture channel art — generative image prompts

## Boundary

Household / operator **prompts** for a favorite **external** image generator (Midjourney, DALL·E, Flux, local SD, etc.). Output is **channel chrome**: Roku splash + Home icon, Kodi add-on icon + fanart, optional GitHub README header.

This is **not** furnace work. Do **not** ask `jellyflam3-worker`, idle-breed, or the parked Phase 5 Ventuno agent to mint these files. Do **not** ingest the PNGs into the Sheep library. Catalog posters stay mid-loop JPEGs from flam3 stills ([USER_GUIDE](USER_GUIDE_AND_RUNBOOK.md#catalog-posters-after-render)).

**Status:** Prompt pack for sideload / private-channel refresh. Store listing still parked ([phase4/04](phase4/04_ROKU_PUBLISH.md)).

## Intent

JellyFlam3 is a **furnace → pasture** product: a Raspberry Pi **furnace** renders **flam3** genomes, **ffmpeg** encodes Rec.709 H.264 **loops**, **Jellyfin** catalogs the **flock**, and **pasture** clients play them in the living room.

| Word | Show this | Do not show this |
|---|---|---|
| **Furnace** | Compact Pi-class node, heat-sink glow, quiet factory | Datacenter racks, cloud logos |
| **Sheep / flock** | Abstract **fractal flame** orbits (soft palettes, living-room TV) | Farm animals, Electric Sheep **Cesari** mascot |
| **Jelly** | Soft bell / gel volume as a *media* metaphor | Official **Jellyfin** jellyfish trademark |
| **Pasture** | Dark TV / Roku-like remote / Kodi idle, Direct Play | Netflix/YouTube chrome, transcode spinners |
| **Name** | **JellyFlam3** (product) | `jellyflam3-server` as on-image title |

Use **original JellyFlam3 art**. Do **not** crop `docs/media/watermark/Electric-Sheep-Icon*.png` or `Electric-Sheep-Logo.svg` into a channel mark ([NOTICE](../NOTICE), [watermark README](media/watermark/README.md)). Generated art is also **not** a tuple edge watermark unless you deliberately install it as `watermark.image`.

Generate at high resolution, then **crop and export** to the sizes below. Keep generator watermarks off the canvas (and strip them in post if they appear).

## Target files and sizes

Generate **one** 16:9 hero and **one** square mark, then crop.

| Role | Pixels | Install as |
|---|---|---|
| Roku splash HD (and lab FHD downsample) | **1280×720** | `roku-channel/images/splash-screen.png`, `roku-screensaver/images/splash-screen.png` |
| Optional Roku FHD splash | **1920×1080** | same filenames if you only ship one; letterbox/crop from the hero |
| Roku Home / focus icon | **290×218** | `mm_icon_focus_hd.png` (both Roku packages) |
| Kodi add-on icon | **256×256** (512 source is fine) | `kodi-screensaver/screensaver.jellyflam3/resources/icon.png` |
| Kodi fanart (this repo) | **1280×720** JPEG | `resources/fanart.jpg` — `build_kodi_screensaver_assets.py` currently prefers **live flock posters**; a custom hero is an operator override |
| GitHub README header | **1280×640** or 16:9 | optional; not required for sideload |

Keep a numbered source (`splash-screen-02.png`, `icon-03.png`) beside the unnumbered package files, matching the existing `-00` / `-01` convention.

**Safe area:** keep title glyphs and the mark’s bell inside the center ~80%. Roku splash can letterbox; do not put the only readable word on the extreme left/right edge.

**Palette:** match shipped splash `splash_color=#0a0a12` — near-black navy (`#0a0a12`), warm **amber / coral** flam3 heat, cool **cyan** for Jellyfin/LAN strands. Complementary living-room palettes are a furnace encode concern ([architecture](Pi5_Flam3_VoD_Pipeline.md)); the chrome can echo them without copying a specific sheep poster.

**Two packages, one household mark (recommended):** same square icon for VoD, Roku Dreams, and Kodi Dreams. Optional **hero variants** (below) so VoD feels like a player and Dreams feels like idle stills.

## Shared negatives (append to every prompt)

```text
No watermarks, no signatures, no stock-photo captions, no UI mockups with Settings text.
No official logos or wordmarks: Raspberry Pi, Roku, Jellyfin, Kodi, ffmpeg, Electric Sheep, Spotworks, Cesari sheep mascot, Netflix, YouTube.
No photoreal Raspberry Pi PCB dump, no barcode, no QR code, no GitHub octocat.
No farm sheep, no wool, no pasture-as-grass-field, no cute cartoon livestock.
No transcode progress bars, no HLS playlist glyphs, no datacenter aisle.
Readable at small size; avoid tiny filigree that turns to mud at 128 px.
```

## Set 1 — Hero / banner (16:9 splash + fanart + README)

**Use for:** Roku `splash-screen.png`, optional Kodi fanart, README header.

Copy the block into the generator. Then crop to 1280×720 (splash/fanart) or 1920×1080.

```text
Wide 16:9 cinematic hero for JellyFlam3, a household generative-media furnace.
Mood: modern, slightly dark, ambient living-room Direct Play — not a SaaS landing page.

Left third: a stylized Raspberry Pi–class furnace node (compact board + cooler, not a branded PCB photo). Soft neon amber and coral heat at the heatsink (“flam3” fire). Faint orbit rings suggest a fractal flame sheep looping, not a farm animal.

Center: the wordmark “JellyFlam3” in a clean geometric sans-serif, high contrast on deep navy. Optional smaller subtitle “furnace → pasture” underneath — never the filename “jellyflam3-server”.

Right third: abstract flam3 flame filaments resolving into a seamless loop of media frames (H.264 tiles as translucent glass, not a video-editor timeline). A dim TV bezel in the far right implies the pasture (Roku VoD / screensaver / Kodi idle). A simple remote silhouette is allowed; do not copy Roku’s trademark remote.

Background: #0a0a12 charcoal-navy with a very subtle square grid (Jellyfin catalog / LAN), not a HUD. Thin cyan traces connect furnace to pasture like a quiet homelab, not a city cyberpunk skyline.

Composition: dynamic but professional; suitable as a Roku channel splash and a GitHub README header. Rec.709-friendly contrast. No people, no watermarks.
```

### Optional variant — VoD (player)

Add: `Faint flock of mid-loop poster tiles in a RowList-like strip behind the flame, one tile enlarging into the loop. Feels like picking a sheep, then ambient playback. Still no real Roku UI screenshot.`

### Optional variant — Dreams (screensaver)

Add: `Quieter, stills-first: overlapping mid-loop posters as stained glass, slow crossfade implied, no remote in hand. Idle living room, gate-open furnace glow on the left. No Video transport bar.`

## Set 2 — Icon / logo mark (square badge)

**Use for:** Kodi `icon.png`; crop/pad to 290×218 for Roku `mm_icon_focus_hd.png` (keep the bell on the left or centered; do not clip tentacles into unreadability).

```text
Square app-icon / service mark for JellyFlam3 pasture clients (Roku channel tile and Kodi screensaver badge).

Central motif: a stylized jellyfish whose bell is a simplified furnace tower (one small SBC/heatsink block, rounded, not a 42U rack). Trailing tentacles morph into flam3 flame strands and streaming data threads with a few glowing dots (catalog packets / Direct Play frames). Playful and technical.

Color: bell and core in warm amber/red (jelly + flame). Tendrils in cool cyan under-glow (Jellyfin LAN). Background flat #0a0a12 or #1a1a1a, no texture, no vignette.

Style: flat-vector hybrid, minimal linework, generous negative space, instantly readable at 128×128 and at 256×256. No text, no letters, no “JF3” monogram unless it stays abstract.

Not the official Jellyfin jellyfish. Not the Electric Sheep Cesari mascot. Not a farm sheep. No watermarks.
```

## Post-production (crop before copy)

1. Pick one hero and one mark; discard extras that look like trademark mashups.
2. Splash / fanart source: crop 16:9 → **1280×720** PNG (JPEG for Kodi fanart). Keep `#0a0a12` in the letterbox if needed (`splash_color` already matches).
3. Roku Home icon: from the square mark, a **290×218** landscape badge (pad with `#0a0a12`, do not stretch). VoD and screensaver may share the pixels.
4. Kodi add-on icon: **256×256** PNG.

Do **not** drop generator filenames (`DALL·E 2026-….png`) into the client trees. Rename to the live names in the next section.

## Operator: swap into client trees

Work from a **clone of this repo** (Windows workstation or a furnace at `/opt/jellyflam3-server`). The sideload/add-on zips only ship the **unnumbered** live files. Numbered `*-00.png` / `*-01.png` stay in git as previous generations and are **excluded** from `package_roku_*` / `package_kodi_screensaver.*`. Do **not** add `*-02.png` under `images/` or `resources/` — packaging does not exclude `-02`, so it would ship as junk.

Assume cropped files are in `~/jf3-art/` (Linux/macOS) or `$HOME\jf3-art\` (Windows):

| Local crop | Live path (replaces previous) |
|---|---|
| `splash-1280x720.png` | `roku-channel/images/splash-screen.png` **and** `roku-screensaver/images/splash-screen.png` (or a Dreams variant) |
| `icon-290x218.png` | `roku-channel/images/mm_icon_focus_hd.png` **and** `roku-screensaver/images/mm_icon_focus_hd.png` |
| `icon-256.png` | `kodi-screensaver/screensaver.jellyflam3/resources/icon.png` |
| `hero-1280x720.jpg` (optional) | `kodi-screensaver/screensaver.jellyflam3/resources/fanart.jpg` — see [Kodi fanart](#kodi-fanart-vs-the-asset-builder) |

Manifests already point at those live names (`splash_screen_hd`, `mm_icon_focus_hd`, Kodi `<icon>` / `<fanart>`). Do not edit manifests for a pixel swap.

### 1 — Archive the outgoing live files

Rotate two generations in-tree: live → `-00`, old `-00` → `-01`. That overwrites the previous `-01` slot (copy off-tree first if you want a longer history).

**Linux / furnace / macOS** (repo root):

```bash
# VoD
cp roku-channel/images/splash-screen-00.png     roku-channel/images/splash-screen-01.png
cp roku-channel/images/splash-screen.png        roku-channel/images/splash-screen-00.png
cp roku-channel/images/mm_icon_focus_hd-00.png  roku-channel/images/mm_icon_focus_hd-01.png
cp roku-channel/images/mm_icon_focus_hd.png     roku-channel/images/mm_icon_focus_hd-00.png

# Roku Dreams (same rotation)
cp roku-screensaver/images/splash-screen-00.png     roku-screensaver/images/splash-screen-01.png
cp roku-screensaver/images/splash-screen.png        roku-screensaver/images/splash-screen-00.png
cp roku-screensaver/images/mm_icon_focus_hd-00.png  roku-screensaver/images/mm_icon_focus_hd-01.png
cp roku-screensaver/images/mm_icon_focus_hd.png     roku-screensaver/images/mm_icon_focus_hd-00.png

# Kodi (icon-00.png / icon-02.png may already exist — still rotate into -00)
cp kodi-screensaver/screensaver.jellyflam3/resources/icon-00.png \
   kodi-screensaver/screensaver.jellyflam3/resources/icon-01.png 2>/dev/null || true
cp kodi-screensaver/screensaver.jellyflam3/resources/icon.png \
   kodi-screensaver/screensaver.jellyflam3/resources/icon-00.png
```

**Windows PowerShell** (repo root):

```powershell
function Rotate-Live($live, $slot0, $slot1) {
  if (Test-Path $slot0) { Copy-Item $slot0 $slot1 -Force }
  Copy-Item $live $slot0 -Force
}
Rotate-Live roku-channel\images\splash-screen.png `
  roku-channel\images\splash-screen-00.png roku-channel\images\splash-screen-01.png
Rotate-Live roku-channel\images\mm_icon_focus_hd.png `
  roku-channel\images\mm_icon_focus_hd-00.png roku-channel\images\mm_icon_focus_hd-01.png
Rotate-Live roku-screensaver\images\splash-screen.png `
  roku-screensaver\images\splash-screen-00.png roku-screensaver\images\splash-screen-01.png
Rotate-Live roku-screensaver\images\mm_icon_focus_hd.png `
  roku-screensaver\images\mm_icon_focus_hd-00.png roku-screensaver\images\mm_icon_focus_hd-01.png
Rotate-Live kodi-screensaver\screensaver.jellyflam3\resources\icon.png `
  kodi-screensaver\screensaver.jellyflam3\resources\icon-00.png `
  kodi-screensaver\screensaver.jellyflam3\resources\icon-01.png
```

### 2 — Install the new live files

Overwrite **only** the unnumbered names:

```bash
cp ~/jf3-art/splash-1280x720.png  roku-channel/images/splash-screen.png
cp ~/jf3-art/icon-290x218.png     roku-channel/images/mm_icon_focus_hd.png
cp ~/jf3-art/splash-1280x720.png  roku-screensaver/images/splash-screen.png   # or Dreams variant
cp ~/jf3-art/icon-290x218.png     roku-screensaver/images/mm_icon_focus_hd.png
cp ~/jf3-art/icon-256.png         kodi-screensaver/screensaver.jellyflam3/resources/icon.png
```

```powershell
Copy-Item $HOME\jf3-art\splash-1280x720.png roku-channel\images\splash-screen.png -Force
Copy-Item $HOME\jf3-art\icon-290x218.png    roku-channel\images\mm_icon_focus_hd.png -Force
Copy-Item $HOME\jf3-art\splash-1280x720.png roku-screensaver\images\splash-screen.png -Force
Copy-Item $HOME\jf3-art\icon-290x218.png    roku-screensaver\images\mm_icon_focus_hd.png -Force
Copy-Item $HOME\jf3-art\icon-256.png        kodi-screensaver\screensaver.jellyflam3\resources\icon.png -Force
```

If art was generated on Windows but you **package on a furnace**, copy the live files (and the `-00`/`-01` archives if you rotated on Windows) onto the Pi, then package there:

```powershell
# Example furnace host. Do not scp secrets.env.
scp roku-channel/images/splash-screen*.png roku-channel/images/mm_icon_focus_hd*.png `
  jellyflam3@<RPi_IP_Address>:/opt/jellyflam3-server/roku-channel/images/
scp roku-screensaver/images/splash-screen*.png roku-screensaver/images/mm_icon_focus_hd*.png `
  jellyflam3@<RPi_IP_Address>:/opt/jellyflam3-server/roku-screensaver/images/
scp kodi-screensaver/screensaver.jellyflam3/resources/icon.png `
    kodi-screensaver/screensaver.jellyflam3/resources/icon-00.png `
    kodi-screensaver/screensaver.jellyflam3/resources/icon-01.png `
  jellyflam3@<RPi_IP_Address>:/opt/jellyflam3-server/kodi-screensaver/screensaver.jellyflam3/resources/
```

Confirm dimensions (optional): `file roku-channel/images/splash-screen.png` or open in an image editor. Wrong aspect still sideloads; Roku letterboxes.

### 3 — Kodi fanart vs the asset builder

`package_kodi_screensaver.*` always runs `scripts/build_kodi_screensaver_assets.py`, which **rewrites** `resources/fanart.jpg` and `screenshot-0{1,2,3}.jpg` from flock posters. A custom `fanart.jpg` in the tree is discarded at package time.

| Want | Do |
|---|---|
| Poster collage fanart (default) | Swap `icon.png` only; package as usual |
| Fanart from the new VoD splash | After packaging, run `python3 scripts/build_kodi_screensaver_assets.py --splash-fallback`, then copy `resources/fanart.jpg` into the zip (below) |
| Custom 1280×720 JPEG | After packaging, copy that JPEG into the zip as `screensaver.jellyflam3/resources/fanart.jpg` |

Replace fanart inside the finished zip (Linux):

```bash
unzip -o dist/screensaver.jellyflam3.zip -d dist/kodi-art-fix
cp kodi-screensaver/screensaver.jellyflam3/resources/fanart.jpg \
   dist/kodi-art-fix/screensaver.jellyflam3/resources/fanart.jpg
# or: cp ~/jf3-art/hero-1280x720.jpg dist/kodi-art-fix/screensaver.jellyflam3/resources/fanart.jpg
(cd dist/kodi-art-fix && zip -r -0 ../screensaver.jellyflam3.zip screensaver.jellyflam3)
```

PowerShell: expand the zip, `Copy-Item` onto `screensaver.jellyflam3\resources\fanart.jpg`, compress the folder back to `dist\screensaver.jellyflam3.zip` (store/no extra compression is fine for Kodi).

### 4 — Rebuild packages

Prefer a **furnace** so Jellyfin presets land in the zip ([USER_GUIDE](USER_GUIDE_AND_RUNBOOK.md#roku--kodi-packaging)):

```bash
cd /opt/jellyflam3-server
./scripts/package_roku_channel.sh          # dist/jellyflam3-roku.zip
./scripts/package_roku_screensaver.sh      # dist/jellyflam3-screensaver.zip
./scripts/package_kodi_screensaver.sh      # dist/screensaver.jellyflam3.zip
```

Windows (no furnace presets — paste Settings on device):

```powershell
.\scripts\package_roku_channel.ps1
.\scripts\package_roku_screensaver.ps1
.\scripts\package_kodi_screensaver.ps1
```

Do not commit `registry/jellyflam3-presets.json` or a filled Kodi `settings.xml`. Committing the **PNG/JPEG chrome** is optional; household-only art can stay untracked.

### 5 — Install on pasture devices

| Client | How the new art appears |
|---|---|
| **Roku VoD** | Developer installer → upload `dist/jellyflam3-roku.zip` (replaces the sideload slot). Splash shows on launch; Home tile uses `mm_icon_focus_hd`. If the tile is stale, remove the sideloaded channel and upload again. Private-channel `.pkg` must be **re-packaged on a Roku** ([phase4/04](phase4/04_ROKU_PUBLISH.md#private-channel-path-wave-2)) — a zip swap does not update an already-published private channel. |
| **Roku Dreams** | Sideload `dist/jellyflam3-screensaver.zip` (replaces VoD in the developer slot unless VoD is a private channel). Theme → Screensavers still points at JellyFlam3 Dreams. |
| **Kodi Dreams** | Copy zip to the Kodi box → Add-ons → Install from zip (overwrite). Icon/fanart refresh in the add-on browser; if Kodi caches art, disable/re-enable the add-on or reboot LibreELEC. |

Roku holds **one** sideload at a time. Do not sideload SS over household VoD unless Owner asked.

### 6 — Rollback

Copy `-00` (previous live) back over the unnumbered name, package, sideload/install again:

```bash
cp roku-channel/images/splash-screen-00.png roku-channel/images/splash-screen.png
cp roku-channel/images/mm_icon_focus_hd-00.png roku-channel/images/mm_icon_focus_hd.png
# same for roku-screensaver/ and Kodi icon-00.png → icon.png
```

**License of the pixels:** you (or the generator’s terms) own the result. The repo does not treat AI chrome as Free Sheep CC. Do not imply affiliation with Spotworks or Jellyfin.

## See also

[phase4/04](phase4/04_ROKU_PUBLISH.md) (Store brand work item) · [phase1/08](phase1/08_ROKU_BRIGHTSCRIPT.md) · [kodi-screensaver/README.md](../kodi-screensaver/README.md) · [roku-channel/README.md](../roku-channel/README.md) · [roku-screensaver/README.md](../roku-screensaver/README.md) · [NOTICE](../NOTICE)
