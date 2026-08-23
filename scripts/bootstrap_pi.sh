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
#   Prepares CachePath/MetadataPath so Jellyfin can write temp files (see install_jellyfin.sh).

set -euo pipefail

HOST="$(hostname -s 2>/dev/null || hostname)"
USER_NAME="${SUDO_USER:-$USER}"

sudo mkdir -p /media/sheep/by-generation \
  /media/sheep/_refactor-preview \
  /var/cache/jellyflam3/{frames,transcodes,images,smoke} \
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
  # Jellyfin-owned scratch (matches lab 08a)
  sudo mkdir -p /var/cache/jellyflam3/transcodes /var/lib/jellyflam3/library
  sudo chown jellyfin:jellyfin /var/cache/jellyflam3/transcodes /var/lib/jellyflam3/library
  sudo chmod 775 /var/cache/jellyflam3/transcodes
  echo "Jellyfin user present: group membership + transcodes/library ownership set."
  echo "Verify write: sudo -u jellyfin touch /var/cache/jellyflam3/.write_ok /var/lib/jellyflam3/.write_ok && sudo rm -f /var/cache/jellyflam3/.write_ok /var/lib/jellyflam3/.write_ok"
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
