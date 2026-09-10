import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.stills import (
    SIDECAR_RESERVED_KEYS,
    extract_stills_for_mp4,
    frame_path,
    iter_catalog_mp4s,
    load_sidecar,
    merge_reserved_sidecar_keys,
    seek_points_sec,
    stills_dir_for_mp4,
    write_sidecar,
)

# Keep in lockstep with docs/phase1/07_LICENSE_AND_METADATA.md reserved table.
_EXPECTED_RESERVED = frozenset(
    {
        "type",
        "from_id",
        "to_id",
        "watermark",
        "viewer_feedback",
        "alias",
        "alias_source",
    }
)


def test_seek_points_sec_midpoints():
    pts = seek_points_sec(40.0, 4)
    assert pts == [5.0, 15.0, 25.0, 35.0]


def test_stills_dir_layout():
    media = Path("/media/sheep")
    mp4 = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    assert stills_dir_for_mp4(media, mp4) == media / "by-generation" / "247" / "stills" / "electricsheep.247.00505"


def test_iter_catalog_mp4s_skips_tuples_and_edges(tmp_path: Path):
    media = tmp_path / "media"
    gen = media / "by-generation" / "247"
    gen.mkdir(parents=True)
    (media / "by-generation" / "tuple").mkdir(parents=True)
    (gen / "edges").mkdir(parents=True)
    loop = gen / "electricsheep.247.00505.mp4"
    ped = media / "by-generation" / "pedigree"
    ped.mkdir(parents=True)
    pedigree = ped / "electricsheep.pedigree.mutate.abc.mp4"
    tup = media / "by-generation" / "tuple" / "electricsheep.tuple.a_to_b.mp4"
    edge = gen / "edges" / "edge.mp4"
    for p in (loop, pedigree, tup, edge):
        p.write_bytes(b"x")
    names = {p.name for p in iter_catalog_mp4s(media, skip_tuples=True)}
    assert names == {
        "electricsheep.247.00505.mp4",
        "electricsheep.pedigree.mutate.abc.mp4",
    }


def test_extract_stills_skips_tuple(tmp_path: Path):
    media = tmp_path / "media"
    tup_dir = media / "by-generation" / "tuple"
    tup_dir.mkdir(parents=True)
    mp4 = tup_dir / "electricsheep.tuple.a_to_b.mp4"
    mp4.write_bytes(b"fake-mp4")
    write_sidecar(mp4, {"id": mp4.stem, "type": "tuple"})
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {"media_library": str(media), "status_file": str(tmp_path / "status.json")},
        "stills": {"enabled": True, "count": 4, "jpeg_quality": 2, "respect_idle_gate": False},
        "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
    }
    with patch("pipeline.stills.subprocess.run") as run:
        out = extract_stills_for_mp4(cfg, mp4, force=True)
    run.assert_not_called()
    assert out["status"] == "skipped_tuple"
    assert out["screensaver_safe"] is False
    dest = stills_dir_for_mp4(media, mp4)
    assert not dest.exists()


def test_extract_stills_writes_frames(tmp_path: Path):
    media = tmp_path / "media"
    gen = media / "by-generation" / "247"
    gen.mkdir(parents=True)
    mp4 = gen / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake-mp4")
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {"media_library": str(media), "status_file": str(tmp_path / "status.json")},
        "stills": {"enabled": True, "count": 3, "jpeg_quality": 2, "respect_idle_gate": False},
        "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
    }

    def _fake_run(cmd, check=True, capture_output=True):  # noqa: ARG001
        Path(cmd[-1]).write_bytes(b"\xff\xd8\xfffakejpeg")
        return MagicMock(returncode=0)

    with patch("pipeline.stills.subprocess.run", side_effect=_fake_run):
        with patch("pipeline.stills.probe_duration_sec", return_value=30.0):
            out = extract_stills_for_mp4(cfg, mp4, force=True)

    assert out["ok"] is True
    assert out["count"] == 3
    dest = stills_dir_for_mp4(media, mp4)
    assert frame_path(dest, 0).is_file()
    assert frame_path(dest, 2).is_file()
    side = mp4.with_suffix(".jellyflam3.json")
    assert side.is_file()
    assert "screensaver_safe" in side.read_text(encoding="utf-8")


def test_sidecar_reserved_keys_match_schema():
    assert SIDECAR_RESERVED_KEYS == _EXPECTED_RESERVED


def test_load_write_preserves_phase4_reserved_keys(tmp_path: Path):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    payload = {
        "id": mp4.stem,
        "license": "cc-by",
        "type": "loop",
        "from_id": None,
        "to_id": None,
        "watermark": {"enabled": False, "style": "corner", "text": ""},
        "viewer_feedback": {
            "likes": 0,
            "loves": 0,
            "votes": 0,
            "last_voted_at": None,
            "share_candidate": False,
        },
        "alias": "frosty_swirles",
        "alias_source": "auto",
    }
    write_sidecar(mp4, payload)
    loaded = load_sidecar(mp4)
    for key in ("type", "watermark", "viewer_feedback", "alias"):
        assert loaded[key] == payload[key]
    assert loaded["alias_source"] == "auto"
    assert loaded["license"] == "cc-by"


def test_extract_stills_preserves_reserved_keys(tmp_path: Path):
    media = tmp_path / "media"
    gen = media / "by-generation" / "247"
    gen.mkdir(parents=True)
    mp4 = gen / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake-mp4")
    write_sidecar(
        mp4,
        {
            "id": mp4.stem,
            "duration_sec": 30.0,
            "type": "loop",
            "watermark": {"enabled": False, "style": "corner", "text": ""},
            "viewer_feedback": {"likes": 1, "share_candidate": True},
            "alias": "frosty_swirles",
            "alias_source": "human",
        },
    )
    cfg = {
        "_repo_root": str(tmp_path),
        "paths": {"media_library": str(media), "status_file": str(tmp_path / "status.json")},
        "stills": {"enabled": True, "count": 2, "jpeg_quality": 2, "respect_idle_gate": False},
        "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
    }

    def _fake_run(cmd, check=True, capture_output=True):  # noqa: ARG001
        Path(cmd[-1]).write_bytes(b"\xff\xd8\xfffakejpeg")
        return MagicMock(returncode=0)

    with patch("pipeline.stills.subprocess.run", side_effect=_fake_run):
        out = extract_stills_for_mp4(cfg, mp4, force=True)

    assert out["ok"] is True
    loaded = load_sidecar(mp4)
    assert loaded["type"] == "loop"
    assert loaded["alias"] == "frosty_swirles"
    assert loaded["alias_source"] == "human"
    assert loaded["viewer_feedback"]["share_candidate"] is True
    assert loaded["stills"]["screensaver_safe"] is True


def test_merge_reserved_loop_keeps_alias_and_votes():
    sidecar = {
        "id": "electricsheep.247.00505",
        "license": "cc-by",
        "nframes": 312,
    }
    prior = {
        "id": "electricsheep.247.00505",
        "license": "cc-by-nc",
        "type": "loop",
        "viewer_feedback": {"likes": 3, "loves": 1, "votes": 4, "share_candidate": True},
        "alias": "frosty_swirles",
        "alias_source": "human",
        "duration_sec": 13.0,
    }
    merge_reserved_sidecar_keys(sidecar, prior)
    assert sidecar["alias"] == "frosty_swirles"
    assert sidecar["alias_source"] == "human"
    assert sidecar["viewer_feedback"]["likes"] == 3
    assert sidecar["type"] == "loop"
    assert sidecar["license"] == "cc-by"
    assert "duration_sec" not in sidecar


def test_merge_reserved_tuple_overwrites_watermark_keeps_votes():
    sidecar = {
        "id": "electricsheep.tuple.a_to_b",
        "type": "tuple",
        "from_id": "a",
        "to_id": "b",
        "watermark": {"enabled": True, "style": "text", "text": "Electric Sheep", "image": ""},
    }
    prior = {
        "type": "tuple",
        "from_id": "old_a",
        "to_id": "old_b",
        "watermark": {"enabled": True, "style": "image", "text": "", "image": "old.png"},
        "viewer_feedback": {"votes": 9, "share_candidate": False},
        "alias": "angry_bardeen",
        "alias_source": "auto",
    }
    merge_reserved_sidecar_keys(sidecar, prior)
    assert sidecar["type"] == "tuple"
    assert sidecar["from_id"] == "a"
    assert sidecar["to_id"] == "b"
    assert sidecar["watermark"]["style"] == "text"
    assert sidecar["watermark"]["image"] == ""
    assert sidecar["alias"] == "angry_bardeen"
    assert sidecar["viewer_feedback"]["votes"] == 9


def test_merge_reserved_skips_missing_prior():
    sidecar = {"id": "x", "license": "cc-by"}
    merge_reserved_sidecar_keys(sidecar, None)
    merge_reserved_sidecar_keys(sidecar, {})
    assert sidecar == {"id": "x", "license": "cc-by"}


def test_worker_merges_reserved_sidecar_keys():
    text = (
        Path(__file__).resolve().parents[1].joinpath("pipeline", "worker.py").read_text(
            encoding="utf-8"
        )
    )
    assert "merge_reserved_sidecar_keys" in text
    assert "load_sidecar(dest)" in text
    assert "ensure_auto_alias" in text


def test_worker_does_not_write_reserved_phase4_keys():
    tree = ast.parse(
        Path(__file__).resolve().parents[1].joinpath("pipeline", "worker.py").read_text(
            encoding="utf-8"
        )
    )
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.AnnAssign):
            continue
        target = node.target
        if not (isinstance(target, ast.Name) and target.id == "sidecar"):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for k in node.value.keys:
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keys.add(k.value)
        break
    else:
        raise AssertionError("worker sidecar dict literal not found")
    assert not (keys & SIDECAR_RESERVED_KEYS)
