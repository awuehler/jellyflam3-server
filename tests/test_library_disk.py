"""Unit tests for pipeline.library_disk (WARN/BAD only; no rotate)."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.library_disk import (
    EXIT_BAD,
    EXIT_OK,
    EXIT_WARN,
    _Usage,
    assess_config,
    classify_usage,
    exit_code_for,
    format_check,
    main,
    missing_check,
    thresholds_from_cfg,
)

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "configs" / "jellyflam3.yaml.example"
GiB = 1024**3


def _usage(*, total_gb: float, used_gb: float) -> _Usage:
    total = int(total_gb * GiB)
    used = int(used_gb * GiB)
    return _Usage(total=total, used=used, free=total - used)


def test_classify_ok_warn_bad_by_percent():
    ok = classify_usage(_usage(total_gb=100, used_gb=10), role="sheep", path="/m")
    assert ok.level == "ok"
    assert ok.used_pct == 10.0
    warn = classify_usage(_usage(total_gb=100, used_gb=81), role="sheep", path="/m")
    assert warn.level == "warn"
    assert any("80" in r for r in warn.reasons)
    bad = classify_usage(_usage(total_gb=100, used_gb=96), role="sheep", path="/m")
    assert bad.level == "bad"
    assert any("95" in r for r in bad.reasons)


def test_classify_free_gb_floor():
    plenty = classify_usage(_usage(total_gb=100, used_gb=10), role="sheep", path="/m")
    assert plenty.level == "ok"
    warn = classify_usage(_usage(total_gb=20, used_gb=15), role="sheep", path="/m")
    assert warn.level == "warn"
    assert any("16" in r for r in warn.reasons)
    bad = classify_usage(_usage(total_gb=10, used_gb=8), role="sheep", path="/m")
    assert bad.level == "bad"
    assert any("4" in r for r in bad.reasons)


def test_bad_percent_wins_over_warn_free():
    c = classify_usage(_usage(total_gb=100, used_gb=96), role="sheep", path="/m")
    assert c.level == "bad"


def test_missing_path_is_bad():
    m = missing_check("sheep", "/no/such")
    assert m.level == "bad"
    assert m.exists is False
    assert format_check(m) == "BAD sheep /no/such missing"


def test_exit_codes():
    assert exit_code_for("ok") == EXIT_OK
    assert exit_code_for("warn") == EXIT_WARN
    assert exit_code_for("bad") == EXIT_BAD


def test_assess_injected_usage(tmp_path: Path):
    media = tmp_path / "sheep"
    scratch = tmp_path / "frames"
    media.mkdir()
    scratch.mkdir()
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {"media_library": str(media), "frames_scratch": str(scratch)},
        "library_disk": {"check_scratch": True},
    }
    u = _usage(total_gb=100, used_gb=50)
    report = assess_config(cfg, usage_for={str(media): u, str(scratch): u})
    assert "sheep" in {c.role for c in report.checks}
    assert report.worst == "ok"
    cfg["library_disk"]["check_scratch"] = False
    report = assess_config(cfg, usage_for={str(media): u})
    assert [c.role for c in report.checks] == ["sheep"]


def test_assess_missing_media_is_bad(tmp_path: Path):
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "media_library": str(tmp_path / "nope"),
            "frames_scratch": str(tmp_path / "nope2"),
        },
        "library_disk": {"check_scratch": False},
    }
    report = assess_config(cfg)
    assert report.worst == "bad"
    assert report.checks[0].exists is False


def test_thresholds_from_cfg_defaults_and_override():
    d = thresholds_from_cfg({})
    assert d["warn_used_pct"] == 80.0
    assert d["bad_free_gb"] == 4.0
    o = thresholds_from_cfg({"library_disk": {"warn_used_pct": 70, "bad_free_gb": 2}})
    assert o["warn_used_pct"] == 70.0
    assert o["bad_free_gb"] == 2.0
    assert o["bad_used_pct"] == 95.0


def test_cli_check_json_loose_thresholds(tmp_path: Path, capsys):
    media = tmp_path / "media"
    media.mkdir()
    cfg = tmp_path / "jellyflam3.yaml"
    cfg.write_text(
        "paths:\n"
        f"  media_library: {media.as_posix()}\n"
        "library_disk:\n"
        "  check_scratch: false\n"
        "  warn_used_pct: 100\n"
        "  bad_used_pct: 100\n"
        "  warn_free_gb: 0\n"
        "  bad_free_gb: 0\n",
        encoding="utf-8",
    )
    rc = main(["check", "--config", str(cfg), "--json"])
    assert rc == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["worst"] == "ok"
    assert data["checks"][0]["role"] == "sheep"


def test_example_yaml_documents_library_disk():
    text = EXAMPLE.read_text(encoding="utf-8")
    assert "library_disk:" in text
    assert "python3 -m pipeline.library_disk" in text


def test_worker_does_not_import_library_disk():
    text = (ROOT / "pipeline" / "worker.py").read_text(encoding="utf-8")
    assert "library_disk" not in text


def test_healthcheck_wires_library_disk_probe():
    text = (ROOT / "scripts" / "healthcheck.sh").read_text(encoding="utf-8")
    assert "library_disk" in text
    assert "pipeline.library_disk" in text
