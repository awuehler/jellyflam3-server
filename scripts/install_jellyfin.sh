#!/usr/bin/env bash

# Purpose: Print Jellyfin install/setup notes for Debian/Ubuntu/Pi OS (does not auto-install).
#
# Requirements: bash; apt-get optional for the suggested install line.
# Usage: ./scripts/install_jellyfin.sh
#
# When to run: After bootstrap_pi.sh; read the printed notes, then follow official Jellyfin Linux docs.
# Success: This script always prints and exits 0 — it does not apt-install. Confirm jellyfin can write
#   CachePath/MetadataPath (see body) before first-run Dashboard.
# Docs: docs/phase1/04_JELLYFIN_LIBRARY.md ; lab reference host rpi-jellyflam3-08a
#
# Assumptions: Operator follows official Jellyfin docs; post-steps match JellyFlam3 guides
#   (lab reference: rpi-jellyflam3-08a). Paths use /var/cache/jellyflam3 + /var/lib/jellyflam3.

set -euo pipefail

cat <<'EOF'
Install Jellyfin (official repo for your distro):
  https://jellyfin.org/docs/general/installation/linux/

========================================================================
0) BEFORE first-run / BEFORE changing Cache & Metadata paths — permissions
========================================================================
Jellyfin runs as user `jellyfin`. If CachePath / MetadataPath are not group-writable
(or owned so jellyfin can create temp/metadata files), the web UI often fails with an
Axios error and the Jellyfin log shows PermissionDenied / UnauthorizedAccessException
creating temporary files.

Lab layout (rpi-jellyflam3-08a):
  /var/cache/jellyflam3  → CachePath   (mode 0775, owner jellyflam3:jellyflam3)
  /var/lib/jellyflam3    → MetadataPath (mode 0775, owner jellyflam3:jellyflam3)
  jellyfin ∈ group jellyflam3  (and jellyflam3 ∈ group jellyfin)
  jellyfin also needs video/render groups for V4L2 encode when used

Prep (adjust USER if your login is not jellyflam3):

  sudo mkdir -p /var/cache/jellyflam3/{frames,transcodes,images} \
                /var/lib/jellyflam3/{jobs,logs,library,display_profiles}
  sudo chown -R jellyflam3:jellyflam3 /var/cache/jellyflam3 /var/lib/jellyflam3
  sudo chmod 775 /var/cache/jellyflam3 /var/lib/jellyflam3
  sudo usermod -aG jellyflam3 jellyfin          # jellyfin can write group dirs
  sudo usermod -aG jellyfin jellyflam3          # lab: mutual membership (08a)
  sudo usermod -aG video,render jellyfin        # V4L2 / DRM encode devices
  # Jellyfin-owned scratch under those roots (matches 08a):
  sudo mkdir -p /var/cache/jellyflam3/transcodes /var/lib/jellyflam3/library
  sudo chown jellyfin:jellyfin /var/cache/jellyflam3/transcodes /var/lib/jellyflam3/library
  sudo chmod 775 /var/cache/jellyflam3/transcodes
  sudo systemctl restart jellyfin

Verify jellyfin can write before pointing Dashboard paths here:

  sudo -u jellyfin touch /var/cache/jellyflam3/.write_ok /var/lib/jellyflam3/.write_ok \
    && sudo rm -f /var/cache/jellyflam3/.write_ok /var/lib/jellyflam3/.write_ok

Sheep catalog trickplay also needs group-write under /media/sheep — see
docs/phase1/04_JELLYFIN_LIBRARY.md and: python3 -m pipeline.media_layout

========================================================================
1) First-run wizard
========================================================================
  Open http://<pi>:8096 and complete the wizard.
  Guide: https://jellyfin.org/docs/general/post-install/setup-wizard

========================================================================
2) Cache path + Metadata path (required for JellyFlam3 lab layout)
========================================================================
  Dashboard → Administration → Dashboard → Paths (label may be Host / Paths
  depending on Jellyfin version), set:

    Cache path:    /var/cache/jellyflam3
    Metadata path: /var/lib/jellyflam3

  Equivalent in /etc/jellyfin/system.xml then restart jellyfin:

    <CachePath>/var/cache/jellyflam3</CachePath>
    <MetadataPath>/var/lib/jellyflam3</MetadataPath>

  Remux/HLS segments land under /var/cache/jellyflam3/transcodes (must stay
  writable by jellyfin). Gold Sheep Lite H.264+AAC remux needs no encoding.xml
  change for Direct Stream / HLS remux.

========================================================================
3) Library, API key, ParentId (libraryId)
========================================================================
  • Add library Sheep → folder /media/sheep/by-generation (Movies or Home videos).
    Hard separation: do NOT point Sheep at /media/sheep mount root.
  • Add library Rework Poster (or Refactor previews) → /media/sheep/_refactor-preview
    (Phase 3 guide 09). Keep Roku/Kodi on live Sheep library Id only.
  • Dashboard → API Keys → create a key for JellyFlam3.
  • ParentId = the Sheep library id (secrets.env JELLYFIN_LIBRARY_ID / Roku libraryId).

  How to find ParentId:
    A) Preferred — after secrets.env has URL + API key:
         cd /opt/jellyflam3-server
         python3 scripts/jellyfin_id_dump.py
       Prints userId and libraryId (Views / VirtualFolders ParentId). See
       docs/phase3/08_JELLYFIN_ID_DUMP.md.
    B) Dashboard: open the Sheep library; the item id in the browser URL
       (…/details?id=… or similar) for the library root is the ParentId.
    C) API (API key header Authorization: MediaBrowser Token="KEY"):
         curl -sH 'Authorization: MediaBrowser Token=KEY' \
           http://127.0.0.1:8096/Library/VirtualFolders
       Use the Id for the Sheep /media/sheep/by-generation entry (not Rework Poster).

  Fill secrets.env (from secrets.env.example):
    JELLYFIN_URL, JELLYFIN_API_KEY, JELLYFIN_USER_ID, JELLYFIN_LIBRARY_ID

========================================================================
4) Playback / transcoding — recommend V4L2 HW acceleration (Pi)
========================================================================
  Dashboard → Playback → Transcoding:
    Hardware acceleration → Video4Linux2 (V4L2)
  Lab encoding.xml value: <HardwareAccelerationType>v4l2m2m</HardwareAccelerationType>
  Enable hardware encoding when the UI offers it. Remux/Direct Stream for Gold
  Sheep Lite still prefers copy; V4L2 helps when Jellyfin must re-encode.

========================================================================
5) Quick checks
========================================================================
  curl -H 'Authorization: MediaBrowser Token=KEY' http://127.0.0.1:8096/Sessions
  HLS smoke (Phase 2 guide 03): ./scripts/hls_smoke.sh
  Path 1: jellyfin-roku; Path 2 JellyFlam3 uses main.m3u8 + AudioCodec=aac

Note: long-running HLS VoD may log WRN 'no transcode is running' for .ts segments
      after the remux job ends — see docs/phase2/03_HLS_CLIENT_STREAMING.md

EOF

if command -v apt-get >/dev/null 2>&1; then
  echo "If the Jellyfin apt repo is already configured:"
  echo "  sudo apt update && sudo apt install -y jellyfin"
fi
