#!/bin/bash
# Pengin Pi 3 installer - Debian / Ubuntu (apt). Also runs fine under WSL2
# on Windows (Ubuntu app) - see README/install_readme.md; there is no
# separate Windows script, WSL is the recommended path there.
#
# Installs Docker CE + the Compose v2 plugin from Docker's own apt repo
# (not the distro's, which lags - the same class of problem that forced a
# manual docker-compose install on Amazon Linux EC2 boxes in the past),
# installs and configures fail2ban with the project's baseline profile,
# then hands off to deploy.sh to build and bring up the stack.
set -uo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THIS_SCRIPT="$SOURCE_DIR/$(basename "${BASH_SOURCE[0]}")"
# shellcheck source=scripts/lib/common.sh
source "$SOURCE_DIR/scripts/lib/common.sh"

if ! command -v apt-get >/dev/null 2>&1; then
  c_err "apt-get not found - this script is for Debian/Ubuntu (or WSL running one of them). Use deploy_fedora.sh or deploy_mac.sh instead."
  exit 1
fi

require_root "$@"

echo "=== Pengin Pi 3 - Debian/Ubuntu installer ==="
if grep -qi microsoft /proc/version 2>/dev/null; then
  c_info "WSL detected. This will work as long as the Docker daemon is reachable from here - either via Docker Desktop's WSL integration, or by running dockerd directly inside this WSL distro."
fi
echo

prompt_install_dir
cd "$INSTALL_DIR"

# --- Docker -------------------------------------------------------------

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  c_ok "Docker + Compose plugin already installed ($(docker --version))."
else
  c_info "Installing Docker CE from Docker's official apt repo..."
  apt-get update
  apt-get -y install ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  . /etc/os-release
  DOCKER_APT_ID="$ID"
  # WSL Ubuntu reports ID=ubuntu same as bare-metal Ubuntu - the docker
  # apt repo layout is identical either way, so no special-casing needed.
  curl -fsSL "https://download.docker.com/linux/${DOCKER_APT_ID}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${DOCKER_APT_ID} $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker 2>/dev/null || service docker start
  c_ok "Docker installed: $(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
  c_err "docker compose (the v2 plugin) still isn't available after install - check the output above and re-run."
  exit 1
fi

if command -v systemctl >/dev/null 2>&1 && systemctl status >/dev/null 2>&1; then
  systemctl is-active --quiet docker || systemctl start docker
elif ! docker info >/dev/null 2>&1; then
  c_warn "No systemd available (common under WSL without systemd enabled in /etc/wsl.conf) and the Docker daemon isn't reachable. Start it manually (e.g. 'sudo dockerd &' or enable Docker Desktop's WSL integration) and re-run."
fi

# --- fail2ban -------------------------------------------------------------

if ! command -v fail2ban-client >/dev/null 2>&1; then
  c_info "Installing fail2ban..."
  apt-get -y install fail2ban
fi
install_fail2ban_profile
if command -v systemctl >/dev/null 2>&1 && systemctl status >/dev/null 2>&1; then
  systemctl enable --now fail2ban >/dev/null 2>&1 || systemctl restart fail2ban
  verify_fail2ban_running
else
  c_warn "No systemd available - start fail2ban yourself (e.g. 'sudo service fail2ban start') if this host needs it. Under WSL, a dev box behind Windows' own network stack usually doesn't."
fi

# --- firewall -------------------------------------------------------------

open_firewall_ports_ufw

# --- hand off to the shared build/deploy step ------------------------

echo
c_info "Handing off to deploy.sh to build and start the stack..."
echo
exec "$INSTALL_DIR/deploy.sh"
