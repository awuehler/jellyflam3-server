"""Purpose: Estimate how many concurrent Jellyfin video sessions a LAN link can carry.

Requirements: Optional ffprobe for catalog probe; ``encode.video_bitrate`` as Direct Play fallback.

Usage:
  python3 -m pipeline.link_capacity estimate --profile wifi-pi --mode directplay
  python3 -m pipeline.link_capacity probe --config configs/jellyflam3.yaml
  python3 -m pipeline.link_capacity profiles
  python3 -m pipeline.link_capacity bench-serve --port 18791 --mib 64
  python3 -m pipeline.link_capacity bench-recv --host <Pi_LAN_IP> --port 18791

Assumptions: ``N_max`` is an estimate, not a Jellyfin connection cap. Formula:

  N_max = floor( (usable_link_bps * (1 - headroom)) / bps_per_active_session )
"""

from __future__ import annotations

import argparse
import json
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pipeline.stills import iter_catalog_mp4s
from pipeline.tool_lookup import tool as _tool

DEFAULT_HEADROOM = 0.30
DEFAULT_DIRECTPLAY_MBPS = 4.0
DEFAULT_TRANSCODE_MBPS = 8.0
HLS_REMUX_MULTIPLIER = 1.05
CODEC_LABEL = "H.264 High @ L4.2"
RESOLUTION_LABEL = "1920x1080 @ 24 fps"

# Usable TCP Mbps *before* headroom. Lab 2026-09-03: STA furnaces, eth0 DOWN.
PROFILES: dict[str, dict[str, Any]] = {
    "wifi-pi": {
        "usable_mbps": 35.0,
        "kind": "wifi",
        "source": "lab",
        "notes": (
            "Pi as WiFi STA serving WiFi clients (STA to AP to STA). "
            "Lab 2026-09-03: 16a to 08a 35.3 Mbps, 16a to 04a 47.1 Mbps; "
            "profile uses the slower hop."
        ),
    },
    "wifi-ap-gigabit-backhaul": {
        "usable_mbps": 80.0,
        "kind": "wifi",
        "source": "profiled",
        "notes": (
            "Pi on Ethernet, clients on a typical 5 GHz AP with gigabit backhaul. "
            "Not measured on the WiFi-STA lab fleet (eth0 DOWN)."
        ),
    },
    "eth-gigabit": {
        "usable_mbps": 900.0,
        "kind": "eth",
        "source": "profiled",
        "notes": (
            "TCP goodput on 1 Gbit Ethernet (about 0.9 of PHY). "
            "Not measured on this lab fleet (eth0 DOWN)."
        ),
    },
}

PROFILE_ALIASES = {
    "wifi": "wifi-pi",
    "eth": "eth-gigabit",
    "ethernet": "eth-gigabit",
}

SESSION_MODES = ("directplay", "hls-remux", "transcode")


@dataclass
class Estimate:
    """One N_max calculation with the assumptions that produced it."""

    n_max: int
    profile: str
    kind: str
    usable_mbps: float
    usable_source: str
    headroom: float
    budget_mbps: float
    mode: str
    session_mbps: float
    session_source: str
    codec: str = CODEC_LABEL
    resolution: str = RESOLUTION_LABEL
    warn: str | None = None
    notes: list[str] = field(default_factory=list)


def parse_bitrate_bps(raw: str | int | float) -> int:
    """Parse ffmpeg-style ``4M`` / ``4000k`` / integer bps into bits per second (SI)."""
    if isinstance(raw, bool):
        raise ValueError("bitrate must be a number or ffmpeg size string")
    if isinstance(raw, (int, float)):
        v = float(raw)
        if v <= 0:
            raise ValueError(f"bitrate must be positive, got {raw!r}")
        # Bare numbers in yaml encode.video_bitrate are bits/sec; small values
        # (< 1000) are treated as Mbps (CLI --session-mbps style).
        if v < 1000:
            return int(v * 1_000_000)
        return int(v)
    s = str(raw).strip().lower().replace(" ", "")
    if not s:
        raise ValueError("empty bitrate")
    mult = 1.0
    for suffix, factor in (("gbps", 1e9), ("g", 1e9), ("mbps", 1e6), ("m", 1e6), ("kbps", 1e3), ("k", 1e3), ("bps", 1.0)):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            mult = factor
            break
    v = float(s)
    if v <= 0:
        raise ValueError(f"bitrate must be positive, got {raw!r}")
    return int(v * mult)


def resolve_profile_id(name: str) -> str:
    """Map ``wifi`` / ``eth`` aliases to a PROFILES key."""
    key = (name or "").strip().lower()
    if key in PROFILES:
        return key
    if key in PROFILE_ALIASES:
        return PROFILE_ALIASES[key]
    known = ", ".join(list(PROFILES) + list(PROFILE_ALIASES))
    raise SystemExit(f"unknown profile {name!r}; choose one of: {known}")


def n_max_from_bps(usable_bps: float, headroom: float, session_bps: float) -> int:
    """Floor of leftover link after headroom, divided by one video session."""
    if session_bps <= 0:
        raise ValueError("session_bps must be positive")
    if not 0.0 <= headroom < 1.0:
        raise ValueError("headroom must be in [0, 1)")
    budget = float(usable_bps) * (1.0 - float(headroom))
    if budget <= 0:
        return 0
    return int(budget // float(session_bps))


def session_bps_for_mode(
    mode: str,
    *,
    directplay_bps: int,
    transcode_mbps: float = DEFAULT_TRANSCODE_MBPS,
) -> tuple[int, str]:
    """Return (session_bps, source label) for a playback mode."""
    m = (mode or "directplay").strip().lower()
    if m not in SESSION_MODES:
        raise SystemExit(f"unknown mode {mode!r}; choose one of: {', '.join(SESSION_MODES)}")
    if m == "transcode":
        return int(transcode_mbps * 1_000_000), f"profiled transcode {transcode_mbps:g} Mbps"
    if m == "hls-remux":
        bps = int(directplay_bps * HLS_REMUX_MULTIPLIER)
        return bps, f"Direct Play x {HLS_REMUX_MULTIPLIER:g} HLS remux"
    return int(directplay_bps), "Direct Play catalog / encode target"


def estimate(
    *,
    profile: str = "wifi-pi",
    mode: str = "directplay",
    headroom: float = DEFAULT_HEADROOM,
    usable_mbps: float | None = None,
    session_mbps: float | None = None,
    encode_bitrate: str | int | float | None = None,
    transcode_mbps: float = DEFAULT_TRANSCODE_MBPS,
) -> Estimate:
    """Compute integer N_max plus the assumptions used."""
    pid = resolve_profile_id(profile)
    meta = PROFILES[pid]
    if usable_mbps is not None:
        u_mbps = float(usable_mbps)
        u_src = "override"
        if u_mbps <= 0:
            raise ValueError("usable_mbps must be positive")
    else:
        u_mbps = float(meta["usable_mbps"])
        u_src = str(meta["source"])
    if session_mbps is not None:
        if session_mbps <= 0:
            raise ValueError("session_mbps must be positive")
        dp_bps = int(float(session_mbps) * 1_000_000)
        sess_src_base = f"override {session_mbps:g} Mbps"
    elif encode_bitrate is not None:
        dp_bps = parse_bitrate_bps(encode_bitrate)
        sess_src_base = f"encode.video_bitrate {encode_bitrate}"
    else:
        dp_bps = int(DEFAULT_DIRECTPLAY_MBPS * 1_000_000)
        sess_src_base = f"default Direct Play {DEFAULT_DIRECTPLAY_MBPS:g} Mbps"

    sess_bps, mode_src = session_bps_for_mode(
        mode, directplay_bps=dp_bps, transcode_mbps=transcode_mbps
    )
    if session_mbps is not None and mode != "transcode":
        # Explicit session rate wins; still apply remux multiplier only when
        # caller did not pass --session-mbps.
        sess_bps = int(float(session_mbps) * 1_000_000)
        mode_src = sess_src_base
    elif session_mbps is not None and mode == "transcode":
        sess_bps = int(float(session_mbps) * 1_000_000)
        mode_src = sess_src_base
    elif mode != "transcode":
        mode_src = f"{sess_src_base}; {mode_src}" if mode == "hls-remux" else sess_src_base

    n = n_max_from_bps(u_mbps * 1_000_000, headroom, sess_bps)
    budget = u_mbps * (1.0 - headroom)
    warn = None
    if n < 1:
        warn = (
            f"N_max={n}: this hop cannot carry one {mode} session at "
            f"{sess_bps / 1e6:.2f} Mbps with {headroom:.0%} headroom. "
            "Prefer Ethernet for the furnace, Direct Play MP4, or fewer TVs."
        )
    notes = [
        str(meta["notes"]),
        "Image screensaver clients are out of the video-N count; "
        "Kodi ES screensaver (video loops) counts as a full session.",
        "Idle-gate still pauses the furnace while any matching TV is Playing.",
        "Estimate is LAN only; Tailscale / WAN is a worse budget.",
        "N_max is not a Jellyfin connection cap.",
    ]
    return Estimate(
        n_max=n,
        profile=pid,
        kind=str(meta["kind"]),
        usable_mbps=u_mbps,
        usable_source=u_src,
        headroom=float(headroom),
        budget_mbps=budget,
        mode=mode.strip().lower(),
        session_mbps=sess_bps / 1e6,
        session_source=mode_src,
        warn=warn,
        notes=notes,
    )


def probe_mp4_bps(ffprobe: str, mp4: Path) -> int | None:
    """Container bit_rate, else size*8/duration. None if unreadable."""
    try:
        out = subprocess.check_output(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=bit_rate,duration,size",
                "-of",
                "json",
                str(mp4),
            ],
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    try:
        fmt = json.loads(out).get("format") or {}
    except json.JSONDecodeError:
        return None
    br = fmt.get("bit_rate")
    if br:
        try:
            v = int(float(br))
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    dur = fmt.get("duration")
    size = fmt.get("size")
    try:
        d = float(dur)
        sz = float(size)
    except (TypeError, ValueError):
        return None
    if d > 0 and sz > 0:
        return int(sz * 8.0 / d)
    return None


def summarize_bps(samples: list[int]) -> dict[str, Any]:
    """Count / mean / p50 / p90 / min / max for a list of bit/s samples."""
    if not samples:
        return {"count": 0, "mean_bps": None, "p50_bps": None, "p90_bps": None, "min_bps": None, "max_bps": None}
    ordered = sorted(samples)

    def pct(q: float) -> int:
        i = max(0, min(len(ordered) - 1, int(round(q * (len(ordered) - 1)))))
        return ordered[i]

    mean = int(statistics.mean(ordered))
    return {
        "count": len(ordered),
        "mean_bps": mean,
        "p50_bps": pct(0.5),
        "p90_bps": pct(0.9),
        "min_bps": ordered[0],
        "max_bps": ordered[-1],
        "mean_mbps": round(mean / 1e6, 3),
        "p50_mbps": round(pct(0.5) / 1e6, 3),
        "p90_mbps": round(pct(0.9) / 1e6, 3),
        "min_mbps": round(ordered[0] / 1e6, 3),
        "max_mbps": round(ordered[-1] / 1e6, 3),
    }


def probe_catalog(media_root: Path, ffprobe: str, *, limit: int = 0) -> dict[str, Any]:
    """ffprobe catalog MP4s under ``by-generation`` (skips edges)."""
    files = iter_catalog_mp4s(Path(media_root))
    if limit and limit > 0:
        files = files[:limit]
    samples: list[int] = []
    failed = 0
    for p in files:
        bps = probe_mp4_bps(ffprobe, p)
        if bps is None:
            failed += 1
            continue
        samples.append(bps)
    summary = summarize_bps(samples)
    summary["files"] = len(files)
    summary["failed"] = failed
    summary["media_root"] = str(media_root)
    return summary


def _load_cfg(config_path: Path) -> dict[str, Any]:
    """Load yaml without failing closed on missing Jellyfin secrets."""
    from pipeline.config import load_config

    if not config_path.is_file():
        return {}
    return load_config(config_path, strict_secrets=False)


def _encode_bitrate(cfg: dict[str, Any]) -> str | None:
    enc = cfg.get("encode") or {}
    raw = enc.get("video_bitrate")
    if raw is None:
        return None
    return str(raw)


def _media_root(cfg: dict[str, Any]) -> Path | None:
    paths = cfg.get("paths") or {}
    raw = paths.get("media_library")
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        root = Path(cfg.get("_repo_root") or ".")
        p = root / p
    return p


def _lc_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    block = cfg.get("link_capacity") or {}
    return block if isinstance(block, dict) else {}


def format_estimate(est: Estimate) -> str:
    """Human-readable N_max block for the CLI."""
    lines = [
        f"N_max={est.n_max}",
        f"profile={est.profile} kind={est.kind} usable_mbps={est.usable_mbps:g} source={est.usable_source}",
        f"headroom={est.headroom:.0%} budget_mbps={est.budget_mbps:.2f}",
        f"mode={est.mode} session_mbps={est.session_mbps:.3f} ({est.session_source})",
        f"codec={est.codec} resolution={est.resolution}",
    ]
    if est.warn:
        lines.append(f"WARN {est.warn}")
    return "\n".join(lines)


def _bench_serve(port: int, mib: int) -> int:
    """Send ``mib`` MiB of zeros to the first TCP client (lab goodput)."""
    blob = b"\0" * (1024 * 1024)
    target = int(mib) * 1024 * 1024
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", port))
    sock.listen(1)
    print(f"bench-serve listening 0.0.0.0:{port} mib={mib}", flush=True)
    conn, addr = sock.accept()
    print(f"bench-serve client {addr[0]}", flush=True)
    sent = 0
    try:
        while sent < target:
            conn.sendall(blob)
            sent += len(blob)
    finally:
        conn.close()
        sock.close()
    print(f"bench-serve sent_bytes={sent}", flush=True)
    return 0


def _bench_recv(host: str, port: int, timeout: float) -> int:
    """Pull until the sender closes; print TCP Mbps."""
    sock = socket.socket()
    sock.settimeout(timeout)
    t0 = time.time()
    sock.connect((host, port))
    n = 0
    try:
        while True:
            buf = sock.recv(1024 * 1024)
            if not buf:
                break
            n += len(buf)
    finally:
        sock.close()
    dt = time.time() - t0
    mbps = (n * 8 / dt / 1e6) if dt > 0 else 0.0
    print(f"bytes={n} sec={dt:.3f} Mbps={mbps:.2f}")
    print(f"hint: python3 -m pipeline.link_capacity estimate --usable-mbps {mbps:.1f}")
    return 0 if n > 0 else 1


def main(argv: list[str] | None = None) -> int:
    """CLI: estimate N_max, probe catalog bit-rate, or bench a hop."""
    ap = argparse.ArgumentParser(
        description="Estimate concurrent Jellyfin video sessions (N_max) for a LAN hop"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_est = sub.add_parser("estimate", help="Print integer N_max plus assumptions")
    p_est.add_argument("--config", default="configs/jellyflam3.yaml")
    p_est.add_argument("--profile", default="", help="wifi-pi | wifi-ap-gigabit-backhaul | eth-gigabit")
    p_est.add_argument(
        "--mode",
        default="directplay",
        choices=SESSION_MODES,
        help="directplay (ambient MP4), hls-remux, or transcode",
    )
    p_est.add_argument("--headroom", type=float, default=None, help="Unused fraction (default 0.30)")
    p_est.add_argument("--usable-mbps", type=float, default=None, help="Override measured hop goodput")
    p_est.add_argument("--session-mbps", type=float, default=None, help="Override per-session demand")
    p_est.add_argument("--json", action="store_true")

    p_pr = sub.add_parser("probe", help="ffprobe catalog MP4 bit-rates (p50/p90)")
    p_pr.add_argument("--config", default="configs/jellyflam3.yaml")
    p_pr.add_argument("--limit", type=int, default=0)
    p_pr.add_argument("--json", action="store_true")

    sub.add_parser("profiles", help="List builtin usable-link profiles")

    p_bs = sub.add_parser("bench-serve", help="TCP sender for a hop measurement")
    p_bs.add_argument("--port", type=int, default=18791)
    p_bs.add_argument("--mib", type=int, default=64)

    p_br = sub.add_parser("bench-recv", help="TCP receiver; prints Mbps")
    p_br.add_argument("--host", required=True)
    p_br.add_argument("--port", type=int, default=18791)
    p_br.add_argument("--timeout", type=float, default=60.0)

    args = ap.parse_args(argv)
    cfg: dict[str, Any] = {}
    if args.cmd in ("estimate", "probe"):
        cfg = _load_cfg(Path(args.config))
    lc = _lc_cfg(cfg)

    if args.cmd == "profiles":
        for pid, meta in PROFILES.items():
            print(
                f"{pid}  kind={meta['kind']}  usable_mbps={meta['usable_mbps']:g}  "
                f"source={meta['source']}"
            )
            print(f"  {meta['notes']}")
        print(f"default_headroom={DEFAULT_HEADROOM:.0%}")
        print("N_max is an estimate — not a Jellyfin cap.")
        return 0

    if args.cmd == "probe":
        root = _media_root(cfg) or Path("/media/sheep")
        ffprobe = _tool(cfg, "ffprobe")
        summary = probe_catalog(root, ffprobe, limit=int(args.limit or 0))
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"media_root={summary.get('media_root')} files={summary.get('files')} failed={summary.get('failed')}")
            if summary.get("count"):
                print(
                    f"mean_mbps={summary['mean_mbps']} p50={summary['p50_mbps']} "
                    f"p90={summary['p90_mbps']} min={summary['min_mbps']} max={summary['max_mbps']}"
                )
                print(
                    "hint: python3 -m pipeline.link_capacity estimate "
                    f"--session-mbps {summary['p90_mbps']}"
                )
            else:
                print("no catalog bit-rates (empty library or ffprobe failed)")
                return 1
        return 0

    if args.cmd == "bench-serve":
        return _bench_serve(int(args.port), int(args.mib))
    if args.cmd == "bench-recv":
        return _bench_recv(str(args.host), int(args.port), float(args.timeout))

    if args.cmd == "estimate":
        profile = args.profile or str(lc.get("default_profile") or "wifi-pi")
        headroom = args.headroom
        if headroom is None:
            headroom = float(lc.get("headroom") if lc.get("headroom") is not None else DEFAULT_HEADROOM)
        usable = args.usable_mbps
        if usable is None and lc.get("usable_mbps") is not None:
            usable = float(lc["usable_mbps"])
        enc = _encode_bitrate(cfg)
        est = estimate(
            profile=profile,
            mode=args.mode,
            headroom=headroom,
            usable_mbps=usable,
            session_mbps=args.session_mbps,
            encode_bitrate=enc,
        )
        if args.json:
            print(json.dumps(asdict(est), indent=2))
        else:
            print(format_estimate(est))
            print("wifi-uplinked Pi is the tight case — prefer Ethernet for the furnace when N>1.")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
