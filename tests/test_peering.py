from pathlib import Path

from pipeline.peering import (
    assess_peering_readiness,
    ensure_layout,
    hygiene,
    is_opted_in,
    list_inbox_flam3,
    list_peer_junk_files,
    opt_in,
    opt_out,
    peers_inbox,
    peers_share_out,
    promote,
    publish,
    tailscale_ready,
    write_stignore,
)
from pipeline import share_security


def _cfg(tmp_path: Path, *, security: bool = True) -> dict:
    return {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": "genomes/inbox",
            "genomes_quarantine": "genomes/quarantine",
        },
        "peering": {
            "peers_dir": "genomes/peers",
            "peers_inbox": "genomes/peers/inbox",
            "opt_in_ack": "genomes/peers/OPT_IN",
            "status_file": str(tmp_path / "peering_status.json"),
            "sync_glob": "*.flam3,*-poster.jpg",
            "share_pedigree_only_eventually": True,
            "tailscale": {"tag": "tag:jellyflam3", "auth_key_env": "TS_AUTHKEY"},
            "share_security": {
                "enabled": security,
                "prefer_ed25519": True,
                "allow_sha256_fallback": True,
                "private_key_file": "var/share_security/ed25519.pem",
                "public_key_file": "var/share_security/ed25519.pub",
                "trusted_keys_dir": "var/share_security/trusted",
            },
        },
        "sheep_tax": {"enabled": True, "on_peer_promote": True},
    }


GOOD_FLAME = (
    '<flame size="800 600" scale="600">'
    '<xform weight="1" coefs="1 0 0 1 0 0"/>'
    "</flame>"
)


def test_ensure_layout_writes_stignore(tmp_path: Path):
    (tmp_path / "deploy" / "peering").mkdir(parents=True)
    (tmp_path / "deploy" / "peering" / "stignore").write_text(
        "!*.flam3\n!*-poster.jpg\n!*.flam3.sha256\n!*.flam3.jellyflam3.sig\n*\n",
        encoding="utf-8",
    )
    cfg = _cfg(tmp_path)
    out = ensure_layout(cfg)
    st = Path(out["stignore"])
    assert st.is_file()
    text = st.read_text(encoding="utf-8")
    assert text.index("!*.flam3") < text.index("\n*")
    assert "!*.flam3.sha256" in text
    assert (tmp_path / "genomes" / "peers" / "share-out").is_dir()


def test_write_stignore_fallback(tmp_path: Path):
    inbox = tmp_path / "inbox"
    dest = write_stignore(inbox, tmp_path / "missing")
    assert dest.is_file()
    text = dest.read_text(encoding="utf-8")
    assert "!*.flam3" in text
    assert "!*-poster.jpg" in text
    assert "!*.flam3.sha256" in text
    assert "!*.flam3.jellyflam3.sig" in text
    assert text.index("!*.flam3") < text.rindex("\n*")


def _live_share_mocks(monkeypatch):
    monkeypatch.setattr("pipeline.peering.unit_active", lambda _u: "active")
    monkeypatch.setattr(
        "pipeline.peering._tailscale_status_brief",
        lambda: {
            "installed": True,
            "ok": True,
            "backend_state": "Running",
            "online": True,
            "dns_name": "pi.test.ts.net",
        },
    )


def test_tailscale_ready_requires_running_online():
    assert tailscale_ready(
        {"installed": True, "ok": True, "backend_state": "Running", "online": True}
    )
    assert not tailscale_ready(
        {"installed": True, "ok": True, "backend_state": "NeedsLogin", "online": False}
    )


def test_assess_peering_readiness_opt_in_not_live(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path)
    ack = tmp_path / "genomes" / "peers" / "OPT_IN"
    ack.parent.mkdir(parents=True, exist_ok=True)
    ack.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("pipeline.peering.unit_active", lambda _u: "inactive")
    monkeypatch.setattr(
        "pipeline.peering._tailscale_status_brief",
        lambda: {
            "installed": True,
            "ok": True,
            "backend_state": "NeedsLogin",
            "online": False,
        },
    )
    live = assess_peering_readiness(cfg)
    assert live["share_opt_in"] is True
    assert live["share_live"] is False
    assert len(live["issues"]) == 2


def test_assess_peering_readiness_opt_out_ok(tmp_path: Path, monkeypatch):
    cfg = _cfg(tmp_path)
    monkeypatch.setattr("pipeline.peering.unit_active", lambda _u: "inactive")
    live = assess_peering_readiness(cfg)
    assert live["share_opt_in"] is False
    assert live["share_live"] is False
    assert live["issues"] == []


def test_opt_in_out_ack(tmp_path: Path, monkeypatch):
    (tmp_path / "deploy" / "peering").mkdir(parents=True)
    (tmp_path / "deploy" / "peering" / "stignore").write_text(
        "!*.flam3\n!*-poster.jpg\n*\n", encoding="utf-8"
    )
    cfg = _cfg(tmp_path)
    monkeypatch.delenv("TS_AUTHKEY", raising=False)
    _live_share_mocks(monkeypatch)
    r = opt_in(cfg, dry_run=False)
    assert r["ok"] is True
    assert r["opted_in"] is True
    assert r["share_live"] is True
    assert is_opted_in(cfg)
    r2 = opt_out(cfg, dry_run=False)
    assert r2["opted_in"] is False
    assert not is_opted_in(cfg)


def test_opt_in_rolls_back_without_live_share(tmp_path: Path, monkeypatch):
    (tmp_path / "deploy" / "peering").mkdir(parents=True)
    (tmp_path / "deploy" / "peering" / "stignore").write_text(
        "!*.flam3\n!*-poster.jpg\n*\n", encoding="utf-8"
    )
    cfg = _cfg(tmp_path)
    monkeypatch.delenv("TS_AUTHKEY", raising=False)
    monkeypatch.setattr("pipeline.peering.unit_active", lambda _u: "inactive")
    monkeypatch.setattr(
        "pipeline.peering._tailscale_status_brief",
        lambda: {
            "installed": True,
            "ok": True,
            "backend_state": "NeedsLogin",
            "online": False,
        },
    )
    r = opt_in(cfg, dry_run=False)
    assert r["ok"] is False
    assert r["opted_in"] is False
    assert not is_opted_in(cfg)


def test_promote_tax_quarantines_bad_xml(tmp_path: Path):
    (tmp_path / "deploy" / "peering").mkdir(parents=True)
    (tmp_path / "deploy" / "peering" / "stignore").write_text(
        "!*.flam3\n!*-poster.jpg\n*\n", encoding="utf-8"
    )
    cfg = _cfg(tmp_path, security=False)
    ensure_layout(cfg)
    flam = peers_inbox(cfg) / "bad.flam3"
    flam.write_text("<<<not-xml>>>", encoding="utf-8")
    summary = promote(cfg, apply=True, skip_tax=False)
    assert summary["results"][0]["action"] == "quarantine"
    assert not flam.is_file()
    assert (tmp_path / "genomes" / "quarantine" / "bad.flam3").is_file()


def test_promote_tax_allows_good_genome(tmp_path: Path):
    (tmp_path / "deploy" / "peering").mkdir(parents=True)
    (tmp_path / "deploy" / "peering" / "stignore").write_text(
        "!*.flam3\n!*-poster.jpg\n*\n", encoding="utf-8"
    )
    cfg = _cfg(tmp_path, security=False)
    ensure_layout(cfg)
    flam = peers_inbox(cfg) / "good.flam3"
    flam.write_text(GOOD_FLAME, encoding="utf-8")
    summary = promote(cfg, apply=True, skip_tax=False)
    assert summary["results"][0]["action"] == "promote"
    assert (tmp_path / "genomes" / "inbox" / "good.flam3").is_file()


def test_promote_skip_tax_moves(tmp_path: Path):
    (tmp_path / "deploy" / "peering").mkdir(parents=True)
    (tmp_path / "deploy" / "peering" / "stignore").write_text(
        "!*.flam3\n!*-poster.jpg\n*\n", encoding="utf-8"
    )
    cfg = _cfg(tmp_path, security=False)
    ensure_layout(cfg)
    flam = peers_inbox(cfg) / "peer.flam3"
    flam.write_text("<flame/>", encoding="utf-8")
    summary = promote(cfg, apply=True, skip_tax=True)
    assert summary["results"][0]["action"] == "promote"
    assert not flam.is_file()
    assert (tmp_path / "genomes" / "inbox" / "peer.flam3").is_file()


def test_promote_moves_companion_poster(tmp_path: Path):
    (tmp_path / "deploy" / "peering").mkdir(parents=True)
    (tmp_path / "deploy" / "peering" / "stignore").write_text(
        "!*.flam3\n!*-poster.jpg\n*\n", encoding="utf-8"
    )
    cfg = _cfg(tmp_path, security=False)
    ensure_layout(cfg)
    flam = peers_inbox(cfg) / "peer.flam3"
    poster = peers_inbox(cfg) / "peer-poster.jpg"
    flam.write_text("<flame/>", encoding="utf-8")
    poster.write_bytes(b"jpeg")
    summary = promote(cfg, apply=True, skip_tax=True)
    assert summary["results"][0]["action"] == "promote"
    assert summary["results"][0].get("poster_dest")
    assert (tmp_path / "genomes" / "inbox" / "peer.flam3").is_file()
    assert (tmp_path / "genomes" / "inbox" / "peer-poster.jpg").is_file()
    assert not poster.is_file()


def test_list_inbox(tmp_path: Path):
    cfg = _cfg(tmp_path)
    ensure_layout(cfg)
    (peers_inbox(cfg) / "a.flam3").write_text("x", encoding="utf-8")
    (peers_inbox(cfg) / "b.mp4").write_text("x", encoding="utf-8")
    names = [p.name for p in list_inbox_flam3(cfg)]
    assert names == ["a.flam3"]


def test_hygiene_lists_and_removes_peer_mp4(tmp_path: Path):
    cfg = _cfg(tmp_path)
    ensure_layout(cfg)
    junk = peers_inbox(cfg) / "should_ignore.mp4"
    junk.write_bytes(b"")
    assert list_peer_junk_files(cfg) == [junk]
    listed = hygiene(cfg, apply=False)
    assert str(junk) in listed["peer_junk"]
    assert junk.is_file()
    applied = hygiene(cfg, apply=True)
    assert str(junk) in applied["removed"]
    assert not junk.exists()


def test_share_security_sha256_roundtrip_promote(tmp_path: Path):
    cfg = _cfg(tmp_path)
    # No private key → SHA-256 fallback
    ensure_layout(cfg)
    flam = peers_inbox(cfg) / "peer.flam3"
    flam.write_text(GOOD_FLAME, encoding="utf-8")
    written = share_security.write_integrity(flam, cfg)
    assert written["ok"] is True
    assert written["alg"] == "sha256"
    assert share_security.sha256_sidecar_path_for(flam).is_file()
    summary = promote(cfg, apply=True, skip_tax=True)
    assert summary["results"][0]["action"] == "promote"
    assert summary["results"][0]["share_security"]["result"] == "verified"


def test_share_security_missing_sidecar_quarantines(tmp_path: Path):
    cfg = _cfg(tmp_path)
    ensure_layout(cfg)
    flam = peers_inbox(cfg) / "peer.flam3"
    flam.write_text(GOOD_FLAME, encoding="utf-8")
    summary = promote(cfg, apply=True, skip_tax=True)
    assert summary["results"][0]["action"] == "quarantine"
    assert summary["results"][0]["quarantine_reason"] == "share_security"
    assert (tmp_path / "genomes" / "quarantine" / "peer.flam3").is_file()


def test_share_security_tamper_rejects(tmp_path: Path):
    cfg = _cfg(tmp_path)
    ensure_layout(cfg)
    flam = peers_inbox(cfg) / "peer.flam3"
    flam.write_text(GOOD_FLAME, encoding="utf-8")
    share_security.write_integrity(flam, cfg)
    flam.write_text(GOOD_FLAME + "<!--tamper-->", encoding="utf-8")
    summary = promote(cfg, apply=True, skip_tax=True)
    assert summary["results"][0]["action"] == "quarantine"
    assert summary["results"][0]["share_security"]["ok"] is False


def test_share_security_ed25519_roundtrip(tmp_path: Path):
    cfg = _cfg(tmp_path)
    ensure_layout(cfg)
    keys = share_security.gen_keypair(cfg)
    assert keys["ok"] is True
    assert keys["key_id"]
    flam = peers_inbox(cfg) / "peer.flam3"
    flam.write_text(GOOD_FLAME, encoding="utf-8")
    written = share_security.write_integrity(flam, cfg)
    assert written["alg"] == "ed25519"
    assert share_security.sig_path_for(flam).is_file()
    verified = share_security.verify_integrity(flam, cfg)
    assert verified["ok"] is True
    assert verified["alg"] == "ed25519"
    summary = promote(cfg, apply=True, skip_tax=True)
    assert summary["results"][0]["action"] == "promote"


def test_share_security_ed25519_roundtrip_missing_pub(tmp_path: Path):
    """Regression: priv without .pub must still verify (heal from private key)."""
    cfg = _cfg(tmp_path)
    ensure_layout(cfg)
    share_security.gen_keypair(cfg)
    pub = share_security.public_key_path(cfg)
    pub.unlink()
    flam = peers_inbox(cfg) / "peer.flam3"
    flam.write_text(GOOD_FLAME, encoding="utf-8")
    written = share_security.write_integrity(flam, cfg)
    assert written["alg"] == "ed25519"
    verified = share_security.verify_integrity(flam, cfg)
    assert verified["ok"] is True
    assert verified["alg"] == "ed25519"


def test_publish_writes_sidecar_and_stages(tmp_path: Path):
    cfg = _cfg(tmp_path)
    ensure_layout(cfg)
    share_security.gen_keypair(cfg)
    src = tmp_path / "local.flam3"
    src.write_text(GOOD_FLAME, encoding="utf-8")
    summary = publish(cfg, [src], apply=True, skip_tax=False)
    assert summary["results"][0]["action"] == "publish"
    assert summary["results"][0]["share_security"]["ok"] is True
    dest = peers_share_out(cfg) / "local.flam3"
    assert dest.is_file()
    assert share_security.sig_path_for(dest).is_file() or share_security.sha256_sidecar_path_for(
        dest
    ).is_file()


def test_trust_key_enrolls_peer(tmp_path: Path):
    peer = tmp_path / "peer"
    local = tmp_path / "local"
    peer.mkdir()
    local.mkdir()
    cfg_peer = _cfg(peer)
    cfg_local = _cfg(local)
    share_security.gen_keypair(cfg_peer)
    share_security.gen_keypair(cfg_local)

    flam = local / "peer.flam3"
    flam.write_text(GOOD_FLAME, encoding="utf-8")
    cfg_sign = _cfg(peer)
    cfg_sign["peering"]["share_security"]["private_key_file"] = str(
        share_security.private_key_path(cfg_peer)
    )
    cfg_sign["peering"]["share_security"]["public_key_file"] = str(
        share_security.public_key_path(cfg_peer)
    )
    written = share_security.write_integrity(flam, cfg_sign)
    assert written["alg"] == "ed25519"

    bad = share_security.verify_integrity(flam, cfg_local)
    assert bad["ok"] is False
    assert bad["reason"] == "untrusted_key"

    enrolled = share_security.trust_public_key(
        cfg_local, share_security.public_key_path(cfg_peer), name="peer"
    )
    assert enrolled["ok"] is True
    good = share_security.verify_integrity(flam, cfg_local)
    assert good["ok"] is True
    assert good["alg"] == "ed25519"
