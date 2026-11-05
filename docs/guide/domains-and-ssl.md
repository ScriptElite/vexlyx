# Domains, subdomains and SSL

Every project gets a free `<name>.<your-domain>` subdomain with HTTPS the moment it deploys (see
[Getting started](/guide/getting-started)) — that wildcard comes from the `*.<base-domain>` A
record the installer told you to create. This guide covers attaching your **own** domain instead,
and how SSL certificates work once you do.

## Two ways to connect a domain

Vexlyx supports two independent modes, and it's worth knowing which one you actually need before
you start:

| | **Connect (self-serve)** — default | **Host DNS on Vexlyx** — optional |
|---|---|---|
| What it does | You add one A record and one TXT record at your *existing* registrar/DNS provider. | You delegate the domain's **entire** DNS zone — every record, not just this project's — to Vexlyx's own nameservers. |
| Where | `/domains` → **Verify** | `/domains/[id]/dns` |
| Required? | Yes — this is how any domain routes to a project. | No. Most users never touch this. |
| Risk | Low — one extra record at your registrar. | Higher — it moves *all* your DNS, including any existing email (MX) records, if you don't recreate them first. |

Unless you specifically want Vexlyx to manage a domain's full DNS zone (e.g. you're not using
another DNS provider at all), stick with **Connect**.

## Connect your own domain

1. Go to **Domains** → **Add Domain**, enter the hostname (`app.example.com`), and optionally
   assign it to a project right away.
2. Vexlyx shows you two records to create at your registrar:
   - A **TXT** record at `_vexlyx-challenge.<hostname>` proving you own the domain.
   - An **A** record at `<hostname>` pointing at the server's public IP (shown in the same
     dialog, and also on `/settings` if you're an admin).
3. Add both records at your registrar/DNS provider, then click **Verify** back in Vexlyx.

Verification queries public resolvers (Cloudflare, Google, Quad9) directly rather than the
server's own DNS cache, so it reflects real-world propagation. If you click Verify before the
record has propagated everywhere, just wait a few minutes and try again — DNS changes can take
anywhere from a couple of minutes to a few hours depending on your provider's TTL.

Once verified, traffic routing turns on immediately (no container restart), and Vexlyx requests a
Let's Encrypt certificate for that hostname in the same step — you do not have to do anything else
to get HTTPS. The certificate itself takes a moment to issue; see
[Enable HTTPS](#enable-https) below.

### Subdomains and wildcards

Once an apex domain (`example.com`) is verified, any subdomain or wildcard you add under it
(`api.example.com`, `*.example.com`) is activated immediately — no separate DNS challenge needed,
since ownership of the apex already proves it. Add subdomains from the same **Domains** screen; a
specific subdomain always takes priority over a wildcard covering the same traffic.

Those auto-activated names are served over HTTP until they get their own certificate, and a
**wildcard** hostname (`*.example.com`) never gets one: certificates here are issued through the
HTTP-01 challenge, which cannot validate a `*.…` name. Use a specific subdomain for anything you
want HTTPS on.

## Enable HTTPS

Verifying a domain requests its certificate automatically, so this is normally a step you watch
rather than perform. What happens:

1. The moment verification succeeds, Vexlyx enables SSL on the domain and Traefik asks Let's
   Encrypt for the certificate. The **SSL** tab shows the request.
2. Issuing takes a few seconds to a couple of minutes, and the domain has to resolve to this
   server for the challenge to pass. Until it is issued, plain HTTP keeps working.
3. Vexlyx keeps the certificate current automatically (auto-renew is on by default) and warns you
   7 days before anything is due to expire, with a badge on `/domains` and an amber banner on the
   dashboard home page.
4. **Force HTTPS** is on by default once a certificate is issued, redirecting plain HTTP requests
   to HTTPS.

Open the domain's **SSL** tab to **Upload Custom Certificate** instead (your own PEM certificate and
key), or to click **Provision** yourself if the automatic request was skipped — a wildcard, or a
verification done before this existed.

If a certificate shows `EXPIRED` or `ERROR`, use **Renew** on the same SSL tab — this is also
useful if you rotate a custom certificate before it lapses.

## Hosting DNS on Vexlyx (optional, advanced)

If you'd rather manage a domain's entire DNS zone from inside Vexlyx — not just the one A/TXT
record — open the domain's **Host DNS on Vexlyx** option from `/domains`. This requires:

1. The domain already verified (`ACTIVE`) via the Connect flow above.
2. Changing the domain's nameservers at your registrar to Vexlyx's (`ns1.vexlyx.com` /
   `ns2.vexlyx.com`, or your own server's, if it's been set up to serve DNS publicly).

Switching this on seeds the zone with sensible defaults (apex A record, `www` CNAME, NS records)
and gives you a full record editor — A, AAAA, CNAME, MX, TXT, NS, SRV — with zone file
import/export and a live propagation checker per record.

**Before you switch a live domain's nameservers**, recreate every record it currently has
(especially `MX`/`TXT` records for email) in Vexlyx's zone editor first, and confirm the switch
succeeded with a DNS lookup tool before assuming it's done — moving nameservers moves everything,
not just the web traffic, and if you have mailboxes on this domain, Vexlyx blocks switching back
to Connect mode until they're removed. If in doubt, this is exactly the case where **Connect**
(the one-A-record approach) is the safer, sufficient choice.

## Troubleshooting

- **Verified but the site doesn't load over HTTPS** — the certificate is still being issued, or the
  A record does not point at this server yet, so the HTTP-01 challenge cannot complete. Check the
  domain's **SSL** tab, and confirm the A record points at the current server IP — it can change
  after a server migration.
- **Verify keeps failing after adding the TXT record** — give it more time; registrar propagation
  and TTLs vary. Double-check the record was added at the exact host shown
  (`_vexlyx-challenge.<hostname>`, not just `<hostname>`).
- **Confirming the server's own DNS setup** — as an admin, `/settings` shows the panel's required
  records (panel, API, webmail, wildcard) with a live **Verify DNS** check against public
  resolvers, useful right after install or after migrating servers.

## Next steps

- [Deploying a project](/guide/deploying) — connect code to a project before pointing a domain at
  it.
- [Email](/guide/email) — mailboxes for a domain need their own MX/SPF/DKIM setup, whether you're
  in Connect or Hosted DNS mode.
