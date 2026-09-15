"""Active worker quality admission before expensive render/publication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from pipeline.quality_gate import (
    QualityGateRejected,
    assess_genome_quality,
    assess_image_quality,
    enforce_quality,
)
from pipeline.worker import record_quality_check


FROZEN_LINEAR = """<flame name="bad" size="1920 1080">
  <xform weight="1" symmetry="1" linear="1" coefs="1 0 0 1 0 0" />
</flame>"""

ANIMATED = """<flame name="good" size="1920 1080">
  <xform weight="1" animate="1" spherical="1" coefs="1 0 0 1 0 0" />
</flame>"""

TWO_FLAME = """<flames>
  <flame name="a" time="0" size="1920 1080">
    <xform weight="1" symmetry="1" spherical="1" coefs="1 0 0 1 0 0" />
  </flame>
  <flame name="b" time="1" size="1920 1080">
    <xform weight="1" symmetry="1" spherical="1" coefs="0.5 0 0 0.5 0.1 0" />
  </flame>
</flames>"""


def _cfg() -> dict:
    return {
        "quality_gate": {"enabled": True},
        "refactor": {"desat_mean_max": 0.12},
    }


def test_pre_render_rejects_frozen_linear_and_washed_palette():
    result = assess_genome_quality(
        _cfg(),
        FROZEN_LINEAR,
        palette={"seed_hex": "#777777", "complement_hex": "#888888"},
    )
    assert result["status"] == "rejected"
    assert set(result["reasons"]) == {
        "genome_linear_only",
        "genome_orbit_frozen",
        "palette_washed_out",
    }
    with pytest.raises(QualityGateRejected, match="pre_render_genome"):
        enforce_quality(result)


def test_pre_render_accepts_animated_vivid_genome():
    result = assess_genome_quality(
        _cfg(),
        ANIMATED,
        palette={"seed_hex": "#ff0000", "complement_hex": "#00ffff"},
    )
    assert result["status"] == "passed"
    assert result["reasons"] == []
    enforce_quality(result)


def test_tuple_control_points_are_not_rejected_as_static():
    result = assess_genome_quality(
        _cfg(),
        TWO_FLAME,
        palette={"seed_hex": "#ff0000", "complement_hex": "#00ffff"},
        is_tuple=True,
    )
    assert "genome_orbit_frozen" not in result["reasons"]
    assert result["status"] == "passed"


def test_preview_and_output_reject_desaturated_image(tmp_path: Path):
    grey = tmp_path / "grey.png"
    vivid = tmp_path / "vivid.png"
    Image.new("RGB", (32, 32), (120, 120, 120)).save(grey)
    Image.new("RGB", (32, 32), (255, 0, 0)).save(vivid)

    rejected = assess_image_quality(_cfg(), grey, stage="pre_render_preview")
    assert rejected["status"] == "rejected"
    assert rejected["reasons"] == ["catalog_desaturated"]
    assert rejected["metrics"]["mean_saturation"] == 0.0

    passed = assess_image_quality(_cfg(), vivid, stage="pre_publish_output")
    assert passed["status"] == "passed"
    assert passed["metrics"]["mean_saturation"] == 1.0


def test_quality_decision_is_persisted_before_rejection(tmp_path: Path):
    state: dict = {"id": "job"}
    result = assess_genome_quality(_cfg(), FROZEN_LINEAR)
    record_quality_check(state, tmp_path, result)

    saved = json.loads((tmp_path / "job.json").read_text(encoding="utf-8"))
    assert saved["quality_gate"]["status"] == "rejected"
    assert saved["quality_gate"]["checks"][0]["stage"] == "pre_render_genome"


def test_disabled_gate_preserves_explicit_operator_escape_hatch(tmp_path: Path):
    cfg = {"quality_gate": {"enabled": False}}
    genome = assess_genome_quality(cfg, FROZEN_LINEAR)
    image = assess_image_quality(cfg, tmp_path / "missing.png", stage="pre_publish_output")
    assert genome["status"] == "disabled"
    assert image["status"] == "disabled"
    enforce_quality(genome)
    enforce_quality(image)


def test_unreadable_quality_image_fails_closed(tmp_path: Path):
    result = assess_image_quality(
        _cfg(),
        tmp_path / "missing.png",
        stage="pre_render_preview",
    )
    assert result["status"] == "rejected"
    assert result["reasons"] == ["quality_image_unreadable"]
