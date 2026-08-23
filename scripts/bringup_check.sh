#!/usr/bin/env bash

# Purpose: Staged bring-up checklist for a new JellyFlam3 Raspberry Pi (read-only checks).
# Requirements: bash; optional systemctl/python3/ffprobe when those stages are reached.
#          flam3 tools: this script prepends /usr/local/bin (same as cron wrappers).
#
# Usage:
#   ./scripts/bringup_check.sh           # non-zero exit if any FAIL
#   ./scripts/bringup_check.sh --strict  # also non-zero if any WARN
#
# When to run: First boot after bootstrap + install_flam3 / install_jellyfin; after hostname/profile apply.
# Success: identity/hostname class OK, toolchain on PATH, units present (FAIL always exits non-zero).
# Docs: docs/phase2/09_PI_FROM_SCRATCH.md (and Phase 3 RC health in 10_TESTING_AND_ACCEPTANCE.md)
#
# Assumptions: Run on the Pi as the jellyflam3 (or deploy) user; /opt/jellyflam3-server preferred.

set -euo pipefail

# flam3 make install lands in /usr/local/bin; non-login shells often miss it.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

STRICT=0
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -d /opt/jellyflam3-server ]]; then
  ROOT="$(readlink -f /opt/jellyflam3-server 2>/dev/null || echo /opt/jellyflam3-server)"
fi

for arg in "$@"; do
  case "$arg" in
    --strict) STRICT=1 ;;
    -h|--help)
      sed -n '1,18p' "$0"
      exit 0
      ;;
  esac
done

PASS=0
FAIL=0
WARN=0

ok() { echo "  OK  $*"; PASS=$((PASS + 1)); }
bad() { echo "  FAIL $*"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN $*"; WARN=$((WARN + 1)); }

section() { echo; echo "== $* =="; }

HOST="$(hostname -s 2>/dev/null || hostname)"
MEM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)"

section "1. Identity"
echo "  host=$HOST mem_mb=$MEM_MB"
case "$HOST" in
  rpi-jellyflam3-16*) ok "hostname class -16" ;;
  rpi-jellyflam3-08*) ok "hostname class -08" ;;
  rpi-jellyflam3-04*) ok "hostname class -04 (compact)" ;;
  *) warn "hostname '$HOST' does not match rpi-jellyflam3-{16,08,04}*" ;;
esac
if getent hosts "$HOST" >/dev/null 2>&1; then
  ok "hostname resolves via getent/hosts"
else
  bad "hostname '$HOST' does not resolve — add '127.0.1.1 $HOST' to /etc/hosts (and cloud-init hosts template if manage_etc_hosts=true)"
fi
if [[ "$MEM_MB" -gt 0 && "$MEM_MB" -lt 5000 ]]; then
  case "$HOST" in
    rpi-jellyflam3-04*) ok "RAM ~4 GB matches -04 class" ;;
    *) warn "RAM ${MEM_MB} MiB looks like 4 GB class — prefer hostname rpi-jellyflam3-04a" ;;
  esac
fi

section "2. Mounts"
for m in /media/sheep /var/cache/jellyflam3 /var/lib/jellyflam3; do
  if findmnt -n "$m" >/dev/null 2>&1 || [[ -d "$m" ]]; then
    if df -P "$m" >/dev/null 2>&1; then
      ok "$m present ($(df -hP "$m" | awk 'NR==2{print $2" total,"$4" free"}'))"
    else
      warn "$m exists but df failed"
    fi
  else
    bad "$m missing — format/mount disks then ./scripts/bootstrap_pi.sh"
  fi
done
if findmnt -n /var/cache/jellyflam3 >/dev/null 2>&1 && findmnt -n /var/lib/jellyflam3 >/dev/null 2>&1; then
  src="$(findmnt -n -o SOURCE /var/lib/jellyflam3 2>/dev/null || true)"
  if [[ "$src" == *"bind"* ]] || findmnt -n /var/lib/jellyflam3 2>/dev/null | grep -qi bind; then
    ok "/var/lib/jellyflam3 is a mount (prefer bind → cache/lib)"
  else
    # bind mounts often show as same device
    ok "/var/lib/jellyflam3 mounted"
  fi
fi

section "3. Cache / Metadata permissions (Jellyfin)"
for d in /var/cache/jellyflam3 /var/lib/jellyflam3; do
  mode="$(stat -c '%a' "$d" 2>/dev/null || echo '?')"
  if [[ "$mode" == "775" || "$mode" == "2775" || "$mode" == "775"* ]]; then
    ok "$d mode=$mode"
  else
    warn "$d mode=$mode (lab uses 775; Axios/temp errors if jellyfin cannot write)"
  fi
done
if id jellyfin &>/dev/null; then
  if id -nG jellyfin 2>/dev/null | tr ' ' '\n' | grep -qx "$(id -un)"; then
    ok "jellyfin ∈ group $(id -un)"
  else
    bad "jellyfin not in group $(id -un) — sudo usermod -aG $(id -un) jellyfin && sudo systemctl restart jellyfin"
  fi
  if sudo -n -u jellyfin test -w /var/cache/jellyflam3 2>/dev/null \
    && sudo -n -u jellyfin test -w /var/lib/jellyflam3 2>/dev/null; then
    ok "jellyfin can write CachePath + MetadataPath roots"
  else
    warn "could not verify jellyfin write (passwordless sudo -n required, or run install_jellyfin.sh prep)"
  fi
else
  warn "jellyfin user not present yet — install before setting Dashboard Cache/Metadata paths"
fi

section "4. Repo + config"
if [[ -d "$ROOT" ]]; then
  ok "repo root $ROOT"
else
  bad "repo not found"
fi
if [[ -L /opt/jellyflam3-server || -d /opt/jellyflam3-server ]]; then
  ok "/opt/jellyflam3-server → $(readlink -f /opt/jellyflam3-server 2>/dev/null || echo present)"
else
  bad "missing /opt/jellyflam3-server symlink"
fi
CFG="$ROOT/configs/jellyflam3.yaml"
SEC="$ROOT/secrets.env"
if [[ -f "$CFG" ]]; then
  ok "configs/jellyflam3.yaml present"
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<PY 2>/dev/null && ok "hw_profile readable" || warn "could not load hw_profile from yaml"
import sys
sys.path.insert(0, "$ROOT")
from pipeline.config import load_config
c = load_config("$CFG")
r = c.get("render") or {}
print("  hw_profile=", r.get("hw_profile"), "edition=", r.get("edition"), "quality=", r.get("quality"), "max_cpus=", r.get("max_cpus"))
host = "$HOST"
hp = str(r.get("hw_profile") or "")
if "04" in host and "04" not in hp:
    print("  WARN hostname -04 but hw_profile=", hp)
    sys.exit(2)
if "08" in host and "08" not in hp:
    print("  WARN hostname -08 but hw_profile=", hp)
    sys.exit(2)
if "16" in host and "16" not in hp:
    print("  WARN hostname -16 but hw_profile=", hp)
    sys.exit(2)
PY
  fi
else
  bad "missing $CFG — cp configs/jellyflam3.yaml.example configs/jellyflam3.yaml && hw_profile apply"
fi
if [[ -f "$SEC" ]]; then
  ok "secrets.env present"
  # shellcheck disable=SC1090
  set +u
  # grep without sourcing secrets into this shell's env permanently
  missing=0
  for k in JELLYFIN_URL JELLYFIN_API_KEY JELLYFIN_USER_ID JELLYFIN_LIBRARY_ID; do
    if ! grep -qE "^${k}=.+" "$SEC" 2>/dev/null; then
      warn "secrets.env $k empty or missing"
      missing=1
    fi
  done
  [[ "$missing" -eq 0 ]] && ok "JELLYFIN_* keys non-empty"
  set -u
else
  warn "secrets.env missing — copy secrets.env.example after Jellyfin wizard"
fi
# Secrets hygiene: filled yaml/secrets must never be tracked
if [[ -d "$ROOT/.git" ]] && command -v git >/dev/null 2>&1; then
  if git -C "$ROOT" ls-files --error-unmatch secrets.env >/dev/null 2>&1 \
    || git -C "$ROOT" ls-files --error-unmatch configs/jellyflam3.yaml >/dev/null 2>&1; then
    bad "secrets.env or jellyflam3.yaml is tracked by git — git rm --cached + rotate API keys"
  else
    ok "secrets.env / jellyflam3.yaml not tracked by git"
  fi
fi

section "5. Toolchain"
for t in flam3-animate flam3-genome ffmpeg ffprobe; do
  if command -v "$t" >/dev/null 2>&1; then
    ok "$t on PATH"
  else
    bad "$t missing — ./scripts/install_flam3.sh"
  fi
done

section "6. Systemd units"
for u in jellyfin jellyflam3-worker jellyflam3-idlegate jellyflam3-display-sink; do
  if systemctl list-unit-files "${u}.service" &>/dev/null; then
    st="$(systemctl is-active "${u}.service" 2>/dev/null || echo missing)"
    if [[ "$st" == "active" ]]; then
      ok "$u active"
    else
      warn "$u state=$st"
    fi
  else
    warn "$u unit not installed yet"
  fi
done

section "7. Health surfaces"
if [[ -x "$ROOT/scripts/healthcheck.sh" ]]; then
  if (cd "$ROOT" && ./scripts/healthcheck.sh >/tmp/jellyflam3-bringup-health.txt 2>&1); then
    ok "healthcheck.sh exit 0"
  else
    bad "healthcheck.sh failed — see /tmp/jellyflam3-bringup-health.txt"
  fi
else
  warn "healthcheck.sh not executable / missing"
fi

section "Summary"
echo "  PASS=$PASS WARN=$WARN FAIL=$FAIL"
echo "  Guide: docs/phase2/09_PI_FROM_SCRATCH.md"
echo "  Jellyfin notes: ./scripts/install_jellyfin.sh"

# Gate mode: any FAIL is non-zero. --strict also fails on WARN.
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
if [[ "$STRICT" -eq 1 && "$WARN" -gt 0 ]]; then
  exit 1
fi
exit 0
