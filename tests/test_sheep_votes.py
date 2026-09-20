"""Unit tests for pipeline.sheep_votes (sidecar-only tallies)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.sheep_votes import (
    DEFAULT_FEEDBACK,
    InvalidVote,
    StemNotFound,
    SWEEP_CONFIRM_TOKEN,
    apply_vote,
    cleared_feedback,
    feedback_needs_reset,
    increment_feedback,
    list_top_votes,
    main,
    normalize_feedback,
    resolve_vote_sidecar,
    show_vote,
    stem_from_media_path,
    sweep_votes,
)

STEM = "electricsheep.247.00505"


def _catalog(tmp_path: Path, extra: dict | None = None) -> Path:
    media = tmp_path / "media"
    gen = media / "by-generation" / "247"
    gen.mkdir(parents=True)
    mp4 = gen / f"{STEM}.mp4"
    mp4.write_bytes(b"x")
    sidecar = {
        "id": STEM,
        "type": "loop",
        "alias": "frosty_swirles",
        "alias_source": "auto",
        "watermark": {"enabled": False},
        "viewer_feedback": {
            "likes": 0,
            "loves": 0,
            "votes": 0,
            "last_voted_at": None,
            "share_candidate": False,
        },
    }
    if extra:
        sidecar.update(extra)
    (gen / f"{STEM}.jellyflam3.json").write_text(
        json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
    )
    return media


def _load(media: Path) -> dict:
    path = media / "by-generation" / "247" / f"{STEM}.jellyflam3.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_stem_from_media_path():
    assert stem_from_media_path("/media/sheep/by-generation/247/%s.mp4" % STEM) == STEM
    assert (
        stem_from_media_path("C:\\media\\sheep\\%s.jellyflam3.json" % STEM) == STEM
    )


def test_increment_like_sets_share_candidate():
    out = increment_feedback({}, "like", when="2026-09-11T20:00:00Z")
    assert out["likes"] == 1
    assert out["loves"] == 0
    assert out["votes"] == 1
    assert out["share_candidate"] is True
    assert out["last_voted_at"] == "2026-09-11T20:00:00Z"


def test_increment_love_and_plain_vote():
    love = increment_feedback(normalize_feedback(None), "love", when="t1")
    assert love["loves"] == 1 and love["votes"] == 1 and love["likes"] == 0
    vote = increment_feedback(love, "vote", when="t2")
    assert vote["votes"] == 2
    assert vote["loves"] == 1
    assert vote["likes"] == 0


def test_invalid_kind():
    with pytest.raises(InvalidVote, match="like, love, or vote"):
        increment_feedback({}, "star")


def test_apply_like_revote_preserves_reserved_keys(tmp_path: Path):
    media = _catalog(tmp_path)
    first = apply_vote(media, {"stem": STEM, "kind": "like"}, when="t1")
    assert first["ok"] is True
    assert first["viewer_feedback"]["likes"] == 1
    assert first["viewer_feedback"]["share_candidate"] is True
    second = apply_vote(
        media, {"STEM": STEM, "Kind": "like", "deviceId": "roku-lab"}, when="t2"
    )
    assert second["viewer_feedback"]["likes"] == 2
    assert second["viewer_feedback"]["votes"] == 2
    loaded = _load(media)
    assert loaded["alias"] == "frosty_swirles"
    assert loaded["type"] == "loop"
    assert loaded["watermark"] == {"enabled": False}
    assert loaded["viewer_feedback"]["last_voted_at"] == "t2"


def test_apply_via_mediapath_lowercase_roku_keys(tmp_path: Path):
    media = _catalog(tmp_path)
    path = "/media/sheep/by-generation/247/%s.mp4" % STEM
    result = apply_vote(
        media,
        {"mediapath": str(media / "by-generation" / "247" / f"{STEM}.mp4"), "kind": "love"},
        when="t3",
    )
    assert result["kind"] == "love"
    assert result["viewer_feedback"]["loves"] == 1
    assert result["viewer_feedback"]["votes"] == 1
    _ = path


def test_unknown_stem_404(tmp_path: Path):
    media = _catalog(tmp_path)
    with pytest.raises(StemNotFound):
        apply_vote(media, {"stem": "electricsheep.247.99999", "kind": "like"})


def test_missing_identity_is_invalid(tmp_path: Path):
    media = _catalog(tmp_path)
    with pytest.raises(InvalidVote, match="stem or mediaPath"):
        apply_vote(media, {"kind": "like"})


def test_does_not_invent_sidecar(tmp_path: Path):
    media = tmp_path / "media"
    (media / "by-generation" / "247").mkdir(parents=True)
    with pytest.raises(StemNotFound):
        apply_vote(media, {"stem": STEM, "kind": "vote"})
    assert not (media / "by-generation" / "247" / f"{STEM}.jellyflam3.json").exists()


def test_show_defaults_missing_block(tmp_path: Path):
    media = _catalog(tmp_path, extra={"viewer_feedback": {}})
    shown = show_vote(media, STEM)
    assert shown["viewer_feedback"]["likes"] == 0
    assert shown["viewer_feedback"]["share_candidate"] is False


def test_resolve_generation_sheep_id(tmp_path: Path):
    media = _catalog(tmp_path)
    path = resolve_vote_sidecar(media, generation="247", sheep_id="00505")
    assert path.name == f"{STEM}.jellyflam3.json"


def _catalog_cfg(tmp_path: Path, media: Path) -> Path:
    cfg = tmp_path / "jellyflam3.yaml"
    cfg.write_text(
        "paths:\n  media_library: %s\n" % media.as_posix().replace("\\", "/"),
        encoding="utf-8",
    )
    return cfg


def _write_sidecar(
    media: Path,
    stem: str,
    *,
    votes: int = 0,
    likes: int = 0,
    loves: int = 0,
    extra_root: dict | None = None,
    extra_fb: dict | None = None,
    gen: str | None = None,
) -> Path:
    parts = stem.split(".")
    generation = gen or (parts[1] if len(parts) > 2 else "247")
    dest = media / "by-generation" / generation
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{stem}.mp4").write_bytes(b"x")
    fb = dict(DEFAULT_FEEDBACK)
    fb.update(
        {
            "likes": likes,
            "loves": loves,
            "votes": votes,
            "share_candidate": votes > 0 or likes > 0 or loves > 0,
            "last_voted_at": "2026-09-16T00:00:00Z" if votes else None,
        }
    )
    if extra_fb:
        fb.update(extra_fb)
    payload = {
        "id": stem,
        "type": "loop",
        "alias": "keep_me",
        "alias_source": "human",
        "tags": ["cc-by", "pedigree"],
        "license": "cc-by",
        "watermark": {"enabled": False, "style": "image"},
        "viewer_feedback": fb,
        "refactor": [{"reason": "keep"}],
    }
    if extra_root:
        payload.update(extra_root)
    path = dest / f"{stem}.jellyflam3.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_feedback_needs_reset_defaults():
    assert feedback_needs_reset(None) is False
    assert feedback_needs_reset({}) is False
    assert feedback_needs_reset(dict(DEFAULT_FEEDBACK)) is False
    assert feedback_needs_reset({"votes": 1, "share_candidate": True}) is True
    assert feedback_needs_reset({"likes": 0, "extra": 1}) is True
    assert feedback_needs_reset("nope") is True
    assert cleared_feedback() == DEFAULT_FEEDBACK
    cleared_feedback()["votes"] = 9
    assert DEFAULT_FEEDBACK["votes"] == 0


def test_sweep_dry_run_does_not_write(tmp_path: Path):
    media = tmp_path / "media"
    path = _write_sidecar(media, STEM, votes=3, likes=2)
    before = path.read_text(encoding="utf-8")
    mtime = path.stat().st_mtime_ns
    out = sweep_votes(media, apply=False)
    assert out["action"] == "plan"
    assert out["dirty"] == 1
    assert out["reset"] == 0
    assert out["stems"] == [STEM]
    assert path.read_text(encoding="utf-8") == before
    assert path.stat().st_mtime_ns == mtime


def test_sweep_apply_resets_votes_preserves_other_keys(tmp_path: Path):
    media = tmp_path / "media"
    _write_sidecar(
        media,
        STEM,
        votes=4,
        likes=2,
        loves=1,
        extra_fb={"note": "drop-me"},
    )
    clean = _write_sidecar(media, "electricsheep.247.00999", votes=0)
    clean_mtime = clean.stat().st_mtime_ns
    out = sweep_votes(media, apply=True)
    assert out["ok"] is True
    assert out["action"] == "apply"
    assert out["scanned"] == 2
    assert out["dirty"] == 1
    assert out["reset"] == 1
    assert out["unchanged"] == 1
    loaded = json.loads(
        (media / "by-generation" / "247" / f"{STEM}.jellyflam3.json").read_text(
            encoding="utf-8"
        )
    )
    assert loaded["alias"] == "keep_me"
    assert loaded["alias_source"] == "human"
    assert loaded["type"] == "loop"
    assert loaded["tags"] == ["cc-by", "pedigree"]
    assert loaded["license"] == "cc-by"
    assert loaded["watermark"] == {"enabled": False, "style": "image"}
    assert loaded["refactor"] == [{"reason": "keep"}]
    assert loaded["viewer_feedback"] == DEFAULT_FEEDBACK
    assert "note" not in loaded["viewer_feedback"]
    assert clean.stat().st_mtime_ns == clean_mtime
    shown = show_vote(media, STEM)
    assert shown["viewer_feedback"]["votes"] == 0
    assert shown["viewer_feedback"]["share_candidate"] is False


def test_sweep_skips_unpublished_quarantine(tmp_path: Path):
    media = tmp_path / "media"
    _write_sidecar(media, STEM, votes=2)
    parked = (
        media
        / "_refactor-quarantine"
        / "by-generation"
        / "247"
        / "electricsheep.247.07777.jellyflam3.json"
    )
    parked.parent.mkdir(parents=True)
    parked.write_text(
        json.dumps(
            {
                "id": "electricsheep.247.07777",
                "viewer_feedback": {
                    "likes": 9,
                    "loves": 9,
                    "votes": 9,
                    "share_candidate": True,
                },
            }
        ),
        encoding="utf-8",
    )
    out = sweep_votes(media, apply=True)
    assert out["stems"] == [STEM]
    parked_data = json.loads(parked.read_text(encoding="utf-8"))
    assert parked_data["viewer_feedback"]["votes"] == 9


def test_sweep_one_stem_leaves_others(tmp_path: Path):
    media = tmp_path / "media"
    _write_sidecar(media, STEM, votes=2)
    other = "electricsheep.247.00111"
    _write_sidecar(media, other, votes=5)
    out = sweep_votes(media, apply=True, stem=STEM)
    assert out["scanned"] == 1
    assert out["reset"] == 1
    assert show_vote(media, STEM)["viewer_feedback"]["votes"] == 0
    assert show_vote(media, other)["viewer_feedback"]["votes"] == 5


def test_list_top_votes_ranks_and_caps(tmp_path: Path):
    media = tmp_path / "media"
    _write_sidecar(
        media, "electricsheep.247.00001", votes=2, likes=2, extra_root={"alias": "low_score"}
    )
    _write_sidecar(
        media,
        "electricsheep.247.00002",
        votes=9,
        likes=1,
        loves=8,
        extra_root={"alias": "hot_sheep"},
    )
    _write_sidecar(
        media, "electricsheep.247.00003", votes=5, likes=5, extra_root={"alias": "mid_sheep"}
    )
    _write_sidecar(media, "electricsheep.247.00004", votes=0)
    parked = (
        media
        / "_refactor-quarantine"
        / "by-generation"
        / "247"
        / "electricsheep.247.09999.jellyflam3.json"
    )
    parked.parent.mkdir(parents=True)
    parked.write_text(
        json.dumps(
            {
                "id": "electricsheep.247.09999",
                "viewer_feedback": {"votes": 99, "likes": 0, "loves": 0},
            }
        ),
        encoding="utf-8",
    )
    out = list_top_votes(media, limit=2)
    assert out["ok"] is True
    assert out["scanned"] == 4
    assert out["matched"] == 3
    assert out["count"] == 2
    assert [r["stem"] for r in out["rows"]] == [
        "electricsheep.247.00002",
        "electricsheep.247.00003",
    ]
    assert out["rows"][0]["alias"] == "hot_sheep"
    assert out["rows"][0]["votes"] == 9
    assert out["rows"][0]["loves"] == 8
    zeros = list_top_votes(media, limit=10, min_votes=0)
    assert zeros["matched"] == 4
    with pytest.raises(InvalidVote, match="limit"):
        list_top_votes(media, limit=0)


def test_top_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    media = tmp_path / "media"
    _write_sidecar(media, STEM, votes=3, likes=1, loves=2)
    cfg = _catalog_cfg(tmp_path, media)
    rc = main(["--config", str(cfg), "top", "-n", "1"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["rows"][0]["stem"] == STEM
    rc = main(["--config", str(cfg), "list", "--limit", "1"])
    assert rc == 0


def test_sweep_reports_unreadable_sidecar(tmp_path: Path):
    media = tmp_path / "media"
    dest = media / "by-generation" / "247"
    dest.mkdir(parents=True)
    (dest / f"{STEM}.jellyflam3.json").write_text("{not-json", encoding="utf-8")
    out = sweep_votes(media, apply=True)
    assert out["ok"] is False
    assert out["errors"][0]["reason"] == "unreadable_sidecar"
    assert out["reset"] == 0


def test_sweep_cli_confirm_and_wrong_token(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    media = tmp_path / "media"
    _write_sidecar(media, STEM, votes=2)
    cfg = _catalog_cfg(tmp_path, media)
    rc = main(["--config", str(cfg), "sweep"])
    assert rc == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["action"] == "plan"
    assert plan["dirty"] == 1
    assert show_vote(media, STEM)["viewer_feedback"]["votes"] == 2

    rc = main(["--config", str(cfg), "sweep", "--confirm", "DELETE"])
    assert rc == 2
    err = capsys.readouterr().err
    assert SWEEP_CONFIRM_TOKEN in err
    assert show_vote(media, STEM)["viewer_feedback"]["votes"] == 2

    rc = main(["--config", str(cfg), "sweep", "--confirm", SWEEP_CONFIRM_TOKEN])
    assert rc == 0
    applied = json.loads(capsys.readouterr().out)
    assert applied["action"] == "apply"
    assert applied["reset"] == 1
    assert show_vote(media, STEM)["viewer_feedback"] == DEFAULT_FEEDBACK
