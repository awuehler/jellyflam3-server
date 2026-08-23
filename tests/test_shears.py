"""Tests for Phase 3 Sheep Shears cascade discover / delete / add."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.shears import (
    CONFIRM_TOKEN,
    apply_delete,
    discover_cascade,
    find_pedigree_orphan_warnings,
    resolve_sheep_base,
    shears_add,
)


def _cfg(tmp: Path) -> dict:
    media = tmp / "media"
    inbox = tmp / "genomes" / "inbox"
    quarantine = tmp / "genomes" / "quarantine"
    done = tmp / "genomes" / "done"
    jobs = tmp / "jobs"
    frames = tmp / "frames"
    peers = tmp / "genomes" / "peers"
    for d in (media, inbox, quarantine, done, jobs, frames, peers / "inbox", peers / "share-out"):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "genomes_inbox": str(inbox),
            "genomes_quarantine": str(quarantine),
            "genomes_done": str(done),
            "jobs_dir": str(jobs),
            "frames_scratch": str(frames),
            "media_library": str(media),
        },
        "peering": {
            "peers_dir": str(peers),
            "peers_inbox": str(peers / "inbox"),
            "opt_in_ack": str(peers / "OPT_IN"),
        },
        "jellyfin": {"url": "", "api_key": ""},
    }


def test_resolve_sheep_base_variants():
    assert resolve_sheep_base("electricsheep.247.00505") == "electricsheep.247.00505"
    assert resolve_sheep_base("electricsheep.247.00505.flam3") == "electricsheep.247.00505"
    assert resolve_sheep_base(Path("/media/x/electricsheep.247.00505.mp4")) == (
        "electricsheep.247.00505"
    )
    assert resolve_sheep_base("jellyflam3.247.00505.flam3") == "electricsheep.247.00505"
    assert resolve_sheep_base("electricsheep.247.00505-poster.jpg") == (
        "electricsheep.247.00505"
    )


def test_discover_and_confirm_delete(tmp_path: Path):
    cfg = _cfg(tmp_path)
    base = "electricsheep.247.00505"
    inbox = Path(cfg["paths"]["genomes_inbox"])
    flam3 = inbox / f"{base}.flam3"
    flam3.write_text("<flame/>", encoding="utf-8")
    (inbox / f"{base}.jellyflam3.json").write_text("{}", encoding="utf-8")

    media = Path(cfg["paths"]["media_library"])
    cat = media / "by-generation" / "247"
    cat.mkdir(parents=True)
    mp4 = cat / f"{base}.mp4"
    mp4.write_bytes(b"mp4")
    (cat / f"{base}.jellyflam3.json").write_text(
        json.dumps({"id": base}), encoding="utf-8"
    )
    (cat / f"{base}-poster.jpg").write_bytes(b"jpg")

    job_id = "abcdef012345"
    job_dir = Path(cfg["paths"]["jobs_dir"]) / job_id
    job_dir.mkdir(parents=True)
    (job_dir / "job.json").write_text(
        json.dumps({"state": "ingested", "src": str(flam3)}),
        encoding="utf-8",
    )
    frames = Path(cfg["paths"]["frames_scratch"]) / job_id
    frames.mkdir(parents=True)
    (frames / "f00001.png").write_bytes(b"x")

    report = discover_cascade(cfg, base)
    assert report.base == base
    assert flam3 in report.genomes
    assert mp4 in report.catalog
    assert job_dir in report.jobs
    assert frames in report.frames

    # dry-run leaves files
    apply_delete(cfg, report, dry_run=True)
    assert flam3.is_file()
    assert mp4.is_file()

    apply_delete(cfg, report, dry_run=False)
    assert not flam3.exists()
    assert not mp4.exists()
    assert not (cat / f"{base}-poster.jpg").exists()
    assert not job_dir.exists()
    assert not frames.exists()


def test_pedigree_orphan_warning(tmp_path: Path):
    cfg = _cfg(tmp_path)
    parent = "electricsheep.247.00505"
    child = "electricsheep.pedigree.mutate.deadbeef"
    done = Path(cfg["paths"]["genomes_done"])
    side = done / f"{child}.jellyflam3.json"
    side.write_text(
        json.dumps(
            {
                "id": child,
                "origin": "local_pedigree",
                "parents": [str(done / f"{parent}.flam3")],
            }
        ),
        encoding="utf-8",
    )
    warns = find_pedigree_orphan_warnings(cfg, parent)
    assert warns
    assert any(child in w for w in warns)


def test_shears_add(tmp_path: Path):
    cfg = _cfg(tmp_path)
    src = tmp_path / "electricsheep.244.00128.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    dest = shears_add(cfg, src)
    assert dest is not None
    assert dest.is_file()
    assert dest.name == "electricsheep.244.00128.flam3"
    assert shears_add(cfg, src) is None  # skip duplicate


def test_git_genome_dirs_scanned(tmp_path: Path):
    cfg = _cfg(tmp_path)
    base = "electricsheep.pedigree.smoke.0001"
    ped = tmp_path / "genomes" / "pedigree" / "smoke"
    ped.mkdir(parents=True)
    flam3 = ped / f"{base}.flam3"
    flam3.write_text("<flame/>", encoding="utf-8")
    (ped / f"{base}.jellyflam3.json").write_text("{}", encoding="utf-8")
    samples = tmp_path / "genomes" / "samples"
    samples.mkdir(parents=True)
    sample = samples / "electricsheep.247.00505.flam3"
    sample.write_text("<flame/>", encoding="utf-8")

    r_ped = discover_cascade(cfg, base)
    assert flam3 in r_ped.genomes

    r_samp = discover_cascade(cfg, "electricsheep.247.00505")
    assert sample in r_samp.genomes


def test_confirm_token_constant():
    assert CONFIRM_TOKEN == "DELETE"


def test_audit_and_sweep_orphans(tmp_path: Path):
    cfg = _cfg(tmp_path)
    media = Path(cfg["paths"]["media_library"])
    # orphan catalog (mp4, no genome)
    orphan = "electricsheep.242.00600"
    cat = media / "by-generation" / "242"
    cat.mkdir(parents=True)
    mp4 = cat / f"{orphan}.mp4"
    mp4.write_bytes(b"x")
    (cat / f"{orphan}.jellyflam3.json").write_text("{}", encoding="utf-8")
    # healthy sheep with genome + full catalog
    keep = "electricsheep.247.00505"
    done = Path(cfg["paths"]["genomes_done"])
    (done / f"{keep}.flam3").write_text("<flame/>", encoding="utf-8")
    kdir = media / "by-generation" / "247"
    kdir.mkdir(parents=True)
    (kdir / f"{keep}.mp4").write_bytes(b"y")
    (kdir / f"{keep}-poster.jpg").write_bytes(b"j")
    (kdir / f"{keep}.jellyflam3.json").write_text("{}", encoding="utf-8")
    # peer junk
    peers_inbox = Path(cfg["peering"]["peers_inbox"])
    junk = peers_inbox / "should_ignore.mp4"
    junk.write_bytes(b"")

    from pipeline.shears import audit_flock, sweep_orphans

    audit = audit_flock(cfg)
    assert orphan in audit.catalog_without_genome
    assert keep in audit.sheep
    assert keep not in audit.catalog_without_genome
    assert junk in audit.peer_junk
    assert keep not in audit.needs_backfill()

    sweep_orphans(cfg, dry_run=True, peer_junk=True)
    assert mp4.is_file()
    assert junk.is_file()

    sweep_orphans(cfg, dry_run=False, peer_junk=True)
    assert not mp4.exists()
    assert not junk.exists()
    assert (kdir / f"{keep}.mp4").is_file()
