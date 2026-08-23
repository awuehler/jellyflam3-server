"""Sheep refactor history helpers — pending companion + sidecar merge."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from pipeline.refactor_scan import find_catalog_mp4
from pipeline.stills import load_sidecar, sidecar_path_for_mp4, write_sidecar

log = logging.getLogger("jellyflam3.refactor")

REFACTOR_PENDING_SUFFIX = ".refactor.json"


def refactor_pending_path(flam3: Path) -> Path:
    """Companion beside an inbox ``.flam3``: ``{stem}.refactor.json``."""
    return flam3.with_name(f"{flam3.stem}{REFACTOR_PENDING_SUFFIX}")


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def build_refactor_history_entry(
    *,
    reason: str | None = None,
    score: float | None = None,
    score_reasons: list[str] | None = None,
    palette_before: dict[str, Any] | None = None,
    palette_after: dict[str, Any] | None = None,
    status: str = "staged",
    ts: str | None = None,
) -> dict[str, Any]:
    """One sidecar ``refactor[]`` entry (guide 09 shape)."""
    reasons: list[str] = []
    if reason:
        reasons.append(str(reason))
    for r in score_reasons or []:
        if r and r not in reasons:
            reasons.append(str(r))
    before = {"palette": dict(palette_before or {})}
    after = {"palette": dict(palette_after or {})}
    return {
        "ts": ts or _utc_now_iso(),
        "reason": reasons,
        "score": score,
        "before": before,
        "after": after,
        "palette": dict(palette_after or {}),
        "status": status,
    }


def write_refactor_pending(flam3: Path, entry: dict[str, Any]) -> Path:
    """Write pending history companion next to a staged inbox genome."""
    path = refactor_pending_path(flam3)
    payload = {"entries": [entry]}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def load_refactor_pending(flam3: Path) -> list[dict[str, Any]]:
    """Load pending ``.refactor.json`` entries beside an inbox genome (empty if absent)."""
    path = refactor_pending_path(flam3)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("refactor pending read failed for %s: %s", path, exc)
        return []
    if isinstance(data, list):
        return [e for e in data if isinstance(e, dict)]
    if isinstance(data, dict):
        entries = data.get("entries")
        if isinstance(entries, list):
            return [e for e in entries if isinstance(e, dict)]
        if data.get("ts") or data.get("palette") or data.get("before"):
            return [data]
    return []


def merge_refactor_history(
    prior: list[Any] | None,
    pending: list[Any] | None,
) -> list[dict[str, Any]]:
    """Concatenate prior + pending ``refactor`` entries; same ``ts`` → last wins."""
    by_ts: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    anon: list[dict[str, Any]] = []
    for raw in list(prior or []) + list(pending or []):
        if not isinstance(raw, dict):
            continue
        entry = dict(raw)
        ts = str(entry.get("ts") or "")
        if not ts:
            anon.append(entry)
            continue
        if ts not in by_ts:
            order.append(ts)
        by_ts[ts] = entry
    return [by_ts[t] for t in order] + anon


def append_catalog_refactor_history(
    cfg: dict[str, Any],
    sheep_id: str,
    entry: dict[str, Any],
) -> bool:
    """Append one entry to the live catalog sidecar ``refactor`` list (if MP4 exists)."""
    mp4 = find_catalog_mp4(cfg, sheep_id)
    if mp4 is None or not mp4.is_file():
        return False
    sc = load_sidecar(mp4)
    prior = sc.get("refactor") if isinstance(sc.get("refactor"), list) else []
    sc["refactor"] = merge_refactor_history(prior, [entry])
    write_sidecar(mp4, sc)
    return True


def merge_pending_refactor_into_sidecar(
    sidecar: dict[str, Any],
    *,
    catalog_mp4: Path | None = None,
    inbox_flam3: Path | None = None,
    ingest_status: str = "ingested",
) -> dict[str, Any]:
    """Merge prior catalog + pending inbox history into ``sidecar['refactor']``.

    Deletes the pending companion when present. Safe to call on every ingest.
    """
    prior: list[Any] = []
    if catalog_mp4 is not None:
        side_path = sidecar_path_for_mp4(catalog_mp4)
        if side_path.is_file():
            try:
                old = json.loads(side_path.read_text(encoding="utf-8"))
                if isinstance(old, dict) and isinstance(old.get("refactor"), list):
                    prior = list(old["refactor"])
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("prior refactor sidecar read failed for %s: %s", side_path, exc)
    pending: list[dict[str, Any]] = []
    if inbox_flam3 is not None:
        pending = load_refactor_pending(inbox_flam3)
        for e in pending:
            if e.get("status") == "staged":
                e["status"] = ingest_status
        pend_path = refactor_pending_path(inbox_flam3)
        if pend_path.is_file():
            try:
                pend_path.unlink()
            except OSError as exc:
                log.warning("could not remove refactor pending %s: %s", pend_path, exc)
    existing = sidecar.get("refactor") if isinstance(sidecar.get("refactor"), list) else []
    merged = merge_refactor_history(prior, list(existing) + pending)
    if merged:
        sidecar["refactor"] = merged
    return sidecar
