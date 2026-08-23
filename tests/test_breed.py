"""Unit tests for pipeline.breed (guide 07 task 1)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from pipeline.breed import (
    breed_cross,
    breed_mutate,
    inherit_license_tags,
    pedigree_name,
    prepare_parent,
    write_pedigree_sidecar,
)


def _simple_flame(name: str = "p") -> str:
    return (
        f'<flame name="{name}" size="800 600" scale="600">'
        f'<xform weight="1" coefs="1 0 0 1 0 0"/>'
        f"</flame>"
    )


def _cfg(tmp_path: Path, **breed_overrides) -> dict:
    inbox = tmp_path / "genomes" / "inbox"
    inbox.mkdir(parents=True)
    (tmp_path / "configs").mkdir(exist_ok=True)
    template = tmp_path / "configs" / "tv.flam3"
    template.write_text(_simple_flame("tpl"), encoding="utf-8")
    breed = {
        "tax_parents": True,
        "multi_flame": "strip_to_first",
        "default_cross_method": "alternate",
    }
    breed.update(breed_overrides)
    return {
        "_repo_root": str(tmp_path),
        "paths": {
            "genomes_inbox": "genomes/inbox",
            "genomes_done": "genomes/done",
            "template": "configs/tv.flam3",
        },
        "tools": {"flam3_genome": "flam3-genome"},
        "sheep_tax": {"enabled": True, "repair": True, "multi_flame": "strip_to_first"},
        "breed": breed,
    }


def test_pedigree_name():
    assert pedigree_name("mutate", "abc12def") == (
        "electricsheep.pedigree.mutate.abc12def.flam3"
    )
    assert pedigree_name("cross", "x").startswith("electricsheep.pedigree.cross.")


def test_inherit_license_human_forces_nc(tmp_path: Path):
    p = tmp_path / "electricsheep.247.00505.flam3"
    p.write_text(
        '<flame nick="alice" size="100 100" scale="100">'
        '<xform weight="1" coefs="1 0 0 1 0 0"/></flame>',
        encoding="utf-8",
    )
    tags = inherit_license_tags([p])
    assert "cc-by-nc" in tags
    assert "cc-by" not in tags


def test_prepare_parent_strips_multi_flame(tmp_path: Path):
    cfg = _cfg(tmp_path)
    parent = tmp_path / "multi.flam3"
    parent.write_text(
        _simple_flame("a") + _simple_flame("b"),
        encoding="utf-8",
    )
    prep = prepare_parent(parent, cfg, tmp_path / "work")
    text = prep.read_text(encoding="utf-8")
    assert text.count("<flame") == 1


def test_breed_mutate_stages_and_sidecar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = _cfg(tmp_path)
    parent = tmp_path / "parent.flam3"
    parent.write_text(_simple_flame("parent"), encoding="utf-8")

    def fake_run(cmd, check, stdout, env):
        assert "mutate" in env
        stdout.write(_simple_flame("child"))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("pipeline.breed.subprocess.run", fake_run)
    paths = breed_mutate(cfg, parent, count=1)
    assert len(paths) == 1
    dest = paths[0]
    assert dest.name.startswith("electricsheep.pedigree.mutate.")
    assert dest.is_file()
    side = json.loads(dest.with_suffix(".jellyflam3.json").read_text(encoding="utf-8"))
    assert side["origin"] == "local_pedigree"
    assert side["method"] == "mutate"
    assert str(parent.resolve()) in side["parents"]


def test_breed_cross_uses_alternate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = _cfg(tmp_path)
    a = tmp_path / "a.flam3"
    b = tmp_path / "b.flam3"
    a.write_text(_simple_flame("a"), encoding="utf-8")
    b.write_text(_simple_flame("b"), encoding="utf-8")

    def fake_run(cmd, check, stdout, env):
        assert env.get("cross0")
        assert env.get("cross1")
        assert env.get("method") == "alternate"
        stdout.write(_simple_flame("child"))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("pipeline.breed.subprocess.run", fake_run)
    dest = breed_cross(cfg, a, b, method="alternate", mode_label="cross")
    assert dest.name.startswith("electricsheep.pedigree.cross.")
    side = json.loads(dest.with_suffix(".jellyflam3.json").read_text(encoding="utf-8"))
    assert side["method"] == "cross"
    assert side["cross_method"] == "alternate"
    assert side["origin"] == "local_pedigree"


def test_breed_interpolate_label(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = _cfg(tmp_path)
    a = tmp_path / "a.flam3"
    b = tmp_path / "b.flam3"
    a.write_text(_simple_flame("a"), encoding="utf-8")
    b.write_text(_simple_flame("b"), encoding="utf-8")

    def fake_run(cmd, check, stdout, env):
        assert env.get("method") == "interpolate"
        stdout.write(_simple_flame("child"))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("pipeline.breed.subprocess.run", fake_run)
    dest = breed_cross(
        cfg, a, b, method="interpolate", mode_label="interpolate"
    )
    assert dest.name.startswith("electricsheep.pedigree.interpolate.")


def test_write_pedigree_sidecar(tmp_path: Path):
    flam = tmp_path / "electricsheep.pedigree.mutate.abcd1234.flam3"
    flam.write_text(_simple_flame(), encoding="utf-8")
    path = write_pedigree_sidecar(
        flam,
        method="mutate",
        parents=[tmp_path / "p.flam3"],
        tags=["cc-by-nc", "brood"],
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["id"] == flam.stem
    assert data["origin"] == "local_pedigree"
