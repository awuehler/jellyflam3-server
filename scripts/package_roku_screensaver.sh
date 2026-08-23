#!/usr/bin/env bash

# Purpose: Build sideloadable JellyFlam3 Roku Screensaver zip (Phase 3 guide 01).
# Requirements: bash; zip preferred else python3 with zipfile.
#
# Usage: ./scripts/package_roku_screensaver.sh [out.zip]
#
# When to run: Before Roku Screensaver sideload (Settings → Theme → Screensavers, not Home).
# Success: dist/jellyflam3-screensaver.zip with manifest at archive root.
# Note: Roku allows one sideload at a time — this zip replaces the VoD channel on that device.
# Docs: docs/phase3/01_SCREENSAVERS_AND_STILLS.md
#
# Assumptions: roku-screensaver/ has manifest, source/, components/, images/.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CHANNEL="$ROOT/roku-screensaver"
OUT="${1:-$ROOT/dist/jellyflam3-screensaver.zip}"

mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"

python3 "$ROOT/scripts/client_pack_presets.py" prepare --roku-registry "$CHANNEL/registry" || true

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
echo "NOTE: Roku allows one sideload at a time — this zip replaces jellyflam3-roku.zip on that device."
echo "      Pick under Settings -> Theme -> Screensavers (not Home). Re-sideload VoD when done."
ls -la "$OUT"
