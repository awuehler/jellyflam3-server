# Phase 5 overview

## Boundary

Phase 5 is a **parked slice** with **two deployments**. They are **not interchangeable** and **must not overlap** on one host.

| | **A — JellyFlam3 Furnace** | **B — LLM Agent Platform** |
|---|---|---|
| **What it is** | The sheep factory: render, encode, catalog, stream | The on-device model host: advise names, breed briefs, operator agents |
| **Hardware** | Raspberry Pi 5 (`16a` / `08a` / `04a`) | Arduino **Ventuno Q** |
| **OS** | Raspberry Pi OS 64-bit | Ubuntu aarch64 (vendor image) |
| **Runs** | `flam3-animate`, `ffmpeg`, Jellyfin, `jellyflam3-worker`, idle-gate | Local LLM / VLM runtime + agent adapters |
| **Does not run** | Local LLM / VLM / NPU inference as a product role | Worker, flam3, Jellyfin-as-flock-server, `/media/sheep` as catalog SoT |
| **SoT** | Catalog MP4 + `{stem}.jellyflam3.json` on the furnace | None for flock metadata — writes **through** furnace contracts |
| **Playbook** | [phase2/09](../phase2/09_PI_FROM_SCRATCH.md) (already shipped) | [01](01_VENTUNO_Q_HOST.md) (this slice) |

**Status:** Synopsis only (2026-09-10). Do **not** buy-for-fleet, install models on a furnace Pi, install the worker on a Ventuno, or call cloud/local model APIs from `jellyflam3-worker` until Owner opens this slice.

Architecture SoT remains [Pi5_Flam3_VoD_Pipeline.md](../Pi5_Flam3_VoD_Pipeline.md). The Pi 5 fleet is the **only** supported furnace. Ventuno Q is **not** a 16-class furnace and **not** a Pi replacement.

```text
  Pasture (Roku / Kodi)
        ▲  Direct Play / remux
        │
  A  JellyFlam3 Furnace (Pi 5)
        │  LAN: posters, sidecars, SSH/CLI, optional agent HTTP
        ▼
  B  LLM Agent Platform (Ventuno Q)
        │  proposes alias / breed brief / ops text
        ▼
  A  applies (sidecar, pipeline.breed, Shears confirm) — still the factory
```

## Status

| Item | State |
|---|---|
| Phase 5 products | **Parked** (2026-09-10) — docs only |
| A — Furnace | **Shipped** on Pi — not re-specified here; see [phase2/09](../phase2/09_PI_FROM_SCRATCH.md) |
| B — LLM Agent Platform host | Parked — [01](01_VENTUNO_Q_HOST.md) (Ventuno BOM + INT4 model store, bring-up, **non-furnace**) |
| Agent ↔ furnace contracts | Parked — [02](02_LLM_INTEGRATION.md) (naming, breeding; vision pipeline; **VoD-as-camera**) |
| Agent-platform gaps | Parked — [03](03_AI_PLATFORM_GAPS.md) |
| Phase 4 products | Unchanged — [../phase4/00_OVERVIEW.md](../phase4/00_OVERVIEW.md) |

## Goal

Stand up **deployment B** next to an existing **deployment A**, so that:

1. The **furnace** keeps rendering **Gold Sheep Lite** exactly as today (16/08/04 overlays, `libx264`, Jellyfin, idle-gate).
2. The **agent platform** hosts a **local, opt-in** stack: **one** hot 7–8B Instruct INT4 on Hexagon, plus a **small** VLM (2B–3B INT4) on Adreno. Vision path is **pixels → caption text → Instruct JSON** ([02](02_LLM_INTEGRATION.md#vision-pipeline)). Frame source is **Jellyfin VoD as a virtual camera** (Images snapshot; optional Static Direct Play peek; follow pasture NowPlaying) — not MIPI CSI and not catalog files on B ([02](02_LLM_INTEGRATION.md#vod-as-camera)). Switch Instruct graphs with service stop → config → start. No chat SLA. It **advises**; the furnace **does**.
3. Writes use existing contracts only: catalog sidecar (`alias` / `alias_source=llm`), `pipeline.breed` / idle-breed **on the furnace**, Shears / refactor CLIs **on the furnace**, operator-facing briefs.
4. Defaults **offline** on B. Cloud model calls are a config kill-switch, never the MVP path.
5. **No colocation:** a host is furnace **or** agent platform, never both.

This is the deferred **LLM-assisted pedigree** note from [phase2/07](../phase2/07_PEDIGREE_BREEDING.md) and [phase3/00](../phase3/00_OVERVIEW.md), plus [phase4/09](../phase4/09_SHEEP_NAMING.md) work item **D** (LLM poster naming), on silicon that can run the models **without** sharing a board with `flam3-animate`.

## Reading order

| # | Guide | Focus |
|---|---|---|
| 00 | This file | Two-deployment split / parked DoD |
| 01 | [01_VENTUNO_Q_HOST.md](01_VENTUNO_Q_HOST.md) | Deployment B BOM, power/disks, bring-up — **not** a furnace port |
| 02 | [02_LLM_INTEGRATION.md](02_LLM_INTEGRATION.md) | Agent → furnace map; **vision pipeline**; **VoD-as-camera** |
| 03 | [03_AI_PLATFORM_GAPS.md](03_AI_PLATFORM_GAPS.md) | NPU / RAM / thermal / driver / eval / **Hexagon+GPU** gaps **on B** |

Execute **01 before 02**. Guide 03 is the honesty check for the agent platform. There is no Phase 5 acceptance guide until Owner opens implementation. Do **not** start from [phase2/09](../phase2/09_PI_FROM_SCRATCH.md) expecting to land models on the Pi.

## Locked decisions (design)

1. **Two hosts, two roles.** Furnace = Pi 5 + [phase2/09](../phase2/09_PI_FROM_SCRATCH.md). Agent platform = Ventuno Q + [01](01_VENTUNO_Q_HOST.md). No `ventuno-jellyflam3-16` hw overlay. No LLM runtime as a furnace systemd unit.
2. **Not interchangeable.** A Ventuno does not become a 16a by installing flam3. A Pi 16a does not become an agent platform by installing llama.cpp. Pasture clients talk to **furnace Jellyfin**, never to the Ventuno.
3. **Not overlapping.** Do not install `jellyflam3-worker`, idle-gate, Jellyfin Sheep library, or `/media/sheep` catalog mounts on the Ventuno. Do not run Hexagon/LLM inference as a product service on the Pi.
4. **Sidecar SoT stays on the furnace.** LLM output is applied **on A** (`{stem}.jellyflam3.json`, breed/Shears). B may keep prompt logs; those are not flock SoT ([phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema)).
5. **Human override sticky.** `alias_source=human` wins over `llm` and `auto` ([phase4/09](../phase4/09_SHEEP_NAMING.md)).
6. **License / NC unchanged.** Model suggestions cannot flip Creative Commons or commercial-safe policy ([phase1/07](../phase1/07_LICENSE_AND_METADATA.md), [phase2/07](../phase2/07_PEDIGREE_BREEDING.md)).
7. **Phase 4 products stay on Phase 4.** Vote overlay, auto-promote, pasture filename/alias toggle, library rotate are **not** pulled into this slice.
8. **16-class quality is a furnace concern only.** Agent-platform sizing does not change `quality` / supersample / VoD bands on A.
9. **One hot 7–8B INT4 Instruct.** Do not co-resident two 7B Instruct graphs in 16 GB. Store Llama 3.1 8B / Qwen2.5 7B / Mistral 7B (all INT4) on NVMe; load **one** per session. INT16/FP16 7–8B is out of RAM budget.
10. **Vision pipeline, small VLM co-resident.** Posters/stills: **pixels → text → Instruct JSON**. A 2B–3B INT4 VLM (Adreno) may stay loaded **in parallel** with the hot Instruct (Hexagon) as two sessions. Do **not** feed pixels into the 7B, and do **not** run a 7B VLM beside a 7B Instruct. Per sheep the stages are sequential; the graphs stay resident. See [02](02_LLM_INTEGRATION.md#vision-pipeline).
11. **VoD is the camera, not MIPI.** B samples furnace Jellyfin as a remote sensor for **single-sheep** loops only (Images API; optional `stream.mp4?Static=true` frame grab; follow TV `NowPlayingItem` when that item is one loop). Spectra 692 stays unused. B must **not** look like a TV client (idle-gate), must **not** force transcode, must **not** mount `/media/sheep`. Dynamic sampling is for follow-up tasks after naming MVP. See [02](02_LLM_INTEGRATION.md#vod-as-camera).

## In scope (when opened)

1. [01_VENTUNO_Q_HOST.md](01_VENTUNO_Q_HOST.md) — Ubuntu agent-platform bring-up (models + LAN to furnace). Explicit **non-install** of the furnace stack.
2. [02_LLM_INTEGRATION.md](02_LLM_INTEGRATION.md) — adapters that call **furnace** CLIs/APIs; default off.
3. [03_AI_PLATFORM_GAPS.md](03_AI_PLATFORM_GAPS.md) — keep the gap list honest as silicon/drivers land on **B**.

## Out of scope

- Using Ventuno Q as a JellyFlam3 furnace (no 16a port, no `smoke_render` DoD on B)
- Using a furnace Pi as the LLM/VLM host
- Running flam3 (or a “neural flame”) on the Hexagon NPU
- DeepDream / alternate render backends as a second furnace language
- Arduino App Lab as a required operator UI (allowed as a bench tool on **B**; furnace CLI stays canonical on **A**)
- Cloud-only naming or breeding
- Colocating A and B “to save a board”
- Using MIPI/USB cameras as the naming/VoD sample path (ISP toys only; sensor is furnace Jellyfin)
- Tuple (loop+edge+loop) VoD as a VLM camera target — single-sheep loops only

## Prerequisites

- Phase 3 complete ([../phase3/00_OVERVIEW.md](../phase3/00_OVERVIEW.md))
- At least one live **furnace** (16a class preferred) per [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md)
- RNG aliases shipped so `alias` / `alias_source` are real sidecar fields ([../phase4/09_SHEEP_NAMING.md](../phase4/09_SHEEP_NAMING.md))
- Owner waiver to open this slice **without** waiting for remaining Phase 4 products

## Definition of done (when opened)

Phase 5 is complete for a first RC when:

- [ ] One **furnace** (Pi) still satisfies existing 16/08/04 healthcheck; no LLM units added there
- [ ] One **agent platform** (Ventuno) boots Ubuntu, loads a local model, and reaches the furnace on LAN
- [ ] Worker / flam3 / Jellyfin Sheep are **absent** on the Ventuno (`bringup` check fails closed if they appear)
- [ ] Agent can propose an alias that the **furnace** writes as `alias_source=llm` without overwriting `human`
- [ ] Breed brief schema → **furnace** `pipeline.breed`; tax + NC still hold; flam3-genome remains the mutator
- [ ] One hot INT4 7–8B; session switch (stop → `model_id` → start) labbed; two 7Bs not co-resident
- [ ] Vision pipeline labbed: small GPU VLM caption → hot Instruct JSON; RSS with both resident stays under ~14 GB
- [ ] VoD-as-camera: Images snapshot of a **single sheep** does not close idle-gate; optional Static peek + NowPlaying follow documented; no Playing POST from B
- [ ] Gap list in [03](03_AI_PLATFORM_GAPS.md) triaged (accept / fix / defer)
- [ ] Docs + glossary; no secrets in-repo

## See also

[01_VENTUNO_Q_HOST.md](01_VENTUNO_Q_HOST.md) · [02_LLM_INTEGRATION.md](02_LLM_INTEGRATION.md) · [03_AI_PLATFORM_GAPS.md](03_AI_PLATFORM_GAPS.md) · [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md) · [../phase4/09_SHEEP_NAMING.md](../phase4/09_SHEEP_NAMING.md) · [../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md) · [../phase4/00_OVERVIEW.md](../phase4/00_OVERVIEW.md)
