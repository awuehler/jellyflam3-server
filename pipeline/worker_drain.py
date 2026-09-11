#!/usr/bin/env python3
"""Purpose: Drain the furnace — finish the in-flight inbox job, then stop claiming.

Requirements: Writable ``paths.worker_drain_file`` (default beside idle-gate status);
job.json records under ``paths.jobs_dir`` to know if a render is still in flight.

Usage:
  python3 -m pipeline.worker_drain request
  python3 -m pipeline.worker_drain request --wait
  python3 -m pipeline.worker_drain status
  python3 -m pipeline.worker_drain wait
  python3 -m pipeline.worker_drain cancel

Assumptions: Drain is pause-before-next-inbox, not mid-frame. Flag persists across
worker restart until cancel. Distinct from idle-gate (TV Playing) and from an
empty inbox (seed/breed may still refill). ``--once`` is explicit and still runs.
Docs: docs/phase4/00_OVERVIEW.md (furnace polish), docs/phase1/05_RENDER_PIPELINE.md
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path
from pipeline.job_recovery import IN_FLIGHT, list_jobs, utc_now

log = logging.getLogger("jellyflam3.worker_drain")

DEFAULT_NAME = "worker_drain.json"
EXIT_OK = 0
EXIT_TIMEOUT = 1
EXIT_NOT_REQUESTED = 2


def drain_path(cfg: dict[str, Any]) -> Path:
    """Status JSON path: ``paths.worker_drain_file``, else beside idle-gate status."""
    paths = cfg.get("paths") or {}
    if paths.get("worker_drain_file"):
        return resolve_path(cfg, "worker_drain_file")
    if paths.get("status_file"):
        return resolve_path(cfg, "status_file").parent / DEFAULT_NAME
    root = Path(cfg.get("_repo_root") or ".")
    return root / "var" / "lib" / "jellyflam3" / DEFAULT_NAME


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON via a sibling tmp + replace so readers never see a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_flag(cfg: dict[str, Any]) -> dict[str, Any]:
    """Raw drain file, or empty dict when missing/unreadable."""
    path = drain_path(cfg)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("unreadable drain file %s: %s", path, exc)
        return {}
    return data if isinstance(data, dict) else {}


def is_drain_requested(cfg: dict[str, Any]) -> bool:
    """True when the operator asked the worker to stop claiming inbox genomes."""
    return bool(read_flag(cfg).get("drain"))


def in_flight_jobs(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Job.json records still queued/rendering/encoding/gating (claimed, not done)."""
    try:
        jobs_dir = resolve_path(cfg, "jobs_dir")
    except (KeyError, TypeError):
        return []
    rows: list[dict[str, Any]] = []
    for job in list_jobs(jobs_dir):
        if job.state not in IN_FLIGHT:
            continue
        rows.append(
            {
                "id": job.job_id,
                "state": job.state,
                "src": str(job.src) if job.src else None,
            }
        )
    return rows


def inbox_pending(cfg: dict[str, Any]) -> int:
    """Count of ``*.flam3`` / ``*.flame`` waiting in the inbox (not claimed)."""
    try:
        inbox = resolve_path(cfg, "genomes_inbox")
    except (KeyError, TypeError):
        return 0
    if not inbox.is_dir():
        return 0
    return len(list(inbox.glob("*.flam3"))) + len(list(inbox.glob("*.flame")))


def phase_for(requested: bool, in_flight: list[dict[str, Any]]) -> str:
    """``off`` | ``draining`` (job still in flight) | ``idle`` (safe to restart)."""
    if not requested:
        return "off"
    if in_flight:
        return "draining"
    return "idle"


def status_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    """Combined flag + in-flight jobs for CLI / healthcheck / status_report."""
    flag = read_flag(cfg)
    requested = bool(flag.get("drain"))
    inflight = in_flight_jobs(cfg)
    return {
        "drain": requested,
        "phase": phase_for(requested, inflight),
        "requested_at": flag.get("requested_at"),
        "cleared_at": flag.get("cleared_at"),
        "updated_at": utc_now(),
        "path": str(drain_path(cfg)),
        "in_flight": inflight,
        "inbox_pending": inbox_pending(cfg),
    }


def request_drain(cfg: dict[str, Any]) -> dict[str, Any]:
    """Set the persist-until-cancel flag. Idempotent; keeps the original timestamp."""
    path = drain_path(cfg)
    flag = read_flag(cfg)
    now = utc_now()
    if flag.get("drain"):
        requested_at = str(flag.get("requested_at") or now)
    else:
        requested_at = now
    payload = {
        "drain": True,
        "requested_at": requested_at,
        "cleared_at": None,
        "updated_at": now,
    }
    _atomic_write(path, payload)
    log.info("worker drain requested (%s)", path)
    return status_payload(cfg)


def cancel_drain(cfg: dict[str, Any]) -> dict[str, Any]:
    """Clear the flag so the running worker resumes claiming without a restart."""
    path = drain_path(cfg)
    flag = read_flag(cfg)
    now = utc_now()
    payload = {
        "drain": False,
        "requested_at": flag.get("requested_at"),
        "cleared_at": now,
        "updated_at": now,
    }
    _atomic_write(path, payload)
    log.info("worker drain cancelled (%s)", path)
    return status_payload(cfg)


def wait_until_idle(
    cfg: dict[str, Any],
    *,
    timeout_sec: float | None = None,
    poll_sec: float = 2.0,
) -> dict[str, Any]:
    """Block until phase is idle. Raises TimeoutError; ValueError if drain is off."""
    start = time.monotonic()
    interval = max(0.0, float(poll_sec))
    while True:
        snap = status_payload(cfg)
        if snap["phase"] == "off":
            raise ValueError("drain is not requested; run: python3 -m pipeline.worker_drain request")
        if snap["phase"] == "idle":
            return snap
        n = len(snap["in_flight"])
        if timeout_sec is not None:
            elapsed = time.monotonic() - start
            if elapsed >= float(timeout_sec) or float(timeout_sec) == 0:
                raise TimeoutError("still draining when timeout expired")
            remain = float(timeout_sec) - elapsed
            log.info("waiting for drain idle (%s in-flight job(s))", n)
            time.sleep(min(interval if interval > 0 else remain, remain))
        else:
            log.info("waiting for drain idle (%s in-flight job(s))", n)
            time.sleep(interval if interval > 0 else 2.0)


def _load_cfg(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        alt = Path("configs/jellyflam3.yaml.example")
        if alt.is_file():
            log.warning("config %s missing; using %s", config_path, alt)
            config_path = alt
        else:
            raise SystemExit(f"config not found: {config_path}")
    return load_config(config_path, strict_secrets=False)


def main(argv: list[str] | None = None) -> int:
    """CLI: request / cancel / status / wait for worker drain."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(
        description="Finish the current sheep, then pause inbox claiming until cancel"
    )
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    sub = p.add_subparsers(dest="cmd", required=True)

    req = sub.add_parser("request", help="Stop claiming after the current job finishes")
    req.add_argument("--wait", action="store_true", help="Block until no in-flight job remains")
    req.add_argument("--timeout-sec", type=float, default=None)
    req.add_argument("--poll-sec", type=float, default=2.0)

    sub.add_parser("status", help="Print drain flag + in-flight jobs as JSON")
    sub.add_parser("cancel", help="Resume claiming inbox (no worker restart)")
    sub.add_parser("resume", help="Alias for cancel")
    sub.add_parser("undrain", help="Alias for cancel")

    w = sub.add_parser("wait", help="Block until drain is idle (flag must already be set)")
    w.add_argument("--timeout-sec", type=float, default=None)
    w.add_argument("--poll-sec", type=float, default=2.0)

    args = p.parse_args(argv)
    cfg = _load_cfg(Path(args.config))

    if args.cmd in ("cancel", "resume", "undrain"):
        print(json.dumps(cancel_drain(cfg), indent=2))
        return EXIT_OK
    if args.cmd == "status":
        print(json.dumps(status_payload(cfg), indent=2))
        return EXIT_OK
    if args.cmd == "request":
        snap = request_drain(cfg)
        if not args.wait:
            print(json.dumps(snap, indent=2))
            return EXIT_OK
        try:
            snap = wait_until_idle(
                cfg, timeout_sec=args.timeout_sec, poll_sec=args.poll_sec
            )
        except TimeoutError as exc:
            print(json.dumps(status_payload(cfg), indent=2))
            log.error("%s", exc)
            return EXIT_TIMEOUT
        print(json.dumps(snap, indent=2))
        return EXIT_OK
    if args.cmd == "wait":
        try:
            snap = wait_until_idle(
                cfg, timeout_sec=args.timeout_sec, poll_sec=args.poll_sec
            )
        except ValueError as exc:
            print(json.dumps(status_payload(cfg), indent=2))
            log.error("%s", exc)
            return EXIT_NOT_REQUESTED
        except TimeoutError as exc:
            print(json.dumps(status_payload(cfg), indent=2))
            log.error("%s", exc)
            return EXIT_TIMEOUT
        print(json.dumps(snap, indent=2))
        return EXIT_OK
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
