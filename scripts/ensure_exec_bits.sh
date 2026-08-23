#!/usr/bin/env bash

# Purpose: Set git executable bits for CLI tools per repo policy.
# Requirements: bash, git; run from a clone with an index.
# Policy (repo default):
#   +x  scripts/*.{sh,py,ps1}
#   +x  pipeline/*.py          (python -m pipeline.* / direct invoke)
#   644 tests/**               (not CLI tools)
#
# Usage: ./scripts/ensure_exec_bits.sh | ./scripts/ensure_exec_bits.sh --check
#
# When to run: After adding or renaming CLI tools (scripts/*.{sh,py,ps1} or pipeline/*.py).
# Success: --check prints nothing / exit 0; without --check, git update-index --chmod=+x as needed.
# Docs: .cursor/rules/exec-bits.mdc
#
# Assumptions: Only staged index modes change; commit separately when ready.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CHECK=0
for arg in "$@"; do
  case "$arg" in
    --check) CHECK=1 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

want_exec=()
while IFS= read -r -d '' f; do
  want_exec+=("$f")
done < <(git ls-files -z -- 'scripts/*.sh' 'scripts/*.py' 'scripts/*.ps1' 'pipeline/*.py')

want_nonexec=()
while IFS= read -r -d '' f; do
  want_nonexec+=("$f")
done < <(git ls-files -z -- 'tests/*.py')

drift=0

# Return git index mode for path (e.g. 100755 / 100644).
mode_of() {
  # git ls-files -s → "100755 <sha> <stage> <path>"
  git ls-files -s -- "$1" | awk '{print $1}'
}

for f in "${want_exec[@]}"; do
  [[ -n "$f" ]] || continue
  m="$(mode_of "$f")"
  if [[ "$m" != "100755" ]]; then
    if [[ "$CHECK" -eq 1 ]]; then
      echo "MISSING +x: $f (mode=$m)"
      drift=1
    else
      git update-index --chmod=+x -- "$f"
      echo "+x $f"
    fi
  fi
done

for f in "${want_nonexec[@]}"; do
  [[ -n "$f" ]] || continue
  m="$(mode_of "$f")"
  if [[ "$m" == "100755" ]]; then
    if [[ "$CHECK" -eq 1 ]]; then
      echo "UNEXPECTED +x: $f"
      drift=1
    else
      git update-index --chmod=-x -- "$f"
      echo "-x $f"
    fi
  fi
done

if [[ "$CHECK" -eq 1 ]]; then
  if [[ "$drift" -ne 0 ]]; then
    echo "exec-bit drift detected; run: ./scripts/ensure_exec_bits.sh" >&2
    exit 1
  fi
  echo "OK exec bits match policy"
  exit 0
fi

echo "done (staged mode changes only — commit when ready)"
