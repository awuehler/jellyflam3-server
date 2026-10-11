#!/usr/bin/env python3
"""Purpose: Read-only flock size, condition, status, votes, and history.

Requirements: Catalog under ``paths.media_library``; optional jobs, inbox,
quarantine, idle-gate, drain, and breed-history files. Does not write them.

Usage:
  python3 -m pipeline.flock_report
  python3 -m pipeline.flock_report --json
  python3 -m pipeline.flock_report --stem frosty_swirles
  python3 -m pipeline.flock_report --stem electricsheep.247.00505 --score

Assumptions: Live flock is ``by-generation`` only. ``_refactor-preview`` and
``_refactor-quarantine`` are counted apart from that flock. Voting reads
sidecar ``viewer_feedback`` and does not cast or sweep. History is the newest
breed, job, refactor, park, and last-vote timestamps. ``--score`` is the only
path that re-scores genomes. Thermals stay on ``scripts/status_report.sh``.
Exit 0. An unknown ``adjective_surname`` exits 2.
Docs: docs/USER_GUIDE_AND_RUNBOOK.md
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path
from pipeline.inbox_queue import inbox_fifo_path
from pipeline.media_layout import (
    REFACTOR_PREVIEW_DIRNAME,
    REFACTOR_QUARANTINE_DIRNAME,
    is_unpublished_media_path,
)
from pipeline.sheep_naming import alias_of, resolve_sheep_token
from pipeline.sheep_names import catalog_generation
from pipeline.sheep_tuple import is_tuple_stem
from pipeline.sheep_votes import normalize_feedback

_GENOME_SUFFIXES = (".flam3", ".flame")


def _optional_path(cfg: dict[str, Any], key: str) -> Path | None:
    try:
        return resolve_path(cfg, key)
    except (KeyError, TypeError, ValueError):
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _parse_ts(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt_ts(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mtime_ts(path: Path) -> str | None:
    try:
        stamped = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    except OSError:
        return None
    return _fmt_ts(stamped)


def _genomes(directory: Path | None) -> list[Path]:
    if directory is None or not directory.is_dir():
        return []
    found: list[Path] = []
    try:
        entries = list(directory.iterdir())
    except OSError:
        return []
    for path in entries:
        if path.suffix.lower() not in _GENOME_SUFFIXES:
            continue
        try:
            if path.is_file():
                found.append(path)
        except OSError:
            continue
    return found


def iter_live_mp4s(media_root: Path) -> list[Path]:
    """Catalog MP4s under ``by-generation``, skipping parked ``_`` trees and stills."""
    root = Path(media_root) / "by-generation"
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*.mp4")):
        if any(part.startswith("_") for part in path.parts):
            continue
        if "stills" in path.parts:
            continue
        out.append(path)
    return out


def _sidecar_for_mp4(mp4: Path) -> dict[str, Any]:
    path = mp4.with_name(mp4.stem + ".jellyflam3.json")
    data = _load_json(path)
    return data or {}


def _count_mp4s(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(1 for path in root.rglob("*.mp4") if "stills" not in path.parts)


def _fmt_bytes(n: int) -> str:
    if n >= 1024**3:
        return f"{n / 1024**3:.1f} GiB"
    if n >= 1024**2:
        return f"{n / 1024**2:.1f} MiB"
    return f"{n} B"


def _fmt_duration(seconds: float) -> str:
    if seconds >= 60:
        return f"{seconds / 60:.1f} min"
    return f"{seconds:.1f}s"


def _license_text(counts: dict[str, int]) -> str:
    order = ["cc-by", "cc-by-nc", "unknown"]
    keys = list(order)
    for key in sorted(counts):
        if key not in keys:
            keys.append(key)
    return ", ".join(f"{key} {counts.get(key, 0)}" for key in keys)


def _generation_text(counts: dict[str, int]) -> str:
    return "  ".join(f"{key}:{counts[key]}" for key in sorted(counts))


def inbox_snapshot(cfg: dict[str, Any]) -> dict[str, Any]:
    """Inbox depth and FIFO head. Reads the ledger and does not write it."""
    inbox = _optional_path(cfg, "genomes_inbox")
    files = _genomes(inbox)
    head: str | None = None
    if files:
        by_name = {path.name: path for path in files}
        ordered: list[tuple[int, Path]] = []
        known: set[str] = set()
        ledger = _load_json(inbox_fifo_path(cfg)) or {}
        recorded = ledger.get("files") if isinstance(ledger.get("files"), dict) else {}
        for path in files:
            rec = recorded.get(path.name) if isinstance(recorded, dict) else None
            if not isinstance(rec, dict):
                continue
            try:
                st = path.stat()
                if int(rec["dev"]) != int(st.st_dev) or int(rec["ino"]) != int(st.st_ino):
                    continue
                ordered.append((int(rec["seq"]), path))
                known.add(path.name)
            except (KeyError, TypeError, ValueError, OSError):
                continue
        if ordered:
            ordered.sort(key=lambda row: (row[0], row[1].name))
            head = ordered[0][1].stem
        else:
            unknown = [by_name[name] for name in by_name if name not in known]
            unknown.sort(key=lambda path: (path.stat().st_ctime_ns, path.name))
            if unknown:
                head = unknown[0].stem
    return {"count": len(files), "head": head}


def _sheep_rows(media_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for mp4 in iter_live_mp4s(media_root):
        side = _sidecar_for_mp4(mp4)
        stem = mp4.stem
        try:
            size = mp4.stat().st_size
        except OSError:
            size = 0
        try:
            duration = float(side["duration_sec"]) if side.get("duration_sec") is not None else 0.0
        except (TypeError, ValueError):
            duration = 0.0
        license_name = str(side.get("license") or "unknown")
        kind = "tuple" if is_tuple_stem(stem) or str(side.get("type") or "") == "tuple" else "loop"
        feedback = normalize_feedback(side.get("viewer_feedback"))
        rows.append(
            {
                "stem": stem,
                "alias": alias_of(side) or None,
                "generation": catalog_generation(stem),
                "kind": kind,
                "license": license_name,
                "duration_sec": duration,
                "bytes": size,
                "signals": side.get("signals") if isinstance(side.get("signals"), dict) else None,
                "refactor": side.get("refactor") if isinstance(side.get("refactor"), list) else [],
                "feedback": feedback,
                "mp4": mp4,
            }
        )
    return rows


def _size_block(rows: list[dict[str, Any]], cfg: dict[str, Any], media: Path) -> dict[str, Any]:
    licenses: dict[str, int] = {}
    generations: dict[str, int] = {}
    for row in rows:
        licenses[row["license"]] = licenses.get(row["license"], 0) + 1
        generations[row["generation"]] = generations.get(row["generation"], 0) + 1
    inbox = inbox_snapshot(cfg)
    quarantine = _optional_path(cfg, "genomes_quarantine")
    return {
        "sheep": len(rows),
        "loops": sum(1 for row in rows if row["kind"] == "loop"),
        "tuples": sum(1 for row in rows if row["kind"] == "tuple"),
        "duration_sec": round(sum(row["duration_sec"] for row in rows), 3),
        "duration": _fmt_duration(sum(row["duration_sec"] for row in rows)),
        "bytes": sum(row["bytes"] for row in rows),
        "catalog_bytes": _fmt_bytes(sum(row["bytes"] for row in rows)),
        "license": licenses,
        "license_text": _license_text(licenses),
        "alias_present": sum(1 for row in rows if row["alias"]),
        "alias_missing": sum(1 for row in rows if not row["alias"]),
        "by_generation": generations,
        "by_generation_text": _generation_text(generations),
        "inbox_flam3": inbox["count"],
        "inbox_head": inbox["head"],
        "quarantine_flam3": len(_genomes(quarantine)),
        "parked_catalog": _count_mp4s(media / REFACTOR_QUARANTINE_DIRNAME),
        "preview_catalog": _count_mp4s(media / REFACTOR_PREVIEW_DIRNAME),
    }


def _one_size(row: dict[str, Any] | None, stem: str) -> dict[str, Any]:
    if row is None:
        return {
            "stem": stem,
            "alias": None,
            "generation": catalog_generation(stem),
            "kind": "tuple" if is_tuple_stem(stem) else "loop",
            "license": "unknown",
            "duration_sec": 0.0,
            "duration": "0.0s",
            "bytes": 0,
            "catalog_bytes": "0 B",
            "in_catalog": False,
        }
    return {
        "stem": row["stem"],
        "alias": row["alias"],
        "generation": row["generation"],
        "kind": row["kind"],
        "license": row["license"],
        "duration_sec": row["duration_sec"],
        "duration": _fmt_duration(row["duration_sec"]),
        "bytes": row["bytes"],
        "catalog_bytes": _fmt_bytes(row["bytes"]),
        "in_catalog": True,
    }


def _live_audit_bases(audit: Any) -> set[str]:
    live: set[str] = set()
    for base, kinds in audit.sheep.items():
        paths: list[Path] = []
        for key in ("mp4", "poster", "sidecar"):
            paths.extend(kinds.get(key) or [])
        if any(not is_unpublished_media_path(path) for path in paths):
            live.add(base)
    return live


def _condition_block(
    cfg: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    stem: str | None,
    score: bool,
) -> dict[str, Any]:
    from pipeline.shears import audit_flock

    audit = audit_flock(cfg)
    live = _live_audit_bases(audit)
    if stem:
        live = {stem} & live

    def listed(names: list[str]) -> list[str]:
        return [name for name in names if name in live]

    considered = [row for row in rows if stem is None or row["stem"] == stem]
    recorded = sum(1 for row in considered if row["signals"])
    block: dict[str, Any] = {
        "catalog_without_genome": listed(audit.catalog_without_genome),
        "missing_poster": listed(audit.missing_poster),
        "missing_sidecar": listed(audit.missing_sidecar),
        "orphan_poster": listed(audit.orphan_poster),
        "orphan_sidecar": listed(audit.orphan_sidecar),
        "pedigree_warnings": [w for w in audit.pedigree_warnings if stem is None or stem in w],
        "signals_recorded": recorded,
        "score": _score_counts(cfg, stem) if score else None,
    }
    return block


def _score_counts(cfg: dict[str, Any], stem: str | None) -> dict[str, Any]:
    from pipeline.refactor_scan import scan_catalog

    try:
        scored = scan_catalog(cfg, sheep_id=stem, limit=None)
    except Exception as exc:  # noqa: BLE001 — a score failure must not hide the report
        return {"ok": 0, "candidate": 0, "quarantine": 0, "error": str(exc)}
    counts = {"ok": 0, "candidate": 0, "quarantine": 0}
    for row in scored:
        verdict = str(getattr(row, "verdict", "") or "")
        if verdict in counts:
            counts[verdict] += 1
    return counts


def _status_block(cfg: dict[str, Any], stem: str | None, media: Path) -> dict[str, Any]:
    from pipeline.idle_gate import is_gate_open
    from pipeline.job_recovery import classify_jobs
    from pipeline.peering import peers_share_out
    from pipeline.worker_drain import in_flight_jobs, phase_for, read_flag

    try:
        gate = "open" if is_gate_open(cfg) else "closed"
    except Exception:  # noqa: BLE001
        gate = "closed"
    try:
        live_jobs = list(classify_jobs(cfg).get("live_jobs") or [])
    except Exception:  # noqa: BLE001
        live_jobs = []
    try:
        in_flight = in_flight_jobs(cfg)
        drain = phase_for(bool(read_flag(cfg).get("drain")), in_flight)
    except Exception:  # noqa: BLE001
        drain = "off"
    worker: dict[str, Any] = {"state": "idle"}
    if live_jobs:
        job = live_jobs[0]
        src = str(job.get("src") or "")
        worker = {
            "state": "rendering",
            "job": job.get("id"),
            "job_state": job.get("state"),
            "stem": Path(src).stem if src else None,
        }
    share_dir = peers_share_out(cfg)
    share_files = sorted(path.name for path in _genomes(share_dir))
    block: dict[str, Any] = {
        "idle_gate": gate,
        "drain": drain,
        "worker": worker,
        "share_out_flam3": len(share_files),
        "share_out_files": share_files,
    }
    if stem:
        block["sheep"] = _sheep_place(cfg, stem, media)
    return block


def _sheep_place(cfg: dict[str, Any], stem: str, media: Path) -> str:
    gen = catalog_generation(stem)
    if (media / "by-generation" / gen / f"{stem}.mp4").is_file():
        return "live"
    inbox = _optional_path(cfg, "genomes_inbox")
    if inbox is not None and any(path.stem == stem for path in _genomes(inbox)):
        return "inbox"
    quarantine = _optional_path(cfg, "genomes_quarantine")
    if quarantine is not None and any(path.stem == stem for path in _genomes(quarantine)):
        return "quarantine"
    parked = media / REFACTOR_QUARANTINE_DIRNAME
    if parked.is_dir() and any(path.stem == stem for path in parked.rglob("*.mp4")):
        return "parked"
    return "absent"


def _voting_block(rows: list[dict[str, Any]], *, top_limit: int, stem: str | None) -> dict[str, Any]:
    considered = [row for row in rows if stem is None or row["stem"] == stem]
    likes = loves = votes = share = with_votes = 0
    ranked: list[dict[str, Any]] = []
    for row in considered:
        fb = row["feedback"]
        likes += int(fb["likes"])
        loves += int(fb["loves"])
        votes += int(fb["votes"])
        if fb["share_candidate"]:
            share += 1
        if int(fb["votes"]) > 0:
            with_votes += 1
            ranked.append(
                {
                    "stem": row["stem"],
                    "alias": row["alias"],
                    "likes": int(fb["likes"]),
                    "loves": int(fb["loves"]),
                    "votes": int(fb["votes"]),
                    "share_candidate": bool(fb["share_candidate"]),
                    "last_voted_at": fb.get("last_voted_at"),
                }
            )
    ranked.sort(key=lambda row: (-row["votes"], -row["loves"], -row["likes"], row["stem"]))
    cap = max(0, int(top_limit))
    return {
        "with_votes": with_votes,
        "unvoted": len(considered) - with_votes,
        "likes": likes,
        "loves": loves,
        "votes": votes,
        "share_candidate": share,
        "top_limit": cap,
        "top": ranked[:cap],
    }


def _history_events(
    cfg: dict[str, Any],
    rows: list[dict[str, Any]],
    media: Path,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    from pipeline.breed_idle import load_history

    for entry in load_history(cfg):
        at = str(entry.get("at") or "")
        parents = [Path(str(path)).stem for path in entry.get("parents") or []]
        staged = [Path(str(path)).stem for path in entry.get("staged") or []]
        method = str(entry.get("method") or "breed")
        cross = str(entry.get("cross_method") or "")
        left = " ".join(part for part in (method, cross) if part)
        detail = left
        if parents:
            detail += "  " + " x ".join(parents)
        if staged:
            detail += "  -> " + ", ".join(staged)
        events.append(
            {
                "at": at,
                "kind": "breed",
                "detail": detail.strip(),
                "stems": parents + staged,
            }
        )

    jobs_dir = _optional_path(cfg, "jobs_dir")
    if jobs_dir is not None and jobs_dir.is_dir():
        from pipeline.job_recovery import list_jobs, sheep_basename_from_src

        for job in list_jobs(jobs_dir):
            stem = sheep_basename_from_src(job.src)
            at = str(job.data.get("updated_at") or job.data.get("started_at") or "")
            if not at:
                at = _mtime_ts(job.path) or ""
            state = str(job.data.get("state") or "?")
            reason = job.data.get("reason") or job.data.get("reject_reason")
            detail = state if not stem else f"{state}  {stem}"
            if reason:
                detail += f"  {reason}"
            elif job.data.get("duration_sec") is not None:
                detail += f"  {job.data.get('duration_sec')}s"
            events.append(
                {
                    "at": at,
                    "kind": "job",
                    "detail": detail,
                    "stems": [stem] if stem else [],
                }
            )

    for row in rows:
        for entry in row["refactor"]:
            if not isinstance(entry, dict):
                continue
            reason = entry.get("reason")
            if isinstance(reason, list):
                reason_text = " ".join(str(part) for part in reason if part)
            else:
                reason_text = str(reason or "")
            status = str(entry.get("status") or "refactor")
            detail = status
            if reason_text:
                detail += f"  {reason_text}"
            detail += f"  {row['stem']}"
            events.append(
                {
                    "at": str(entry.get("ts") or ""),
                    "kind": "refactor",
                    "detail": detail,
                    "stems": [row["stem"]],
                }
            )
        last = row["feedback"].get("last_voted_at")
        if last:
            fb = row["feedback"]
            alias = row["alias"] or "-"
            events.append(
                {
                    "at": str(last),
                    "kind": "vote",
                    "detail": (
                        f"{row['stem']}  {alias}  "
                        f"votes={fb['votes']} likes={fb['likes']} loves={fb['loves']}"
                    ),
                    "stems": [row["stem"]],
                }
            )

    quarantine = _optional_path(cfg, "genomes_quarantine")
    for path in _genomes(quarantine):
        at = _mtime_ts(path)
        if not at:
            continue
        events.append(
            {
                "at": at,
                "kind": "park",
                "detail": f"{path.stem}  genomes/quarantine",
                "stems": [path.stem],
            }
        )
    parked = media / REFACTOR_QUARANTINE_DIRNAME
    if parked.is_dir():
        for path in sorted(parked.rglob("*.mp4")):
            if "stills" in path.parts:
                continue
            at = _mtime_ts(path)
            if not at:
                continue
            events.append(
                {
                    "at": at,
                    "kind": "park",
                    "detail": f"{path.stem}  _refactor-quarantine",
                    "stems": [path.stem],
                }
            )
    return events


def _history_block(
    events: list[dict[str, Any]],
    *,
    limit: int,
    stem: str | None,
) -> dict[str, Any]:
    chosen = events
    if stem:
        chosen = [event for event in events if stem in event.get("stems", [])]
    def sort_key(event: dict[str, Any]) -> tuple[int, float, str]:
        parsed = _parse_ts(event.get("at"))
        if parsed is None:
            return (1, 0.0, event.get("kind") or "")
        return (0, -parsed.timestamp(), event.get("kind") or "")

    chosen.sort(key=sort_key)
    cap = max(0, int(limit))
    shown = chosen[:cap]
    return {"shown": len(shown), "limit": cap, "matched": len(chosen), "events": shown}


def build_report(
    cfg: dict[str, Any],
    *,
    stem: str | None = None,
    history_limit: int = 20,
    top_limit: int = 10,
    score: bool = False,
    host: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the five sections. Reads catalog and state files; writes nothing."""
    media = resolve_path(cfg, "media_library")
    rows = _sheep_rows(media)
    selected = next((row for row in rows if row["stem"] == stem), None) if stem else None
    scope_rows = [selected] if stem and selected else ([] if stem else rows)
    voting_rows = scope_rows if stem else rows
    return {
        "host": host or platform.node(),
        "generated_at": generated_at or datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": stem or "live by-generation",
        "stem": stem,
        "size": _one_size(selected, stem) if stem else _size_block(rows, cfg, media),
        "condition": _condition_block(cfg, rows, stem=stem, score=score),
        "status": _status_block(cfg, stem, media),
        "voting": _voting_block(voting_rows, top_limit=top_limit, stem=None),
        "history": _history_block(
            _history_events(cfg, rows, media),
            limit=history_limit,
            stem=stem,
        ),
    }


def _count_line(label: str, items: list[str], width: int = 24) -> str:
    if not items:
        return f"{label + ':':<{width}} 0"
    if len(items) == 1:
        return f"{label + ':':<{width}} 1   {items[0]}"
    shown = ", ".join(items[:8])
    extra = "" if len(items) <= 8 else f"  +{len(items) - 8}"
    return f"{label + ':':<{width}} {len(items)}   {shown}{extra}"


def _field(label: str, value: Any, width: int = 18) -> str:
    return f"{label + ':':<{width}} {value}"


def format_report(report: dict[str, Any]) -> str:
    """Human text matching the flock-report sample."""
    lines = [
        f"JellyFlam3 flock report — {report['host']}",
        f"generated: {report['generated_at']}",
        f"scope:     {report['scope']}",
        "",
        "== size ==",
    ]
    size = report["size"]
    if report.get("stem"):
        lines.extend(
            [
                _field("stem", size["stem"]),
                _field("alias", size["alias"] or "-"),
                _field("generation", size["generation"]),
                _field("type", size["kind"]),
                _field("license", size["license"]),
                _field("duration", size["duration"]),
                _field("catalog_bytes", size["catalog_bytes"]),
                _field("in_catalog", "yes" if size["in_catalog"] else "no"),
            ]
        )
    else:
        lines.extend(
            [
                _field("sheep", size["sheep"]),
                _field("loops", size["loops"]),
                _field("tuples", size["tuples"]),
                _field("duration", size["duration"]),
                _field("catalog_bytes", size["catalog_bytes"]),
                _field("license", size["license_text"]),
                _field(
                    "alias",
                    f"{size['alias_present']} present, {size['alias_missing']} missing",
                ),
                _field("by_generation", size["by_generation_text"]),
                _field(
                    "inbox_flam3",
                    f"{size['inbox_flam3']}   head: {size['inbox_head']}"
                    if size["inbox_head"]
                    else size["inbox_flam3"],
                ),
                _field("quarantine_flam3", size["quarantine_flam3"]),
                _field("parked_catalog", f"{size['parked_catalog']}   _refactor-quarantine"),
                _field("preview_catalog", f"{size['preview_catalog']}   _refactor-preview"),
            ]
        )

    condition = report["condition"]
    lines.extend(["", "== condition =="])
    for key in (
        "catalog_without_genome",
        "missing_poster",
        "missing_sidecar",
        "orphan_poster",
        "orphan_sidecar",
        "pedigree_warnings",
    ):
        lines.append(_count_line(key, list(condition[key])))
    lines.append(
        _field("signals_recorded", f"{condition['signals_recorded']}   ingest record, not a fresh score", 24)
    )
    score = condition.get("score")
    if not score:
        lines.append(_field("score", "omitted   pass --score", 24))
    elif score.get("error"):
        lines.append(_field("score", f"error   {score['error']}", 24))
    else:
        lines.append(
            _field(
                "score",
                f"ok {score['ok']}  candidate {score['candidate']}  quarantine {score['quarantine']}",
                24,
            )
        )

    status = report["status"]
    worker = status["worker"]
    if worker.get("state") == "rendering":
        worker_text = (
            f"rendering  {worker.get('stem') or '-'}  "
            f"state={worker.get('job_state')}  job={worker.get('job')}"
        )
    else:
        worker_text = "idle"
    lines.extend(
        [
            "",
            "== status ==",
            _field("idle_gate", status["idle_gate"]),
            _field("drain", status["drain"]),
            _field("worker", worker_text),
            _field("share_out_flam3", status["share_out_flam3"]),
        ]
    )
    for name in status["share_out_files"]:
        lines.append(f"  {name}")
    if status.get("sheep"):
        lines.append(_field("sheep", status["sheep"]))

    voting = report["voting"]
    lines.extend(
        [
            "",
            "== voting ==",
            _field("with_votes", voting["with_votes"]),
            _field("unvoted", voting["unvoted"]),
            _field("likes", voting["likes"]),
            _field("loves", voting["loves"]),
            _field("votes", voting["votes"]),
            _field("share_candidate", voting["share_candidate"]),
            _field(
                "top",
                f"{len(voting['top'])} shown, limit {voting['top_limit']}, zeros omitted",
            ),
            "",
        ]
    )
    if report.get("stem"):
        top = voting["top"]
        if top:
            row = top[0]
            lines.extend(
                [
                    _field("likes", row["likes"]),
                    _field("loves", row["loves"]),
                    _field("votes", row["votes"]),
                    _field("share", "yes" if row["share_candidate"] else "no"),
                    _field("last_voted_at", row["last_voted_at"] or "-"),
                ]
            )
        else:
            lines.append(_field("votes", 0))
    else:
        lines.append(
            f"{'votes':>5}  {'likes':>5}  {'loves':>5}  {'share':<5}  "
            f"{'last_voted_at':<20}  {'alias':<16}  stem"
        )
        for row in voting["top"]:
            lines.append(
                f"{row['votes']:5d}  {row['likes']:5d}  {row['loves']:5d}  "
                f"{('yes' if row['share_candidate'] else 'no'):<5}  "
                f"{(row['last_voted_at'] or '-'):<20}  {(row['alias'] or '-'):<16}  {row['stem']}"
            )

    history = report["history"]
    lines.extend(
        [
            "",
            "== history ==",
            f"{history['shown']} shown, limit {history['limit']}, newest first",
            "",
        ]
    )
    for event in history["events"]:
        lines.append(f"{event['at']}  {event['kind']:<8}  {event['detail']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Read-only flock size, condition, status, votes, and history")
    ap.add_argument("--config", default="configs/jellyflam3.yaml")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stem", default="", help="Filename stem or catalog alias")
    ap.add_argument("--history", type=int, default=20, help="Newest history rows (default 20)")
    ap.add_argument("--top", type=int, default=10, help="Vote leaderboard rows (default 10)")
    ap.add_argument(
        "--score",
        action="store_true",
        help="Re-score the live catalog and add ok / candidate / quarantine counts",
    )
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    stem = (args.stem or "").strip() or None
    if stem:
        try:
            stem = resolve_sheep_token(resolve_path(cfg, "media_library"), stem)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    report = build_report(
        cfg,
        stem=stem,
        history_limit=args.history,
        top_limit=args.top,
        score=args.score,
    )
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(format_report(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
