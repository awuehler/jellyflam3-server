"""Purpose: Limit render/encode CPU so Jellyfin and system services stay responsive.

Requirements: Linux ``taskset`` optional; config ``render.max_cpus`` / ``flam3_nthreads``.

Usage: ``wrap_cmd(cfg, cmd)``, ``flam3_nthreads(cfg)``, ``ffmpeg_thread_args(cfg)`` around heavy children.

Assumptions: Default leaves one core free on multi-core hosts; ``max_cpus=0`` means unlimited.
"""

from __future__ import annotations

import os
import shutil
from typing import Any


def host_cpu_count() -> int:
    """Logical CPU count from the OS (at least 1)."""
    return int(os.cpu_count() or 1)


def effective_cpus(cfg: dict[str, Any]) -> int | None:
    """
    Max CPUs the heavy worker children may use.

    Config:
      render.max_cpus: int
        >0  → clamp to that many cores (default 3 on a 4-core Pi)
         0  → unlimited (all host cores)
        <0  → leave that many cores free (e.g. -1 → nproc-1)
    """
    render = cfg.get("render") or {}
    if "max_cpus" not in render:
        # Default: leave one core free when the host has 2+ CPUs.
        n = host_cpu_count()
        return max(1, n - 1) if n >= 2 else n
    raw = int(render.get("max_cpus") or 0)
    n = host_cpu_count()
    if raw == 0:
        return None
    if raw < 0:
        return max(1, n + raw)
    return max(1, min(raw, n))


def flam3_nthreads(cfg: dict[str, Any]) -> int:
    """flam3-animate nthreads; 0 means omit (flam3 default = all cores)."""
    render = cfg.get("render") or {}
    explicit = int(render.get("flam3_nthreads", 0) or 0)
    if explicit > 0:
        return explicit
    cpus = effective_cpus(cfg)
    return int(cpus) if cpus else 0


def taskset_prefix(cfg: dict[str, Any]) -> list[str]:
    """Prefix argv with taskset -c 0..(N-1) when max_cpus is set and taskset exists."""
    cpus = effective_cpus(cfg)
    if not cpus:
        return []
    if not shutil.which("taskset"):
        return []
    spec = "0" if cpus == 1 else f"0-{cpus - 1}"
    return ["taskset", "-c", spec]


def wrap_cmd(cfg: dict[str, Any], cmd: list[str]) -> list[str]:
    """Return ``cmd`` prefixed with taskset when CPU limiting is active."""
    return taskset_prefix(cfg) + list(cmd)


def ffmpeg_thread_args(cfg: dict[str, Any]) -> list[str]:
    """ffmpeg ``-threads`` / ``-filter_threads`` args matching effective_cpus, or []."""
    cpus = effective_cpus(cfg)
    if not cpus:
        return []
    return ["-threads", str(cpus), "-filter_threads", str(cpus)]
