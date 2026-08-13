#!/usr/bin/env bash
# Completely remove BOSS-Sentinel / BOSS-Optimize from the system.
# After this script, nothing related should remain (packages, files, configs, .debs).
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/saiprajith7/killer-crock/cursor/boss-sentinel-cpp-unified-02f6/scripts/purge-boss-sentinel.sh | bash
# Or:
#   sudo bash purge-boss-sentinel.sh
set -euo pipefail

log() { printf '==> %s\n' "$*"; }
warn() { printf 'WARN: %s\n' "$*" >&2; }

need_sudo() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

kill_running() {
  log "Stopping running BOSS-Sentinel / BOSS-Optimize processes"
  need_sudo pkill -f 'boss-sentinel-bin' 2>/dev/null || true
  need_sudo pkill -f 'boss-sentinel-gtk3' 2>/dev/null || true
  need_sudo pkill -f 'boss-sentinel-ui' 2>/dev/null || true
  need_sudo pkill -f '/usr/bin/boss-sentinel' 2>/dev/null || true
  need_sudo pkill -f 'boss-optimize' 2>/dev/null || true
  need_sudo pkill -f 'bossoptimize' 2>/dev/null || true
  sleep 0.5 || true
}

purge_packages() {
  log "Purging Debian packages"
  local pkgs=()
  local cand
  for cand in boss-sentinel boss-optimize bossoptimize vitaheal-pc-monitor vitaheal \
              python3-boss-sentinel python3-boss-optimize; do
    if dpkg -s "$cand" >/dev/null 2>&1; then
      pkgs+=("$cand")
    fi
  done
  if ((${#pkgs[@]})); then
    need_sudo dpkg --purge "${pkgs[@]}" 2>/dev/null || true
    need_sudo apt-get remove -y --purge "${pkgs[@]}" 2>/dev/null || true
    need_sudo apt-get autoremove -y 2>/dev/null || true
  else
    log "No related packages were installed"
  fi
}

remove_system_files() {
  log "Removing system files and launchers"
  need_sudo rm -rf \
    /usr/bin/boss-sentinel \
    /usr/bin/boss-optimize \
    /usr/bin/bossoptimize \
    /usr/lib/boss-sentinel \
    /usr/lib/boss-optimize \
    /usr/libexec/boss-sentinel \
    /usr/libexec/boss-optimize \
    /usr/share/boss-sentinel \
    /usr/share/boss-optimize \
    /usr/share/doc/boss-sentinel \
    /usr/share/doc/boss-optimize \
    /usr/share/polkit-1/actions/org.bosssentinel.policy \
    /usr/share/polkit-1/actions/org.bossoptimize.policy \
    /usr/share/applications/org.bosssentinel.BossSentinel.desktop \
    /usr/share/applications/boss-optimize.desktop \
    /usr/share/applications/org.bossoptimize*.desktop \
    /usr/share/icons/hicolor/scalable/apps/org.bosssentinel.BossSentinel.svg \
    /usr/share/icons/hicolor/scalable/apps/boss-optimize.svg \
    /etc/xdg/autostart/*boss-sentinel* \
    /etc/xdg/autostart/*boss-optimize* \
    2>/dev/null || true

  # Catch any leftover path with the product name under /usr
  need_sudo find /usr -xdev \( \
      -iname '*boss-sentinel*' -o \
      -iname '*boss_sentinel*' -o \
      -iname '*bosssentinel*' -o \
      -iname '*boss-optimize*' -o \
      -iname '*bossoptimize*' \
    \) \( -type f -o -type l -o -type d \) -print 2>/dev/null \
    | while IFS= read -r p; do
        log "Removing $p"
        need_sudo rm -rf "$p" 2>/dev/null || true
      done || true
}

remove_user_files() {
  log "Removing user config, cache, logs, and local copies"
  local home homes=()
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != root ]]; then
    homes+=("$(getent passwd "$SUDO_USER" | cut -d: -f6)")
  fi
  homes+=("${HOME}")
  # Also scrub other interactive users
  while IFS=: read -r _ _ uid _ _ home _; do
    [[ "$uid" -ge 1000 ]] || continue
    homes+=("$home")
  done < /etc/passwd

  local h
  local -A seen=()
  for h in "${homes[@]}"; do
    [[ -n "$h" && -d "$h" ]] || continue
    [[ -z "${seen[$h]:-}" ]] || continue
    seen[$h]=1
    rm -rf \
      "$h/.config/boss-sentinel" \
      "$h/.config/boss-optimize" \
      "$h/.local/share/boss-sentinel" \
      "$h/.local/share/boss-optimize" \
      "$h/.cache/boss-sentinel" \
      "$h/.cache/boss-optimize" \
      "$h/boss-sentinel" \
      "$h/.local/share/applications/org.bosssentinel.BossSentinel.desktop" \
      "$h/.local/share/applications/boss-optimize.desktop" \
      2>/dev/null || true
    # Desktop / Downloads leftovers
    find "$h/Desktop" "$h/Downloads" "$h/download" "$h/downloads" \
      -maxdepth 2 -type f \( \
        -iname '*boss-sentinel*' -o -iname '*boss-optimize*' -o -iname '*bossoptimize*' \
      \) -print 2>/dev/null | while IFS= read -r f; do
        log "Removing $f"
        rm -f "$f" || true
      done || true
  done
}

remove_debs_and_cache() {
  log "Removing .deb packages and apt cache copies"
  local roots=(/tmp /var/tmp /var/cache/apt/archives "$PWD" "$HOME" /root)
  local r
  for r in "${roots[@]}"; do
    [[ -d "$r" ]] || continue
    find "$r" -maxdepth 4 -type f \( \
      -iname 'boss-sentinel*.deb' -o \
      -iname 'boss-optimize*.deb' -o \
      -iname 'bossoptimize*.deb' \
    \) -print 2>/dev/null | while IFS= read -r f; do
      log "Removing $f"
      rm -f "$f" 2>/dev/null || need_sudo rm -f "$f" 2>/dev/null || true
    done || true
  done
}

refresh_caches() {
  log "Refreshing desktop / icon caches"
  need_sudo update-desktop-database /usr/share/applications 2>/dev/null || true
  need_sudo gtk-update-icon-cache -f /usr/share/icons/hicolor 2>/dev/null || true
  hash -r 2>/dev/null || true
}

verify_clean() {
  log "Verifying removal"
  local leftover=0
  if command -v boss-sentinel >/dev/null 2>&1 || command -v boss-optimize >/dev/null 2>&1; then
    warn "Launcher still on PATH"
    leftover=1
  fi
  if dpkg -l 'boss-sentinel' 'boss-optimize' 2>/dev/null | grep -E '^ii|^rc' >/dev/null; then
    warn "dpkg still lists a package (ii/rc)"
    dpkg -l 'boss-sentinel' 'boss-optimize' 2>/dev/null || true
    leftover=1
  fi
  if [[ -e /usr/bin/boss-sentinel || -e /usr/lib/boss-sentinel || -e /usr/share/boss-sentinel ]]; then
    warn "System paths still exist under /usr"
    leftover=1
  fi
  if [[ "$leftover" -eq 0 ]]; then
    log "OK: BOSS-Sentinel / BOSS-Optimize are gone from this system"
  else
    warn "Some leftovers remain — re-run with sudo or remove manually"
    exit 1
  fi
}

main() {
  log "Full purge of BOSS-Sentinel and BOSS-Optimize"
  kill_running
  purge_packages
  remove_system_files
  remove_user_files
  remove_debs_and_cache
  refresh_caches
  verify_clean
}

main "$@"
