from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.media_layout import STILLS_IGNORE_NAME
from pipeline.poster import (
    extract_mid_loop_poster,
    legacy_poster_path_for_mp4,
    mid_loop_seek_sec,
    poster_path_for_mp4,
    relocate_legacy_poster,
    resolve_poster_path,
)


def test_poster_path_for_mp4():
    mp4 = Path("/media/sheep/by-generation/247/electricsheep.247.00505.mp4")
    assert poster_path_for_mp4(mp4) == Path(
        "/media/sheep/by-generation/247/stills/electricsheep.247.00505/"
        "electricsheep.247.00505-poster.jpg"
    )


def test_poster_path_unpublished_stays_sibling():
    mp4 = Path(
        "/media/sheep/_refactor-quarantine/electricsheep.247.00505/"
        "electricsheep.247.00505.mp4"
    )
    assert poster_path_for_mp4(mp4) == Path(
        "/media/sheep/_refactor-quarantine/electricsheep.247.00505/"
        "electricsheep.247.00505-poster.jpg"
    )
    assert poster_path_for_mp4(mp4) == legacy_poster_path_for_mp4(mp4)


def test_mid_loop_seek_sec():
    assert mid_loop_seek_sec(24.0) == 12.0
    assert mid_loop_seek_sec(0) == 0.0
    assert mid_loop_seek_sec(-1) == 0.0


def _fake_ffmpeg_run(cmd, check=True, capture_output=True):  # noqa: ARG001
    Path(cmd[-1]).write_bytes(b"\xff\xd8\xfffakejpeg")
    return MagicMock(returncode=0)


def test_extract_mid_loop_poster_writes_stills_folder(tmp_path: Path):
    mp4 = tmp_path / "media" / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"fake-mp4")
    expected = poster_path_for_mp4(mp4)

    with patch("pipeline.poster.subprocess.run", side_effect=_fake_ffmpeg_run) as run:
        out = extract_mid_loop_poster(
            ffmpeg="ffmpeg",
            mp4=mp4,
            duration_sec=13.0,
        )

    assert out == expected
    assert expected.is_file() and expected.stat().st_size > 0
    assert (expected.parent.parent / STILLS_IGNORE_NAME).is_file()
    cmd = run.call_args.args[0]
    assert cmd[0] == "ffmpeg"
    assert "-ss" in cmd
    assert cmd[cmd.index("-ss") + 1] == "6.500"
    assert cmd[-1] == str(expected)


def test_extract_without_by_generation_uses_local_stills(tmp_path: Path):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake-mp4")
    expected = tmp_path / "stills" / "electricsheep.247.00505" / "electricsheep.247.00505-poster.jpg"

    with patch("pipeline.poster.subprocess.run", side_effect=_fake_ffmpeg_run):
        out = extract_mid_loop_poster(
            ffmpeg="ffmpeg",
            mp4=mp4,
            duration_sec=13.0,
        )

    assert out == expected
    assert expected.is_file()
    assert (expected.parent.parent / STILLS_IGNORE_NAME).is_file()


def test_relocate_legacy_poster_into_stills(tmp_path: Path):
    mp4 = tmp_path / "media" / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"x")
    legacy = legacy_poster_path_for_mp4(mp4)
    legacy.write_bytes(b"\xff\xd8\xfflegacy")
    dest = relocate_legacy_poster(mp4)
    assert dest == poster_path_for_mp4(mp4)
    assert dest is not None and dest.read_bytes() == b"\xff\xd8\xfflegacy"
    assert not legacy.exists()
    assert (dest.parent.parent / STILLS_IGNORE_NAME).is_file()
    assert resolve_poster_path(mp4) == dest


def test_resolve_poster_path_prefers_stills_then_legacy(tmp_path: Path):
    mp4 = tmp_path / "media" / "by-generation" / "247" / "x.mp4"
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"x")
    legacy = legacy_poster_path_for_mp4(mp4)
    legacy.write_bytes(b"old")
    assert resolve_poster_path(mp4) == legacy
    canonical = poster_path_for_mp4(mp4)
    canonical.parent.mkdir(parents=True)
    canonical.write_bytes(b"new")
    assert resolve_poster_path(mp4) == canonical


def test_extract_requires_duration_or_ffprobe(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    with pytest.raises(ValueError, match="duration_sec or ffprobe"):
        extract_mid_loop_poster(ffmpeg="ffmpeg", mp4=mp4)


def test_extract_missing_mp4(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        extract_mid_loop_poster(
            ffmpeg="ffmpeg",
            mp4=tmp_path / "missing.mp4",
            duration_sec=1.0,
        )
