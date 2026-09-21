#!/bin/bash
# Pengin Pi 3 installer - Fedora (dnf).
#
# Installs Docker CE + the Compose v2 plugin from Docker's own repo (not
# Fedora's, which lags - this is the same class of problem that forced a
# manual docker-compose install on Amazon Linux EC2 boxes in the past),
# installs and configures fail2ban with the project's baseline profile,
# then hands off to deploy.sh to build and bring up the stack.
set -uo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THIS_SCRIPT="$SOURCE_DIR/$(basename "${BASH_SOURCE[0]}")"
# shellcheck source=scripts/lib/common.sh
source "$SOURCE_DIR/scripts/lib/common.sh"

if ! command -v dnf >/dev/null 2>&1; then
  c_err "dnf not found - this script is for Fedora (or dnf-based RHEL family distros). Use deploy_debian_ubuntu.sh or deploy_mac.sh instead."
  exit 1
fi

require_root "$@"

echo "=== Pengin Pi 3 - Fedora installer ==="
echo

prompt_install_dir
cd "$INSTALL_DIR"

# --- Docker -------------------------------------------------------------

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  c_ok "Docker + Compose plugin already installed ($(docker --version))."
else
  c_info "Installing Docker CE from Docker's official repo..."
  dnf -y install dnf-plugins-core
  dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
  dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
  c_ok "Docker installed: $(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
  c_err "docker compose (the v2 plugin) still isn't available after install - check for a conflicting 'moby-engine'/'podman-docker' package and re-run."
  exit 1
fi

systemctl is-active --quiet docker || systemctl start docker

# --- fail2ban -------------------------------------------------------------

if ! command -v fail2ban-client >/dev/null 2>&1; then
  c_info "Installing fail2ban..."
  dnf -y install fail2ban
fi
install_fail2ban_profile
systemctl enable --now fail2ban >/dev/null 2>&1 || systemctl restart fail2ban
verify_fail2ban_running

# --- firewall -------------------------------------------------------------

open_firewall_ports_firewalld

# --- hand off to the shared build/deploy step ------------------------

echo
c_info "Handing off to deploy.sh to build and start the stack..."
echo
exec "$INSTALL_DIR/deploy.sh"
