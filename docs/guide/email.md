# Email

Vexlyx runs a full mail stack (Postfix + Dovecot + Roundcube) alongside the hosting panel, so you
can create real mailboxes on any domain you manage without a third-party mail provider.

## Before you start

The installer sets up the mail stack itself, but the operator must publish the inbound routing
records shown at the end of installation and in **Settings → DNS Records & Public IP**:

```text
A  <configured-mail-hostname>  → <server-public-ip>
MX <configured-mail-domain>    → <configured-mail-hostname>  (priority 10)
```

The defaults are `mail.<panel-domain>` and `<panel-domain>`, but unattended installations may set
different `VEXLYX_MAIL_HOSTNAME` and `VEXLYX_MAIL_DOMAIN` values. Do not replace configured values
with assumptions based on the panel hostname.

The hosting provider must also set PTR/reverse DNS for the server IP to the mail hostname and
allow inbound TCP ports 25, 587, and 993. Many providers block outbound TCP/25; that affects
server-to-server sending and may require the provider to remove the restriction. Panel
transactional email can instead use the authenticated SMTP relay configured in **Settings →
System Email**.

For **other** domains you want to send or receive mail on:

1. [Connect and verify the domain](/guide/domains-and-ssl) first — mail auth records are attached
   to the domain, so it needs to exist in Vexlyx before you create mailboxes on it.
2. Know which [DNS mode](/guide/domains-and-ssl#two-ways-to-connect-a-domain) the domain is in —
   it changes one important thing below (deliverability records).

## Create a mailbox

Go to **Mail** → **Mailboxes** → **New Mailbox**, pick the domain, a local part (`jane` for
`jane@example.com`), and a quota (256MB up to 10GB, or unlimited). The password is generated for
you and shown **exactly once** in a copy-to-clipboard dialog — Vexlyx never stores it in
reversible form, so if you lose it, use **Reset Password** to generate a new one (this invalidates
the old one immediately).

The mailbox is usable right away — no separate "sync" step.

## Deliverability: SPF, DKIM, DMARC, MX

The moment a domain gets its **first** mailbox, Vexlyx generates the four records mail providers
check before trusting your mail: SPF, DKIM, DMARC, and (if none exists yet) MX. What happens next
depends on the domain's DNS mode:

- **Hosted DNS domains** — the records are written straight into the zone Vexlyx serves. Nothing
  more to do.
- **Connected domains (the default)** — Vexlyx can't write to your registrar's DNS, so instead it
  shows you the exact records to add yourself, on the **Domains & Email Auth** tab. Add them at
  your registrar the same way you added the domain's A/TXT records, then click **Check records**
  to confirm they've propagated.

Either way, the same tab shows a 0–100 deliverability score (25 points each for SPF/DKIM/DMARC/MX
being present and valid) with a **Regenerate All** / **Check records** button — safe to click
repeatedly, since it only creates what's missing.

SPF starts as a soft-fail (`~all`) and DMARC starts in report-only mode (`p=none`) — safe
defaults for a domain that hasn't built sending reputation yet. Both can be tightened later
through the domain's [DNS record editor](/guide/domains-and-ssl#hosting-dns-on-vexlyx-optional-advanced)
once you're confident mail is landing correctly.

## Forwarding and catch-all addresses

**Mail → Aliases** lets you forward an address to one or more real mailboxes without creating a
login for it — `sales@example.com` → `you@example.com`, for instance. A single **catch-all**
address per domain (anything sent to `@example.com` that doesn't match a mailbox or alias) is also
supported; only one is allowed per domain, so creating a second is rejected rather than silently
replacing the first.

## Vacation auto-responder

Each mailbox in the **Mailboxes** table has a palm-tree icon that opens its auto-reply settings:
subject, message, an optional date range, and a repeat interval (1–30 days) that stops the same
sender from getting the reply more than once in that window. Auto-replies are sent from the
mailbox itself and DKIM-signed like any other outgoing mail, and normal inbox delivery keeps
working exactly as before.

## Webmail

Every mailbox can be read and sent from a browser at `https://webmail.<your-panel-domain>` — one
shared Roundcube instance for every domain and mailbox on the server, reachable from **Mail →
Webmail** in the dashboard too. Log in with the mailbox's own address and password (the one shown
at creation, or the latest from **Reset Password**) — there's no single sign-on from the panel,
since Vexlyx doesn't retain plaintext passwords to hand over automatically.

## Using a desktop or mobile mail client

Any IMAP/SMTP client (Apple Mail, Outlook, Thunderbird, the stock mail app on your phone) works
with these settings:

|                    | Host                          | Port  | Security | Authentication  |
| ------------------ | ----------------------------- | ----- | -------- | --------------- |
| Incoming (IMAP)    | Your configured mail hostname | `993` | SSL/TLS  | Normal password |
| Incoming (IMAP)    | Your configured mail hostname | `143` | STARTTLS | Normal password |
| Outgoing (SMTP)    | Your configured mail hostname | `587` | STARTTLS | Normal password |

Username is the full mailbox address (`jane@example.com`); password is the one shown at creation
or reset. There's no POP3 — only IMAP.

`587` is the only submission port: Vexlyx does not listen on `465` (implicit TLS SMTP), and port
`25` is for server-to-server delivery rather than mail clients. Both the `143` and `587` listeners
refuse a password until the connection is encrypted, so a client left with its security set to
*None* fails at the password step with `Must issue a STARTTLS command first` — that is the server
requiring TLS, not a wrong password.

## Troubleshooting delivery

If mail isn't arriving, admins can check **Mail → Queue** for stuck/deferred messages (hold,
release, or force-flush them) and **Mail → Delivery Log** for per-message bounce reasons — see the
[mail operations reference](/reference/email/mail-operations) for the full toolset, including
rotating a domain's DKIM key without breaking in-flight mail.

## Next steps

- [Domains, subdomains and SSL](/guide/domains-and-ssl) — connect the domain you want to send
  mail from, if you haven't already.
