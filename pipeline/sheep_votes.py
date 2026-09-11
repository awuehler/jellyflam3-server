#!/usr/bin/env python3
"""Purpose: Sidecar-only viewer vote tallies (Phase 4 / 08 overlay + sink).

Requirements: catalog ``*.jellyflam3.json`` beside MP4s; stdlib only.

Usage:
  python3 -m pipeline.sheep_votes apply --stem electricsheep.247.00505 --kind like
  python3 -m pipeline.sheep_votes apply --stem electricsheep.247.00505 --kind love
  python3 -m pipeline.sheep_votes apply --stem electricsheep.247.00505 --kind vote
  python3 -m pipeline.sheep_votes show --stem electricsheep.247.00505

Assumptions: The catalog sidecar is the sole metadata SoT. No store under
  ``/var/lib/jellyflam3/``. Unlimited re-vote. Any event sets ``share_candidate``.
  Share cron and idle-breed weights stay parked (Wave 3). HTTP lives on the
  display-profile sink (``POST /v1/sheep-votes``).
Docs: docs/phase4/08_VIEWER_FEEDBACK_LOOP.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from pipeline.config import load_config, resolve_path
from pipeline.sheep_naming import load_sidecar_for_stem, sidecar_stem
from pipeline.stills import sidecar_path_for_mp4

VOTE_KINDS = frozenset({"like", "love", "vote"})

DEFAULT_FEEDBACK: dict[str, Any] = {
    "likes": 0,
    "loves": 0,
    "votes": 0,
    "last_voted_at": None,
    "share_candidate": False,
}


class StemNotFound(FileNotFoundError):
    """No catalog sidecar for the requested stem / media path."""


class InvalidVote(ValueError):
    """Bad vote kind or missing identity fields."""


def utc_now_iso() -> str:
    """UTC timestamp with a Z suffix for sidecar ``last_voted_at``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pick(payload: dict[str, Any], *names: str) -> str:
    """First non-empty string for ``names`` (case-insensitive keys)."""
    lower = {str(k).lower(): v for k, v in payload.items()}
    for name in names:
        raw = lower.get(name.lower())
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            return text
    return ""


def normalize_kind(raw: str) -> str:
    """Map like/love/vote; reject anything else."""
    kind = (raw or "").strip().lower()
    if kind in ("likes", "liked"):
        kind = "like"
    elif kind in ("loves", "loved"):
        kind = "love"
    elif kind in ("votes", "voted"):
        kind = "vote"
    if kind not in VOTE_KINDS:
        raise InvalidVote("kind must be like, love, or vote")
    return kind


def normalize_feedback(raw: Any) -> dict[str, Any]:
    """Coerce ``viewer_feedback``; keep unknown keys."""
    out = dict(DEFAULT_FEEDBACK)
    if isinstance(raw, dict):
        out.update(raw)
    for key in ("likes", "loves", "votes"):
        try:
            out[key] = int(out.get(key) or 0)
        except (TypeError, ValueError):
            out[key] = 0
        if out[key] < 0:
            out[key] = 0
    out["share_candidate"] = bool(out.get("share_candidate"))
    last = out.get("last_voted_at")
    if last is not None:
        text = str(last).strip()
        out["last_voted_at"] = text or None
    return out


def increment_feedback(block: dict[str, Any], kind: str, *, when: str | None = None) -> dict[str, Any]:
    """Mutate a normalized ``viewer_feedback`` block for one event."""
    kind = normalize_kind(kind)
    out = normalize_feedback(block)
    if kind == "like":
        out["likes"] = int(out["likes"]) + 1
    elif kind == "love":
        out["loves"] = int(out["loves"]) + 1
    out["votes"] = int(out["votes"]) + 1
    out["share_candidate"] = True
    out["last_voted_at"] = when or utc_now_iso()
    return out


def stem_from_media_path(media_path: str) -> str:
    """Basename of an MP4 / sidecar path, without suffix."""
    name = Path(str(media_path).replace("\\", "/")).name.strip()
    lower = name.lower()
    if lower.endswith(".jellyflam3.json"):
        return name[: -len(".jellyflam3.json")]
    if lower.endswith(".mp4"):
        return name[: -len(".mp4")]
    return Path(name).stem


def _is_under(child: Path, root: Path) -> bool:
    """True when ``child`` resolves inside ``root`` (no path escape)."""
    try:
        child.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def resolve_vote_sidecar(
    media_root: Path,
    *,
    stem: str = "",
    media_path: str = "",
    generation: str = "",
    sheep_id: str = "",
) -> Path:
    """Locate an existing catalog sidecar. Never create one."""
    want = (stem or "").strip()
    if want.lower().endswith(".mp4"):
        want = Path(want).stem
    errors: list[str] = []
    if want:
        try:
            path, _data = load_sidecar_for_stem(media_root, want)
            return path
        except FileNotFoundError as exc:
            errors.append(str(exc))
    constructed = ""
    if generation.strip() and sheep_id.strip():
        constructed = f"electricsheep.{generation.strip()}.{sheep_id.strip()}"
        if constructed != want:
            try:
                path, _data = load_sidecar_for_stem(media_root, constructed)
                return path
            except FileNotFoundError as exc:
                errors.append(str(exc))
    raw_path = (media_path or "").strip()
    if raw_path:
        derived = stem_from_media_path(raw_path)
        if derived and derived not in {want, constructed}:
            try:
                path, _data = load_sidecar_for_stem(media_root, derived)
                return path
            except FileNotFoundError as exc:
                errors.append(str(exc))
        candidate = Path(raw_path.replace("\\", "/"))
        if candidate.suffix.lower() == ".mp4":
            side = sidecar_path_for_mp4(candidate)
        elif candidate.name.lower().endswith(".jellyflam3.json"):
            side = candidate
        else:
            side = sidecar_path_for_mp4(candidate)
        if side.is_file() and _is_under(side, media_root):
            return side
        errors.append("no sidecar at mediaPath %s" % raw_path)
    if not want and not raw_path and not constructed:
        raise InvalidVote("stem or mediaPath required")
    raise StemNotFound("; ".join(errors) if errors else "no sidecar for stem")


@contextmanager
def sidecar_lock(path: Path) -> Iterator[None]:
    """Exclusive lock beside the sidecar so concurrent Rokus cannot clobber."""
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            if fh.read(1) == "":
                fh.write("0")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt

                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Temp + replace so readers never see a partial sidecar."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def apply_vote(
    media_root: Path,
    payload: dict[str, Any],
    *,
    when: str | None = None,
) -> dict[str, Any]:
    """Load–mutate–write ``viewer_feedback`` on the resolved sidecar."""
    if not isinstance(payload, dict):
        raise InvalidVote("JSON object required")
    kind = normalize_kind(_pick(payload, "kind", "vote") or "vote")
    path = resolve_vote_sidecar(
        media_root,
        stem=_pick(payload, "stem"),
        media_path=_pick(payload, "mediaPath", "mediapath"),
        generation=_pick(payload, "generation"),
        sheep_id=_pick(payload, "sheepId", "sheepid"),
    )
    with sidecar_lock(path):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StemNotFound("unreadable sidecar %s" % path) from exc
        if not isinstance(data, dict):
            raise StemNotFound("sidecar is not an object: %s" % path)
        data["viewer_feedback"] = increment_feedback(
            data.get("viewer_feedback"), kind, when=when
        )
        atomic_write_json(path, data)
        feedback = data["viewer_feedback"]
    return {
        "ok": True,
        "stem": sidecar_stem(path),
        "kind": kind,
        "sidecar": str(path),
        "viewer_feedback": feedback,
        "itemId": _pick(payload, "itemId", "itemid") or None,
        "deviceId": _pick(payload, "deviceId", "deviceid") or None,
    }


def show_vote(media_root: Path, stem: str) -> dict[str, Any]:
    """Return the sidecar ``viewer_feedback`` block (defaults if missing)."""
    path, data = load_sidecar_for_stem(media_root, stem)
    return {
        "ok": True,
        "stem": sidecar_stem(path),
        "sidecar": str(path),
        "viewer_feedback": normalize_feedback(data.get("viewer_feedback")),
    }


def _media_root(config: Path) -> Path:
    cfg = load_config(str(config))
    return resolve_path(cfg, "media_library")


def main(argv: list[str] | None = None) -> int:
    """CLI: apply or show sidecar vote tallies."""
    ap = argparse.ArgumentParser(description="Catalog sidecar viewer votes (like/love/vote)")
    ap.add_argument("--config", default="configs/jellyflam3.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_apply = sub.add_parser("apply", help="Increment sidecar viewer_feedback")
    p_apply.add_argument("--stem", required=True)
    p_apply.add_argument("--kind", default="vote", help="like | love | vote")
    p_apply.add_argument("--media-path", default="", dest="media_path")

    p_show = sub.add_parser("show", help="Print viewer_feedback for a stem")
    p_show.add_argument("--stem", required=True)

    args = ap.parse_args(argv)
    media = _media_root(Path(args.config))
    try:
        if args.cmd == "show":
            print(json.dumps(show_vote(media, args.stem), indent=2))
            return 0
        result = apply_vote(
            media,
            {"stem": args.stem, "kind": args.kind, "mediaPath": args.media_path},
        )
        print(json.dumps(result, indent=2))
        return 0
    except InvalidVote as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (StemNotFound, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
