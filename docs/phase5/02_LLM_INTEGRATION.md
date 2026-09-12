# 02 — LLM Agent Platform ↔ furnace contracts

## Boundary

Map **deployment B** (local LLM / VLM on Ventuno) onto contracts that **already exist on deployment A** (Pi furnace). Host bring-up for B is [01](01_VENTUNO_Q_HOST.md). Gaps on B are [03](03_AI_PLATFORM_GAPS.md).

**Status:** Parked. Do not add model stubs to `jellyflam3-worker`, idle-breed, or naming **ingest on the furnace** until Owner opens this guide. RNG aliases already ship **on A** without an LLM ([phase4/09](../phase4/09_SHEEP_NAMING.md)).

Models on **B advise** (names, parent briefs, operator actions). **flam3-genome** and the **furnace worker** still **do**. B never becomes a second factory.

## Intent

| Surface | Where it runs | Prior SoT |
|---|---|---|
| **LLM poster naming** | Small GPU VLM → caption → hot Instruct JSON on **B**; `set-alias` / sidecar write on **A** | [phase4/09](../phase4/09_SHEEP_NAMING.md) § D; [vision pipeline](#vision-pipeline) |
| **LLM-assisted pedigree** | Brief on **B**; `pipeline.breed` / idle-breed on **A** | [phase2/07](../phase2/07_PEDIGREE_BREEDING.md) |
| **Vote-aware briefs** | Read `viewer_feedback` **from A’s sidecar** (overlay + `/v1/sheep-votes` shipped; share cron / breed weights still parked) | [phase4/08](../phase4/08_VIEWER_FEEDBACK_LOOP.md), [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) |
| **Shears / refactor agent** | NL on **B** → CLI on **A** with confirm tokens | [phase3/03](../phase3/03_SHEEP_SHEARS.md), [phase3/09](../phase3/09_SHEEP_REFACTOR.md) |
| **Ops agent** | Explain gate/inbox using **A** JSON; later request drain on **A** | [phase1/09](../phase1/09_RUNTIME_AND_OPS.md), [phase4/00](../phase4/00_OVERVIEW.md#furnace-polish-parked--not-numbered) |
| **Share brief** | Propose candidates; Opt In + share-security still on **A** | [phase2/05](../phase2/05_SYNCTHING_GENOME_PEERING.md), [phase3/05](../phase3/05_SHARED_SHEEP_SECURITY.md), [phase4/01](../phase4/01_PEER_SHARE_PATH.md) |

```text
  A  Furnace Jellyfin  (VoD camera: Item Id / NowPlaying)
           │  frames over LAN (Images; optional Static MP4 grab)
           ▼
  B  pixels → text → Instruct JSON  (opt-in)
           │  small VLM (Adreno) captions JPEG
           │  hot 7–8B Instruct (Hexagon) emits schema
           ▼
  A  uniqueness + license + tax gates
           │
           ├─► alias (alias_source=llm)     [phase4/09]   on A
           ├─► pipeline.breed argv           [phase2/07]  on A
           ├─► shears / refactor (confirm)   [phase3]     on A
           └─► operator notes (B logs ≠ sidecar SoT)
```

Arduino App Lab / Qualcomm AI Hub / QNN / LiteRT / llama.cpp run on **B**. Canonical flock operators still use `python3 -m pipeline.*` **on A** (or a thin SSH wrapper from B). Hexagon is a **single** accelerator for Instruct graphs: agentic batches (no chat SLA) tolerate a **cold session switch** between compiled INT4 Instruct models. Adreno holds a **separate** small-VLM session ([vision pipeline](#vision-pipeline)).

## INT4 7–8B comparison (agentic API → furnace)

All three are **Instruct INT4**, Hub/QNN-converted, **one hot at a time**. They are **text** models: they never see JPEG bytes. Poster/still **pixels** go through the [vision pipeline](#vision-pipeline). Strengths vs [integration map](#integration-map-prior-phases):

| | **Llama 3.1 8B Instruct INT4** | **Qwen2.5 7B Instruct INT4** | **Mistral 7B Instruct INT4** |
|---|---|---|---|
| **Fit on 16 GB (one hot)** | Yes — ~6–7 GB weights+KV; OS ~2–3 GB | Yes — ~6 GB class | Yes — ~6 GB class |
| **Chat SLA** | Not required. Few tok/s on 40 TOPS is OK for briefs | Same | Same |
| **Default role** | General agent / NL → CLI intent | **Workhorse** (MVP `model_id`) | Fallback if Hub compile or JSON schema fails |
| **A — Poster naming** ([phase4/09](../phase4/09_SHEEP_NAMING.md) D) | Alias / rationale from **VLM caption** + sidecar cards | Strong at constrained `adjective_surname` + JSON | Adequate fallback |
| **B — Pedigree brief** ([phase2/07](../phase2/07_PEDIGREE_BREEDING.md)) | Best all-round parent/mode suggestion | Structured `{mode, parents[], method?}` JSON | Solid fallback brief |
| **Sidecar / XML·JSON parse** | Fine | **Best** JSON-ish extraction (Overview, tags, `viewer_feedback`) | Fine |
| **Vote-aware briefs** ([phase4/08](../phase4/08_VIEWER_FEEDBACK_LOOP.md)) | Read A’s sidecar integers; do not “remember likes” | Same — structured tally → share_candidate language | Same |
| **C — Shears / refactor** | NL → propose audit list | Map messy operator notes → pathway ids | Fallback |
| **C — Ops / drain / disk** | Explain `idle_gate_status.json` / `worker_drain status` | Compact status JSON → human paragraph | Fallback |
| **C — Share brief** | Propose candidates; apply still on A | Same | Same |
| **Still image analysis** | Consumes caption / palette tags from the small VLM — not pixels | Same | Same |
| **Skip** | Unquantized / FP16 8B; 13B+ | Dual-hot with Mistral 7B | Dual-hot with Qwen 7B (redundant, ~12–13 GB + OS) |

**MVP:** compile all three Instruct graphs onto NVMe; run **Qwen2.5 7B INT4** as the hot workhorse. Switch to Llama when briefs need more general agentic behavior; switch to Mistral only as a Hub/runtime fallback. **Co-resident:** small VLM INT4 on GPU, not a second 7B and not Qwen2.5 3B-as-a-substitute-for-vision (3B Instruct is optional routing — [03](03_AI_PLATFORM_GAPS.md) T2).

## Vision pipeline

**Locked goal** ([00](00_OVERVIEW.md) decision 10): keep a **small VLM resident on Adreno** in **parallel** with the **hot Instruct on Hexagon**, and caption **one loop** as:

```text
  A  {stem}-poster.jpg (or still)  ──LAN──►  B
                                              │
                          Adreno  2B–3B INT4 VLM  (session 1, stays loaded)
                                              │  caption / palette / “orbit frozen?” text
                                              ▼
                          Hexagon  hot 7–8B Instruct INT4  (session 2, stays loaded)
                                              │  Instruct JSON: alias? | breed brief | tags
                                              ▼
  A  uniqueness / tax / human-sticky apply
```

| Rule | Why |
|---|---|
| **Two sessions, two engines** | QNN/Genie is HTP **or** GPU per session ([03](03_AI_PLATFORM_GAPS.md#g18--hexagon--adreno-during-one-llm-runtime-investigation) H4). |
| **Co-resident (“parallel”)** | Avoid reload tax on every poster. RSS target ~11–14 GB ([01](01_VENTUNO_Q_HOST.md#llm-storage-math-why-nvme-not-emmc)). |
| **Per-request sequential** | Caption must exist before Instruct JSON. Do not wait on a chat SLA; batches can pipeline sheep N+1 on GPU while N is on HTP if RSS allows. |
| **VLM is small** | 2B–3B INT4 (Hub captioner / Qwen2-VL-class). **Not** Qwen2-VL 7B beside the Instruct 7B. |
| **Instruct never sees pixels** | JPEG stays on the VLM path; Instruct gets text + sidecar cards (alias, tags, votes). |
| **VLM does not apply aliases** | It describes. The 7B proposes `adjective_surname` / breed JSON. **A** still writes SoT. |
| **Fail-open** | VLM down → skip LLM naming (keep `auto`). Instruct down → same. Do not block ingest on A. |
| **Quarantine** | Do not auto-name washed-out / orbit-frozen stems ([phase3/09](../phase3/09_SHEEP_REFACTOR.md)); VLM may still flag them for Shears. |

Illustrative config (names TBD):

```yaml
# /etc/jellyflam3-agent/agent.yaml  — B only
model_id: qwen25-7b-int4          # Hexagon; session switch restarts the unit
vlm_id: qwen2vl-2b-int4           # Adreno; leave loaded across Instruct switches if RSS allows
vision_pipeline: pixels_then_json # locked; no pixels_into_instruct
vision_source: jellyfin_vod       # [VoD as camera](#vod-as-camera); not MIPI / flock mount
```

If the first lab OOM-kills with both resident, drop to **load VLM on demand** (still pixels → text → JSON; lose parallel residency). Do not change the stage order. Do not put the VLM on Hexagon and the 7B on GPU as MVP (HTP is the Instruct workhorse).

Non-pixel briefs (sidecar JSON parse, drain explain, Shears NL) skip the VLM and hit Instruct only.

## VoD as camera

**Implementation goal** ([00](00_OVERVIEW.md) decision 11): treat furnace **Jellyfin VoD** as the VLM’s remote sensor — the job a MIPI camera + Spectra 692 would do (deliver RGB/JPEG frames), without CSI, without ISP, and without catalog files on B.

**Scope: one rendered sheep (one loop MP4).** Naming MVP stays **Images snapshot** of that Item. Peek + follow-pasture are the **flexible/dynamic** sample route for follow-up tasks (live wall, missed phase, refactor burst) on the **same** single-sheep Item.

| MIPI (unused) | Jellyfin stand-in | Into the VLM |
|---|---|---|
| CSI + lens | 2.5 GbE to furnace Jellyfin | Network, not JMEDIA |
| What the sensor faces | Single-sheep Item Id or TV `NowPlayingItem` when that item is one loop | Which sheep |
| Spectra 692 ISP | Already-baked Lite + Images/ffmpeg | JPEG / few RGB frames |
| V4L2 `/dev/videoN` | `GET …/Videos/{id}/stream.mp4?Static=true` | Decode on B, then N frames |
| Snapshot | Images **Primary** or **Backdrop/{i}** (no Playing) | Default shutter |
| Preview burst | ffmpeg 1–4 frames from Static MP4, then drop socket | Only if Images miss the phase |
| USB camera | Closer analog than MIPI for HTTP decode | Not the product sensor |

Ambient default is Direct Play MP4 ([phase2/03](../phase2/03_HLS_CLIENT_STREAMING.md) `streamMode=mp4`). HLS remux `.ts` and any `TranscodingInfo` path are the wrong firmware.

### Three lens modes

1. **Snapshot (MVP)** — HTTP GET Primary (mid-loop poster) and optionally up to four Backdrops (`stills.count`) for **one loop**. No `NowPlayingItem` from B. Fail-open naming.
2. **Peek the stream (follow-up)** — silent ffmpeg grab from Static Direct Play of that **same** single-sheep Item when a poster/Backdrop missed the phase. DeviceName **`jf3agent-vlm`** (must **not** match `tv_client_patterns` `roku|jellyflam3`). Add `idle_gate.ignore_client_patterns` on A like the screensaver. **Never** POST `/Sessions/Playing`. **Never** force transcode on A.
3. **Follow the pasture (follow-up)** — read TV Sessions `NowPlayingItem`; if it is a **single sheep**, snapshot that id (mode 1). Skip if the playing item is not one loop. Do not Direct Play a second TV-class copy.

### Must not

| Do not | Why |
|---|---|
| Mount `/media/sheep` and open `{stem}.mp4` | Catalog SoT stays on A |
| Feed a whole loop into the VLM | Camera pipelines sample frames; QNN wants static N×JPEG |
| Route HTTP through Spectra 692 | ISP is MIPI-only |
| Name the Jellyfin client `jellyflam3-*` without ignore | Gate `active_tv_client` pauses flam3 |
| HLS remux / transcode as the grabber | `block_on_any_transcode`; competes with encode |

### Frame budget

Agentic briefs have no chat SLA — do not run a 30 fps CSI preview. Default **1× Primary**. After H4 RSS, **Primary + ≤4 Backdrops** if the compiled VLM arity is N>1. Stream peek only when Images are not enough, then close the socket. Concurrent Static peeks count toward `N_max` if they overlap TVs ([phase4/07](../phase4/07_CONCURRENT_CLIENTS.md)).

Illustrative (names TBD):

```yaml
# /etc/jellyflam3-agent/agent.yaml  — B only
vision_source: jellyfin_vod       # not mipi, not usb, not flock_mount
vod_camera:
  shutter: images                 # MVP: Primary / Backdrop of one loop
  peek_static: false              # follow-up: stream.mp4?Static=true (same Item)
  follow_nowplaying: false        # follow-up: Sessions → snapshot if single sheep
  client_name: jf3agent-vlm
```

On A, ignore that client the way screensaver is ignored ([phase1/06](../phase1/06_IDLE_GATE.md)).

## Model session switch

Goal: change which INT4 graph is hot **without** two 7Bs in RAM and **without** a furnace restart.

Illustrative (unit name TBD; **B** only):

```bash
# On ventuno-jellyflam3-agent — furnace A stays up
sudo systemctl stop jellyflam3-agent
sudoedit /etc/jellyflam3-agent/agent.yaml   # model_id: qwen25-7b-int4 | llama31-8b-int4 | mistral-7b-int4
sudo systemctl start jellyflam3-agent
# Confirm RSS + loaded graph; A’s naming/breed adapters time out → RNG / random parents until B is back
```

| Step | Who | Notes |
|---|---|---|
| 1. Stop agent unit | B | Unloads Hexagon context; in-flight brief fails closed |
| 2. Update `model_id` (path under NVMe `models/`) | B | Do not copy weights; already on disk |
| 3. Start agent unit | B | Loads **one** compiled graph; first request pays compile/load latency — fine for agentic batches |
| 4. Furnace A | A | `naming.llm` / `breed.llm` stay default off until B healthz; no worker restart |

Do **not** hot-swap two QNN Instruct contexts to fake parallelism on one NPU as MVP. Prefer leaving the **VLM session** loaded across an Instruct session switch if RSS allows. Do **not** `systemctl restart jellyflam3-worker` on A for a model change.

## Locked product rules (design)

1. **A and B stay split.** No worker unit on Ventuno; no LLM unit on the Pi. See [00](00_OVERVIEW.md).
2. **flam3 stays the renderer (on A).** No “generate a sheep with the NPU.” The small VLM looks at **posters/stills** fetched from A; Instruct consumes the caption ([phase1/05](../phase1/05_RENDER_PIPELINE.md), [vision pipeline](#vision-pipeline)).
3. **Offline default on B.** `naming.llm.enabled` / `breed.llm.enabled` (names TBD) default **false** on the **furnace** side (A ignores B if unset). No cloud unless configured; no API keys in git ([phase4/09](../phase4/09_SHEEP_NAMING.md) rule 8).
4. **Sidecar SoT is on A.** Models do not get a flock database on B. Votes, aliases, license, pedigree hints stay on `{stem}.jellyflam3.json` beside the MP4 ([phase1/07](../phase1/07_LICENSE_AND_METADATA.md)).
5. **Human sticky.** Never overwrite `alias_source=human`. LLM apply only when source is `auto` or operator `--accept` **on A**.
6. **Not flam3 `nick`.** ([phase4/09](../phase4/09_SHEEP_NAMING.md) rule 5).
7. **Breed = flam3-genome on A.** B may pick parent stems + mode + method; it must not emit genome XML as SoT. Sheep tax still runs on A ([phase2/06](../phase2/06_SHEEP_TAX.md)).
8. **No AI-gate on the furnace.** Idle-gate remains TV Playing vs render ([phase1/06](../phase1/06_IDLE_GATE.md)). B may infer while A renders — that is the point of two boxes. B should still shed load if it overheats ([03](03_AI_PLATFORM_GAPS.md)).
9. **Confirm tokens stay on A.** Shears `DELETE`, refactor `APPLY` / `QUARANTINE` / `BATCH`, Hammer `HAMMER` are never auto-fired from B without the same operator confirm.
10. **Commercial / NC** still enforced on A ([phase1/07](../phase1/07_LICENSE_AND_METADATA.md)).
11. **Uniqueness** of aliases is computed against **A’s catalog** ([phase4/09](../phase4/09_SHEEP_NAMING.md) rule 3).
12. **Vision pipeline.** Pixels → text → Instruct JSON. Small VLM on GPU may stay loaded with the hot Instruct; see [vision pipeline](#vision-pipeline).
13. **VoD as camera.** Frames from furnace Jellyfin **single-sheep** Items only ([vod-as-camera](#vod-as-camera)). B is not a pasture client.

## Integration map (prior phases)

### A — Sheep naming (Phase 4 / 09 D)

**Already shipped on the furnace:** hash-seed RNG, ingest hook, backfill, `set-alias` / `clear-alias`, `alias_source` ∈ `auto|human|llm`.

**This slice adds:**

1. **B** samples **one loop** via [VoD as camera](#vod-as-camera): Images Primary (and optional Backdrops) for that Jellyfin Item. Disk `stills/{stem}/` is A’s feedstock, not B’s mount.
2. **B** runs the [vision pipeline](#vision-pipeline): small VLM caption → hot Instruct proposes an alias; optional rationale in **B** logs (or a sidecar field only if [phase1/07](../phase1/07_LICENSE_AND_METADATA.md) grows a reserved key).
3. **A** applies: `python3 -m pipeline.sheep_naming set-alias --source llm` (illustrative) after uniqueness check.
4. Pasture filename-vs-alias **toggle** stays Phase 4 / 09 C. Pasture still talks to **A**.

Furnace ingest must **not** block on B (timeout → keep `alias_source=auto`).

### B — LLM-assisted pedigree (Phase 2 / 07)

**Already shipped on the furnace:** `pipeline.breed`; idle cron; `origin: local_pedigree`; tax-parents; NC inheritance.

**This slice adds:**

1. **Parent picker brief on B** — compact cards from A (stem, alias, tags, duration, optional votes) plus optional VLM caption of the poster thumb; not raw `.flam3` XML.
2. **Mode suggestion** — `mutate` / `cross` / `interpolate` (+ `method`).
3. **Idle policy (optional, default off) on A** — `cron_breed_idle` may **HTTP/SSH to B** for a parent pick, then run `pipeline.breed` **locally**. Gates stay on A: empty inbox, idle-gate, `archive_cron_imminent`, fingerprint dedup ([phase2/07](../phase2/07_PEDIGREE_BREEDING.md#daily-idle-breed-cron)). If B is down, idle-breed falls back to uniform random — furnace must not stall.
4. **Viewer weights** — A’s sidecar integers (`viewer_feedback`) win over B “remembering likes.” Breed-weight / auto-promote stay Phase 4 parked.

Do **not** implement cloud-API pedigree **on the Pi** as a substitute for B.

### C — Other agentic vectors

| Vector | B may | Must not | Prior doc |
|---|---|---|---|
| **Shears** | Propose audit/sweep/delete list | Cascade delete without `DELETE` **on A** | [phase3/03](../phase3/03_SHEEP_SHEARS.md) |
| **Refactor** | Map “grey / muddy / frozen orbit” to pathways | `APPLY` without token on A | [phase3/09](../phase3/09_SHEEP_REFACTOR.md) |
| **Idle-gate / drain** | Explain A’s `idle_gate_status.json` and `worker_drain status` | Restart worker on A; fake Sessions; cancel drain without operator | [phase1/06](../phase1/06_IDLE_GATE.md), [phase4/00](../phase4/00_OVERVIEW.md#furnace-polish-shipped-drain) |
| **Library disk** | Read A’s `library_disk check` | Auto-purge (parked in 06) | [phase4/06](../phase4/06_LIBRARY_DISK_ROTATE.md) |
| **Share / promote** | Flag candidates after 08 | Bypass Opt Out / tax / Ed25519 on A | [phase4/01](../phase4/01_PEER_SHARE_PATH.md) |
| **Display profiles** | Read A’s TV probe JSON | Auto-escalate 4K | [phase2/04](../phase2/04_ROKU_CHANNEL_POLISH.md) |
| **VoD camera** | Images snapshot; optional Static peek; follow NowPlaying **single sheep** | Playing POST; transcode; flock MP4 mount; MIPI as SoT; non-loop Items | [vod-as-camera](#vod-as-camera) |
| **Hammer** | Refuse | Any Hammer from a model | [phase3/07](../phase3/07_JELLYFLAM3_HAMMER.md) |
| **DeepDream** | Out of scope | Second renderer on A or B | [phase2/00](../phase2/00_OVERVIEW.md) |

### D — Operator chat (thin, on B)

Chat on **B** (“name this poster”, “breed something like `frosty_swirles`”) wraps the same apply path to **A**. It does not replace furnace healthcheck or the fridge card ([FRIDGE_CARD.md](../FRIDGE_CARD.md)).

## Work items (when Phase 5 opens)

### 1 — Runtime on B

1. One local stack: llama.cpp GGUF **or** Qualcomm AI Hub / QNN / LiteRT — [03](03_AI_PLATFORM_GAPS.md); headless. Conversion (export → INT4 → Hexagon compile) is the real engineering, not model shopping.
2. **Three Instruct INT4 graphs on disk**, **one** hot (default Qwen2.5 7B Instruct). Session switch: stop → `model_id` → start. **Do not** load Qwen 7B and Mistral 7B together.
3. systemd agent unit on **B** only.
4. **Vision pipeline:** small Adreno VLM co-resident with the hot HTP Instruct; pixels → text → Instruct JSON ([vision pipeline](#vision-pipeline)). Lab RSS ([03](03_AI_PLATFORM_GAPS.md#g18--hexagon--adreno-during-one-llm-runtime-investigation) H4). Not one-session HTP+GPU.
5. **VoD as camera:** Images shutter MVP on **single-sheep** Items; `jf3agent-vlm` + A ignore pattern; peek/follow-nowplaying default off ([vod-as-camera](#vod-as-camera)).

### 2 — Naming adapter

1. B: VLM caption + Instruct `suggest`; A: uniqueness + `--accept` → `alias_source=llm`.
2. Tests: sticky human; collision against **fixture catalog**; disabled-by-default; **no live network** in unit tests (fake B + fake A).
3. Runbook: curator CLI on A; “agent down” fallback.

### 3 — Breed adapter

1. JSON schema `{ mode, parents[], method?, rationale }` validated **before** A’s `pipeline.breed`.
2. Idle-breed on A: `llm_parents: false` by default; timeout → random.
3. Tests with `genomes/pedigree/` fixtures ([phase3/06](../phase3/06_GIT_PEDIGREE_SHEEP.md)).

### 4 — Agent wrapper (later)

1. Read-only against A: `healthcheck`, `status_report`, `sheep_naming resolve`, `library_disk check`.
2. Write: naming accept + breed on A; Shears/refactor behind confirms.
3. Deny: Hammer, `secrets.env` dump, peering Opt Out.

## Artifacts (planned)

| Artifact | Kind | Role |
|---|---|---|
| Agent service on B | deploy | Inference |
| Thin apply helpers on A (or SSH) | pipeline | `alias_source=llm`, breed argv |
| `naming.llm` / `breed.llm` on **A** yaml | config | Default off; furnace URL of B |
| This guide | docs | Split integration map |

## Non-goals

- Cloud LLM as the only path
- Writing aliases into genome `nick=`
- Auto-promote of LLM-named sheep
- Replacing idle-breed on A with a queue on B
- Training a flock LoRA as MVP
- STM32 as idle-gate
- In-process LLM inside `jellyflam3-worker`
- Pixels into the 7B Instruct graph; 7B VLM co-resident with 7B Instruct
- Catalog MP4 file ingest or MIPI/USB as the naming sensor
- Agent Sessions/Playing or transcode grabs
- Tuple / edge VoD as a camera target (single-sheep loops only)

## Exit criteria (when opened)

- [ ] LLM naming: B proposes, A writes `alias_source=llm`, `human` sticky; A ingest does not hang if B is down
- [ ] Breed brief → A’s `pipeline.breed`; tax + NC hold
- [ ] Furnace has **no** LLM systemd unit; Ventuno has **no** worker
- [ ] Session switch documented and labbed: Qwen ↔ Llama (or Mistral) via stop / config / start; one RSS 7–8B Instruct
- [ ] Vision pipeline: small GPU VLM + hot Instruct; pixels → caption → JSON; both resident or documented on-demand fallback
- [ ] VoD-as-camera: Images snapshot of a **single sheep** labbed without closing idle-gate; peek/follow flags default off
- [ ] Unit tests use fake A/B (CI offline) — fake caption string, no live VLM
- [ ] Cross-links from [phase4/09](../phase4/09_SHEEP_NAMING.md) § D and [phase2/07](../phase2/07_PEDIGREE_BREEDING.md) stay accurate

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [01_VENTUNO_Q_HOST.md](01_VENTUNO_Q_HOST.md) · [03_AI_PLATFORM_GAPS.md](03_AI_PLATFORM_GAPS.md) · [../phase4/09_SHEEP_NAMING.md](../phase4/09_SHEEP_NAMING.md) · [../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md) · [../phase4/08_VIEWER_FEEDBACK_LOOP.md](../phase4/08_VIEWER_FEEDBACK_LOOP.md) · [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) · [../phase3/09_SHEEP_REFACTOR.md](../phase3/09_SHEEP_REFACTOR.md)
