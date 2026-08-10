#!/usr/bin/env bash
# BOSS-Sentinel installer — resolves dependencies, then installs the .deb.
#
# Usage:
#   bash install-boss-sentinel.sh
#   bash install-boss-sentinel.sh /path/to/boss-sentinel_*.deb
#
# Note: plain `dpkg -i` cannot download dependencies. This script checks each
# package, prints installed / not installed, installs missing ones with apt,
# then configures boss-sentinel and runs a smoke test.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

GREEN=$'\033[32m'
RED=$'\033[31m'
YELLOW=$'\033[33m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

ok()   { printf '%s✔%s %s\n' "$GREEN" "$RESET" "$*"; }
warn() { printf '%s!%s %s\n' "$YELLOW" "$RESET" "$*"; }
fail() { printf '%s✖%s %s\n' "$RED" "$RESET" "$*"; }

need_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -E bash "$0" "$@"
  fi
}

find_deb() {
  if [[ $# -ge 1 && -f "${1:-}" ]]; then
    printf '%s\n' "$1"
    return
  fi
  local candidates=()
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$SCRIPT_DIR"/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$PWD"/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$SCRIPT_DIR"/../install/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$SCRIPT_DIR"/../releases/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  while IFS= read -r f; do candidates+=("$f"); done < <(ls -1 "$SCRIPT_DIR"/../dist/boss-sentinel_*.deb 2>/dev/null | sort -V || true)
  if ((${#candidates[@]} == 0)); then
    fail "no boss-sentinel_*.deb found near $SCRIPT_DIR or current directory"
    exit 1
  fi
  printf '%s\n' "${candidates[-1]}"
}

# Return 0 if any alternative in an OR-list is installed.
pkg_satisfied() {
  local expr="$1"
  local alt
  IFS='|' read -ra alts <<< "$expr"
  for alt in "${alts[@]}"; do
    alt="$(echo "$alt" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g; s/:any$//; s/[[:space:]]*\(.*\)$//')"
    [[ -z "$alt" ]] && continue
    if dpkg-query -W -f='${Status}' "$alt" 2>/dev/null | grep -q 'install ok installed'; then
      return 0
    fi
  done
  return 1
}

# Prefer first available candidate from apt for an OR-list.
pick_installable() {
  local expr="$1"
  local alt
  IFS='|' read -ra alts <<< "$expr"
  for alt in "${alts[@]}"; do
    alt="$(echo "$alt" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g; s/:any$//; s/[[:space:]]*\(.*\)$//')"
    [[ -z "$alt" ]] && continue
    if apt-cache show "$alt" >/dev/null 2>&1; then
      printf '%s\n' "$alt"
      return 0
    fi
  done
  # Fall back to first name even if cache miss (apt may still resolve).
  alt="$(echo "${alts[0]}" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g; s/:any$//; s/[[:space:]]*\(.*\)$//')"
  printf '%s\n' "$alt"
}

check_and_collect_missing() {
  local -n _missing=$1
  shift
  local expr status pick
  printf '\n%sDependency check%s\n' "$BOLD" "$RESET"
  printf '─────────────────\n'
  for expr in "$@"; do
    if pkg_satisfied "$expr"; then
      status="${GREEN}installed${RESET}"
      ok "$expr  →  $status"
    else
      status="${RED}not installed${RESET}"
      fail "$expr  →  $status"
      pick="$(pick_installable "$expr")"
      _missing+=("$pick")
    fi
  done
}

need_root "$@"

DEB="$(find_deb "${1:-}")"
DEB="$(readlink -f "$DEB")"
VERSION="$(dpkg-deb -f "$DEB" Version 2>/dev/null || echo unknown)"

printf '%sBOSS-Sentinel installer%s\n' "$BOLD" "$RESET"
printf 'Package : %s\n' "$(basename "$DEB")"
printf 'Version : %s\n' "$VERSION"

# Required for a working install (Depends + important Recommends we always pull).
REQUIRED=(
  "python3"
  "python3-gi"
  "python3-gi-cairo"
  "python3-cairo"
  "gir1.2-gtk-4.0"
  "gir1.2-adw-1"
  "pkexec | policykit-1"
  "polkitd | policykit-1"
  "libnotify-bin"
  "fonts-hack | fonts-firacode | fonts-jetbrains-mono"
)

MISSING=()
check_and_collect_missing MISSING "${REQUIRED[@]}"

if ((${#MISSING[@]} > 0)); then
  printf '\n%sInstalling missing packages via apt...%s\n' "$BOLD" "$RESET"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y "${MISSING[@]}"
  printf '\n%sRe-check after apt install%s\n' "$BOLD" "$RESET"
  printf '──────────────────────────\n'
  STILL=()
  for expr in "${REQUIRED[@]}"; do
    if pkg_satisfied "$expr"; then
      ok "$expr  →  ${GREEN}installed${RESET}"
    else
      fail "$expr  →  ${RED}still missing${RESET}"
      STILL+=("$expr")
    fi
  done
  if ((${#STILL[@]} > 0)); then
    fail "Could not satisfy: ${STILL[*]}"
    fail "Fix apt sources / network, then re-run this installer."
    exit 1
  fi
else
  ok "All required dependencies already present."
fi

# Install .deb from /tmp to avoid apt home-dir sandbox warnings.
TMP="$(mktemp /tmp/boss-sentinel_XXXXXX.deb)"
cleanup() { rm -f "$TMP"; }
trap cleanup EXIT
cp -f "$DEB" "$TMP"
chmod 644 "$TMP"

printf '\n%sInstalling boss-sentinel package...%s\n' "$BOLD" "$RESET"
set +e
dpkg -i "$TMP"
DPKG_RC=$?
set -e
if [[ "$DPKG_RC" -ne 0 ]]; then
  warn "dpkg reported issues — running apt-get install -f to finish configuration"
  apt-get install -f -y
fi

# Final package state
printf '\n%sPackage status%s\n' "$BOLD" "$RESET"
printf '──────────────\n'
if dpkg-query -W -f='${Status}\n' boss-sentinel 2>/dev/null | grep -q 'install ok installed'; then
  ok "boss-sentinel  →  ${GREEN}installed${RESET} ($(dpkg-query -W -f='${Version}' boss-sentinel))"
else
  fail "boss-sentinel is not fully configured"
  dpkg -l boss-sentinel || true
  exit 1
fi

printf '\n%sSmoke test%s\n' "$BOLD" "$RESET"
printf '──────────\n'
if command -v boss-sentinel >/dev/null 2>&1; then
  if boss-sentinel --once >/tmp/boss-sentinel-once.json 2>/tmp/boss-sentinel-once.err; then
    ok "boss-sentinel --once  →  OK"
  else
    warn "boss-sentinel --once failed (GUI deps may still work on a desktop session)"
    warn "stderr: $(tr '\n' ' ' </tmp/boss-sentinel-once.err | head -c 200)"
  fi
else
  fail "boss-sentinel command not on PATH"
  exit 1
fi

printf '\n%sDone.%s Launch with: boss-sentinel\n' "$GREEN" "$RESET"
printf 'For ISO seeds, also include: pkexec polkitd libnotify-bin fonts-hack\n'
printf '                          python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1\n'
