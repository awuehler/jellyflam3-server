"""Unit tests for pipeline.sheep_votes (sidecar-only tallies)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.sheep_votes import (
    InvalidVote,
    StemNotFound,
    apply_vote,
    increment_feedback,
    normalize_feedback,
    resolve_vote_sidecar,
    show_vote,
    stem_from_media_path,
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
