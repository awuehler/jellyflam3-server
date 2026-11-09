#!/usr/bin/env bash

# Purpose: Build a sideloadable Roku channel zip for the Developer Application Installer.
# Requirements: bash; zip preferred, else python3 with zipfile.
#
# Usage: ./scripts/package_roku_channel.sh [--no-presets] [--cert] [--from-package-profile] [out.zip]
#   --no-presets            Channel Store zip: skip Jellyfin presets (empty Settings).
#   --cert                  Embed the committed Funnel lab presets
#                           (roku-channel/registry/jellyflam3-presets.json) as-is.
#                           Do not regenerate from secrets.env (that would bake LAN).
#   --from-package-profile  Embed Office Settings captured at
#                           /var/lib/jellyflam3/roku-package-profile.json literally.
#                           Do not combine with --cert (Office values win).
#
# When to run: Before sideload / Phase 3 RC packaging. Default: dist/jellyflam3-roku.zip
# Success: Zip entries at archive root (manifest, source/, components/, images/) — not a nested folder.
# Fail: Missing roku-channel/ tree. Roku allows one sideload at a time (replaces screensaver zip).
# Docs: docs/phase4/04_ROKU_PUBLISH.md (cert presets); docs/phase2/04_ROKU_CHANNEL_POLISH.md
#
# Assumptions: roku-channel/ has manifest, source/, components/, images/ at archive root.
# Cert: committed jellyflam3-presets.json must exist (Funnel baseUrl, HLS, displaySinkUrl).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHANNEL="$ROOT/roku-channel"
OUT="$ROOT/dist/jellyflam3-roku.zip"
NO_PRESETS=0
CERT=0
FROM_PROFILE=0
for arg in "$@"; do
  case "$arg" in
    --no-presets) NO_PRESETS=1 ;;
    --cert) CERT=1 ;;
    --from-package-profile) FROM_PROFILE=1 ;;
    *) OUT="$arg" ;;
  esac
done
if [[ "$FROM_PROFILE" -eq 1 && "$CERT" -eq 1 ]]; then
  echo "package_roku_channel: use --from-package-profile or --cert, not both" >&2
  exit 2
fi

# zip runs after cd into roku-channel/; relative OUT would land under that tree.
if [[ "$OUT" != /* ]]; then
  OUT="$ROOT/$OUT"
fi

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"

PRESETS="$CHANNEL/registry/jellyflam3-presets.json"
if [[ "$NO_PRESETS" -eq 0 ]]; then
  if [[ "$FROM_PROFILE" -eq 1 ]]; then
    python3 "$ROOT/scripts/client_pack_presets.py" prepare \
      --roku-registry "$CHANNEL/registry" \
      --from-package-profile
  elif [[ "$CERT" -eq 1 ]]; then
    if [[ ! -f "$PRESETS" ]]; then
      echo "package_roku_channel: --cert needs committed $PRESETS" >&2
      exit 2
    fi
    echo "package_roku_channel: --cert using committed jellyflam3-presets.json"
  else
    # Household furnace fill (LAN Jellyfin). Overwrites the working tree presets;
    # restore with git checkout -- roku-channel/registry/jellyflam3-presets.json
    # before committing. Release CI uses --no-presets instead.
    python3 "$ROOT/scripts/client_pack_presets.py" prepare --roku-registry "$CHANNEL/registry" || true
  fi
fi

# Roku expects zip contents at archive root (manifest, source/, components/, images/, registry/)
ZIP_DIRS=(manifest source components images)
if [[ "$NO_PRESETS" -eq 0 && -f "$CHANNEL/registry/jellyflam3-presets.json" ]]; then
  ZIP_DIRS+=(registry)
fi
(
  cd "$CHANNEL"
  if command -v zip >/dev/null 2>&1; then
    zip -r -9 "$OUT" "${ZIP_DIRS[@]}" \
      -x "*.git*" -x "*__MACOSX*" -x "*.DS_Store" -x "images/.gitkeep" -x "registry/.gitkeep" \
      -x "images/*-[0-9][0-9].png"
  else
    python3 - <<PY
import zipfile
from pathlib import Path
channel = Path(r"$CHANNEL")
out = Path(r"$OUT")
skip = {".gitkeep", ".DS_Store"}
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(channel / "manifest", "manifest")
    folders = ("source", "components", "images")
    if r"$NO_PRESETS" == "0":
        folders = folders + ("registry",)
    for folder in folders:
        d = channel / folder
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.name not in skip and p.name != ".gitkeep":
                # Numbered PNGs are source-art revisions, not package assets.
                if p.suffix.lower() == ".png" and p.stem[-3:-2] == "-" and p.stem[-2:].isdigit():
                    continue
                zf.write(p, p.relative_to(channel).as_posix())
print(out)
PY
  fi
)

echo "Sideload package: $OUT"
echo "Upload via https://<roku-ip> (dev password) → Installer → Upload"
ls -la "$OUT"
