# Webmail (Roundcube) (F4.4)

> **Feature:** F4.4 — Webmail (Roundcube)
> **Status:** 🟢 COMPLETED
> **Package:** `@vexlyx/api`, `@vexlyx/dashboard`, `@vexlyx/shared`
> **Depends on:** F4.1 (Postfix SMTP), F4.2 (Dovecot IMAP), F4.3 (Mailbox Management UI)

---

## 1. Overview

F4.4 adds browser-based email access for mailboxes created in F4.3, so users who don't want to configure a desktop/mobile mail client can read and send mail directly from the Vexlyx dashboard.

- **Single shared Roundcube instance** — one container (`vexlyx-roundcube`), not a per-domain deployment. This mirrors how `adminer` is a single shared infra container rather than one-per-database.
- **No changes to Postfix/Dovecot config** — Roundcube authenticates over IMAP (`dovecot:143`, STARTTLS) and sends over SMTP (`postfix:587`, STARTTLS) using the mailbox's own address + password, the exact same Dovecot SASL path Postfix already uses for authenticated submission. **STARTTLS is mandatory, not optional** — Dovecot's `ssl = required` rejects auth on a plaintext connection, so Roundcube's `ROUNDCUBEMAIL_DEFAULT_HOST`/`ROUNDCUBEMAIL_SMTP_SERVER` use the `tls://` scheme (not a bare hostname) to force it. See §5.
- **Manual login only** — no SSO/autologin. Users type the mailbox address and password shown when the mailbox was created (or reset) in the Mailboxes tab. Vexlyx never stores or has access to a mailbox's plaintext password (only the Argon2id hash), so autologin isn't possible without a separate credential-recovery design.
- **SQLite persistence** — Roundcube's own state (address book, UI prefs, header cache) lives in a bind-mounted SQLite file, not a shared Postgres database.

---

## 2. Architecture & Data Flow

```
┌──────────────────────────────────────────────────────────────┐
│                     Next.js Dashboard UI                      │
│  /mail → "Webmail" tab (WebmailPanel.tsx)                     │
│  status card + "Open Webmail" link (opens in new tab)         │
└──────────────────────────────┬───────────────────────────────┘
                                │ HTTP / JSON
                                ▼
┌──────────────────────────────────────────────────────────────┐
│                     Fastify API Server                        │
│  GET /api/mail/webmail/status   container + reachability check│
└───────────────────────────────┬───────────────────────────────┘
                                 ▼
                system/python/webmail_manager.py
                  status(host, port) → TCP probe + docker inspect
                                 │
                                 ▼
                     vexlyx-roundcube container
              (roundcube/roundcubemail:1.6.18-apache)
                                 │
                  ┌──────────────┴──────────────┐
                  ▼                              ▼
        dovecot:143 (IMAP, STARTTLS —           postfix:587 (SMTP,
        Dovecot's `ssl = required`               STARTTLS + Dovecot
        rejects plaintext auth)                  SASL auth — same path
                                                  as any mail client)
```

The user's browser talks directly to Roundcube (via Traefik at `webmail.vexlyx.localhost`, or the mapped host port `8089` in dev) — the Fastify API is only involved in the status check, not in serving webmail itself.

---

## 3. Files

**Infrastructure**
- `docker-compose.yml` — `roundcube` service: official image, no custom Dockerfile (unlike Postfix/Dovecot, which need custom config). Joins `default` (to reach `dovecot`/`postfix`, and to be reachable, by container name) and `traefik-net`. Also carries `traefik.enable=true` Docker labels for `webmail.vexlyx.localhost`, kept for portability to environments where Traefik's Docker provider works — see the routing note below.
- `docker/traefik/dynamic/webmail.yml` — the route that actually works in this dev environment: a Traefik **file-provider** static router for `webmail.vexlyx.localhost` → `http://vexlyx-roundcube:80`, the same mechanism `DomainService.syncTraefikRouter()` (F3.3/F3.4) uses for per-domain routing. See §5.
- `vexlyx_roundcube_data` named volume → `/var/roundcube/db` (SQLite file).
- `docker/roundcube/config/local.inc.php`, bind-mounted read-only to `/var/roundcube/config/` (the official image auto-includes any `*.php` dropped there) — sets `imap_conn_options`/`smtp_conn_options`. TLS verification is **on by default**; only `ROUNDCUBE_MAIL_TLS_VERIFY=false` (set by `docker-compose.yml`, i.e. local development) relaxes it, and `docker-compose.prod.yml` sets it back to `true` and supplies `ROUNDCUBE_MAIL_TLS_PEER_NAME`. See §5 and §5.1.

**System layer**
- `system/python/webmail_manager.py` — `status` command: TCP-probes the mapped host port and runs `docker inspect vexlyx-roundcube`, mirroring `dovecot_manager.py::get_dovecot_status()`.

**API**
- `apps/api/src/config/env.ts` / `.env.example` — `WEBMAIL_URL`, `WEBMAIL_PORT`, `WEBMAIL_CONTAINER_NAME`.
- `apps/api/src/modules/mail/service.ts` — `runWebmailManager()` helper (same shape as `runPostfixManager`/`runDovecotManager`) and `MailService.getWebmailStatus()`.
- `apps/api/src/modules/mail/routes.ts` — `GET /api/mail/webmail/status` (auth required).

**Shared**
- `packages/shared/src/schemas/mail.ts` — `WebmailStatusSchema` / `WebmailStatusResponse`.

**Dashboard**
- `apps/dashboard/src/hooks/useWebmail.ts` — fetches webmail status on mount.
- `apps/dashboard/src/components/mail/WebmailPanel.tsx` — status card + "Open Webmail" button (`window.open`, new tab) + a note on how to log in.
- `apps/dashboard/src/app/(panel)/mail/page.tsx` — third `TabsTrigger`/`TabsContent` ("Webmail") alongside "Domains & DKIM" and "Mailboxes".

---

## 4. How to Test

1. `docker compose up -d roundcube` → `docker ps` shows `vexlyx-roundcube` running and healthy.
2. `curl http://localhost:8089/` → Roundcube's login page returns `200`.
3. In the dashboard, open `/mail` → "Webmail" tab shows a "Running" badge and an "Open Webmail" button.
4. Log in to Roundcube with a mailbox address + password from the Mailboxes tab (create one first, or reset an existing one to get a fresh password) → inbox loads.
5. Compose and send an email to another local mailbox → delivered (validates `postfix:587` STARTTLS + Dovecot SASL auth).
6. Upload/download an attachment → round-trips.
7. Add a contact to the address book, restart the container (`docker compose restart roundcube`), confirm the contact persists (validates the SQLite volume).
8. `GET /api/mail/webmail/status` (authenticated) → returns `{ service: "roundcube", status: "active", containerRunning: true, url, lastChecked }`.

## 5. Fixed Bug — "Login failed" on Every Correct Password

**Symptom:** every Roundcube login attempt returned "Login failed", even with a password copied directly from the Mailboxes tab's one-time reveal dialog.

**Root cause:** `docker/dovecot/dovecot.conf` sets `ssl = required`, which makes Dovecot refuse the `AUTHENTICATE`/`LOGIN` command entirely on a connection that hasn't negotiated TLS. The initial compose config pointed Roundcube at a bare hostname (`ROUNDCUBEMAIL_DEFAULT_HOST: dovecot`, `ROUNDCUBEMAIL_SMTP_SERVER: postfix`) with no scheme — Roundcube's IMAP/SMTP client only attempts STARTTLS when the host is prefixed with `tls://` (or `ssl://` for implicit TLS), so it was authenticating in plaintext and getting silently rejected. `docker exec vexlyx-dovecot doveadm auth test ...` and the Dovecot log (`auth failed`) confirmed the passdb layer itself was fine — this was purely a transport-negotiation gap.

**Fix (`docker-compose.yml`):**
```yaml
ROUNDCUBEMAIL_DEFAULT_HOST: tls://dovecot   # was: dovecot
ROUNDCUBEMAIL_SMTP_SERVER: tls://postfix    # was: postfix
```
Forcing STARTTLS then hit a second, expected development problem: Dovecot/Postfix's local self-signed cert isn't trusted by PHP's default TLS verification, so the handshake failed again. `docker/roundcube/config/local.inc.php` (auto-included by the official image from `/var/roundcube/config/*.php`) sets `imap_conn_options`/`smtp_conn_options` to skip verification for the internal container connection **in development only** (see §5.1 — this used to be unconditional, which also disabled verification in production, #42).

**Verified independently of Roundcube's UI**, from inside the `vexlyx_default` network:
```
curl --url 'imap://dovecot:143/' --user 'user@domain:password' --ssl-reqd -k   # -> A004 OK Logged in
curl --url 'smtp://postfix:587/' --user 'user@domain:password' --ssl-reqd -k … # -> 235 Authentication successful
```

### 5.1 TLS verification policy (#42)

| Setting | Dev (`docker-compose.yml`) | Production (`docker-compose.prod.yml`) |
|---|---|---|
| `ROUNDCUBE_MAIL_TLS_VERIFY` | `"false"` — self-signed container cert, no verification | `"true"` — verify chain **and** name |
| `ROUNDCUBE_MAIL_TLS_PEER_NAME` | unset | `${VEXLYX_MAIL_HOSTNAME}` |

How it works (`docker/roundcube/config/local.inc.php`):

- **Fail secure.** Verification is disabled only when the variable is exactly the string `false`. Absent, empty, `FALSE`, `0` or a typo all keep it enabled, so a misconfiguration can never silently turn it off in production. The failure mode of a bad dev setting is a visible "Login failed", not a silent MITM window.
- **Why `peer_name`.** Roundcube connects to the internal service names (`tls://dovecot`, `tls://postfix`), but the production certificate (synced from Traefik/Let's Encrypt by `system/scripts/install/sync-mail-tls.sh`) is issued for the public mail hostname. PHP is told to validate the certificate against `ROUNDCUBE_MAIL_TLS_PEER_NAME` rather than the service name. Without it, strict verification would reject every login.
- **A blank peer name says so.** The name is applied only when it is a non-blank string, so an unset or blank value leaves verification on with nothing to check against and every login refused — which used to happen with no explanation anywhere. `local.inc.php` then writes one line to the webmail container's error log (`docker logs vexlyx-roundcube`) naming both `ROUNDCUBE_MAIL_TLS_PEER_NAME` and `VEXLYX_MAIL_HOSTNAME`, because the installer renders the latter (`system/scripts/install/config.sh:43`, default `mail.$VEXLYX_DOMAIN`) and a stack started without that env file is where the blank arrives. It stays a diagnostic: verification is not disabled, startup is not aborted, and the login page keeps serving, so the fail-secure behaviour above is unchanged. The config is loaded per request, so a misconfigured webmail that is actually being used logs the line once per request.
- **Prod overlay is explicit.** `docker-compose.prod.yml` sets `ROUNDCUBE_MAIL_TLS_VERIFY: "true"` itself instead of relying on the default, so it can never inherit the dev value from the base file.

**Operational note:** if a production install is still running the installer's self-signed fallback certificate (`07-render-config.sh`, used until the trusted cert is synced — see the warning in `14-services-up.sh`), webmail login will now fail until the trusted certificate for `VEXLYX_MAIL_HOSTNAME` has been synced (`bash system/scripts/install/sync-mail-tls.sh`). That is the intended behaviour: the previous setup would have accepted the untrusted certificate silently.

**How to verify**

1. Render both configs: `docker compose -f docker-compose.yml config` shows `ROUNDCUBE_MAIL_TLS_VERIFY: "false"`; `docker compose -f docker-compose.yml -f docker-compose.prod.yml config` shows `"true"` plus the peer name.
2. Dev: webmail login still works against the self-signed cert.
3. Production-like: with a trusted cert for the mail hostname, webmail login works. To prove an untrusted certificate is rejected, replace **both** `docker/mail-data/certs/cert.pem` and `key.pem` with a freshly generated, matching self-signed pair (for example `openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj "/CN=$VEXLYX_MAIL_HOSTNAME" -keyout key.pem -out cert.pem`) and restart Dovecot. Replacing only the certificate would leave Dovecot with a mismatched pair it cannot load, and login would then fail for the wrong reason (no TLS service at all) instead of demonstrating that Roundcube rejects an untrusted certificate. Check that Dovecot started and listens on 143 before concluding anything, then restore the original pair.
4. PHP-level matrix (what was run for #42): a local `openssl s_server` with a cert for `mail.example.com` — strict + correct `peer_name` + trusted CA connects; no `peer_name`, untrusted CA, wrong `peer_name`, and `FALSE`/`0`/empty values are all rejected; `false` connects.

## 6. Routing Note — Why a File-Provider Route Instead of Just Docker Labels

Docker-label-based routing (what `adminer`'s `db.vexlyx.localhost` route relies on) turned out to be broken in this dev environment: Traefik 3.4.5's Docker provider fails to query the Docker socket at all, with an opaque `Error response from daemon: ` (empty). This reproduces with a bare vanilla `traefik:v3.4` container with no Vexlyx config involved — it's an upstream Traefik/Docker-Engine-29.x incompatibility, not something this feature (or Vexlyx) caused, and it identically breaks `adminer` today.

Rather than ship a webmail tab that 404s in this environment, `docker/traefik/dynamic/webmail.yml` routes `webmail.vexlyx.localhost` through Traefik's **file provider** instead — the same mechanism already relied on for per-domain SSL routing (F3.3/F3.4), which talks to Traefik's own config-reload API, not the Docker socket. The Docker labels stay on the `roundcube` compose service too, for portability to environments where the Docker provider isn't broken.

**Gotcha:** on this Windows Docker Desktop bind mount, the file provider's `watch: true` inotify reload did not pick up the new `webmail.yml` file on its own — a `docker restart vexlyx-traefik` was needed. If you add further static file-provider routes, restart Traefik afterward rather than assuming the live watch caught it.

The direct host port (`http://localhost:8089`, configurable via `WEBMAIL_PORT`) always works regardless of any of the above.

## Regression test: strict TLS between Roundcube and the mail servers

`tests/test_roundcube_tls.py` loads the real `docker/roundcube/config/local.inc.php` into the pinned Roundcube image (`roundcube/roundcubemail:1.6.18-apache`) and drives Roundcube's own IMAP and SMTP client classes against throwaway mail peers presenting different certificates. Only a certificate that chains to the trusted CA **and** matches `ROUNDCUBE_MAIL_TLS_PEER_NAME` may succeed; a wrong host name, an expired certificate, an untrusted CA and a self-signed certificate must be rejected **without the client ever sending credentials**. It also checks that a plaintext peer never receives credentials, that the development relaxation (`ROUNDCUBE_MAIL_TLS_VERIFY=false`) still works, that only the exact value `false` relaxes verification (a typo such as `FALSE` keeps it on), and that the production compose overlay overrides the development setting. The test needs Docker and runs in CI (`mail-credential-security` job):

```bash
python -m unittest tests.test_roundcube_tls -v
```

The certificate-matrix design is from PR #103 by @umair-sajjad, adapted to the settings this repository actually uses.

## 7. How to Extend

- **F4.5 (SPF/DKIM/DMARC)** — no changes needed here; Roundcube doesn't touch DNS/DKIM.
- **SSO/autologin** — would need a way to hand Roundcube a usable plaintext password (e.g. via its `autologin` plugin) at the moment a user clicks into Webmail from the dashboard. Today mailbox passwords are one-way Argon2id hashes shown only once at creation/reset, so this needs a deliberate credential-handling design, not just a UI change.
- **Per-domain webmail** (`webmail.<customer-domain>`) — reuse `DomainService.syncTraefikRouter()` / `SslService.provisionAutoSsl()` (F3.3/F3.4) instead of the static Docker-label route, if a per-tenant vanity URL is ever required.
