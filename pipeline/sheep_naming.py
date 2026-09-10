#!/usr/bin/env python3
"""Purpose: Memorable catalog aliases (adjective_surname) on sidecar JSON.

Requirements: catalog ``*.jellyflam3.json`` beside MP4s; stdlib only.

Usage:
  python3 -m pipeline.sheep_naming backfill
  python3 -m pipeline.sheep_naming backfill --dry-run
  python3 -m pipeline.sheep_naming set-alias --stem electricsheep.247.00505 --alias frosty_swirles
  python3 -m pipeline.sheep_naming clear-alias --stem electricsheep.247.00505
  python3 -m pipeline.sheep_naming resolve frosty_swirles
  python3 -m pipeline.sheep_naming show --stem electricsheep.247.00505

Assumptions: Filename stays canonical. Hash-seed from stem so re-ingest of the
same sheep keeps the alias. ``alias_source=human`` is sticky until clear-alias.
LLM path and pasture filename/alias toggles stay parked (guide 09).
Docs: docs/phase4/09_SHEEP_NAMING.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Iterable

from pipeline.config import load_config, resolve_path
from pipeline.stills import write_sidecar

# Modest offline vocabulary (scientists, artists, places). Not flam3 nick=.
ADJECTIVES: tuple[str, ...] = (
    "amber",
    "arctic",
    "ashen",
    "azure",
    "bold",
    "bright",
    "calm",
    "copper",
    "cosmic",
    "crisp",
    "curious",
    "deep",
    "dusty",
    "electric",
    "ember",
    "faint",
    "fiery",
    "foggy",
    "fractal",
    "frosty",
    "gentle",
    "gilded",
    "glassy",
    "golden",
    "hazy",
    "hollow",
    "icy",
    "indigo",
    "iron",
    "ivory",
    "jade",
    "keen",
    "kinetic",
    "lilac",
    "liquid",
    "lunar",
    "marble",
    "misty",
    "molten",
    "neon",
    "nimbus",
    "ochre",
    "opal",
    "pale",
    "pearl",
    "pewter",
    "plasma",
    "polar",
    "prism",
    "quiet",
    "rapid",
    "rose",
    "ruby",
    "rustic",
    "sandy",
    "scarlet",
    "silent",
    "silver",
    "smoky",
    "solar",
    "sparse",
    "stark",
    "steel",
    "still",
    "stormy",
    "subtle",
    "swift",
    "teal",
    "tender",
    "tidal",
    "umber",
    "velvet",
    "vivid",
    "warm",
    "wild",
    "windy",
    "winter",
    "wooly",
)

SURNAMES: tuple[str, ...] = (
    "babbage",
    "bardeen",
    "bohr",
    "brahe",
    "cantor",
    "clarke",
    "curie",
    "darwin",
    "dirac",
    "dyson",
    "edison",
    "euler",
    "faraday",
    "fermi",
    "feynman",
    "galileo",
    "gauss",
    "godel",
    "goodall",
    "hawking",
    "herschel",
    "hopper",
    "hubble",
    "huygens",
    "hypatia",
    "kepler",
    "knuth",
    "lagrange",
    "laplace",
    "lovelace",
    "maxwell",
    "mendeleev",
    "minkowski",
    "noether",
    "ohm",
    "oslo",
    "pascal",
    "planck",
    "poincare",
    "ptolemy",
    "ramanujan",
    "riemann",
    "sagan",
    "swirles",
    "turing",
    "volta",
    "watt",
    "cairo",
    "kyoto",
    "cusco",
    "andes",
    "nile",
    "yukon",
    "sahel",
    "albers",
    "calvino",
    "escher",
    "miro",
    "mondrian",
    "neruda",
    "okapi",
    "salk",
    "tesla",
    "vesalius",
)

ALIAS_RE = re.compile(r"^[a-z][a-z0-9]*_[a-z][a-z0-9]*$")
HUMAN_SOURCES = frozenset({"human"})
KEEP_SOURCES = frozenset({"auto", "human", "llm"})


def naming_enabled(cfg: dict[str, Any] | None) -> bool:
    block = (cfg or {}).get("naming") or {}
    if not isinstance(block, dict):
        return True
    if "enabled" not in block:
        return True
    return bool(block.get("enabled"))


def normalize_alias(raw: str) -> str:
    s = (raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def validate_alias(alias: str) -> str:
    n = normalize_alias(alias)
    if not ALIAS_RE.match(n):
        raise ValueError("alias must be snake_case adjective_surname (ascii)")
    return n


def generate_alias(
    stem: str,
    existing: Iterable[str],
    *,
    adjectives: tuple[str, ...] = ADJECTIVES,
    surnames: tuple[str, ...] = SURNAMES,
) -> str:
    """Stable hash-seed from stem; walk the pair grid on collision."""
    taken = {normalize_alias(x) for x in existing if x}
    adj = adjectives
    sur = surnames
    n_adj = len(adj)
    n_sur = len(sur)
    space = n_adj * n_sur
    if space < 1:
        raise RuntimeError("empty alias word lists")
    digest = hashlib.sha256(stem.encode("utf-8")).hexdigest()
    rng = random.Random(int(digest, 16))
    start = rng.randrange(space)
    for step in range(space):
        idx = (start + step) % space
        alias = f"{adj[idx // n_sur]}_{sur[idx % n_sur]}"
        if alias not in taken:
            return alias
    raise RuntimeError("alias space exhausted")


def source_of(sidecar: dict[str, Any] | None) -> str:
    return str((sidecar or {}).get("alias_source") or "").strip().lower()


def alias_of(sidecar: dict[str, Any] | None) -> str:
    return normalize_alias(str((sidecar or {}).get("alias") or ""))


def is_human_locked(sidecar: dict[str, Any] | None) -> bool:
    return source_of(sidecar) in HUMAN_SOURCES and bool(alias_of(sidecar))


def ensure_auto_alias(
    sidecar: dict[str, Any],
    stem: str,
    taken: Iterable[str],
) -> dict[str, Any]:
    """Write alias/alias_source=auto when missing. Never overwrite human."""
    if is_human_locked(sidecar):
        return sidecar
    existing = alias_of(sidecar)
    src = source_of(sidecar)
    if existing and src in KEEP_SOURCES:
        return sidecar
    if existing and not src:
        sidecar["alias"] = existing
        sidecar["alias_source"] = "auto"
        return sidecar
    skip = {existing} if existing else set()
    taken_set = {normalize_alias(x) for x in taken if x} - skip
    sidecar["alias"] = generate_alias(stem, taken_set)
    sidecar["alias_source"] = "auto"
    return sidecar


def set_human_alias(
    sidecar: dict[str, Any],
    alias: str,
    taken: Iterable[str],
) -> dict[str, Any]:
    n = validate_alias(alias)
    current = alias_of(sidecar)
    others = {normalize_alias(x) for x in taken if x} - {current}
    if n in others:
        raise ValueError("alias already used: %s" % n)
    sidecar["alias"] = n
    sidecar["alias_source"] = "human"
    return sidecar


def clear_to_auto(
    sidecar: dict[str, Any],
    stem: str,
    taken: Iterable[str],
) -> dict[str, Any]:
    current = alias_of(sidecar)
    others = {normalize_alias(x) for x in taken if x} - {current}
    sidecar.pop("alias", None)
    sidecar.pop("alias_source", None)
    return ensure_auto_alias(sidecar, stem, others)


def iter_sidecars(media_root: Path) -> list[Path]:
    root = Path(media_root) / "by-generation"
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.rglob("*.jellyflam3.json")):
        if any(part.startswith("_") for part in p.parts):
            continue
        out.append(p)
    return out


def sidecar_stem(path: Path) -> str:
    name = path.name
    suffix = ".jellyflam3.json"
    if name.endswith(suffix):
        return name[: -len(suffix)]
    return path.stem


def collect_taken_aliases(
    media_root: Path,
    *,
    exclude_stem: str | None = None,
) -> set[str]:
    taken: set[str] = set()
    skip = (exclude_stem or "").strip()
    for path in iter_sidecars(media_root):
        if skip and sidecar_stem(path) == skip:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        a = alias_of(data)
        if a:
            taken.add(a)
    return taken


def load_sidecar_for_stem(media_root: Path, stem: str) -> tuple[Path, dict[str, Any]]:
    """Resolve catalog sidecar by stem (MP4 basename)."""
    want = stem.strip()
    if want.lower().endswith(".mp4"):
        want = Path(want).stem
    matches = [p for p in iter_sidecars(media_root) if sidecar_stem(p) == want]
    if not matches:
        raise FileNotFoundError("no sidecar for stem %s" % want)
    path = matches[0]
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("sidecar is not an object: %s" % path)
    return path, data


def resolve_alias(media_root: Path, alias: str) -> str | None:
    want = normalize_alias(alias)
    hits: list[str] = []
    for path in iter_sidecars(media_root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if alias_of(data) == want:
            hits.append(sidecar_stem(path))
    if not hits:
        return None
    if len(hits) > 1:
        raise ValueError("alias %s maps to multiple stems: %s" % (want, ", ".join(hits)))
    return hits[0]


def backfill_catalog(
    media_root: Path,
    *,
    dry_run: bool = False,
    limit: int = 0,
) -> list[dict[str, str]]:
    """Assign auto aliases to sidecars that lack one. Human rows are skipped."""
    rows: list[dict[str, str]] = []
    taken = collect_taken_aliases(media_root)
    n = 0
    for path in iter_sidecars(media_root):
        if limit and n >= limit:
            break
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        stem = sidecar_stem(path)
        before = alias_of(data), source_of(data)
        if is_human_locked(data) or (alias_of(data) and source_of(data) in KEEP_SOURCES):
            continue
        others = set(taken) - {alias_of(data)}
        ensure_auto_alias(data, stem, others)
        after = alias_of(data)
        if after:
            taken.add(after)
        n += 1
        action = "would_write" if dry_run else "wrote"
        rows.append(
            {
                "stem": stem,
                "alias": after,
                "source": source_of(data),
                "action": action,
                "prior": before[0],
            }
        )
        if not dry_run:
            mp4 = path.with_name(stem + ".mp4")
            write_sidecar(mp4, data)
    return rows


def _media_root(config: Path) -> Path:
    cfg = load_config(str(config))
    return resolve_path(cfg, "media_library")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Catalog sheep aliases (adjective_surname)")
    ap.add_argument("--config", default="configs/jellyflam3.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_bf = sub.add_parser("backfill", help="Assign auto aliases where missing")
    p_bf.add_argument("--dry-run", action="store_true")
    p_bf.add_argument("--limit", type=int, default=0)

    p_set = sub.add_parser("set-alias", help="Sticky human override")
    p_set.add_argument("--stem", required=True)
    p_set.add_argument("--alias", required=True)

    p_clear = sub.add_parser("clear-alias", help="Reset to auto and regenerate")
    p_clear.add_argument("--stem", required=True)

    p_res = sub.add_parser("resolve", help="Print stem for an alias")
    p_res.add_argument("alias")

    p_show = sub.add_parser("show", help="Print alias fields for a stem")
    p_show.add_argument("--stem", required=True)

    args = ap.parse_args(argv)
    media = _media_root(Path(args.config))
    cfg = load_config(str(args.config))
    if not naming_enabled(cfg) and args.cmd in {"backfill"}:
        print("naming.enabled is false — skip", file=sys.stderr)
        return 0

    if args.cmd == "backfill":
        rows = backfill_catalog(media, dry_run=args.dry_run, limit=args.limit)
        print(json.dumps({"count": len(rows), "rows": rows}, indent=2))
        return 0

    if args.cmd == "resolve":
        stem = resolve_alias(media, args.alias)
        if not stem:
            print("not found", file=sys.stderr)
            return 1
        print(stem)
        return 0

    if args.cmd == "show":
        _path, data = load_sidecar_for_stem(media, args.stem)
        print(
            json.dumps(
                {
                    "stem": sidecar_stem(_path),
                    "alias": alias_of(data) or None,
                    "alias_source": source_of(data) or None,
                },
                indent=2,
            )
        )
        return 0

    path, data = load_sidecar_for_stem(media, args.stem)
    stem = sidecar_stem(path)
    taken = collect_taken_aliases(media, exclude_stem=stem)
    if args.cmd == "set-alias":
        set_human_alias(data, args.alias, taken)
    elif args.cmd == "clear-alias":
        clear_to_auto(data, stem, taken)
    mp4 = path.with_name(stem + ".mp4")
    write_sidecar(mp4, data)
    print(
        json.dumps(
            {"stem": stem, "alias": alias_of(data), "alias_source": source_of(data)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
