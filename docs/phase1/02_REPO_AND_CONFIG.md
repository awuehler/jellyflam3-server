# 02 — Repo and config

## Boundary

Repository scaffold + config schema — **stop before** compiling flam3.

## Tasks

1. Clone this repository onto the Pi (or sync via git). Symlink `/opt/jellyflam3-server` → the checkout.
2. Add interactive shell PATH / PYTHONPATH for user `jellyflam3` (idempotent):

   ```bash
   # JellyFlam3: Development
   export PATH="$PATH:/usr/local/bin:/home/jellyflam3/GitHub/jellyflam3-server/scripts:."
   export PYTHONPATH="/home/jellyflam3/GitHub/jellyflam3-server"
   ```

   Append those lines to `~/.bashrc` if missing (lab hosts already have this block).
3. Copy examples:
   ```bash
   cp configs/jellyflam3.yaml.example configs/jellyflam3.yaml
   cp secrets.env.example secrets.env
   ```
4. Edit `configs/jellyflam3.yaml` paths if mounts differ.
5. Confirm `.gitignore` excludes `secrets.env`, filled `configs/jellyflam3.yaml`, scratch, and MP4s.
6. **Secrets hygiene (required):**
   - `secrets.env` and `configs/jellyflam3.yaml` are **host-local** — one API key / library ID set per Pi.
   - Never `git add` them; never commit; never push. Prefer `cp *.example` then edit on the Pi only.
   - Do **not** scp filled secrets between Pis or restore them from shared git history (stale keys → idle-gate **401**).
   - If either file was ever committed: `git rm --cached secrets.env configs/jellyflam3.yaml`, commit the removal, **rotate the Jellyfin API key**, rewrite `secrets.env` on each host.
   - Verify: `git check-ignore -v secrets.env configs/jellyflam3.yaml` and `git ls-files secrets.env configs/jellyflam3.yaml` (must be empty).
7. Read [docs/README.md](../README.md) and phase1 guide index.

## Config keys (summary)

| Section | Purpose |
|---|---|
| `paths` | inbox, scratch, library, status |
| `vod` | 7–37 s band, fps 24, nframes 552 default (~23 s); smoke 13 s |
| `idle_gate` | poll, idle_delay, TV patterns |
| `jellyfin` | URL / ids (prefer env) |
| `license` | commercial filter tags |
| `encode` | H.264 High 4.2 profile |

## Artifacts

| Artifact | Kind | Role |
|---|---|---|
| `configs/jellyflam3.yaml.example` → `configs/jellyflam3.yaml` | config | Local runtime config (paths, vod, idle_gate, jellyfin, license, encode) |
| `secrets.env.example` → `secrets.env` | config | Jellyfin URL / API key / user / library (gitignored) |
| `.gitignore` | config | Exclude secrets, scratch, catalog MP4s |
| `docs/Pi5_Flam3_VoD_Pipeline.md` | config | Architecture SoT |
| `docs/phase1/*` | config | Phase 1 numbered guides |

## Exit criteria

- [x] Repo present on Pi
- [x] `configs/jellyflam3.yaml` and `secrets.env` exist locally (not committed)
- [x] Secrets hygiene documented (host-local keys; never commit / never share across Pis)
- [x] `docs/Pi5_Flam3_VoD_Pipeline.md` and `docs/phase1/*` present
- [x] No secrets staged in git
