"""Purpose: Post-encode flock artwork — mid-loop poster on disk plus Jellyfin Primary attach.

Requirements: ffmpeg; optional Jellyfin api_key / attach_posters / refresh settings.

Usage: ``apply_flock_artwork`` after ingest, or ``extract_poster_for_mp4`` / ``attach_primary_after_refresh`` separately.

Assumptions: Soft-fail dicts for sidecars; metadata enrich still runs when poster
upload is skipped. Ingest default is ``attach_posters: auto`` (standalone off,
2+ live mesh furnaces on). Operator backfill passes ``force=True``.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from pipeline.jellyfin_client import ImageAttachResult, JellyfinClient
from pipeline.poster import extract_mid_loop_poster, poster_path_for_mp4
from pipeline.tool_lookup import tool as _tool

log = logging.getLogger("jellyflam3.flock_artwork")


def attach_posters_mode(cfg: dict[str, Any]) -> str:
    """``always`` / ``never`` / ``auto`` from ``jellyfin.attach_posters`` (default auto)."""
    raw = (cfg.get("jellyfin") or {}).get("attach_posters", "auto")
    if isinstance(raw, bool):
        return "always" if raw else "never"
    s = str(raw).strip().lower()
    if s in ("true", "yes", "on", "always", "1"):
        return "always"
    if s in ("false", "no", "off", "never", "0"):
        return "never"
    return "auto"


def posters_ingest_state(
    cfg: dict[str, Any],
    *,
    mesh_size: int | None = None,
) -> dict[str, Any]:
    """Ingest poster policy: standalone auto=off; 2+ live mesh furnaces auto=on."""
    mode = attach_posters_mode(cfg)
    if mode == "always":
        mesh = 1 if mesh_size is None else int(mesh_size)
        return {"mode": mode, "mesh_size": mesh, "ingest_enabled": True}
    if mode == "never":
        mesh = 1 if mesh_size is None else int(mesh_size)
        return {"mode": mode, "mesh_size": mesh, "ingest_enabled": False}
    from pipeline.peering import furnace_mesh_size

    mesh = furnace_mesh_size(cfg) if mesh_size is None else int(mesh_size)
    return {"mode": mode, "mesh_size": mesh, "ingest_enabled": mesh >= 2}


def posters_enabled_for_ingest(cfg: dict[str, Any]) -> bool:
    """True when the worker should extract a mid-loop poster after encode."""
    return bool(posters_ingest_state(cfg)["ingest_enabled"])


def extract_poster_for_mp4(
    cfg: dict[str, Any],
    mp4: Path,
    *,
    duration_sec: float,
    force: bool = False,
) -> dict[str, Any]:
    """Write ``{stem}-poster.jpg`` beside ``mp4``. Soft-fail dict for sidecar.

    ``force=True`` is for operator backfill (ignores ingest auto/never).
    """
    if not force:
        state = posters_ingest_state(cfg)
        if not state["ingest_enabled"]:
            return {
                "ok": False,
                "status": "skipped",
                "error": (
                    f"attach_posters {state['mode']} "
                    f"(mesh={state['mesh_size']}, ingest_enabled=false)"
                ),
            }

    dest = poster_path_for_mp4(mp4)
    try:
        out = extract_mid_loop_poster(
            ffmpeg=_tool(cfg, "ffmpeg"),
            mp4=mp4,
            dest=dest,
            duration_sec=duration_sec,
        )
        return {
            "ok": True,
            "status": "extracted",
            "poster_path": str(out),
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("poster extract failed for %s: %s", mp4, exc)
        return {
            "ok": False,
            "status": "extract_failed",
            "poster_path": str(dest),
            "error": str(exc),
        }


def attach_primary_after_refresh(
    cfg: dict[str, Any],
    mp4: Path,
    poster_path: Path | None,
    *,
    tags: list[str],
    sidecar: dict[str, Any] | None = None,
    client: JellyfinClient | None = None,
    sleep: Any = time.sleep,
    refresh: bool = True,
    force: bool = False,
) -> dict[str, Any]:
    """Resolve item, metadata enrich + optional Primary upload.

    Soft-fail dict. Metadata (Overview/SortName/Tags) still runs when
    ingest posters are off; only the Images API upload is skipped then.
    ``force=True`` uploads a Primary when an operator backfill extracted a poster.

    When ``refresh`` is true (default ingest path), calls Library/Refresh and
    waits ``refresh_settle_sec``. Backfill should pass ``refresh=False`` and
    refresh once for the whole batch instead.
    """
    jf = cfg.get("jellyfin") or {}
    if not jf.get("api_key"):
        return {"ok": False, "status": "skipped", "error": "no jellyfin api_key"}
    if refresh and not jf.get("refresh_after_ingest", True):
        return {"ok": False, "status": "skipped", "error": "refresh_after_ingest false"}

    client = client or JellyfinClient.from_config(cfg)
    settle = float(jf.get("refresh_settle_sec", 2))
    retries = int(jf.get("image_upload_retries", 5))
    backoff = float(jf.get("image_upload_backoff_sec", 1.0))
    want_poster = bool(force or posters_enabled_for_ingest(cfg))
    side = sidecar or {}

    try:
        if refresh:
            client.refresh_library()
            if settle > 0:
                sleep(settle)
        item = client.find_item_for_media(mp4)
        if not item or not item.get("Id"):
            return {
                "ok": False,
                "status": "item_not_found",
                "error": f"no Jellyfin item for {mp4}",
            }
        item_id = str(item["Id"])

        meta = client.enrich_item_metadata(
            item_id,
            sheep_id=str(side.get("id") or mp4.stem),
            license=str(side.get("license") or "unknown"),
            tags=tags,
            duration_sec=(
                float(side["duration_sec"])
                if side.get("duration_sec") is not None
                else None
            ),
            edition=str(side["edition"]) if side.get("edition") else None,
        )

        if not want_poster:
            out: dict[str, Any] = {
                "ok": True,
                "status": "metadata_only",
                "item_id": item_id,
                "attempts": 0,
            }
        elif poster_path is not None and poster_path.is_file():
            # Local-image-first: FS ``{stem}-poster.jpg`` + refresh often yields
            # ImageTags.Primary without Images API (and survives write denials).
            if client.has_primary_image(item_id):
                out = {
                    "ok": True,
                    "status": "local_primary",
                    "item_id": item_id,
                    "attempts": 0,
                    "error": None,
                    "http_status": None,
                }
            else:
                image_result = client.upload_primary_image(
                    item_id,
                    poster_path,
                    retries=retries,
                    backoff_sec=backoff,
                    sleep=sleep,
                )
                out = image_result.to_sidecar()
                out["item_id"] = item_id
                if not image_result.ok and client.has_primary_image(item_id):
                    # Upload failed but local provider still attached Primary.
                    out = {
                        "ok": True,
                        "status": "local_primary",
                        "item_id": item_id,
                        "attempts": image_result.attempts,
                        "error": image_result.error,
                        "http_status": image_result.http_status,
                    }
        else:
            out = ImageAttachResult(
                ok=False,
                item_id=item_id,
                attempts=0,
                status="missing_file",
                error="poster missing; skipped Primary upload",
            ).to_sidecar()
            out["item_id"] = item_id

        out["metadata"] = meta.to_sidecar()

        try:
            client.ensure_commercial_collection(
                jf.get("commercial_collection_name") or "commercial-safe"
            )
        except Exception as exc:  # noqa: BLE001
            log.info("ensure_commercial_collection soft-fail: %s", exc)
        return out
    except Exception as exc:  # noqa: BLE001
        log.warning("Jellyfin poster attach failed for %s: %s", mp4, exc)
        return {"ok": False, "status": "failed", "error": str(exc)}


def apply_flock_artwork(
    cfg: dict[str, Any],
    mp4: Path,
    sidecar: dict[str, Any],
    *,
    duration_sec: float,
    tags: list[str],
    client: JellyfinClient | None = None,
    sleep: Any = time.sleep,
) -> dict[str, Any]:
    """Mutate ``sidecar`` with poster + jellyfin_image / metadata fields."""
    poster_info = extract_poster_for_mp4(cfg, mp4, duration_sec=duration_sec)
    sidecar["poster"] = poster_info
    if poster_info.get("poster_path"):
        sidecar["poster_path"] = poster_info["poster_path"]

    poster_path = (
        Path(poster_info["poster_path"])
        if poster_info.get("ok") and poster_info.get("poster_path")
        else None
    )
    attach = attach_primary_after_refresh(
        cfg,
        mp4,
        poster_path,
        tags=tags,
        sidecar=sidecar,
        client=client,
        sleep=sleep,
    )
    sidecar["jellyfin_image"] = attach
    if isinstance(attach.get("metadata"), dict):
        sidecar["jellyfin_metadata"] = attach["metadata"]
    return sidecar
