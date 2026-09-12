# 01 — LLM Agent Platform host (Arduino Ventuno Q)

## Boundary

Hardware, OS, storage, power, and **bring-up** for **deployment B**: an **Arduino Ventuno Q** that runs **only** the LLM Agent Platform. Stop before furnace integration adapters ([02](02_LLM_INTEGRATION.md)).

**This is not a furnace port.** Do not map 16a disk roles, do not apply `rpi-jellyflam3-16`, do not install `flam3-animate` / Jellyfin / `jellyflam3-worker` here. The JellyFlam3 Furnace (**deployment A**) stays on a Raspberry Pi 5 — [phase2/09](../phase2/09_PI_FROM_SCRATCH.md).

**Status:** Parked. Do not treat Ventuno Q as a supported **furnace** or as a required lab box until Owner opens Phase 5.

Depends on a reachable furnace (SSH, Jellyfin URL, catalog posters) and on [00](00_OVERVIEW.md) split rules.

## Intent

Ventuno Q is Arduino’s Linux SBC. Phase 5 uses that silicon as an **agent platform**: local LLM/VLM inference that **talks to one or more** Pi furnaces. Workload is **agentic API** (batch briefs, no interactive-chat SLA). Posters/stills use a **small GPU VLM** plus the **hot Hexagon Instruct** graph ([02](02_LLM_INTEGRATION.md#vision-pipeline)). When the household has **two or more** furnaces sharing sheep, B joins the **same flock Tailscale tailnet** as those Pis ([tailscale](#tailscale-flock-tailnet)) — it does **not** become a Syncthing node.

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
| Hostname (proposed) | `rpi-jellyflam3-16a` (existing; 08a / 04a / …) | `ventuno-jellyflam3-agent` (one per household; letter suffix only if several **agents**) |
| RAM | 4 / 8 / 16 GB per class | 16 GB LPDDR5 — models, not PNG dumps |
| OS disk | microSD | 64 GB eMMC |
| Fast disk | 1 TB NVMe scratch + state | NVMe for **model weights** + agent logs (not flam3 frames) |
| Flock disk | 1 TB USB → `/media/sheep` | **None** — read posters from furnace / Jellyfin |
| LAN | Lab often WiFi STA; Tailscale when Opt In | Prefer **2.5 GbE** on-site; **Tailscale** to reach every A when N≥2 |
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
| 6 | **Cat6 patch** | 1 | 5–10 | 2.5 GbE on-site; Tailscale when N≥2 |

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

## Tailscale (flock tailnet)

The flock’s private underlay is **Tailscale**, not a campus VLAN. When **two or more** Raspberry Pi furnaces Opt In to share genomes ([phase2/05](../phase2/05_SYNCTHING_GENOME_PEERING.md)), they already live on that tailnet (`tag:jellyflam3`). The LLM Agent Platform **must join the same tailnet** so one B can reach every A (SSH, Jellyfin Images / Static VoD, display-sink) even when the Pis are not on one Ethernet switch.

**B is not a furnace peer.** Do not install Syncthing. Do not run `python3 -m pipeline.peering opt-in` / `opt-out`. Do not advertise `tag:jellyflam3`. Genome land stays `genomes/peers/inbox` **on each A**.

Required when: N≥2 furnaces, or any furnace is off the Ventuno’s L2 (remote site, guest Wi-Fi, CGNAT). Optional but useful for N=1 so MagicDNS names stay stable.

### Admin (tailnet, once)

1. Paste the Phase 5 fragment in [`deploy/peering/tailscale-acl.example.json`](../../deploy/peering/tailscale-acl.example.json) into the tailnet ACL (keep furnace `tag:jellyflam3` ↔ `tag:jellyflam3:*`).
2. Create a **reusable tagged pre-auth key** for `tag:jellyflam3-agent` only. Store as `TS_AUTHKEY_AGENT` on **B** (not in git; do not copy furnace `secrets.env` wholesale — [03](03_AI_PLATFORM_GAPS.md) G17).
3. Confirm furnaces stay on `tag:jellyflam3` via existing Opt In. Agent ACL is SSH **22**, Jellyfin **8096**, display-sink **8791** toward furnaces — not Syncthing **22000**.

### On the Ventuno (B)

```bash
# Ubuntu — https://tailscale.com/download/linux
curl -fsSL https://tailscale.com/install.sh | sh

# Enroll as agent, not as a furnace
sudo tailscale up --auth-key="$TS_AUTHKEY_AGENT" \
  --hostname=ventuno-jellyflam3-agent \
  --advertise-tags=tag:jellyflam3-agent
# Do not: --advertise-exit-node, subnet routes, tag:jellyflam3

tailscale status
tailscale ip -4
# MagicDNS: ventuno-jellyflam3-agent.<tailnet>.ts.net  (or short name if enabled)
```

4. From B, `ping` / `tailscale ping` each furnace MagicDNS or `100.x` address (`rpi-jellyflam3-16a`, `08a`, `04a`, …).
5. SSH as user `jellyflam3` to each A (key from C2). Jellyfin URL per furnace: `http://<magicdns-or-100.x>:8096` (or the LAN URL when on-site).
6. `jf3agent-vlm` Images/VoD client still must not match idle-gate TV patterns ([C4](#c--network-to-a)); ignore pattern **on each A**.
7. Bring-up **fails closed** if `syncthing` or `jellyflam3-syncthing.service` is present.

Logout (agent only — does **not** Opt Out the Pis):

```bash
sudo tailscale logout   # or: sudo tailscale down
```

Furnace `pipeline.tailscale_watch` stays **on A**. Do not install that cron on B as a Syncthing healer.

### Agent config for many furnaces

Illustrative ([02](02_LLM_INTEGRATION.md) applies per furnace):

```yaml
# /etc/jellyflam3-agent/agent.yaml  — B only
furnaces:
  - id: 16a
    ssh: jellyflam3@rpi-jellyflam3-16a
    jellyfin_url: http://rpi-jellyflam3-16a:8096
  - id: 08a
    ssh: jellyflam3@rpi-jellyflam3-08a
    jellyfin_url: http://rpi-jellyflam3-08a:8096
  - id: 04a
    ssh: jellyflam3@rpi-jellyflam3-04a
    jellyfin_url: http://rpi-jellyflam3-04a:8096
```

Use Tailscale MagicDNS (or `100.x`) when L2 does not reach. Each A still has its own sidecar SoT, idle-gate, and `ignore_client_patterns`.

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
| C1 | Ethernet to same LAN when on-site; document **each** furnace hostname / Jellyfin URL | operator | [phase1/04](../phase1/04_JELLYFIN_LIBRARY.md) |
| C2 | SSH key **agent → each furnace** for CLI apply (or token to a small sink **on each A**) | `authorized_keys` on **every A** | [phase1/09](../phase1/09_RUNTIME_AND_OPS.md) |
| C3 | Virtual-camera fetch: Images Primary/Backdrop on **single-sheep** Items; optional silent `stream.mp4?Static=true` grab | [02](02_LLM_INTEGRATION.md#vod-as-camera) | [phase2/02](../phase2/02_JELLYFIN_FLOCK_UX.md), [phase2/03](../phase2/03_HLS_CLIENT_STREAMING.md) |
| C4 | Jellyfin client id `jf3agent-vlm` (not `jellyflam3-*`); **each** A `idle_gate.ignore_client_patterns` | furnace yaml | Must not close the gate ([phase1/06](../phase1/06_IDLE_GATE.md)) |
| C5 | Thermal log under VLM load (not flam3) | runbook | |
| C6 | Tailscale enroll `tag:jellyflam3-agent` when N≥2 (or off-L2); **no** Syncthing | [tailscale](#tailscale-flock-tailnet) | [phase2/05](../phase2/05_SYNCTHING_GENOME_PEERING.md); ACL example |

### D — Explicit non-tasks (do not “port”)

| Do not | Why |
|---|---|
| `bootstrap_pi.sh` / three-disk fstab | Furnace layout |
| `ventuno-jellyflam3-16.yaml` overlay | Would imply B is a 16-class renderer |
| Tailscale Syncthing as a **fourth furnace** | Peering is genome land on **A**; B may join the **tailnet only** ([tailscale](#tailscale-flock-tailnet)) |
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
- `pipeline.peering opt-in` on the Ventuno

## Exit criteria (when opened)

- [ ] SSH to `ventuno-jellyflam3-agent`; furnace stack **not** installed
- [ ] NVMe holds **three** Instruct INT4 graphs + **one** small VLM on disk; **one** Instruct loaded on HTP; VLM may be co-resident on GPU; **no** `/media/sheep` catalog SoT
- [ ] Local model loads; reach **each** configured A (LAN and/or Tailscale MagicDNS / `100.x`)
- [ ] N≥2: B on `tag:jellyflam3-agent`; Syncthing **absent**; ACL allows 22/8096/8791 to furnaces only
- [ ] Barrel PSU in use; BOM matches purchase (or is corrected)
- [ ] Tasks A–C closed or deferred to [03](03_AI_PLATFORM_GAPS.md)
- [ ] Operator docs state A vs B in one paragraph

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [02_LLM_INTEGRATION.md](02_LLM_INTEGRATION.md) · [03_AI_PLATFORM_GAPS.md](03_AI_PLATFORM_GAPS.md) · [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md) (deployment **A** only)
