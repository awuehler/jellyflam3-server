# Tuple edge watermark assets

Look and timing: [docs/phase4/03_EDGES_AND_WATERMARK.md](../../phase4/03_EDGES_AND_WATERMARK.md#look-and-feel-what-the-viewer-sees).

## Private mixed vs commercial-safe / public

This is the encode boundary until Spotworks, Scott Draves, or Laura Cesari say otherwise. It is **not** the CC-vs-NC genome tag split (that was the inverted rule). Knob: `license.commercial_mode`.

| Flock | `license.commercial_mode` | Edge-stage mark |
|---|---|---|
| **Private mixed** (default household: BY + BY-NC) | `false` | Cesari PNG (`Electric-Sheep-Icon-7A8B99.png`) when `watermark.style: image`, **or** an operator PNG. Missing PNG or `style: text` → short `Electric Sheep` drawtext. |
| **Commercial-safe / public** (venue, CC-only, Channel Store, published) | `true` | **Never** the Cesari logo. Operator PNG still overlays. Otherwise **“artwork by Scott Draves and the Electric Sheep”**. |

Sidecars record the **effective** style (`text` on commercial-safe furnaces when the image is still a Cesari file). Already-catalogued tuples keep whatever was burned in until they are re-rendered.

### Operator PNG (both flocks)

Point `watermark.image` at **your own** RGBA PNG (not `Electric-Sheep-Icon*` / `Electric-Sheep-Logo*`). ffmpeg overlays it at native size — about **180×180** with transparent padding matches the default sheepcloud; 1024-class files are too large. Absolute path is best (`/var/lib/jellyflam3/watermark.png`). Repo-relative paths resolve from the git tree. `*.png` is gitignored outside `docs/**`, so a file under `configs/` will not be committed. Restart `jellyflam3-worker` and re-furnace tuples. You must have rights to that art; do not drop a third-party trademark in as a substitute. Copying the Cesari file to `watermark.png` still burns the mascot (the public skip keys off the Cesari **filename**).

Do not point `watermark.image` at the 1024 Cesari icon or the SVG.

| File | Role |
|---|---|
| `Electric-Sheep-Icon-7A8B99.png` | Private-mixed default — 180×180 RGBA; white sheep, `#7A8B99` spiral; transparent padding |
| `Electric-Sheep-Icon.png` | Source 1024×1024 (too large to overlay without scale; keep as art) |
| `Electric-Sheep-Logo.svg` | Wordmark lockup (ffmpeg on the Pis does not decode SVG) |

## Addendum — license, trademark, fair use

Not legal advice. Project genome policy: [docs/phase1/07_LICENSE_AND_METADATA.md](../../phase1/07_LICENSE_AND_METADATA.md). ES reuse text: [electricsheep.org/license](https://electricsheep.org/license/).

**Bottom line:** Tuple **content** (Free Sheep A/B + flam3 `sequence=`) is still within this repo’s Electric Sheep guidelines. The **Cesari-style logo overlay is the piece that is not clearly covered** by those guidelines. **Encode policy (trademark-safer, pending correspondence):** **private mixed** flocks may overlay the Cesari PNG. **Commercial-safe / public** flocks **never** burn that mascot (ES attribution sentence instead). An **operator-owned PNG** in `watermark.image` overlays on **both** flocks. Treat the Cesari files as **provisional** until Spotworks, Scott Draves, or Laura Cesari say otherwise (`info@spotworks.com`). Do not use them on a Channel Store or other public build.

### Provenance (Laura Cesari)

Scott Draves commissioned **Laura Cesari** (aka Caballera) in 2008 for a new Electric Sheep mascot and logo as v2.7 went “pro.” She is a sheep designer; Draves hired her for traditional graphic design after seeing a Firefox theme that used a sheep throbber. The line-art SVG and the silhouette we overlay descend from that commission — not from a Free Sheep genome. See [spot blog: New Electric Sheep Mascot and Logo](https://draves.org/blog/archives/000607) (6 Nov 2008).

Creative Commons on Free Sheep **animations and parameters** does **not** license that mascot. Recoloring the spiral to `#7A8B99`, committing the PNG in this MIT tree, and burning it into catalog MP4s is using **Spotworks / Electric Sheep brand identity**, not remixing a sheep.

### What ES asks for vs what we burn in

| ES reuse recipe | This watermark |
|---|---|
| Credit **“artwork by Scott Draves and the Electric Sheep”** | **Commercial-safe / public** when the image is still Cesari (or `style: text`). **Private mixed** uses Cesari PNG or short `Electric Sheep`. Operator PNG replaces both. |
| Web: legible text + link to electricsheep.org | No on-screen electricsheep.org link (Scott Draves is named on the public path) |
| Corner watermark OK for TV/wall as **attribution** | Edge-only, 45% opacity, ~13 s of ~39 s |
| Redistributed files: `electricsheep.{gen}.{id}` | Tuples: `electricsheep.tuple.{from}_to_{to}` (parent IDs present; not the archive form) |

Nominative fair use covers **naming** Electric Sheep in docs; it is a weak fit for a **source-identifying mark on our own product**. The Roku channel is still named JellyFlam3. The Cesari sheepcloud is **private mixed flock only** until permission; the **commercial-safe / public** path uses their written credit string unless you set an operator PNG.

### Practical heat

| Context | Genome CC | Logo / wordmark |
|---|---|---|
| **Private mixed** flock, Opt-Out (`commercial_mode: false`) | Consistent with existing policy | Cesari PNG allowed (provisional household use) |
| Peering / packing files for others | Filenames + sidecar help; tuple names are imperfect | Distributing the PNG in git is extra |
| **Commercial-safe / public** (`commercial_mode: true`) / Channel Store | NC still filtered | **No Cesari logo** — operator PNG still overlays; else ES attribution sentence; leftover Cesari-marked files remain the hot case if they leak onto this path |

Gold Sheep / HiFi / paid masters stay out of the furnace. Household / private viewing of Free Sheep remains the lane ES describes as free with attribution.
