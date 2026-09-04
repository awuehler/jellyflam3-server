#!/usr/bin/env bash

# Purpose: Snapshot current JellyFlam3 Pi conditions: load, flock/inbox, thermals, top procs.
# Requirements: bash, python3, PyYAML; systemctl/vcgencmd/ip optional depending on host.
#
# Usage:
#   ./scripts/status_report.sh
#   ./scripts/status_report.sh /path/to/jellyflam3.yaml
#   ./scripts/status_report.sh --json    # machine-readable summary on stdout
#
# When to run: Anytime — queue depth, live-vs-orphan jobs, thermals. Pair with healthcheck.sh for pass/fail.
# Success: Always exit 0 (informational). --json is for scripts / RC logs.
# Docs: docs/phase2/01_ARCHIVE_SEED_LIBRARY.md (orphan jobs); docs/phase3/10_TESTING_AND_ACCEPTANCE.md
#
# Assumptions: Informational only — always exits 0 (use healthcheck.sh / perf_healthcheck.sh for pass/fail).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG="${1:-$ROOT/configs/jellyflam3.yaml}"
JSON=0
if [[ "${1:-}" == "--json" ]]; then
  JSON=1
  CFG="${2:-$ROOT/configs/jellyflam3.yaml}"
elif [[ "${2:-}" == "--json" ]]; then
  JSON=1
fi

export JF_CFG="$CFG" JF_ROOT="$ROOT" JF_JSON="$JSON"

python3 - <<'PY'
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

CFG = Path(os.environ["JF_CFG"])
ROOT = Path(os.environ["JF_ROOT"])
AS_JSON = os.environ.get("JF_JSON") == "1"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from pipeline.library_disk import assess_config, format_check


def sh(cmd: list[str] | str, *, timeout: float = 15) -> str:
    """Run cmd (list or shell string); return stripped stdout (errors ignored)."""
    if isinstance(cmd, str):
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
    else:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return (proc.stdout or "").strip()


def load_cfg() -> dict:
    """Load YAML config and resolve common paths into cfg['_paths']."""
    if not CFG.is_file():
        return {}
    raw = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    paths = raw.get("paths") or {}
    out = dict(raw)
    out["_paths"] = {}
    for key, default in (
        ("genomes_inbox", str(ROOT / "genomes" / "inbox")),
        ("genomes_quarantine", str(ROOT / "genomes" / "quarantine")),
        ("genomes_done", str(ROOT / "genomes" / "done")),
        ("jobs_dir", "/var/lib/jellyflam3/jobs"),
        ("frames_scratch", "/var/cache/jellyflam3/frames"),
        ("media_library", "/media/sheep"),
        ("status_file", "/var/lib/jellyflam3/idle_gate_status.json"),
    ):
        p = Path(paths.get(key) or default)
        if not p.is_absolute():
            p = ROOT / p
        out["_paths"][key] = p
    return out


def decode_throttled(val: str) -> dict:
    """Raspberry Pi get_throttled bitfield."""
    try:
        n = int(val.replace("throttled=", "").strip(), 16)
    except ValueError:
        return {"raw": val, "current": [], "sticky": []}
    labels = {
        0: "under-voltage",
        1: "arm freq capped",
        2: "throttling",
        3: "soft temp limit",
        16: "under-voltage has occurred",
        17: "arm freq capped has occurred",
        18: "throttling has occurred",
        19: "soft temp limit has occurred",
    }
    current = [labels[b] for b in (0, 1, 2, 3) if n & (1 << b)]
    sticky = [labels[b] for b in (16, 17, 18, 19) if n & (1 << b)]
    return {"raw": hex(n), "current": current, "sticky": sticky}


def df_entry(path: Path) -> dict | None:
    """Disk usage for path, or None if missing."""
    if not path.exists():
        return None
    usage = shutil.disk_usage(path)
    return {
        "path": str(path),
        "total_gb": round(usage.total / (1024**3), 1),
        "used_gb": round(usage.used / (1024**3), 1),
        "free_gb": round(usage.free / (1024**3), 1),
        "used_pct": round(100 * usage.used / usage.total, 1) if usage.total else 0,
    }


def meminfo() -> dict:
    """Parse /proc/meminfo into GiB used/available/swap fields."""
    data = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        parts = v.split()
        try:
            data[k] = int(parts[0])  # kB
        except ValueError:
            continue
    total = data.get("MemTotal", 0)
    avail = data.get("MemAvailable", 0)
    return {
        "total_gib": round(total / (1024**2), 1),
        "available_gib": round(avail / (1024**2), 1),
        "used_gib": round((total - avail) / (1024**2), 1),
        "swap_total_gib": round(data.get("SwapTotal", 0) / (1024**2), 1),
        "swap_used_gib": round(
            (data.get("SwapTotal", 0) - data.get("SwapFree", 0)) / (1024**2), 1
        ),
    }


def loadavg() -> dict:
    """1/5/15m load averages plus procs and nproc."""
    a, b, c, procs, _last = Path("/proc/loadavg").read_text().split()[:5]
    return {
        "1m": float(a),
        "5m": float(b),
        "15m": float(c),
        "procs": procs,
        "nproc": os.cpu_count() or 0,
    }


def thermal() -> dict:
    """Pi vcgencmd temp/throttle/clocks plus thermal_zone0 when available."""
    out: dict = {}
    if shutil.which("vcgencmd"):
        out["temp"] = sh(["vcgencmd", "measure_temp"])
        out["throttled"] = decode_throttled(sh(["vcgencmd", "get_throttled"]))
        out["volts_core"] = sh(["vcgencmd", "measure_volts", "core"])
        arm = sh(["vcgencmd", "measure_clock", "arm"])
        out["clock_arm"] = arm
        try:
            hz = int(arm.split("=")[-1])
            out["clock_arm_ghz"] = round(hz / 1e9, 2)
        except (ValueError, IndexError):
            pass
    tz = Path("/sys/class/thermal/thermal_zone0/temp")
    if tz.is_file():
        out["thermal_zone0_c"] = round(int(tz.read_text().strip()) / 1000.0, 1)
    return out


def services() -> dict:
    """systemctl is-active for core JellyFlam3 / Jellyfin units."""
    units = (
        "jellyflam3-worker",
        "jellyflam3-idlegate",
        "jellyfin",
        "jellyflam3-display-sink",
        "jellyflam3-syncthing",
        "jellyflam3-peering",
    )
    out = {}
    for u in units:
        st = sh(f"systemctl is-active {u} 2>/dev/null || echo missing")
        out[u] = st or "missing"
    return out


def peering_status() -> dict | None:
    """Load peering_status.json or infer Opt In from genomes/peers/OPT_IN."""
    path = Path("/var/lib/jellyflam3/peering_status.json")
    if not path.is_file():
        # Fall back to OPT_IN ack under repo
        ack = ROOT / "genomes" / "peers" / "OPT_IN"
        if ack.is_file():
            return {"share_opt_in": True, "opt_in_ack": str(ack), "status_file": None}
        return {"share_opt_in": False}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def sheep_stats(cfg: dict) -> dict:
    """Catalog mp4 counts, inbox/quarantine/done, job states, and frame progress."""
    paths = cfg.get("_paths") or {}
    media: Path = paths.get("media_library") or Path("/media/sheep")
    inbox: Path = paths.get("genomes_inbox") or Path("/var/lib/jellyflam3/genomes/inbox")
    quar: Path = paths.get("genomes_quarantine") or Path(
        "/var/lib/jellyflam3/genomes/quarantine"
    )
    done: Path = paths.get("genomes_done") or Path("/var/lib/jellyflam3/genomes/done")
    jobs: Path = paths.get("jobs_dir") or Path("/var/lib/jellyflam3/jobs")
    frames: Path = paths.get("frames_scratch") or Path("/var/cache/jellyflam3/frames")

    mp4s = list(media.rglob("*.mp4")) if media.exists() else []
    by_gen: dict[str, int] = {}
    for p in mp4s:
        parts = p.parts
        gen = (
            parts[parts.index("by-generation") + 1]
            if "by-generation" in parts
            else "other"
        )
        by_gen[gen] = by_gen.get(gen, 0) + 1

    inbox_files = sorted(inbox.glob("*.flam3")) if inbox.exists() else []
    quar_files = sorted(quar.glob("*.flam3")) if quar.exists() else []
    done_files = sorted(done.glob("*.flam3")) if done.exists() else []

    job_states: dict[str, int] = {}
    active_jobs = []
    orphan_jobs = []
    live_job_ids: set[str] = set()
    if jobs.exists():
        try:
            import sys

            if str(ROOT) not in sys.path:
                sys.path.insert(0, str(ROOT))
            from pipeline.config import load_config as _lc
            from pipeline.job_recovery import classify_jobs

            _cfg = _lc(CFG)
            classified = classify_jobs(_cfg)
            live_job_ids = set(classified.get("live_job_ids") or [])
            orphan_jobs = classified.get("orphan_jobs") or []
        except Exception:
            live_job_ids = set()
            orphan_jobs = []
        for jpath in sorted(jobs.glob("*/job.json")):
            try:
                data = json.loads(jpath.read_text(encoding="utf-8"))
                st = data.get("state", "?")
            except Exception:
                data, st = {}, "?"
            job_states[st] = job_states.get(st, 0) + 1
            if st in ("queued", "rendering", "encoding", "gating"):
                row = {
                    "id": jpath.parent.name,
                    "state": st,
                    "src": data.get("src"),
                    "nframes": data.get("nframes"),
                    "live": jpath.parent.name in live_job_ids,
                }
                active_jobs.append(row)

    # Best-effort frame progress for active animate job dirs
    progress = []
    if frames.exists():
        for job in active_jobs:
            jdir = frames / job["id"]
            if not jdir.is_dir():
                continue
            pngs = list(jdir.glob("*.png"))
            nframes = job.get("nframes") or 0
            newest = None
            if pngs:
                try:
                    newest = max(p.stat().st_mtime for p in pngs)
                except OSError:
                    newest = None
            progress.append(
                {
                    "id": job["id"],
                    "frames_done": len(pngs),
                    "nframes": nframes,
                    "pct": round(100 * len(pngs) / nframes, 1) if nframes else None,
                    "live": job.get("live"),
                    "stale_sec": round(time.time() - newest, 1) if newest else None,
                }
            )

    return {
        "catalog_mp4_total": len(mp4s),
        "by_generation": dict(sorted(by_gen.items())),
        "inbox_path": str(inbox),
        "inbox_flam3": len(inbox_files),
        "inbox_files": [p.name for p in inbox_files],
        "quarantine_flam3": len(quar_files),
        "done_path": str(done),
        "done_flam3": len(done_files),
        "job_states": job_states,
        "active_jobs": active_jobs,
        "orphan_jobs": orphan_jobs,
        "live_job_ids": sorted(live_job_ids),
        "render_progress": progress,
        "frames_scratch_mib": round(
            sum(f.stat().st_size for f in frames.rglob("*") if f.is_file()) / (1024**2),
            1,
        )
        if frames.exists()
        else 0,
    }


def top_procs(n: int = 12) -> list[dict]:
    """Top n processes by CPU from ps --sort=-%cpu."""
    out = sh(
        "ps -eo pid,user,%cpu,%mem,rss,etime,cmd --sort=-%cpu | head -n {}".format(n + 1)
    )
    lines = out.splitlines()
    rows = []
    for line in lines[1:]:
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        rows.append(
            {
                "pid": parts[0],
                "user": parts[1],
                "cpu": parts[2],
                "mem": parts[3],
                "rss_kib": parts[4],
                "etime": parts[5],
                "cmd": parts[6],
            }
        )
    return rows


def idle_gate(cfg: dict) -> dict | None:
    """Parse idle_gate status JSON from config paths, or None/error dict."""
    path = (cfg.get("_paths") or {}).get("status_file")
    if not path or not Path(path).is_file():
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def _library_disk_block(cfg: dict) -> dict:
    """WARN/BAD classification for sheep (and scratch) mounts — guide 06 slice."""
    try:
        report = assess_config(cfg)
    except Exception as exc:
        return {"worst": "bad", "error": str(exc), "checks": [], "lines": []}
    return {
        "worst": report.worst,
        "thresholds": report.thresholds,
        "checks": [asdict(c) for c in report.checks],
        "lines": [format_check(c) for c in report.checks],
    }


def build_report() -> dict:
    """Collect host, load, thermal, disk, services, sheep, and top CPU into one dict."""
    cfg = load_cfg()
    paths = cfg.get("_paths") or {}
    now = datetime.now(timezone.utc)
    report = {
        "generated_at": now.isoformat(),
        "host": platform.node(),
        "uptime": sh("uptime"),
        "load": loadavg(),
        "memory": meminfo(),
        "thermal": thermal(),
        "disk": {
            "root": df_entry(Path("/")),
            "sheep": df_entry(paths.get("media_library") or Path("/media/sheep")),
            "cache": df_entry(Path("/var/cache/jellyflam3")),
            "lib": df_entry(Path("/var/lib/jellyflam3")),
        },
        "library_disk": _library_disk_block(cfg),
        "services": services(),
        "idle_gate": idle_gate(cfg),
        "peering": peering_status(),
        "sheep": sheep_stats(cfg),
        "top_cpu": top_procs(12),
        "network": sh("ip -br addr show 2>/dev/null || true").splitlines(),
        "users": sh("who 2>/dev/null || true").splitlines(),
    }
    return report


def print_human(r: dict) -> None:
    """Pretty-print a build_report() dict to stdout."""
    print(f"JellyFlam3 status report — {r['host']}")
    print(f"generated: {r['generated_at']}")
    print(f"uptime:    {r['uptime']}")
    print()
    load = r["load"]
    print("== load / memory ==")
    print(
        f"loadavg {load['1m']:.2f} {load['5m']:.2f} {load['15m']:.2f}  "
        f"nproc={load['nproc']}  procs={load['procs']}"
    )
    mem = r["memory"]
    print(
        f"mem used {mem['used_gib']} GiB / {mem['total_gib']} GiB  "
        f"avail {mem['available_gib']} GiB  swap {mem['swap_used_gib']}/{mem['swap_total_gib']} GiB"
    )
    print()
    print("== thermal / power ==")
    th = r["thermal"]
    if th.get("temp"):
        print(th["temp"])
    if "thermal_zone0_c" in th:
        print(f"thermal_zone0: {th['thermal_zone0_c']} C")
    if th.get("volts_core"):
        print(th["volts_core"])
    if th.get("clock_arm_ghz") is not None:
        print(f"clock_arm: {th['clock_arm_ghz']} GHz ({th.get('clock_arm')})")
    elif th.get("clock_arm"):
        print(th["clock_arm"])
    thr = th.get("throttled") or {}
    if thr:
        print(f"throttled: {thr.get('raw')}")
        if thr.get("current"):
            print("  current:", ", ".join(thr["current"]))
        else:
            print("  current: none")
        if thr.get("sticky"):
            print("  sticky: ", ", ".join(thr["sticky"]))
        else:
            print("  sticky:  none")
    print()
    print("== disk ==")
    for label, d in (r.get("disk") or {}).items():
        if not d:
            print(f"{label}: missing")
            continue
        print(
            f"{label}: {d['used_gb']}G/{d['total_gb']}G ({d['used_pct']}%) "
            f"free {d['free_gb']}G  {d['path']}"
        )
    ld = r.get("library_disk") or {}
    print()
    print("== library disk ==")
    print(f"worst: {ld.get('worst', '?')}")
    for line in ld.get("lines") or []:
        print(line)
    print()
    print("== services ==")
    for u, st in (r.get("services") or {}).items():
        print(f"{u}: {st}")
    gate = r.get("idle_gate")
    print()
    print("== idle gate ==")
    if gate:
        print(
            f"gate={gate.get('gate')} reason={gate.get('reason')} "
            f"eta={gate.get('seconds_until_resume')}s"
        )
    else:
        print("status file missing")
    peer = r.get("peering") or {}
    print()
    print("== peering ==")
    print(f"share_opt_in:      {peer.get('share_opt_in')}")
    units = peer.get("units") or {}
    if units:
        print(f"syncthing:         {units.get('jellyflam3-syncthing')}")
    print(f"inbox_flam3:       {peer.get('inbox_flam3_count')}")
    sheep = r.get("sheep") or {}
    print()
    print("== sheep / queue ==")
    print(f"catalog_mp4_total: {sheep.get('catalog_mp4_total')}")
    print(f"by_generation:     {sheep.get('by_generation')}")
    print(f"inbox_path:        {sheep.get('inbox_path')}")
    print(f"inbox_flam3:       {sheep.get('inbox_flam3')} (pending)")
    print(f"done_flam3:        {sheep.get('done_flam3')} (rendered archive)")
    print(f"quarantine_flam3:  {sheep.get('quarantine_flam3')}")
    print(f"job_states:        {sheep.get('job_states')}")
    print(f"frames_scratch:    {sheep.get('frames_scratch_mib')} MiB")
    if sheep.get("orphan_jobs"):
        print("orphan_jobs:       (reclaim: python -m pipeline.job_recovery)")
        for j in sheep["orphan_jobs"]:
            print(f"  {j.get('id')} state={j.get('state')} src={j.get('src')}")
    if sheep.get("active_jobs"):
        print("active_jobs:")
        for j in sheep["active_jobs"]:
            tag = "live" if j.get("live") else "orphan?"
            print(
                f"  {j['id']} state={j['state']} [{tag}] "
                f"nframes={j.get('nframes')} src={j.get('src')}"
            )
    if sheep.get("render_progress"):
        print("render_progress:")
        for p in sheep["render_progress"]:
            tag = "live" if p.get("live") else "stale"
            stale = p.get("stale_sec")
            extra = f" stale={stale}s" if stale is not None and not p.get("live") else ""
            print(
                f"  {p['id']}: {p['frames_done']}/{p.get('nframes') or '?'} "
                f"({p.get('pct')}%) [{tag}]{extra}"
            )
    if sheep.get("inbox_files"):
        print("inbox files:")
        for name in sheep["inbox_files"]:
            print(f"  {name}")
    print()
    print("== top cpu ==")
    print(f"{'PID':>7} {'USER':8} {'%CPU':>5} {'%MEM':>5} {'RSS':>8} {'ELAPSED':>10} CMD")
    for row in r.get("top_cpu") or []:
        print(
            f"{row['pid']:>7} {row['user'][:8]:8} {row['cpu']:>5} {row['mem']:>5} "
            f"{row['rss_kib']:>8} {row['etime']:>10} {row['cmd'][:80]}"
        )
    print()
    print("== network ==")
    for line in r.get("network") or []:
        print(line)
    print()
    print("== users ==")
    for line in r.get("users") or ["(none)"]:
        print(line)


def main() -> int:
    """Emit JSON or human status report; always return 0."""
    report = build_report()
    if AS_JSON:
        print(json.dumps(report, indent=2))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PY
