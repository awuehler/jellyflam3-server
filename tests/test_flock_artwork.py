from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.flock_artwork import (
    apply_flock_artwork,
    attach_primary_after_refresh,
    extract_poster_for_mp4,
)
from pipeline.jellyfin_client import ImageAttachResult, MetadataEnrichResult


def _cfg(attach: bool = True, api_key: str = "k") -> dict:
    return {
        "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
        "jellyfin": {
            "url": "http://jf",
            "api_key": api_key,
            "user_id": "u1",
            "library_id": "lib1",
            "refresh_after_ingest": True,
            "attach_posters": attach,
            "refresh_settle_sec": 0.25,
            "image_upload_retries": 3,
            "image_upload_backoff_sec": 0.1,
            "commercial_collection_name": "commercial-safe",
        },
    }


def test_extract_poster_writes_sidecar_fields(tmp_path: Path):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    poster = tmp_path / "electricsheep.247.00505-poster.jpg"

    with patch(
        "pipeline.flock_artwork.extract_mid_loop_poster",
        return_value=poster,
    ) as ext:
        poster.write_bytes(b"\xff\xd8\xff")
        info = extract_poster_for_mp4(_cfg(), mp4, duration_sec=13.0)

    assert info["ok"] is True
    assert info["status"] == "extracted"
    assert info["poster_path"] == str(poster)
    ext.assert_called_once()


def test_extract_skipped_when_disabled(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    info = extract_poster_for_mp4(_cfg(attach=False), mp4, duration_sec=1.0)
    assert info["status"] == "skipped"


def test_extract_soft_fails(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    with patch(
        "pipeline.flock_artwork.extract_mid_loop_poster",
        side_effect=RuntimeError("ffmpeg boom"),
    ):
        info = extract_poster_for_mp4(_cfg(), mp4, duration_sec=1.0)
    assert info["ok"] is False
    assert info["status"] == "extract_failed"


def test_attach_primary_happy_path(tmp_path: Path):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    poster = tmp_path / "electricsheep.247.00505-poster.jpg"
    poster.write_bytes(b"\xff\xd8\xff")
    sleeps: list[float] = []

    client = MagicMock()
    client.find_item_for_media.return_value = {"Id": "item-9", "Path": str(mp4)}
    client.has_primary_image.return_value = False
    client.enrich_item_metadata.return_value = MetadataEnrichResult(
        ok=True,
        item_id="item-9",
        status="enriched",
        overview="ov",
        sort_name="electricsheep.247.00505",
        tags=["cc-by"],
    )
    client.upload_primary_image.return_value = ImageAttachResult(
        ok=True,
        item_id="item-9",
        attempts=1,
        status="uploaded",
        http_status=204,
    )

    out = attach_primary_after_refresh(
        _cfg(),
        mp4,
        poster,
        tags=["cc-by"],
        sidecar={
            "id": "electricsheep.247.00505",
            "license": "cc-by",
            "duration_sec": 13.0,
            "edition": "gold_sheep_lite",
        },
        client=client,
        sleep=sleeps.append,
    )
    assert out["ok"] is True
    assert out["status"] == "uploaded"
    assert out["item_id"] == "item-9"
    assert out["metadata"]["status"] == "enriched"
    client.refresh_library.assert_called_once()
    client.find_item_for_media.assert_called_once_with(mp4)
    client.enrich_item_metadata.assert_called_once()
    client.upload_primary_image.assert_called_once()
    assert sleeps == [0.25]


def test_attach_skips_without_api_key(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    out = attach_primary_after_refresh(
        _cfg(api_key=""),
        mp4,
        None,
        tags=[],
    )
    assert out["status"] == "skipped"


def test_attach_metadata_only_when_posters_disabled(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    client = MagicMock()
    client.find_item_for_media.return_value = {"Id": "item-t"}
    client.enrich_item_metadata.return_value = MetadataEnrichResult(
        ok=True, item_id="item-t", status="enriched", sort_name="x"
    )
    out = attach_primary_after_refresh(
        _cfg(attach=False),
        mp4,
        None,
        tags=["cc-by"],
        sidecar={"id": "x", "license": "cc-by"},
        client=client,
        sleep=lambda _s: None,
    )
    assert out["status"] == "metadata_only"
    assert out["item_id"] == "item-t"
    client.enrich_item_metadata.assert_called_once()
    client.upload_primary_image.assert_not_called()


def test_attach_uses_local_primary_when_already_present(tmp_path: Path):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    poster = tmp_path / "electricsheep.247.00505-poster.jpg"
    poster.write_bytes(b"\xff\xd8\xff")
    client = MagicMock()
    client.find_item_for_media.return_value = {"Id": "item-l"}
    client.has_primary_image.return_value = True
    client.enrich_item_metadata.return_value = MetadataEnrichResult(
        ok=True, item_id="item-l", status="enriched", sort_name="electricsheep.247.00505"
    )
    out = attach_primary_after_refresh(
        _cfg(),
        mp4,
        poster,
        tags=["cc-by"],
        sidecar={"id": "electricsheep.247.00505", "license": "cc-by"},
        client=client,
        sleep=lambda _s: None,
    )
    assert out["ok"] is True
    assert out["status"] == "local_primary"
    client.upload_primary_image.assert_not_called()


def test_attach_item_not_found(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    poster = tmp_path / "x-poster.jpg"
    poster.write_bytes(b"j")
    client = MagicMock()
    client.find_item_for_media.return_value = None
    out = attach_primary_after_refresh(
        _cfg(),
        mp4,
        poster,
        tags=[],
        client=client,
        sleep=lambda _s: None,
    )
    assert out["status"] == "item_not_found"
    client.upload_primary_image.assert_not_called()


def test_apply_flock_artwork_updates_sidecar(tmp_path: Path):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    poster = tmp_path / "electricsheep.247.00505-poster.jpg"
    poster.write_bytes(b"\xff\xd8\xff")
    sidecar: dict = {"id": "electricsheep.247.00505"}

    client = MagicMock()
    client.find_item_for_media.return_value = {"Id": "i1"}
    client.has_primary_image.return_value = False
    client.enrich_item_metadata.return_value = MetadataEnrichResult(
        ok=True,
        item_id="i1",
        status="enriched",
        overview="ov",
        sort_name="electricsheep.247.00505",
    )
    client.upload_primary_image.return_value = ImageAttachResult(
        ok=True, item_id="i1", attempts=2, status="uploaded", http_status=204
    )

    with patch(
        "pipeline.flock_artwork.extract_mid_loop_poster",
        return_value=poster,
    ):
        apply_flock_artwork(
            _cfg(),
            mp4,
            sidecar,
            duration_sec=13.0,
            tags=["cc-by-nc"],
            client=client,
            sleep=lambda _s: None,
        )

    assert sidecar["poster"]["ok"] is True
    assert sidecar["poster_path"] == str(poster)
    assert sidecar["jellyfin_image"]["ok"] is True
    assert sidecar["jellyfin_image"]["item_id"] == "i1"
    assert sidecar["jellyfin_metadata"]["status"] == "enriched"


def test_apply_does_not_raise_when_client_explodes(tmp_path: Path):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    poster = tmp_path / "x-poster.jpg"
    poster.write_bytes(b"j")
    sidecar: dict = {"id": "x"}
    client = MagicMock()
    client.refresh_library.side_effect = RuntimeError("jf down")

    with patch(
        "pipeline.flock_artwork.extract_mid_loop_poster",
        return_value=poster,
    ):
        apply_flock_artwork(
            _cfg(),
            mp4,
            sidecar,
            duration_sec=1.0,
            tags=[],
            client=client,
            sleep=lambda _s: None,
        )

    assert sidecar["poster"]["ok"] is True
    assert sidecar["jellyfin_image"]["ok"] is False
    assert sidecar["jellyfin_image"]["status"] == "failed"
