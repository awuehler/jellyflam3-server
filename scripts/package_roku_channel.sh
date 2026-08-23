#!/usr/bin/env bash

# Purpose: Build a sideloadable Roku channel zip for the Developer Application Installer.
# Requirements: bash; zip preferred, else python3 with zipfile.
#
# Usage: ./scripts/package_roku_channel.sh [out.zip]
#
# When to run: Before sideload / Phase 3 RC packaging. Default: dist/jellyflam3-roku.zip
# Success: Zip entries at archive root (manifest, source/, components/, images/) — not a nested folder.
# Fail: Missing roku-channel/ tree. Roku allows one sideload at a time (replaces screensaver zip).
# Docs: docs/phase2/04_ROKU_CHANNEL_POLISH.md ; docs/phase3/10_TESTING_AND_ACCEPTANCE.md
#
# Assumptions: roku-channel/ has manifest, source/, components/, images/ at archive root.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHANNEL="$ROOT/roku-channel"
OUT="${1:-$ROOT/dist/jellyflam3-roku.zip}"

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"

python3 "$ROOT/scripts/client_pack_presets.py" prepare --roku-registry "$CHANNEL/registry" || true

# Roku expects zip contents at archive root (manifest, source/, components/, images/, registry/)
ZIP_DIRS=(manifest source components images)
if [[ -f "$CHANNEL/registry/jellyflam3-presets.json" ]]; then
  ZIP_DIRS+=(registry)
fi
(
  cd "$CHANNEL"
  if command -v zip >/dev/null 2>&1; then
    zip -r -9 "$OUT" "${ZIP_DIRS[@]}" \
      -x "*.git*" -x "*__MACOSX*" -x "*.DS_Store" -x "images/.gitkeep" -x "registry/.gitkeep"
  else
    python3 - <<PY
import zipfile
from pathlib import Path
channel = Path(r"$CHANNEL")
out = Path(r"$OUT")
skip = {".gitkeep", ".DS_Store"}
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(channel / "manifest", "manifest")
    for folder in ("source", "components", "images", "registry"):
        d = channel / folder
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.name not in skip and p.name != ".gitkeep":
                zf.write(p, p.relative_to(channel).as_posix())
print(out)
PY
  fi
)

echo "Sideload package: $OUT"
echo "Upload via https://<roku-ip> (dev password) → Installer → Upload"
ls -la "$OUT"
