"""Purpose: Hardware profile overlays for Pi-from-scratch hosts (Phase 2 guide 09).

Requirements: Profile YAMLs under configs/profiles/; target jellyflam3.yaml writable for apply.

Usage:
  python3 -m pipeline.hw_profile list
  python3 -m pipeline.hw_profile show rpi-jellyflam3-04
  python3 -m pipeline.hw_profile apply rpi-jellyflam3-08
  python3 -m pipeline.hw_profile apply 04   # short id

Assumptions: Deep-merge overwrites leaves; apply drops YAML comments in the target file.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

import yaml

PROFILE_IDS = ("rpi-jellyflam3-16", "rpi-jellyflam3-08", "rpi-jellyflam3-04")
# Hostnames are letter-suffixed: rpi-jellyflam3-16a, -08b, -04a, …
ALIASES = {
    "16": "rpi-jellyflam3-16",
    "08": "rpi-jellyflam3-08",
    "8": "rpi-jellyflam3-08",
    "04": "rpi-jellyflam3-04",
    "4": "rpi-jellyflam3-04",
}


def profiles_dir(repo_root: Path) -> Path:
    """Directory containing bundled ``rpi-jellyflam3-*.yaml`` overlays."""
    return repo_root / "configs" / "profiles"


def resolve_profile_id(name: str) -> str:
    """Map full id, short id (04/08/16), or hostname suffix to a PROFILE_IDS entry."""
    key = name.strip().lower()
    if key in PROFILE_IDS:
        return key
    if key in ALIASES:
        return ALIASES[key]
    # …-08a / …-16b style: strip trailing letter after class digits
    import re

    m = re.fullmatch(r"(?:rpi-jellyflam3-)?(16|08|04|8|4)[a-z]?", key)
    if m:
        return resolve_profile_id(m.group(1))
    # allow bare suffix match
    for pid in PROFILE_IDS:
        if key.endswith(pid[-2:]) or key == pid.replace("rpi-jellyflam3-", ""):
            return pid
    raise SystemExit(
        f"unknown profile {name!r}; choose one of: {', '.join(PROFILE_IDS)} "
        f"(aliases: 16/16a, 08/08a, 04/04a, …)"
    )


def load_profile(repo_root: Path, profile_id: str) -> dict[str, Any]:
    """Load one profile overlay YAML as a dict (exits if missing/invalid)."""
    path = profiles_dir(repo_root) / f"{profile_id}.yaml"
    if not path.is_file():
        raise SystemExit(f"missing profile file: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"profile must be a mapping: {path}")
    return data


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` into a deep copy of ``base`` (dicts only)."""
    out = copy.deepcopy(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], val)
        else:
            out[key] = copy.deepcopy(val)
    return out


def apply_profile(
    config_path: Path,
    repo_root: Path,
    profile_id: str,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Deep-merge profile into ``config_path``; dry_run returns merged dict without writing."""
    overlay = load_profile(repo_root, profile_id)
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise SystemExit(f"config must be a mapping: {config_path}")
    merged = deep_merge(raw, overlay)
    if dry_run:
        return merged
    # Preserve readability: dump with default style (comments in target are lost —
    # apply against a copy of jellyflam3.yaml.example on first setup).
    config_path.write_text(
        yaml.safe_dump(merged, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return merged


def cmd_list(repo_root: Path) -> int:
    """Print bundled profile files and hostname naming convention."""
    d = profiles_dir(repo_root)
    print(f"profiles dir: {d}")
    for pid in PROFILE_IDS:
        p = d / f"{pid}.yaml"
        mark = "OK" if p.is_file() else "MISSING"
        print(f"  [{mark}] {pid}")
    print("hostnames: rpi-jellyflam3-16a|16b…, -08a|08b…, -04a|04b…")
    return 0


def cmd_show(repo_root: Path, name: str) -> int:
    """Print resolved profile overlay YAML to stdout."""
    pid = resolve_profile_id(name)
    data = load_profile(repo_root, pid)
    print(f"# {pid}")
    sys.stdout.write(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
    return 0


def cmd_apply(
    repo_root: Path,
    name: str,
    config: Path,
    *,
    dry_run: bool,
) -> int:
    """CLI apply: merge profile into config and print a short render summary."""
    pid = resolve_profile_id(name)
    if not config.is_file():
        raise SystemExit(f"config not found: {config}")
    merged = apply_profile(config, repo_root, pid, dry_run=dry_run)
    render = merged.get("render") or {}
    print(
        f"{'dry-run ' if dry_run else ''}applied {pid} → {config}\n"
        f"  hw_profile={render.get('hw_profile')} edition={render.get('edition')} "
        f"quality={render.get('quality')} supersample={render.get('supersample')} "
        f"max_cpus={render.get('max_cpus')}"
    )
    if dry_run:
        print("(no files written)")
    else:
        print("Restart worker after apply: sudo systemctl restart jellyflam3-worker")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI: list / apply / show hardware profile overlays for Pi variants."""
    root = Path(__file__).resolve().parent.parent
    ap = argparse.ArgumentParser(description="JellyFlam3 HW profile overlays (guide 09)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List bundled profiles")

    p_show = sub.add_parser("show", help="Print a profile overlay")
    p_show.add_argument("profile", help="rpi-jellyflam3-16|08|04 or short id")

    p_apply = sub.add_parser("apply", help="Deep-merge profile into jellyflam3.yaml")
    p_apply.add_argument("profile", help="rpi-jellyflam3-16|08|04 or short id")
    p_apply.add_argument(
        "--config",
        default=str(root / "configs" / "jellyflam3.yaml"),
        help="Target yaml (default: configs/jellyflam3.yaml)",
    )
    p_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="Merge in memory only; do not write",
    )

    args = ap.parse_args(argv)
    if args.cmd == "list":
        return cmd_list(root)
    if args.cmd == "show":
        return cmd_show(root, args.profile)
    if args.cmd == "apply":
        return cmd_apply(root, args.profile, Path(args.config), dry_run=args.dry_run)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
