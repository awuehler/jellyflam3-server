# 08 — Jellyfin ID dump (Roku Settings helper)

## Boundary

Ops helper to list Jellyfin **users, libraries, and item Guids** for pasting into the **JellyFlam3** Roku channel Settings registry. Shipped as a small script; not part of Phase 2 channel polish DoD.

**Status: complete** — Owner OK 2026-08-14 (fleet dump + `--items`; Settings paste; flock loads in Jellyfin + JellyFlam3 Roku).

## Intent

Operators often need stable IDs that the Dashboard UI does not surface clearly:

| Roku registry key (`JellyFlam3`) | Source in dump |
|---|---|
| `baseUrl` | `JELLYFIN_PUBLIC_URL` or LAN-facing URL (not `127.0.0.1` from the TV) |
| `apiKey` | `JELLYFIN_API_KEY` (masked unless `--show-secrets`) |
| `userId` | Users list / configured `JELLYFIN_USER_ID` |
| `libraryId` | Views / VirtualFolders ParentId (Sheep library) |
| — | Item Guids for deep-link smoke (`contentId=…`) |

## Commands

```bash
cd /opt/jellyflam3-server   # or repo root
# secrets.env must have JELLYFIN_URL + JELLYFIN_API_KEY (user/library optional)

python3 scripts/jellyfin_id_dump.py
python3 scripts/jellyfin_id_dump.py --items --limit 50
python3 scripts/jellyfin_id_dump.py --json --items > /tmp/jellyfin_ids.json
python3 scripts/jellyfin_id_dump.py --show-secrets   # full apiKey (careful)
```

## Furnace packaging (pre-configured client zips)

On a **furnace Pi** (`secrets.env` with `JELLYFIN_URL` + `JELLYFIN_API_KEY`), the sideload package scripts call `scripts/client_pack_presets.py` before zipping. That reuses this dump’s `resolve_creds` / `rokuSettings` logic — no separate manual step.

| Client zip | What gets baked in |
|---|---|
| `dist/jellyflam3-roku.zip` | `registry/jellyflam3-presets.json` → `applyJellyFlam3PackPresets()` on first launch (empty keys only) |
| `dist/jellyflam3-screensaver.zip` | Same preset file (screensaver can run without VoD Settings on a new Roku when built on furnace) |
| `dist/screensaver.jellyflam3.zip` | Kodi `settings.xml` `default=` attributes for `server_url`, `api_key`, `user_id`, `library_id` |

- **Per-host:** `16a` / `08a` / `04a` each emit zips for **that** Pi’s Jellyfin URL and library.
- **Non-furnace** (Windows dev box, laptop without `secrets.env`): presets are skipped; operators paste IDs manually (dump script or Dashboard).
- **Cache:** `dist/client-presets/jellyflam3-presets.json` (gitignored). Preset paths under `roku-*/registry/` are gitignored.
- **Security:** treat furnace-built zips like `jellyfin_id_dump.py --show-secrets` output — LAN-only distribution.

```bash
# Explicit (normally invoked by package_roku_* / package_kodi_screensaver):
python3 scripts/client_pack_presets.py prepare --roku-registry roku-channel/registry
python3 scripts/client_pack_presets.py prepare --kodi-settings kodi-screensaver/screensaver.jellyflam3/resources/settings.xml
```

## Guidelines

1. Prefer `JELLYFIN_PUBLIC_URL=http://<pi-lan-ip>:8096` so `baseUrl` is Roku-reachable (and matches furnace-built zips).
2. Do not commit dump output that includes `--show-secrets`, or furnace preset JSON / pre-filled zips.
3. `shuffleFlock` eligibility still uses archive gens only — item rows show `generation` when Path/Tags allow.
4. Deep link after dump: `curl -d '' "http://ROKU_IP:8060/launch/dev?contentId=ITEM_ID"`.

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `scripts/jellyfin_id_dump.py` | script | Dump users, libraries, optional item Guids |
| `scripts/client_pack_presets.py` | script | Bake dump settings into client zips on furnace hosts |
| `secrets.env` (`JELLYFIN_URL`, `JELLYFIN_API_KEY`, optional user/library) | config | Live Jellyfin auth (never commit dumps with `--show-secrets`) |
| Printed / `--json` Settings fields (`baseUrl`, `userId`, `libraryId`, masked `apiKey`) | ops | Paste into JellyFlam3 Roku registry (or auto via furnace zip) |
| `registry/jellyflam3-presets.json` (in Roku zips) | package | Furnace-built preset payload (gitignored in tree) |
| `--items` Guid rows | ops | Deep-link `contentId` smoke targets |

## Exit criteria

- [x] Script runs on lab Pi against live Jellyfin — fleet `16a` / `08a` / `04a` 2026-08-14
- [x] Printed `userId` / `libraryId` work in JellyFlam3 Settings → flock loads (Jellyfin + Roku TV app; Owner OK 2026-08-14)
- [x] Optional `--items` lists Guids usable as `contentId` — Guids listed on all three Pis (deep-link smoke available when needed)

### Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Owner | Project owner | 2026-08-14 | [x] |

## See also

[`scripts/jellyfin_id_dump.py`](../../scripts/jellyfin_id_dump.py) · [`scripts/client_pack_presets.py`](../../scripts/client_pack_presets.py) · [../phase1/08_ROKU_BRIGHTSCRIPT.md](../phase1/08_ROKU_BRIGHTSCRIPT.md) · [../phase2/04_ROKU_CHANNEL_POLISH.md](../phase2/04_ROKU_CHANNEL_POLISH.md) · [`roku-channel/README.md`](../../roku-channel/README.md)
