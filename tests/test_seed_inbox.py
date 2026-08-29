from io import StringIO
from pathlib import Path
import contextlib
import re

import pytest

from pipeline.seed_inbox import catalog_mp4_exists, inbox_filename, main, run, sample_pool, select_samples, stage_file


def test_inbox_filename_extracts_electricsheep():
    p = Path("genomes/samples/electricsheep.247.00505.flam3")
    assert inbox_filename(p) == "electricsheep.247.00505.flam3"


def test_inbox_filename_normalizes_legacy_jellyflam3():
    assert inbox_filename(Path("jellyflam3.local.demo.flam3")) == (
        "electricsheep.local.demo.flam3"
    )


def test_inbox_filename_prefixes_plain_stem():
    assert inbox_filename(Path("my_seed.flam3")) == "electricsheep.my_seed.flam3"


def test_select_samples_count(tmp_path: Path):
    pool = [tmp_path / f"s{i}.flam3" for i in range(5)]
    for p in pool:
        p.write_text("<flame/>", encoding="utf-8")
    picked = select_samples(pool, 2, all_samples=False)
    assert len(picked) == 2
    assert set(picked).issubset(set(pool))


def test_stage_file_copy_and_skip(tmp_path: Path):
    inbox = tmp_path / "inbox"
    src = tmp_path / "electricsheep.247.00505.flam3"
    src.write_text("<flame nick=\"demo\"/>", encoding="utf-8")
    dest = stage_file(src, inbox)
    assert dest is not None
    assert dest.is_file()
    assert dest.name == "electricsheep.247.00505.flam3"
    assert stage_file(src, inbox) is None  # already present
    dest2 = stage_file(src, inbox, force=True)
    assert dest2 == dest


def test_run_samples_dry_run(tmp_path: Path):
    samples = tmp_path / "genomes" / "samples"
    samples.mkdir(parents=True)
    seed = samples / "electricsheep.244.00128.flam3"
    seed.write_text("<flame/>", encoding="utf-8")
    inbox = tmp_path / "genomes" / "inbox"
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": str(inbox),
            "media_library": str(tmp_path / "media"),
            "template": str(tmp_path / "missing.flam3"),
        },
        "tools": {"flam3_genome": "flam3-genome"},
    }
    staged = run(cfg, use_samples=True, all_samples=True, dry_run=True)
    assert len(staged) == 1
    assert staged[0].name == "electricsheep.244.00128.flam3"
    assert not inbox.exists()


def test_run_samples_skips_catalog_by_default(tmp_path: Path):
    samples = tmp_path / "genomes" / "samples"
    samples.mkdir(parents=True)
    seed = samples / "electricsheep.244.00128.flam3"
    seed.write_text("<flame/>", encoding="utf-8")
    media = tmp_path / "media"
    dest = media / "by-generation" / "244" / "electricsheep.244.00128.mp4"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"x")
    inbox = tmp_path / "genomes" / "inbox"
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": str(inbox),
            "media_library": str(media),
            "template": str(tmp_path / "missing.flam3"),
        },
        "tools": {"flam3_genome": "flam3-genome"},
    }
    assert run(cfg, use_samples=True, all_samples=True, dry_run=True) == []
    restage = run(cfg, use_samples=True, all_samples=True, dry_run=True, skip_catalog=False)
    assert len(restage) == 1
    assert restage[0].name == "electricsheep.244.00128.flam3"


def test_catalog_mp4_exists(tmp_path: Path):
    media = tmp_path / "media"
    dest = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"x")
    cfg = {"_repo_root": str(tmp_path), "paths": {"media_library": str(media)}}
    assert catalog_mp4_exists(cfg, "electricsheep.247.00505.flam3")
    assert not catalog_mp4_exists(cfg, "electricsheep.247.99999.flam3")


def test_sample_pool_finds_genomes_samples_only():
    root = Path(__file__).resolve().parents[1]
    pool = sample_pool(root)
    assert pool, "expected genomes/samples feedstock"
    assert any(re.search(r"electricsheep\.\d+\.\d+", p.name) for p in pool)
    assert all("genomes" in str(p).replace("\\", "/") and "/samples/" in str(p).replace("\\", "/") for p in pool)
    assert not any("electricsheep.smoke." in p.name for p in pool)
    assert not any("electricsheep.tv." in p.name for p in pool)
    assert not any("configs/templates" in str(p).replace("\\", "/") for p in pool)


def test_cli_help_documents_skip_catalog_default():
    out = StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit) as ei:
        main(["-h"])
    help_text = out.getvalue()
    assert ei.value.code == 0
    assert "--skip-catalog" in help_text
    assert "--no-skip-catalog" in help_text
    assert "default: on" in help_text

