"""Purpose: FIFO order for genomes waiting in the worker inbox.

Requirements: Writable ledger beside the drain/status files (``inbox_fifo.json``).

Usage: Landings call ``stamp_inbox_arrival`` after the ``.flam3`` is in the inbox.
  The worker calls ``sync_inbox_fifo`` and claims ``queued[0]``.

Assumptions: Single worker. Filename order is not arrival order — archive ids and
  ``tuple`` / ``pedigree`` names sort in ASCII and can sit behind older files.
  The ledger remembers the first time each inode was seen so a later name cannot
  jump the queue. Files already present when the ledger is created are ordered by
  ctime (copy / cross-device move time). After that, new files go to the tail,
  and a batch first seen together is ordered by enqueue stamp (mtime) or ctime.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from pipeline.config import resolve_path

log = logging.getLogger("jellyflam3.inbox_queue")

LEDGER_NAME = "inbox_fifo.json"
_GENOME_SUFFIXES = (".flam3", ".flame")
_last_stamp_ns = 0


def inbox_fifo_path(cfg: dict[str, Any]) -> Path:
    """Ledger path: ``paths.inbox_fifo_file``, else beside drain or idle-gate status."""
    paths = cfg.get("paths") or {}
    if paths.get("inbox_fifo_file"):
        return resolve_path(cfg, "inbox_fifo_file")
    if paths.get("worker_drain_file"):
        return resolve_path(cfg, "worker_drain_file").parent / LEDGER_NAME
    if paths.get("status_file"):
        return resolve_path(cfg, "status_file").parent / LEDGER_NAME
    root = Path(cfg.get("_repo_root") or ".")
    return root / "var" / "lib" / "jellyflam3" / LEDGER_NAME


def stamp_inbox_arrival(path: Path) -> None:
    """Set mtime to enqueue time so a later scan can order a batch by arrival.

    ``os.utime`` also refreshes ctime on Linux, including after a same-filesystem
    rename that would otherwise keep the source inode's timestamps.
    """
    global _last_stamp_ns
    now = time.time_ns()
    if now <= _last_stamp_ns:
        now = _last_stamp_ns + 1
    _last_stamp_ns = now
    try:
        os.utime(path, ns=(now, now))
    except OSError as exc:
        log.warning("inbox arrival stamp failed for %s: %s", path.name, exc)


def sync_inbox_fifo(inbox: Path, ledger_path: Path) -> list[Path]:
    """Return inbox genomes oldest-arrival first, and persist that order.

    Sequence numbers already in the ledger stay put. Names that disappeared are
    dropped. Inodes the ledger has not seen are appended (never inserted by name).
    """
    present = _list_genomes(inbox)
    existed = ledger_path.is_file()
    state = _load(ledger_path)
    prev = state["files"]
    next_seq = state["next_seq"]

    kept: dict[str, dict[str, int]] = {}
    ordered: list[tuple[int, str, Path]] = []
    unknown: list[tuple[tuple[int, int, str], Path, os.stat_result]] = []

    for path in present:
        try:
            st = path.stat()
        except OSError:
            continue
        rec = prev.get(path.name)
        if rec is not None and rec["dev"] == int(st.st_dev) and rec["ino"] == int(st.st_ino):
            kept[path.name] = rec
            ordered.append((rec["seq"], path.name, path))
            continue
        unknown.append((_order_key(path, st, backlog=not existed), path, st))

    unknown.sort(key=lambda row: row[0])
    for _key, path, st in unknown:
        rec = {"seq": next_seq, "dev": int(st.st_dev), "ino": int(st.st_ino)}
        kept[path.name] = rec
        ordered.append((next_seq, path.name, path))
        next_seq += 1

    if kept:
        hi = max(rec["seq"] for rec in kept.values())
        if next_seq <= hi:
            next_seq = hi + 1

    ordered.sort()
    payload = {"next_seq": next_seq, "files": kept}
    if payload != {"next_seq": state["next_seq"], "files": prev}:
        _atomic_write(ledger_path, payload)
    return [path for _seq, _name, path in ordered]


def next_inbox_genome(inbox: Path, ledger_path: Path) -> Path | None:
    """Oldest queued genome, or None when the inbox has no ``.flam3`` / ``.flame``."""
    queued = sync_inbox_fifo(inbox, ledger_path)
    return queued[0] if queued else None


def _list_genomes(inbox: Path) -> list[Path]:
    if not inbox.is_dir():
        return []
    found: list[Path] = []
    try:
        entries = list(inbox.iterdir())
    except OSError as exc:
        log.warning("inbox unreadable %s: %s", inbox, exc)
        return []
    for path in entries:
        if path.suffix not in _GENOME_SUFFIXES:
            continue
        try:
            if path.is_file():
                found.append(path)
        except OSError:
            continue
    return found


def _order_key(path: Path, st: os.stat_result, *, backlog: bool) -> tuple[int, int, str]:
    """Backlog uses ctime. Later batches use the enqueue stamp, then ctime.

    A preserved source mtime must not move a newly copied file ahead of one
    that was stamped when it landed. ``max(ctime, mtime)`` is the stamp after
    ``stamp_inbox_arrival``, and it is ctime for a plain copy.
    """
    ctime_ns = int(st.st_ctime_ns)
    mtime_ns = int(st.st_mtime_ns)
    if backlog:
        return (ctime_ns, mtime_ns, path.name)
    return (max(ctime_ns, mtime_ns), mtime_ns, path.name)


def _load(ledger_path: Path) -> dict[str, Any]:
    empty: dict[str, Any] = {"next_seq": 1, "files": {}}
    if not ledger_path.is_file():
        return empty
    try:
        raw = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("unreadable inbox fifo ledger %s: %s", ledger_path, exc)
        return empty
    if not isinstance(raw, dict):
        return empty
    files_in = raw.get("files")
    files: dict[str, dict[str, int]] = {}
    if isinstance(files_in, dict):
        for name, rec in files_in.items():
            if not isinstance(name, str) or not isinstance(rec, dict):
                continue
            try:
                files[name] = {
                    "seq": int(rec["seq"]),
                    "dev": int(rec["dev"]),
                    "ino": int(rec["ino"]),
                }
            except (KeyError, TypeError, ValueError):
                continue
    try:
        next_seq = int(raw.get("next_seq") or 1)
    except (TypeError, ValueError):
        next_seq = 1
    if next_seq < 1:
        next_seq = 1
    return {"next_seq": next_seq, "files": files}


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
