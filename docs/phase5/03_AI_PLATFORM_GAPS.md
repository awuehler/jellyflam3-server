# 03 — LLM Agent Platform gaps (Ventuno Q)

## Boundary

Honest gaps between Arduino’s **edge-AI** story and **deployment B** (LLM Agent Platform). Furnace gaps stay on the Pi playbook ([phase2/09](../phase2/09_PI_FROM_SCRATCH.md)). Complements [01](01_VENTUNO_Q_HOST.md) and [02](02_LLM_INTEGRATION.md).

**Status:** Parked living list. Update when a lab Ventuno exists as an **agent**, not as a furnace.

## What the silicon is for vs the two deployments

| Vendor pitch | A — Furnace (Pi) | B — Agent platform (Ventuno) |
|---|---|---|
| Hexagon NPU, 40 dense TOPS | **Not used.** flam3 is CPU | **This is the product role** |
| Local LLM / VLM / ASR / TTS | **Must not** run here as a service | Load here; advise A over LAN |
| Adreno GPU | N/A on Pi path (`libx264`) | Optional vision decode on B; not Jellyfin transcode |
| STM32H5 / ROS 2 / CAN-FD | Unused | Unused in MVP |
| App Lab + AI Hub | Do not install on A | Optional bench on B; need **headless** path |
| Pi HAT header | NVMe HAT + USB flock | Irrelevant to flock disks |

If the only goal is **faster sheep**, do not buy a Ventuno — cool the Pi and keep NVMe on **A**. Buy B when Owner wants **on-device agents on a second box**.

## Gap list

### G1 — Render vs NPU (architectural)

flam3 does not run on B and does not use Hexagon. A “neural flam3” would be a different product. **Accept.**

### G2 — 16 GB on B is for models, not the flock

LPDDR5 on Ventuno is shared by CPU, GPU, and NPU. Size models so Ubuntu + VLM fit **without** Jellyfin or PNG dumps (those live on A). Measure RSS on B before enabling unattended briefs.

### G3 — Thermal and power on B

NPU + NVMe heat is unknown. Barrel PSU only ([01](01_VENTUNO_Q_HOST.md)). **Work:** thermals under VLM load. Do not compare to 16a flam3 throttling — different host, different workload.

### G4 — Driver / distro maturity on B

New IQ8 Ubuntu image: NVMe, Ethernet, Wi-Fi, vendor vs mainline kernel, NPU userspace. **Work:** 01 exit is “model loads + LAN to A,” not `smoke_render`.

### G5 — Model stack lock-in

AI Hub / App Lab / GenieX vs portable llama.cpp GGUF. Hub may be faster on Hexagon; GGUF is easier to fake in CI. **Decision (when opened):** swappable runner on **B**; unit tests never call the Hub. Do not require GGUF on the **Pi**.

### G6 — Vision input quality

Naming-from-poster uses JPEGs **from A** ([phase2/02](../phase2/02_JELLYFIN_FLOCK_UX.md)). Washed-out / orbit-frozen sheep ([phase3/09](../phase3/09_SHEEP_REFACTOR.md)) yield garbage names — A should not auto-apply LLM aliases on quarantined stems.

### G7 — Genome XML is a bad prompt

Do not dump `.flam3` from A into B’s context. Structured cards only ([02](02_LLM_INTEGRATION.md) § B). Sheep tax remains on A ([phase2/06](../phase2/06_SHEEP_TAX.md)).

### G8 — Evaluation

No metric for a “good” alias. MVP is mechanical: schema, uniqueness **on A**, sticky human, tax, no license flip.

### G9 — Privacy and peering

Local models on B keep posters on-LAN (good) if fetch is from A, not the cloud. Cloud fallback on B would upload household art. Peering stays genome land on **A** ([phase2/05](../phase2/05_SYNCTHING_GENOME_PEERING.md), [phase3/05](../phase3/05_SHARED_SHEEP_SECURITY.md)). B is not a Syncthing furnace node.

### G10 — Jellyfin is not on B

No V4L2/VAAPI transcode work on Ventuno. Direct Play remains A’s path ([phase2/03](../phase2/03_HLS_CLIENT_STREAMING.md)). **Accept** (out of B’s job).

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

## Open questions (Owner)

1. MVP runner on B: llama.cpp, GenieX, or App Lab-export only?
2. Apply path: SSH from B→A vs small authenticated sink **on A**?
3. May A’s idle-breed call B unattended, or naming-only until 08 votes exist?
4. One agent per household vs one agent per furnace?

## Non-goals

- Promising Lite renders faster because a Ventuno exists
- Documenting Ventuno as a Pi 5 substitute
- Treating 40 TOPS as a flam3 quality multiplier
- Dual-use of one board as A **and** B

## Exit criteria (when opened)

- [ ] Lab notes for G3/G4 (thermals, kernel, model load) **on B**
- [ ] Written runner choice for G5
- [ ] G16: A continues if B is stopped; B refuses writes if A is gone
- [ ] This list triaged: accept / fix in 01 / fix in 02 / defer

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [01_VENTUNO_Q_HOST.md](01_VENTUNO_Q_HOST.md) · [02_LLM_INTEGRATION.md](02_LLM_INTEGRATION.md) · [../phase2/09_PI_FROM_SCRATCH.md](../phase2/09_PI_FROM_SCRATCH.md) · [Arduino VENTUNO Q](https://www.arduino.cc/product-ventuno-q)
