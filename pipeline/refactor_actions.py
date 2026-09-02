"""Sheep refactor Pathways B/C/D — quarantine, apply, and batch."""

from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from pipeline.config import resolve_path
from pipeline.media_layout import REFACTOR_QUARANTINE_DIRNAME, ensure_refactor_quarantine_dir
from pipeline.poster import poster_path_for_mp4
from pipeline.refactor_history import (
    append_catalog_refactor_history,
    build_refactor_history_entry,
    write_refactor_pending,
)
from pipeline.refactor_preview import (
    cfg_with_palette_overrides,
    discard_preview,
    preview_dir_for,
    soft_refresh_jellyfin,
)
from pipeline.refactor_scan import (
    SCORE_CANDIDATE_MIN,
    SheepScore,
    _neon_clash,
    _palette_block,
    filter_report,
    find_catalog_mp4,
    find_genome_for_stem,
    genome_dud_reasons,
    genome_dud_score,
    scan_catalog,
    score_sheep,
    verdict_for,
)
from pipeline.sheep_names import normalize_stem, stem_of
from pipeline.sheep_tax import tax_xml
from pipeline.stills import sidecar_path_for_mp4

log = logging.getLogger("jellyflam3.refactor")

QUARANTINE_CONFIRM_TOKEN = "QUARANTINE"
APPLY_CONFIRM_TOKEN = "APPLY"
BATCH_CONFIRM_TOKEN = "BATCH"


def catalog_quarantine_root(cfg: dict[str, Any]) -> Path:
    """Holding area for unpublished catalog artifacts (not genetics)."""
    media = resolve_path(cfg, "media_library")
    return ensure_refactor_quarantine_dir(media)


def catalog_quarantine_dir_for(cfg: dict[str, Any], sheep_id: str) -> Path:
    stem = normalize_stem(stem_of(sheep_id))
    return catalog_quarantine_root(cfg) / stem


def _move_file(src: Path, dest: Path, *, dry_run: bool) -> str:
    """Move ``src`` → ``dest``; return dest path string. Overwrite dest if present."""
    if dry_run:
        return str(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    return str(dest)


def _genome_companions(genome: Path) -> list[Path]:
    try:
        from pipeline.share_security import companion_integrity_paths

        return [p for p in companion_integrity_paths(genome) if p.is_file()]
    except Exception:  # noqa: BLE001
        return []


@dataclass
class QuarantineResult:
    """Pathway C outcome (dry-run or applied)."""

    id: str
    dry_run: bool
    verdict: str | None = None
    score: float | None = None
    reasons: list[str] = field(default_factory=list)
    genome_src: str | None = None
    genome_dest: str | None = None
    companions_moved: list[str] = field(default_factory=list)
    catalog_moved: list[str] = field(default_factory=list)
    catalog_quarantine_dir: str | None = None
    unpublish: bool = False
    jellyfin: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def soft_unpublish_jellyfin(
    cfg: dict[str, Any],
    sheep_id: str,
    *,
    mp4_hint: Path | None = None,
    item_id: str | None = None,
) -> dict[str, Any]:
    """Best-effort delete Jellyfin library item for ``sheep_id`` (genetics preserved)."""
    try:
        from pipeline.jellyfin_client import JellyfinClient

        client = JellyfinClient.from_config(cfg)
        resolved_id = item_id
        if not resolved_id:
            item = None
            if mp4_hint is not None and mp4_hint.is_file():
                item = client.find_item_for_media(mp4_hint)
            if item is None:
                item = client.find_item_by_path_name(
                    f"{normalize_stem(stem_of(sheep_id))}.mp4"
                )
            if not item:
                return {"ok": True, "status": "not_found"}
            resolved_id = str(item.get("Id") or "")
        if not resolved_id:
            return {"ok": False, "status": "missing_id"}
        client.delete_item(resolved_id)
        return {"ok": True, "status": "deleted", "item_id": resolved_id}
    except Exception as exc:  # noqa: BLE001
        log.warning("Jellyfin unpublish skipped/failed: %s", exc)
        return {"ok": False, "status": "skipped", "error": str(exc)}


def run_quarantine(
    cfg: dict[str, Any],
    sheep_id: str,
    *,
    dry_run: bool = True,
    reason: str | None = None,
    unpublish: bool = True,
    force: bool = False,
    refresh_jellyfin: bool = True,
    refresh_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    unpublish_fn: Callable[..., dict[str, Any]] | None = None,
) -> QuarantineResult:
    """Move genetics to ``genomes_quarantine``; optionally park catalog (no deletes)."""
    stem = normalize_stem(stem_of(sheep_id))
    notes: list[str] = []
    if reason:
        notes.append(f"operator_reason:{reason}")

    mp4 = find_catalog_mp4(cfg, stem)
    genome = find_genome_for_stem(cfg, stem)
    scored: SheepScore | None = None
    if mp4 is not None:
        scored = score_sheep(cfg, mp4, genome_path=genome)
    elif genome is not None:
        notes.append("no_catalog_mp4")
        # Genome-only: tax / neon signals without probing a missing MP4.
        xml = genome.read_text(encoding="utf-8", errors="replace")
        reasons: list[str] = ["missing_catalog_mp4"]
        score = 40.0
        tax_cfg = dict(cfg)
        st = dict(tax_cfg.get("sheep_tax") or {})
        st["repair"] = False
        tax_cfg["sheep_tax"] = st
        tax = tax_xml(xml, tax_cfg)
        if not tax.get("ok"):
            reasons.append("sheep_tax_fail")
            score += 50.0
        palette = _palette_block(xml, cfg)
        if _neon_clash(palette):
            reasons.append("palette_neon_clash")
            score += 30.0
        for dud in genome_dud_reasons(xml):
            reasons.append(dud)
        score += genome_dud_score(cfg, reasons)
        verdict = verdict_for(score, reasons)
        scored = SheepScore(
            id=stem,
            mp4="",
            verdict=verdict,
            score=score,
            reasons=reasons,
            palette=palette,
            genome=str(genome),
            tax_status=str(tax.get("status") or ("ok" if tax.get("ok") else "fail")),
        )

    if scored is None:
        raise FileNotFoundError(f"no genome or catalog mp4 for {stem}")

    if scored.verdict != "quarantine" and not force:
        raise ValueError(
            f"{stem} verdict={scored.verdict!r} (score={scored.score}); "
            "pass --force to quarantine non-quarantine verdicts"
        )
    if scored.verdict != "quarantine" and force:
        notes.append("forced")

    qdir = resolve_path(cfg, "genomes_quarantine")
    genome_src = genome
    genome_dest: Path | None = None
    companions_moved: list[str] = []

    # Prefer moving from done/inbox; skip if already under quarantine.
    if genome_src is not None:
        try:
            already = genome_src.resolve().is_relative_to(qdir.resolve())
        except (OSError, ValueError):
            already = "quarantine" in genome_src.parts
        if already:
            notes.append("genome_already_quarantined")
            genome_dest = genome_src
        else:
            genome_dest = qdir / genome_src.name
            if not dry_run:
                qdir.mkdir(parents=True, exist_ok=True)
            for side in _genome_companions(genome_src):
                companions_moved.append(
                    _move_file(side, qdir / side.name, dry_run=dry_run)
                )
            _move_file(genome_src, genome_dest, dry_run=dry_run)
            notes.append("genome_moved" if not dry_run else "genome_would_move")
    else:
        notes.append("missing_genome")

    catalog_moved: list[str] = []
    cat_q_dir: Path | None = None
    jelly: dict[str, Any] = {"ok": False, "status": "skipped"}

    if unpublish:
        cat_q_dir = catalog_quarantine_dir_for(cfg, stem)
        # Stash Jellyfin Id before parking files (path lookup fails after move).
        jelly_item_id: str | None = None
        if not dry_run and mp4 is not None and mp4.is_file():
            try:
                from pipeline.jellyfin_client import JellyfinClient

                item = JellyfinClient.from_config(cfg).find_item_for_media(mp4)
                if item:
                    jelly_item_id = str(item.get("Id") or "") or None
            except Exception as exc:  # noqa: BLE001
                log.warning("Jellyfin item lookup soft-fail: %s", exc)

        if mp4 is not None and mp4.is_file():
            try:
                under_hold = mp4.resolve().is_relative_to(
                    catalog_quarantine_root(cfg).resolve()
                )
            except (OSError, ValueError, AttributeError):
                under_hold = REFACTOR_QUARANTINE_DIRNAME in mp4.parts
            if under_hold:
                notes.append("catalog_already_unpublished")
            else:
                if not dry_run:
                    cat_q_dir.mkdir(parents=True, exist_ok=True)
                for src in (
                    mp4,
                    sidecar_path_for_mp4(mp4),
                    poster_path_for_mp4(mp4),
                ):
                    if not src.is_file():
                        continue
                    catalog_moved.append(
                        _move_file(src, cat_q_dir / src.name, dry_run=dry_run)
                    )
                notes.append(
                    "catalog_unpublished" if not dry_run else "catalog_would_unpublish"
                )
        else:
            notes.append("no_catalog_to_unpublish")

        if not dry_run:
            unpub = unpublish_fn or soft_unpublish_jellyfin
            jelly = unpub(cfg, stem, mp4_hint=None, item_id=jelly_item_id)
            if refresh_jellyfin:
                refresher = refresh_fn or soft_refresh_jellyfin
                jelly["refresh"] = refresher(cfg)
        else:
            jelly = {"ok": True, "status": "dry_run_would_unpublish"}
    else:
        notes.append("unpublish_skipped")

    return QuarantineResult(
        id=stem,
        dry_run=dry_run,
        verdict=scored.verdict,
        score=scored.score,
        reasons=list(scored.reasons),
        genome_src=str(genome_src) if genome_src else None,
        genome_dest=str(genome_dest) if genome_dest else None,
        companions_moved=companions_moved,
        catalog_moved=catalog_moved,
        catalog_quarantine_dir=str(cat_q_dir) if cat_q_dir else None,
        unpublish=unpublish,
        jellyfin=jelly,
        notes=notes,
    )


@dataclass
class ApplyResult:
    """Pathway B outcome: genome staged for re-furnace (encode is worker-owned)."""

    id: str
    dry_run: bool
    genome_src: str | None = None
    inbox_dest: str | None = None
    staged: bool = False
    palette_before: dict[str, Any] = field(default_factory=dict)
    palette_after: dict[str, Any] = field(default_factory=dict)
    preview_discarded: bool = False
    jellyfin: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    notes: list[str] = field(default_factory=list)
    refactor_history: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_apply(
    cfg: dict[str, Any],
    sheep_id: str,
    *,
    dry_run: bool = True,
    palette_mode: str | None = None,
    palette_seed: str | None = None,
    reason: str | None = None,
    discard_preview_dir: bool = True,
    refresh_jellyfin: bool = True,
    stage_fn: Callable[..., Path | None] | None = None,
    refresh_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> ApplyResult:
    """Pathway B: TV-optimize + palette override, then stage into ``genomes_inbox``.

    Does **not** wait for encode/poster — the worker owns furnace pickup. Live catalog
    stays until the worker replaces the same Id after render.
    """
    from pipeline.seed_inbox import inbox_filename, stage_file
    from pipeline.shears import shears_modify
    from pipeline.tv_optimize import tv_optimize_xml

    stem = normalize_stem(stem_of(sheep_id))
    notes: list[str] = []
    if reason:
        notes.append(f"operator_reason:{reason}")

    genome = find_genome_for_stem(cfg, stem)
    if genome is None:
        raise FileNotFoundError(f"no genome found for {stem}")

    xml = genome.read_text(encoding="utf-8", errors="replace")
    palette_before = _palette_block(xml, cfg)

    work_cfg = cfg_with_palette_overrides(
        cfg, palette_mode=palette_mode, palette_seed=palette_seed
    )
    out_xml, harmony = tv_optimize_xml(xml, work_cfg)
    if harmony is None:
        palette_after = {
            "mode": "off",
            "seed_hex": None,
            "complement_hex": None,
            "source": "disabled",
        }
        notes.append("palette_disabled")
    else:
        palette_after = {
            "mode": harmony.mode,
            "seed_hex": harmony.seed_hex,
            "complement_hex": harmony.complement_hex,
            "source": str((work_cfg.get("palette") or {}).get("seed") or "genome_accent"),
        }

    inbox = resolve_path(cfg, "genomes_inbox")
    # Name as if staging the catalog stem so worker keeps the stable Id.
    name_src = Path(f"{stem}.flam3")
    inbox_dest = inbox / inbox_filename(name_src)
    notes.append("furnace_async_via_worker")

    staged = False
    if dry_run:
        notes.append("would_stage_inbox")
    else:
        with tempfile.TemporaryDirectory(prefix="refactor-apply-") as tmp:
            staged_path = Path(tmp) / f"{stem}.flam3"
            staged_path.write_text(out_xml, encoding="utf-8")
            if stage_fn is not None:
                dest = stage_fn(cfg, staged_path, dry_run=False, force=True)
            else:
                # Prefer shears_modify (force re-queue even when catalog MP4 exists).
                dest = shears_modify(cfg, staged_path, dry_run=False, force=True)
                if dest is None:
                    dest = stage_file(
                        staged_path, inbox, dry_run=False, force=True, move=False
                    )
            if dest is None:
                raise RuntimeError(f"failed to stage apply genome for {stem}")
            inbox_dest = Path(dest)
            staged = True
            notes.append("staged_inbox")

    score_val: float | None = None
    score_reasons: list[str] = []
    mp4 = find_catalog_mp4(cfg, stem)
    if mp4 is not None and mp4.is_file():
        try:
            scored = score_sheep(cfg, mp4, genome_path=genome, xml_text=xml)
            score_val = float(scored.score)
            score_reasons = list(scored.reasons)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"score_skipped:{exc}")

    history_entry = build_refactor_history_entry(
        reason=reason,
        score=score_val,
        score_reasons=score_reasons,
        palette_before=palette_before,
        palette_after=palette_after,
        status="staged",
    )
    if dry_run:
        notes.append("would_write_refactor_pending")
        notes.append("would_append_catalog_refactor_history")
    else:
        if staged:
            write_refactor_pending(inbox_dest, history_entry)
            notes.append("refactor_pending_written")
        if append_catalog_refactor_history(cfg, stem, history_entry):
            notes.append("catalog_sidecar_history_appended")
        else:
            notes.append("catalog_sidecar_absent")

    preview_discarded = False
    jelly: dict[str, Any] = {"ok": False, "status": "skipped"}
    if discard_preview_dir:
        prev = preview_dir_for(cfg, stem)
        if prev.is_dir():
            if dry_run:
                notes.append("would_discard_preview")
            else:
                discard_preview(
                    cfg,
                    stem,
                    refresh_jellyfin=False,
                    refresh_fn=refresh_fn,
                )
                preview_discarded = True
                notes.append("preview_discarded")
        else:
            notes.append("preview_absent")

    if refresh_jellyfin:
        if dry_run:
            jelly = {"ok": True, "status": "dry_run_would_refresh"}
        else:
            refresher = refresh_fn or soft_refresh_jellyfin
            jelly = refresher(cfg)

    return ApplyResult(
        id=stem,
        dry_run=dry_run,
        genome_src=str(genome),
        inbox_dest=str(inbox_dest),
        staged=staged,
        palette_before=palette_before,
        palette_after=palette_after,
        preview_discarded=preview_discarded,
        jellyfin=jelly,
        reason=reason,
        notes=notes,
        refactor_history=history_entry,
    )


@dataclass
class BatchItemResult:
    """One Pathway D decision (apply / quarantine / skip)."""

    id: str
    action: str  # apply | quarantine | skip
    verdict: str
    score: float
    dry_run: bool
    detail: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BatchResult:
    """Pathway D summary."""

    dry_run: bool
    limit: int | None
    failing_only: bool
    items: list[BatchItemResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_batch(
    cfg: dict[str, Any],
    *,
    dry_run: bool = True,
    limit: int | None = None,
    failing_only: bool = True,
    palette_mode: str | None = None,
    palette_seed: str | None = None,
    reason: str | None = None,
    unpublish: bool = True,
    refresh_jellyfin: bool = False,
    apply_fn: Callable[..., ApplyResult] | None = None,
    quarantine_fn: Callable[..., QuarantineResult] | None = None,
) -> BatchResult:
    """Pathway D: scan → route quarantine verdicts to C and candidates to B.

    Default dry-run. Live runs require CLI ``--confirm BATCH``. Per-item Jellyfin
    refresh is off by default (expensive); callers may enable.
    """
    notes: list[str] = []
    if reason:
        notes.append(f"operator_reason:{reason}")
    notes.append("furnace_async_via_worker")

    rows = scan_catalog(cfg, limit=limit)
    if failing_only:
        rows = filter_report(rows, failing_only=True)
    # Respect limit after filter as well (scan limit is pre-filter).
    if limit is not None and limit >= 0:
        rows = rows[:limit]

    applyer = apply_fn or run_apply
    quarantiner = quarantine_fn or run_quarantine
    items: list[BatchItemResult] = []

    for row in rows:
        stem = row.id
        if row.verdict == "quarantine":
            action = "quarantine"
            try:
                detail = quarantiner(
                    cfg,
                    stem,
                    dry_run=dry_run,
                    reason=reason,
                    unpublish=unpublish,
                    force=False,
                    refresh_jellyfin=refresh_jellyfin,
                )
                items.append(
                    BatchItemResult(
                        id=stem,
                        action=action,
                        verdict=row.verdict,
                        score=row.score,
                        dry_run=dry_run,
                        detail=detail.to_dict(),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                items.append(
                    BatchItemResult(
                        id=stem,
                        action=action,
                        verdict=row.verdict,
                        score=row.score,
                        dry_run=dry_run,
                        error=str(exc),
                    )
                )
        elif row.verdict == "candidate":
            action = "apply"
            try:
                detail = applyer(
                    cfg,
                    stem,
                    dry_run=dry_run,
                    palette_mode=palette_mode,
                    palette_seed=palette_seed,
                    reason=reason,
                    discard_preview_dir=True,
                    refresh_jellyfin=refresh_jellyfin,
                )
                items.append(
                    BatchItemResult(
                        id=stem,
                        action=action,
                        verdict=row.verdict,
                        score=row.score,
                        dry_run=dry_run,
                        detail=detail.to_dict(),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                items.append(
                    BatchItemResult(
                        id=stem,
                        action=action,
                        verdict=row.verdict,
                        score=row.score,
                        dry_run=dry_run,
                        error=str(exc),
                    )
                )
        else:
            items.append(
                BatchItemResult(
                    id=stem,
                    action="skip",
                    verdict=row.verdict,
                    score=row.score,
                    dry_run=dry_run,
                    detail={"note": "ok_left_alone"},
                )
            )

    n_a = sum(1 for i in items if i.action == "apply")
    n_q = sum(1 for i in items if i.action == "quarantine")
    n_s = sum(1 for i in items if i.action == "skip")
    n_e = sum(1 for i in items if i.error)
    notes.append(f"summary:apply={n_a}:quarantine={n_q}:skip={n_s}:errors={n_e}")

    return BatchResult(
        dry_run=dry_run,
        limit=limit,
        failing_only=failing_only,
        items=items,
        notes=notes,
    )
