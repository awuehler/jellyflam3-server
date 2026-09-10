"""Unit tests for pipeline.sheep_naming (hash-seed aliases)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.sheep_naming import (
    ADJECTIVES,
    SURNAMES,
    alias_of,
    backfill_catalog,
    clear_to_auto,
    collect_taken_aliases,
    ensure_auto_alias,
    generate_alias,
    naming_enabled,
    set_human_alias,
    source_of,
    validate_alias,
)

ROOT = Path(__file__).resolve().parents[1]


def test_word_lists_unique_and_sized():
    assert len(ADJECTIVES) == len(set(ADJECTIVES))
    assert len(SURNAMES) == len(set(SURNAMES))
    assert len(ADJECTIVES) >= 64
    assert len(SURNAMES) >= 64


def test_same_stem_same_alias():
    a = generate_alias("electricsheep.247.00505", [])
    b = generate_alias("electricsheep.247.00505", [])
    assert a == b
    assert "_" in a
    validate_alias(a)


def test_collision_walks_next_pair():
    adj = ("frosty", "quiet")
    sur = ("swirles", "turing")
    first = generate_alias("stem-a", [], adjectives=adj, surnames=sur)
    second = generate_alias("stem-a", {first}, adjectives=adj, surnames=sur)
    assert second != first
    taken = {first, second}
    third = generate_alias("stem-a", taken, adjectives=adj, surnames=sur)
    assert third not in taken
    all_pairs = {f"{a}_{s}" for a in adj for s in sur}
    with pytest.raises(RuntimeError, match="exhausted"):
        generate_alias("stem-a", all_pairs, adjectives=adj, surnames=sur)


def test_human_override_is_sticky():
    side = {"alias": "frosty_swirles", "alias_source": "human"}
    ensure_auto_alias(side, "electricsheep.247.001", {"other_name"})
    assert side["alias"] == "frosty_swirles"
    assert side["alias_source"] == "human"


def test_ensure_assigns_auto_when_missing():
    side: dict = {"id": "electricsheep.247.001"}
    ensure_auto_alias(side, "electricsheep.247.001", [])
    assert side["alias_source"] == "auto"
    assert "_" in side["alias"]


def test_set_human_rejects_duplicate():
    side = {"alias": "old_name", "alias_source": "auto"}
    set_human_alias(side, "frosty_swirles", [])
    assert source_of(side) == "human"
    with pytest.raises(ValueError, match="already used"):
        set_human_alias({"id": "other"}, "frosty_swirles", {"frosty_swirles"})


def test_clear_to_auto_regenerates():
    side = {"alias": "custom_name", "alias_source": "human"}
    clear_to_auto(side, "electricsheep.247.00505", [])
    assert source_of(side) == "auto"
    assert alias_of(side) != "custom_name"


def test_backfill_skips_human(tmp_path: Path):
    gen = tmp_path / "by-generation" / "247"
    gen.mkdir(parents=True)
    auto_path = gen / "electricsheep.247.001.jellyflam3.json"
    human_path = gen / "electricsheep.247.002.jellyflam3.json"
    auto_path.write_text(json.dumps({"id": "electricsheep.247.001"}), encoding="utf-8")
    human_path.write_text(
        json.dumps(
            {
                "id": "electricsheep.247.002",
                "alias": "kept_human",
                "alias_source": "human",
            }
        ),
        encoding="utf-8",
    )
    rows = backfill_catalog(tmp_path, dry_run=False)
    assert len(rows) == 1
    assert rows[0]["stem"] == "electricsheep.247.001"
    written = json.loads(auto_path.read_text(encoding="utf-8"))
    assert written["alias_source"] == "auto"
    human = json.loads(human_path.read_text(encoding="utf-8"))
    assert human["alias"] == "kept_human"
    taken = collect_taken_aliases(tmp_path)
    assert written["alias"] in taken
    assert "kept_human" in taken


def test_naming_enabled_defaults_on():
    assert naming_enabled({}) is True
    assert naming_enabled({"naming": {"enabled": False}}) is False


def test_worker_assigns_alias_after_reserved_merge():
    text = (ROOT / "pipeline" / "worker.py").read_text(encoding="utf-8")
    assert "ensure_auto_alias" in text
    assert "collect_taken_aliases" in text


def test_example_yaml_documents_naming():
    text = (ROOT / "configs" / "jellyflam3.yaml.example").read_text(encoding="utf-8")
    assert "naming:" in text
    assert "python3 -m pipeline.sheep_naming" in text
    assert "pipeline.sheep_naming" in (ROOT / "pipeline" / "__main__.py").read_text(
        encoding="utf-8"
    )
