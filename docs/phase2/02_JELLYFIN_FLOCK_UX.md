# 02 — Jellyfin flock UX

## Boundary

Catalog posters, thumbnails, and browse metadata for the Sheep library in **Jellyfin web** and **jellyfin-roku** — **stop before** HLS client streaming ([03](03_HLS_CLIENT_STREAMING.md)) / JellyFlam3 channel polish ([04](04_ROKU_CHANNEL_POLISH.md)).

## Problem

Ingested MP4s often lack useful Primary images; Jellyfin and jellyfin-roku show empty/generic posters.

## Guidelines (locked)

1. After successful encode in `pipeline/worker.py`, extract a **mid-loop** frame with `ffmpeg`.
2. Write a poster file beside the MP4 under `/media/sheep/by-generation/…` (Jellyfin-friendly naming) **and** upload via Jellyfin Images API (`POST .../Items/{id}/Images/Primary`) with **retry/backoff** after `refresh_library` (item Id race).
3. Enrich `*.jellyflam3.json` sidecar; best-effort Items Overview / SortName / tags.
4. Provide a **backfill** path for existing catalog MP4s (one-shot script or worker flag).
5. Verify in Jellyfin web **and** stock jellyfin-roku (custom channel is guide 03).

## Implementation notes

- Extend [`pipeline/jellyfin_client.py`](../../pipeline/jellyfin_client.py) with image upload + safer item lookup than fuzzy `searchTerm` alone.
- Repo `*.png` gitignore is fine — posters live on the flock disk, not in git.
- Phase 1 Tags soft-fail remains acceptable; Overview updates may need full Item POST (test against installed Jellyfin version).

### Landed helpers (pieces A–F)

| Piece | Status | Notes |
|---|---|---|
| **A** Mid-loop poster extract | Done | [`pipeline/poster.py`](../../pipeline/poster.py) — `{stem}-poster.jpg` beside MP4 |
| **B** Safer item lookup | Done | `JellyfinClient.find_item_for_media` — library-scoped Path/Name scoring; `find_item_by_path_name` delegates |
| **C** Images API upload + retry | Done | `JellyfinClient.upload_primary_image` — binary `POST .../Images/Primary`, retry/backoff on 404/race, soft-fail `ImageAttachResult` |
| **D** Wire into new ingest | Done | [`pipeline/flock_artwork.py`](../../pipeline/flock_artwork.py) via `worker.process_genome` — extract → refresh → resolve → Primary; sidecar `poster` / `poster_path` / `jellyfin_image` |
| **E** Metadata enrich | Done | `enrich_item_metadata` — Overview / SortName / Tags via Item GET+POST; tags-only fallback; sidecar `jellyfin_metadata` |
| **F** Backfill flock | Done | `python -m pipeline.backfill_posters` — scan catalog MP4s; idle-gate aware; rate-limited; `--dry-run` / `--limit` / `--force` / `--poster-only` |
| **G** Lab acceptance | Done | Owner confirmed Primary thumbnails in Jellyfin web, jellyfin-roku, JellyFlam3 Roku app, and `/media/sheep/by-generation` (2026-07-31) |

### Lab backfill (piece F)

```bash
# Preview
python -m pipeline.backfill_posters --config configs/jellyflam3.yaml --dry-run

# Small batch first, then full flock when idle
python -m pipeline.backfill_posters --config configs/jellyflam3.yaml --limit 10 --interval-sec 2
python -m pipeline.backfill_posters --config configs/jellyflam3.yaml --interval-sec 1
```

Skips sheep whose sidecar already shows poster + Primary (`uploaded` / `local_primary`) + metadata enrich (use `--force` to redo). One Library/Refresh at batch start (not per item).

**Ops note (lab):** Jellyfin must be able to write media folders and `MetadataPath` (`/var/lib/jellyflam3` on the Pi). Add `jellyfin` to the `jellyflam3` group and `g+rwX` (setgid) on `/media/sheep/by-generation` + MetadataPath, then restart Jellyfin. Client prefers user-scoped Item GET and treats FS `{stem}-poster.jpg` + `ImageTags.Primary` as success (`local_primary`) before Images API upload.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `pipeline/poster.py` | pipeline | Mid-loop `{stem}-poster.jpg` extract |
| `pipeline/flock_artwork.py` | pipeline | Ingest artwork + metadata enrich |
| `pipeline/jellyfin_client.py` | pipeline | Item lookup + Primary Images API upload |
| `pipeline/backfill_posters.py` | pipeline | One-shot flock poster / metadata backfill |
| `ffmpeg` | binary | Mid-loop frame grab |
| `jellyfin` Images API | binary | Primary image attach |

## Exit criteria

- [x] New ingest / catalog items produce Primary image visible in Jellyfin web
- [x] Same items show poster in jellyfin-roku (and JellyFlam3 Roku app)
- [x] Sidecar records poster/path or image attach status; FS `{stem}-poster.jpg` under `/media/sheep/by-generation`
- [x] Backfill documented and run on lab flock (`python -m pipeline.backfill_posters`)
- [x] Unit or integration smoke for image attach helper (`tests/test_jellyfin_client.py`, `tests/test_flock_artwork.py`, `tests/test_backfill_posters.py`)

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | | 2026-07-31 | [x] |

Guide 02 complete. Next: [03_HLS_CLIENT_STREAMING.md](03_HLS_CLIENT_STREAMING.md).

## See also

[../phase1/04_JELLYFIN_LIBRARY.md](../phase1/04_JELLYFIN_LIBRARY.md) · Architecture posters note in design choices locked.
