"""Purpose: Detect and reclaim orphaned render jobs after worker crashes.

Requirements: Config paths jobs_dir / frames_scratch / genomes_inbox / media_library; Linux /proc for live detection.

Usage: Run on worker startup, or ``python -m pipeline.job_recovery [--dry-run] [--startup] [--classify]``.

Assumptions: Single-job worker; flam3-animate cannot resume partial frames — drop scratch, mark orphaned/superseded, re-queue when still needed.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path

log = logging.getLogger("jellyflam3.job_recovery")

IN_FLIGHT = frozenset({"queued", "rendering", "encoding", "gating"})
TERMINAL = frozenset({"ingested", "failed", "orphaned", "superseded"})


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    path: Path
    data: dict[str, Any]

    @property
    def state(self) -> str:
        return str(self.data.get("state") or "?")

    @property
    def src(self) -> Path | None:
        raw = self.data.get("src")
        return Path(raw) if raw else None


@dataclass
class ReclaimAction:
    job_id: str
    previous_state: str
    outcome: str  # orphaned | superseded | skipped_live | skipped
    reason: str
    requeued: str | None = None
    frames_removed: bool = False
    dry_run: bool = False


def utc_now() -> str:
    """UTC timestamp ``YYYY-MM-DDTHH:MM:SSZ``."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sheep_basename_from_src(src: Path | None) -> str | None:
    """Normalized sheep stem from job ``src``, or None if unset."""
    if src is None:
        return None
    from pipeline.sheep_names import normalize_stem

    return normalize_stem(src.stem)


def catalog_mp4_for_base(cfg: dict[str, Any], base: str) -> Path | None:
    """Existing catalog MP4 path for ``base``, or None if not on disk."""
    from pipeline.sheep_names import catalog_generation

    media = resolve_path(cfg, "media_library")
    gen = catalog_generation(base)
    path = media / "by-generation" / gen / f"{base}.mp4"
    return path if path.is_file() else None


def list_jobs(jobs_dir: Path) -> list[JobRecord]:
    """Load all readable ``*/job.json`` records under ``jobs_dir``."""
    out: list[JobRecord] = []
    if not jobs_dir.is_dir():
        return out
    for jpath in sorted(jobs_dir.glob("*/job.json")):
        try:
            data = json.loads(jpath.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("unreadable job %s: %s", jpath, exc)
            continue
        out.append(JobRecord(job_id=jpath.parent.name, path=jpath, data=data))
    return out


def _is_job_id(part: str) -> bool:
    """True for 12-char lowercase hex job ids used in frames paths."""
    return len(part) == 12 and all(c in "0123456789abcdef" for c in part)


def live_job_ids_from_proc(frames_root: Path) -> set[str]:
    """Best-effort: job ids referenced by living flam3-animate / ffmpeg processes.

    flam3-animate often has a bare cmdline; the worker sets ``prefix=.../frames/<id>/f``
    in the child environment — prefer that signal.
    """
    live: set[str] = set()
    try:
        frames_s = str(frames_root.resolve())
    except OSError:
        frames_s = str(frames_root)
    frames_s = frames_s.replace("\\", "/")
    proc = Path("/proc")
    if not proc.is_dir():
        return live
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        blob = ""
        try:
            blob += (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except OSError:
            pass
        try:
            blob += "\n" + (entry / "environ").read_bytes().replace(b"\0", b"\n").decode(
                "utf-8", "replace"
            )
        except OSError:
            pass
        if not blob:
            continue
        blob_n = blob.replace("\\", "/")
        if frames_s not in blob_n and "flam3-animate" not in blob.lower() and "ffmpeg" not in blob.lower():
            continue
        # prefix=/var/cache/jellyflam3/frames/<job_id>/f
        marker = "/frames/"
        idx = 0
        while True:
            i = blob_n.find(marker, idx)
            if i < 0:
                break
            rest = blob_n[i + len(marker) :]
            job_part = rest.split("/", 1)[0].split()[0]
            if _is_job_id(job_part):
                live.add(job_part)
            idx = i + len(marker)
    return live


def is_orphan(job: JobRecord, *, live_ids: set[str], treat_all_inflight_as_orphan: bool) -> bool:
    """True for in-flight jobs with no live owner (or all in-flight at startup)."""
    if job.state not in IN_FLIGHT:
        return False
    if treat_all_inflight_as_orphan:
        # Worker startup: nothing is owned yet (single-threaded worker).
        return True
    return job.job_id not in live_ids


def _write_job(job: JobRecord, data: dict[str, Any], *, dry_run: bool) -> None:
    """Persist updated job.json unless ``dry_run``."""
    if dry_run:
        return
    job.path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _remove_frames(frames_root: Path, job_id: str, *, dry_run: bool) -> bool:
    """Delete ``frames_root/job_id`` if present; True when removed or would remove."""
    frame_dir = frames_root / job_id
    if not frame_dir.exists():
        return False
    if dry_run:
        return True
    shutil.rmtree(frame_dir, ignore_errors=True)
    return True


def _inbox_originated(src: Path | None, inbox: Path) -> bool:
    """True when job src lived under the genomes inbox (path heuristics if resolve fails)."""
    if src is None:
        return False
    try:
        return src.resolve().parent == inbox.resolve()
    except OSError:
        s = str(src).replace("\\", "/")
        return "genomes/inbox" in s or s.startswith(str(inbox).replace("\\", "/"))


def _is_manual_sample(src: Path | None) -> bool:
    """True for in-repo sample genomes that should not be re-queued."""
    if src is None:
        return False
    s = str(src).replace("\\", "/")
    return "/samples/" in s or "/templates/" in s or s.startswith("configs/samples")


def _ensure_inbox(cfg: dict[str, Any], job: JobRecord, *, dry_run: bool) -> str | None:
    """Copy genome back into inbox if needed. Returns staged basename or None."""
    inbox = resolve_path(cfg, "genomes_inbox")
    src = job.src
    base = sheep_basename_from_src(src)

    if base is None:
        for name in ("tv_optimized.flam3", "resized.flam3"):
            cand = job.path.parent / name
            if cand.is_file() and cand.stat().st_size > 32:
                from pipeline.sheep_names import reclaim_filename

                dest_name = reclaim_filename(job.job_id)
                dest = inbox / dest_name
                if dry_run:
                    return dest_name
                inbox.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cand, dest)
                return dest_name
        return None

    dest_name = f"{base}.flam3"
    dest = inbox / dest_name
    if dest.is_file():
        return None  # already queued

    candidates: list[Path] = []
    if src is not None and src.is_file():
        candidates.append(src)
    for name in ("tv_optimized.flam3", "resized.flam3"):
        cand = job.path.parent / name
        if cand.is_file() and cand.stat().st_size > 32:
            candidates.append(cand)
    if not candidates:
        return None
    if dry_run:
        return dest_name
    inbox.mkdir(parents=True, exist_ok=True)
    shutil.copy2(candidates[0], dest)
    log.info("re-queued %s -> %s", candidates[0], dest)
    return dest_name


def reclaim_job(
    cfg: dict[str, Any],
    job: JobRecord,
    *,
    dry_run: bool = False,
    requeue: bool = True,
) -> ReclaimAction:
    """Drop frames, mark orphaned/superseded, and optionally re-queue the genome."""
    frames_root = resolve_path(cfg, "frames_scratch")
    previous = job.state
    base = sheep_basename_from_src(job.src)
    catalog = catalog_mp4_for_base(cfg, base) if base else None

    frames_removed = _remove_frames(frames_root, job.job_id, dry_run=dry_run)

    data = dict(job.data)
    data["previous_state"] = previous
    data["orphaned_at"] = utc_now()
    data["updated_at"] = data["orphaned_at"]

    if catalog is not None:
        data["state"] = "superseded"
        data["orphan_reason"] = f"catalog already has {catalog.name}; dropped stale in-flight job"
        _write_job(job, data, dry_run=dry_run)
        return ReclaimAction(
            job_id=job.job_id,
            previous_state=previous,
            outcome="superseded",
            reason=data["orphan_reason"],
            frames_removed=frames_removed,
            dry_run=dry_run,
        )

    requeued = None
    inbox = resolve_path(cfg, "genomes_inbox")
    should_requeue = bool(requeue)
    if _is_manual_sample(job.src) and job.src is not None and job.src.is_file():
        should_requeue = False
    elif not (
        _inbox_originated(job.src, inbox)
        or (job.src is not None and not job.src.is_file())
        or any((job.path.parent / n).is_file() for n in ("tv_optimized.flam3", "resized.flam3"))
    ):
        should_requeue = False

    if should_requeue:
        requeued = _ensure_inbox(cfg, job, dry_run=dry_run)

    data["state"] = "orphaned"
    data["orphan_reason"] = "in-flight job with no live worker/process; frames discarded (no resume)"
    if requeued:
        data["requeued"] = requeued
    _write_job(job, data, dry_run=dry_run)
    return ReclaimAction(
        job_id=job.job_id,
        previous_state=previous,
        outcome="orphaned",
        reason=data["orphan_reason"],
        requeued=requeued,
        frames_removed=frames_removed,
        dry_run=dry_run,
    )


def reclaim_orphans(
    cfg: dict[str, Any],
    *,
    dry_run: bool = False,
    startup: bool = False,
    requeue: bool = True,
    job_ids: set[str] | None = None,
) -> list[ReclaimAction]:
    """Reclaim orphaned in-flight jobs.

    ``startup=True`` treats every in-flight job as orphaned (safe for the
    single-threaded worker before it begins polling).
    """
    jobs_dir = resolve_path(cfg, "jobs_dir")
    frames_root = resolve_path(cfg, "frames_scratch")
    live = set() if startup else live_job_ids_from_proc(frames_root)
    actions: list[ReclaimAction] = []
    for job in list_jobs(jobs_dir):
        if job_ids is not None and job.job_id not in job_ids:
            continue
        if not is_orphan(job, live_ids=live, treat_all_inflight_as_orphan=startup):
            if job.state in IN_FLIGHT and job.job_id in live:
                actions.append(
                    ReclaimAction(
                        job_id=job.job_id,
                        previous_state=job.state,
                        outcome="skipped_live",
                        reason="live process owns this job_id",
                        dry_run=dry_run,
                    )
                )
            continue
        action = reclaim_job(cfg, job, dry_run=dry_run, requeue=requeue)
        log.info(
            "reclaim %s %s→%s frames=%s requeued=%s%s",
            action.job_id,
            action.previous_state,
            action.outcome,
            action.frames_removed,
            action.requeued,
            " (dry-run)" if dry_run else "",
        )
        actions.append(action)
    return actions


def classify_jobs(cfg: dict[str, Any]) -> dict[str, Any]:
    """Status helper: split in-flight jobs into live vs orphan."""
    jobs_dir = resolve_path(cfg, "jobs_dir")
    frames_root = resolve_path(cfg, "frames_scratch")
    live = live_job_ids_from_proc(frames_root)
    live_jobs: list[dict[str, Any]] = []
    orphan_jobs: list[dict[str, Any]] = []
    for job in list_jobs(jobs_dir):
        if job.state not in IN_FLIGHT:
            continue
        row = {
            "id": job.job_id,
            "state": job.state,
            "src": str(job.src) if job.src else None,
            "nframes": job.data.get("nframes"),
        }
        if job.job_id in live:
            live_jobs.append(row)
        else:
            orphan_jobs.append(row)
    return {"live_job_ids": sorted(live), "live_jobs": live_jobs, "orphan_jobs": orphan_jobs}


def main(argv: list[str] | None = None) -> int:
    """CLI: detect and reclaim orphaned render jobs into the inbox."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Detect/reclaim orphaned JellyFlam3 render jobs")
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--startup",
        action="store_true",
        help="Treat all in-flight jobs as orphans (worker boot semantics)",
    )
    p.add_argument("--no-requeue", action="store_true", help="Only mark/clean; do not stage inbox")
    p.add_argument("--classify", action="store_true", help="Print live vs orphan JSON and exit")
    p.add_argument("--job", action="append", default=[], help="Limit to job id(s)")
    args = p.parse_args(argv)

    cfg_path = Path(args.config)
    if not cfg_path.is_file():
        alt = Path("configs/jellyflam3.yaml.example")
        if alt.is_file():
            log.warning("config %s missing; using %s", cfg_path, alt)
            cfg_path = alt
        else:
            raise SystemExit(f"config not found: {args.config}")
    cfg = load_config(cfg_path)

    if args.classify:
        print(json.dumps(classify_jobs(cfg), indent=2))
        return 0

    job_ids = set(args.job) if args.job else None
    actions = reclaim_orphans(
        cfg,
        dry_run=args.dry_run,
        startup=args.startup,
        requeue=not args.no_requeue,
        job_ids=job_ids,
    )
    summary = {
        "dry_run": args.dry_run,
        "startup": args.startup,
        "actions": [a.__dict__ for a in actions],
        "reclaimed": sum(1 for a in actions if a.outcome in ("orphaned", "superseded")),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
