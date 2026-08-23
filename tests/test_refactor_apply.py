"""Pathway B tests for sheep refactor apply (stage inbox; no encode wait)."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.refactor import run_apply


def _cfg(tmp: Path) -> dict:
    media = tmp / "media"
    (media / "by-generation" / "247").mkdir(parents=True)
    done = tmp / "genomes" / "done"
    done.mkdir(parents=True)
    inbox = tmp / "genomes" / "inbox"
    inbox.mkdir(parents=True)
    return {
        "_repo_root": str(tmp),
        "paths": {
            "media_library": str(media),
            "genomes_done": str(done),
            "genomes_inbox": str(inbox),
            "genomes_quarantine": str(tmp / "genomes" / "quarantine"),
        },
        "palette": {"mode": "complementary", "seed": "genome_accent"},
        "render": {"target_width": 1920, "target_height": 1080},
        "tools": {},
    }


def _genome_xml() -> str:
    return """<flame name="t" size="800 600" quality="100">
  <xform weight="1" coefs="1 0 0 1 0 0" color="0"/>
  <color index="0" rgb="180 60 40"/>
  <color index="1" rgb="40 80 200"/>
</flame>"""


def test_apply_dry_run_does_not_stage(tmp_path: Path):
    cfg = _cfg(tmp_path)
    stem = "electricsheep.247.00505"
    genome = Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3"
    genome.write_text(_genome_xml(), encoding="utf-8")
    inbox = Path(cfg["paths"]["genomes_inbox"])

    result = run_apply(
        cfg,
        stem,
        dry_run=True,
        palette_mode="complementary",
        palette_seed="#112233",
        reason="lab-check",
        refresh_jellyfin=False,
    )
    assert result.dry_run is True
    assert result.staged is False
    assert "would_stage_inbox" in result.notes
    assert "operator_reason:lab-check" in result.notes
    assert result.palette_after.get("seed_hex")
    assert result.palette_after.get("complement_hex")
    assert list(inbox.glob("*.flam3")) == []


def test_apply_stages_inbox_and_discards_preview(tmp_path: Path):
    cfg = _cfg(tmp_path)
    stem = "electricsheep.247.00505"
    genome = Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3"
    genome.write_text(_genome_xml(), encoding="utf-8")
    preview = Path(cfg["paths"]["media_library"]) / "_refactor-preview" / stem
    preview.mkdir(parents=True)
    (preview / f"{stem}.flam3").write_text("preview", encoding="utf-8")

    staged_paths: list[Path] = []

    def fake_stage(_cfg, src: Path, *, dry_run: bool = False, force: bool = True):
        inbox = Path(_cfg["paths"]["genomes_inbox"])
        dest = inbox / src.name
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        staged_paths.append(dest)
        return dest

    result = run_apply(
        cfg,
        stem,
        dry_run=False,
        palette_mode="split_complementary",
        reason="neon-fix",
        discard_preview_dir=True,
        refresh_jellyfin=True,
        stage_fn=fake_stage,
        refresh_fn=lambda _c: {"ok": True, "status": "stub"},
    )
    assert result.dry_run is False
    assert result.staged is True
    assert result.preview_discarded is True
    assert not preview.exists()
    assert staged_paths and staged_paths[0].is_file()
    assert "size=\"1920 1080\"" in staged_paths[0].read_text(encoding="utf-8")
    assert result.jellyfin.get("status") == "stub"
    assert "furnace_async_via_worker" in result.notes
    pending = staged_paths[0].with_name(f"{staged_paths[0].stem}.refactor.json")
    assert pending.is_file()
    assert "refactor_pending_written" in result.notes
    assert result.refactor_history is not None
    assert result.refactor_history["palette"]["mode"] == "split_complementary"
    assert "neon-fix" in result.refactor_history["reason"]


def test_apply_appends_catalog_sidecar_history(tmp_path: Path):
    cfg = _cfg(tmp_path)
    stem = "electricsheep.247.00505"
    genome = Path(cfg["paths"]["genomes_done"]) / f"{stem}.flam3"
    genome.write_text(_genome_xml(), encoding="utf-8")
    mp4 = (
        Path(cfg["paths"]["media_library"])
        / "by-generation"
        / "247"
        / f"{stem}.mp4"
    )
    mp4.write_bytes(b"fake")
    side = mp4.with_suffix(".jellyflam3.json")
    side.write_text(
        json.dumps({"id": stem, "duration_sec": 12.0, "refactor": []}),
        encoding="utf-8",
    )

    def fake_stage(_cfg, src: Path, *, dry_run: bool = False, force: bool = True):
        inbox = Path(_cfg["paths"]["genomes_inbox"])
        dest = inbox / src.name
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return dest

    result = run_apply(
        cfg,
        stem,
        dry_run=False,
        palette_mode="complementary",
        reason="lab-history",
        discard_preview_dir=False,
        refresh_jellyfin=False,
        stage_fn=fake_stage,
    )
    assert "catalog_sidecar_history_appended" in result.notes
    data = json.loads(side.read_text(encoding="utf-8"))
    assert isinstance(data.get("refactor"), list) and data["refactor"]
    entry = data["refactor"][-1]
    assert entry["before"]["palette"]
    assert entry["after"]["palette"]
    assert entry["palette"]["mode"] == "complementary"
    assert "lab-history" in entry["reason"]
    assert entry["status"] == "staged"


def test_merge_pending_refactor_into_sidecar(tmp_path: Path):
    from pipeline.refactor import (
        merge_pending_refactor_into_sidecar,
        write_refactor_pending,
        build_refactor_history_entry,
    )

    stem = "electricsheep.247.00505"
    media = tmp_path / "media" / "by-generation" / "247"
    media.mkdir(parents=True)
    mp4 = media / f"{stem}.mp4"
    mp4.write_bytes(b"x")
    side = mp4.with_suffix(".jellyflam3.json")
    prior_entry = build_refactor_history_entry(
        reason="old",
        palette_before={"mode": "off"},
        palette_after={"mode": "complementary", "seed_hex": "#111111"},
        status="ingested",
        ts="2026-01-01T00:00:00Z",
    )
    same_ts = "2026-08-22T01:00:00Z"
    staged = build_refactor_history_entry(
        reason="fresh",
        score=12.0,
        palette_before={"mode": "complementary", "seed_hex": "#aaaaaa"},
        palette_after={"mode": "complementary", "seed_hex": "#bbbbbb"},
        status="staged",
        ts=same_ts,
    )
    side.write_text(
        json.dumps({"id": stem, "refactor": [prior_entry, staged]}, indent=2),
        encoding="utf-8",
    )
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    flam3 = inbox / f"{stem}.flam3"
    flam3.write_text("<flame/>", encoding="utf-8")
    write_refactor_pending(flam3, staged)

    sidecar: dict = {"id": stem, "duration_sec": 10.0}
    merge_pending_refactor_into_sidecar(
        sidecar, catalog_mp4=mp4, inbox_flam3=flam3
    )
    assert not flam3.with_name(f"{stem}.refactor.json").exists()
    hist = sidecar["refactor"]
    assert len(hist) == 2
    assert hist[0]["reason"] == ["old"]
    assert hist[1]["ts"] == same_ts
    assert hist[1]["status"] == "ingested"
    assert hist[1]["palette"]["seed_hex"] == "#bbbbbb"


def test_apply_requires_genome(tmp_path: Path):
    cfg = _cfg(tmp_path)
    try:
        run_apply(cfg, "electricsheep.247.99999", dry_run=True, refresh_jellyfin=False)
        raised = False
    except FileNotFoundError:
        raised = True
    assert raised
