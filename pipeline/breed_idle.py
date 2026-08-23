"""Purpose: Daily idle-window pedigree breed when inbox is empty (cron helper).

Requirements: pipeline.breed, idle_gate, job_recovery; parent pool under genomes_done,
genomes/samples, genomes/pedigree; optional history file under /var/lib/jellyflam3.

Usage:
  python3 -m pipeline.breed_idle --config configs/jellyflam3.yaml
  python3 -m pipeline.breed_idle --dry-run --json

Assumptions: Archive seed cron schedule is configured via breed.idle_breed or env;
breed only when inbox is empty, idle gate is open, and no live render jobs exist.
Random modes: mutate, cross (union), blend (alternate), interpolate — exactly one child per run.
flam3-genome may emit "warning: reached maximum attempts, giving up." on stderr during
mutate/cross; benign when the run still stages a child (see docs/phase2/07_PEDIGREE_BREEDING.md).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from pipeline.breed import breed_cross, breed_mutate, breed_cfg
from pipeline.config import load_config, resolve_path
from pipeline.idle_gate import is_gate_open
from pipeline.job_recovery import classify_jobs
from pipeline.worker import genomes_done_dir

log = logging.getLogger("jellyflam3.breed_idle")

BREED_MODES = ("mutate", "cross", "blend", "interpolate")
_FLAM3_SUFFIXES = {".flam3", ".flame"}


@dataclass(frozen=True)
class BreedPlan:
    """One idle breed attempt: method + ordered parent paths."""

    method: str
    parents: tuple[Path, ...]
    cross_method: str | None = None

    def fingerprint(self) -> tuple[Any, ...]:
        """Stable key for dedup against recent history."""
        keys = tuple(sorted(p.resolve().as_posix() for p in self.parents))
        if self.method == "mutate":
            return ("mutate", keys[0])
        return (self.method, keys, self.cross_method or "alternate")


@dataclass
class IdleBreedResult:
    action: str
    reason: str | None = None
    plan: BreedPlan | None = None
    staged: list[str] | None = None
    inbox_count: int = 0
    parent_pool_size: int = 0
    hours_until_archive: float | None = None
    next_archive_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        hours = self.hours_until_archive
        if hours is not None:
            hours = round(hours, 2)
        out = {
            "action": self.action,
            "reason": self.reason,
            "inbox_count": self.inbox_count,
            "parent_pool_size": self.parent_pool_size,
            "hours_until_archive": hours,
            "next_archive_at": self.next_archive_at,
            "staged": self.staged,
        }
        if self.plan:
            out["plan"] = {
                "method": self.plan.method,
                "parents": [str(p) for p in self.plan.parents],
                "cross_method": self.plan.cross_method,
                "fingerprint": list(self.plan.fingerprint()),
            }
        return out


def idle_breed_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    """Return ``breed.idle_breed`` section merged with defaults."""
    bc = breed_cfg(cfg)
    defaults = {
        "enabled": True,
        "history_file": "/var/lib/jellyflam3/breed_idle_history.json",
        "history_max": 8,
        "small_flock_threshold": 6,
        "dedup_depth_small": 1,
        "dedup_depth_large": 2,
        "max_rerolls": 24,
        "archive_cron_dom": [3, 13, 23],
        "archive_cron_hour": 3,
        "archive_cron_minute": 17,
        "min_hours_before_archive": 1.0,
        "include_samples": True,
        "include_pedigree": True,
    }
    raw = dict(bc.get("idle_breed") or {})
    merged = {**defaults, **raw}
    return merged


def _repo_root(cfg: dict[str, Any]) -> Path:
    return Path(cfg.get("_repo_root") or ".")


def inbox_dir(cfg: dict[str, Any]) -> Path:
    return resolve_path(cfg, "genomes_inbox")


def count_inbox(cfg: dict[str, Any]) -> int:
    inbox = inbox_dir(cfg)
    if not inbox.is_dir():
        return 0
    return sum(
        1
        for p in inbox.iterdir()
        if p.is_file() and p.suffix.lower() in _FLAM3_SUFFIXES
    )


def _iter_flam3_files(root: Path) -> Iterable[Path]:
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in _FLAM3_SUFFIXES:
            yield path


def collect_parent_pool(cfg: dict[str, Any]) -> list[Path]:
    """Rendered done pool + optional samples and git pedigree trees."""
    ib = idle_breed_cfg(cfg)
    root = _repo_root(cfg)
    seen: set[str] = set()
    pool: list[Path] = []

    def add(path: Path) -> None:
        key = path.resolve().as_posix()
        if key in seen:
            return
        seen.add(key)
        pool.append(path.resolve())

    done = genomes_done_dir(cfg)
    for path in _iter_flam3_files(done):
        add(path)

    if ib.get("include_pedigree", True):
        for path in _iter_flam3_files(root / "genomes" / "pedigree"):
            add(path)

    if ib.get("include_samples", True):
        for path in _iter_flam3_files(root / "genomes" / "samples"):
            add(path)

    return pool


def parse_dom_list(value: Any) -> list[int]:
    if isinstance(value, str):
        parts = [p.strip() for p in value.replace(";", ",").split(",") if p.strip()]
        return [int(p) for p in parts]
    if isinstance(value, (list, tuple)):
        return [int(v) for v in value]
    return [3, 13, 23]


def next_archive_cron_at(
    *,
    now: datetime | None = None,
    dom_days: list[int] | None = None,
    hour: int = 3,
    minute: int = 17,
) -> datetime | None:
    """Next archive-seed cron fire in local time, or None if not found in window."""
    now = now or datetime.now().astimezone()
    dom_days = sorted(set(dom_days or [3, 13, 23]))
    candidates: list[datetime] = []
    for day_offset in range(0, 40):
        day = now.date() + timedelta(days=day_offset)
        if day.day not in dom_days:
            continue
        fire = datetime(
            day.year,
            day.month,
            day.day,
            hour,
            minute,
            tzinfo=now.tzinfo,
        )
        if fire >= now:
            candidates.append(fire)
    if not candidates:
        return None
    return candidates[0]


def hours_until_next_archive_cron(
    *,
    now: datetime | None = None,
    dom_days: list[int] | None = None,
    hour: int = 3,
    minute: int = 17,
) -> float:
    """Wall-clock hours until the next archive-seed cron fire (local time)."""
    nxt = next_archive_cron_at(now=now, dom_days=dom_days, hour=hour, minute=minute)
    if nxt is None:
        return 24.0 * 11
    now = now or datetime.now().astimezone()
    delta = nxt - now
    return max(0.0, delta.total_seconds() / 3600.0)


def history_path(cfg: dict[str, Any]) -> Path:
    ib = idle_breed_cfg(cfg)
    path = Path(str(ib.get("history_file") or "/var/lib/jellyflam3/breed_idle_history.json"))
    if not path.is_absolute():
        path = _repo_root(cfg) / path
    return path


def load_history(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    path = history_path(cfg)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return []
    return [e for e in entries if isinstance(e, dict)]


def save_history_entry(
    cfg: dict[str, Any],
    plan: BreedPlan,
    staged: list[Path],
) -> None:
    ib = idle_breed_cfg(cfg)
    path = history_path(cfg)
    entries = load_history(cfg)
    entries.append(
        {
            "at": datetime.now().astimezone().isoformat(),
            "fingerprint": list(plan.fingerprint()),
            "method": plan.method,
            "parents": [str(p) for p in plan.parents],
            "cross_method": plan.cross_method,
            "staged": [str(p) for p in staged],
        }
    )
    cap = max(1, int(ib.get("history_max", 8)))
    entries = entries[-cap:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"entries": entries}, indent=2) + "\n", encoding="utf-8")


def recent_fingerprints(cfg: dict[str, Any], pool_size: int) -> set[tuple[Any, ...]]:
    ib = idle_breed_cfg(cfg)
    threshold = int(ib.get("small_flock_threshold", 6))
    depth = int(
        ib.get("dedup_depth_small" if pool_size <= threshold else "dedup_depth_large", 1)
    )
    fps: set[tuple[Any, ...]] = set()
    for entry in load_history(cfg)[-depth:]:
        fp = entry.get("fingerprint")
        if isinstance(fp, list):
            fps.add(tuple(fp))
    return fps


def pick_random_plan(pool: list[Path], rng: random.Random | None = None) -> BreedPlan | None:
    rng = rng or random.Random()
    if not pool:
        return None
    method = rng.choice(BREED_MODES)
    if method == "mutate":
        return BreedPlan(method="mutate", parents=(rng.choice(pool),))
    if len(pool) < 2:
        return BreedPlan(method="mutate", parents=(rng.choice(pool),))
    a, b = rng.sample(pool, 2)
    if method == "blend":
        return BreedPlan(method="blend", parents=(a, b), cross_method="alternate")
    if method == "interpolate":
        return BreedPlan(method="interpolate", parents=(a, b), cross_method="interpolate")
    return BreedPlan(method="cross", parents=(a, b), cross_method="union")


def pick_unique_plan(
    cfg: dict[str, Any],
    pool: list[Path],
    rng: random.Random | None = None,
) -> BreedPlan | None:
    ib = idle_breed_cfg(cfg)
    rng = rng or random.Random()
    avoid = recent_fingerprints(cfg, len(pool))
    max_rerolls = max(1, int(ib.get("max_rerolls", 24)))
    for _ in range(max_rerolls):
        plan = pick_random_plan(pool, rng)
        if plan is None:
            return None
        if plan.fingerprint() not in avoid:
            return plan
    return pick_random_plan(pool, rng)


def worker_is_idle(cfg: dict[str, Any]) -> tuple[bool, str]:
    if not is_gate_open(cfg):
        return False, "idle_gate_closed"
    jobs = classify_jobs(cfg)
    if jobs.get("live_jobs"):
        return False, "worker_rendering"
    return True, "ok"


def evaluate_idle_breed(cfg: dict[str, Any], *, now: datetime | None = None) -> IdleBreedResult:
    ib = idle_breed_cfg(cfg)
    if not ib.get("enabled", True):
        return IdleBreedResult(action="skip", reason="disabled")

    inbox_count = count_inbox(cfg)
    if inbox_count > 0:
        return IdleBreedResult(
            action="skip",
            reason="inbox_not_empty",
            inbox_count=inbox_count,
        )

    idle_ok, idle_reason = worker_is_idle(cfg)
    if not idle_ok:
        return IdleBreedResult(
            action="skip",
            reason=idle_reason,
            inbox_count=inbox_count,
        )

    dom = parse_dom_list(ib.get("archive_cron_dom"))
    cron_hour = int(ib.get("archive_cron_hour", 3))
    cron_minute = int(ib.get("archive_cron_minute", 17))
    next_at = next_archive_cron_at(
        now=now,
        dom_days=dom,
        hour=cron_hour,
        minute=cron_minute,
    )
    hours_archive = hours_until_next_archive_cron(
        now=now,
        dom_days=dom,
        hour=cron_hour,
        minute=cron_minute,
    )
    next_archive_at = next_at.isoformat() if next_at else None
    min_hours = float(ib.get("min_hours_before_archive", 1.0))
    if hours_archive < min_hours:
        return IdleBreedResult(
            action="skip",
            reason="archive_cron_imminent",
            inbox_count=inbox_count,
            hours_until_archive=hours_archive,
            next_archive_at=next_archive_at,
        )

    pool = collect_parent_pool(cfg)
    if not pool:
        return IdleBreedResult(
            action="skip",
            reason="parent_pool_empty",
            inbox_count=inbox_count,
            hours_until_archive=hours_archive,
            next_archive_at=next_archive_at,
        )

    plan = pick_unique_plan(cfg, pool)
    if plan is None:
        return IdleBreedResult(
            action="skip",
            reason="no_plan",
            inbox_count=inbox_count,
            parent_pool_size=len(pool),
            hours_until_archive=hours_archive,
            next_archive_at=next_archive_at,
        )

    return IdleBreedResult(
        action="breed",
        plan=plan,
        inbox_count=inbox_count,
        parent_pool_size=len(pool),
        hours_until_archive=hours_archive,
        next_archive_at=next_archive_at,
    )


def execute_plan(cfg: dict[str, Any], plan: BreedPlan, *, dry_run: bool = False) -> list[Path]:
    if plan.method == "mutate":
        return breed_mutate(cfg, plan.parents[0], count=1, dry_run=dry_run)
    if plan.method == "interpolate":
        dest = breed_cross(
            cfg,
            plan.parents[0],
            plan.parents[1],
            method="interpolate",
            mode_label="interpolate",
            dry_run=dry_run,
        )
        return [dest]
    method = plan.cross_method or "alternate"
    dest = breed_cross(
        cfg,
        plan.parents[0],
        plan.parents[1],
        method=method,
        mode_label="cross",
        dry_run=dry_run,
    )
    return [dest]


def run_idle_breed(
    cfg: dict[str, Any],
    *,
    dry_run: bool = False,
    rng: random.Random | None = None,
) -> IdleBreedResult:
    result = evaluate_idle_breed(cfg)
    if result.action != "breed" or result.plan is None:
        return result

    # Re-pick with optional seeded rng for tests.
    pool = collect_parent_pool(cfg)
    plan = pick_unique_plan(cfg, pool, rng=rng) or result.plan
    result.plan = plan

    staged = execute_plan(cfg, plan, dry_run=dry_run)
    result.staged = [str(p) for p in staged]
    if not dry_run and staged:
        save_history_entry(cfg, plan, staged)
    return result


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(
        description="Idle-window pedigree breed when inbox is empty (daily cron helper)"
    )
    ap.add_argument("--config", default=os.environ.get("JELLYFLAM3_CONFIG", "configs/jellyflam3.yaml"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true", help="Print result JSON on stdout")
    ap.add_argument("--evaluate", action="store_true", help="Evaluate gates only; do not breed")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    if args.evaluate:
        result = evaluate_idle_breed(cfg)
    else:
        result = run_idle_breed(cfg, dry_run=args.dry_run)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        if result.action == "breed":
            log.info(
                "bred method=%s parents=%s staged=%s",
                result.plan.method if result.plan else "?",
                [str(p) for p in result.plan.parents] if result.plan else [],
                result.staged,
            )
        else:
            log.info("skip reason=%s inbox=%s", result.reason, result.inbox_count)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
