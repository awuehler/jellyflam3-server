"""Purpose: Sheep-library (and optional scratch) free-space WARN/BAD for healthcheck.

Requirements: ``paths.media_library``; optional ``library_disk.*`` thresholds in yaml.

Usage:
  python3 -m pipeline.library_disk check
  python3 -m pipeline.library_disk check --json

Assumptions: Ops only — no auto-purge, no worker ingest refuse (Phase 4 / 06
full rotate). Exit 0=ok, 1=warn, 2=bad. healthcheck fails only on bad.
"""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

GiB = 1024**3

DEFAULT_WARN_USED_PCT = 80.0
DEFAULT_BAD_USED_PCT = 95.0
DEFAULT_WARN_FREE_GB = 16.0
DEFAULT_BAD_FREE_GB = 4.0

EXIT_OK = 0
EXIT_WARN = 1
EXIT_BAD = 2


class _Usage(NamedTuple):
    total: int
    used: int
    free: int


@dataclass
class DiskCheck:
    """One filesystem assessment (ok / warn / bad)."""

    role: str
    path: str
    exists: bool
    total_bytes: int = 0
    used_bytes: int = 0
    free_bytes: int = 0
    used_pct: float = 0.0
    free_gb: float = 0.0
    total_gb: float = 0.0
    used_gb: float = 0.0
    level: str = "ok"  # ok | warn | bad
    reasons: list[str] = field(default_factory=list)


@dataclass
class DiskReport:
    """Worst-of several mount checks plus the threshold set used."""

    checks: list[DiskCheck]
    worst: str
    thresholds: dict[str, float]


def thresholds_from_cfg(cfg: dict[str, Any] | None) -> dict[str, float]:
    """Read ``library_disk.*`` with documented defaults."""
    block = (cfg or {}).get("library_disk") or {}
    if not isinstance(block, dict):
        block = {}
    return {
        "warn_used_pct": float(block.get("warn_used_pct", DEFAULT_WARN_USED_PCT)),
        "bad_used_pct": float(block.get("bad_used_pct", DEFAULT_BAD_USED_PCT)),
        "warn_free_gb": float(block.get("warn_free_gb", DEFAULT_WARN_FREE_GB)),
        "bad_free_gb": float(block.get("bad_free_gb", DEFAULT_BAD_FREE_GB)),
    }


def classify_usage(
    usage: _Usage | Any,
    *,
    role: str,
    path: str,
    warn_used_pct: float = DEFAULT_WARN_USED_PCT,
    bad_used_pct: float = DEFAULT_BAD_USED_PCT,
    warn_free_gb: float = DEFAULT_WARN_FREE_GB,
    bad_free_gb: float = DEFAULT_BAD_FREE_GB,
) -> DiskCheck:
    """Map total/used/free bytes onto ok / warn / bad (percent or GiB floor)."""
    total = int(usage.total)
    used = int(usage.used)
    free = int(usage.free)
    used_pct = round(100.0 * used / total, 1) if total else 0.0
    free_gb = round(free / GiB, 1)
    reasons: list[str] = []
    level = "ok"
    if total <= 0:
        level = "bad"
        reasons.append("zero-size filesystem")
    else:
        if used_pct >= bad_used_pct:
            level = "bad"
            reasons.append(f"used {used_pct}% >= {bad_used_pct:g}%")
        elif used_pct >= warn_used_pct:
            level = "warn"
            reasons.append(f"used {used_pct}% >= {warn_used_pct:g}%")
        if free_gb < bad_free_gb:
            level = "bad"
            reasons.append(f"free {free_gb}G < {bad_free_gb:g}G")
        elif free_gb < warn_free_gb:
            if level != "bad":
                level = "warn"
            reasons.append(f"free {free_gb}G < {warn_free_gb:g}G")
    return DiskCheck(
        role=role,
        path=path,
        exists=True,
        total_bytes=total,
        used_bytes=used,
        free_bytes=free,
        used_pct=used_pct,
        free_gb=free_gb,
        total_gb=round(total / GiB, 1),
        used_gb=round(used / GiB, 1),
        level=level,
        reasons=reasons,
    )


def missing_check(role: str, path: str) -> DiskCheck:
    """BAD row when the configured path is not on disk."""
    return DiskCheck(
        role=role,
        path=path,
        exists=False,
        level="bad",
        reasons=["path missing"],
    )


def _resolve(cfg: dict[str, Any], key: str, default: str) -> Path:
    paths = cfg.get("paths") or {}
    raw = paths.get(key) or default
    p = Path(raw)
    if not p.is_absolute():
        root = Path(cfg.get("_repo_root") or ".")
        p = root / p
    return p


def _dev_id(path: Path) -> int | None:
    try:
        return path.resolve().stat().st_dev
    except OSError:
        return None


def assess_config(
    cfg: dict[str, Any] | None,
    *,
    usage_for: dict[str, Any] | None = None,
) -> DiskReport:
    """Check media_library (and scratch when on a different device)."""
    cfg = cfg or {}
    thr = thresholds_from_cfg(cfg)
    media = _resolve(cfg, "media_library", "/media/sheep")
    scratch = _resolve(cfg, "frames_scratch", "/var/cache/jellyflam3/frames")
    block = cfg.get("library_disk") or {}
    check_scratch = bool(block.get("check_scratch", True)) if isinstance(block, dict) else True

    checks: list[DiskCheck] = []
    seen_dev: set[int] = set()

    def add(role: str, path: Path) -> None:
        key = str(path)
        injected = usage_for.get(key) if usage_for else None
        if injected is not None:
            checks.append(classify_usage(injected, role=role, path=key, **thr))
            return
        if not path.exists():
            checks.append(missing_check(role, key))
            return
        dev = _dev_id(path)
        if dev is not None:
            if dev in seen_dev:
                return
            seen_dev.add(dev)
        checks.append(classify_usage(shutil.disk_usage(path), role=role, path=key, **thr))

    add("sheep", media)
    if check_scratch:
        scratch_mount = scratch if scratch.exists() else scratch.parent
        add("scratch", scratch_mount)

    order = {"ok": 0, "warn": 1, "bad": 2}
    worst = "ok"
    for c in checks:
        if order.get(c.level, 0) > order[worst]:
            worst = c.level
    if not checks:
        worst = "bad"
    return DiskReport(checks=checks, worst=worst, thresholds=thr)


def format_check(check: DiskCheck) -> str:
    """One healthcheck-style line."""
    tag = check.level.upper()
    if not check.exists:
        return f"{tag} {check.role} {check.path} missing"
    why = f" ({'; '.join(check.reasons)})" if check.reasons else ""
    return (
        f"{tag} {check.role} {check.path} used {check.used_pct}% "
        f"({check.used_gb}G/{check.total_gb}G) free {check.free_gb}G{why}"
    )


def format_report(report: DiskReport) -> str:
    """Human block for CLI / healthcheck."""
    lines = [format_check(c) for c in report.checks]
    t = report.thresholds
    lines.append(
        f"thresholds warn>={t['warn_used_pct']:g}% or free<{t['warn_free_gb']:g}G; "
        f"bad>={t['bad_used_pct']:g}% or free<{t['bad_free_gb']:g}G "
        "(no auto-purge; no worker refuse)"
    )
    return "\n".join(lines)


def exit_code_for(worst: str) -> int:
    """Map worst level to process exit status."""
    if worst == "bad":
        return EXIT_BAD
    if worst == "warn":
        return EXIT_WARN
    return EXIT_OK


def _load_cfg(config_path: Path) -> dict[str, Any]:
    from pipeline.config import load_config

    if not config_path.is_file():
        return {"_repo_root": str(Path.cwd()), "paths": {}}
    return load_config(config_path, strict_secrets=False)


def main(argv: list[str] | None = None) -> int:
    """CLI: print sheep/scratch disk level; exit 0/1/2 for ok/warn/bad."""
    ap = argparse.ArgumentParser(
        description="Sheep-library free-space check (WARN/BAD only; no rotate)"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check", help="Assess media_library (and scratch if other device)")
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    p.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    cfg = _load_cfg(Path(args.config))
    report = assess_config(cfg)
    if args.json:
        print(
            json.dumps(
                {
                    "worst": report.worst,
                    "thresholds": report.thresholds,
                    "checks": [asdict(c) for c in report.checks],
                },
                indent=2,
            )
        )
    else:
        print(format_report(report))
    return exit_code_for(report.worst)


if __name__ == "__main__":
    raise SystemExit(main())
