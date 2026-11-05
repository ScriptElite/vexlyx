#!/usr/bin/env bash
set -euo pipefail

log_step "[16/16] Done"

COMPOSE=(docker compose --env-file "${VEXLYX_SECRETS_FILE}" -f docker-compose.yml -f docker-compose.prod.yml)

# The ACME store is read into a variable and matched in the shell. Piping `cat`
# into `grep -q` instead reports "no certificate" on a server that does have one
# (#184): `grep -Eq` exits the moment it matches, the writer is then killed by
# SIGPIPE, and `set -o pipefail` (line 2) turns that signal into a failed
# pipeline even though the match succeeded — which happens for any store bigger
# than the pipe buffer, i.e. every panel holding more than a couple of certs.
read_acme_store() {
  "${COMPOSE[@]}" exec -T traefik cat /etc/traefik/acme.json 2>/dev/null || true
}

acme_store_has_certificate_for() {
  local store="$1" hostname="$2"
  # Traefik writes `"main": "host"`; the compact form is accepted too so this
  # stays as tolerant as the `"main\": ?\""` regex it replaces.
  [[ "${store}" == *"\"main\": \"${hostname}\""* || "${store}" == *"\"main\":\"${hostname}\""* ]]
}

# Prints one line per panel hostname that has no certificate; no output means
# every name is covered. Each hostname is reported on its own line so a
# partially-issued pair names the hostname that is actually missing.
missing_certificates() {
  local store="$1" hostname
  for hostname in "${VEXLYX_DOMAIN}" "api.${VEXLYX_DOMAIN}"; do
    acme_store_has_certificate_for "${store}" "${hostname}" || printf '%s\n' "${hostname}"
  done
}

# Traefik requests certificates on first start and Let's Encrypt takes up to a
# minute or so to answer; checking once, straight away, made a healthy install
# end with a warning.
log_info "Waiting for the Let's Encrypt certificates for ${VEXLYX_DOMAIN}..."
cert_tries=45
until [[ -z "$(missing_certificates "$(read_acme_store)")" ]] || (( cert_tries == 0 )); do
  sleep 2
  (( cert_tries-- ))
done

echo ""
echo "  Vexlyx is installed."
echo ""
echo "  Panel:        https://${VEXLYX_DOMAIN}"
echo "  Admin email:  ${VEXLYX_ADMIN_EMAIL}"
if [[ "${ADMIN_USER_CREATED}" != "true" ]]; then
  echo "  Admin password: unchanged — an admin account with this email already existed."
elif [[ "${ADMIN_PASSWORD_WAS_GENERATED}" == "true" ]]; then
  # Shown on the terminal only, never through the tee into ${VEXLYX_STATE_FILE}.
  if show_secret_to_operator "  Admin password (generated, shown once): ${VEXLYX_ADMIN_PASSWORD}" \
    && show_secret_to_operator "  Save it now. It is not written to ${VEXLYX_STATE_FILE} or ${VEXLYX_SECRETS_FILE}; only its Argon2id hash is stored, so it cannot be recovered."; then
    echo "  Admin password (generated): shown on your terminal only, not recorded in ${VEXLYX_STATE_FILE}."
  else
    echo "  Admin password (generated): could not be shown because no terminal is attached, and it is deliberately not logged."
    echo "  Create a new admin with the command in the Troubleshooting guide."
  fi
else
  echo "  Admin password: the one you provided via VEXLYX_ADMIN_PASSWORD."
fi
echo ""
echo "  Install root:  ${VEXLYX_HOME}"
echo "  Secrets file:  ${VEXLYX_SECRETS_FILE} (mode 0600 — back this up)"
echo ""
if [[ -n "${VEXLYX_PUBLIC_IP:-}" ]]; then
  echo "  Server public IP: ${VEXLYX_PUBLIC_IP}"
  echo ""
  echo "  Point these DNS records at it before the panel/api/webmail/deployed"
  echo "  projects will be reachable:"
  echo "    A     ${VEXLYX_DOMAIN}              -> ${VEXLYX_PUBLIC_IP}"
  echo "    A     api.${VEXLYX_DOMAIN}          -> ${VEXLYX_PUBLIC_IP}"
  echo "    A     webmail.${VEXLYX_DOMAIN}      -> ${VEXLYX_PUBLIC_IP}"
  echo "    A     *.${VEXLYX_BASE_DOMAIN}       -> ${VEXLYX_PUBLIC_IP}  (deployed project subdomains)"
  if [[ "${VEXLYX_BASE_DOMAIN}" != "${VEXLYX_DOMAIN}" ]]; then
    echo "    (base domain for deployed projects is configured separately from the panel domain —"
    echo "     the api. record above is required in this case, not just covered by the wildcard)"
  fi
  echo ""
  echo "  Inbound hosted mail requires these additional DNS records:"
  echo "    A     ${VEXLYX_MAIL_HOSTNAME}       -> ${VEXLYX_PUBLIC_IP}"
  echo "    MX    ${VEXLYX_MAIL_DOMAIN}         -> ${VEXLYX_MAIL_HOSTNAME}  (priority 10)"
  echo ""
  echo "  This same info is available later in the dashboard under Settings."
else
  echo "  Could not auto-detect this server's public IP — point the following"
  echo "  at whatever your server's public IP turns out to be:"
  echo "    A     ${VEXLYX_DOMAIN}"
  echo "    A     api.${VEXLYX_DOMAIN}"
  echo "    A     webmail.${VEXLYX_DOMAIN}"
  echo "    A     *.${VEXLYX_BASE_DOMAIN}   (deployed project subdomains)"
  echo ""
  echo "  Inbound hosted mail also requires:"
  echo "    A     ${VEXLYX_MAIL_HOSTNAME}"
  echo "    MX    ${VEXLYX_MAIL_DOMAIN}     -> ${VEXLYX_MAIL_HOSTNAME}  (priority 10)"
fi
echo ""
echo "  Panel emails (password resets, security alerts) are sent as"
echo "  notifications@${VEXLYX_DOMAIN} from this server. To keep them out of spam, publish"
echo "  an SPF, DKIM and DMARC record for ${VEXLYX_DOMAIN} — Settings > System Email in"
echo "  the dashboard lists the exact values and checks them live."
echo "  Configure PTR/reverse DNS for ${VEXLYX_MAIL_HOSTNAME} at your hosting provider,"
echo "  and allow inbound TCP ports 25, 587 and 993 for SMTP submission and IMAP."
echo "  If your host blocks outbound port 25, set EMAIL_SMTP_HOST (and credentials) to use"
echo "  an external SMTP relay instead — see docs/dev/system-transactional-email.md."
echo ""
echo "  Adminer (web database browser) is disabled in production by default."
echo "  To enable it (HTTPS + basic auth at adminer.${VEXLYX_DOMAIN}), run:"
echo "    sudo bash ${VEXLYX_HOME}/system/scripts/enable-adminer.sh"
echo ""
echo "  Manage the stack:"
echo "    cd ${VEXLYX_HOME}"
echo "    docker compose --env-file ${VEXLYX_SECRETS_FILE} -f docker-compose.yml -f docker-compose.prod.yml ps"
echo "    docker compose --env-file ${VEXLYX_SECRETS_FILE} -f docker-compose.yml -f docker-compose.prod.yml logs -f"
echo ""
echo "  To upgrade or repair the install, just re-run install.sh — every step is safe to run again."
echo ""
missing="$(missing_certificates "$(read_acme_store)")"
if [[ -n "${missing}" ]]; then
  while IFS= read -r hostname; do
    log_warn "No Let's Encrypt certificate detected yet for ${hostname}."
  done <<< "${missing}"
  log_warn "If ${VEXLYX_DOMAIN} does not yet point at this server's public IP, Traefik will keep retrying automatically once DNS propagates — the panel is reachable over HTTPS with a browser warning in the meantime."
fi
