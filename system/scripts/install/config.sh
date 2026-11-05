#!/usr/bin/env bash
# ==============================================================================
# Vexlyx Installer — configuration collection (F5.1)
# Sourced by run.sh after lib.sh. Populates the VEXLYX_* variables every step
# script needs. Values already persisted in /etc/vexlyx/vexlyx.env (from a
# previous run) are reused automatically; an explicit env var passed this run
# always takes priority over both the persisted file and any prompt/default.
# ==============================================================================

ADMIN_PASSWORD_WAS_GENERATED=false
ADMIN_USER_CREATED=false

collect_config() {
  load_secrets_file

  env_or_prompt VEXLYX_DOMAIN "Panel domain (e.g. panel.example.com)" ""
  if [[ -z "${VEXLYX_DOMAIN}" ]]; then
    die "VEXLYX_DOMAIN is required. Re-run with: VEXLYX_DOMAIN=panel.example.com curl -fsSL https://vexlyx.atlantiqs.org/install.sh | bash"
  fi

  # Base domain deployed projects get subdomains under: {slug}.<base-domain>
  # (F5.9). Defaults to the panel domain itself — the common case — but can
  # be set to a separate zone (e.g. panel on panel.example.com, deployed
  # apps on apps.example.net) if the admin wants them split.
  env_or_prompt VEXLYX_BASE_DOMAIN "Base domain for deployed project subdomains" "${VEXLYX_DOMAIN}"

  env_or_prompt VEXLYX_ADMIN_EMAIL "Admin email" "admin@${VEXLYX_DOMAIN}"
  env_or_prompt VEXLYX_ADMIN_NAME "Admin display name" "Admin"

  if [[ -z "${VEXLYX_ADMIN_PASSWORD:-}" ]]; then
    if is_tty; then
      local typed_password=""
      read -r -s -p "Admin password (leave blank to auto-generate): " typed_password
      echo
      VEXLYX_ADMIN_PASSWORD="${typed_password}"
    fi
    if [[ -z "${VEXLYX_ADMIN_PASSWORD:-}" ]]; then
      VEXLYX_ADMIN_PASSWORD="$(rand_hex 12)"
      ADMIN_PASSWORD_WAS_GENERATED=true
    fi
  fi

  env_or_prompt VEXLYX_MAIL_HOSTNAME "Mail server hostname" "mail.${VEXLYX_DOMAIN}"
  env_or_prompt VEXLYX_MAIL_DOMAIN "Mail domain" "${VEXLYX_DOMAIN}"

  VEXLYX_ENABLE_PUBLIC_DNS="${VEXLYX_ENABLE_PUBLIC_DNS:-false}"
  VEXLYX_MAIL_STATE_DIR="${VEXLYX_MAIL_STATE_DIR:-/var/lib/vexlyx/mail}"
  [[ "$VEXLYX_MAIL_STATE_DIR" =~ ^/[a-zA-Z0-9_./-]+$ && "$VEXLYX_MAIL_STATE_DIR" != / ]] || die "VEXLYX_MAIL_STATE_DIR must be a dedicated absolute path without whitespace or shell characters."
  VEXLYX_REPO_URL="${VEXLYX_REPO_URL:-https://github.com/atlantiqshq/vexlyx.git}"
  VEXLYX_REPO_REF="${VEXLYX_REPO_REF:-latest}"

  export VEXLYX_DOMAIN VEXLYX_BASE_DOMAIN VEXLYX_ADMIN_EMAIL VEXLYX_ADMIN_NAME VEXLYX_ADMIN_PASSWORD
  export VEXLYX_MAIL_HOSTNAME VEXLYX_MAIL_DOMAIN VEXLYX_ENABLE_PUBLIC_DNS
  export VEXLYX_MAIL_STATE_DIR
  export VEXLYX_REPO_URL VEXLYX_REPO_REF VEXLYX_HOME
}

# Adds REDIS_PASSWORD to a secrets file that has none (an install from before
# Redis required a password). A password already present is never replaced, so
# re-running the installer cannot rotate it out from under live sessions.
ensure_redis_password() {
  if [[ -n "$(sed -n 's/^REDIS_PASSWORD=//p' "${VEXLYX_SECRETS_FILE}" | tail -n 1)" ]]; then
    return 0
  fi
  upsert_secret REDIS_PASSWORD "$(rand_hex 32)"
  log_ok "Generated a Redis password in ${VEXLYX_SECRETS_FILE}."
}

# Generates the long-lived application secrets exactly once. Safe to call on
# every run — skips generation entirely once the secrets file exists, so a
# re-run never rotates a live SESSION_SECRET or database password out from
# under a running install.
generate_secrets() {
  if [[ -f "${VEXLYX_SECRETS_FILE}" ]]; then
    log_ok "Secrets already present at ${VEXLYX_SECRETS_FILE} — leaving them untouched."
    load_secrets_file
    if ! grep -q '^VEXLYX_MAIL_STATE_DIR=' "${VEXLYX_SECRETS_FILE}"; then
      printf '\nVEXLYX_MAIL_STATE_DIR=%s\n' "${VEXLYX_MAIL_STATE_DIR:-/var/lib/vexlyx/mail}" >> "${VEXLYX_SECRETS_FILE}"
    fi
    ensure_redis_password
    return 0
  fi

  log_info "Generating application secrets (first run only)..."
  SESSION_SECRET="$(rand_hex 32)"
  ENCRYPTION_KEY="$(rand_hex 32)"
  POSTGRES_PASSWORD="$(rand_hex 16)"
  MYSQL_ROOT_PASSWORD="$(rand_hex 16)"
  MYSQL_PASSWORD="$(rand_hex 16)"
  REDIS_PASSWORD="$(rand_hex 32)"
  export SESSION_SECRET ENCRYPTION_KEY POSTGRES_PASSWORD MYSQL_ROOT_PASSWORD MYSQL_PASSWORD REDIS_PASSWORD

  install -d -m 0700 "${VEXLYX_SECRETS_DIR}"
  umask 077
  cat > "${VEXLYX_SECRETS_FILE}" <<EOF
# Vexlyx generated secrets and install configuration — DO NOT COMMIT.
# Created by the installer on $(date -u +%Y-%m-%dT%H:%M:%SZ). Re-running the
# installer reuses this file; delete it only if you intend to rotate every
# secret below and accept that existing sessions/encrypted data become invalid.
VEXLYX_DOMAIN=${VEXLYX_DOMAIN}
VEXLYX_BASE_DOMAIN=${VEXLYX_BASE_DOMAIN}
VEXLYX_ADMIN_EMAIL=${VEXLYX_ADMIN_EMAIL}
VEXLYX_MAIL_HOSTNAME=${VEXLYX_MAIL_HOSTNAME}
VEXLYX_MAIL_DOMAIN=${VEXLYX_MAIL_DOMAIN}
VEXLYX_MAIL_STATE_DIR=${VEXLYX_MAIL_STATE_DIR}
SESSION_SECRET=${SESSION_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
MYSQL_PASSWORD=${MYSQL_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}
EOF
  chmod 0600 "${VEXLYX_SECRETS_FILE}"
  log_ok "Secrets written to ${VEXLYX_SECRETS_FILE} (mode 0600)."
}
