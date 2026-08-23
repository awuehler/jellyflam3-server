#!/usr/bin/env bash

# Purpose: Build installable Kodi screensaver zip (Phase 3 guide 02).
#
# Requirements: bash; zip preferred else python3.
#
# Usage: ./scripts/package_kodi_screensaver.sh [out.zip]
#
# When to run: Before Kodi install-from-zip on rpi-kodi-01a (or any Kodi 21 host).
# Success: dist/screensaver.jellyflam3.zip with zip root screensaver.jellyflam3/ (addon.xml).
# Docs: docs/phase3/02_KODI_ELECTRIC_SHEEP_SCREENSAVER.md
#
# Zip root is screensaver.jellyflam3/ (Kodi install-from-zip convention).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ADDON_ID="screensaver.jellyflam3"
SRC="$ROOT/kodi-screensaver/$ADDON_ID"
STAGE="$ROOT/dist/kodi-stage/$ADDON_ID"
OUT="${1:-$ROOT/dist/screensaver.jellyflam3.zip}"

if [[ ! -f "$SRC/addon.xml" ]]; then
  echo "missing addon: $SRC/addon.xml" >&2
  exit 1
fi

python3 "$ROOT/scripts/build_kodi_screensaver_assets.py"

mkdir -p "$(dirname "$OUT")" "$STAGE"
rm -f "$OUT"
rm -rf "$STAGE"
mkdir -p "$STAGE"

if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude '.gitkeep' --exclude '__pycache__' --exclude '*.pyc' --exclude 'posters' "$SRC/" "$STAGE/"
else
  python3 - <<PY
import shutil
from pathlib import Path
src = Path(r"$SRC")
dst = Path(r"$STAGE")
skip_names = {".gitkeep"}
for p in src.rglob("*"):
    if not p.is_file():
        continue
    if p.name in skip_names or p.suffix == ".pyc":
        continue
    if "__pycache__" in p.parts or "posters" in p.parts:
        continue
    rel = p.relative_to(src)
    dest = dst / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dest)
PY
fi

python3 "$ROOT/scripts/client_pack_presets.py" prepare \
  --kodi-settings "$STAGE/resources/settings.xml" || true

(
  cd "$ROOT/dist/kodi-stage"
  if command -v zip >/dev/null 2>&1; then
    zip -r -0 "$OUT" "$ADDON_ID" \
      -x "*.git*" -x "*__MACOSX*" -x "*.DS_Store" -x "*.gitkeep" -x "*__pycache__*" -x "*.pyc" -x "*posters*"
  else
    python3 - <<PY
import zipfile
from pathlib import Path
root = Path(r"$ROOT/dist/kodi-stage")
out = Path(r"$OUT")
skip = {".gitkeep", ".DS_Store"}
with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:
    for p in (root / "$ADDON_ID").rglob("*"):
        if not p.is_file() or p.name in skip or p.suffix == ".pyc":
            continue
        if "__pycache__" in p.parts or "posters" in p.parts:
            continue
        zf.write(p, p.relative_to(root).as_posix())
print(out)
PY
  fi
)

echo "Kodi screensaver package: $OUT"
echo "Install from zip in Kodi, then Settings -> Interface -> Screensaver -> JellyFlam3 Dreams"
ls -la "$OUT"
