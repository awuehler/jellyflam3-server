# 04 — Jellyfin library

## Boundary

Jellyfin server + library + API credentials — **stop before** worker automation.

## Tasks

1. Install Jellyfin (native package recommended for Phase 1):
   - Follow https://jellyfin.org/docs/general/installation/
2. Complete first-run wizard (admin user).
3. Add library **Sheep** → folder `/media/sheep/by-generation` (Movies or Home videos).
   - **Hard separation:** do **not** point Sheep at the `/media/sheep` mount root (that would also index `_refactor-preview`).
4. Add a second library (e.g. **Rework Poster** / **Refactor previews**) → `/media/sheep/_refactor-preview` for Phase 3 guide 09 palette/poster previews. Keep live Sheep `library_id` for Roku/Kodi. See [../phase3/09_SHEEP_REFACTOR.md](../phase3/09_SHEEP_REFACTOR.md).
5. Dashboard → API Keys → create key for JellyFlam3.
6. Note `userId` and library `ParentId` (live Sheep — not the preview library).
7. Fill `secrets.env` with `JELLYFIN_URL`, `JELLYFIN_API_KEY`, `JELLYFIN_USER_ID`, `JELLYFIN_LIBRARY_ID`.
8. Open firewall for `8096` on LAN (or Caddy/HTTPS for off-LAN).
9. Copy a test MP4 into `/media/sheep/by-generation/test/` and refresh library.
10. **Path 1:** Install https://github.com/jellyfin/jellyfin-roku ; confirm **Direct Play**.
11. Verify Sessions API with curl (Authorization MediaBrowser Token).

### Catalog permissions (trickplay / group write)

Jellyfin runs as user `jellyfin` and must be in group `jellyflam3`. It writes **`{stem}.trickplay/`** beside each MP4 when “Save trickplay images next to media” is on.

| Path | Mode | Why |
|---|---|---|
| `/media/sheep/by-generation` and gen folders (`243`, …) | **`2775`** (setgid + `rwxrwxr-x`) | Group can create `.trickplay` dirs |
| Catalog files (`*.mp4`, `*-poster.jpg`, `*.jellyflam3.json`) | **`664`** | Group-readable/writable |

`umask 022` + setgid parent alone yields **`2755`** (no group write) — that produces `UnauthorizedAccessException` on `.trickplay` in Jellyfin logs.

Repair / enforce:

```bash
# one-shot (also runs on jellyflam3-worker start)
cd /opt/jellyflam3-server
python3 -m pipeline.media_layout --config configs/jellyflam3.yaml
# verify jellyfin can mkdir
sudo -u jellyfin mkdir -p /media/sheep/by-generation/243/_perm_ok && sudo -u jellyfin rmdir /media/sheep/by-generation/243/_perm_ok
```

`/media/sheep/lost+found` stays root-only; directory-watcher warnings for it are expected noise.

See [10_TESTING_AND_ACCEPTANCE.md](10_TESTING_AND_ACCEPTANCE.md) for Path 1 sign-off.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `jellyfin` | binary | Sheep library server + Sessions / Items API |
| `scripts/install_jellyfin.sh` | script | Install notes wrapper for Jellyfin on Pi |
| `secrets.env` (`JELLYFIN_*`) | config | API credentials for worker / idle-gate / channel |
| `pipeline/media_layout.py` | pipeline | Enforce 2775/664 catalog perms for trickplay |
| `jellyfin-roku` | channel | Path 1 Direct Play baseline client |
| `/media/sheep` | mount | Catalog volume (not a Jellyfin library root) |
| `/media/sheep/by-generation` | config | Live **Sheep** Jellyfin library folder |
| `/media/sheep/_refactor-preview` | config | Preview Jellyfin library folder (guide 09) |

## Exit criteria

- [x] Sheep library points at `/media/sheep/by-generation` (not the mount root)
- [x] API key works from Pi localhost
- [x] jellyfin-roku Direct Plays a test MP4
- [x] `GET /Sessions` returns JSON
