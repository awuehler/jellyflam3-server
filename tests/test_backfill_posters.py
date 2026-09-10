import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from pipeline.backfill_posters import (
    backfill_one,
    iter_catalog_mp4s,
    needs_backfill,
    run_backfill,
)
from pipeline.jellyfin_client import ImageAttachResult, MetadataEnrichResult
from pipeline.poster import poster_path_for_mp4


def _media_tree(tmp: Path) -> Path:
    media = tmp / "media"
    (media / "by-generation" / "247").mkdir(parents=True)
    return media


def _cfg(tmp: Path, media: Path, api_key: str = "k") -> dict:
    return {
        "_repo_root": str(tmp),
        "tools": {"ffmpeg": "ffmpeg", "ffprobe": "ffprobe"},
        "paths": {"media_library": str(media)},
        "idle_gate": {"enabled": False},
        "jellyfin": {
            "url": "http://jf",
            "api_key": api_key,
            "user_id": "u1",
            "library_id": "lib1",
            "refresh_after_ingest": True,
            "attach_posters": True,
            "refresh_settle_sec": 0,
            "image_upload_retries": 2,
            "image_upload_backoff_sec": 0.01,
        },
    }


def test_iter_catalog_mp4s(tmp_path: Path):
    media = _media_tree(tmp_path)
    a = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    b = media / "by-generation" / "247" / "electricsheep.247.00128.mp4"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    (media / "by-generation" / "247" / "notes.txt").write_text("x")
    parked = media / "_refactor-quarantine" / "electricsheep.247.00505" / "electricsheep.247.00505.mp4"
    parked.parent.mkdir(parents=True)
    parked.write_bytes(b"q")
    preview = media / "_refactor-preview" / "electricsheep.247.00128" / "electricsheep.247.00128.mp4"
    preview.parent.mkdir(parents=True)
    preview.write_bytes(b"p")
    found = iter_catalog_mp4s(media)
    assert [p.name for p in found] == [
        "electricsheep.247.00128.mp4",
        "electricsheep.247.00505.mp4",
    ]
    assert parked not in found
    assert preview not in found


def test_needs_backfill_already_complete(tmp_path: Path):
    media = _media_tree(tmp_path)
    mp4 = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"x")
    poster = mp4.with_name("electricsheep.247.00505-poster.jpg")
    poster.write_bytes(b"\xff\xd8\xff")
    sidecar = {
        "jellyfin_image": {"ok": True, "status": "uploaded"},
        "jellyfin_metadata": {"ok": True, "status": "enriched"},
        "stills": {"ok": True, "status": "extracted", "screensaver_safe": True},
    }
    needed, reason = needs_backfill(mp4, sidecar)
    assert not needed and reason == "already_complete"
    needed, reason = needs_backfill(mp4, sidecar, force=True)
    assert needed and reason == "force"


def test_needs_backfill_stills_folder_poster(tmp_path: Path):
    media = _media_tree(tmp_path)
    mp4 = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"x")
    poster = (
        media
        / "by-generation"
        / "247"
        / "stills"
        / "electricsheep.247.00505"
        / "electricsheep.247.00505-poster.jpg"
    )
    poster.parent.mkdir(parents=True)
    poster.write_bytes(b"\xff\xd8\xff")
    sidecar = {
        "jellyfin_image": {"ok": True, "status": "uploaded"},
        "jellyfin_metadata": {"ok": True, "status": "enriched"},
        "stills": {"ok": True, "status": "extracted", "screensaver_safe": True},
    }
    needed, reason = needs_backfill(mp4, sidecar)
    assert not needed and reason == "already_complete"


def test_needs_backfill_tuple_complete_without_stills(tmp_path: Path):
    media = _media_tree(tmp_path)
    mp4 = media / "by-generation" / "tuple" / "electricsheep.tuple.a_to_b.mp4"
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"x")
    poster = mp4.with_name("electricsheep.tuple.a_to_b-poster.jpg")
    poster.write_bytes(b"\xff\xd8\xff")
    sidecar = {
        "type": "tuple",
        "jellyfin_image": {"ok": True, "status": "uploaded"},
        "jellyfin_metadata": {"ok": True, "status": "enriched"},
    }
    needed, reason = needs_backfill(mp4, sidecar)
    assert not needed and reason == "already_complete"


def test_needs_backfill_missing_poster(tmp_path: Path):
    media = _media_tree(tmp_path)
    mp4 = media / "by-generation" / "247" / "x.mp4"
    mp4.write_bytes(b"x")
    needed, reason = needs_backfill(mp4, {})
    assert needed and reason == "missing_poster"


def test_run_backfill_dry_run_counts(tmp_path: Path):
    media = _media_tree(tmp_path)
    done = media / "by-generation" / "247" / "done.mp4"
    todo = media / "by-generation" / "247" / "todo.mp4"
    done.write_bytes(b"d")
    todo.write_bytes(b"t")
    done.with_name("done-poster.jpg").write_bytes(b"j")
    done.with_suffix(".jellyflam3.json").write_text(
        json.dumps(
            {
                "jellyfin_image": {"ok": True, "status": "uploaded"},
                "jellyfin_metadata": {"ok": True, "status": "enriched"},
                "stills": {"ok": True, "status": "extracted", "screensaver_safe": True},
            }
        ),
        encoding="utf-8",
    )
    stats = run_backfill(_cfg(tmp_path, media), dry_run=True)
    assert stats.scanned == 2
    assert stats.skipped == 1
    assert stats.dry_run_would_process == 1
    assert stats.reasons.get("missing_poster") == 1


def test_run_backfill_relocates_legacy_poster(tmp_path: Path):
    media = _media_tree(tmp_path)
    mp4 = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"d")
    legacy = mp4.with_name("electricsheep.247.00505-poster.jpg")
    legacy.write_bytes(b"j")
    mp4.with_suffix(".jellyflam3.json").write_text(
        json.dumps(
            {
                "jellyfin_image": {"ok": True, "status": "uploaded"},
                "jellyfin_metadata": {"ok": True, "status": "enriched"},
                "stills": {"ok": True, "status": "extracted", "screensaver_safe": True},
            }
        ),
        encoding="utf-8",
    )
    stats = run_backfill(
        _cfg(tmp_path, media, api_key=""),
        skip_jellyfin=True,
        interval_sec=0,
        sleep=lambda _s: None,
    )
    dest = (
        media
        / "by-generation"
        / "247"
        / "stills"
        / "electricsheep.247.00505"
        / "electricsheep.247.00505-poster.jpg"
    )
    assert dest.is_file()
    assert dest.read_bytes() == b"j"
    assert not legacy.exists()
    assert stats.skipped == 1


def test_run_backfill_dry_run_ignores_quarantine_mp4s(tmp_path: Path):
    media = _media_tree(tmp_path)
    live = media / "by-generation" / "247" / "todo.mp4"
    live.write_bytes(b"t")
    parked = media / "_refactor-quarantine" / "electricsheep.247.00505" / "electricsheep.247.00505.mp4"
    parked.parent.mkdir(parents=True)
    parked.write_bytes(b"q")
    stats = run_backfill(_cfg(tmp_path, media), dry_run=True)
    assert stats.scanned == 1
    assert stats.dry_run_would_process == 1
    assert "unpublished" not in stats.reasons


def test_backfill_one_skips_quarantine_without_extract(tmp_path: Path):
    media = _media_tree(tmp_path)
    mp4 = media / "_refactor-quarantine" / "electricsheep.247.00505" / "electricsheep.247.00505.mp4"
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"q")
    with patch("pipeline.backfill_posters.extract_poster_for_mp4") as poster, patch(
        "pipeline.backfill_posters.extract_stills_for_mp4"
    ) as stills:
        result = backfill_one(_cfg(tmp_path, media), mp4, skip_jellyfin=True, force=True)
    assert result["status"] == "skipped"
    assert result["reason"] == "unpublished"
    poster.assert_not_called()
    stills.assert_not_called()


def test_backfill_one_poster_only(tmp_path: Path):
    media = _media_tree(tmp_path)
    mp4 = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    poster = poster_path_for_mp4(mp4)
    poster.parent.mkdir(parents=True, exist_ok=True)
    mp4.with_suffix(".jellyflam3.json").write_text(
        json.dumps({"id": "electricsheep.247.00505", "duration_sec": 13.0}),
        encoding="utf-8",
    )
    cfg = _cfg(tmp_path, media, api_key="")

    with patch(
        "pipeline.backfill_posters.extract_poster_for_mp4",
        return_value={"ok": True, "status": "extracted", "poster_path": str(poster)},
    ) as ext, patch(
        "pipeline.backfill_posters.extract_stills_for_mp4",
        return_value={"ok": True, "status": "already_complete", "count": 4, "dir": str(tmp_path)},
    ):
        poster.write_bytes(b"\xff\xd8\xff")
        result = backfill_one(cfg, mp4, skip_jellyfin=True)

    assert result["status"] == "poster_only"
    assert ext.call_args.kwargs.get("force") is True
    side = json.loads(mp4.with_suffix(".jellyflam3.json").read_text(encoding="utf-8"))
    assert side["poster"]["ok"] is True


def test_backfill_one_uploads_with_mocked_client(tmp_path: Path):
    media = _media_tree(tmp_path)
    mp4 = media / "by-generation" / "247" / "electricsheep.247.00505.mp4"
    mp4.write_bytes(b"fake")
    poster = poster_path_for_mp4(mp4)
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"\xff\xd8\xff")
    mp4.with_suffix(".jellyflam3.json").write_text(
        json.dumps(
            {
                "id": "electricsheep.247.00505",
                "license": "cc-by",
                "tags": ["cc-by"],
                "duration_sec": 13.0,
            }
        ),
        encoding="utf-8",
    )

    client = MagicMock()
    client.find_item_for_media.return_value = {"Id": "item-1", "Path": str(mp4)}
    client.has_primary_image.return_value = False
    client.enrich_item_metadata.return_value = MetadataEnrichResult(
        ok=True, item_id="item-1", status="enriched", sort_name="electricsheep.247.00505"
    )
    client.upload_primary_image.return_value = ImageAttachResult(
        ok=True, item_id="item-1", attempts=1, status="uploaded", http_status=204
    )

    with patch(
        "pipeline.backfill_posters.extract_poster_for_mp4",
        return_value={"ok": True, "status": "extracted", "poster_path": str(poster)},
    ), patch(
        "pipeline.backfill_posters.extract_stills_for_mp4",
        return_value={"ok": True, "status": "already_complete", "count": 4, "dir": str(tmp_path)},
    ), patch(
        "pipeline.backfill_posters.attach_stills_backdrops",
        return_value={"ok": True, "status": "uploaded", "uploaded": 4},
    ):
        result = backfill_one(
            _cfg(tmp_path, media),
            mp4,
            client=client,
            sleep=lambda _s: None,
        )

    assert result["status"] == "processed"
    client.refresh_library.assert_not_called()  # batch refresh only
    client.upload_primary_image.assert_called_once()
    side = json.loads(mp4.with_suffix(".jellyflam3.json").read_text(encoding="utf-8"))
    assert side["jellyfin_image"]["ok"] is True
    assert side["jellyfin_metadata"]["status"] == "enriched"
    assert side["stills"]["status"] == "already_complete"
    assert side["jellyfin_stills"]["status"] == "uploaded"


def test_run_backfill_respects_limit_and_interval(tmp_path: Path):
    media = _media_tree(tmp_path)
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        (media / "by-generation" / "247" / name).write_bytes(b"x")
    sleeps: list[float] = []
    cfg = _cfg(tmp_path, media, api_key="")

    with patch(
        "pipeline.backfill_posters.backfill_one",
        return_value={"status": "poster_only", "poster": {"ok": True}},
    ) as one:
        stats = run_backfill(
            cfg,
            limit=2,
            interval_sec=0.5,
            skip_jellyfin=True,
            sleep=sleeps.append,
        )

    assert stats.processed == 2
    assert one.call_count == 2
    assert sleeps == [0.5, 0.5]
