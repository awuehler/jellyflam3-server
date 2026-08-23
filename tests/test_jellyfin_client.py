from pathlib import Path
from unittest.mock import MagicMock

from pipeline.jellyfin_client import (
    JellyfinClient,
    build_flock_overview,
    build_flock_sort_name,
    image_content_type,
    normalize_media_path,
    pick_best_item,
    score_item_for_media,
)


def test_normalize_media_path():
    assert normalize_media_path(r"C:\media\sheep\a.mp4") == "c:/media/sheep/a.mp4"
    assert normalize_media_path("/media/sheep/a.mp4/") == "/media/sheep/a.mp4"


def test_score_prefers_exact_path():
    media = "/media/sheep/by-generation/247/electricsheep.247.00505.mp4"
    exact = {"Id": "1", "Name": "other", "Path": media}
    name_only = {"Id": "2", "Name": "electricsheep.247.00505", "Path": "/other/x.mp4"}
    assert score_item_for_media(exact, media) > score_item_for_media(name_only, media)


def test_pick_best_item_filename_suffix():
    media = Path("/media/sheep/by-generation/247/electricsheep.247.00505.mp4")
    items = [
        {"Id": "wrong", "Name": "electricsheep.247.00505", "Path": "/tmp/other.mp4"},
        {
            "Id": "right",
            "Name": "electricsheep.247.00505",
            "Path": "/var/lib/jellyfin/media/sheep/by-generation/247/electricsheep.247.00505.mp4",
        },
    ]
    best = pick_best_item(items, media)
    assert best is not None and best["Id"] == "right"


def test_find_item_for_media_scopes_library_and_path():
    client = JellyfinClient(
        url="http://jf",
        api_key="k",
        user_id="u1",
        library_id="lib1",
    )
    media = "/media/sheep/by-generation/247/electricsheep.247.00505.mp4"
    captured: list[dict[str, str]] = []

    def _items_query(**params: str):
        captured.append(params)
        return [
            {
                "Id": "hit",
                "Name": "electricsheep.247.00505",
                "Path": media,
            }
        ]

    client._items_query = _items_query  # type: ignore[method-assign]
    item = client.find_item_for_media(media)
    assert item is not None and item["Id"] == "hit"
    assert captured[0]["ParentId"] == "lib1"
    assert "Path" in captured[0]["Fields"]
    assert "ImageTags" in captured[0]["Fields"]
    assert captured[0]["searchTerm"] == "electricsheep.247.00505"


def test_find_item_for_media_falls_back_without_parent():
    client = JellyfinClient(url="http://jf", api_key="k", user_id="u1", library_id="bad")
    media = "/media/sheep/x.mp4"
    calls = {"n": 0}

    def _items_query(**params: str):
        calls["n"] += 1
        if "ParentId" in params:
            return []
        return [{"Id": "ok", "Name": "x", "Path": media}]

    client._items_query = _items_query  # type: ignore[method-assign]
    item = client.find_item_for_media(media)
    assert item is not None and item["Id"] == "ok"
    assert calls["n"] == 2


def test_find_item_by_path_name_delegates_to_media_lookup():
    client = JellyfinClient(url="http://jf", api_key="k", user_id="u1")
    client.find_item_for_media = MagicMock(return_value={"Id": "z"})  # type: ignore[method-assign]
    assert client.find_item_by_path_name("electricsheep.247.00505") == {"Id": "z"}
    client.find_item_for_media.assert_called_once_with("electricsheep.247.00505.mp4")


def test_find_item_without_user_returns_none():
    client = JellyfinClient(url="http://jf", api_key="k")
    assert client.find_item_for_media("/media/sheep/a.mp4") is None


def test_image_content_type():
    assert image_content_type(Path("a.jpg")) == "image/jpeg"
    assert image_content_type(Path("a.PNG")) == "image/png"


def test_upload_primary_retries_404_then_succeeds(tmp_path: Path):
    client = JellyfinClient(url="http://jf", api_key="k")
    img = tmp_path / "sheep-poster.jpg"
    img.write_bytes(b"\xff\xd8\xfffake")
    sleeps: list[float] = []
    calls = {"n": 0}

    def _raw(method, path, data, *, content_type, timeout=60):  # noqa: ARG001
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(f"Jellyfin POST {path} → 404: not found")
        return 204, b""

    client.request_raw = _raw  # type: ignore[method-assign]
    result = client.upload_primary_image(
        "item-1",
        img,
        retries=5,
        backoff_sec=0.5,
        sleep=sleeps.append,
    )
    assert result.ok
    assert result.status == "uploaded"
    assert result.attempts == 3
    assert result.http_status == 204
    assert sleeps == [0.5, 1.0]
    assert calls["n"] == 3


def test_upload_primary_permanent_failure_soft_fails(tmp_path: Path):
    client = JellyfinClient(url="http://jf", api_key="k")
    img = tmp_path / "sheep-poster.jpg"
    img.write_bytes(b"\xff\xd8\xfffake")
    sleeps: list[float] = []

    def _raw(method, path, data, *, content_type, timeout=60):  # noqa: ARG001
        raise RuntimeError(f"Jellyfin POST {path} → 400: bad image")

    client.request_raw = _raw  # type: ignore[method-assign]
    result = client.upload_primary_image(
        "item-1",
        img,
        retries=5,
        backoff_sec=1.0,
        sleep=sleeps.append,
    )
    assert not result.ok
    assert result.status == "failed"
    assert result.attempts == 1
    assert result.http_status == 400
    assert sleeps == []
    assert "400" in (result.error or "")
    # Sidecar-friendly dict for piece D.
    assert result.to_sidecar()["ok"] is False


def test_upload_primary_missing_file(tmp_path: Path):
    client = JellyfinClient(url="http://jf", api_key="k")
    result = client.upload_primary_image("item-1", tmp_path / "missing.jpg")
    assert not result.ok
    assert result.status == "missing_file"
    assert result.attempts == 0


def test_upload_primary_missing_item_id(tmp_path: Path):
    client = JellyfinClient(url="http://jf", api_key="k")
    img = tmp_path / "p.jpg"
    img.write_bytes(b"x")
    result = client.upload_primary_image("", img)
    assert result.status == "missing_item_id"


def test_build_flock_overview_and_sort_name():
    ov = build_flock_overview(
        sheep_id="electricsheep.247.00505",
        license="cc-by-nc",
        tags=["cc-by-nc", "generation-247"],
        duration_sec=23.0,
        edition="gold_sheep_lite",
    )
    assert "electricsheep.247.00505" in ov
    assert "cc-by-nc" in ov
    assert "23.0s" in ov
    assert "gold_sheep_lite" in ov
    assert "Scott Draves" in ov
    assert build_flock_sort_name("electricsheep.247.00505") == "electricsheep.247.00505"


def test_enrich_item_metadata_posts_merged_item():
    client = JellyfinClient(url="http://jf", api_key="k", user_id="u1")
    calls: list[tuple[str, str, dict | None]] = []

    def _request(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET":
            return {
                "Id": "item-1",
                "Name": "electricsheep.247.00505",
                "Tags": ["legacy"],
                "Overview": "old",
            }
        return None

    client.request = _request  # type: ignore[method-assign]
    result = client.enrich_item_metadata(
        "item-1",
        sheep_id="electricsheep.247.00505",
        license="cc-by",
        tags=["cc-by", "generation-247"],
        duration_sec=13.0,
        edition="gold_sheep_lite",
    )
    assert result.ok and result.status == "enriched"
    assert result.sort_name == "electricsheep.247.00505"
    assert "legacy" in (result.tags or [])
    assert "cc-by" in (result.tags or [])
    assert calls[0][0] == "GET"
    assert calls[0][1] == "/Users/u1/Items/item-1"
    assert calls[1][0] == "POST" and calls[1][1] == "/Items/item-1"
    posted = calls[1][2]
    assert posted is not None
    assert posted["Overview"] == result.overview
    assert posted["SortName"] == "electricsheep.247.00505"
    assert posted["ForcedSortName"] == "electricsheep.247.00505"
    assert "legacy" in posted["Tags"]


def test_has_primary_image_true_false():
    client = JellyfinClient(url="http://jf", api_key="k", user_id="u1")
    client.get_item = MagicMock(return_value={"ImageTags": {"Primary": "abc"}})  # type: ignore[method-assign]
    assert client.has_primary_image("i1") is True
    client.get_item = MagicMock(return_value={"ImageTags": {}})  # type: ignore[method-assign]
    assert client.has_primary_image("i1") is False


def test_enrich_item_metadata_falls_back_to_tags_on_post_fail():
    client = JellyfinClient(url="http://jf", api_key="k", user_id="u1")

    def _request(method, path, body=None):  # noqa: ARG001
        if method == "GET":
            return {"Id": "item-1", "Tags": []}
        raise RuntimeError("Jellyfin POST /Items/item-1 → 400: bad")

    client.request = _request  # type: ignore[method-assign]
    client.add_tags = MagicMock()  # type: ignore[method-assign]
    result = client.enrich_item_metadata(
        "item-1",
        sheep_id="x",
        license="unknown",
        tags=["cc-by"],
    )
    assert result.ok
    assert result.status == "tags_only"
    client.add_tags.assert_called_once_with("item-1", ["cc-by"])


def test_enrich_item_metadata_soft_fails_completely():
    client = JellyfinClient(url="http://jf", api_key="k")

    def _request(method, path, body=None):  # noqa: ARG001
        raise RuntimeError("Jellyfin GET /Items/item-1 → 404: gone")

    client.request = _request  # type: ignore[method-assign]
    client.add_tags = MagicMock(side_effect=RuntimeError("tags down"))  # type: ignore[method-assign]
    result = client.enrich_item_metadata("item-1", sheep_id="x", tags=["cc-by"])
    assert not result.ok
    assert result.status == "failed"
