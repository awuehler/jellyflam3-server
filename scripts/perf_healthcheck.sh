#!/usr/bin/env bash

# Purpose: Fast preliminary performance / layout health check for JellyFlam3 on Pi 5.
# Aligns with Phase 1 goals: NVMe/SSD storage, thermal headroom, disk IO for
# flam3 scratch + flock, memory, and (when present) toolchain readiness.
# Requirements: bash, python3, findmnt, df; vcgencmd optional (Pi); dd for microbench.
#          flam3 tools: this script prepends /usr/local/bin.
#
# Usage:
#   ./scripts/perf_healthcheck.sh
#   ./scripts/perf_healthcheck.sh --quick    # skip disk microbench
#   ./scripts/perf_healthcheck.sh --bench-mb 256
#
# When to run: After storage layout (bootstrap_pi.sh); before trusting overnight Gold Sheep Lite renders.
# Success: exit 0 = no FAIL items (WARN alone still 0). Fail: 1 = one or more FAIL.
# Docs: docs/phase1 (storage / thermal) and docs/phase3/10_TESTING_AND_ACCEPTANCE.md
#
# Assumptions: Paths via SHEEP_PATH/CACHE_PATH/LIB_PATH/FRAMES_PATH or defaults under
#   /media/sheep, /var/cache/jellyflam3, /var/lib/jellyflam3.
#
# Exit: 0 = no FAIL items; 1 = one or more FAIL (WARN alone still exits 0).

set -euo pipefail

# flam3 make install lands in /usr/local/bin; non-login shells often miss it.
export PATH="/usr/local/bin:/usr/bin:/bin:${PATH:-}"

QUICK=0
BENCH_MB=128
SHEEP="${SHEEP_PATH:-/media/sheep}"
CACHE="${CACHE_PATH:-/var/cache/jellyflam3}"
LIB="${LIB_PATH:-/var/lib/jellyflam3}"
FRAMES="${FRAMES_PATH:-$CACHE/frames}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick) QUICK=1; shift ;;
    --bench-mb) BENCH_MB="${2:?}"; shift 2 ;;
    -h|--help)
      sed -n '2,22p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

PASS=0
WARN=0
FAIL=0
declare -a NOTES=()

ok()   { PASS=$((PASS + 1)); echo "  [PASS] $*"; }
warn() { WARN=$((WARN + 1)); echo "  [WARN] $*"; NOTES+=("WARN: $*"); }
fail() { FAIL=$((FAIL + 1)); echo "  [FAIL] $*"; NOTES+=("FAIL: $*"); }

section() { echo; echo "== $* =="; }

# True if findmnt SOURCE for path contains needle (e.g. nvme, mmcblk).
is_block_under() {
  local path="$1" needle="$2"
  local src
  src="$(findmnt -n -o SOURCE --target "$path" 2>/dev/null || true)"
  [[ -n "$src" && "$src" == *"$needle"* ]]
}

# Classify backing device for path: nvme | sd | usb_or_sata | other:… | unmounted.
device_kind() {
  local path="$1" src base
  src="$(findmnt -n -o SOURCE --target "$path" 2>/dev/null || true)"
  [[ -z "$src" ]] && { echo "unmounted"; return; }
  # Strip partition suffix hints like [/lib] from bind mounts
  src="${src%%\[*}"
  base="$(basename "$src")"
  if [[ "$base" == nvme* || "$src" == *nvme* ]]; then
    echo "nvme"
  elif [[ "$base" == mmcblk* || "$src" == *mmcblk* ]]; then
    echo "sd"
  elif [[ "$base" == sd* || "$base" == vd* ]]; then
    echo "usb_or_sata"
  else
    echo "other:$src"
  fi
}

# Free space on path's filesystem in GiB (one decimal), via df -B1.
avail_gb() {
  local path="$1"
  df -PB1 "$path" 2>/dev/null | awk 'NR==2{printf "%.1f", $4/1024/1024/1024}'
}

# Sequential O_DIRECT write/read of mb MiB under dir; prints speeds and soft verdict.
bench_write_read() {
  local dir="$1" label="$2" mb="$3"
  local tmp="$dir/.jellyflam3_perf_$$"
  mkdir -p "$dir" 2>/dev/null || { warn "$label: cannot create $dir"; return; }
  if [[ ! -w "$dir" ]]; then
    warn "$label: not writable by $(whoami) ($dir)"
    return
  fi
  # Sequential write
  local wr rd
  wr="$(dd if=/dev/zero of="$tmp" bs=1M count="$mb" oflag=direct conv=fsync 2>&1 | awk '/copied|records out/{line=$0} END{print line}')" || true
  # Sequential read
  rd="$(dd if="$tmp" of=/dev/null bs=1M iflag=direct 2>&1 | awk '/copied|records out/{line=$0} END{print line}')" || true
  rm -f "$tmp"
  local wr_mbs rd_mbs
  wr_mbs="$(echo "$wr" | grep -oE '[0-9.]+ [GM]B/s' | tail -1 || true)"
  rd_mbs="$(echo "$rd" | grep -oE '[0-9.]+ [GM]B/s' | tail -1 || true)"
  echo "  $label write: ${wr_mbs:-n/a}  read: ${rd_mbs:-n/a}  (${mb} MiB direct)"

  # Rough thresholds for Pi 5 + NVMe/USB3 SSD goals (sequential, not synthetic peak)
  python3 - "$wr_mbs" "$rd_mbs" "$label" <<'PY' || true
import re, sys
wr, rd, label = sys.argv[1], sys.argv[2], sys.argv[3]

def mbs(s):
    if not s or s == "n/a":
        return None
    m = re.match(r"([0-9.]+)\s*([GM])B/s", s)
    if not m:
        return None
    v = float(m.group(1))
    return v * 1024 if m.group(2) == "G" else v

w, r = mbs(wr), mbs(rd)
# Soft goals: USB3 SSD often ~100–300+ MB/s; NVMe higher; SD often <80 write
def judge(v, good, ok):
    if v is None:
        return "skip"
    if v >= good:
        return "good"
    if v >= ok:
        return "ok"
    return "slow"

jw, jr = judge(w, 150, 80), judge(r, 200, 100)
print(f"  {label} verdict: write={jw} read={jr}")
open("/tmp/jellyflam3_perf_verdict", "a").write(f"{label}:{jw}:{jr}\n")
PY
}

echo "JellyFlam3 preliminary performance health check"
echo "host=$(hostname)  user=$(whoami)  $(date -u +%Y-%m-%dT%H:%M:%SZ)"

section "platform"
if [[ -r /proc/device-tree/model ]]; then
  model="$(tr -d '\0' </proc/device-tree/model)"
  echo "  model: $model"
  if echo "$model" | grep -qi "Raspberry Pi 5"; then
    ok "Raspberry Pi 5 detected"
  else
    warn "Expected Raspberry Pi 5; got: $model"
  fi
else
  warn "No device-tree model (not a Pi?)"
fi
echo "  kernel: $(uname -r)  arch: $(uname -m)"
mem_gb="$(awk '/MemTotal/{printf "%.1f", $2/1024/1024}' /proc/meminfo)"
echo "  memory: ${mem_gb} GiB"
python3 -c "import sys; m=float('$mem_gb'); sys.exit(0 if m>=7.0 else 1)" && ok "RAM ≥ ~8 GiB class (${mem_gb} GiB)" || warn "RAM ${mem_gb} GiB (8 GiB preferred; 4 GiB workable with zram)"
nproc="$(nproc)"
echo "  CPUs: $nproc"
[[ "$nproc" -ge 4 ]] && ok "4+ CPU cores ($nproc)" || warn "Only $nproc CPUs"

section "thermals"
if command -v vcgencmd >/dev/null 2>&1; then
  temp="$(vcgencmd measure_temp 2>/dev/null | sed -E "s/temp=//;s/'C//")"
  throttled="$(vcgencmd get_throttled 2>/dev/null | sed 's/throttled=//')"
  echo "  temp=${temp}°C  throttled=$throttled"
  python3 -c "import sys; t=float('$temp'); sys.exit(0 if t<70 else 1)" && ok "Idle/load temp under 70°C (${temp}°C)" || warn "Temp ${temp}°C — confirm Active Cooler / airflow"
  if [[ "$throttled" == "0x0" ]]; then
    ok "No throttle flags (0x0)"
  else
    # Bits 0–3 = currently active; bits 16–19 = sticky history (until power cut).
    thr_kind="$(python3 - "$throttled" <<'PY'
import sys
raw = sys.argv[1].strip().lower().replace("throttled=", "")
try:
    v = int(raw, 16)
except ValueError:
    print("other")
    raise SystemExit
active = v & 0xF
sticky = (v >> 16) & 0xF
if active:
    print("active")
elif sticky:
    print("sticky")
else:
    print("other")
PY
)"
    if [[ "$thr_kind" == "active" ]]; then
      fail "Active throttle/under-voltage flags ($throttled) — check PSU 5V/5A and cooling"
    elif [[ "$thr_kind" == "sticky" ]]; then
      warn "Sticky throttle history ($throttled) — OK if idle temp is fine; clears on full power cut"
    else
      warn "Unexpected throttle value ($throttled)"
    fi
  fi
else
  warn "vcgencmd missing"
fi

section "storage layout (project goals)"
for p in "$SHEEP" "$CACHE" "$LIB"; do
  if [[ -d "$p" ]]; then
    kind="$(device_kind "$p")"
    avail="$(avail_gb "$p")"
    src="$(findmnt -n -o SOURCE --target "$p" 2>/dev/null || echo '?')"
    echo "  $p → $src ($kind)  free=${avail}G"
  else
    fail "Missing path $p"
  fi
done

sheep_k="$(device_kind "$SHEEP")"
cache_k="$(device_kind "$CACHE")"
lib_k="$(device_kind "$LIB")"

case "$sheep_k" in
  sd) fail "/media/sheep is on microSD — move flock to NVMe or USB SSD" ;;
  nvme|usb_or_sata) ok "/media/sheep on $sheep_k (not microSD)" ;;
  *) warn "/media/sheep device kind: $sheep_k" ;;
esac

case "$cache_k" in
  sd) fail "scratch ($CACHE) on microSD — frames will punish the card" ;;
  nvme) ok "scratch on NVMe" ;;
  usb_or_sata) warn "scratch on USB/SATA SSD (NVMe preferred for frames)" ;;
  *) warn "scratch device kind: $cache_k" ;;
esac

case "$lib_k" in
  sd) fail "$LIB on microSD" ;;
  nvme|usb_or_sata) ok "$LIB on $lib_k" ;;
  *) warn "$LIB device kind: $lib_k" ;;
esac

sheep_free="$(avail_gb "$SHEEP" || echo 0)"
cache_free="$(avail_gb "$CACHE" || echo 0)"
python3 -c "import sys; sys.exit(0 if float('$sheep_free')>=50 else 1)" && ok "Sheep free ≥ 50 GiB (${sheep_free}G)" || warn "Sheep free only ${sheep_free}G"
python3 -c "import sys; sys.exit(0 if float('$cache_free')>=20 else 1)" && ok "Scratch free ≥ 20 GiB (${cache_free}G)" || fail "Scratch free ${cache_free}G — need headroom for PNG dumps (goal ≥ ~8–20 GiB)"

if [[ -d "$FRAMES" ]]; then
  ok "Frames dir exists: $FRAMES"
else
  warn "Frames dir missing ($FRAMES) — create before renders"
fi

section "memory / swap"
swaps="$(swapon --show=NAME,TYPE,SIZE,USED --noheadings 2>/dev/null || true)"
echo "  $swaps"
if echo "$swaps" | grep -qi zram; then
  ok "zram swap present"
elif [[ -n "$swaps" ]]; then
  warn "Swap without zram — OK if 8GB RAM; prefer zram on 4GB"
else
  warn "No swap configured"
fi
avail_mem="$(awk '/MemAvailable/{printf "%.1f", $2/1024/1024}' /proc/meminfo)"
python3 -c "import sys; sys.exit(0 if float('$avail_mem')>=2.0 else 1)" && ok "MemAvailable ≥ 2 GiB (${avail_mem}G)" || warn "MemAvailable only ${avail_mem}G"

section "toolchain (preliminary)"
for t in flam3-genome flam3-animate ffmpeg ffprobe; do
  if command -v "$t" >/dev/null 2>&1; then
    ok "$t on PATH ($(command -v "$t"))"
  else
    warn "$t not on PATH yet (expected until guide 03)"
  fi
done
if command -v jellyfin >/dev/null 2>&1 || systemctl is-active --quiet jellyfin 2>/dev/null; then
  ok "Jellyfin appears installed/active"
else
  warn "Jellyfin not detected yet (expected until guide 04)"
fi

if [[ "$QUICK" -eq 0 ]]; then
  section "disk microbench (${BENCH_MB} MiB, O_DIRECT)"
  rm -f /tmp/jellyflam3_perf_verdict
  bench_write_read "$FRAMES" "scratch/frames" "$BENCH_MB"
  # Prefer writable sheep subdir
  if [[ -w "$SHEEP" ]]; then
    bench_write_read "$SHEEP" "sheep" "$BENCH_MB"
  else
    warn "sheep not writable by $(whoami); skipping sheep bench (chown/jellyfin group later)"
  fi
  if [[ -f /tmp/jellyflam3_perf_verdict ]]; then
    while IFS=: read -r lab jw jr; do
      if [[ "$jw" == "slow" || "$jr" == "slow" ]]; then
        warn "$lab sequential IO below soft goal (write=$jw read=$jr)"
      elif [[ "$jw" == "skip" && "$jr" == "skip" ]]; then
        :
      else
        ok "$lab sequential IO acceptable (write=$jw read=$jr)"
      fi
    done < /tmp/jellyflam3_perf_verdict
    rm -f /tmp/jellyflam3_perf_verdict
  fi
else
  section "disk microbench"
  echo "  skipped (--quick)"
fi

section "summary vs project goals"
echo "  Goals: Pi 5 + cooler/PSU headroom; flock+scratch off microSD;"
echo "         NVMe/USB3 SSD IO for overnight flam3→ffmpeg; RAM for encode."
echo "  PASS=$PASS  WARN=$WARN  FAIL=$FAIL"
if [[ ${#NOTES[@]} -gt 0 ]]; then
  echo "  Notes:"
  for n in "${NOTES[@]}"; do echo "    - $n"; done
fi

if [[ "$FAIL" -gt 0 ]]; then
  echo "  RESULT: FAIL — address FAIL items before heavy renders"
  exit 1
fi
if [[ "$WARN" -gt 0 ]]; then
  echo "  RESULT: PASS WITH WARNINGS — OK for preliminary Phase 1 progress"
  exit 0
fi
echo "  RESULT: PASS — layout/performance look aligned with Phase 1 goals"
exit 0
