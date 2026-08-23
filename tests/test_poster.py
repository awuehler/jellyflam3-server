from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.poster import (
    extract_mid_loop_poster,
    mid_loop_seek_sec,
    poster_path_for_mp4,
)


def test_poster_path_for_mp4():
    mp4 = Path("/media/sheep/by-generation/247/electricsheep.247.00505.mp4")
    assert poster_path_for_mp4(mp4) == Path(
        "/media/sheep/by-generation/247/electricsheep.247.00505-poster.jpg"
    )


def test_mid_loop_seek_sec():
    assert mid_loop_seek_sec(24.0) == 12.0
    assert mid_loop_seek_sec(0) == 0.0
    assert mid_loop_seek_sec(-1) == 0.0


def test_extract_mid_loop_poster_writes_beside_mp4(tmp_path: Path):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake-mp4")
    expected = tmp_path / "electricsheep.247.00505-poster.jpg"

    def _fake_run(cmd, check=True, capture_output=True):  # noqa: ARG001
        # Last arg is output path
        Path(cmd[-1]).write_bytes(b"\xff\xd8\xfffakejpeg")
        return MagicMock(returncode=0)

    with patch("pipeline.poster.subprocess.run", side_effect=_fake_run) as run:
        out = extract_mid_loop_poster(
            ffmpeg="ffmpeg",
            mp4=mp4,
            duration_sec=13.0,
        )

    assert out == expected
    assert expected.is_file() and expected.stat().st_size > 0
    cmd = run.call_args.args[0]
    assert cmd[0] == "ffmpeg"
    assert "-ss" in cmd
    assert cmd[cmd.index("-ss") + 1] == "6.500"
    assert cmd[-1] == str(expected)


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
