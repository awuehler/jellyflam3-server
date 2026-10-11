"""Pedigree breed sidecars leave the inbox with the genome."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.breed import (
    adopt_pedigree_lineage,
    merge_pedigree_lineage,
    reap_orphaned_pedigree_sidecars,
    release_pedigree_sidecar,
    settle_pedigree_after_recovery,
)
from pipeline.job_recovery import JobRecord, reclaim_job
from pipeline.refactor_actions import _genome_companions
from pipeline.sheep_tax import tax_path
from pipeline.stills import merge_reserved_sidecar_keys
from pipeline.worker import claim_inbox_genome, quarantine_genome

STEM = "electricsheep.pedigree.mutate.abcd1234"
PARENT = "/pool/electricsheep.247.00505.flam3"


def _breed(stem: str = STEM, **extra: object) -> str:
    payload = {
        "id": stem,
        "origin": "local_pedigree",
        "method": "mutate",
        "parents": [PARENT],
        "generation": 1,
        "license": "cc-by-nc",
        "tags": ["cc-by-nc", "brood"],
        "bred_at": "2026-10-10T00:00:00Z",
    }
    payload.update(extra)
    return json.dumps(payload)


def _write_breed(directory: Path, stem: str = STEM) -> Path:
    path = directory / f"{stem}.jellyflam3.json"
    path.write_text(_breed(stem), encoding="utf-8")
    return path


def _cfg(tmp: Path) -> dict:
    inbox = tmp / "inbox"
    media = tmp / "media"
    jobs = tmp / "jobs"
    frames = tmp / "frames"
    quarantine = tmp / "quarantine"
    done = tmp / "done"
    for path in (inbox, media, jobs, frames, quarantine, done):
        path.mkdir(parents=True, exist_ok=True)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "media_library": str(media),
            "genomes_inbox": str(inbox),
            "genomes_quarantine": str(quarantine),
            "genomes_done": str(done),
            "jobs_dir": str(jobs),
            "frames_scratch": str(frames),
        },
    }


def test_merge_keeps_catalog_license_and_existing_parents():
    catalog = {"id": STEM, "license": "cc-by", "parents": ["/already"]}
    merge_pedigree_lineage(catalog, json.loads(_breed()))
    assert catalog["license"] == "cc-by"
    assert catalog["parents"] == ["/already"]
    assert catalog["origin"] == "local_pedigree"
    assert catalog["method"] == "mutate"
    assert catalog["bred_at"] == "2026-10-10T00:00:00Z"


def test_merge_reserved_keeps_lineage_on_reingest():
    sidecar = {"id": STEM, "license": "cc-by"}
    prior = {
        "id": STEM,
        "origin": "local_pedigree",
        "method": "cross",
        "parents": [PARENT],
        "generation": 1,
        "bred_at": "2026-10-01T00:00:00Z",
        "cross_method": "alternate",
        "alias": "quiet_turing",
    }
    merge_reserved_sidecar_keys(sidecar, prior)
    assert sidecar["parents"] == [PARENT]
    assert sidecar["cross_method"] == "alternate"
    assert sidecar["alias"] == "quiet_turing"
    assert sidecar["license"] == "cc-by"


def test_release_leaves_git_feedstock(tmp_path: Path):
    git = tmp_path / "genomes" / "pedigree"
    git.mkdir(parents=True)
    side = _write_breed(git)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    assert release_pedigree_sidecar(side, inbox) is False
    assert side.is_file()


def test_claim_moves_breed_sidecar_and_leaves_other_json(tmp_path: Path):
    inbox = tmp_path / "inbox"
    work = tmp_path / "job"
    inbox.mkdir()
    work.mkdir()
    src = inbox / f"{STEM}.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    side = _write_breed(inbox)
    other = inbox / "notes.jellyflam3.json"
    other.write_text("{}", encoding="utf-8")
    claimed = claim_inbox_genome(src, work, inbox)
    assert claimed == work / src.name
    assert not side.exists()
    assert (work / side.name).is_file()
    assert other.is_file()
    assert json.loads((work / side.name).read_text(encoding="utf-8"))["origin"] == "local_pedigree"


def test_quarantine_remove_src_parks_sidecar_beside_dest(tmp_path: Path):
    src = tmp_path / "work" / f"{STEM}.flam3"
    src.parent.mkdir()
    src.write_text("<flame/>", encoding="utf-8")
    side = _write_breed(src.parent)
    quarantine = tmp_path / "quarantine"
    dest = quarantine_genome(src, quarantine, remove_src=True)
    assert dest.is_file()
    assert not src.exists()
    assert not side.exists()
    parked = dest.with_suffix(".jellyflam3.json")
    assert parked.is_file()
    assert json.loads(parked.read_text(encoding="utf-8"))["parents"] == [PARENT]


def test_quarantine_copy_leaves_sidecar_with_source(tmp_path: Path):
    src = tmp_path / "inbox" / f"{STEM}.flam3"
    src.parent.mkdir()
    src.write_text("<flame/>", encoding="utf-8")
    side = _write_breed(src.parent)
    quarantine_genome(src, tmp_path / "quarantine", remove_src=False)
    assert src.is_file()
    assert side.is_file()
    assert list((tmp_path / "quarantine").glob("*.jellyflam3.json")) == []


def test_adopt_then_release_only_after_catalog_write(tmp_path: Path):
    inbox = tmp_path / "inbox"
    work = tmp_path / "work"
    inbox.mkdir()
    work.mkdir()
    genome = work / f"{STEM}.flam3"
    genome.write_text("<flame/>", encoding="utf-8")
    side = _write_breed(work)
    catalog = {"id": STEM, "license": "cc-by"}
    found = adopt_pedigree_lineage(catalog, genome, inbox)
    assert found == side
    assert side.is_file()
    assert catalog["parents"] == [PARENT]
    assert catalog["license"] == "cc-by"
    assert release_pedigree_sidecar(found, inbox, work) is True
    assert not side.exists()


def test_reap_leaves_waiting_genome_and_publishes_orphan(tmp_path: Path):
    cfg = _cfg(tmp_path)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    waiting = "electricsheep.pedigree.cross.b02b4b20"
    (inbox / f"{waiting}.flam3").write_text("<flame/>", encoding="utf-8")
    waiting_side = _write_breed(inbox, waiting)
    orphan = _write_breed(inbox, STEM)
    (inbox / "not-pedigree.jellyflam3.json").write_text("{}", encoding="utf-8")
    mp4 = (
        Path(cfg["paths"]["media_library"])
        / "by-generation"
        / "pedigree"
        / f"{STEM}.mp4"
    )
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"mp4")
    (mp4.with_suffix(".jellyflam3.json")).write_text(
        json.dumps({"id": STEM, "license": "cc-by"}), encoding="utf-8"
    )

    assert reap_orphaned_pedigree_sidecars(cfg) == 1
    assert waiting_side.is_file()
    assert (inbox / f"{waiting}.flam3").is_file()
    assert not orphan.exists()
    assert (inbox / "not-pedigree.jellyflam3.json").is_file()
    catalog = json.loads(mp4.with_suffix(".jellyflam3.json").read_text(encoding="utf-8"))
    assert catalog["license"] == "cc-by"
    assert catalog["parents"] == [PARENT]
    assert catalog["origin"] == "local_pedigree"


def test_reap_parks_beside_quarantine_genome_or_into_quarantine(tmp_path: Path):
    cfg = _cfg(tmp_path)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    quarantine = Path(cfg["paths"]["genomes_quarantine"])
    q_stem = "electricsheep.pedigree.mutate.1111aaaa"
    (quarantine / f"{q_stem}.flam3").write_text("<flame/>", encoding="utf-8")
    _write_breed(inbox, q_stem)
    gone = "electricsheep.pedigree.interpolate.2222bbbb"
    _write_breed(inbox, gone)

    assert reap_orphaned_pedigree_sidecars(cfg) == 2
    assert not list(inbox.glob("*.jellyflam3.json"))
    parked = quarantine / f"{q_stem}.jellyflam3.json"
    assert parked.is_file()
    assert (quarantine / f"{gone}.jellyflam3.json").is_file()
    assert not (quarantine / f"{gone}.flam3").exists()


def test_tax_quarantine_moves_breed_sidecar(tmp_path: Path, monkeypatch):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    genome = inbox / f"{STEM}.flam3"
    genome.write_text("<not-xml", encoding="utf-8")
    side = _write_breed(inbox)
    quarantine = tmp_path / "quarantine"

    monkeypatch.setattr(
        "pipeline.sheep_tax.scan_file",
        lambda *_a, **_k: {"ok": False, "issues": []},
    )
    tax_path(genome, {}, quarantine_dir=quarantine, write=True)
    assert not genome.exists()
    assert not side.exists()
    assert (quarantine / f"{STEM}.flam3").is_file()
    assert (quarantine / f"{STEM}.jellyflam3.json").is_file()


def test_refactor_companions_include_breed_sidecar(tmp_path: Path):
    genome = tmp_path / f"{STEM}.flam3"
    genome.write_text("<flame/>", encoding="utf-8")
    side = _write_breed(tmp_path)
    names = [path.name for path in _genome_companions(genome)]
    assert side.name in names


def test_recovery_requeue_restores_sidecar(tmp_path: Path):
    cfg = _cfg(tmp_path)
    job_id = "aaaabbbbcccc"
    work = Path(cfg["paths"]["jobs_dir"]) / job_id
    work.mkdir()
    missing = Path(cfg["paths"]["genomes_inbox"]) / f"{STEM}.flam3"
    optimized = work / "tv_optimized.flam3"
    optimized.write_text("<flame/>" + ("x" * 40), encoding="utf-8")
    side = _write_breed(work)
    jpath = work / "job.json"
    jpath.write_text(
        json.dumps({"id": job_id, "state": "rendering", "src": str(missing)}),
        encoding="utf-8",
    )
    action = reclaim_job(
        cfg, JobRecord(job_id, jpath, json.loads(jpath.read_text(encoding="utf-8")))
    )
    assert action.outcome == "orphaned"
    assert action.requeued == f"{STEM}.flam3"
    inbox = Path(cfg["paths"]["genomes_inbox"])
    assert (inbox / f"{STEM}.flam3").is_file()
    assert (inbox / side.name).is_file()
    assert not side.exists()


def test_recovery_superseded_merges_job_sidecar(tmp_path: Path):
    cfg = _cfg(tmp_path)
    mp4 = (
        Path(cfg["paths"]["media_library"])
        / "by-generation"
        / "pedigree"
        / f"{STEM}.mp4"
    )
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"mp4")
    (mp4.with_suffix(".jellyflam3.json")).write_text(
        json.dumps({"id": STEM, "license": "cc-by-nc"}), encoding="utf-8"
    )
    job_id = "dddd1111eeee"
    work = Path(cfg["paths"]["jobs_dir"]) / job_id
    work.mkdir()
    claimed = work / f"{STEM}.flam3"
    claimed.write_text("<flame/>", encoding="utf-8")
    side = _write_breed(work)
    jpath = work / "job.json"
    jpath.write_text(
        json.dumps({"id": job_id, "state": "encoding", "src": str(claimed)}),
        encoding="utf-8",
    )
    action = reclaim_job(
        cfg, JobRecord(job_id, jpath, json.loads(jpath.read_text(encoding="utf-8")))
    )
    assert action.outcome == "superseded"
    assert not side.exists()
    catalog = json.loads(mp4.with_suffix(".jellyflam3.json").read_text(encoding="utf-8"))
    assert catalog["parents"] == [PARENT]
    assert catalog["license"] == "cc-by-nc"
    assert list(Path(cfg["paths"]["genomes_inbox"]).glob("*.jellyflam3.json")) == []


def test_recovery_leaves_inbox_sidecar_while_genome_waits(tmp_path: Path):
    cfg = _cfg(tmp_path)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    genome = inbox / f"{STEM}.flam3"
    genome.write_text("<flame/>", encoding="utf-8")
    side = _write_breed(inbox)
    mp4 = (
        Path(cfg["paths"]["media_library"])
        / "by-generation"
        / "pedigree"
        / f"{STEM}.mp4"
    )
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"mp4")
    job_id = "ffff2222aaaa"
    work = Path(cfg["paths"]["jobs_dir"]) / job_id
    work.mkdir()
    jpath = work / "job.json"
    jpath.write_text(
        json.dumps({"id": job_id, "state": "queued", "src": str(genome)}),
        encoding="utf-8",
    )
    reclaim_job(cfg, JobRecord(job_id, jpath, json.loads(jpath.read_text(encoding="utf-8"))))
    assert side.is_file()
    assert genome.is_file()


def test_worker_wires_lineage_before_catalog_write():
    text = Path(__file__).resolve().parents[1].joinpath("pipeline", "worker.py").read_text(
        encoding="utf-8"
    )
    adopt_at = text.index("adopt_pedigree_lineage")
    write_at = text.index('(dest_dir / f"{base}.jellyflam3.json").write_text')
    release_at = text.index("release_pedigree_sidecar")
    assert adopt_at < write_at < release_at
    assert "reap_orphaned_pedigree_sidecars" in text
    assert "take_pedigree_sidecar" in text
    assert "park_pedigree_sidecar" in text
