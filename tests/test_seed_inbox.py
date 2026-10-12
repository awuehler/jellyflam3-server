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
    assert "--sheep" in help_text
    assert "--from-file" in help_text
    assert "default: on" in help_text


def _named_cfg(tmp_path: Path) -> dict:
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    return {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": str(inbox),
            "media_library": str(tmp_path / "media"),
            "inbox_fifo_file": str(tmp_path / "inbox_fifo.json"),
        },
        "sheep_tax": {"enabled": False},
    }


def _fake_materialize(monkeypatch: pytest.MonkeyPatch, root: Path):
    calls: list[str] = []

    def fake(sheep, cfg, tv_port=True, use_cache=True):
        calls.append(sheep.filename)
        path = root / "cache" / sheep.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"<flame name=\"{sheep.name}\"/>", encoding="utf-8")
        return path

    monkeypatch.setattr("pipeline.seed_inbox.materialize_sheep", fake)
    return calls


def test_named_archive_appends_behind_existing_fifo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from pipeline.inbox_queue import stamp_inbox_arrival, sync_inbox_fifo
    from pipeline.seed_inbox import stage_named_archive

    cfg = _named_cfg(tmp_path)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    ledger = Path(cfg["paths"]["inbox_fifo_file"])
    waiting = inbox / "electricsheep.pedigree.mutate.aaaaaaaa.flam3"
    waiting.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(waiting)
    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == [waiting.name]

    calls = _fake_materialize(monkeypatch, tmp_path)
    report = stage_named_archive(cfg, ["247.00505", "245.61"])
    assert calls == ["electricsheep.247.00505.flam3", "electricsheep.245.00061.flam3"]
    assert [p.name for p in report.staged] == calls
    queued = [p.name for p in sync_inbox_fifo(inbox, ledger)]
    assert queued == [
        waiting.name,
        "electricsheep.247.00505.flam3",
        "electricsheep.245.00061.flam3",
    ]
    assert report.failed == []


def test_named_archive_file_follows_sheep_list_and_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from pipeline.seed_inbox import collect_sheep_tokens, stage_named_archive

    cfg = _named_cfg(tmp_path)
    media = Path(cfg["paths"]["media_library"])
    catalog = media / "by-generation" / "243" / "electricsheep.243.16930.mp4"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(b"x")
    inbox = Path(cfg["paths"]["genomes_inbox"])
    (inbox / "electricsheep.242.00100.flam3").write_text("<flame/>", encoding="utf-8")
    listing = tmp_path / "sheep.txt"
    listing.write_text(
        "# night batch\n\n243.16930\n242.100, 244.00007\n",
        encoding="utf-8",
    )
    tokens = collect_sheep_tokens(["247.505, 247.00505"], listing)
    assert tokens == ["247.505", "247.00505", "243.16930", "242.100", "244.00007"]
    calls = _fake_materialize(monkeypatch, tmp_path)
    report = stage_named_archive(cfg, tokens)
    assert calls == ["electricsheep.247.00505.flam3", "electricsheep.244.00007.flam3"]
    assert [p.name for p in report.staged] == calls
    assert ("electricsheep.247.00505.flam3", "duplicate in this request") in report.skipped
    assert ("electricsheep.243.16930.flam3", "catalog exists") in report.skipped
    assert ("electricsheep.242.00100.flam3", "already in inbox") in report.skipped
    assert collect_sheep_tokens(["247.00505", "245.61"]) == ["247.00505", "245.61"]


def test_named_archive_force_keeps_fifo_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from pipeline.inbox_queue import stamp_inbox_arrival, sync_inbox_fifo
    from pipeline.seed_inbox import stage_named_archive

    cfg = _named_cfg(tmp_path)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    ledger = Path(cfg["paths"]["inbox_fifo_file"])
    dest = inbox / "electricsheep.247.00505.flam3"
    dest.write_text("<flame old=\"1\"/>", encoding="utf-8")
    later = inbox / "electricsheep.245.00061.flam3"
    later.write_text("<flame/>", encoding="utf-8")
    stamp_inbox_arrival(dest)
    stamp_inbox_arrival(later)
    before = dest.stat()
    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == [dest.name, later.name]
    _fake_materialize(monkeypatch, tmp_path)
    report = stage_named_archive(cfg, ["247.00505"], force=True)
    assert [p.name for p in report.staged] == [dest.name]
    after = dest.stat()
    assert (after.st_dev, after.st_ino) == (before.st_dev, before.st_ino)
    assert "old" not in dest.read_text(encoding="utf-8")
    assert [p.name for p in sync_inbox_fifo(inbox, ledger)] == [dest.name, later.name]


def test_named_archive_no_skip_catalog_fetches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from pipeline.seed_inbox import stage_named_archive

    cfg = _named_cfg(tmp_path)
    media = Path(cfg["paths"]["media_library"])
    catalog = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    catalog.parent.mkdir(parents=True)
    catalog.write_bytes(b"x")
    calls = _fake_materialize(monkeypatch, tmp_path)
    skipped = stage_named_archive(cfg, ["247.00505"])
    assert calls == []
    assert skipped.skipped == [("electricsheep.247.00505.flam3", "catalog exists")]
    fetched = stage_named_archive(cfg, ["247.00505"], skip_catalog=False)
    assert calls == ["electricsheep.247.00505.flam3"]
    assert [p.name for p in fetched.staged] == calls


def test_named_archive_dry_run_does_not_fetch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from pipeline.seed_inbox import stage_named_archive

    cfg = _named_cfg(tmp_path)

    def boom(*_a, **_k):
        raise AssertionError("dry-run must not fetch")

    monkeypatch.setattr("pipeline.seed_inbox.materialize_sheep", boom)
    report = stage_named_archive(cfg, ["247.00505", "no-such"], dry_run=True)
    assert [p.name for p in report.staged] == ["electricsheep.247.00505.flam3"]
    assert not report.staged[0].exists()
    assert len(report.failed) == 1
    assert report.failed[0][0] == "no-such"


def test_named_archive_fetch_failure_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from pipeline.seed_inbox import stage_named_archive

    cfg = _named_cfg(tmp_path)

    def fake(sheep, cfg, tv_port=True, use_cache=True):
        if sheep.sheep_id == 505:
            raise RuntimeError("mirror down")
        path = tmp_path / sheep.filename
        path.write_text("<flame/>", encoding="utf-8")
        return path

    monkeypatch.setattr("pipeline.seed_inbox.materialize_sheep", fake)
    report = stage_named_archive(cfg, ["247.505", "245.00061"])
    assert [p.name for p in report.staged] == ["electricsheep.245.00061.flam3"]
    assert report.failed[0][0] == "electricsheep.247.00505.flam3"
    assert "mirror down" in report.failed[0][1]


def test_main_named_sheep_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    inbox = tmp_path / "genomes" / "inbox"
    media = tmp_path / "media"
    (cfg_dir / "jellyflam3.yaml").write_text(
        "paths:\n"
        f"  genomes_inbox: {inbox.as_posix()}\n"
        f"  media_library: {media.as_posix()}\n"
        f"  inbox_fifo_file: {(tmp_path / 'inbox_fifo.json').as_posix()}\n"
        "sheep_tax:\n"
        "  enabled: false\n",
        encoding="utf-8",
    )
    listing = tmp_path / "sheep.txt"
    listing.write_text("# only a comment\n\n", encoding="utf-8")

    def fake(sheep, cfg, tv_port=True, use_cache=True):
        if sheep.sheep_id == 1:
            raise RuntimeError("missing")
        path = tmp_path / "cache" / sheep.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<flame/>", encoding="utf-8")
        return path

    monkeypatch.setattr("pipeline.seed_inbox.materialize_sheep", fake)
    config = str(cfg_dir / "jellyflam3.yaml")
    with pytest.raises(SystemExit) as empty:
        main(["--config", config, "--from-file", str(listing)])
    assert empty.value.code == 2

    code = main(["--config", config, "--sheep", "247.00001,245.00061"])
    captured = capsys.readouterr().out
    assert code == 1
    assert "fail electricsheep.247.00001.flam3" in captured
    assert "staged" in captured
    assert (inbox / "electricsheep.245.00061.flam3").is_file()
    assert not (inbox / "electricsheep.247.00001.flam3").exists()


def test_main_missing_list_and_named_before_archive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    cfg_dir = tmp_path / "configs"
    cfg_dir.mkdir()
    inbox = tmp_path / "genomes" / "inbox"
    (cfg_dir / "jellyflam3.yaml").write_text(
        "paths:\n"
        f"  genomes_inbox: {inbox.as_posix()}\n"
        f"  media_library: {(tmp_path / 'media').as_posix()}\n"
        "sheep_tax:\n"
        "  enabled: false\n",
        encoding="utf-8",
    )
    config = str(cfg_dir / "jellyflam3.yaml")
    with pytest.raises(SystemExit) as missing:
        main(["--config", config, "--from-file", str(tmp_path / "missing.txt")])
    assert "sheep list not found" in str(missing.value)

    order: list[str] = []

    def fake_named(cfg, tokens, **kwargs):
        from pipeline.seed_inbox import NamedArchiveReport

        order.append("named")
        report = NamedArchiveReport()
        report.staged.append(inbox / "electricsheep.247.00505.flam3")
        return report

    def fake_archive(cfg, **kwargs):
        order.append("archive")
        return [inbox / "electricsheep.245.00061.flam3"]

    monkeypatch.setattr("pipeline.seed_inbox.stage_named_archive", fake_named)
    monkeypatch.setattr("pipeline.seed_inbox.stage_archive", fake_archive)
    code = main(
        ["--config", config, "--sheep", "247.00505", "--archive", "--fetch-count", "1", "--dry-run"]
    )
    captured = capsys.readouterr().out
    assert code == 0
    assert order == ["named", "archive"]
    named_at = captured.index("electricsheep.247.00505.flam3")
    archive_at = captured.index("electricsheep.245.00061.flam3")
    assert named_at < archive_at

