"""Shears cascade Id matching must not use bare substrings (review P4)."""

from __future__ import annotations

from pathlib import Path

from pipeline.shears import _id_equals_base, _path_refers_to_base, discover_cascade


def test_path_refers_to_base_rejects_prefix_collision():
    base = "electricsheep.247.00505"
    assert _path_refers_to_base(f"{base}.mp4", base)
    assert _path_refers_to_base(f"{base}-poster.jpg", base)
    assert _path_refers_to_base(f"{base}.jellyflam3.json", base)
    assert not _path_refers_to_base("electricsheep.247.005050.mp4", base)
    assert not _path_refers_to_base("electricsheep.247.00505x.mp4", base)


def test_id_equals_base_exact_only():
    base = "electricsheep.247.00505"
    assert _id_equals_base(base, base)
    assert _id_equals_base(f"{base}.flam3", base)
    assert not _id_equals_base("electricsheep.247.005050", base)
    assert not _id_equals_base(f"prefix-{base}", base)


def test_edge_cascade_ignores_prefix_neighbor(tmp_path: Path):
    media = tmp_path / "media"
    edges = media / "by-generation" / "247" / "edges"
    edges.mkdir(parents=True)
    base = "electricsheep.247.00505"
    neighbor = "electricsheep.247.005050"
    (edges / f"{neighbor}.mp4").write_bytes(b"x")
    (edges / f"{base}.mp4").write_bytes(b"y")
    # JSON edge that names the neighbor only — must not attach to base.
    (edges / f"{neighbor}.json").write_text(
        f'{{"from_id": "{neighbor}", "to_id": "electricsheep.247.00001"}}',
        encoding="utf-8",
    )
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {
            "media_library": str(media),
            "genomes_inbox": str(tmp_path / "inbox"),
            "genomes_quarantine": str(tmp_path / "q"),
            "genomes_done": str(tmp_path / "done"),
            "jobs_dir": str(tmp_path / "jobs"),
            "frames_scratch": str(tmp_path / "frames"),
        },
    }
    for d in ("inbox", "q", "done", "jobs", "frames"):
        (tmp_path / d).mkdir()
    report = discover_cascade(cfg, base)
    names = {p.name for p in report.edges}
    assert f"{base}.mp4" in names
    assert f"{neighbor}.mp4" not in names
    assert f"{neighbor}.json" not in names
