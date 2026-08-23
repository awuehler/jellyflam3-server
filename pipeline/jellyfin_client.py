"""Purpose: Minimal Jellyfin API client for library refresh, tags, and Primary image upload.

Requirements: jellyfin.url + api_key; user_id for item search; optional library_id scope.

Usage: ``JellyfinClient.from_config(cfg)`` then refresh / find_item / enrich / upload_primary_image.

Assumptions: Soft-fail results for ingest; sidecar remains license source of truth when Tags API fails.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("jellyflam3.jellyfin")

# HTTP statuses that often mean "try again after library refresh / item race".
_RETRYABLE_HTTP = frozenset({404, 408, 409, 425, 429, 500, 502, 503, 504})


@dataclass(frozen=True)
class ImageAttachResult:
    """Soft-fail status for Primary image upload (never raises into ingest)."""

    ok: bool
    item_id: str
    attempts: int
    status: str  # uploaded | failed | missing_file | missing_item_id
    error: str | None = None
    http_status: int | None = None

    def to_sidecar(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MetadataEnrichResult:
    """Soft-fail status for Overview / SortName / Tags enrich."""

    ok: bool
    item_id: str
    status: str  # enriched | tags_only | failed | skipped | missing_item_id
    error: str | None = None
    overview: str | None = None
    sort_name: str | None = None
    tags: list[str] | None = None

    def to_sidecar(self) -> dict[str, Any]:
        return asdict(self)


def build_flock_overview(
    *,
    sheep_id: str,
    license: str = "unknown",
    tags: list[str] | None = None,
    duration_sec: float | None = None,
    edition: str | None = None,
) -> str:
    """Short Jellyfin Overview for browse/detail clients."""
    lines = [
        f"JellyFlam3 sheep · {sheep_id}",
        f"License: {license}",
    ]
    if duration_sec is not None:
        lines.append(f"Duration: {float(duration_sec):.1f}s")
    if edition:
        lines.append(f"Edition: {edition}")
    if tags:
        lines.append("Tags: " + ", ".join(tags))
    lines.append(
        "Artwork by Scott Draves and the Electric Sheep "
        "(Free Sheep / remix lineage)."
    )
    return "\n".join(lines)


def build_flock_sort_name(sheep_id: str) -> str:
    """Stable SortName from sheep basename (generation.serial ordering)."""
    return (sheep_id or "").strip() or "jellyflam3-sheep"


def image_content_type(path: Path) -> str:
    """MIME type from image suffix (jpeg/png/webp), else octet-stream."""
    suf = path.suffix.lower()
    if suf in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suf == ".png":
        return "image/png"
    if suf == ".webp":
        return "image/webp"
    return "application/octet-stream"


def normalize_media_path(path: str | Path) -> str:
    """Lowercase POSIX-ish path for comparisons across hosts."""
    return str(path).replace("\\", "/").rstrip("/").lower()


def score_item_for_media(item: dict[str, Any], media_path: str | Path) -> int:
    """Higher score = better match. 0 means not a candidate."""
    target = Path(media_path)
    target_n = normalize_media_path(target)
    item_path = item.get("Path") or ""
    item_n = normalize_media_path(item_path) if item_path else ""
    name = (item.get("Name") or "").strip()
    stem = target.stem
    filename = target.name

    if item_n and item_n == target_n:
        return 100
    if item_n and item_n.endswith("/" + filename.lower()):
        return 90
    if item_n and filename.lower() in item_n:
        return 70
    if name.lower() == stem.lower():
        return 80
    if stem.lower() in name.lower():
        return 10
    return 0


def pick_best_item(
    items: list[dict[str, Any]], media_path: str | Path
) -> dict[str, Any] | None:
    """Return the highest-scoring item for ``media_path``, or None if none match."""
    best: dict[str, Any] | None = None
    best_score = 0
    for it in items:
        score = score_item_for_media(it, media_path)
        if score > best_score:
            best = it
            best_score = score
    return best if best_score > 0 else None


def _http_status_from_error(message: str) -> int | None:
    """Parse status code from ``Jellyfin … → NNN: …`` RuntimeError text."""
    # RuntimeError text: "Jellyfin POST /Items/... → 404: ..."
    marker = " → "
    if marker not in message:
        return None
    try:
        code_part = message.split(marker, 1)[1]
        code = code_part.split(":", 1)[0].strip()
        return int(code)
    except (IndexError, ValueError):
        return None


class JellyfinClient:
    """Thin MediaBrowser-token client for the JellyFlam3 ingest/artwork paths."""

    def __init__(self, url: str, api_key: str, user_id: str = "", library_id: str = ""):
        self.base = url.rstrip("/")
        self.api_key = api_key
        self.user_id = user_id
        self.library_id = library_id

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def request(self, method: str, path: str, body: dict | None = None) -> Any:
        """JSON API call; empty body → None; HTTP errors become RuntimeError with status."""
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers=self._headers(),
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                if not raw:
                    return None
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Jellyfin {method} {path} → {e.code}: {detail}") from e

    def request_raw(
        self,
        method: str,
        path: str,
        data: bytes,
        *,
        content_type: str,
        timeout: float = 60,
    ) -> tuple[int, bytes]:
        """HTTP request with a raw body (e.g. image bytes). Returns (status, body)."""
        headers = {
            "Authorization": f'MediaBrowser Token="{self.api_key}"',
            "Accept": "*/*",
            "Content-Type": content_type,
        }
        req = urllib.request.Request(
            f"{self.base}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return int(resp.status), resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read()
            raise RuntimeError(
                f"Jellyfin {method} {path} → {e.code}: "
                f"{detail.decode('utf-8', errors='replace')}"
            ) from e

    def refresh_library(self) -> None:
        """Trigger a full Jellyfin library refresh."""
        self.request("POST", "/Library/Refresh")

    def upload_primary_image(
        self,
        item_id: str,
        image_path: str | Path,
        *,
        retries: int = 5,
        backoff_sec: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> ImageAttachResult:
        """POST Primary image bytes with retry/backoff (library refresh race).

        Soft-fails: returns ``ImageAttachResult`` instead of raising, so the
        worker ingest path can continue after a permanent upload failure.
        """
        if not item_id:
            return ImageAttachResult(
                ok=False,
                item_id="",
                attempts=0,
                status="missing_item_id",
                error="empty item_id",
            )

        path = Path(image_path)
        if not path.is_file() or path.stat().st_size <= 0:
            return ImageAttachResult(
                ok=False,
                item_id=item_id,
                attempts=0,
                status="missing_file",
                error=f"image not found or empty: {path}",
            )

        blob = path.read_bytes()
        ctype = image_content_type(path)
        api_path = f"/Items/{item_id}/Images/Primary"
        attempts = max(1, int(retries))
        last_error: str | None = None
        last_http: int | None = None

        for attempt in range(1, attempts + 1):
            retryable = False
            try:
                status, _body = self.request_raw(
                    "POST", api_path, blob, content_type=ctype
                )
                if 200 <= status < 300 or status == 204:
                    log.info(
                        "Primary image uploaded for %s (%s) attempt=%s",
                        item_id,
                        path.name,
                        attempt,
                    )
                    return ImageAttachResult(
                        ok=True,
                        item_id=item_id,
                        attempts=attempt,
                        status="uploaded",
                        http_status=status,
                    )
                last_http = status
                last_error = f"unexpected HTTP {status}"
                retryable = status in _RETRYABLE_HTTP
                log.info(
                    "Primary image upload attempt %s/%s for %s: %s",
                    attempt,
                    attempts,
                    item_id,
                    last_error,
                )
            except RuntimeError as exc:
                last_error = str(exc)
                last_http = _http_status_from_error(last_error)
                # Unknown transport errors: retry a few times; known non-retryable: stop.
                if last_http is None:
                    retryable = True
                else:
                    retryable = last_http in _RETRYABLE_HTTP
                log.info(
                    "Primary image upload attempt %s/%s for %s failed: %s",
                    attempt,
                    attempts,
                    item_id,
                    last_error,
                )

            if attempt >= attempts or not retryable:
                break
            sleep(backoff_sec * attempt)

        log.warning(
            "Primary image upload failed for %s after %s attempt(s): %s",
            item_id,
            attempt,
            last_error,
        )
        return ImageAttachResult(
            ok=False,
            item_id=item_id,
            attempts=attempt,
            status="failed",
            error=last_error,
            http_status=last_http,
        )

    def sessions(self, active_within_seconds: int = 60) -> list[dict[str, Any]]:
        """List active Jellyfin sessions (for idle-gate style checks)."""
        q = urllib.parse.urlencode({"activeWithinSeconds": active_within_seconds})
        data = self.request("GET", f"/Sessions?{q}")
        return data if isinstance(data, list) else []

    def _items_query(self, **params: str) -> list[dict[str, Any]]:
        """User-scoped Items query; empty list when user_id is unset."""
        if not self.user_id:
            return []
        q = urllib.parse.urlencode(params)
        data = self.request("GET", f"/Users/{self.user_id}/Items?{q}")
        items = (data or {}).get("Items") or []
        return items if isinstance(items, list) else []

    def find_item_for_media(self, media_path: str | Path) -> dict[str, Any] | None:
        """Resolve a catalog MP4 to a Jellyfin item, preferring Path + library scope.

        Safer than ``searchTerm`` alone: scores Path / filename / Name matches and
        scopes to ``library_id`` when configured.
        """
        if not self.user_id:
            return None

        media = Path(media_path)
        params: dict[str, str] = {
            "searchTerm": media.stem,
            "IncludeItemTypes": "Movie,Video",
            "Recursive": "true",
            "Fields": "Path,ImageTags,Tags,Overview",
            "Limit": "25",
        }
        if self.library_id:
            params["ParentId"] = self.library_id

        items = self._items_query(**params)
        best = pick_best_item(items, media)
        if best is not None:
            return best

        # Broader fallback without ParentId (misconfigured library_id).
        if self.library_id:
            params.pop("ParentId", None)
            items = self._items_query(**params)
            best = pick_best_item(items, media)
            if best is not None:
                return best

        return None

    def find_item_by_path_name(self, name: str) -> dict[str, Any] | None:
        """Legacy helper: treat ``name`` as a media stem or filename."""
        if not name:
            return None
        # If callers pass a bare stem (Phase 1), synthesize a path-like key.
        media = name if name.lower().endswith((".mp4", ".mkv", ".m4v")) else f"{name}.mp4"
        return self.find_item_for_media(media)

    def item_get_path(self, item_id: str) -> str:
        """Prefer user-scoped Item GET — bare ``/Items/{id}`` returns 400 on some builds."""
        if self.user_id:
            return f"/Users/{self.user_id}/Items/{item_id}"
        return f"/Items/{item_id}"

    def get_item(self, item_id: str) -> dict[str, Any]:
        """Fetch one item object via the preferred user-scoped GET path."""
        data = self.request("GET", self.item_get_path(item_id))
        if not isinstance(data, dict):
            raise RuntimeError(f"Jellyfin GET item {item_id} returned non-object")
        return data

    def delete_item(self, item_id: str) -> None:
        """Delete a library item by Id (Sheep Shears cascade). Uses ``DELETE /Items/{id}``."""
        if not item_id:
            raise ValueError("empty item_id")
        self.request("DELETE", f"/Items/{item_id}")

    def has_primary_image(self, item_id: str) -> bool:
        """True when ImageTags.Primary is present (False on fetch failure)."""
        try:
            item = self.get_item(item_id)
        except Exception:  # noqa: BLE001
            return False
        tags = item.get("ImageTags") or {}
        return bool(tags.get("Primary"))

    def add_tags(self, item_id: str, tags: list[str]) -> None:
        """Best-effort Jellyfin Items Tags write.

        Phase 1 license SoT is the on-disk sidecar (*.jellyflam3.json). Empty Items
        API Tags are acceptable for private-first deployments; commercial_mode /
        BrightScript commercialMode remain available when tags are present.
        """
        if not item_id or not tags:
            return
        # Merge with existing tags when possible
        existing: list[str] = []
        try:
            item = self.get_item(item_id)
            existing = list(item.get("Tags") or [])
        except Exception:  # noqa: BLE001
            pass
        merged = sorted(set(existing) | set(tags))
        try:
            self.request("POST", f"/Items/{item_id}/Tags", {"Tags": merged})
        except RuntimeError:
            log.info(
                "Jellyfin Items Tags not updated for %s (sidecar remains license SoT)",
                item_id,
            )

    def enrich_item_metadata(
        self,
        item_id: str,
        *,
        sheep_id: str,
        license: str = "unknown",
        tags: list[str] | None = None,
        duration_sec: float | None = None,
        edition: str | None = None,
    ) -> MetadataEnrichResult:
        """Best-effort Overview + SortName + Tags via full Item GET/POST.

        Soft-fails on 4xx/5xx. If the full Item POST fails, falls back to
        ``add_tags`` only (Phase 1 soft-fail path).
        """
        if not item_id:
            return MetadataEnrichResult(
                ok=False,
                item_id="",
                status="missing_item_id",
                error="empty item_id",
            )

        tag_list = list(tags or [])
        overview = build_flock_overview(
            sheep_id=sheep_id,
            license=license,
            tags=tag_list,
            duration_sec=duration_sec,
            edition=edition,
        )
        sort_name = build_flock_sort_name(sheep_id)

        try:
            item = self.get_item(item_id)

            existing_tags = list(item.get("Tags") or [])
            merged_tags = sorted(set(existing_tags) | set(tag_list))
            item["Overview"] = overview
            item["SortName"] = sort_name
            if merged_tags:
                item["Tags"] = merged_tags
            # ForcedSortName helps some Jellyfin builds keep custom sort.
            item["ForcedSortName"] = sort_name

            self.request("POST", f"/Items/{item_id}", item)
            log.info(
                "Jellyfin metadata enriched for %s (SortName=%s)",
                item_id,
                sort_name,
            )
            return MetadataEnrichResult(
                ok=True,
                item_id=item_id,
                status="enriched",
                overview=overview,
                sort_name=sort_name,
                tags=merged_tags or None,
            )
        except Exception as exc:  # noqa: BLE001
            log.info(
                "Jellyfin Item POST enrich failed for %s (%s); trying tags-only",
                item_id,
                exc,
            )
            try:
                self.add_tags(item_id, tag_list)
                return MetadataEnrichResult(
                    ok=True,
                    item_id=item_id,
                    status="tags_only",
                    error=str(exc),
                    overview=overview,
                    sort_name=sort_name,
                    tags=tag_list or None,
                )
            except Exception as tag_exc:  # noqa: BLE001
                log.info(
                    "Jellyfin metadata enrich failed for %s: %s",
                    item_id,
                    tag_exc,
                )
                return MetadataEnrichResult(
                    ok=False,
                    item_id=item_id,
                    status="failed",
                    error=str(tag_exc),
                    overview=overview,
                    sort_name=sort_name,
                )

    def ensure_commercial_collection(self, name: str = "commercial-safe") -> None:
        """Note commercial-safe policy; Phase 1 defaults to private (filter off)."""
        if not name:
            return
        log.info(
            "commercial collection '%s' optional; license.commercial_mode default false "
            "(sidecar SoT; enable filter only for venue/commercial-safe paths)",
            name,
        )

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "JellyfinClient":
        """Build a client from the ``jellyfin`` config section."""
        jf = cfg.get("jellyfin") or {}
        return cls(
            url=jf.get("url") or "",
            api_key=jf.get("api_key") or "",
            user_id=jf.get("user_id") or "",
            library_id=jf.get("library_id") or "",
        )
