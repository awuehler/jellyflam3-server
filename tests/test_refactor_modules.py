"""Direct imports for split refactor pathway modules (review T5).

Facade re-exports in pipeline.refactor are the stable API; these tests lock
module boundaries so import-cycle or rename regressions fail fast.
"""

from __future__ import annotations

from pathlib import Path

from pipeline.refactor_actions import (
    APPLY_CONFIRM_TOKEN,
    BATCH_CONFIRM_TOKEN,
    QUARANTINE_CONFIRM_TOKEN,
    ApplyResult,
    BatchResult,
    QuarantineResult,
    run_apply,
    run_batch,
    run_quarantine,
)
from pipeline.refactor_history import (
    build_refactor_history_entry,
    merge_pending_refactor_into_sidecar,
    merge_refactor_history,
    refactor_pending_path,
    write_refactor_pending,
)
from pipeline.refactor_preview import PreviewResult, discard_preview, run_preview
from pipeline.refactor_scan import (
    HARD_QUARANTINE_REASONS,
    SCORE_CANDIDATE_MIN,
    SCORE_QUARANTINE_MIN,
    SheepScore,
    filter_report,
    find_catalog_mp4,
    find_genome_for_stem,
    format_table,
    genome_dud_reasons,
    scan_catalog,
    score_sheep,
    verdict_for,
)


def test_scan_module_public_surface():
    assert SCORE_CANDIDATE_MIN == 1.0
    assert SCORE_QUARANTINE_MIN == 80.0
    assert "genome_linear_only" in HARD_QUARANTINE_REASONS
    assert "genome_singularity_cloned" in HARD_QUARANTINE_REASONS
    assert "genome_orbit_frozen" not in HARD_QUARANTINE_REASONS
    assert callable(score_sheep)
    assert callable(scan_catalog)
    assert callable(genome_dud_reasons)
    assert verdict_for(0.0, ["genome_linear_only"]) == "quarantine"
    assert verdict_for(25.0, ["genome_orbit_frozen"]) == "candidate"
    assert callable(filter_report)
    assert callable(format_table)
    assert callable(find_genome_for_stem)
    assert callable(find_catalog_mp4)
    assert SheepScore.__name__ == "SheepScore"


def test_preview_module_public_surface():
    assert callable(run_preview)
    assert callable(discard_preview)
    assert PreviewResult.__name__ == "PreviewResult"


def test_actions_module_public_surface():
    assert QUARANTINE_CONFIRM_TOKEN == "QUARANTINE"
    assert APPLY_CONFIRM_TOKEN == "APPLY"
    assert BATCH_CONFIRM_TOKEN == "BATCH"
    assert callable(run_quarantine)
    assert callable(run_apply)
    assert callable(run_batch)
    assert QuarantineResult.__name__ == "QuarantineResult"
    assert ApplyResult.__name__ == "ApplyResult"
    assert BatchResult.__name__ == "BatchResult"


def test_history_module_public_surface():
    assert callable(build_refactor_history_entry)
    assert callable(write_refactor_pending)
    assert callable(merge_refactor_history)
    assert callable(merge_pending_refactor_into_sidecar)
    assert refactor_pending_path(Path("x.flam3")).name.endswith(".refactor.json")


def test_merge_refactor_history_same_ts_last_wins():
    first = build_refactor_history_entry(reason="old", status="staged", ts="2026-08-21T00:00:00Z")
    second = build_refactor_history_entry(reason="new", status="ingested", ts="2026-08-21T00:00:00Z")
    merged = merge_refactor_history([first], [second])
    assert len(merged) == 1
    assert merged[0]["reason"] == ["new"]
    assert merged[0]["status"] == "ingested"
