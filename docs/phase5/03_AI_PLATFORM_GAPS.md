# 03 — LLM Agent Platform gaps (Ventuno Q)

## Boundary

Honest gaps between Arduino’s **edge-AI** story and **deployment B** (LLM Agent Platform). Furnace gaps stay on the Pi playbook ([phase2/09](../phase2/09_PI_FROM_SCRATCH.md)). Complements [01](01_VENTUNO_Q_HOST.md) and [02](02_LLM_INTEGRATION.md).

**Status:** Parked living list. Update when a lab Ventuno exists as an **agent**, not as a furnace.

## What the silicon is for vs the two deployments

| Vendor pitch | A — Furnace (Pi) | B — Agent platform (Ventuno) |
|---|---|---|
| Hexagon NPU, 40 dense TOPS | **Not used.** flam3 is CPU | **This is the product role** |
| Local LLM / VLM / ASR / TTS | **Must not** run here as a service | Load here; advise A over LAN |
| Adreno GPU | N/A on Pi path (`libx264`) | Small VLM session (pixels); LLM fallback. Two sessions with HTP Instruct — [G18](#g18--hexagon--adreno-during-one-llm-runtime-investigation) H4 |
| STM32H5 / ROS 2 / CAN-FD | Unused | Unused in MVP |
| App Lab + AI Hub | Do not install on A | Optional bench on B; need **headless** path |
| Pi HAT header | NVMe HAT + USB flock | Irrelevant to flock disks |

If the only goal is **faster sheep**, do not buy a Ventuno — cool the Pi and keep NVMe on **A**. Buy B when Owner wants **on-device agents on a second box**.

## Gap list

### G1 — Render vs NPU (architectural)

flam3 does not run on B and does not use Hexagon. A “neural flam3” would be a different product. **Accept.**

### G2 — 16 GB on B is for **one** hot 7–8B INT4

LPDDR5 is shared by CPU, GPU, and NPU. **INT4** 7–8B Instruct (~6 GB + OS) is the Instruct budget. INT16/FP16 7–8B fills RAM before KV. Two 7B INT4 graphs + both KV caches (~12–13 GB + OS) is technically loadable and **practically OOM**. Hexagon is one accelerator for Instruct — “parallel Instruct” = sequential session switch ([02](02_LLM_INTEGRATION.md#model-session-switch)). **Allowed exception:** one small (2B–3B INT4) VLM on Adreno **co-resident** with the hot Instruct (~11–14 GB total) — [02](02_LLM_INTEGRATION.md#vision-pipeline). Measure RSS on B before unattended briefs.

### G2b — Conversion pipeline, not `transformers`

Arbitrary Hugging Face checkpoints do not run. Workflow remains: AI Hub curated list → export → INT8/INT4 → compile for Hexagon → QNN or LiteRT. Ubuntu/Debian on the MPU is an advantage vs Android phone stacks; **days** go to drivers/tooling, not picking among Llama / Qwen / Mistral.

### G3 — Thermal and power on B

NPU + NVMe heat is unknown. Barrel PSU only ([01](01_VENTUNO_Q_HOST.md)). **Work:** thermals under VLM load. Do not compare to 16a flam3 throttling — different host, different workload.

### G4 — Driver / distro maturity on B

New IQ8 Ubuntu image: NVMe, Ethernet, Wi-Fi, vendor vs mainline kernel, NPU userspace. **Work:** 01 exit is “model loads + LAN to A,” not `smoke_render`.

### G5 — Model stack lock-in

AI Hub / App Lab / GenieX vs portable llama.cpp GGUF. Hub may be faster on Hexagon; GGUF is easier to fake in CI. **Decision (when opened):** swappable runner on **B**; unit tests never call the Hub. Do not require GGUF on the **Pi**.

### G6 — Vision input quality

Naming-from-poster uses JPEGs **from A** ([phase2/02](../phase2/02_JELLYFIN_FLOCK_UX.md)). Instruct graphs are **text only**. Pixels go through the small GPU VLM, then caption text into Instruct JSON ([02](02_LLM_INTEGRATION.md#vision-pipeline)). Washed-out / orbit-frozen sheep ([phase3/09](../phase3/09_SHEEP_REFACTOR.md)) yield garbage names — A should not auto-apply LLM aliases on quarantined stems (VLM may still tag them for Shears).

### G7 — Genome XML is a bad prompt

Do not dump `.flam3` from A into B’s context. Structured cards only ([02](02_LLM_INTEGRATION.md) § B). Sheep tax remains on A ([phase2/06](../phase2/06_SHEEP_TAX.md)).

### G8 — Evaluation

No metric for a “good” alias. MVP is mechanical: schema, uniqueness **on A**, sticky human, tax, no license flip.

### G9 — Privacy and peering

Local models on B keep posters on-LAN (good) if fetch is from A, not the cloud. Cloud fallback on B would upload household art. Peering stays genome land on **A** ([phase2/05](../phase2/05_SYNCTHING_GENOME_PEERING.md), [phase3/05](../phase3/05_SHARED_SHEEP_SECURITY.md)). B is not a Syncthing furnace node.

### G10 — Jellyfin is not on B

No V4L2/VAAPI transcode work on Ventuno. Direct Play remains A’s path for TVs ([phase2/03](../phase2/03_HLS_CLIENT_STREAMING.md)). B may **consume** Static MP4 as a silent frame grabber for **one loop** ([02](02_LLM_INTEGRATION.md#vod-as-camera)) without becoming a TV session. **Accept** (B is not a flock server).

### G11 — MCU idle

STM32H5 does not name or breed sheep. Later panel toys on B must not remote-control A’s systemd without auth.

### G12 — Do not pin flam3 on B

big.LITTLE flam3 advice is **void** here — no flam3. If someone installs it “to compare,” that is a scope violation ([00](00_OVERVIEW.md)).

### G13 — App Lab vs headless agent

B should be an SSH appliance. If App Lab is the only way to load NPU models, that is a **blocker**.

### G14 — Client-side AI

Roku/Kodi talk to **A**. They will not call B. Alias display toggle stays Phase 4.

### G15 — Always-on agent logs

Log hygiene on **B** (not next to catalog MP4s on A). [phase1/09](../phase1/09_RUNTIME_AND_OPS.md) style caps.

### G16 — Split-brain / A down

If A is offline, B must not invent sidecar writes. If B is offline, A must keep rendering and RNG-aliasing. **Work:** timeouts and fail-open on A ([02](02_LLM_INTEGRATION.md)).

### G17 — Credential spread

Agent SSH/token to A is a new secret. Do not copy furnace `secrets.env` onto B wholesale (Jellyfin API key for Images maybe; no need for Hammer paths).

### G18 — Hexagon + Adreno during one LLM runtime (investigation)

**Question:** Can deployment B use the Hexagon NPU **and** the Adreno 623 GPU together while serving agentic briefs, or is one accelerator idle?

**Product goal (locked):** **H4** — two sessions: small VLM on GPU (pixels → caption) and hot Instruct on HTP (caption → JSON). Graphs **co-resident**; each sheep’s stages stay sequential. This is **not** one Genie/QNN session using both backends, and **not** two 7Bs.

HTP-only Instruct remains the first bring-up check. Enabling unattended naming-from-poster waits on H4 RSS/thermal lab. Do not assume “40 TOPS + GPU = add them” inside a single LLM forward pass.

#### What the silicon can do vs what the stack exposes

CPU, Adreno, and Hexagon sit on the **same 16 GB LPDDR5**. Extra FLOPs from a second engine still compete for bandwidth and for the same weight/KV pages. Hybrid that copies activations between HTP SRAM and GPU OpenCL buffers can **lose** to HTP-only.

Vendor / OSS facts to re-check on the IQ-8275 image (dates and SKUs move):

| Path | HTP + GPU in **one** forward pass? | Notes |
|---|---|---|
| QNN / QAIRT session (`backend_type` HTP vs GPU) | **No — exclusive** | ONNX Runtime QNN EP: HTP **or** GPU for that EP; Qualcomm’s GPU-backend note is explicit ([May 2025](https://www.qualcomm.com/developer/blog/2025/05/unlocking-power-of-qualcomm-qnn-execution-provider-gpu-backend-onnx-runtime)). |
| Genie `backend::type` | **No — exclusive** | `QnnHtp` **or** `QnnGpu` **or** transformer/CPU in the dialog JSON ([Genie](https://docs.qualcomm.com/doc/80-70023-15B/topic/use-genai-model-with-genie.html)). |
| AI Hub / QAIRT compiled LLM bundle | **NPU-only** | Fastest curated path; GPU/CPU aliases typically coerce to HTP. |
| GenieX `llama_cpp` GGUF | **Not HTP+GPU** | Aliases: `npu`, `gpu`, `cpu`, `hybrid`. Documented `hybrid` is llama.cpp **HTP + CPU** per-tensor scheduling, not Adreno+Hexagon ([GenieX platforms](https://geniex.aihub.qualcomm.com/en/get-started/platforms)). |
| Research HeteroLLM / HeteroInfer | **Yes, custom engine** | Layer- and tensor-split GPU+NPU on Snapdragon 8 Gen 3; OpenCL kernels + QNN ops; W4A16; not a supported IQ8 Ubuntu product ([arXiv 2501.14794](https://arxiv.org/html/2501.14794v2)). |

ORT can still fall **unsupported ops to CPU** while HTP runs the rest. That is HTP+CPU fallback, not a designed Adreno+Hexagon LLM.

#### Combinations worth labbing (if possible)

Treat these as **hypotheses**. Record tok/s, RSS, SoC temp, and PSU watts. Fail closed if the image has no second backend.

| ID | Pattern | How it would work | Likely outcome on IQ8 |
|---|---|---|---|
| H1 | **HTP-only INT4** (baseline) | One QNN/Genie context | Default; measure first |
| H2 | **GPU-only** (FP16 / W8A16 if Hub allows) | `QnnGpu` or OpenCL llama.cpp | Fallback if HTP graph fails; RAM tighter; Adreno 623 is not an X Elite GPU |
| H3 | **Prefill on one, decode on the other** | Two compiled graphs, host copies KV | Research pattern; vendor session is one backend; DIY is a science project |
| H4 | **Pipeline + co-resident** | Small VLM on GPU; 7B Instruct on HTP; pixels → text → JSON | **Locked product goal** ([02](02_LLM_INTEGRATION.md#vision-pipeline)). Lab RSS; on-demand VLM if OOM |
| H5 | **Unsupported-op spill** | HTP graph + CPU (or GPU if a future EP allows) for leftover nodes | Common; measure PCIe/DMA-style copies on-die |
| H6 | **Custom HeteroLLM-class split** | Own OpenCL + QNN runtime | Out of scope unless Owner funds a research fork |

**Do not** interpret H3–H6 as “two 7B models, one on GPU and one on NPU.” Weights still live in the same 16 GB ([G2](#g2--16-gb-on-b-is-for-one-hot-7-8b-int4)).

#### Lab protocol (when a Ventuno exists)

1. Confirm which backends the vendor Ubuntu image actually loads (`libQnnHtp`, `libQnnGpu`, OpenCL ICD).
2. Run the **same** Qwen2.5 7B INT4 (or Hub equivalent) HTP-only vs GPU-only vs any `hybrid` flag the SDK exposes. Log prefill vs decode separately (agentic briefs are prefill-heavy).
3. Load the small VLM on GPU while the 7B stays hot on HTP (H4). Caption one poster, then Instruct JSON. Optionally start sheep N+1 on GPU while N is on HTP (true overlap) and compare tok/s vs sequential-only.
4. Watch RSS: GPU runtimes often keep FP16 activations; HTP INT4 may still pin weights. Target **under ~14 GB**. OOM → keep stage order, unload VLM between jobs.
5. Write the result into this section: **H4 co-resident** / **H4 on-demand VLM** / **defer unattended naming**.

#### Provisional verdict

**One-session HTP+GPU LLM is not a product path** (QNN/Genie exclusive backends). **Two-session H4 is the vision goal:** small Adreno VLM + Hexagon Instruct, pixels → text → JSON, graphs kept loaded when RSS allows. GPU is not a second 7B. Promoting H3 (prefill/decode split of one LLM) still needs lab numbers on **this** IQ-8275, not Snapdragon phone papers.

## Open questions (Owner)

1. MVP runner on B: llama.cpp, GenieX/QNN, or App Lab-export only?
2. Apply path: SSH from B→A vs small authenticated sink **on A**?
3. May A’s idle-breed call B unattended, or naming-only until share/breed-weight from 08 exists?
4. One agent per household vs one agent per furnace?
5. Default hot `model_id`: Qwen2.5 7B INT4 (structured JSON) vs Llama 3.1 8B INT4 (general agent)?
6. H4 lab: co-resident small VLM + hot Instruct, or on-demand VLM? Do **not** assume concurrent HTP+GPU inside one Genie session.

## Additional goals (TBD)

Parked until Owner opens implementation. Not DoD for first RC unless promoted.

| ID | Goal | Notes |
|---|---|---|
| T1 | Small **2B–3B INT4 VLM** on Adreno, co-resident with hot Instruct | Locked: [02](02_LLM_INTEGRATION.md#vision-pipeline). Hub/Qwen2-VL-class; **not** a 7B VLM |
| T2 | Optional always-resident **3B Instruct** INT4 for cheap routing | Text-only sidecar; **not** a substitute for T1; **not** a second 7B |
| T3 | Compile-cache on NVMe so session switch is load, not re-quantize | Scratch dir in [01](01_VENTUNO_Q_HOST.md) BOM |
| T4 | Healthz reports `model_id` + RSS so A can fail-open with a reason | Furnace logs, not sidecar SoT |
| T5 | Eval set: alias uniqueness + breed JSON schema vs the three Instruct graphs | Mechanical [G8](#g8--evaluation); no “good name” metric |
| T6 | Headless QNN/LiteRT on Ubuntu without App Lab | Blocker if App Lab is the only loader ([G13](#g13--app-lab-vs-headless-agent)) |
| T7 | Lab Hexagon + Adreno as **two sessions** (H4) | [G18](#g18--hexagon--adreno-during-one-llm-runtime-investigation); co-resident VLM vs on-demand |
| T8 | VoD as virtual camera (Images; optional Static peek; follow NowPlaying) | **Single-sheep loops only** ([02](02_LLM_INTEGRATION.md#vod-as-camera)). Not MIPI. |

## Non-goals

- Promising Lite renders faster because a Ventuno exists
- Documenting Ventuno as a Pi 5 substitute
- Treating 40 TOPS as a flam3 quality multiplier
- Dual-use of one board as A **and** B
- Tuple VoD as a VLM camera target

## Exit criteria (when opened)

- [ ] Lab notes for G3/G4 (thermals, kernel, model load) **on B**
- [ ] Written runner choice for G5; INT4 session switch labbed (one hot 7–8B)
- [ ] G18 H4: small GPU VLM + HTP Instruct RSS/thermals; co-resident or on-demand written
- [ ] G16: A continues if B is stopped; B refuses writes if A is gone
- [ ] This list triaged: accept / fix in 01 / fix in 02 / defer

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [01_VENTUNO_Q_HOST.md](01_VENTUNO_Q_HOST.md) · [02_LLM_INTEGRATION.md](02_LLM_INTEGRATION.md) · [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md) · [Arduino VENTUNO Q](https://www.arduino.cc/product-ventuno-q)
