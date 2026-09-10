# 02 — LLM Agent Platform ↔ furnace contracts

## Boundary

Map **deployment B** (local LLM / VLM on Ventuno) onto contracts that **already exist on deployment A** (Pi furnace). Host bring-up for B is [01](01_VENTUNO_Q_HOST.md). Gaps on B are [03](03_AI_PLATFORM_GAPS.md).

**Status:** Parked. Do not add model stubs to `jellyflam3-worker`, idle-breed, or naming **ingest on the furnace** until Owner opens this guide. RNG aliases already ship **on A** without an LLM ([phase4/09](../phase4/09_SHEEP_NAMING.md)).

Models on **B advise** (names, parent briefs, operator actions). **flam3-genome** and the **furnace worker** still **do**. B never becomes a second factory.

## Intent

| Surface | Where it runs | Prior SoT |
|---|---|---|
| **LLM poster naming** | VLM on **B**; `set-alias` / sidecar write on **A** | [phase4/09](../phase4/09_SHEEP_NAMING.md) § D; [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) |
| **LLM-assisted pedigree** | Brief on **B**; `pipeline.breed` / idle-breed on **A** | [phase2/07](../phase2/07_PEDIGREE_BREEDING.md) |
| **Vote-aware briefs** | Read `viewer_feedback` **from A’s sidecar** (when [phase4/08](../phase4/08_VIEWER_FEEDBACK_LOOP.md) opens) | [phase1/07](../phase1/07_LICENSE_AND_METADATA.md#catalog-sidecar-schema) |
| **Shears / refactor agent** | NL on **B** → CLI on **A** with confirm tokens | [phase3/03](../phase3/03_SHEEP_SHEARS.md), [phase3/09](../phase3/09_SHEEP_REFACTOR.md) |
| **Ops agent** | Explain gate/inbox using **A** JSON; later request drain on **A** | [phase1/09](../phase1/09_RUNTIME_AND_OPS.md), [phase4/00](../phase4/00_OVERVIEW.md#furnace-polish-parked--not-numbered) |
| **Share brief** | Propose candidates; Opt In + share-security still on **A** | [phase2/05](../phase2/05_SYNCTHING_GENOME_PEERING.md), [phase3/05](../phase3/05_SHARED_SHEEP_SECURITY.md), [phase4/01](../phase4/01_PEER_SHARE_PATH.md) |

```text
  A  Furnace catalog  (poster / sidecar / genomes/done)
           │  fetch over LAN (Jellyfin Images, SSH)
           ▼
  B  local VLM / LLM  (opt-in)
           │  structured JSON brief
           ▼
  A  uniqueness + license + tax gates
           │
           ├─► alias (alias_source=llm)     [phase4/09]   on A
           ├─► pipeline.breed argv           [phase2/07]  on A
           ├─► shears / refactor (confirm)   [phase3]     on A
           └─► operator notes (B logs ≠ sidecar SoT)
```

Arduino App Lab / Qualcomm AI Hub / llama.cpp / GenieX run on **B**. Canonical flock operators still use `python3 -m pipeline.*` **on A** (or a thin SSH wrapper from B).

## Locked product rules (design)

1. **A and B stay split.** No worker unit on Ventuno; no LLM unit on the Pi. See [00](00_OVERVIEW.md).
2. **flam3 stays the renderer (on A).** No “generate a sheep with the NPU.” VLM may look at **posters/stills** fetched from A ([phase1/05](../phase1/05_RENDER_PIPELINE.md)).
3. **Offline default on B.** `naming.llm.enabled` / `breed.llm.enabled` (names TBD) default **false** on the **furnace** side (A ignores B if unset). No cloud unless configured; no API keys in git ([phase4/09](../phase4/09_SHEEP_NAMING.md) rule 8).
4. **Sidecar SoT is on A.** Models do not get a flock database on B. Votes, aliases, license, pedigree hints stay on `{stem}.jellyflam3.json` beside the MP4 ([phase1/07](../phase1/07_LICENSE_AND_METADATA.md)).
5. **Human sticky.** Never overwrite `alias_source=human`. LLM apply only when source is `auto` or operator `--accept` **on A**.
6. **Not flam3 `nick`.** ([phase4/09](../phase4/09_SHEEP_NAMING.md) rule 5).
7. **Breed = flam3-genome on A.** B may pick parent stems + mode + method; it must not emit genome XML as SoT. Sheep tax still runs on A ([phase2/06](../phase2/06_SHEEP_TAX.md)).
8. **No AI-gate on the furnace.** Idle-gate remains TV Playing vs render ([phase1/06](../phase1/06_IDLE_GATE.md)). B may infer while A renders — that is the point of two boxes. B should still shed load if it overheats ([03](03_AI_PLATFORM_GAPS.md)).
9. **Confirm tokens stay on A.** Shears `DELETE`, refactor `APPLY` / `QUARANTINE` / `BATCH`, Hammer `HAMMER` are never auto-fired from B without the same operator confirm.
10. **Commercial / NC** still enforced on A ([phase1/07](../phase1/07_LICENSE_AND_METADATA.md)).
11. **Uniqueness** of aliases is computed against **A’s catalog** ([phase4/09](../phase4/09_SHEEP_NAMING.md) rule 3).

## Integration map (prior phases)

### A — Sheep naming (Phase 4 / 09 D)

**Already shipped on the furnace:** hash-seed RNG, ingest hook, backfill, `set-alias` / `clear-alias`, `alias_source` ∈ `auto|human|llm`.

**This slice adds:**

1. **B** fetches catalog `*-poster.jpg` (preferred) or a still ([phase2/02](../phase2/02_JELLYFIN_FLOCK_UX.md), [phase3/01](../phase3/01_SCREENSAVERS_AND_STILLS.md)). Never tuple stills if the stills pipeline excludes tuples.
2. **B** proposes an alias; optional rationale in **B** logs (or a sidecar field only if [phase1/07](../phase1/07_LICENSE_AND_METADATA.md) grows a reserved key).
3. **A** applies: `python3 -m pipeline.sheep_naming set-alias --source llm` (illustrative) after uniqueness check.
4. Pasture filename-vs-alias **toggle** stays Phase 4 / 09 C. Pasture still talks to **A**.

Furnace ingest must **not** block on B (timeout → keep `alias_source=auto`).

### B — LLM-assisted pedigree (Phase 2 / 07)

**Already shipped on the furnace:** `pipeline.breed`; idle cron; `origin: local_pedigree`; tax-parents; NC inheritance.

**This slice adds:**

1. **Parent picker brief on B** — compact cards from A (stem, alias, tags, duration, optional votes, poster thumb), not raw `.flam3` XML.
2. **Mode suggestion** — `mutate` / `cross` / `interpolate` (+ `method`).
3. **Idle policy (optional, default off) on A** — `cron_breed_idle` may **HTTP/SSH to B** for a parent pick, then run `pipeline.breed` **locally**. Gates stay on A: empty inbox, idle-gate, `archive_cron_imminent`, fingerprint dedup ([phase2/07](../phase2/07_PEDIGREE_BREEDING.md#daily-idle-breed-cron)). If B is down, idle-breed falls back to uniform random — furnace must not stall.
4. **Viewer weights** — when 08 ships, A’s sidecar integers win over B “remembering likes.”

Do **not** implement cloud-API pedigree **on the Pi** as a substitute for B.

### C — Other agentic vectors

| Vector | B may | Must not | Prior doc |
|---|---|---|---|
| **Shears** | Propose audit/sweep/delete list | Cascade delete without `DELETE` **on A** | [phase3/03](../phase3/03_SHEEP_SHEARS.md) |
| **Refactor** | Map “grey / muddy / frozen orbit” to pathways | `APPLY` without token on A | [phase3/09](../phase3/09_SHEEP_REFACTOR.md) |
| **Idle-gate / drain** | Explain A’s `idle_gate_status.json` | Restart worker on A; fake Sessions | [phase1/06](../phase1/06_IDLE_GATE.md) |
| **Library disk** | Read A’s `library_disk check` | Auto-purge (parked in 06) | [phase4/06](../phase4/06_LIBRARY_DISK_ROTATE.md) |
| **Share / promote** | Flag candidates after 08 | Bypass Opt Out / tax / Ed25519 on A | [phase4/01](../phase4/01_PEER_SHARE_PATH.md) |
| **Display profiles** | Read A’s TV probe JSON | Auto-escalate 4K | [phase2/04](../phase2/04_ROKU_CHANNEL_POLISH.md) |
| **Hammer** | Refuse | Any Hammer from a model | [phase3/07](../phase3/07_JELLYFLAM3_HAMMER.md) |
| **DeepDream** | Out of scope | Second renderer on A or B | [phase2/00](../phase2/00_OVERVIEW.md) |

### D — Operator chat (thin, on B)

Chat on **B** (“name this poster”, “breed something like `frosty_swirles`”) wraps the same apply path to **A**. It does not replace furnace healthcheck or the fridge card ([FRIDGE_CARD.md](../FRIDGE_CARD.md)).

## Work items (when Phase 5 opens)

### 1 — Runtime on B

1. One local stack: llama.cpp GGUF **or** Qualcomm AI Hub / GenieX — [03](03_AI_PLATFORM_GAPS.md); headless.
2. Small vision model + small text model; 16 GB on B is for models + OS, **not** Jellyfin + frames.
3. systemd agent unit on **B** only.

### 2 — Naming adapter

1. B: `suggest`; A: uniqueness + `--accept` → `alias_source=llm`.
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

## Exit criteria (when opened)

- [ ] LLM naming: B proposes, A writes `alias_source=llm`, `human` sticky; A ingest does not hang if B is down
- [ ] Breed brief → A’s `pipeline.breed`; tax + NC hold
- [ ] Furnace has **no** LLM systemd unit; Ventuno has **no** worker
- [ ] Unit tests use fake A/B (CI offline)
- [ ] Cross-links from [phase4/09](../phase4/09_SHEEP_NAMING.md) § D and [phase2/07](../phase2/07_PEDIGREE_BREEDING.md) stay accurate

## See also

[00_OVERVIEW.md](00_OVERVIEW.md) · [01_VENTUNO_Q_HOST.md](01_VENTUNO_Q_HOST.md) · [03_AI_PLATFORM_GAPS.md](03_AI_PLATFORM_GAPS.md) · [../phase4/09_SHEEP_NAMING.md](../phase4/09_SHEEP_NAMING.md) · [../phase2/07_PEDIGREE_BREEDING.md](../phase2/07_PEDIGREE_BREEDING.md) · [../phase4/08_VIEWER_FEEDBACK_LOOP.md](../phase4/08_VIEWER_FEEDBACK_LOOP.md) · [../phase3/03_SHEEP_SHEARS.md](../phase3/03_SHEEP_SHEARS.md) · [../phase3/09_SHEEP_REFACTOR.md](../phase3/09_SHEEP_REFACTOR.md)
