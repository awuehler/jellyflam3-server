# 05 — Shared sheep security (pre / post share)

## Boundary

Phase 3 guide 05 — **integrity and anti-tamper checks** for `.flam3` genomes that leave or enter a JellyFlam3 server via peering (Syncthing over Tailscale).

Complements Phase 2 sheep tax (XML/vocab hygiene) and peering (`*.flam3` only). This guide is about **trust between servers**, not license tagging.

**Status: complete** — Owner OK 2026-08-16 (Ed25519 + SHA-256 fallback; publish/promote gates; unit tests; fleet lab smoke **PASS 24/24**; fleet `PYTHONPATH=/opt/jellyflam3-server`).

## Locked decisions (2026-08-16)

| Decision | Choice |
|---|---|
| Artifact | **Ed25519** detached sig (`.flam3.jellyflam3.sig`) when device key exists |
| Fallback | **SHA-256** sidecar (`.flam3.sha256`) when signing is not possible |
| Pre-share | `python3 -m pipeline.peering publish` — sheep tax → write integrity → stage `peers/share-out` |
| Post-share | `promote` verifies integrity **before** sheep tax; fail closed → quarantine |
| Trust | Peer pubs in `trusted_keys_dir`; `peering trust-key`; own pub always trusted |
| Keys | `peering gen-keys` (also on Opt In); paths under `peering.share_security.*` |

## Threat model (short)

Opt-In peers are not a public CDN, but a compromised or malicious node could still push:

- Truncated / corrupted genomes that crash parsers or burn CPU
- Polyglot or non-flame payloads disguised as `.flam3`
- Tampered content after a “good” file was advertised

Goal: make silent malware / poison-genome spread between JellyFlam3 servers **hard** — signed hashes (preferred) or checksum sidecars plus pre/post share gates.

## Locked intent

| Gate | When | Action |
|---|---|---|
| **Pre-share (outbound)** | `peering publish` before stage to share-out | Tax → Ed25519 sig (or SHA-256 fallback); refuse if tax/integrity fails |
| **Post-share (inbound)** | On `promote` from `genomes/peers/inbox` | Verify sig/hash; on mismatch / missing / untrusted key → quarantine, never promote |
| **Alongside file** | Next to each shared `.flam3` | `*.flam3.jellyflam3.sig` and/or `*.flam3.sha256` |

Phase 2 `.stignore` allowlist now includes integrity sidecars (still never MP4/secrets) — see `deploy/peering/stignore`.

## Integrity artifact options

| Approach | Notes |
|---|---|
| **B. Detached Ed25519 (preferred)** | Sign canonical `jellyflam3-share-v1\n{name}\n{sha256}\n`; verify against trust store |
| **A. SHA-256 fallback** | When no private key / sign failure; detects bit-flips, not a malicious peer who rewrites both files |

Canonicalization: hash the **on-disk `.flam3` bytes** after sheep tax repair (or refuse share until tax `ok`/`repaired`).

## Pipeline sketch

```text
Outbound:  local genome → sheep tax → sign/hash → peers/share-out/
Inbound:   peers/inbox → verify hash/sig → sheep tax → gated promote → worker inbox
                              └ fail → quarantine + alert
```

## Work items (implementation)

1. ~~**Choose artifact format**~~ — **locked:** Ed25519 preferred; SHA-256 fallback
2. ~~**Pre-share writer**~~ — `pipeline.share_security.write_integrity` + `peering publish`
3. ~~**Post-share verifier**~~ — `verify_integrity` before tax in `peering promote`
4. ~~**Peering globs**~~ — `deploy/peering/stignore` allows `*.flam3.sha256` / `*.flam3.jellyflam3.sig`
5. ~~**Wire hooks**~~ — `pipeline/peering.py` publish / promote / gen-keys / trust-key
6. ~~**Ops logging**~~ — structured `share_security: { direction, result, reason }`
7. ~~**Tests**~~ — intact / tamper / missing sidecar (+ Ed25519 trust enroll)
8. ~~**Lab smoke**~~ — fleet matrix **PASS 24/24** 2026-08-16 (see below)
9. ~~**Docs**~~ — Phase 2 peering cross-link + this lab section; Phase 4 still owns promote-path / mesh scripting

## Lab smoke (fleet)

**Throwaway feedstock:** copy of `genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3`.

**Suite:**

| Script | Role |
|---|---|
| [`scripts/lab_smoke05_local.py`](../../scripts/lab_smoke05_local.py) | On-Pi: setup / publish / receive / trust / cleanup. Inserts repo root on `sys.path` (same pattern as `jellyfin_id_dump.py`) so `python3 scripts/…` works without a manual `PYTHONPATH`. |
| [`scripts/lab_smoke05_fleet.ps1`](../../scripts/lab_smoke05_fleet.ps1) | Windows operator: all publisher→receiver pairs × pathways A–D; sets `PYTHONPATH=/opt/jellyflam3-server` over SSH as belt-and-suspenders. |

**Pathways:** A happy Ed25519 · B tamper → quarantine · C missing sidecar → quarantine · D SHA-256 fallback.

**Pairs:** 04a→08a/16a · 08a→04a/16a · 16a→04a/08a (manual scp land; Syncthing not required for this smoke).

**Recorded result (2026-08-16):** **PASS 24 / 24** on tip with share-security. Keys under `var/share_security/` (gitignored).

```bash
# On any Pi after pull:
cd /opt/jellyflam3-server
python3 scripts/lab_smoke05_local.py setup
# Operator matrix from Windows:
# powershell -NoProfile -File scripts/lab_smoke05_fleet.ps1
```

## Guidelines

1. Host peering service owns key material and verify hooks — same Opt In/Out control plane as Phase 2 guide [05](../phase2/05_SYNCTHING_GENOME_PEERING.md).
2. Never execute genomes; treat as data only. Verification is cryptographic + schema (sheep tax), not “antivirus of flam3 semantics.”
3. Fail closed: missing sidecar, bad signature, or untrusted key = do not promote.
4. Rotate device signing keys with Opt Out / re-enroll; `trust-key` for peer pubs; document revocation in tailnet notes.
5. Logging: structured `share_security: { direction, result, reason }` for ops/`status_report`.
6. Lab-only escapes: `promote --skip-security`, `publish --skip-tax` — never fleet default.

## Non-goals

- Full malware sandbox / DRM
- Trusting archive Free Sheep mirrors (different threat; local hash optional)
- Blocking artistic “weird but valid” flam3 once integrity + tax pass
- Changing gated promote vs auto-ingest (that is [Phase 4 peer share path](../phase4/01_PEER_SHARE_PATH.md))

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/share_security.py` | pipeline | Hash / Ed25519 sign / verify / keygen |
| `*.flam3.jellyflam3.sig` | sidecar | Preferred integrity companion |
| `*.flam3.sha256` | sidecar | Fallback integrity companion |
| `peering publish` | CLI | Pre-share writer → `peers/share-out` |
| `peering promote` verify | CLI | Post-share gate before tax |
| `peering gen-keys` / `trust-key` | CLI | Device key + peer trust store |
| `scripts/lab_smoke05_local.py` | script | On-Pi lab pathways (auto `sys.path`) |
| `scripts/lab_smoke05_fleet.ps1` | script | Fleet matrix driver (Windows → Pis) |
| `deploy/peering/stignore` | deploy | Allow checksum/sig companions |
| `share_security` structured logs | ops | Direction / result / reason |

## Exit criteria

- [x] Pre-share: integrity artifact written for every outbound `.flam3` (`publish`)
- [x] Post-share: verify before promote; mismatch → quarantine
- [x] Sidecar formats documented; peering globs updated
- [x] Ed25519 preferred; SHA-256 fallback when keys unavailable
- [x] Unit: tamper / missing sidecar reject; intact pair promote OK
- [x] Lab smoke on fleet — **PASS 24/24** (2026-08-16; `scripts/lab_smoke05_*`)
- [x] Cross-link from Phase 2 peering + sheep tax guides
- [x] Owner OK 2026-08-16

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-16 | [x] |

## See also

[../phase2/05_SYNCTHING_GENOME_PEERING.md](../phase2/05_SYNCTHING_GENOME_PEERING.md) · [../phase2/06_SHEEP_TAX.md](../phase2/06_SHEEP_TAX.md) · [06_GIT_PEDIGREE_SHEEP.md](06_GIT_PEDIGREE_SHEEP.md) (in-repo pedigree ≠ peer share) · [../phase4/00_OVERVIEW.md](../phase4/00_OVERVIEW.md) · [00_OVERVIEW.md](00_OVERVIEW.md) · [`deploy/peering/README.md`](../../deploy/peering/README.md)
