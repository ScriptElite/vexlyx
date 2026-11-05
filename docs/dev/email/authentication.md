# SPF, DKIM, DMARC Auto-Configuration (F4.5)

> **Feature:** F4.5 — SPF, DKIM, DMARC Auto-Configuration
> **Status:** 🟢 COMPLETED
> **Package:** `@vexlyx/api`, `@vexlyx/dashboard`, `@vexlyx/shared`
> **Prisma Models:** `Domain`, `DnsRecord`, `Mailbox`
> **Depends on:** F3.3 (DNS Record Management), F4.1 (Postfix + OpenDKIM), F4.3 (Mailbox Management)

---

## 1. Overview

F4.5 closes the gap between "a domain can send/receive mail" and "a domain's mail actually lands in inboxes." As soon as a domain gets its first mailbox, Vexlyx auto-generates:

- **SPF** — a TXT record at `@` authorizing this server to send as the domain.
- **DKIM** — reuses the existing F4.1 key generation (`MailService.getOrGenerateDkim`); this feature does not regenerate DKIM logic, only wires it into the same trigger as SPF/DMARC/MX.
- **DMARC** — a TXT record at `_dmarc` in monitor-only mode (`p=none`).
- **MX** — an MX record at `@` pointing at `mail.<hostname>`, if none already exists (never overwrites a pre-existing custom MX, e.g. Google Workspace).

The dashboard's "Domains & Email Auth" tab (formerly "Domains & DKIM") shows an **internal, 0–100 deliverability score** per domain — 25 points each for SPF/DKIM/DMARC/MX being present and syntactically valid. This score is computed entirely from Vexlyx's own `DnsRecord` table; it makes **no external API calls or live DNS lookups** (unlike mail-tester.com), so it reflects what Vexlyx has configured, not what has propagated to the public internet — use the existing DNS Propagation Checker (F3.3) to verify actual resolution once records go live.

---

## 2. Trigger & Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│  User creates a mailbox: POST /api/mailboxes                │
└──────────────────────────────┬──────────────────────────────┘
                                ▼
         MailboxService.create() — apps/api/src/modules/mailboxes/service.ts
         1. Counts existing mailboxes for the domain BEFORE creating.
         2. Creates the Mailbox row.
         3. Syncs Postfix/Dovecot (existing F4.1/F4.2 behavior, unchanged).
         4. If this was the domain's FIRST mailbox:
                await mailService.ensureEmailAuthRecords(userId, domainId)
            wrapped in try/catch — a DNS/filesystem failure never blocks
            mailbox creation.
                                ▼
         MailService.ensureEmailAuthRecords() — apps/api/src/modules/mail/service.ts
         1. dnsService.initializeEmailAuthRecords()  → SPF + DMARC + MX
         2. this.getOrGenerateDkim(..., autoAddToDns: true)  → DKIM (F4.1, reused)
         3. Returns getMailAuthStatus() — the fresh scorecard.
                                ▼
         DnsService.initializeEmailAuthRecords() — apps/api/src/modules/domains/dns-service.ts
         Same "check findFirst, create if missing" loop as the existing
         initializeDefaultRecords() (F3.3), then one syncZoneFile() call so
         CoreDNS picks up the new records.
```

A manual **"Regenerate All"** button (per domain, in the expanded accordion row) calls the same `ensureEmailAuthRecords` via `POST /api/mail/auth/:domainId/regenerate` — safe to click repeatedly, since every record is check-then-create and never destructive.

---

## 3. Generated Record Templates

| Record | Name | Value | TTL |
|---|---|---|---|
| SPF | `@` (TXT) | `v=spf1 mx a ip4:<SERVER_IP> ~all` | 3600 |
| DMARC | `_dmarc` (TXT) | `v=DMARC1; p=none; rua=mailto:postmaster@<hostname>; pct=100` | 3600 |
| MX | `@` (MX, priority 10) | `mail.<hostname>` | 3600 |
| DKIM | `default._domainkey` (TXT) | `v=DKIM1; k=rsa; p=<public-key>` (F4.1, unchanged) | 3600 |

`SERVER_IP` is read from `process.env.SERVER_IP` (falls back to `127.0.0.1` in dev), the same environment variable F3.3's `initializeDefaultRecords` already uses for the apex A record.

SPF uses the soft-fail qualifier (`~all`) rather than a hard fail (`-all`) as a safer default for a domain that hasn't yet proven its sending reputation. DMARC starts at `p=none` (report-only) rather than `quarantine`/`reject` for the same reason — both are one-line edits away via the standard DNS record editor (F3.3) if an operator wants to tighten policy later.

---

## 4. Deliverability Scoring

Computed by `MailService.computeAuthChecks()` (private helper), shared by both `listVirtualDomains()` (the list the dashboard renders) and `getMailAuthStatus()` (used by the regenerate endpoint). Pure function — no I/O, no network calls:

| Check | Pass condition | Points |
|---|---|---|
| SPF | A TXT record at `@` starting with `v=spf1` **and** matching `/^v=spf1(\s+\S+)*\s+[-~?]all$/` | 25 |
| DKIM | A TXT record named `default._domainkey` exists | 25 |
| DMARC | A TXT record at `_dmarc` starting with `v=DMARC1` **and** containing a valid `p=` tag | 25 |
| MX | An MX record exists at `@` | 25 |

`score` is the sum (0/25/50/75/100); `grade` is `Excellent` (100), `Good` (≥75), `Needs Improvement` (≥50), or `Poor` (<50).

---

## 5. API Reference

### 1. List Virtual Domains (extended for F4.5)
- **Endpoint:** `GET /api/mail/domains` (existing F4.1 endpoint)
- **Response:** each `VirtualDomain` now also carries `spfConfigured`, `dmarcConfigured`, `mxConfigured`, `deliverabilityScore`, `deliverabilityGrade`, and `authChecks` (per-check pass/fail + detail string), alongside the existing `dkimEnabled`/`dkimRecord`/`mailboxCount` fields.

### 2. Regenerate Email Auth Records
- **Endpoint:** `POST /api/mail/auth/:domainId/regenerate`
- **Action:** Idempotently (re-)provisions SPF, DKIM, DMARC, and MX for the domain.
- **Response:** `200 OK` — `MailAuthStatusResponse` (the fresh scorecard for that one domain).

---

## 6. How to Test

Run the automated test suite (live dev stack required for the end-to-end cases; the security test degrades gracefully otherwise):
```bash
python tests/test_mail_authentication.py
```

Verify TypeScript & linting:
```bash
pnpm typecheck
pnpm lint
```

Manual check:
1. Dashboard → Mail → "Domains & Email Auth" tab → create the first mailbox on a domain with none yet.
2. Confirm the score badge jumps to "Excellent (100/100)" and the SPF/DMARC/MX cards all show green.
3. Inspect `docker/coredns/zones/<hostname>.db` on disk and confirm the SPF/DMARC/MX lines are present.
4. Create a second mailbox on the same domain and confirm no duplicate DNS rows are created.
5. Delete the SPF record via the DNS tab (F3.3), refresh the Mail page, confirm the score drops to 75/100 with SPF flagged; click "Regenerate All" and confirm it returns to 100/100.

---

## 7. How to Extend

- **Hard-fail SPF / enforced DMARC**: expose a per-domain toggle that swaps `~all` → `-all` and `p=none` → `p=quarantine`/`p=reject` once a domain's sending reputation is established — the record templates are centralized in `DnsService.initializeEmailAuthRecords`, a single place to parameterize.
- **Live propagation-aware scoring**: the score is currently DB-only by design (no external calls). A "live" variant could reuse F3.3's `DnsService.checkPropagation()` resolver-query logic to additionally confirm the records have actually propagated to public DNS, surfaced as a separate "Propagation" badge rather than folded into this score.
- **BIMI / MTA-STS**: additional TXT/CNAME records for brand indicators or transport security policy would follow the exact same "define template + check-then-create + syncZoneFile" pattern already established here and in F3.3's `initializeDefaultRecords`.

## Connect-only domains (F5.26)

Records are only written to a zone when the domain's `dnsMode` is `MANAGED` (see `docs/dev/dns-management.md` §9). For a `CONNECTED` domain, DNS lives at the user's registrar, so:

- `DnsService.initializeEmailAuthRecords`, `getOrGenerateDkim` and `rotateDkim` write no `DnsRecord` rows and no zone file. The DKIM key pair is still generated (OpenDKIM signs with it).
- `buildRequiredMailRecords` (`apps/api/src/modules/mail/required-records.ts`) is the single source for the MX/SPF/DMARC/DKIM values. MANAGED seeds them into the zone; CONNECTED returns them as `requiredRecords` for the user to add at their registrar.
- The scorecard for a CONNECTED domain is computed from live public DNS (`lookupLiveMailRecords`: 1.1.1.1 / 8.8.8.8 / 9.9.9.9). Any valid SPF/DMARC/MX counts; DKIM must carry the same public key we generated. `computeAuthChecks` itself is unchanged and stays pure.
- `POST /api/mail/auth/:domainId/check` re-runs the check on demand (the dashboard's "Check records" button).
- **The first check creates the DKIM key (#159).** A CONNECTED domain has no zone for `initializeEmailAuthRecords` to seed, so before this change its first check listed MX, host, SPF and DMARC but no DKIM record until "regenerate" was clicked. `MailService.connectedDomainDkimValue` now reads the key (`get_dkim`) and, only when none exists and the active selector did not come from a rotation, creates it (`generate_dkim`). `generate_dkim` returns an existing key unchanged and never rotates it, so repeating the check, or "regenerate", always shows the same record. Later checks only read, so a polled check does not rewrite OpenDKIM's tables or signal it. Creation goes through the same code as before: the private key is written `0600`, and OpenDKIM is told to reload with `SIGUSR1` after the container fixes ownership (never `SIGHUP`, see #138 and #141). If the key cannot be created the check still answers without the DKIM row and logs a warning. `GET /api/mail/domains` stays read-only. MANAGED domains are unchanged: their records, DKIM included, are seeded by "regenerate".
- Rotating DKIM on a CONNECTED domain switches signing immediately, but the new record must be added at the registrar. The rotate dialog warns about this and `newKey.inDns` is `false`.
- With `NODE_ENV=test` or `VEXLYX_MOCK_DNS=true` the live lookup reports every required record as present.

## Exposed development DKIM keys

The `default` signing keys that were tracked for `api.wp-blogs.vexlyx.localhost`,
`wp-blogs.vexlyx.localhost`, `test-postfix-mailer.org` and `vexlyx-test.com` are
public and must not be used. They are out of the checkout now (#139): every file
under `docker/postfix/opendkim/keys/` is runtime state, and a tracked file there
both ships to each new install and is swept into a customer's mail state by the
legacy state migrator as though it were a real domain's key. Private keys are
runtime state, including keys for local development and tests; generate fresh keys
on each installation.

Removing the files from the checkout does not revoke copies in runtime state or
older Git history. If any deployment used one of these keys, rotate it through
the Mail domain's DKIM rotation flow, publish the new selector's TXT record at
the authoritative DNS provider, and retire the exposed selector's DNS record.
The legacy mail-state migrator preserves existing keys; migration is not key
rotation.

Run the tracking regression without mail services:

```bash
python -m unittest \
  tests.test_mail_credential_security.TestCredentialBuildContexts.test_dkim_private_keys_are_not_tracked \
  tests.test_mail_credential_security.TestCredentialBuildContexts.test_no_dkim_key_files_are_tracked_at_all
```

