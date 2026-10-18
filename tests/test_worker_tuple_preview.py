"""Tuple saturation still uses one flame; sequence= keeps both control points."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from pipeline.sheep_tuple import combine_parent_genomes
from pipeline.worker import process_genome

ORBITABLE = """<flame name="t" size="1920 1080" rotate="90">
  <xform weight="1" animate="1" spherical="1" coefs="1 0 0 1 0 0" />
</flame>"""


def _cfg(tmp_path: Path) -> dict:
    paths = {}
    for name in (
        "genomes_inbox",
        "jobs_dir",
        "frames_scratch",
        "media_library",
        "genomes_quarantine",
        "genomes_done",
    ):
        dest = tmp_path / name
        dest.mkdir()
        paths[name] = str(dest)
    paths["template"] = str(tmp_path / "missing-template.flam3")
    return {
        "_repo_root": str(tmp_path),
        "paths": paths,
        "render": {"free_space_gb_min": 0, "edition": "off", "target_width": 1920, "target_height": 1080},
        "palette": {"mode": "off"},
        "vod": {
            "fps": 24,
            "min_duration_sec": 11,
            "max_duration_sec": 31,
            "max_duration_sec_hard": 60,
            "allow_bypass_max": True,
        },
        "tuple": {"enabled": True, "stage_duration_sec": 13, "watermark_on_edge": False},
        "watermark": {"enabled": False},
        "idle_gate": {"enabled": False},
        "library_disk": {"worker_refuse_on_sheep_bad": False},
        "quality_gate": {"enabled": True, "check_preview_saturation": True},
        "sheep_tax": {"enabled": True, "on_worker_ingest": True, "multi_flame": "strip_to_first"},
    }


def test_tuple_preview_is_single_root_and_sequence_keeps_both(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cfg = _cfg(tmp_path)
    inbox = Path(cfg["paths"]["genomes_inbox"])
    src = inbox / "electricsheep.tuple.243.14985_to_243.17305.flam3"
    src.write_text(
        combine_parent_genomes(
            ORBITABLE,
            ORBITABLE.replace('name="t"', 'name="u"'),
            from_stem="electricsheep.243.14985",
            to_stem="electricsheep.243.17305",
        ),
        encoding="utf-8",
    )
    seen: dict[str, str] = {}

    def fake_still(_cfg, genome, dest_png):
        seen["preview"] = Path(genome).read_text(encoding="utf-8")
        seen["preview_name"] = Path(genome).name
        Image.new("RGB", (32, 32), (255, 0, 0)).save(dest_png)
        return Path(dest_png)

    def fake_run(argv, check=True, env=None, stdout=None, cwd=None, **_kwargs):
        seen["argv"] = " ".join(str(part) for part in argv)
        seen["sequence"] = str((env or {}).get("sequence") or "")
        raise RuntimeError("stop-after-sequence")

    monkeypatch.setattr("pipeline.worker.render_lite_still", fake_still)
    monkeypatch.setattr("pipeline.worker.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="stop-after-sequence"):
        process_genome(cfg, src)

    preview_root = ET.fromstring(seen["preview"])
    assert preview_root.tag == "flame"
    assert seen["preview"].count("<flame") == 1
    assert seen["preview_name"] == "quality_preview_flame.flam3"
    assert "243.17305" not in seen["preview"]
    assert seen["argv"] == "flam3-genome"
    sequence = Path(seen["sequence"])
    assert sequence.name == "sequence_input.flam3"
    sequence_root = ET.fromstring(sequence.read_text(encoding="utf-8"))
    assert sequence_root.tag == "flames"
    assert [el.get("name") for el in sequence_root if el.tag == "flame"] == [
        "electricsheep.243.14985",
        "electricsheep.243.17305",
    ]
    optimized = sequence.parent / "tv_optimized.flam3"
    assert optimized.read_text(encoding="utf-8").count("<flame") == 2
