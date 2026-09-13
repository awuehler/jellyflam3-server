"""Purpose: JellyFlam3 genome peering host service (Phase 2 guide 05 + Phase 3 share security).

Requirements: configs/jellyflam3.yaml peering.*; optional systemctl, Tailscale, Syncthing units;
deploy/peering/stignore; ``pipeline.share_security`` for pre/post share integrity.

Usage: ``python3 -m pipeline.peering status|opt-in|opt-out|publish|promote|ensure-layout|ensure-mesh-local|mesh-join|hygiene|gen-keys|trust-key``

Assumptions: Default is Opt Out. Sync = ``*.flam3`` + optional ``*-poster.jpg`` + integrity
sidecars via managed ``.stignore`` under peers/inbox; promote is gated (share security then
sheep tax) and moves companion posters when present.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path

log = logging.getLogger("jellyflam3.peering")

STIGNORE_NAME = ".stignore"
PEERS_FOLDER_ID = "jellyflam3-peers-inbox"
OPT_IN_NAME = "OPT_IN"
STATUS_DEFAULT = Path("/var/lib/jellyflam3/peering_status.json")
REPO_STIGNORE = Path("deploy/peering/stignore")
STIGNORE_FALLBACK = (
    "!*.flam3\n"
    "!*-poster.jpg\n"
    "!*.flam3.sha256\n"
    "!*.flam3.jellyflam3.sig\n"
    "*\n"
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def peering_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return dict(cfg.get("peering") or {})


def peers_root(cfg: dict[str, Any]) -> Path:
    """Resolve peers directory (default ``genomes/peers`` under repo root)."""
    p = peering_cfg(cfg)
    raw = p.get("peers_dir") or "genomes/peers"
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cfg["_repo_root"]) / path
    return path


def peers_inbox(cfg: dict[str, Any]) -> Path:
    """Resolve Syncthing receive inbox under peers root."""
    p = peering_cfg(cfg)
    raw = p.get("peers_inbox") or str(peers_root(cfg) / "inbox")
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cfg["_repo_root"]) / path
    return path


def peers_share_out(cfg: dict[str, Any]) -> Path:
    """Resolve outbound share folder under peers root."""
    return peers_root(cfg) / "share-out"


def opt_in_ack_path(cfg: dict[str, Any]) -> Path:
    """Path of the Opt-In acknowledgment file (presence = opted in)."""
    p = peering_cfg(cfg)
    raw = p.get("opt_in_ack") or str(peers_root(cfg) / OPT_IN_NAME)
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cfg["_repo_root"]) / path
    return path


def status_path(cfg: dict[str, Any]) -> Path:
    """JSON status file path (default ``/var/lib/jellyflam3/peering_status.json``)."""
    p = peering_cfg(cfg)
    raw = p.get("status_file") or str(STATUS_DEFAULT)
    path = Path(raw)
    if not path.is_absolute():
        path = Path(cfg["_repo_root"]) / path
    return path


def stignore_template(cfg: dict[str, Any]) -> Path:
    return Path(cfg["_repo_root"]) / REPO_STIGNORE


def write_stignore(inbox: Path, template: Path) -> Path:
    """Install managed ``.stignore`` so genomes + posters + integrity sidecars sync."""
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / STIGNORE_NAME
    if template.is_file():
        dest.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        # Include-first: Syncthing ignores allowlist entries if * comes first.
        dest.write_text(STIGNORE_FALLBACK, encoding="utf-8")
    return dest


def ensure_layout(cfg: dict[str, Any]) -> dict[str, Any]:
    """Create peers dirs (inbox, share-out) and write ``.stignore``; return paths."""
    root = peers_root(cfg)
    inbox = peers_inbox(cfg)
    share_out = peers_share_out(cfg)
    root.mkdir(parents=True, exist_ok=True)
    inbox.mkdir(parents=True, exist_ok=True)
    share_out.mkdir(parents=True, exist_ok=True)
    st = write_stignore(inbox, stignore_template(cfg))
    return {
        "peers_root": str(root),
        "peers_inbox": str(inbox),
        "share_out": str(share_out),
        "stignore": str(st),
    }


def syncthing_home(cfg: dict[str, Any]) -> Path:
    """Managed Syncthing HOME (config under ``$HOME/.local/state/syncthing``)."""
    raw = (peering_cfg(cfg).get("syncthing") or {}).get("home") or "/var/lib/jellyflam3/syncthing"
    path = Path(str(raw))
    if not path.is_absolute():
        path = Path(cfg.get("_repo_root") or ".") / path
    return path


def _syncthing_env(cfg: dict[str, Any]) -> dict[str, str]:
    env = os.environ.copy()
    env["HOME"] = str(syncthing_home(cfg))
    return env


def _syncthing_cli(
    cfg: dict[str, Any],
    args: list[str],
    *,
    dry_run: bool = False,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return _run(
        ["syncthing", "cli", *args],
        dry_run=dry_run,
        env=_syncthing_env(cfg),
        input_text=input_text,
    )


def ensure_mesh_local(cfg: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Option A: dirs + .stignore + discovery harden + local folder id (no peer IDs)."""
    layout = ensure_layout(cfg)
    steps: list[str] = ["layout"]
    inbox = str(peers_inbox(cfg).resolve())
    out: dict[str, Any] = {
        "ok": True,
        "action": "ensure-mesh-local",
        "layout": layout,
        "folder_id": PEERS_FOLDER_ID,
        "folder_path": inbox,
        "steps": steps,
        "dry_run": dry_run,
    }
    if not _have("syncthing"):
        steps.append("syncthing missing")
        out["ok"] = True
        out["reason"] = "syncthing_missing"
        return out

    for flag in ("global-ann-enabled", "relays-enabled", "natenabled"):
        proc = _syncthing_cli(
            cfg, ["config", "options", flag, "set", "false"], dry_run=dry_run
        )
        steps.append(f"{flag} rc={proc.returncode}")

    listed = _syncthing_cli(cfg, ["config", "folders", "list"], dry_run=dry_run)
    already = PEERS_FOLDER_ID in (listed.stdout or "")
    if already:
        steps.append("folder exists")
        return out

    my_id_proc = _run(
        ["syncthing", "--device-id"],
        dry_run=dry_run,
        env=_syncthing_env(cfg),
    )
    my_id = (my_id_proc.stdout or "").strip()
    folder_doc = {
        "id": PEERS_FOLDER_ID,
        "label": PEERS_FOLDER_ID,
        "path": inbox,
        "type": "sendreceive",
        "devices": ([{"deviceID": my_id}] if my_id else []),
    }
    add = _syncthing_cli(
        cfg,
        ["config", "folders", "add-json"],
        dry_run=dry_run,
        input_text=json.dumps(folder_doc),
    )
    steps.append(f"folders add-json rc={add.returncode}")
    if add.returncode != 0 and not dry_run:
        err = (add.stderr or add.stdout or "")[:400]
        if "duplicate" in err.lower() or "already" in err.lower():
            steps.append("folder already present")
        else:
            out["ok"] = False
            out["reason"] = err or "folders_add_failed"
    return out


def load_peers_file(path: Path) -> list[dict[str, Any]]:
    """Parse gitignored peer list (JSON object with ``peers`` or a JSON array)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        items = raw.get("peers") or raw.get("devices") or []
    else:
        items = raw
    if not isinstance(items, list):
        raise ValueError("peers file must be a list or {peers: [...]}")
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        did = str(item.get("deviceID") or item.get("device_id") or "").strip()
        ip = str(item.get("tailscaleIP") or item.get("tailscale_ip") or "").strip()
        name = str(item.get("name") or did[:8] or "peer").strip()
        if not did or did.startswith("REPLACE") or not ip or ip.startswith("100.x"):
            continue
        out.append(
            {
                "name": name,
                "deviceID": did,
                "tailscaleIP": ip,
                "introducer": bool(item.get("introducer")),
            }
        )
    return out


def mesh_join(
    cfg: dict[str, Any],
    peers_file: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Option B: add-json devices + share folder from a host-local peers file."""
    local = ensure_mesh_local(cfg, dry_run=dry_run)
    payload: dict[str, Any] = {
        "ok": True,
        "action": "mesh-join",
        "peers_file": str(peers_file),
        "local": local,
        "added": [],
        "skipped": [],
        "dry_run": dry_run,
    }
    if not peers_file.is_file():
        payload["ok"] = False
        payload["reason"] = "peers_file_missing"
        return payload
    try:
        peers = load_peers_file(peers_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        payload["ok"] = False
        payload["reason"] = str(exc)
        return payload
    if not peers:
        payload["reason"] = "no_usable_peers"
        return payload
    if not _have("syncthing"):
        payload["reason"] = "syncthing_missing"
        payload["ok"] = True
        return payload

    for peer in peers:
        doc = {
            "deviceID": peer["deviceID"],
            "name": peer["name"],
            "addresses": [f"tcp://{peer['tailscaleIP']}:22000"],
            "introducer": peer["introducer"],
        }
        proc = _syncthing_cli(
            cfg,
            ["config", "devices", "add-json"],
            dry_run=dry_run,
            input_text=json.dumps(doc),
        )
        rec = {**peer, "rc": proc.returncode}
        err = (proc.stderr or proc.stdout or "")[:200]
        if proc.returncode != 0 and "duplicate" not in err.lower() and "already" not in err.lower():
            rec["error"] = err
            payload["skipped"].append(rec)
        else:
            payload["added"].append(rec)
            _syncthing_cli(
                cfg,
                [
                    "config",
                    "folders",
                    PEERS_FOLDER_ID,
                    "devices",
                    "add",
                    "--device-id",
                    peer["deviceID"],
                ],
                dry_run=dry_run,
            )
    return payload


def is_opted_in(cfg: dict[str, Any]) -> bool:
    return opt_in_ack_path(cfg).is_file()


def _run(
    cmd: list[str],
    *,
    dry_run: bool = False,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command (or no-op on dry-run); never raises on non-zero exit."""
    # Never log secrets (e.g. --auth-key=tskey-…).
    safe = []
    for part in cmd:
        if part.startswith("--auth-key="):
            safe.append("--auth-key=<redacted>")
        else:
            safe.append(part)
    log.info("%s%s", "DRY-RUN " if dry_run else "", " ".join(safe))
    if dry_run:
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
        env=env,
        input=input_text,
    )


def _systemctl(*args: str, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    """Run systemctl with sudo (jellyflam3 is not root; Opt In/Out manage units)."""
    return _run(["sudo", "systemctl", *args], dry_run=dry_run)


def _have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def unit_active(unit: str) -> str:
    """Return systemctl is-active string, or ``unknown`` if systemctl missing."""
    if not _have("systemctl"):
        return "unknown"
    proc = subprocess.run(
        ["systemctl", "is-active", unit], capture_output=True, text=True, check=False
    )
    return (proc.stdout or proc.stderr or "unknown").strip() or "unknown"


def tailscale_ready(ts: dict[str, Any]) -> bool:
    """True when Tailscale is installed, reporting OK, Running, and online."""
    if not ts.get("installed"):
        return False
    if not ts.get("ok"):
        return False
    if ts.get("backend_state") != "Running":
        return False
    return ts.get("online") is True


def _peer_is_furnace(peer: dict[str, Any], *, tag: str) -> bool:
    """True when a Tailscale Peer looks like a JellyFlam3 furnace (tag or hostname)."""
    want = str(tag or "tag:jellyflam3").lower()
    if not want.startswith("tag:"):
        want = f"tag:{want}"
    for t in peer.get("Tags") or []:
        raw = str(t).lower()
        tagged = raw if raw.startswith("tag:") else f"tag:{raw}"
        if tagged == want:
            return True
    host = f"{peer.get('HostName') or ''} {peer.get('DNSName') or ''}".lower()
    return "jellyflam3" in host


def count_online_furnace_peers_from_status(
    data: dict[str, Any],
    *,
    tag: str = "tag:jellyflam3",
) -> int:
    """Count online Tailscale peers that look like furnaces (excludes Self)."""
    peers = data.get("Peer") or {}
    if not isinstance(peers, dict):
        return 0
    n = 0
    for peer in peers.values():
        if not isinstance(peer, dict):
            continue
        if not peer.get("Online"):
            continue
        if _peer_is_furnace(peer, tag=tag):
            n += 1
    return n


def furnace_mesh_size(
    cfg: dict[str, Any],
    live: dict[str, Any] | None = None,
) -> int:
    """This furnace plus online jellyflam3 Tailscale peers.

    Opt Out, or Opt In that is not share-live, counts as **1** (standalone).
    Two or more means another furnace is actually on the mesh.
    """
    if not is_opted_in(cfg):
        return 1
    if live is None:
        live = assess_peering_readiness(cfg)
    if not live.get("share_live"):
        return 1
    others = int((live.get("tailscale") or {}).get("online_furnace_peers") or 0)
    return 1 + max(0, others)


def assess_peering_readiness(cfg: dict[str, Any]) -> dict[str, Any]:
    """Live Opt In / Syncthing / Tailscale readiness (never stale JSON)."""
    opted_in = is_opted_in(cfg)
    syncthing_unit = unit_active("jellyflam3-syncthing.service")
    ts = _tailscale_status_brief()
    inbox_count = len(list(peers_inbox(cfg).glob("*.flam3")))
    issues: list[str] = []
    if opted_in:
        if syncthing_unit != "active":
            issues.append(f"syncthing unit {syncthing_unit} (expected active)")
        if not tailscale_ready(ts):
            hint = ts.get("backend_state") or ts.get("error") or "not installed"
            issues.append(f"tailscale not connected ({hint})")
    share_live = opted_in and not issues
    return {
        "share_opt_in": opted_in,
        "syncthing_unit": syncthing_unit,
        "tailscale": ts,
        "inbox_flam3_count": inbox_count,
        "share_live": share_live,
        "issues": issues,
    }


def write_status(cfg: dict[str, Any], extra: dict[str, Any] | None = None) -> Path:
    """Refresh peering_status.json (opt-in, units, Tailscale, inbox count)."""
    path = status_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    pc = peering_cfg(cfg)
    live = assess_peering_readiness(cfg)
    body: dict[str, Any] = {
        "updated_at": _utc_now(),
        "share_opt_in": live["share_opt_in"],
        "share_live": live["share_live"],
        "share_issues": live["issues"],
        "opt_in_ack": str(opt_in_ack_path(cfg)),
        "peers_inbox": str(peers_inbox(cfg)),
        "sync_glob": pc.get("sync_glob") or "*.flam3",
        "share_pedigree_only_eventually": bool(
            pc.get("share_pedigree_only_eventually", True)
        ),
        "units": {
            "jellyflam3-syncthing": live["syncthing_unit"],
            "jellyflam3-peering": unit_active("jellyflam3-peering.service"),
        },
        "tailscale": live["tailscale"],
        "inbox_flam3_count": live["inbox_flam3_count"],
        "furnace_mesh_size": furnace_mesh_size(cfg, live=live),
    }
    if extra:
        body.update(extra)
    try:
        from pipeline.flock_artwork import posters_ingest_state

        body["posters"] = posters_ingest_state(
            cfg, mesh_size=body["furnace_mesh_size"]
        )
    except Exception as exc:  # noqa: BLE001
        body["posters"] = {"error": str(exc)}
    path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    return path


def _tailscale_status_brief() -> dict[str, Any]:
    """Compact Tailscale status dict for the peering status file."""
    if not _have("tailscale"):
        return {"installed": False}
    proc = subprocess.run(
        ["tailscale", "status", "--json"], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        return {"installed": True, "ok": False, "error": (proc.stderr or "").strip()[:200]}
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"installed": True, "ok": False, "error": "bad json"}
    self = data.get("Self") or {}
    return {
        "installed": True,
        "ok": True,
        "backend_state": data.get("BackendState"),
        "dns_name": self.get("DNSName"),
        "online": self.get("Online"),
        "online_furnace_peers": count_online_furnace_peers_from_status(data),
    }


def opt_in(cfg: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Enroll Tailscale (if key present), start Syncthing, write Opt-In ack."""
    layout = ensure_layout(cfg)
    pc = peering_cfg(cfg)
    tag = (pc.get("tailscale") or {}).get("tag") or "tag:jellyflam3"
    auth_env = (pc.get("tailscale") or {}).get("auth_key_env") or "TS_AUTHKEY"
    auth_key = os.environ.get(auth_env, "").strip()

    steps: list[str] = []
    if _have("tailscale"):
        if auth_key:
            cmd = [
                "sudo",
                "tailscale",
                "up",
                f"--auth-key={auth_key}",
                f"--advertise-tags={tag}",
                "--accept-routes=false",
            ]
            proc = _run(cmd, dry_run=dry_run)
            steps.append(f"tailscale up rc={proc.returncode}")
            if proc.returncode != 0 and not dry_run:
                log.warning("tailscale up failed: %s", (proc.stderr or proc.stdout)[:400])
        else:
            steps.append(f"skip tailscale up ({auth_env} unset)")
            log.warning(
                "%s not set — Tailscale enroll skipped; set pre-auth key in secrets.env",
                auth_env,
            )
    else:
        steps.append("tailscale binary missing")

    if _have("systemctl"):
        for unit in ("jellyflam3-syncthing.service", "jellyflam3-peering.service"):
            _systemctl("enable", unit, dry_run=dry_run)
            _systemctl("start", unit, dry_run=dry_run)
            steps.append(f"enable/start {unit}")
    else:
        steps.append("systemctl missing")

    try:
        mesh = ensure_mesh_local(cfg, dry_run=dry_run)
        steps.append(
            "ensure-mesh-local ok="
            + str(mesh.get("ok"))
            + (" reason=" + str(mesh["reason"]) if mesh.get("reason") else "")
        )
    except Exception as exc:  # noqa: BLE001
        steps.append(f"ensure-mesh-local skipped: {exc}")

    ack = opt_in_ack_path(cfg)
    if not dry_run:
        ack.parent.mkdir(parents=True, exist_ok=True)
        ack.write_text(
            json.dumps(
                {
                    "opted_in_at": _utc_now(),
                    "sync_glob": pc.get("sync_glob") or "*.flam3",
                    "tag": tag,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        try:
            from pipeline import share_security

            keys = share_security.gen_keypair(cfg, overwrite=False)
            steps.append(f"share_security keys key_id={keys.get('key_id')}")
        except Exception as exc:  # noqa: BLE001
            steps.append(f"share_security gen-keys skipped: {exc}")
    steps.append(f"wrote {ack}")

    status = write_status(cfg, {"last_action": "opt-in", "steps": steps, "layout": layout})
    live = assess_peering_readiness(cfg)
    if not dry_run and live["share_opt_in"] and not live["share_live"]:
        if ack.is_file():
            ack.unlink()
            steps.append(f"rolled back {ack} (share not live)")
        return {
            "ok": False,
            "opted_in": False,
            "share_live": False,
            "issues": live["issues"],
            "status_file": str(status),
            "steps": steps,
        }
    return {
        "ok": True,
        "opted_in": live["share_opt_in"],
        "share_live": live["share_live"],
        "status_file": str(status),
        "steps": steps,
    }


def opt_out(cfg: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    """Stop Syncthing, leave Tailscale flock, remove Opt-In ack. Keeps genome files."""
    steps: list[str] = []
    if _have("systemctl"):
        for unit in ("jellyflam3-syncthing.service", "jellyflam3-peering.service"):
            _systemctl("stop", unit, dry_run=dry_run)
            _systemctl("disable", unit, dry_run=dry_run)
            steps.append(f"stop/disable {unit}")

    if _have("tailscale"):
        # Prefer logout so node does not rejoin on reboot without Opt In.
        proc = _run(["sudo", "tailscale", "logout"], dry_run=dry_run)
        steps.append(f"tailscale logout rc={proc.returncode}")
        if proc.returncode != 0:
            proc2 = _run(["sudo", "tailscale", "down"], dry_run=dry_run)
            steps.append(f"tailscale down rc={proc2.returncode}")
    else:
        steps.append("tailscale binary missing")

    ack = opt_in_ack_path(cfg)
    if ack.is_file() and not dry_run:
        ack.unlink()
        steps.append(f"removed {ack}")
    elif dry_run:
        steps.append(f"would remove {ack}")

    status = write_status(cfg, {"last_action": "opt-out", "steps": steps})
    return {"ok": True, "opted_in": False, "status_file": str(status), "steps": steps}


def list_inbox_flam3(cfg: dict[str, Any]) -> list[Path]:
    """Sorted ``*.flam3`` paths in peers inbox (empty if missing)."""
    inbox = peers_inbox(cfg)
    if not inbox.is_dir():
        return []
    return sorted(inbox.glob("*.flam3"))


def _move_companions(src: Path, dest_dir: Path) -> list[str]:
    """Move integrity sidecars (and return moved paths as strings)."""
    from pipeline import share_security

    moved: list[str] = []
    for side in share_security.companion_integrity_paths(src):
        if side.is_file():
            dest = dest_dir / side.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(side), str(dest))
            moved.append(str(dest))
    return moved


def publish(
    cfg: dict[str, Any],
    sources: list[Path],
    *,
    apply: bool = False,
    skip_tax: bool = False,
    dry_run: bool = False,
    move: bool = False,
) -> dict[str, Any]:
    """Pre-share: sheep tax → integrity sidecar → copy/move into peers/share-out."""
    from pipeline import share_security

    ensure_layout(cfg)
    share_out = peers_share_out(cfg)
    tax_cfg = cfg.get("sheep_tax") or {}
    tax_enabled = bool(tax_cfg.get("enabled", True)) and not skip_tax

    results: list[dict[str, Any]] = []
    for raw in sources:
        src = Path(raw)
        entry: dict[str, Any] = {"file": str(src), "action": "skip"}
        if not src.is_file() or src.suffix != ".flam3":
            entry["action"] = "skip_missing"
            entry["share_security"] = {
                "ok": False,
                "result": "refuse",
                "reason": "not_a_flam3_file",
            }
            results.append(entry)
            continue

        if tax_enabled:
            try:
                from pipeline import sheep_tax

                tax = sheep_tax.scan_file(src, cfg)
                entry["tax"] = tax
                if not tax.get("ok"):
                    entry["action"] = "refuse_tax"
                    entry["share_security"] = {
                        "direction": "outbound",
                        "ok": False,
                        "result": "refuse",
                        "reason": "sheep_tax_failed",
                    }
                    results.append(entry)
                    continue
            except ImportError:
                entry["tax"] = {"ok": False, "status": "deferred"}
                entry["action"] = "blocked_pending_sheep_tax"
                results.append(entry)
                continue
        else:
            entry["tax"] = {"ok": True, "status": "skipped_by_flag"}

        # Write integrity beside source, then stage into share-out
        integrity = share_security.write_integrity(src, cfg)
        entry["share_security"] = integrity
        if not integrity.get("ok"):
            entry["action"] = "refuse_integrity"
            results.append(entry)
            continue

        dest = share_out / src.name
        poster_src = src.with_name(f"{src.stem}-poster.jpg")
        entry["action"] = "publish"
        entry["dest"] = str(dest)
        if apply and not dry_run:
            share_out.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                entry["action"] = "skip_exists"
            else:
                op = shutil.move if move else shutil.copy2
                op(str(src), str(dest))
                for side in share_security.companion_integrity_paths(src):
                    if side.is_file():
                        side_dest = share_out / side.name
                        op(str(side), str(side_dest))
                if poster_src.is_file():
                    poster_dest = share_out / poster_src.name
                    if not poster_dest.exists():
                        op(str(poster_src), str(poster_dest))
                        entry["poster_dest"] = str(poster_dest)
        else:
            entry["dest"] = str(dest)
        results.append(entry)

    summary = {
        "ok": True,
        "apply": apply,
        "move": move,
        "skip_tax": skip_tax,
        "candidates": len(sources),
        "results": results,
        "note": (
            "Pre-share: tax then integrity sidecar, then stage to peers/share-out. "
            "Default copy (leave source); --move overrides."
        ),
    }
    write_status(cfg, {"last_action": "publish", "publish": summary})
    return summary


def promote(
    cfg: dict[str, Any],
    *,
    apply: bool = False,
    skip_tax: bool = False,
    skip_security: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Gated promote: peers/inbox → genomes/inbox after share security + sheep tax.

    Without ``--apply``, only lists candidates. Never auto-drains on Opt In.
    Order: verify integrity → sheep tax → move (or quarantine).
    """
    from pipeline import share_security

    files = list_inbox_flam3(cfg)
    worker_inbox = resolve_path(cfg, "genomes_inbox")
    quarantine = resolve_path(cfg, "genomes_quarantine")
    tax_cfg = cfg.get("sheep_tax") or {}
    tax_enabled = bool(tax_cfg.get("enabled", True)) and bool(
        tax_cfg.get("on_peer_promote", True)
    )

    results: list[dict[str, Any]] = []
    for src in files:
        entry: dict[str, Any] = {"file": str(src), "action": "skip"}

        if skip_security:
            entry["share_security"] = {
                "ok": True,
                "result": "skipped",
                "reason": "skipped_by_flag",
            }
        else:
            sec = share_security.verify_integrity(src, cfg)
            entry["share_security"] = sec
            if not sec.get("ok"):
                entry["action"] = "quarantine"
                entry["quarantine_reason"] = "share_security"
                if apply and not dry_run:
                    quarantine.mkdir(parents=True, exist_ok=True)
                    dest = quarantine / src.name
                    shutil.move(str(src), str(dest))
                    entry["dest"] = str(dest)
                    entry["sidecars"] = _move_companions(src, quarantine)
                results.append(entry)
                continue

        if tax_enabled and not skip_tax:
            try:
                from pipeline import sheep_tax  # type: ignore

                tax = sheep_tax.scan_file(src, cfg)  # type: ignore[attr-defined]
                entry["tax"] = tax
                if not tax.get("ok"):
                    entry["action"] = "quarantine"
                    entry["quarantine_reason"] = "sheep_tax"
                    if apply and not dry_run:
                        quarantine.mkdir(parents=True, exist_ok=True)
                        dest = quarantine / src.name
                        shutil.move(str(src), str(dest))
                        entry["dest"] = str(dest)
                        entry["sidecars"] = _move_companions(src, quarantine)
                    results.append(entry)
                    continue
            except ImportError:
                entry["tax"] = {
                    "ok": False,
                    "status": "deferred",
                    "error": "pipeline.sheep_tax not implemented (guide 06)",
                }
                entry["action"] = "blocked_pending_sheep_tax"
                results.append(entry)
                continue
        elif skip_tax:
            entry["tax"] = {"ok": True, "status": "skipped_by_flag"}

        entry["action"] = "promote"
        dest = worker_inbox / src.name
        poster_src = src.with_name(f"{src.stem}-poster.jpg")
        poster_dest = worker_inbox / poster_src.name
        if poster_src.is_file():
            entry["poster"] = str(poster_src)
        if apply and not dry_run:
            worker_inbox.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                entry["action"] = "skip_exists"
                entry["dest"] = str(dest)
            else:
                shutil.move(str(src), str(dest))
                entry["dest"] = str(dest)
                entry["sidecars"] = _move_companions(src, worker_inbox)
                if poster_src.is_file() and not poster_dest.exists():
                    shutil.move(str(poster_src), str(poster_dest))
                    entry["poster_dest"] = str(poster_dest)
        else:
            entry["dest"] = str(dest)
            if poster_src.is_file():
                entry["poster_dest"] = str(poster_dest)
        results.append(entry)

    summary = {
        "ok": True,
        "apply": apply,
        "skip_tax": skip_tax,
        "skip_security": skip_security,
        "candidates": len(files),
        "results": results,
        "note": (
            "Gated promote: verify share security, then sheep tax, then move. "
            "No silent drain. --skip-tax / --skip-security are lab-only."
        ),
    }
    write_status(cfg, {"last_action": "promote", "promote": summary})
    return summary


def status_report(cfg: dict[str, Any]) -> dict[str, Any]:
    """Ensure layout, write status, return the status JSON body."""
    ensure_layout(cfg)
    path = write_status(cfg, {"last_action": "status"})
    return json.loads(path.read_text(encoding="utf-8"))


def list_peer_junk_files(cfg: dict[str, Any]) -> list[Path]:
    """Unexpected ``*.mp4`` under peers inbox / share-out / quarantine."""
    roots = [
        peers_inbox(cfg),
        peers_share_out(cfg),
        peers_root(cfg) / "quarantine",
    ]
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        found.extend(sorted(p for p in root.rglob("*.mp4") if p.is_file()))
    return found


def hygiene(cfg: dict[str, Any], *, apply: bool = False, dry_run: bool = False) -> dict[str, Any]:
    """Report or remove unexpected peer ``*.mp4`` files (flam3-first peering).

    Default is list-only. ``apply=True`` deletes; ``dry_run=True`` lists would-remove.
    """
    junk = list_peer_junk_files(cfg)
    removed: list[str] = []
    would: list[str] = []
    for p in junk:
        if dry_run or not apply:
            would.append(str(p))
            if dry_run:
                log.info("dry-run would remove peer junk %s", p)
        else:
            p.unlink(missing_ok=True)
            removed.append(str(p))
            log.info("removed peer junk %s", p)
    return {
        "peer_junk": [str(p) for p in junk],
        "would_remove": would if (dry_run or not apply) else [],
        "removed": removed,
        "apply": apply and not dry_run,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry for peering subcommands; returns process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--config", default="configs/jellyflam3.yaml")

    ap = argparse.ArgumentParser(
        description="JellyFlam3 peering host service (guide 05)",
        parents=[parent],
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show Opt In / unit / Tailscale status", parents=[parent])
    sub.add_parser("ensure-layout", help="Create peers dirs + .stignore", parents=[parent])
    p_mesh = sub.add_parser(
        "ensure-mesh-local",
        help="Option A: layout + discovery harden + local folder id (no peer IDs)",
        parents=[parent],
    )
    p_mesh.add_argument("--dry-run", action="store_true")
    p_join = sub.add_parser(
        "mesh-join",
        help="Option B: add-json devices from a gitignored peers file",
        parents=[parent],
    )
    p_join.add_argument(
        "--peers-file",
        type=Path,
        default=Path("configs/peering-peers.json"),
        help="Host-local JSON (never commit real device IDs)",
    )
    p_join.add_argument("--dry-run", action="store_true")

    p_in = sub.add_parser(
        "opt-in", help="Opt In: Tailscale enroll + start Syncthing", parents=[parent]
    )
    p_in.add_argument("--dry-run", action="store_true")

    p_out = sub.add_parser(
        "opt-out", help="Opt Out: stop Syncthing + Tailscale logout", parents=[parent]
    )
    p_out.add_argument("--dry-run", action="store_true")

    p_pub = sub.add_parser(
        "publish",
        help="Pre-share: tax + integrity → peers/share-out",
        parents=[parent],
    )
    p_pub.add_argument("flam3", nargs="+", type=Path, help=".flam3 file(s) to publish")
    p_pub.add_argument(
        "--apply",
        action="store_true",
        help="Actually copy/move into share-out (default: plan only)",
    )
    p_pub.add_argument(
        "--move",
        action="store_true",
        help="Move source into share-out (default: copy, leave source)",
    )
    p_pub.add_argument(
        "--skip-tax",
        action="store_true",
        help="Lab only: publish without sheep tax",
    )
    p_pub.add_argument("--dry-run", action="store_true")

    p_prom = sub.add_parser(
        "promote",
        help="Gated promote from peers/inbox → genomes/inbox (security + sheep tax)",
        parents=[parent],
    )
    p_prom.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files (default: list only)",
    )
    p_prom.add_argument(
        "--skip-tax",
        action="store_true",
        help="Lab only: promote without sheep tax (blocked by default when tax missing)",
    )
    p_prom.add_argument(
        "--skip-security",
        action="store_true",
        help="Lab only: promote without share-security verify",
    )
    p_prom.add_argument("--dry-run", action="store_true")

    p_hyg = sub.add_parser(
        "hygiene",
        help="List/remove unexpected *.mp4 under peers dirs (default: list only)",
        parents=[parent],
    )
    p_hyg.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete unexpected peer MP4s",
    )
    p_hyg.add_argument("--dry-run", action="store_true")

    p_keys = sub.add_parser(
        "gen-keys",
        help="Generate Ed25519 share-security keypair (no overwrite by default)",
        parents=[parent],
    )
    p_keys.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing private/public key files",
    )

    p_trust = sub.add_parser(
        "trust-key",
        help="Add a peer Ed25519 public key to the trust store",
        parents=[parent],
    )
    p_trust.add_argument("pubkey", type=Path, help="Path to peer .pub (32-byte raw or PEM)")
    p_trust.add_argument("--name", default=None, help="Optional filename stem in trusted_keys_dir")

    args = ap.parse_args(argv)
    cfg = load_config(args.config)

    if args.cmd == "status":
        print(json.dumps(status_report(cfg), indent=2))
        return 0
    if args.cmd == "ensure-layout":
        print(json.dumps(ensure_layout(cfg), indent=2))
        write_status(cfg, {"last_action": "ensure-layout"})
        return 0
    if args.cmd == "ensure-mesh-local":
        payload = ensure_mesh_local(cfg, dry_run=args.dry_run)
        print(json.dumps(payload, indent=2))
        write_status(cfg, {"last_action": "ensure-mesh-local", "mesh": payload})
        return 0 if payload.get("ok") else 1
    if args.cmd == "mesh-join":
        payload = mesh_join(cfg, args.peers_file, dry_run=args.dry_run)
        print(json.dumps(payload, indent=2))
        write_status(cfg, {"last_action": "mesh-join", "mesh": payload})
        return 0 if payload.get("ok") else 1
    if args.cmd == "opt-in":
        print(json.dumps(opt_in(cfg, dry_run=args.dry_run), indent=2))
        return 0
    if args.cmd == "opt-out":
        print(json.dumps(opt_out(cfg, dry_run=args.dry_run), indent=2))
        return 0
    if args.cmd == "publish":
        print(
            json.dumps(
                publish(
                    cfg,
                    list(args.flam3),
                    apply=args.apply,
                    skip_tax=args.skip_tax,
                    dry_run=args.dry_run,
                    move=args.move,
                ),
                indent=2,
            )
        )
        return 0
    if args.cmd == "promote":
        print(
            json.dumps(
                promote(
                    cfg,
                    apply=args.apply,
                    skip_tax=args.skip_tax,
                    skip_security=args.skip_security,
                    dry_run=args.dry_run,
                ),
                indent=2,
            )
        )
        return 0
    if args.cmd == "hygiene":
        print(
            json.dumps(
                hygiene(cfg, apply=args.apply, dry_run=args.dry_run),
                indent=2,
            )
        )
        return 0
    if args.cmd == "gen-keys":
        from pipeline import share_security

        print(json.dumps(share_security.gen_keypair(cfg, overwrite=args.overwrite), indent=2))
        return 0
    if args.cmd == "trust-key":
        from pipeline import share_security

        print(
            json.dumps(
                share_security.trust_public_key(cfg, args.pubkey, name=args.name),
                indent=2,
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
