#!/bin/bash
# Pengin Pi 3 installer - macOS.
#
# There's no dockerd-on-bare-metal on macOS, so this installs Docker
# Desktop via Homebrew and waits for you to start it. Deliberately never
# runs as root/sudo end-to-end - Homebrew refuses to run as root, so this
# only asks for a password (via sudo) for the specific steps that
# actually need it (writing to /opt, and starting fail2ban as a
# LaunchDaemon), same as the TODO's "ask for elevated perms" step just
# scoped to what macOS actually requires it for.
#
# Windows is intentionally not supported directly - run
# deploy_debian_ubuntu.sh inside WSL2 (Ubuntu) instead.
set -uo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
THIS_SCRIPT="$SOURCE_DIR/$(basename "${BASH_SOURCE[0]}")"
# shellcheck source=scripts/lib/common.sh
source "$SOURCE_DIR/scripts/lib/common.sh"

if [ "$(uname)" != "Darwin" ]; then
  c_err "This script is for macOS. Use deploy_fedora.sh or deploy_debian_ubuntu.sh instead (or, on Windows, deploy_debian_ubuntu.sh inside WSL2)."
  exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
  c_err "Don't run this with sudo/as root - Homebrew refuses to install formulae as root. Run it as your normal user; it will prompt for a password for the specific steps that need one."
  exit 1
fi

echo "=== Pengin Pi 3 - macOS installer ==="
echo
c_info "This will prompt for your password for the steps that need elevated privileges (writing to /opt, starting fail2ban)."
sudo -v

# --- Homebrew -------------------------------------------------------------

if ! command -v brew >/dev/null 2>&1; then
  c_info "Homebrew not found - installing it (Homebrew's official installer)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
fi
c_ok "Homebrew: $(brew --version | head -n1)"

# --- Docker Desktop ---------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
  c_info "Installing Docker Desktop (brew cask)..."
  brew install --cask docker
fi

if ! docker info >/dev/null 2>&1; then
  c_warn "Docker Desktop is installed but not running (it's a GUI app - macOS has no standalone docker daemon)."
  open -a Docker || true
  c_info "Waiting for Docker Desktop to start..."
  for i in $(seq 1 30); do
    if docker info >/dev/null 2>&1; then
      break
    fi
    sleep 2
  done
  if ! docker info >/dev/null 2>&1; then
    read -r -p "Docker still isn't responding. Open/finish setting up Docker Desktop now, then press Enter to continue (or Ctrl+C to abort): " _
    until docker info >/dev/null 2>&1; do
      read -r -p "Still can't reach Docker. Press Enter to check again once it's running: " _
    done
  fi
fi
c_ok "Docker is running: $(docker --version)"

if ! docker compose version >/dev/null 2>&1; then
  c_err "'docker compose' isn't available - Docker Desktop should include it. Try reinstalling: brew reinstall --cask docker"
  exit 1
fi

# --- install directory ---------------------------------------------------

prompt_install_dir
cd "$INSTALL_DIR"

# --- fail2ban -------------------------------------------------------------
# macOS uses pf, not iptables - the project's bundled fail2ban profile
# (scripts/fail2ban/) targets iptables/Docker's DOCKER-USER chain and
# isn't portable to pf as-is, so it's intentionally not installed here
# rather than shipping something that silently doesn't ban anything.
# macOS is realistically a dev/eval box, not the target for an
# internet-facing deployment anyway - use deploy_fedora.sh or
# deploy_debian_ubuntu.sh for that, where the real profile applies.

if ! command -v fail2ban-client >/dev/null 2>&1; then
  c_info "Installing fail2ban (brew)..."
  brew install fail2ban
fi
c_warn "The bundled fail2ban jail profile targets Linux iptables and isn't installed on macOS (see comment in this script). fail2ban itself will start, but without our nginx-scanner/DoS jails."
sudo brew services start fail2ban >/dev/null 2>&1 || true
verify_fail2ban_running

# --- hand off to the shared build/deploy step ------------------------

echo
c_info "Handing off to deploy.sh to build and start the stack..."
echo
exec "$INSTALL_DIR/deploy.sh"
