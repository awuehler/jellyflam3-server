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
    main,
    naming_enabled,
    push_existing_overviews,
    resolve_sheep_token,
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


def test_cli_mentions_push_jellyfin():
    text = (ROOT / "pipeline" / "sheep_naming.py").read_text(encoding="utf-8")
    assert "--push-jellyfin" in text
    assert "push_overview_from_sidecar" in text
    assert "Alias:" in (ROOT / "pipeline" / "jellyfin_client.py").read_text(encoding="utf-8")


def test_example_yaml_documents_naming():
    text = (ROOT / "configs" / "jellyflam3.yaml.example").read_text(encoding="utf-8")
    assert "naming:" in text
    assert "python3 -m pipeline.sheep_naming" in text
    assert "pipeline.sheep_naming" in (ROOT / "pipeline" / "__main__.py").read_text(
        encoding="utf-8"
    )


def _write_named(media: Path, stem: str, alias: str | None, gen: str = "247") -> None:
    folder = media / "by-generation" / gen
    folder.mkdir(parents=True, exist_ok=True)
    payload: dict = {"id": stem}
    if alias:
        payload["alias"] = alias
        payload["alias_source"] = "auto"
    (folder / f"{stem}.jellyflam3.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_resolve_sheep_token_five_cases(tmp_path: Path):
    stem = "electricsheep.247.00505"
    pedigree = "electricsheep.pedigree.cross.b02b4b20"
    _write_named(tmp_path, stem, "frosty_swirles")
    _write_named(tmp_path, pedigree, "quiet_turing", gen="pedigree")

    suffixed = (
        f"{stem}.flam3",
        f"{stem}.flame",
        f"{stem}.mp4",
        f"{stem}-poster.jpg",
        f"{stem}.jellyflam3.json",
        str(tmp_path / "by-generation" / "247" / f"{stem}.mp4"),
    )
    for token in suffixed:
        assert resolve_sheep_token(tmp_path, token) == token

    assert resolve_sheep_token(tmp_path, stem) == stem
    assert resolve_sheep_token(tmp_path, pedigree) == pedigree
    assert resolve_sheep_token(tmp_path, "frosty_swirles") == stem
    assert resolve_sheep_token(tmp_path, "Frosty-Swirles") == stem

    _write_named(tmp_path, "electricsheep.247.00002", "frosty_swirles", gen="dup")
    with pytest.raises(ValueError, match="multiple stems"):
        resolve_sheep_token(tmp_path, "frosty_swirles")

    bare = tmp_path / "only-missing"
    bare.mkdir()
    with pytest.raises(ValueError, match="alias not found: missing_name"):
        resolve_sheep_token(bare, "missing_name")
    assert resolve_sheep_token(bare, "electricsheep.247.99999") == "electricsheep.247.99999"
    assert resolve_sheep_token(bare, "nope") == "nope"


def test_push_existing_overviews_skips_blank_and_continues(tmp_path: Path, monkeypatch):
    labeled = "electricsheep.247.00505"
    other = "electricsheep.247.00061"
    blank = "electricsheep.247.00002"
    _write_named(tmp_path, labeled, "frosty_swirles")
    _write_named(tmp_path, other, "quiet_turing")
    _write_named(tmp_path, blank, None)
    calls: list[str] = []

    def fake_push(_cfg, mp4: Path, _sidecar: dict):
        calls.append(mp4.name)
        if mp4.stem == labeled:
            return {"ok": False, "status": "item_not_found", "error": "no item"}
        raise RuntimeError("jellyfin down")

    monkeypatch.setattr("pipeline.sheep_naming._push_jellyfin", fake_push)
    dry = push_existing_overviews(tmp_path, {}, dry_run=True)
    assert calls == []
    dry_by = {row["stem"]: row for row in dry}
    assert dry_by[labeled]["action"] == "would_push"
    assert dry_by[labeled]["alias"] == "frosty_swirles"
    assert dry_by[other]["alias"] == "quiet_turing"
    assert blank not in dry_by

    live = push_existing_overviews(tmp_path, {}, dry_run=False)
    assert calls == [f"{other}.mp4", f"{labeled}.mp4"]
    live_by = {row["stem"]: row for row in live}
    assert live_by[labeled]["jellyfin"]["status"] == "item_not_found"
    assert live_by[other]["jellyfin"]["status"] == "error"
    limited = push_existing_overviews(tmp_path, {}, dry_run=True, limit=1)
    assert len(limited) == 1


def _naming_config(tmp_path: Path, media: Path) -> Path:
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    cfg = cfg_dir / "jellyflam3.yaml"
    cfg.write_text("paths:\n  media_library: %s\n" % media.as_posix(), encoding="utf-8")
    return cfg


def test_set_alias_cli_replaces_via_alias(tmp_path: Path, monkeypatch, capsys):
    media = tmp_path / "media"
    stem = "electricsheep.247.00505"
    _write_named(media, stem, "frosty_swirles")
    cfg = _naming_config(tmp_path, media)
    monkeypatch.setattr(
        "pipeline.sheep_naming._push_jellyfin",
        lambda *_a, **_k: {"ok": True, "status": "updated"},
    )
    rc = main(
        [
            "--config",
            str(cfg),
            "set-alias",
            "--stem",
            "frosty_swirles",
            "--alias",
            "quiet_turing",
        ]
    )
    assert rc == 0
    written = json.loads(
        (media / "by-generation" / "247" / f"{stem}.jellyflam3.json").read_text(
            encoding="utf-8"
        )
    )
    assert written["id"] == stem
    assert written["alias"] == "quiet_turing"
    assert written["alias_source"] == "human"
    assert "quiet_turing" in capsys.readouterr().out


def test_backfill_push_dry_run_lists_existing_alias(tmp_path: Path, monkeypatch, capsys):
    media = tmp_path / "media"
    _write_named(media, "electricsheep.247.00505", "frosty_swirles")
    _write_named(media, "electricsheep.247.00002", None)
    cfg = _naming_config(tmp_path, media)
    calls: list[str] = []
    monkeypatch.setattr(
        "pipeline.sheep_naming._push_jellyfin",
        lambda *_a, **_k: calls.append("pushed") or {"ok": True},
    )
    rc = main(["--config", str(cfg), "backfill", "--dry-run", "--push-jellyfin"])
    assert rc == 0
    assert calls == []
    payload = json.loads(capsys.readouterr().out)
    assert payload["overview"] == [
        {
            "stem": "electricsheep.247.00505",
            "alias": "frosty_swirles",
            "action": "would_push",
        }
    ]


def test_refactor_report_resolves_alias_before_scan(tmp_path: Path, monkeypatch, capsys):
    media = tmp_path / "media"
    stem = "electricsheep.247.00505"
    _write_named(media, stem, "frosty_swirles")
    cfg = {"_repo_root": str(tmp_path), "paths": {"media_library": str(media)}}
    calls: list[str | None] = []

    def fake_scan(_cfg, sheep_id=None, limit=None):
        calls.append(sheep_id)
        return []

    monkeypatch.setattr("pipeline.refactor.scan_catalog", fake_scan)
    import argparse

    from pipeline.refactor import _cmd_preview, _cmd_report

    rc = _cmd_report(
        cfg,
        argparse.Namespace(sheep_id="frosty_swirles", limit=None, failing=False, json=True),
    )
    assert rc == 0
    assert calls == [stem]
    missing = _cmd_report(
        cfg,
        argparse.Namespace(sheep_id="missing_name", limit=None, failing=False, json=True),
    )
    assert missing == 2
    assert calls == [stem]
    assert "alias not found: missing_name" in capsys.readouterr().err
    preview = _cmd_preview(
        cfg,
        argparse.Namespace(sheep_id="missing_name", discard=False, preview_poster=False),
    )
    assert preview == 2
