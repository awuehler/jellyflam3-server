#!/usr/bin/env bash

# Purpose: Build and install flam3; verify flam3 + ffmpeg toolchain (guide 03).
# Requirements: bash, sudo, apt (unless --skip-apt), git, build-essential, autotools, libxml2/png/jpeg.
#
# Usage:
#   ./scripts/install_flam3.sh              # apt deps (if needed) + build + verify
#   ./scripts/install_flam3.sh --skip-apt   # build only (deps already installed)
#   ./scripts/install_flam3.sh --verify     # check binaries only
#   ./scripts/install_flam3.sh --smoke      # after install, run smoke_render.sh
# Env: FLAM3_SRC (default $HOME/src/flam3), FLAM3_PREFIX (default /usr/local).
#
# When to run: New Pi after bootstrap_pi.sh; --verify after PATH changes or before RC smoke.
# Success: flam3-genome/animate/render + ffmpeg/ffprobe on PATH (prefix/bin, usually /usr/local/bin).
# Docs: docs/phase1/03_FLAM3_TOOLCHAIN.md
#
# Assumptions: Clone/build scottdraves/flam3; PATH includes $PREFIX/bin after install.

set -euo pipefail

# flam3 make install lands in $PREFIX/bin (default /usr/local/bin).
export PATH="${FLAM3_PREFIX:-/usr/local}/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SKIP_APT=0
VERIFY_ONLY=0
RUN_SMOKE=0
PREFIX="${FLAM3_PREFIX:-/usr/local}"
SRC="${FLAM3_SRC:-$HOME/src/flam3}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-apt) SKIP_APT=1; shift ;;
    --verify) VERIFY_ONLY=1; shift ;;
    --smoke) RUN_SMOKE=1; shift ;;
    -h|--help)
      sed -n '2,18p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Confirm flam3 + ffmpeg tools on PATH; soft-check for an H.264 encoder.
verify_tools() {
  local missing=0
  echo "== verify toolchain =="
  for t in flam3-genome flam3-animate flam3-render ffmpeg ffprobe; do
    if command -v "$t" >/dev/null 2>&1; then
      echo "  OK  $t -> $(command -v "$t")"
    else
      echo "  MISSING  $t"
      missing=1
    fi
  done
  if [[ "$missing" -ne 0 ]]; then
    echo "Toolchain incomplete." >&2
    return 1
  fi
  # quick capability probes
  ffmpeg -hide_banner -encoders 2>/dev/null | grep -qiE 'libx264|h264_v4l2m2m|h264_vaapi' \
    && echo "  OK  ffmpeg H.264 encoder available" \
    || echo "  WARN  no obvious H.264 encoder in ffmpeg -encoders"
  echo "flam3 + ffmpeg OK"
  return 0
}

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  verify_tools
  exit $?
fi

if [[ "$SKIP_APT" -eq 0 ]]; then
  echo "== apt dependencies =="
  sudo apt update
  sudo apt install -y build-essential automake autoconf libtool pkg-config \
    libxml2-dev libpng-dev libjpeg-dev zlib1g-dev git ffmpeg
else
  echo "== apt dependencies =="
  echo "  skipped (--skip-apt)"
fi

echo "== flam3 source ($SRC) =="
mkdir -p "$(dirname "$SRC")"
if [[ ! -d "$SRC/.git" ]]; then
  git clone https://github.com/scottdraves/flam3.git "$SRC"
else
  echo "  existing clone; fetching…"
  git -C "$SRC" fetch --tags --prune || true
fi

cd "$SRC"
echo "== configure / build =="
# Refresh autotools; upstream config.guess can be too old for aarch64 / Pi OS.
if [[ -x ./autogen.sh ]]; then
  ./autogen.sh
else
  libtoolize --force 2>/dev/null || true
  autoreconf -fi 2>/dev/null || {
    aclocal
    autoheader 2>/dev/null || true
    automake --add-missing --copy 2>/dev/null || true
    autoconf
  }
fi

# Re-run configure for prefix / fresh tree
./configure --prefix="$PREFIX"

make -j"$(nproc)"
sudo make install
sudo ldconfig

# Ensure PATH sees prefix bin in this shell
export PATH="${PREFIX}/bin:${PATH}"

verify_tools

if [[ "$RUN_SMOKE" -eq 1 ]]; then
  echo "== smoke render =="
  # Prefer repo venv-less python; ensure PyYAML for smoke helper
  if ! python3 -c "import yaml" 2>/dev/null; then
    sudo apt install -y python3-yaml || pip3 install --user PyYAML
  fi
  export JELLYFLAM3_SMOKE=1
  bash "$ROOT/scripts/smoke_render.sh" "$ROOT/configs/jellyflam3.yaml"
fi

echo "Done. Source tree: $SRC"
