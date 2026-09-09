from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.flock_artwork import (
    apply_flock_artwork,
    attach_posters_mode,
    attach_primary_after_refresh,
    attach_stills_backdrops,
    extract_poster_for_mp4,
    posters_ingest_state,
    stills_enabled_for_ingest,
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


def test_attach_posters_mode_values():
    assert attach_posters_mode({"jellyfin": {}}) == "auto"
    assert attach_posters_mode({"jellyfin": {"attach_posters": True}}) == "always"
    assert attach_posters_mode({"jellyfin": {"attach_posters": False}}) == "never"
    assert attach_posters_mode({"jellyfin": {"attach_posters": "auto"}}) == "auto"
    assert posters_ingest_state({"jellyfin": {"attach_posters": True}})["ingest_enabled"]
    assert not posters_ingest_state({"jellyfin": {"attach_posters": False}})[
        "ingest_enabled"
    ]


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


def test_extract_skipped_when_auto_standalone(tmp_path: Path, monkeypatch):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    cfg = _cfg()
    cfg["jellyfin"]["attach_posters"] = "auto"
    monkeypatch.setattr("pipeline.peering.furnace_mesh_size", lambda _cfg, live=None: 1)
    info = extract_poster_for_mp4(cfg, mp4, duration_sec=1.0)
    assert info["status"] == "skipped"
    assert "mesh=1" in info["error"]


def test_extract_when_auto_mesh_has_peer(tmp_path: Path, monkeypatch):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    poster = tmp_path / "electricsheep.247.00505-poster.jpg"
    cfg = _cfg()
    cfg["jellyfin"]["attach_posters"] = "auto"
    monkeypatch.setattr("pipeline.peering.furnace_mesh_size", lambda _cfg, live=None: 2)
    with patch(
        "pipeline.flock_artwork.extract_mid_loop_poster",
        return_value=poster,
    ) as ext:
        poster.write_bytes(b"\xff\xd8\xff")
        info = extract_poster_for_mp4(cfg, mp4, duration_sec=13.0)
    assert info["ok"] is True
    ext.assert_called_once()


def test_extract_force_ignores_never(tmp_path: Path):
    mp4 = tmp_path / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    poster = tmp_path / "electricsheep.247.00505-poster.jpg"
    with patch(
        "pipeline.flock_artwork.extract_mid_loop_poster",
        return_value=poster,
    ) as ext:
        poster.write_bytes(b"\xff\xd8\xff")
        info = extract_poster_for_mp4(
            _cfg(attach=False), mp4, duration_sec=13.0, force=True
        )
    assert info["ok"] is True
    ext.assert_called_once()


def test_omitted_attach_posters_is_auto_off_standalone(tmp_path: Path, monkeypatch):
    mp4 = tmp_path / "x.mp4"
    mp4.write_bytes(b"x")
    cfg = _cfg()
    del cfg["jellyfin"]["attach_posters"]
    monkeypatch.setattr("pipeline.peering.furnace_mesh_size", lambda _cfg, live=None: 1)
    info = extract_poster_for_mp4(cfg, mp4, duration_sec=1.0)
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
    ), patch(
        "pipeline.flock_artwork.extract_stills_for_mp4",
        return_value={"ok": True, "status": "already_complete", "dir": str(tmp_path)},
    ), patch(
        "pipeline.flock_artwork.attach_stills_backdrops",
        return_value={"ok": True, "status": "uploaded", "uploaded": 4},
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
    assert sidecar["stills"]["status"] == "already_complete"
    assert sidecar["jellyfin_stills"]["status"] == "uploaded"


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
    ), patch(
        "pipeline.flock_artwork.extract_stills_for_mp4",
        return_value={"ok": True, "status": "already_complete", "dir": str(tmp_path)},
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


def test_stills_enabled_follows_poster_ingest_and_skips_tuples(tmp_path: Path):
    loop = tmp_path / "electricsheep.247.00505.mp4"
    tup = tmp_path / "by-generation" / "tuple" / "electricsheep.tuple.a_to_b.mp4"
    tup.parent.mkdir(parents=True)
    loop.write_bytes(b"x")
    tup.write_bytes(b"x")
    assert stills_enabled_for_ingest(_cfg(attach=True), loop)
    assert not stills_enabled_for_ingest(_cfg(attach=False), loop)
    assert not stills_enabled_for_ingest(_cfg(attach=True), tup)
    assert not stills_enabled_for_ingest(_cfg(attach=True), loop, {"type": "tuple"})


def test_attach_stills_backdrops_uploads_frames(tmp_path: Path):
    media = tmp_path / "media"
    dest = media / "by-generation" / "247" / "stills" / "electricsheep.247.00505"
    dest.mkdir(parents=True)
    frames = []
    for i in range(2):
        p = dest / f"frame_{i:02d}.jpg"
        p.write_bytes(b"\xff\xd8\xff")
        frames.append(p)
    mp4 = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"x")
    client = MagicMock()
    client.upload_item_image.return_value = ImageAttachResult(
        ok=True, item_id="i1", attempts=1, status="uploaded", http_status=204
    )
    cfg = _cfg()
    cfg["_repo_root"] = str(tmp_path)
    cfg["paths"] = {"media_library": str(media)}
    out = attach_stills_backdrops(
        cfg,
        mp4,
        {"ok": True, "status": "extracted", "dir": str(dest)},
        client=client,
        item_id="i1",
        sleep=lambda _s: None,
        replace=True,
    )
    assert out["ok"] is True
    assert out["uploaded"] == 2
    client.clear_backdrop_images.assert_called_once_with("i1")
    assert client.upload_item_image.call_count == 2


def test_apply_tuple_skips_stills(tmp_path: Path):
    mp4 = tmp_path / "by-generation" / "tuple" / "electricsheep.tuple.a_to_b.mp4"
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"fake")
    poster = tmp_path / "electricsheep.tuple.a_to_b-poster.jpg"
    poster.write_bytes(b"\xff\xd8\xff")
    sidecar: dict = {"id": mp4.stem, "type": "tuple"}
    client = MagicMock()
    client.find_item_for_media.return_value = {"Id": "t1"}
    client.has_primary_image.return_value = False
    client.enrich_item_metadata.return_value = MetadataEnrichResult(
        ok=True, item_id="t1", status="enriched", sort_name=mp4.stem
    )
    client.upload_primary_image.return_value = ImageAttachResult(
        ok=True, item_id="t1", attempts=1, status="uploaded", http_status=204
    )
    with patch(
        "pipeline.flock_artwork.extract_mid_loop_poster",
        return_value=poster,
    ), patch(
        "pipeline.flock_artwork.extract_stills_for_mp4",
    ) as extract_stills:
        apply_flock_artwork(
            _cfg(),
            mp4,
            sidecar,
            duration_sec=13.0,
            tags=["cc-by"],
            client=client,
            sleep=lambda _s: None,
        )
    extract_stills.assert_not_called()
    assert sidecar["stills"]["status"] == "skipped_tuple"
    assert "jellyfin_stills" not in sidecar
    client.upload_item_image.assert_not_called()
    client.clear_backdrop_images.assert_not_called()
