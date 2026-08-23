"""Tests for post-render genome archive (guide 07 parent pool)."""

from __future__ import annotations

from pathlib import Path

from pipeline.worker import archive_rendered_genome, genomes_done_dir


def test_genomes_done_explicit_path(tmp_path: Path):
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": "genomes/inbox",
            "genomes_done": "genomes/done",
        },
    }
    assert genomes_done_dir(cfg) == tmp_path / "genomes" / "done"


def test_genomes_done_fallback_beside_inbox(tmp_path: Path):
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {"genomes_inbox": "genomes/inbox"},
    }
    assert genomes_done_dir(cfg) == tmp_path / "genomes" / "done"


def test_archive_rendered_genome_moves(tmp_path: Path):
    inbox = tmp_path / "genomes" / "inbox"
    inbox.mkdir(parents=True)
    src = inbox / "sheep.flam3"
    src.write_text("<flame/>", encoding="utf-8")
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": "genomes/inbox",
            "genomes_done": "genomes/done",
        },
    }
    dest = archive_rendered_genome(cfg, src)
    assert dest == tmp_path / "genomes" / "done" / "sheep.flam3"
    assert dest.is_file()
    assert not src.exists()


def test_archive_collision_gets_unique_name(tmp_path: Path):
    done = tmp_path / "genomes" / "done"
    done.mkdir(parents=True)
    (done / "sheep.flam3").write_text("old", encoding="utf-8")
    inbox = tmp_path / "genomes" / "inbox"
    inbox.mkdir(parents=True)
    src = inbox / "sheep.flam3"
    src.write_text("new", encoding="utf-8")
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": "genomes/inbox",
            "genomes_done": "genomes/done",
        },
    }
    dest = archive_rendered_genome(cfg, src)
    assert dest.name.startswith("sheep.")
    assert dest.name.endswith(".flam3")
    assert dest.name != "sheep.flam3"
    assert dest.read_text(encoding="utf-8") == "new"
    assert (done / "sheep.flam3").read_text(encoding="utf-8") == "old"
