#!/usr/bin/env bash

# Purpose: Create JellyFlam3 directory layout on a Raspberry Pi (does not flash OS).
# Requirements: bash, sudo; findmnt for optional bind-mount of state onto NVMe cache.
#
# Usage: ./scripts/bootstrap_pi.sh
#
# When to run: Once on a new Pi after OS install, before install_flam3.sh / install_jellyfin.sh.
# Success: /media/sheep, /var/cache/jellyflam3, /var/lib/jellyflam3 exist and are group-writable.
# Docs: docs/phase2/09_PI_FROM_SCRATCH.md
#
# Assumptions: Prefer NVMe/SSD mounts; if /var/cache/jellyflam3 is a volume, bind-mount
#   /var/cache/jellyflam3/lib → /var/lib/jellyflam3 and persist in fstab.
#   Prepares MetadataPath and a Jellyfin-only CachePath subdirectory so Clean Cache
#   Directory does not walk furnace state (see install_jellyfin.sh).

set -euo pipefail

HOST="$(hostname -s 2>/dev/null || hostname)"
USER_NAME="${SUDO_USER:-$USER}"

sudo mkdir -p /media/sheep/by-generation \
  /media/sheep/_refactor-preview \
  /var/cache/jellyflam3/{frames,transcodes,images,smoke,jellyfin} \
  /var/cache/jellyflam3/lib/{jobs,logs,genomes/inbox,genomes/quarantine,genomes/done,display_profiles} \
  /var/lib/jellyflam3

# Prefer bind mount when cache mount is a dedicated volume and lib is empty/not a mount
if findmnt -n /var/cache/jellyflam3 >/dev/null 2>&1; then
  if ! findmnt -n /var/lib/jellyflam3 >/dev/null 2>&1; then
    sudo mount --bind /var/cache/jellyflam3/lib /var/lib/jellyflam3
  fi
  if ! grep -qE '[[:space:]]/var/lib/jellyflam3[[:space:]]' /etc/fstab; then
    echo '/var/cache/jellyflam3/lib  /var/lib/jellyflam3  none  bind  0  0' | sudo tee -a /etc/fstab >/dev/null
  fi
else
  sudo mkdir -p /var/lib/jellyflam3/{jobs,logs,genomes/inbox,genomes/quarantine,genomes/done,display_profiles}
fi

# Operator owns the tree; Jellyfin joins the same group for CachePath / MetadataPath / sheep.
sudo chown -R "${USER_NAME}:${USER_NAME}" /var/cache/jellyflam3 /var/lib/jellyflam3 /media/sheep
sudo chmod 775 /var/cache/jellyflam3 /var/lib/jellyflam3
sudo chmod 2775 /media/sheep /media/sheep/by-generation /media/sheep/_refactor-preview

if id jellyfin &>/dev/null; then
  sudo usermod -aG "${USER_NAME}" jellyfin || true
  sudo usermod -aG jellyfin,video,render "${USER_NAME}" || true
  # CachePath is the jellyfin/ subdirectory, not the NVMe root (lib bind lives there).
  # TranscodingTempPath stays transcodes/ so HLS segments remain on the NVMe.
  sudo mkdir -p /var/cache/jellyflam3/jellyfin /var/cache/jellyflam3/transcodes /var/lib/jellyflam3/library
  sudo chown jellyfin:jellyfin /var/cache/jellyflam3/jellyfin /var/cache/jellyflam3/transcodes /var/lib/jellyflam3/library
  sudo chmod 775 /var/cache/jellyflam3/jellyfin /var/cache/jellyflam3/transcodes
  echo "Jellyfin user present: cache dir, transcodes, and library ownership set."
  echo "Verify write: sudo -u jellyfin touch /var/cache/jellyflam3/jellyfin/.write_ok /var/cache/jellyflam3/transcodes/.write_ok /var/lib/jellyflam3/.write_ok && sudo rm -f /var/cache/jellyflam3/jellyfin/.write_ok /var/cache/jellyflam3/transcodes/.write_ok /var/lib/jellyflam3/.write_ok"
  if [[ -f /etc/jellyfin/system.xml ]]; then
    tmp="$(mktemp)"
    cat > "$tmp" <<'PY'
from pathlib import Path
import re
import shutil

cache = "/var/cache/jellyflam3/jellyfin"
trans = "/var/cache/jellyflam3/transcodes"
system = Path("/etc/jellyfin/system.xml")
encoding = Path("/etc/jellyfin/encoding.xml")
text = system.read_text(encoding="utf-8")
new, n = re.subn(r"(<CachePath>)[^<]*(</CachePath>)", rf"\1{cache}\2", text, count=1)
if n != 1:
    raise SystemExit("system.xml has no single CachePath element")
if new != text:
    shutil.copy2(system, system.with_name("system.xml.bak-cachepath"))
    system.write_text(new, encoding="utf-8")
    print("updated CachePath in system.xml; restart jellyfin to load it")
else:
    print("CachePath already", cache)
if encoding.is_file():
    enc = encoding.read_text(encoding="utf-8")
    if "<TranscodingTempPath>" not in enc and "<TranscodingTempPath " not in enc:
        if "</EncodingOptions>" not in enc:
            raise SystemExit("encoding.xml has no EncodingOptions close")
        shutil.copy2(encoding, encoding.with_name("encoding.xml.bak-cachepath"))
        enc = enc.replace(
            "</EncodingOptions>",
            f"  <TranscodingTempPath>{trans}</TranscodingTempPath>\n</EncodingOptions>",
            1,
        )
        encoding.write_text(enc, encoding="utf-8")
        print("set TranscodingTempPath; restart jellyfin to load it")
    else:
        enc2, n2 = re.subn(
            r"<TranscodingTempPath\s*/>|<TranscodingTempPath>.*?</TranscodingTempPath>",
            f"<TranscodingTempPath>{trans}</TranscodingTempPath>",
            enc,
            count=1,
            flags=re.DOTALL,
        )
        if n2 == 1 and enc2 != enc:
            shutil.copy2(encoding, encoding.with_name("encoding.xml.bak-cachepath"))
            encoding.write_text(enc2, encoding="utf-8")
            print("updated TranscodingTempPath; restart jellyfin to load it")
        else:
            print("TranscodingTempPath already", trans)
PY
    sudo python3 "$tmp"
    rm -f "$tmp"
  fi
  if [[ -f /etc/default/jellyfin ]]; then
    if grep -q '^JELLYFIN_CACHE_DIR=' /etc/default/jellyfin; then
      sudo sed -i 's|^JELLYFIN_CACHE_DIR=.*|JELLYFIN_CACHE_DIR="/var/cache/jellyflam3/jellyfin"|' /etc/default/jellyfin
    else
      echo 'JELLYFIN_CACHE_DIR="/var/cache/jellyflam3/jellyfin"' | sudo tee -a /etc/default/jellyfin >/dev/null
    fi
    echo "JELLYFIN_CACHE_DIR set; restart jellyfin to load it"
  fi
else
  echo "Jellyfin not installed yet — re-run this script after apt install jellyfin,"
  echo "  or follow ./scripts/install_jellyfin.sh permission prep before setting Cache/Metadata paths."
fi

echo
echo "Layout ready. Mount NVMe → /var/cache/jellyflam3 and USB SSD → /media/sheep"
echo "  (see docs/phase1/01_HARDWARE_AND_OS.md and docs/phase2/09_PI_FROM_SCRATCH.md)."
df -h /media/sheep /var/cache/jellyflam3 /var/lib/jellyflam3 2>/dev/null || true
findmnt /media/sheep /var/cache/jellyflam3 /var/lib/jellyflam3 2>/dev/null || true

case "$HOST" in
  rpi-jellyflam3-04*|*-04[a-z])
    echo
    echo "Hostname looks like -04 class ($HOST): enable journald vacuum (guide 09 step 12)"
    echo "  and apply compact preset: python3 -m pipeline.hw_profile apply 04a"
    ;;
esac

# Interactive shell: flam3 (/usr/local/bin), repo scripts, python -m pipeline.*
BASHRC="$(getent passwd "${USER_NAME}" | cut -d: -f6)/.bashrc"
if [[ -n "$BASHRC" && -f "$BASHRC" ]] || [[ -n "${HOME:-}" ]]; then
  BASHRC="${BASHRC:-$HOME/.bashrc}"
  if [[ -f "$BASHRC" ]] && ! grep -q 'JellyFlam3: Development' "$BASHRC" 2>/dev/null; then
    cat >> "$BASHRC" <<'EOF'

# JellyFlam3: Development
export PATH="$PATH:/usr/local/bin:/opt/jellyflam3-server/scripts"
export PYTHONPATH="/opt/jellyflam3-server"
EOF
    echo "Appended JellyFlam3 PATH/PYTHONPATH block to $BASHRC"
  fi
fi

echo
echo "Next: clone repo → /opt/jellyflam3-server symlink → hw_profile apply → install_flam3 → install_jellyfin"
echo "Validate anytime: ./scripts/bringup_check.sh"
