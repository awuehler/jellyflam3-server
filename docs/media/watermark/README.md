# Tuple edge watermark assets

Default encode overlay is **`Electric-Sheep-Icon-7A8B99.png`**. Look and timing: [docs/phase4/03_EDGES_AND_WATERMARK.md](../../phase4/03_EDGES_AND_WATERMARK.md#look-and-feel-what-the-viewer-sees).

| File | Role |
|---|---|
| `Electric-Sheep-Icon-7A8B99.png` | **Shipped default** — 180×180 RGBA; white sheep, `#7A8B99` spiral; transparent padding |
| `Electric-Sheep-Icon.png` | Source 1024×1024 (too large to overlay without scale; keep as art) |
| `Electric-Sheep-Logo.svg` | Wordmark lockup (ffmpeg on the Pis does not decode SVG) |

Do not point `watermark.image` at the 1024 icon or the SVG.

## Addendum — license, trademark, fair use

Not legal advice. Project genome policy: [docs/phase1/07_LICENSE_AND_METADATA.md](../../phase1/07_LICENSE_AND_METADATA.md). ES reuse text: [electricsheep.org/license](https://electricsheep.org/license/).

**Bottom line:** Tuple **content** (Free Sheep A/B + flam3 `sequence=`) is still within this repo’s Electric Sheep guidelines. The **default Cesari-style logo overlay is the piece that is not clearly covered** by those guidelines. Safer if you want a tight match: keep the edge mark, but use **original JellyFlam3 art**, or the **full attribution sentence** (“artwork by Scott Draves and the Electric Sheep”), and keep electricsheep.org / Scott Draves in the sidecar or Overview. Treat the current PNG as **provisional** until Spotworks says otherwise (`info@spotworks.com`), especially before any public or Channel Store build.

### Provenance (Laura Cesari)

Scott Draves commissioned **Laura Cesari** (aka Caballera) in 2008 for a new Electric Sheep mascot and logo as v2.7 went “pro.” She is a sheep designer; Draves hired her for traditional graphic design after seeing a Firefox theme that used a sheep throbber. The line-art SVG and the silhouette we overlay descend from that commission — not from a Free Sheep genome. See [spot blog: New Electric Sheep Mascot and Logo](https://draves.org/blog/archives/000607) (6 Nov 2008).

Creative Commons on Free Sheep **animations and parameters** does **not** license that mascot. Recoloring the spiral to `#7A8B99`, committing the PNG in this MIT tree, and burning it into catalog MP4s is using **Spotworks / Electric Sheep brand identity**, not remixing a sheep.

### What ES asks for vs what we burn in

| ES reuse recipe | This watermark |
|---|---|
| Credit **“artwork by Scott Draves and the Electric Sheep”** | Logo bug, or the words `Electric Sheep` only |
| Web: legible text + link to electricsheep.org | No on-screen Scott Draves or electricsheep.org |
| Corner watermark OK for TV/wall as **attribution** | Edge-only, 45% opacity, ~13 s of ~39 s |
| Redistributed files: `electricsheep.{gen}.{id}` | Tuples: `electricsheep.tuple.{from}_to_{to}` (parent IDs present; not the archive form) |

A corner mark is closer to their **attribution method** than a title card, but the prescribed **credit string** is missing. Nominative fair use covers **naming** Electric Sheep in docs; it is a weak fit for a **source-identifying mark on our own product**. The Roku channel is still named JellyFlam3, which helps; an official-looking sheep bug on the morph can still read as official Electric Sheep.

### Practical heat

| Context | Genome CC | Logo / wordmark |
|---|---|---|
| Private house flock, Opt-Out | Consistent with existing policy | Low practical heat; still not the credit string they asked for |
| Peering / packing files for others | Filenames + sidecar help; tuple names are imperfect | Distributing the PNG in git is extra |
| Venue / `commercial_mode` / Channel Store | NC still filtered if you turn that on | Logo on a published channel is the hot case |

Gold Sheep / HiFi / paid masters stay out of the furnace. Household / private viewing of Free Sheep remains the lane ES describes as free with attribution.
