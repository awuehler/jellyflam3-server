from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.idle_gate import should_block_render
from pipeline.stills import (
    extract_stills_for_mp4,
    frame_path,
    seek_points_sec,
    stills_dir_for_mp4,
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


def test_idle_gate_ignores_screensaver_client():
    cfg = {
        "idle_gate": {
            "tv_client_patterns": [r"(?i)roku", r"(?i)jellyflam3"],
            "ignore_client_patterns": [r"(?i)jellyflam3.?screensaver", r"(?i)screensaver"],
            "block_on_any_transcode": True,
            "active_within_seconds": 60,
        }
    }
    sessions = [
        {
            "Client": "JellyFlam3-Screensaver",
            "DeviceName": "Roku",
            "NowPlayingItem": {"Id": "x"},  # should still be ignored
        }
    ]
    d = should_block_render(sessions, cfg)
    assert d.blocked is False
    assert d.reason == "idle"
