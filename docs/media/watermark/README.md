# Tuple edge watermark assets

Default encode overlay is **`Electric-Sheep-Icon-7A8B99.png`**. Look and timing: [docs/phase4/03_EDGES_AND_WATERMARK.md](../../phase4/03_EDGES_AND_WATERMARK.md#look-and-feel-what-the-viewer-sees).

| File | Role |
|---|---|
| `Electric-Sheep-Icon-7A8B99.png` | **Shipped default** — 180×180 RGBA; white sheep, `#7A8B99` spiral; transparent padding |
| `Electric-Sheep-Icon.png` | Source 1024×1024 (too large to overlay without scale; keep as art) |
| `Electric-Sheep-Logo.svg` | Wordmark lockup (ffmpeg on the Pis does not decode SVG) |

Do not point `watermark.image` at the 1024 icon or the SVG.
