# 01 — LLM Agent Platform host (Arduino Ventuno Q)

## Boundary

Hardware, OS, storage, power, and **bring-up** for **deployment B**: an **Arduino Ventuno Q** that runs **only** the LLM Agent Platform. Stop before furnace integration adapters ([02](02_LLM_INTEGRATION.md)).

**This is not a furnace port.** Do not map 16a disk roles, do not apply `rpi-jellyflam3-16`, do not install `flam3-animate` / Jellyfin / `jellyflam3-worker` here. The JellyFlam3 Furnace (**deployment A**) stays on a Raspberry Pi 5 — [phase2/09](../phase2/09_PI_FROM_SCRATCH.md).

**Status:** Parked. Do not treat Ventuno Q as a supported **furnace** or as a required lab box until Owner opens Phase 5.

Depends on a reachable furnace (SSH, Jellyfin URL, catalog posters) and on [00](00_OVERVIEW.md) split rules.

## Intent

Ventuno Q is Arduino’s Linux SBC. Phase 5 uses that silicon as an **agent platform**: local LLM/VLM inference that **talks to** a Pi furnace over the LAN. Workload is **agentic API** (batch briefs, no interactive-chat SLA). Posters/stills use a **small GPU VLM** plus the **hot Hexagon Instruct** graph ([02](02_LLM_INTEGRATION.md#vision-pipeline)).

### Silicon (vendor sheet — verify before purchase)

| Block | Spec |
|---|---|
| MPU | Qualcomm Dragonwing **IQ8 (IQ-8275)** |
| CPU | 8-core Qualcomm Kryo |
| GPU | Qualcomm Adreno 623 — home for the **small VLM** (poster/still pixels); LLM fallback if HTP fails. Two sessions (GPU VLM + HTP Instruct), not one QNN graph ([03](03_AI_PLATFORM_GAPS.md#g18--hexagon--adreno-during-one-llm-runtime-investigation)) |
| NPU | Qualcomm Hexagon, **40 dense TOPS** |
| ISP | Qualcomm Spectra 692 — **unused for VoD sampling**; CSI is not a Jellyfin terminator ([02](02_LLM_INTEGRATION.md#vod-as-camera)) |
| MCU | STM32H5F5 (Cortex-M33 @ 250 MHz, 4 MB flash, 1.5 MB RAM) — Zephyr / Arduino core; unused in MVP |
| RAM | **16 GB LPDDR5** |
| On-board storage | **64 GB eMMC** (OS only) |
| Expansion | M.2 **NVMe Gen 4** |
| OS (MPU) | Ubuntu or Debian upstream |
| LAN | Wi-Fi 6 (2.4/5/6 GHz), BT 5.3, **1× 2.5 GbE** RJ45 |
| Video | HDMI (muxed with MIPI DSI on JMEDIA); USB-C DP Alt Mode |
| USB | 1× USB-C (host/device + video); 2× USB 3 Type-A; 2× USB 3 on JOMEGA |
| Power | USB-C 5 V / 3 A (**15 W — not for inference**); **5.5×2.1 mm jack 12–24 V**; screw terminal 7–24 V; 7–24 V on JOMEGA |
| Board | ~160 × 100 × 25.8 mm |

Qualcomm AI Hub / QNN / LiteRT is the expected compile path (not `pip install transformers` of an arbitrary Hub checkpoint). 16 GB makes **one** 7–8B **INT4** Instruct graph comfortable, with headroom for a **2B–3B INT4 VLM** on Adreno. Two 7B INT4 graphs co-resident is OOM-fragile ([03](03_AI_PLATFORM_GAPS.md) G2).

| Concern | A — Furnace (Pi 5) | B — Agent platform (Ventuno Q) |
|---|---|---|
| Role | Render + Jellyfin + worker | Local LLM / VLM + agent daemons |
| Hostname (proposed) | `rpi-jellyflam3-16a` (existing) | `ventuno-jellyflam3-agent` (letter suffix `a`,`b`,… if several) |
| RAM | 4 / 8 / 16 GB per class | 16 GB LPDDR5 — models, not PNG dumps |
| OS disk | microSD | 64 GB eMMC |
| Fast disk | 1 TB NVMe scratch + state | NVMe for **model weights** + agent logs (not flam3 frames) |
| Flock disk | 1 TB USB → `/media/sheep` | **None** — read posters from furnace / Jellyfin |
| LAN | Lab often WiFi STA | Prefer **2.5 GbE** to the furnace |
| Power | 5 V / 5 A USB-C | **12–24 V** barrel / screw terminal — not USB-C 15 W |
| Overlay | `rpi-jellyflam3-{16,08,04}` | **No** furnace hw_profile |
| Extra silicon | — | NPU is the point of B; MCU unused in MVP |

**Do not** pin flam3 to A78s on this board — flam3 is not installed.

## Estimated BOM (USD, 2026-09 — order of magnitude)

Prices move. Treat as **planning**, not a purchase order.

### A — Furnace (not purchased in this guide)

Use [phase2/09](../phase2/09_PI_FROM_SCRATCH.md): Pi 5 + cooler + HAT + 1 TB NVMe + 1 TB USB SSD + 35 W PSU. 16 GB class is roughly **$550–$800**. Phase 5 **requires** at least one such host already in service.

### B — LLM Agent Platform (this guide)

| # | Item | Qty | Est. USD | Notes |
|---|---|---:|---:|---|
| 1 | **Arduino Ventuno Q** | 1 | **300–350** | Store intro ~€299 (VAT incl.); IQ8 + STM32H5; 16 GB; 64 GB eMMC |
| 2 | **12–24 V PSU** (60–90 W class) | 1 | 25–45 | Barrel 5.5×2.1 mm or screw terminal. **Do not** run inference on USB-C 5 V / 3 A (15 W) |
| 3 | **NVMe SSD 1 TB** (M.2) | 1 | 70–110 | **Model store** (see storage math). Not `/var/cache/jellyflam3/frames` |
| 4 | **Active cooling** | 1 | 20–50 | SoC + NPU + NVMe; no official Pi-style cooler playbook |
| 5 | **Case / stand + standoffs** | 1 | 20–40 | Board ~160×100 mm; keep airflow |
| 6 | **Cat6 patch** | 1 | 5–10 | 2.5 GbE to the LAN / furnace |

**Agent-platform subtotal (required): ~$440–$605.** Board ~$300; the rest is PSU + cooler + NVMe so INT4 graphs actually load. No USB sheep disk. Do not reuse the 16a USB SSD on B.

### LLM storage math (why NVMe, not eMMC)

eMMC (64 GB) is Ubuntu + apt only. Weights and QNN/LiteRT compile scratch live on **NVMe**. Planning figures for **one hot Instruct** (Hexagon), **three cold Instruct copies** on disk (session switch — [02](02_LLM_INTEGRATION.md#model-session-switch)), and **one small VLM** co-resident on Adreno ([02](02_LLM_INTEGRATION.md#vision-pipeline)):

| Asset | On disk (order of magnitude) | In RAM when hot |
|---|---|---|
| Llama 3.1 8B Instruct **INT4** | ~4–5 GB compiled | ~4–5 GB weights + 1–2 GB KV @ 8K ≈ **6–7 GB** |
| Qwen2.5 7B Instruct **INT4** | ~4–5 GB | same class ≈ **6 GB** |
| Mistral 7B Instruct **INT4** | ~4–5 GB | same class ≈ **6 GB** |
| Three Instruct INT4 graphs stored | **~15 GB** | **one** of them + KV on Hexagon |
| Small VLM **INT4** (2B–3B class, e.g. Qwen2-VL / captioner) | ~1.5–3 GB | ~2–4 GB on **Adreno** when co-resident |
| Ubuntu + agent runtime + I/O | — | **~2–3 GB** |
| Target resident (hot 7B + small VLM + OS) | — | **~11–14 GB** of 16 GB — lab RSS before unattended |
| QNN / LiteRT export + quantize scratch | **20–40 GB** during a convert | not resident |
| Prompt / eval logs | grow; cap like furnace log hygiene | — |

**Do not** plan INT16/FP16 7–8B (~14–16 GB weights alone) — OS + KV will OOM. **Do not** keep two 7B INT4 graphs + both KV caches resident (~12–13 GB + OS ≈ 14–16 GB), including a **7B VLM** beside the Instruct 7B. Homelab **1 TB** NVMe is the “don’t think about it” size (three Instruct graphs, one small VLM, convert workspace, logs). Floor if buying smaller: **≥128 GB** usable NVMe; 64 GB eMMC is not the model store.

### Nice-to-have / lab

| Item | Est. USD | Notes |
|---|---|---|
| Spare NVMe | 70–110 | Model-store clone |
| HDMI / USB-C DP + keyboard | 15–30 | First-boot; headless after SSH |
| USB-C cable | 10 | Recovery only — not primary power |

### Not in this BOM

| Item | Role |
|---|---|
| Pi 5 furnace stack | **Deployment A** — buy/run via guide 09 |
| 1 TB USB flock SSD on Ventuno | Furnace-only |
| Roku / Kodi pasture | Point at **furnace** Jellyfin, not B |
| MIPI cameras | Out of naming/VoD sample path; optional bench toys only |
| USB camera | Closer analog to HTTP decode than MIPI; still not the product sensor |
| Hailo / USB NPU | On-board Hexagon is the NPU |
| Second Ventuno “as 16a” | Out of scope — B is not a furnace |

Official product refs (vendor; verify before purchase): [Arduino VENTUNO Q](https://www.arduino.cc/product-ventuno-q) · store listing ~€298.99 intro.

## Disk and power mapping

| Mount (B) | Disk | Contents |
|---|---|---|
| `/` | 64 GB eMMC | Ubuntu + apt; **not** flock |
| `/var/lib/jellyflam3-agent` (name TBD) | 1 TB NVMe | `models/` (three Instruct INT4 + one small VLM) + `scratch/convert/` + agent config + prompt logs |
| `/media/sheep` | **must not exist as catalog SoT** | If an operator plugs a disk here by habit, bring-up **fails** |

Furnace mounts (`/media/sheep`, `/var/cache/jellyflam3`, bind `/var/lib/jellyflam3`) stay **only on A**. Agent samples pixels via Jellyfin as a **virtual camera** (Images API; optional Static Direct Play grab) — [02](02_LLM_INTEGRATION.md#vod-as-camera). Never open catalog MP4s from a flock mount on B.

**Power (B):** 12–24 V. Sustained NPU inference is not a 15 W USB-C workload. Confirm draw on the first lab unit.

## Bring-up / “porting” tasks

These are **agent-platform** tasks, not a port of the Pi furnace playbook. Each row is work for when Owner opens 01.

### A — Identity (B only)

| # | Task | Touches | Notes |
|---|---|---|---|
| A1 | Hostname `ventuno-jellyflam3-agent` (letter suffix if multiple) | `/etc/hosts` | **Not** `rpi-jellyflam3-16a` |
| A2 | Dedicated user (e.g. `jf3agent`) — **not** a substitute for furnace user `jellyflam3` on A | accounts | Do not share `secrets.env` copies blindly |
| A3 | **No** `pipeline.hw_profile apply 16a` on this host | — | Furnace overlays stay on Pi |

### B — OS and runtime (B only)

| # | Task | Touches | Notes |
|---|---|---|---|
| B1 | Ubuntu 64-bit; SSH keys; NTP | operator | Vendor image |
| B2 | Local model runtime (llama.cpp **or** GenieX / AI Hub — choose in [03](03_AI_PLATFORM_GAPS.md)) | packages | Headless; App Lab optional |
| B3 | systemd unit for the agent (name TBD) — **must not** be `jellyflam3-worker` | `deploy/` | Stop / start is the **model session switch** ([02](02_LLM_INTEGRATION.md#model-session-switch)) |
| B4 | **Forbid** furnace stack: no `install_flam3.sh`, no `install_jellyfin.sh`, no idle-gate, no worker units | check script | Fail closed if `flam3-animate` or `jellyfin` is present |
| B5 | Python 3 + tests for **agent** adapters only (fake runner in CI) | `tests/` | Furnace pytest stays on Pi / GHA |
| B6 | NVMe layout: `models/{llama31-8b-int4,qwen25-7b-int4,mistral-7b-int4,vlm-2b-int4}/` + `scratch/convert/` | fstab | One Instruct `model_id`; VLM id separate; two sessions |

### C — Network to A

| # | Task | Touches | Prior doc |
|---|---|---|---|
| C1 | Ethernet to same LAN as furnace; document furnace hostname / Jellyfin URL | operator | [phase1/04](../phase1/04_JELLYFIN_LIBRARY.md) |
| C2 | SSH key **agent → furnace** for CLI apply (or token to a small furnace sink) | `authorized_keys` on **A** | [phase1/09](../phase1/09_RUNTIME_AND_OPS.md) |
| C3 | Virtual-camera fetch: Images Primary/Backdrop on **single-sheep** Items; optional silent `stream.mp4?Static=true` grab | [02](02_LLM_INTEGRATION.md#vod-as-camera) | [phase2/02](../phase2/02_JELLYFIN_FLOCK_UX.md), [phase2/03](../phase2/03_HLS_CLIENT_STREAMING.md) |
| C4 | Jellyfin client id `jf3agent-vlm` (not `jellyflam3-*`); A `idle_gate.ignore_client_patterns` | furnace yaml | Must not close the gate ([phase1/06](../phase1/06_IDLE_GATE.md)) |
| C5 | Thermal log under VLM load (not flam3) | runbook | |

### D — Explicit non-tasks (do not “port”)

| Do not | Why |
|---|---|
| `bootstrap_pi.sh` / three-disk fstab | Furnace layout |
| `ventuno-jellyflam3-16.yaml` overlay | Would imply B is a 16-class renderer |
| Tailscale Syncthing as a **fourth furnace** | Peering is genome land on **A** ([phase2/05](../phase2/05_SYNCTHING_GENOME_PEERING.md)) |
| Archive-seed / idle-breed crons on B | Those crons run on **A**; B may be **called** by A ([02](02_LLM_INTEGRATION.md)) |
| Client preset zips built on Ventuno | Package on the **furnace** ([phase3/08](../phase3/08_JELLYFIN_ID_DUMP.md)) |
| `link_capacity` eth-2.5g as a furnace uplink substitute | `N_max` is still the **furnace** hop to TVs ([phase4/07](../phase4/07_CONCURRENT_CLIENTS.md)) |

### E — Docs when 01 ships

- Runbook: “agent platform” vs “furnace” ([USER_GUIDE_AND_RUNBOOK.md](../USER_GUIDE_AND_RUNBOOK.md))
- Glossary: Ventuno ≠ furnace
- Keep [phase2/09](../phase2/09_PI_FROM_SCRATCH.md) as Pi furnace SoT — do not dual-write it

## Artifacts (planned)

| Artifact | Kind | Role |
|---|---|---|
| Agent systemd unit + config | deploy | Runtime on **B** only |
| Bring-up check: furnace stack absent | script | Fail if flam3/Jellyfin/worker found |
| This guide | docs | BOM + non-furnace bring-up |
| Lab notes | docs | Thermals, model RSS, LAN RTT to 16a |

## Non-goals

- Flashing Raspberry Pi OS on Ventuno
- Gold Sheep Lite smoke render on B
- Pi V4L2 / Jellyfin HW transcode on B
- Raising furnace quality because B has 40 TOPS
- Requiring App Lab for headless inference
- Using B as a spare furnace during Pi maintenance

## Exit criteria (when opened)

- [ ] SSH to `ventuno-jellyflam3-agent`; furnace stack **not** installed
- [ ] NVMe holds **three** Instruct INT4 graphs + **one** small VLM on disk; **one** Instruct loaded on HTP; VLM may be co-resident on GPU; **no** `/media/sheep` catalog SoT
- [ ] Local model loads; LAN ping/SSH/Jellyfin reach to **A**
- [ ] Barrel PSU in use; BOM matches purchase (or is corrected)
- [ ] Tasks A–C closed or deferred to [03](03_AI_PLATFORM_GAPS.md)
- [ ] Operator docs state A vs B in one paragraph

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [02_LLM_INTEGRATION.md](02_LLM_INTEGRATION.md) · [03_AI_PLATFORM_GAPS.md](03_AI_PLATFORM_GAPS.md) · [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md) (deployment **A** only)
