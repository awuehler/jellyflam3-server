"""Purpose: JellyFlam3 Hammer — nuclear local factory reset (Phase 3 guide 07).

Requirements: Config paths (inbox, quarantine, done, jobs, frames, media_library,
log_dir, status_file); optional systemd worker unit; optional Jellyfin refresh.

Usage:
  python -m pipeline.hammer --dry-run
  python -m pipeline.hammer --worker --confirm HAMMER
  python -m pipeline.hammer --all --force-stop --confirm HAMMER

Assumptions: Default is dry-run of --all. Never touches secrets.env, jellyflam3.yaml,
git checkout, Tailscale/Syncthing device identity, genomes/samples, genomes/pedigree,
or display_profiles. Distinct from Sheep Shears (per-sheep cascade).
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import load_config, resolve_path
from pipeline.media_layout import ensure_catalog_dir
from pipeline.worker import genomes_done_dir

log = logging.getLogger("jellyflam3.hammer")

CONFIRM_TOKEN = "HAMMER"
KEEP_NAMES = frozenset(
    {
        ".gitkeep",
        ".gitignore",
        ".stignore",
        ".stfolder",
        "OPT_IN",
    }
)
PROTECTED_FILE_NAMES = frozenset(
    {
        "secrets.env",
        "jellyflam3.yaml",
    }
)
FORBIDDEN_MEDIA_ROOTS = frozenset(
    {
        Path("/"),
        Path("/media"),
        Path("/home"),
        Path("/var"),
        Path("/usr"),
        Path("/etc"),
        Path("/opt"),
        Path("/root"),
    }
)

POST_CHECKLIST = [
    "sudo systemctl start jellyflam3-worker",
    "python3 -m pipeline.seed_inbox --config configs/jellyflam3.yaml   # or shears add / breed",
    "python3 -m pipeline.media_layout --config configs/jellyflam3.yaml",
    "./scripts/healthcheck.sh",
    "# Jellyfin library scan is triggered when --outputs/--all applied; confirm flock empty then re-seed",
]


@dataclass
class HammerClass:
    """One purge class (jobs, inbox, media, …) with size/count for dry-run."""

    name: str
    root: Path
    action: str
    file_count: int = 0
    byte_size: int = 0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "root": str(self.root),
            "action": self.action,
            "file_count": self.file_count,
            "byte_size": self.byte_size,
            "notes": list(self.notes),
        }


@dataclass
class HammerPlan:
    """Resolved Hammer plan for a tier (dry-run or apply)."""

    tier: str
    classes: list[HammerClass] = field(default_factory=list)
    jellyfin_refresh: bool = False
    stop_worker: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "jellyfin_refresh": self.jellyfin_refresh,
            "stop_worker": self.stop_worker,
            "file_count": sum(c.file_count for c in self.classes),
            "byte_size": sum(c.byte_size for c in self.classes),
            "classes": [c.to_dict() for c in self.classes],
            "notes": list(self.notes),
        }


def confirm_tokens() -> set[str]:
    """Accepted --confirm values: HAMMER plus this host's hostname."""
    names = {CONFIRM_TOKEN}
    host = socket.gethostname().strip()
    if host:
        names.add(host)
        names.add(host.split(".")[0])
    return {n for n in names if n}


def worker_unit(cfg: dict[str, Any]) -> str:
    """systemd unit name for the render worker."""
    ig = cfg.get("idle_gate") or {}
    unit = str(ig.get("worker_unit") or "jellyflam3-worker.service")
    if not unit.endswith(".service"):
        unit = f"{unit}.service"
    return unit


def is_worker_active(cfg: dict[str, Any]) -> bool:
    """True when the worker systemd unit is active. False if systemd is absent."""
    unit = worker_unit(cfg)
    try:
        proc = subprocess.run(
            ["systemctl", "is-active", "--quiet", unit],
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("systemctl is-active failed: %s", exc)
        return False
    return proc.returncode == 0


def _systemctl(*args: str) -> subprocess.CompletedProcess[bytes]:
    """Run systemctl; retry with sudo when unprivileged stop fails."""
    try:
        proc = subprocess.run(["systemctl", *args], check=False, capture_output=True)
    except FileNotFoundError:
        raise
    if proc.returncode == 0 or args[0] != "stop":
        return proc
    sudo = subprocess.run(["sudo", "systemctl", *args], check=False, capture_output=True)
    if sudo.returncode == 0:
        return sudo
    return proc


def stop_worker_unit(cfg: dict[str, Any]) -> None:
    """Stop the worker unit; raise if it remains active. No-op without systemd."""
    unit = worker_unit(cfg)
    try:
        _systemctl("stop", unit)
    except FileNotFoundError:
        log.info("systemctl not found; skip worker stop")
        return
    except OSError as exc:
        log.warning("systemctl stop failed: %s", exc)
        return
    if is_worker_active(cfg):
        raise RuntimeError(
            f"worker unit still active after stop: {unit} "
            "(try: sudo systemctl stop jellyflam3-worker)"
        )
    log.info("stopped %s", unit)


def _repo_root(cfg: dict[str, Any]) -> Path:
    raw = cfg.get("_repo_root")
    if raw:
        return Path(str(raw))
    return Path(__file__).resolve().parents[1]


def _is_forbidden_media(media: Path) -> str | None:
    """Return a reason if media_library is too dangerous to wipe."""
    try:
        resolved = media.resolve()
    except OSError:
        resolved = media
    if resolved in FORBIDDEN_MEDIA_ROOTS or len(resolved.parts) <= 1:
        return f"media_library is a forbidden root: {resolved}"
    if (resolved / ".git").exists():
        return f"media_library looks like a git checkout: {resolved}"
    return None


def _dir_stats(root: Path, *, keep: frozenset[str] = KEEP_NAMES) -> tuple[int, int]:
    """Count files/bytes under root that Hammer would remove (not keep-names)."""
    if not root.exists():
        return 0, 0
    count = 0
    size = 0
    if root.is_file():
        return 1, int(root.stat().st_size)
    try:
        for p in root.rglob("*"):
            if p.name in keep or p.name in PROTECTED_FILE_NAMES:
                continue
            if p.is_file() or p.is_symlink():
                count += 1
                try:
                    size += p.stat().st_size if p.is_file() else 0
                except OSError:
                    pass
    except OSError as exc:
        log.warning("stat walk failed for %s: %s", root, exc)
    return count, size


def _empty_dir_contents(root: Path, *, keep: frozenset[str] = KEEP_NAMES) -> None:
    """Delete children of root; keep the directory and keep-named entries."""
    if not root.is_dir():
        return
    for child in list(root.iterdir()):
        if child.name in keep or child.name in PROTECTED_FILE_NAMES:
            continue
        if child.is_symlink() or child.is_file():
            child.unlink(missing_ok=True)
        elif child.is_dir():
            shutil.rmtree(child)
        log.info("removed %s", child)


def _safe_empty(root: Path, *, keep: frozenset[str] = KEEP_NAMES) -> None:
    """Empty a directory after refusing protected filenames as the root itself."""
    if root.name in PROTECTED_FILE_NAMES:
        raise RuntimeError(f"refusing to hammer protected path {root}")
    root.mkdir(parents=True, exist_ok=True)
    _empty_dir_contents(root, keep=keep)


def _cache_sibling(frames: Path, name: str) -> Path:
    """``/var/cache/jellyflam3/{name}`` when frames is ``.../frames``."""
    return frames.parent / name


def _class_for_dir(
    name: str,
    root: Path,
    *,
    action: str = "empty_contents",
    extra_notes: list[str] | None = None,
) -> HammerClass:
    notes = list(extra_notes or [])
    if not root.exists():
        notes.append("path does not exist yet (will mkdir on apply)")
        return HammerClass(name=name, root=root, action=action, notes=notes)
    count, size = _dir_stats(root)
    return HammerClass(
        name=name,
        root=root,
        action=action,
        file_count=count,
        byte_size=size,
        notes=notes,
    )


def _class_for_file(name: str, path: Path) -> HammerClass:
    notes: list[str] = []
    if not path.exists():
        notes.append("missing (ok)")
        return HammerClass(name=name, root=path, action="delete_file", notes=notes)
    size = int(path.stat().st_size) if path.is_file() else 0
    return HammerClass(
        name=name,
        root=path,
        action="delete_file",
        file_count=1 if path.is_file() else 0,
        byte_size=size,
        notes=notes,
    )


def resolve_tier(args: argparse.Namespace) -> str:
    """Map CLI flags to a tier name (union if several scoped flags)."""
    flags = []
    if args.worker:
        flags.append("worker")
    if args.inputs:
        flags.append("inputs")
    if args.outputs:
        flags.append("outputs")
    if args.all:
        flags.append("all")
    if not flags:
        return "all"
    if "all" in flags:
        return "all"
    if "outputs" in flags and "inputs" in flags:
        return "all"
    if "outputs" in flags:
        return "outputs"
    if "inputs" in flags:
        return "inputs"
    return "worker"


def build_plan(
    cfg: dict[str, Any],
    *,
    tier: str,
    peers_inbox: bool = False,
    transcode_cache: bool = False,
) -> HammerPlan:
    """Build a Hammer plan from config paths (no deletes)."""
    plan = HammerPlan(tier=tier, stop_worker=True)
    inbox = resolve_path(cfg, "genomes_inbox")
    quarantine = resolve_path(cfg, "genomes_quarantine")
    done = genomes_done_dir(cfg)
    jobs = resolve_path(cfg, "jobs_dir")
    frames = resolve_path(cfg, "frames_scratch")
    media = resolve_path(cfg, "media_library")
    log_dir = resolve_path(cfg, "log_dir") if "log_dir" in (cfg.get("paths") or {}) else jobs.parent / "logs"
    status = resolve_path(cfg, "status_file") if "status_file" in (cfg.get("paths") or {}) else jobs.parent / "idle_gate_status.json"

    reason = _is_forbidden_media(media)
    if reason and tier in {"outputs", "all"}:
        plan.notes.append(reason)
        raise RuntimeError(reason)

    repo = _repo_root(cfg)
    samples = repo / "genomes" / "samples"
    pedigree = repo / "genomes" / "pedigree"
    plan.notes.append("never delete: secrets.env, jellyflam3.yaml, git, samples/, pedigree/, display_profiles/")
    plan.notes.append(f"protected trees: {samples} ; {pedigree}")

    # Tier 1 worker env
    plan.classes.append(_class_for_dir("jobs", jobs))
    plan.classes.append(_class_for_dir("frames_scratch", frames))
    plan.classes.append(_class_for_dir("logs", log_dir))
    plan.classes.append(_class_for_file("idle_gate_status", status))

    if tier in {"inputs", "all"}:
        plan.classes.append(_class_for_dir("genomes_inbox", inbox))
        plan.classes.append(_class_for_dir("genomes_quarantine", quarantine))

    if tier in {"outputs", "all"}:
        plan.classes.append(_class_for_dir("genomes_done", done))
        by_gen = media / "by-generation"
        plan.classes.append(
            _class_for_dir(
                "media_library",
                by_gen if by_gen.exists() or not media.exists() else media,
                extra_notes=["keep media_library mount root; wipe flock tree"],
            )
        )
        plan.jellyfin_refresh = True

    if peers_inbox and tier in {"inputs", "all"}:
        from pipeline.peering import peers_inbox as peers_inbox_path

        pin = peers_inbox_path(cfg)
        plan.classes.append(
            _class_for_dir(
                "peers_inbox",
                pin,
                extra_notes=["local peer land only; Syncthing identity untouched"],
            )
        )

    if transcode_cache or tier == "all":
        for cache_name in ("transcodes", "live-hls"):
            cpath = _cache_sibling(frames, cache_name)
            if cpath.exists() or transcode_cache:
                plan.classes.append(
                    _class_for_dir(
                        cache_name,
                        cpath,
                        extra_notes=["optional cache; skipped if missing on apply"],
                    )
                )

    return plan


def apply_plan(cfg: dict[str, Any], plan: HammerPlan, *, dry_run: bool) -> dict[str, Any]:
    """Apply (or dry-run) a Hammer plan. Recreates empty layout after wipe."""
    result: dict[str, Any] = {
        "ok": True,
        "dry_run": dry_run,
        "tier": plan.tier,
        "plan": plan.to_dict(),
        "removed": [],
        "jellyfin": None,
    }
    if dry_run:
        return result

    if plan.stop_worker:
        stop_worker_unit(cfg)

    media = resolve_path(cfg, "media_library")
    for cls in plan.classes:
        if cls.action == "delete_file":
            if cls.root.is_file():
                cls.root.unlink()
                result["removed"].append(str(cls.root))
            continue
        if cls.name == "media_library":
            flock = media / "by-generation"
            if flock.exists():
                _empty_dir_contents(flock)
                result["removed"].append(str(flock) + "/*")
            elif media.is_dir():
                for child in list(media.iterdir()):
                    if child.name in KEEP_NAMES or child.name in PROTECTED_FILE_NAMES:
                        continue
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink(missing_ok=True)
                result["removed"].append(str(media) + "/*")
            ensure_catalog_dir(media / "by-generation")
            continue
        if cls.root.name in PROTECTED_FILE_NAMES:
            raise RuntimeError(f"refusing protected path {cls.root}")
        if not cls.root.exists() and cls.name in {"transcodes", "live-hls"}:
            continue
        _safe_empty(cls.root)
        result["removed"].append(str(cls.root) + "/*")

    # Recreate worker dirs + idle-gate bootstrap so cold start is open.
    resolve_path(cfg, "jobs_dir").mkdir(parents=True, exist_ok=True)
    resolve_path(cfg, "frames_scratch").mkdir(parents=True, exist_ok=True)
    inbox = resolve_path(cfg, "genomes_inbox")
    inbox.mkdir(parents=True, exist_ok=True)
    resolve_path(cfg, "genomes_quarantine").mkdir(parents=True, exist_ok=True)
    genomes_done_dir(cfg).mkdir(parents=True, exist_ok=True)
    if "status_file" in (cfg.get("paths") or {}):
        status = resolve_path(cfg, "status_file")
        status.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "gate": "open",
            "reason": "hammer",
            "seconds_until_resume": 0,
            "last_tv_activity": None,
            "idle_clear_since": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        status.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    if plan.jellyfin_refresh:
        result["jellyfin"] = _refresh_jellyfin(cfg)

    return result


def _refresh_jellyfin(cfg: dict[str, Any]) -> dict[str, Any]:
    """Trigger Jellyfin library refresh; soft-fail if API unavailable."""
    jf = cfg.get("jellyfin") or {}
    if not jf.get("url") or not jf.get("api_key"):
        return {"ok": False, "error": "jellyfin.url / api_key missing — scan skipped"}
    try:
        from pipeline.jellyfin_client import JellyfinClient

        JellyfinClient.from_config(cfg).refresh_library()
        return {"ok": True, "action": "Library/Refresh"}
    except Exception as exc:  # noqa: BLE001 — operator path; never abort after disk wipe
        log.warning("Jellyfin refresh failed: %s", exc)
        return {"ok": False, "error": str(exc)}


def print_plan(plan: HammerPlan, *, dry_run: bool) -> None:
    """Human-readable Hammer listing."""
    mode = "DRY-RUN (no deletes)" if dry_run else "APPLY"
    print(f"=== JellyFlam3 Hammer — {mode} ===")
    print(f"tier={plan.tier}")
    print(f"stop_worker={plan.stop_worker}  jellyfin_refresh={plan.jellyfin_refresh}")
    total_n = sum(c.file_count for c in plan.classes)
    total_b = sum(c.byte_size for c in plan.classes)
    print(f"totals: files={total_n}  bytes={total_b}")
    for cls in plan.classes:
        print(f"\n[{cls.name}] {cls.action}")
        print(f"  {cls.root}")
        print(f"  files={cls.file_count}  bytes={cls.byte_size}")
        for n in cls.notes:
            print(f"  note: {n}")
    if plan.notes:
        print("\n[notes]")
        for n in plan.notes:
            print(f"  {n}")
    if dry_run:
        print(
            f"\nRe-run with --confirm {CONFIRM_TOKEN} (or this hostname) to apply. "
            "Use --force-stop if jellyflam3-worker is active."
        )
    else:
        print("\n=== Post-Hammer checklist ===")
        for line in POST_CHECKLIST:
            print(f"  {line}")


def run_hammer(
    cfg: dict[str, Any],
    *,
    tier: str,
    confirm: str,
    force_stop: bool,
    peers_inbox: bool,
    transcode_cache: bool,
    as_json: bool,
) -> int:
    """CLI body: plan, gate, optional apply."""
    dry_run = confirm not in confirm_tokens()
    if confirm and dry_run:
        print(
            f"ERROR: --confirm must be {CONFIRM_TOKEN!r} or this hostname "
            f"(got {confirm!r})",
            flush=True,
        )
        return 2

    plan = build_plan(
        cfg, tier=tier, peers_inbox=peers_inbox, transcode_cache=transcode_cache
    )

    if not dry_run:
        if is_worker_active(cfg):
            if not force_stop:
                print(
                    "ERROR: worker unit is active. Pass --force-stop to stop it "
                    "before Hammer, or stop it yourself first.",
                    flush=True,
                )
                return 2
        elif force_stop:
            plan.notes.append("--force-stop set (worker was already inactive)")

    if as_json and dry_run:
        payload = plan.to_dict()
        payload["dry_run"] = True
        print(json.dumps(payload, indent=2))
        return 0

    if not as_json:
        print_plan(plan, dry_run=dry_run)
    if dry_run:
        return 0

    if force_stop and is_worker_active(cfg):
        stop_worker_unit(cfg)

    result = apply_plan(cfg, plan, dry_run=False)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print("\nHammer applied.")
        if result.get("jellyfin"):
            print(f"jellyfin: {result['jellyfin']}")
        print("\n=== Post-Hammer checklist ===")
        for line in POST_CHECKLIST:
            print(f"  {line}")
    return 0 if result.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m pipeline.hammer",
        description="JellyFlam3 Hammer — nuclear local factory reset (not Shears)",
    )
    p.add_argument("--config", default="configs/jellyflam3.yaml")
    p.add_argument("--worker", action="store_true", help="Tier 1: jobs + frames + logs/status")
    p.add_argument("--inputs", action="store_true", help="Tier 2: worker + inbox/quarantine")
    p.add_argument("--outputs", action="store_true", help="Tier 3: worker + done + media + Jellyfin")
    p.add_argument("--all", action="store_true", help="Tier 4: full Hammer (default if no tier flag)")
    p.add_argument(
        "--peers-inbox",
        action="store_true",
        help="Also empty local genomes/peers/inbox (not Syncthing config)",
    )
    p.add_argument(
        "--transcode-cache",
        action="store_true",
        help="Also empty transcodes/ and live-hls/ beside frames_scratch",
    )
    p.add_argument(
        "--confirm",
        default="",
        help=f"Must be {CONFIRM_TOKEN!r} or this hostname to apply (default: dry-run)",
    )
    p.add_argument(
        "--force-stop",
        action="store_true",
        help="systemctl stop worker unit if active (required to apply while running)",
    )
    p.add_argument("--json", action="store_true")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Force dry-run even if --confirm is set",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    confirm = "" if args.dry_run else args.confirm
    return run_hammer(
        cfg,
        tier=resolve_tier(args),
        confirm=confirm,
        force_stop=args.force_stop,
        peers_inbox=args.peers_inbox,
        transcode_cache=args.transcode_cache,
        as_json=args.json,
    )


if __name__ == "__main__":
    sys.exit(main())
