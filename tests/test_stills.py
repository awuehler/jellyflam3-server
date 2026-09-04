import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.stills import (
    SIDECAR_RESERVED_KEYS,
    extract_stills_for_mp4,
    frame_path,
    load_sidecar,
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
