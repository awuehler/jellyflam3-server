"""Unit tests for pipeline.share_votes (Phase 4 / Wave 3 share cron)."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.peering import peers_share_out
from pipeline.share_votes import meets_share_threshold, run_share_votes, share_votes_cfg
from pipeline.share_security import gen_keypair
from pipeline.sheep_votes import DEFAULT_FEEDBACK, increment_feedback

GOOD_FLAME = (
    '<flame size="800 600" scale="600">'
    '<xform weight="1" coefs="1 0 0 1 0 0"/>'
    "</flame>"
)


def _cfg(tmp_path: Path, *, opted: bool = True, **share_over) -> dict:
    (tmp_path / "deploy" / "peering").mkdir(parents=True)
    (tmp_path / "deploy" / "peering" / "stignore").write_text(
        "!*.flam3\n!*-poster.jpg\n!*.flam3.sha256\n!*.flam3.jellyflam3.sig\n*\n",
        encoding="utf-8",
    )
    inbox = tmp_path / "genomes" / "inbox"
    done = tmp_path / "genomes" / "done"
    quar = tmp_path / "genomes" / "quarantine"
    media = tmp_path / "media" / "by-generation" / "247"
    peers = tmp_path / "genomes" / "peers"
    for d in (inbox, done, quar, media, peers):
        d.mkdir(parents=True, exist_ok=True)
    ack = peers / "OPT_IN"
    if opted:
        ack.write_text("1\n", encoding="utf-8")
    share = {
        "enabled": True,
        "min_votes": 1,
        "min_loves": 0,
        "require_opt_in": True,
        "require_share_candidate": True,
    }
    share.update(share_over)
    return {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": "genomes/inbox",
            "genomes_done": "genomes/done",
            "genomes_quarantine": "genomes/quarantine",
            "media_library": str(tmp_path / "media"),
        },
        "share_votes": share,
        "license": {"commercial_mode": False, "exclude_tags": ["cc-by-nc"]},
        "sheep_tax": {"enabled": True, "on_peer_promote": True},
        "peering": {
            "peers_dir": "genomes/peers",
            "peers_inbox": "genomes/peers/inbox",
            "opt_in_ack": str(ack),
            "status_file": str(tmp_path / "peering_status.json"),
            "share_security": {
                "enabled": True,
                "prefer_ed25519": True,
                "allow_sha256_fallback": True,
                "private_key_file": "var/share_security/ed25519.pem",
                "public_key_file": "var/share_security/ed25519.pub",
                "trusted_keys_dir": "var/share_security/trusted",
            },
        },
    }


def _write_voted_sheep(
    tmp_path: Path,
    *,
    stem: str = "electricsheep.247.00505",
    votes: int = 1,
    loves: int = 0,
    likes: int = 1,
    license_tag: str = "cc-by",
    in_done: bool = True,
) -> Path:
    media = tmp_path / "media" / "by-generation" / "247"
    side = media / f"{stem}.jellyflam3.json"
    fb = dict(DEFAULT_FEEDBACK)
    for _ in range(max(0, likes)):
        fb = increment_feedback(fb, "like")
    for _ in range(max(0, loves)):
        fb = increment_feedback(fb, "love")
    # increment_feedback already bumps votes; clamp to requested totals when needed
    fb["votes"] = votes
    fb["likes"] = likes
    fb["loves"] = loves
    fb["share_candidate"] = votes > 0 or likes > 0 or loves > 0
    side.write_text(
        json.dumps(
            {
                "id": stem,
                "license": license_tag,
                "tags": [license_tag],
                "viewer_feedback": fb,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    flam = tmp_path / "genomes" / "done" / f"{stem}.flam3"
    if in_done:
        flam.write_text(GOOD_FLAME, encoding="utf-8")
    return flam


def test_threshold_requires_share_candidate_and_min_votes():
    sv = share_votes_cfg({})
    assert meets_share_threshold({"votes": 2, "share_candidate": True}, sv)
    assert not meets_share_threshold({"votes": 2, "share_candidate": False}, sv)
    assert not meets_share_threshold({"votes": 0, "share_candidate": True}, sv)


def test_skip_when_disabled(tmp_path: Path):
    cfg = _cfg(tmp_path, enabled=False)
    _write_voted_sheep(tmp_path)
    out = run_share_votes(cfg, apply=True)
    assert out["action"] == "skip"
    assert out["reason"] == "disabled"
    assert not list(peers_share_out(cfg).glob("*.flam3"))


def test_skip_when_opt_out(tmp_path: Path):
    cfg = _cfg(tmp_path, opted=False)
    _write_voted_sheep(tmp_path)
    out = run_share_votes(cfg, apply=True)
    assert out["action"] == "skip"
    assert out["reason"] == "opt_out"
    inbox = tmp_path / "genomes" / "inbox"
    assert list(inbox.glob("*.flam3")) == []


def test_plan_does_not_copy(tmp_path: Path):
    cfg = _cfg(tmp_path)
    gen_keypair(cfg)
    _write_voted_sheep(tmp_path)
    out = run_share_votes(cfg, apply=False)
    assert out["action"] == "plan"
    assert out["candidates"] == 1
    assert not (peers_share_out(cfg) / "electricsheep.247.00505.flam3").exists()
    assert list((tmp_path / "genomes" / "inbox").glob("*.flam3")) == []


def test_apply_copies_share_out_not_inbox(tmp_path: Path):
    cfg = _cfg(tmp_path)
    gen_keypair(cfg)
    flam = _write_voted_sheep(tmp_path)
    out = run_share_votes(cfg, apply=True)
    assert out["action"] == "share"
    dest = peers_share_out(cfg) / flam.name
    assert dest.is_file()
    assert flam.is_file()  # copy, not move
    assert list((tmp_path / "genomes" / "inbox").glob("*.flam3")) == []


def test_skip_nc_when_commercial_mode(tmp_path: Path):
    cfg = _cfg(tmp_path)
    cfg["license"]["commercial_mode"] = True
    gen_keypair(cfg)
    _write_voted_sheep(tmp_path, license_tag="cc-by-nc")
    out = run_share_votes(cfg, apply=True)
    assert out["action"] == "skip"
    assert out["reason"] == "no_candidates"
    assert any(s.get("reason") == "commercial_nc" for s in out["skipped"])


def test_skip_missing_genome(tmp_path: Path):
    cfg = _cfg(tmp_path)
    gen_keypair(cfg)
    _write_voted_sheep(tmp_path, in_done=False)
    out = run_share_votes(cfg, apply=True)
    assert out["reason"] == "no_candidates"
    assert any(s.get("reason") == "genome_missing" for s in out["skipped"])


def test_skip_inbox_genome(tmp_path: Path):
    cfg = _cfg(tmp_path)
    gen_keypair(cfg)
    _write_voted_sheep(tmp_path, in_done=False)
    inbox_g = tmp_path / "genomes" / "inbox" / "electricsheep.247.00505.flam3"
    inbox_g.write_text(GOOD_FLAME, encoding="utf-8")
    out = run_share_votes(cfg, apply=True)
    assert any(s.get("reason") == "genome_missing" for s in out["skipped"])
    assert inbox_g.is_file()
    assert list(peers_share_out(cfg).glob("*.flam3")) == []
