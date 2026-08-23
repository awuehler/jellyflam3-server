from pathlib import Path

from pipeline.license_filter import (
    filter_items_for_commercial,
    infer_tags_from_genome,
    is_commercial_allowed,
)


def test_infer_generation_and_nc(tmp_path):
    p = tmp_path / "electricsheep.247.16021.flam3"
    p.write_text('<flame nick="brood"></flame>', encoding="utf-8")
    tags = infer_tags_from_genome(p)
    assert "generation-247" in tags
    assert "cc-by-nc" in tags or "brood" in tags


def test_commercial_filter():
    cfg = {"license": {"commercial_mode": True, "exclude_tags": ["cc-by-nc"]}}
    assert not is_commercial_allowed(["cc-by-nc", "generation-247"], cfg)
    assert is_commercial_allowed(["cc-by", "human"], cfg)
    items = [
        {"Name": "a", "Tags": ["cc-by-nc"]},
        {"Name": "b", "Tags": ["cc-by"]},
    ]
    filtered = filter_items_for_commercial(items, cfg)
    assert len(filtered) == 1 and filtered[0]["Name"] == "b"


def test_commercial_mode_off():
    cfg = {"license": {"commercial_mode": False, "exclude_tags": ["cc-by-nc"]}}
    assert is_commercial_allowed(["cc-by-nc"], cfg)


def test_infer_tags_defaults_nc_for_unknown_robot(tmp_path: Path):
    p = tmp_path / "mystery.flam3"
    p.write_text('<flame nick="brood"></flame>', encoding="utf-8")
    tags = infer_tags_from_genome(p)
    assert "cc-by-nc" in tags
    assert "human" not in tags


def test_infer_tags_human_gets_cc_by(tmp_path: Path):
    p = tmp_path / "electricsheep.247.00001.flam3"
    p.write_text('<flame nick="artist"></flame>', encoding="utf-8")
    tags = infer_tags_from_genome(p)
    assert "human" in tags
    assert "cc-by" in tags
    assert "cc-by-nc" not in tags


def test_filter_items_empty_tags_allowed_in_commercial_mode():
    cfg = {"license": {"commercial_mode": True, "exclude_tags": ["cc-by-nc"]}}
    items = [{"Name": "untagged", "Tags": []}]
    assert filter_items_for_commercial(items, cfg) == items
