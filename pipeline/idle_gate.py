"""Purpose: Idle-gate — pause renders when Jellyfin TV clients or transcodes are active.

Requirements: Jellyfin url + api_key; writable status_file; optional systemd freeze of the worker unit.

Usage:
  python -m pipeline.idle_gate --once
  python -m pipeline.idle_gate   # supervisor loop
  Worker polls ``is_gate_open(cfg)``.

Assumptions: Gate stays closed for idle_delay_sec after the last block; cold start opens immediately when idle.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path

log = logging.getLogger("jellyflam3.idle_gate")


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
        remaining = max(0, int(self.idle_delay - elapsed))
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
        self.status_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
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
    """Worker helper: read status_file, or bootstrap with a live session probe if missing."""
    path = resolve_path(cfg, "status_file")
    if not path.is_file():
        if not (cfg.get("idle_gate") or {}).get("enabled", True):
            return True
        # Bootstrap: no status yet — probe Jellyfin live instead of failing
        # closed forever when the idle-gate supervisor has not written yet.
        try:
            decision = should_block_render(fetch_sessions(cfg), cfg)
        except Exception as exc:  # noqa: BLE001
            log.warning("gate bootstrap probe failed (treating closed): %s", exc)
            return False
        if decision.blocked:
            log.info("gate bootstrap closed: %s", decision.reason)
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "gate": "open",
            "reason": "bootstrap",
            "seconds_until_resume": 0,
            "last_tv_activity": None,
            "idle_clear_since": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        log.info("gate bootstrap open (no prior status; sessions idle)")
        return True
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("gate") == "open"


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
