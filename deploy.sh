#!/bin/bash
# Builds and brings up the docker-compose.yml stack (postgres, web, nginx,
# ferretdb, redis) from whatever directory this script lives in.
#
# Normally called as the last step of deploy_fedora.sh /
# deploy_debian_ubuntu.sh / deploy_mac.sh, after they've installed
# Docker/Compose and fail2ban - but it also works standalone if you
# already have Docker + the `docker compose` plugin set up and just want
# to (re)deploy from an existing checkout.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "$SCRIPT_DIR/scripts/lib/common.sh" ]; then
  # shellcheck source=scripts/lib/common.sh
  source "$SCRIPT_DIR/scripts/lib/common.sh"
else
  c_info() { printf '[*] %s\n' "$*"; }
  c_ok()   { printf '[OK] %s\n' "$*"; }
  c_warn() { printf '[!] %s\n' "$*"; }
  c_err()  { printf '[ERROR] %s\n' "$*" >&2; }
fi

ENV_FILE="$SCRIPT_DIR/.env"

REQUIRED_VARS=(
  "DB_CONTAINER"
  "REDIS_CONTAINER"
  "WEB_CONTAINER"
  "DB_NAME"
  "DB_USER"
  "DB_PASSWORD"
  "FERRETDB_DB"
  "URL"
  "SECRET_KEY"
)

# Checked but never fatal - main/settings.py falls back gracefully when
# these are absent (email prints to console, reCAPTCHA is skipped, S3
# falls back to local storage), so a missing one is a warning, not a
# reason to refuse to deploy.
OPTIONAL_VARS_WARN=(
  "SES_SENDER"
  "SES_USERNAME_SMTP"
  "SES_PASSWORD_SMTP"
)

# --- 1. docker + compose sanity check --------------------------------

if ! command -v docker >/dev/null 2>&1; then
  c_err "docker is not installed or not on PATH. Run deploy_fedora.sh, deploy_debian_ubuntu.sh, or deploy_mac.sh first."
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  c_err "'docker compose' (the v2 plugin) is not available. Run deploy_fedora.sh, deploy_debian_ubuntu.sh, or deploy_mac.sh first."
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  c_err "Docker daemon isn't reachable (is it running, and do you have permission to talk to it?)."
  exit 1
fi

# --- 2. helpers for writing into .env ---------------------------------

random_token() {
  local len="$1"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex $(( (len + 1) / 2 )) | head -c "$len"
  else
    tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$len"
  fi
}

set_env_value() {
  local key="$1" value="$2"
  local escaped
  escaped=$(printf '%s' "$value" | sed -e 's/[\/&]/\\&/g')
  if grep -qE "^${key}[[:space:]]*=" "$ENV_FILE"; then
    # -i.bak suffix form works identically on both GNU sed (Linux) and
    # BSD sed (macOS) - the bare `-i` flag doesn't.
    sed -i.bak -E "s|^${key}[[:space:]]*=.*|${key}=${escaped}|" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

generate_degraded_env() {
  c_warn "Generating a minimal .env with random secrets and no domain/email/S3/reCAPTCHA configuration."
  c_warn "SECURITY AND FEATURES ARE DEGRADED: no real domain means no valid SSL cert, email sends nowhere, reCAPTCHA is off. Replace $ENV_FILE with real values when you're ready."
  cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
  set_env_value SECRET_KEY "$(random_token 50)"
  set_env_value DEBUG "False"
  set_env_value DB_NAME "pengin_pi_3"
  set_env_value DB_USER "pengin_pi_3"
  set_env_value DB_PASSWORD "$(random_token 24)"
  set_env_value DB_CONTAINER "pengin-pi-3-db"
  set_env_value WEB_CONTAINER "pengin-pi-3-web"
  set_env_value REDIS_CONTAINER "pengin-pi-3-redis"
  set_env_value FERRETDB_DB "postgres"
  set_env_value URL "localhost"
  set_env_value URL2 "localhost"
}

# --- 3. get a .env in place --------------------------------------------

if [ ! -f "$ENV_FILE" ]; then
  while true; do
    c_warn "No .env file found at $ENV_FILE."
    read -r -p "Path to an existing .env file to copy in (leave blank to skip): " supplied
    if [ -n "$supplied" ]; then
      if [ -f "$supplied" ]; then
        cp "$supplied" "$ENV_FILE"
        c_ok "Copied $supplied to $ENV_FILE"
        break
      else
        c_err "No file found at '$supplied' - try again."
        continue
      fi
    fi
    read -r -p "Skip supplying a .env file? Core features and security will be degraded. Are you sure? [y/N] " confirm
    case "$confirm" in
      [yY]|[yY][eE][sS])
        generate_degraded_env
        break
        ;;
      *)
        continue
        ;;
    esac
  done
fi

# --- 4. validate .env ---------------------------------------------------

c_info "Validating project environment parameters..."
MISSING_COUNT=0
for VAR in "${REQUIRED_VARS[@]}"; do
  VALUE=$(grep -E "^${VAR}[[:space:]]*=" "$ENV_FILE" | cut -d'=' -f2- | xargs)
  if [ -z "$VALUE" ] || [ "$VALUE" == "SECRET" ]; then
    c_err "Missing or invalid required parameter: $VAR"
    MISSING_COUNT=$((MISSING_COUNT + 1))
  fi
done
if [ "$MISSING_COUNT" -gt 0 ]; then
  c_err "Initialization halted: $MISSING_COUNT configuration error(s) in $ENV_FILE."
  exit 1
fi
c_ok "Required configuration present."

for VAR in "${OPTIONAL_VARS_WARN[@]}"; do
  VALUE=$(grep -E "^${VAR}[[:space:]]*=" "$ENV_FILE" | cut -d'=' -f2- | xargs)
  if [ -z "$VALUE" ]; then
    c_warn "$VAR is not set - outbound email will be printed to the container log instead of actually sent."
  fi
done

SITE_KEY=$(grep -E '^RECAPTCHA_SITE_KEY[[:space:]]*=' "$ENV_FILE" | cut -d'=' -f2- | xargs)
SECRET_KEY_RECAPTCHA=$(grep -E '^RECAPTCHA_SECRET_KEY[[:space:]]*=' "$ENV_FILE" | cut -d'=' -f2- | xargs)
if [ -z "$SITE_KEY" ] || [ -z "$SECRET_KEY_RECAPTCHA" ]; then
  c_warn "reCAPTCHA key missing - security degraded (anonymous-facing forms run without bot verification)."
fi

# --- 5. reverse proxy: bundled Traefik, or bring-your-own -------------

mkdir -p "$SCRIPT_DIR/logs/nginx"

read -r -p "Do you already have your own Traefik (or other reverse proxy) managing the 'root_proxy' Docker network on this host? [y/N] " has_proxy
case "$has_proxy" in
  [yY]*)
    c_info "Skipping the bundled reverse proxy - making sure the 'root_proxy' network exists for the app stack to attach to."
    docker network inspect root_proxy >/dev/null 2>&1 || docker network create root_proxy >/dev/null
    ;;
  *)
    ACME_EMAIL=$(grep -E '^TRAEFIK_ACME_EMAIL[[:space:]]*=' "$ENV_FILE" | cut -d'=' -f2- | xargs)
    if [ -z "$ACME_EMAIL" ]; then
      read -r -p "Email for Let's Encrypt certificate notices (used by the bundled Traefik): " ACME_EMAIL
      set_env_value TRAEFIK_ACME_EMAIL "$ACME_EMAIL"
    fi
    c_info "Bringing up the bundled Traefik reverse proxy (docker-compose.traefik.yml)..."
    if ! docker compose -f docker-compose.traefik.yml up -d; then
      c_err "Failed to start the bundled Traefik reverse proxy - see the output above."
      exit 1
    fi
    c_ok "Bundled Traefik is up."
    ;;
esac

# --- 6. build and deploy the app stack ---------------------------------

c_info "Building and bringing up services..."
docker compose down
if ! docker compose up --build -d; then
  c_err "docker compose up failed - see the output above. Run 'docker compose logs' for details."
  exit 1
fi

# --- 7. report status -----------------------------------------------------

c_ok "Deployment successfully initialized."
echo
docker compose ps
echo
c_info "Useful commands:"
echo "    docker compose logs -f web       # tail the app's logs"
echo "    docker compose ps                # container status"
echo "    docker compose down              # stop the stack"
echo "    docker compose up -d             # start it again (no rebuild)"
echo "    docker compose up --build -d     # rebuild and start (after a code update)"
if [ "$has_proxy" != "y" ] && [ "$has_proxy" != "Y" ]; then
  echo "    docker compose -f docker-compose.traefik.yml logs -f traefik   # reverse proxy / cert issuance logs"
fi
URL_VALUE=$(grep -E '^URL[[:space:]]*=' "$ENV_FILE" | cut -d'=' -f2- | xargs)
if [ "$URL_VALUE" == "localhost" ]; then
  echo
  c_warn "URL is set to 'localhost' - there's no real domain, so no valid SSL certificate was issued. Visit http://<this-machine's-address>/ for now, and set URL/URL2 in $ENV_FILE to a real domain when you're ready."
fi
