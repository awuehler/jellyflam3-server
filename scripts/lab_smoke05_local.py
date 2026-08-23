#!/usr/bin/env python3

"""Purpose: Fleet lab smoke for Phase 3 shared sheep security (guide 05).

Requirements: tip with ``pipeline.share_security``; pedigree smoke genome;
``python3-cryptography`` (or pip cryptography).
Usage (on Pi — always from repo root, or rely on auto PYTHONPATH):
  cd /opt/jellyflam3-server
  python3 scripts/lab_smoke05_local.py setup
  python3 scripts/lab_smoke05_local.py publish --path A|B|C|D --name STEM --out-dir DIR
  python3 scripts/lab_smoke05_local.py receive --path A|B|C|D --name STEM --inbox-src DIR
  python3 scripts/lab_smoke05_local.py cleanup --name STEM
  python3 scripts/lab_smoke05_local.py trust /path/to/peer.pub --name 08a

When to run: On each furnace Pi as driven by ``scripts/lab_smoke05_fleet.ps1``.
Success: Pathway A verifies; B tamper / C missing sidecar reject; D SHA-256 fallback.
Docs: docs/phase3/05_SHARED_SHEEP_SECURITY.md

Fleet matrix driver (Windows operator): ``scripts/lab_smoke05_fleet.ps1``.

Assumptions: Throwaway copies of ``genomes/pedigree/smoke/*.flam3``. Land may be
manual scp (not Syncthing). Keys under ``var/share_security/`` (gitignored via ``/var/``).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Repo root via script location (same pattern as jellyfin_id_dump.py) so
# ``python3 scripts/lab_smoke05_local.py`` works without an external PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CFG = "configs/jellyflam3.yaml"
PEDIGREE = ROOT / "genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3"
KEYS = ROOT / "var/share_security"
PRIV = KEYS / "ed25519.pem"
PUB = KEYS / "ed25519.pub"
TRUST = KEYS / "trusted"
WORK = ROOT / "var/lab_smoke05"


def _cfg():
    from pipeline.config import load_config

    return load_config(ROOT / CFG)


def setup() -> dict:
    KEYS.mkdir(parents=True, exist_ok=True)
    TRUST.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    from pipeline import share_security, peering

    cfg = _cfg()
    # Force key paths under repo var/ (yaml may omit share_security)
    cfg.setdefault("peering", {}).setdefault("share_security", {})
    ss = cfg["peering"]["share_security"]
    ss["enabled"] = True
    ss["prefer_ed25519"] = True
    ss["allow_sha256_fallback"] = True
    ss["private_key_file"] = str(PRIV)
    ss["public_key_file"] = str(PUB)
    ss["trusted_keys_dir"] = str(TRUST)
    peering.ensure_layout(cfg)
    keys = share_security.gen_keypair(cfg, overwrite=False)
    return {"ok": True, "keys": keys, "pub": str(PUB), "priv": str(PRIV)}


def _patch_cfg(cfg):
    cfg.setdefault("peering", {}).setdefault("share_security", {})
    ss = cfg["peering"]["share_security"]
    ss["enabled"] = True
    ss["prefer_ed25519"] = True
    ss["allow_sha256_fallback"] = True
    ss["private_key_file"] = str(PRIV)
    ss["public_key_file"] = str(PUB)
    ss["trusted_keys_dir"] = str(TRUST)
    return cfg


def trust_key(pub_path: Path, name: str) -> dict:
    from pipeline import share_security

    cfg = _patch_cfg(_cfg())
    return share_security.trust_public_key(cfg, pub_path, name=name)


def publish(path: str, name: str, out_dir: Path) -> dict:
    from pipeline import peering, share_security

    cfg = _patch_cfg(_cfg())
    if not PEDIGREE.is_file():
        return {"ok": False, "error": f"missing pedigree {PEDIGREE}"}
    out_dir.mkdir(parents=True, exist_ok=True)
    src = WORK / f"{name}.flam3"
    shutil.copy2(PEDIGREE, src)

    moved_priv = None
    try:
        if path == "D":
            # SHA-256 fallback: hide Ed25519 private key during publish
            if PRIV.is_file():
                moved_priv = PRIV.with_suffix(".pem.labhide")
                PRIV.rename(moved_priv)

        summary = peering.publish(cfg, [src], apply=True, skip_tax=False, move=False)
        entry = summary["results"][0]
        share_out = Path(peering.peers_share_out(cfg))
        staged = share_out / f"{name}.flam3"
        # Collect artifacts into out_dir for transfer
        for p in share_out.glob(f"{name}.flam3*"):
            shutil.copy2(p, out_dir / p.name)
        # Also copy any sidecars written beside source
        for p in src.parent.glob(f"{name}.flam3*"):
            if p.name != src.name or not (out_dir / p.name).exists():
                shutil.copy2(p, out_dir / p.name)

        result = {
            "ok": entry.get("action") == "publish",
            "path": path,
            "name": name,
            "action": entry.get("action"),
            "share_security": entry.get("share_security"),
            "staged": str(staged),
            "out_files": sorted(p.name for p in out_dir.glob(f"{name}*")),
        }
        if path == "D":
            alg = (entry.get("share_security") or {}).get("alg")
            result["ok"] = result["ok"] and alg == "sha256"
            result["expected_alg"] = "sha256"
            result["observed_alg"] = alg
        elif path == "A":
            alg = (entry.get("share_security") or {}).get("alg")
            result["ok"] = result["ok"] and alg == "ed25519"
            result["expected_alg"] = "ed25519"
            result["observed_alg"] = alg
        return result
    finally:
        if moved_priv is not None and moved_priv.is_file():
            moved_priv.rename(PRIV)


def receive(path: str, name: str, inbox_src: Path) -> dict:
    from pipeline import peering, share_security

    cfg = _patch_cfg(_cfg())
    peering.ensure_layout(cfg)
    inbox = Path(peering.peers_inbox(cfg))
    worker = Path(cfg["_repo_root"]) / "genomes" / "inbox"
    quarantine = Path(cfg["_repo_root"]) / "genomes" / "quarantine"

    # Clear prior leftovers for this stem
    for d in (inbox, worker, quarantine):
        for p in d.glob(f"{name}.flam3*"):
            p.unlink(missing_ok=True)

    flam = inbox_src / f"{name}.flam3"
    if not flam.is_file():
        return {"ok": False, "error": f"missing land file {flam}"}

    if path == "C":
        # Missing sidecar: copy flam3 only
        shutil.copy2(flam, inbox / flam.name)
    else:
        for p in inbox_src.glob(f"{name}.flam3*"):
            shutil.copy2(p, inbox / p.name)

    if path == "B":
        target = inbox / f"{name}.flam3"
        with target.open("ab") as fh:
            fh.write(b"\n<!--smoke05-tamper-->\n")

    summary = peering.promote(cfg, apply=True, skip_tax=False, skip_security=False)
    # Find our result
    entry = None
    for r in summary.get("results") or []:
        if Path(r.get("file", "")).name == f"{name}.flam3" or (
            r.get("dest") and Path(r["dest"]).name == f"{name}.flam3"
        ):
            entry = r
            break
    if entry is None and summary.get("results"):
        # Match by stem in any field
        for r in summary["results"]:
            blob = json.dumps(r)
            if name in blob:
                entry = r
                break

    in_inbox = (worker / f"{name}.flam3").is_file()
    in_quar = (quarantine / f"{name}.flam3").is_file()
    action = (entry or {}).get("action")
    sec = (entry or {}).get("share_security") or {}

    if path in ("A", "D"):
        expected_action = "promote"
        expected_loc = "inbox"
        ok = action == "promote" and in_inbox and not in_quar
    else:
        expected_action = "quarantine"
        expected_loc = "quarantine"
        ok = action == "quarantine" and in_quar and not in_inbox

    return {
        "ok": ok,
        "path": path,
        "name": name,
        "expected_action": expected_action,
        "observed_action": action,
        "expected_loc": expected_loc,
        "observed_inbox": in_inbox,
        "observed_quarantine": in_quar,
        "quarantine_reason": (entry or {}).get("quarantine_reason"),
        "share_security": sec,
        "entry": entry,
    }


def cleanup(name: str) -> dict:
    from pipeline import peering

    cfg = _patch_cfg(_cfg())
    peering.ensure_layout(cfg)
    removed = []
    roots = [
        Path(peering.peers_inbox(cfg)),
        Path(peering.peers_share_out(cfg)),
        Path(cfg["_repo_root"]) / "genomes" / "inbox",
        Path(cfg["_repo_root"]) / "genomes" / "quarantine",
        WORK,
    ]
    for root in roots:
        if not root.is_dir():
            continue
        for p in root.glob(f"{name}*"):
            p.unlink(missing_ok=True)
            removed.append(str(p))
    return {"removed": removed}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    p_trust = sub.add_parser("trust")
    p_trust.add_argument("pub")
    p_trust.add_argument("--name", required=True)
    p_pub = sub.add_parser("publish")
    p_pub.add_argument("--path", required=True, choices=list("ABCD"))
    p_pub.add_argument("--name", required=True)
    p_pub.add_argument("--out-dir", required=True)
    p_recv = sub.add_parser("receive")
    p_recv.add_argument("--path", required=True, choices=list("ABCD"))
    p_recv.add_argument("--name", required=True)
    p_recv.add_argument("--inbox-src", required=True)
    p_clean = sub.add_parser("cleanup")
    p_clean.add_argument("--name", required=True)
    args = ap.parse_args()

    if args.cmd == "setup":
        result = setup()
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok", True) else 1
    if args.cmd == "trust":
        result = trust_key(Path(args.pub), args.name)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok", True) else 1
    if args.cmd == "publish":
        result = publish(args.path, args.name, Path(args.out_dir))
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    if args.cmd == "receive":
        result = receive(args.path, args.name, Path(args.inbox_src))
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    if args.cmd == "cleanup":
        result = cleanup(args.name)
        print(json.dumps(result, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
