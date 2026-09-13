"""Purpose: Idle-gate — pause renders when Jellyfin TV clients or transcodes are active.

Requirements: Jellyfin url + api_key; writable status_file; optional systemd freeze of the worker unit.

Usage:
  python -m pipeline.idle_gate --once
  python -m pipeline.idle_gate   # supervisor loop
  Worker polls ``is_gate_open(cfg)`` (read-only).

Assumptions: Only this supervisor writes status_file. Gate stays closed for
idle_delay_sec after the last block (hydrated from JSON across restart).
Cold start opens immediately when idle. Playing does not pause flam3-animate
mid-job; the worker checks the gate at stage boundaries only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from pipeline.config import load_config, resolve_path

log = logging.getLogger("jellyflam3.idle_gate")

GATE_SLEEP_MIN_SEC = 1
GATE_SLEEP_MAX_SEC = 15
STALE_POLL_MULT = 3


def persist_status(path: Path, payload: dict[str, Any]) -> None:
    """Write gate JSON via same-dir temp + ``os.replace`` so readers never see a torn file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def poll_interval_sec(cfg: dict[str, Any]) -> int:
    """Supervisor poll from yaml (default 20)."""
    try:
        return max(1, int((cfg.get("idle_gate") or {}).get("poll_interval_sec", 20)))
    except (TypeError, ValueError):
        return 20


def stale_after_sec(cfg: dict[str, Any]) -> int:
    """Open status older than 3× poll is treated closed (dead supervisor)."""
    return STALE_POLL_MULT * poll_interval_sec(cfg)


def parse_gate_timestamp(value: Any) -> datetime | None:
    """Parse status ISO timestamps (``Z`` or offset). Naive values are UTC."""
    if not value or not isinstance(value, str):
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def load_gate_status(cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Read status JSON. None when missing, unreadable, or not an object."""
    try:
        path = resolve_path(cfg, "status_file")
    except (KeyError, TypeError, ValueError):
        return None
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.warning("gate status unreadable (treating closed): %s", exc)
        return None
    if not isinstance(data, dict):
        log.warning("gate status not an object (treating closed)")
        return None
    return data


def closed_wait_seconds(cfg: dict[str, Any]) -> int:
    """How long ``wait_for_gate`` should sleep while closed (1–15 s)."""
    data = load_gate_status(cfg)
    if not data:
        return GATE_SLEEP_MAX_SEC
    try:
        eta = int(data.get("seconds_until_resume") or 0)
    except (TypeError, ValueError):
        eta = 0
    if eta > 0:
        return max(GATE_SLEEP_MIN_SEC, min(GATE_SLEEP_MAX_SEC, eta))
    return GATE_SLEEP_MAX_SEC


@dataclass
class GateDecision:
    blocked: bool
    reason: str


def _matches_tv(session: dict[str, Any], patterns: list[str]) -> bool:
    """True if any TV client regex matches session identity fields."""
    blob = " ".join(
        str(session.get(k) or "")
        for k in ("Client", "DeviceName", "DeviceType", "ApplicationVersion", "DeviceId")
    )
    for pat in patterns:
        if re.search(pat, blob):
            return True
    return False


def _parse_jf_time(raw: object) -> datetime | None:
    """Parse Jellyfin ISO timestamps (``Z`` → UTC); None if missing/invalid."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _recent_playback_checkin(session: dict[str, Any], within_sec: int) -> bool:
    """True if LastPlaybackCheckIn is within the activity window (architecture signal)."""
    dt = _parse_jf_time(session.get("LastPlaybackCheckIn"))
    if dt is None:
        return False
    age = (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()
    return age <= max(0, int(within_sec))


def should_block_render(sessions: list[dict[str, Any]], cfg: dict[str, Any]) -> GateDecision:
    """Decide if sessions imply a closed gate (transcode / TV / optional non-TV playback)."""
    ig = cfg.get("idle_gate") or {}
    patterns = ig.get("tv_client_patterns") or [r"(?i)roku", r"(?i)jellyflam3"]
    ignore = ig.get("ignore_client_patterns") or [
        r"(?i)jellyflam3.?screensaver",
        r"(?i)screensaver",
    ]
    block_transcode = bool(ig.get("block_on_any_transcode", True))
    block_non_tv = bool(ig.get("block_non_tv_playback", False))
    within = int(ig.get("active_within_seconds", 60))

    for s in sessions:
        if not s:
            continue
        # Guide 01: image-only screensaver must never close the furnace gate.
        if ignore and _matches_tv(s, ignore):
            continue
        if block_transcode and s.get("TranscodingInfo"):
            return GateDecision(True, "active_transcode")
        playing = bool(s.get("NowPlayingItem")) or _recent_playback_checkin(s, within)
        if not playing:
            continue
        if _matches_tv(s, patterns):
            return GateDecision(True, "active_tv_client")
        if block_non_tv:
            return GateDecision(True, "active_playback")
    return GateDecision(False, "idle")


def fetch_sessions(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """GET Jellyfin /Sessions filtered by activeWithinSeconds from idle_gate config."""
    jf = cfg.get("jellyfin") or {}
    base = (jf.get("url") or "").rstrip("/")
    key = jf.get("api_key") or ""
    if not base or not key:
        raise RuntimeError("jellyfin.url and jellyfin.api_key required")
    within = int((cfg.get("idle_gate") or {}).get("active_within_seconds", 60))
    url = f"{base}/Sessions?activeWithinSeconds={within}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f'MediaBrowser Token="{key}"',
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data if isinstance(data, list) else []


class IdleGateSupervisor:
    """Poll Jellyfin sessions, write gate status JSON, optionally freeze/thaw the worker."""

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = cfg
        self.ig = cfg.get("idle_gate") or {}
        self.idle_delay = int(self.ig.get("idle_delay_sec", 600))
        self.poll = int(self.ig.get("poll_interval_sec", 20))
        self.status_path = resolve_path(cfg, "status_file")
        self._clear_since: float | None = None
        self._last_open: bool | None = None
        # idle_delay applies only after we have observed a blocking session
        self._seen_block = False
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        self._hydrate_from_status()

    def _hydrate_from_status(self) -> None:
        """Restore delay RAM from status_file after systemd restart."""
        if not self.status_path.is_file():
            return
        try:
            data = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        if data.get("gate") != "closed":
            return
        self._seen_block = True
        if (data.get("reason") or "") != "idle_delay":
            return
        parsed = parse_gate_timestamp(data.get("idle_clear_since"))
        if parsed is not None:
            self._clear_since = parsed.timestamp()

    def evaluate(self, sessions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        """One poll cycle: update status file and return the gate payload."""
        if not self.ig.get("enabled", True):
            payload = self._write(open_gate=True, reason="disabled", seconds=0)
            self._maybe_freeze(True)
            return payload
        sessions = sessions if sessions is not None else fetch_sessions(self.cfg)
        decision = should_block_render(sessions, self.cfg)
        now = time.time()
        if decision.blocked:
            self._clear_since = None
            self._seen_block = True
            payload = self._write(open_gate=False, reason=decision.reason, seconds=self.idle_delay)
            self._maybe_freeze(False)
            return payload
        # Cold start / never blocked: open immediately (do not invent an idle_delay).
        if not self._seen_block:
            payload = self._write(open_gate=True, reason="idle", seconds=0)
            self._maybe_freeze(True)
            return payload
        if self._clear_since is None:
            self._clear_since = now
        elapsed = now - self._clear_since
        remaining = min(self.idle_delay, max(0, int(self.idle_delay - elapsed)))
        if remaining > 0:
            payload = self._write(
                open_gate=False,
                reason="idle_delay",
                seconds=remaining,
                last_clear=self._clear_since,
            )
            self._maybe_freeze(False)
            return payload
        payload = self._write(open_gate=True, reason="idle", seconds=0, last_clear=self._clear_since)
        self._maybe_freeze(True)
        return payload

    def _maybe_freeze(self, open_gate: bool) -> None:
        """Optional last-resort freeze of the worker unit (systemd freeze/thaw)."""
        if not self.ig.get("freeze_worker", False):
            return
        if self._last_open is open_gate:
            return
        self._last_open = open_gate
        unit = self.ig.get("worker_unit") or "jellyflam3-worker.service"
        action = "thaw" if open_gate else "freeze"
        try:
            subprocess.run(["systemctl", action, unit], check=False, timeout=10)
            log.info("systemctl %s %s", action, unit)
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            log.warning("freeze_worker %s failed: %s", action, exc)

    def _write(
        self,
        *,
        open_gate: bool,
        reason: str,
        seconds: int,
        last_clear: float | None = None,
    ) -> dict[str, Any]:
        """Persist gate status JSON and return the same payload."""
        payload = {
            "gate": "open" if open_gate else "closed",
            "reason": reason,
            "seconds_until_resume": seconds,
            "last_tv_activity": None
            if open_gate and reason == "idle"
            else datetime.now(timezone.utc).isoformat(),
            "idle_clear_since": datetime.fromtimestamp(last_clear, timezone.utc).isoformat()
            if last_clear
            else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        persist_status(self.status_path, payload)
        return payload

    def run_forever(self) -> None:
        """Poll forever; on errors write a closed gate with the exception reason."""
        log.info("idle-gate watching status=%s", self.status_path)
        while True:
            try:
                st = self.evaluate()
                log.info("gate=%s reason=%s eta=%ss", st["gate"], st["reason"], st["seconds_until_resume"])
            except Exception as exc:  # noqa: BLE001
                log.exception("idle-gate poll failed: %s", exc)
                self._write(open_gate=False, reason=f"error:{exc}", seconds=self.idle_delay)
            time.sleep(self.poll)


def is_gate_open(cfg: dict[str, Any]) -> bool:
    """Read-only: True when status says open and ``updated_at`` is fresh.

    Missing, corrupt, non-object, or stale ``open`` is **closed**. This helper
    never writes the status file (supervisor-only SoT).
    """
    ig = cfg.get("idle_gate") or {}
    if not ig.get("enabled", True):
        return True
    data = load_gate_status(cfg)
    if data is None:
        return False
    if data.get("gate") != "open":
        return False
    updated = parse_gate_timestamp(data.get("updated_at"))
    if updated is None:
        log.warning("gate status missing updated_at (treating closed)")
        return False
    age = (datetime.now(timezone.utc) - updated).total_seconds()
    if age > stale_after_sec(cfg):
        log.warning("gate status stale (treating closed): age=%.0fs", age)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """CLI: run the idle-gate supervisor loop (or one-shot status)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="JellyFlam3 idle-gate supervisor")
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    p.add_argument("--once", action="store_true", help="Evaluate once and exit")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    sup = IdleGateSupervisor(cfg)
    if args.once:
        print(json.dumps(sup.evaluate(), indent=2))
        return 0
    sup.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
