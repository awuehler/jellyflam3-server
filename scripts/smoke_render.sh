#!/usr/bin/env bash

# Purpose: Short end-to-end render smoke (~13 s / nframes=312 @ 24 fps); never publish to catalog.
# Requirements: bash, python3, PyYAML; flam3-genome/animate + ffmpeg/ffprobe for a full run.
#          This script prepends /usr/local/bin (flam3 make install).
#
# Usage: ./scripts/smoke_render.sh [config.yaml]
#
# When to run: After install_flam3.sh; Phase 3 RC pedigree smoke (docs/phase3/10).
# Success: prints SMOKE_RENDER_OK (MP4 under smoke scratch, not media_library).
# Fail: missing flam3-genome, ffmpeg, or worker --once error (non-zero exit).
# Docs: docs/phase1/05_RENDER_PIPELINE.md
#
# Assumptions: JELLYFLAM3_SMOKE=1; scratch under JELLYFLAM3_SMOKE_ROOT or /var/cache/.../smoke or .smoke.
# Env: JELLYFLAM3_SMOKE_PREPEND_LOCAL=0 — do not prepend /usr/local/bin (gate tests only).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Prefer /usr/local/bin (flam3 make install) on non-login shells.
# Gate tests set JELLYFLAM3_SMOKE_PREPEND_LOCAL=0 so a stripped PATH fails fast
# (do not re-inject /usr/local/bin and accidentally run a full smoke render).
if [[ "${JELLYFLAM3_SMOKE_PREPEND_LOCAL:-1}" != "0" ]]; then
  export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"
fi

if ! command -v flam3-genome >/dev/null 2>&1; then
  echo "ERROR: flam3-genome not on PATH — install via scripts/install_flam3.sh on the Pi" >&2
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "ERROR: ffmpeg not on PATH" >&2
  exit 1
fi

export JELLYFLAM3_SMOKE=1
CFG="${1:-configs/jellyflam3.yaml}"
if [[ ! -f "$CFG" ]]; then
  CFG="configs/jellyflam3.yaml.example"
fi

# Prefer NVMe scratch when present; else repo-local .smoke
if [[ -z "${JELLYFLAM3_SMOKE_ROOT:-}" ]]; then
  if [[ -d /var/cache/jellyflam3 && -w /var/cache/jellyflam3 ]]; then
    JELLYFLAM3_SMOKE_ROOT=/var/cache/jellyflam3/smoke
  else
    JELLYFLAM3_SMOKE_ROOT="$ROOT/.smoke"
  fi
fi
export JELLYFLAM3_SMOKE_ROOT
mkdir -p "$JELLYFLAM3_SMOKE_ROOT"/{frames,jobs,media,inbox,quarantine}

# Lightweight template for smoke (full TV template is heavy even at 13 s)
SMOKE_TEMPLATE="${SMOKE_TEMPLATE:-$ROOT/configs/templates/electricsheep.smoke.480p.flam3}"
if [[ ! -f "$SMOKE_TEMPLATE" ]]; then
  SMOKE_TEMPLATE="$ROOT/configs/templates/electricsheep.tv.1080p.flam3"
fi

python3 - <<PY
from pathlib import Path
import os, yaml

root = Path(os.environ["JELLYFLAM3_SMOKE_ROOT"])
example = Path("$CFG")
cfg = yaml.safe_load(example.read_text())
cfg["paths"]["frames_scratch"] = str(root / "frames")
cfg["paths"]["jobs_dir"] = str(root / "jobs")
cfg["paths"]["media_library"] = str(root / "media")
cfg["paths"]["genomes_inbox"] = str(root / "inbox")
cfg["paths"]["genomes_quarantine"] = str(root / "quarantine")
cfg["paths"]["status_file"] = str(root / "idle_gate_status.json")
cfg["paths"]["template"] = "$SMOKE_TEMPLATE"
cfg["idle_gate"]["enabled"] = False
cfg["jellyfin"]["api_key"] = ""
cfg["render"]["free_space_gb_min"] = 0.1
cfg["render"]["target_width"] = 640
cfg["render"]["target_height"] = 360
out = root / "smoke.yaml"
out.write_text(yaml.safe_dump(cfg))
print(out)
PY

SMOKE_YAML="$JELLYFLAM3_SMOKE_ROOT/smoke.yaml"
SEED="${SMOKE_SEED:-genomes/pedigree/smoke/electricsheep.pedigree.smoke.0001.flam3}"
if [[ ! -f "$SEED" ]]; then
  SEED="genomes/pedigree/examples/electricsheep.pedigree.mutate.9334119d.flam3"
fi

if ! python3 -c "import yaml" 2>/dev/null; then
  echo "ERROR: PyYAML required: sudo apt install -y python3-yaml" >&2
  exit 1
fi

python3 -m pipeline.worker --config "$SMOKE_YAML" --once "$SEED"
OUT_MP4="$(find "$JELLYFLAM3_SMOKE_ROOT/media" -name '*.mp4' -type f | head -1 || true)"
if [[ -n "$OUT_MP4" ]]; then
  echo "Smoke MP4: $OUT_MP4"
  ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,pix_fmt \
    -of default=noprint_wrappers=1 "$OUT_MP4" || true
else
  echo "ERROR: no MP4 found under $JELLYFLAM3_SMOKE_ROOT/media" >&2
  exit 1
fi
echo "SMOKE_RENDER_OK"
echo "Smoke complete under $JELLYFLAM3_SMOKE_ROOT/media"
