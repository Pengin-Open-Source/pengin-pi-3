#!/bin/bash
# Shared functions for deploy_fedora.sh / deploy_debian_ubuntu.sh / deploy_mac.sh.
# Not meant to be run directly - each OS script does `source "$(dirname
# "${BASH_SOURCE[0]}")/scripts/lib/common.sh"`.

# --- output helpers ---------------------------------------------------

c_info()  { printf '\033[1;34m[*]\033[0m %s\n' "$*"; }
c_ok()    { printf '\033[1;32m[OK]\033[0m %s\n' "$*"; }
c_warn()  { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
c_err()   { printf '\033[1;31m[ERROR]\033[0m %s\n' "$*" >&2; }

# --- elevated privileges ------------------------------------------------
# Installing packages, writing to /opt, and managing system services all
# need root. Re-exec the whole script under sudo once up front (prompting
# for the password here) instead of sprinkling `sudo` over individual
# commands, so a script that dies partway through never leaves the user
# wondering which steps ran with which privileges.
require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    c_info "This installer needs elevated (root) privileges to install packages and write to the install directory."
    exec sudo -E bash "$0" "$@"
  fi
}

# --- install directory --------------------------------------------------
# Sets INSTALL_DIR (SOURCE_DIR - the directory this script was launched
# from, i.e. the extracted release zip / cloned repo - must already be
# set by the caller before calling this; each deploy_<os>.sh sets it from
# its own resolved path at startup, since inferring it from the call
# stack is fragile once any indirection is involved).
prompt_install_dir() {
  : "${SOURCE_DIR:?prompt_install_dir: SOURCE_DIR must be set by the caller first}"
  local default_dir="/opt/pengin-pi-3"
  local answer
  read -r -p "Install directory [${default_dir}]: " answer
  INSTALL_DIR="${answer:-$default_dir}"

  if [ "$SOURCE_DIR" != "$INSTALL_DIR" ]; then
    c_info "Copying project files from $SOURCE_DIR to $INSTALL_DIR ..."
    # Works whether or not we're already root: try plain mkdir first (the
    # no-op fast path when we are), fall back to sudo + handing ownership
    # to the invoking user when we're not (e.g. the macOS installer, which
    # deliberately never runs Homebrew/brew steps as root).
    if ! mkdir -p "$INSTALL_DIR" 2>/dev/null; then
      sudo mkdir -p "$INSTALL_DIR"
    fi
    if [ ! -w "$INSTALL_DIR" ]; then
      sudo chown "$(id -u):$(id -g)" "$INSTALL_DIR"
    fi
    if command -v rsync >/dev/null 2>&1; then
      rsync -a \
        --exclude '.git' \
        --exclude 'db.sqlite3' \
        --exclude '__pycache__' \
        --exclude '*.pyc' \
        --exclude 'env' \
        --exclude '.env' \
        "$SOURCE_DIR"/ "$INSTALL_DIR"/
    else
      # rsync isn't always present (e.g. a bare Fedora minimal install) -
      # fall back to cp and manually strip what shouldn't ship.
      cp -a "$SOURCE_DIR"/. "$INSTALL_DIR"/
      rm -rf "$INSTALL_DIR/.git" "$INSTALL_DIR/db.sqlite3" "$INSTALL_DIR/env"
      find "$INSTALL_DIR" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
    fi
    # An existing .env in the target directory (e.g. a re-run/upgrade) is
    # the user's real secrets file - never let a copy from the source
    # checkout clobber it.
    if [ -f "$SOURCE_DIR/.env" ] && [ ! -f "$INSTALL_DIR/.env" ]; then
      cp "$SOURCE_DIR/.env" "$INSTALL_DIR/.env"
    fi
  else
    c_info "Already running from $INSTALL_DIR, nothing to copy."
  fi

  c_ok "Project files are in place at $INSTALL_DIR"
}

# --- fail2ban profile -----------------------------------------------------
# Installs the project's baseline fail2ban jail (nginx scanner/404/403/DoS
# detection + escalating recidive bans) with the install directory and
# nginx container name substituted in. Never touches an existing
# jail.local so re-running the installer doesn't clobber local tuning.
install_fail2ban_profile() {
  local profile_src="$INSTALL_DIR/scripts/fail2ban"
  local nginx_container="pengin-pi-3-web-nginx"
  if [ -f "$INSTALL_DIR/.env" ]; then
    local web_container
    web_container=$(grep -E '^WEB_CONTAINER[[:space:]]*=' "$INSTALL_DIR/.env" | cut -d'=' -f2- | xargs)
    [ -n "$web_container" ] && nginx_container="${web_container}-nginx"
  fi

  if [ ! -d "$profile_src" ]; then
    c_warn "No bundled fail2ban profile found at $profile_src - skipping."
    return
  fi

  mkdir -p /etc/fail2ban/filter.d /etc/fail2ban/action.d
  cp "$profile_src"/filter.d/*.conf /etc/fail2ban/filter.d/
  sed \
    -e "s#{{INSTALL_DIR}}#${INSTALL_DIR}#g" \
    -e "s#{{NGINX_CONTAINER}}#${nginx_container}#g" \
    "$profile_src/action.d/nginx-blocklist.conf.template" > /etc/fail2ban/action.d/nginx-blocklist.conf

  if [ -f /etc/fail2ban/jail.local ]; then
    c_warn "/etc/fail2ban/jail.local already exists - leaving it as-is. Reference profile installed at $profile_src/jail.local.template."
  else
    sed \
      -e "s#{{INSTALL_DIR}}#${INSTALL_DIR}#g" \
      -e "s#{{NGINX_CONTAINER}}#${nginx_container}#g" \
      "$profile_src/jail.local.template" > /etc/fail2ban/jail.local
    c_ok "Installed fail2ban jail.local (nginx scanner/404/403/DoS detection + recidive escalation)."
  fi

  mkdir -p "$INSTALL_DIR/logs/nginx"
}

# Confirms fail2ban is actually running and reports it as a security
# warning (not a fatal error) if it isn't, per the release checklist -
# the stack should still come up, just loudly flagged as unguarded.
verify_fail2ban_running() {
  if ! command -v fail2ban-client >/dev/null 2>&1; then
    c_warn "SECURITY WARNING: fail2ban is not installed - this host is not guarding against brute-force/scanner traffic."
    return
  fi
  if command -v systemctl >/dev/null 2>&1 && systemctl is-active --quiet fail2ban 2>/dev/null; then
    c_ok "fail2ban is running."
  elif fail2ban-client ping >/dev/null 2>&1; then
    c_ok "fail2ban is running."
  else
    c_warn "SECURITY WARNING: fail2ban is installed but not running - this host is NOT guarding against brute-force/scanner traffic. Check 'systemctl status fail2ban' / fail2ban-client for errors."
  fi
}

# --- firewall ------------------------------------------------------------
# The stack needs 80/443 reachable (plain HTTP for the Let's Encrypt ACME
# challenge, both for the app). Fedora ships with firewalld enabled by
# default; Debian/Ubuntu only if the user turned ufw on themselves - in
# both cases, open the ports if the tool is present and active so people
# aren't left wondering why the site isn't reachable after a clean install.
open_firewall_ports_firewalld() {
  command -v firewall-cmd >/dev/null 2>&1 || return
  systemctl is-active --quiet firewalld 2>/dev/null || return
  c_info "Opening http/https in firewalld..."
  firewall-cmd --permanent --add-service=http >/dev/null
  firewall-cmd --permanent --add-service=https >/dev/null
  firewall-cmd --reload >/dev/null
  c_ok "firewalld: http/https open."
}

open_firewall_ports_ufw() {
  command -v ufw >/dev/null 2>&1 || return
  ufw status 2>/dev/null | grep -q "Status: active" || return
  c_info "Opening 80/443 in ufw..."
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
  c_ok "ufw: 80/443 open."
}
