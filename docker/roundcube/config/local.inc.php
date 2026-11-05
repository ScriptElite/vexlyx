<?php
// TLS between Roundcube and Dovecot/Postfix (F4.1/F4.2).
//
// Secure by default: the certificate chain AND name are verified. Verification
// is only relaxed when ROUNDCUBE_MAIL_TLS_VERIFY is exactly "false", which only
// docker-compose.yml (local development) sets, because the dev stack's
// Dovecot/Postfix present a container-generated self-signed certificate that
// PHP's IMAP/SMTP client cannot interactively trust. Any other value, or the
// variable being absent, keeps verification on, so a missing/typo'd setting
// can never silently disable it in production.
//
// Roundcube connects to the Docker service names (tls://dovecot, tls://postfix),
// but the production certificate is issued for the public mail hostname, not
// for those names. ROUNDCUBE_MAIL_TLS_PEER_NAME makes PHP validate the
// certificate against that hostname instead of the service name.
$verify_mail_tls = getenv('ROUNDCUBE_MAIL_TLS_VERIFY') !== 'false';
// Compose renders an unset variable as an empty string, so "absent" and "present
// but blank" arrive the same way; trim() also keeps a stray space out of the name
// that the certificate is later checked against.
$mail_tls_peer_name = trim((string) getenv('ROUNDCUBE_MAIL_TLS_PEER_NAME'));

$mail_tls_options = [
    'verify_peer' => $verify_mail_tls,
    'verify_peer_name' => $verify_mail_tls,
    'allow_self_signed' => !$verify_mail_tls,
];

if ($verify_mail_tls && $mail_tls_peer_name !== '') {
    $mail_tls_options['peer_name'] = $mail_tls_peer_name;
} elseif ($verify_mail_tls) {
    // With no peer name PHP checks the certificate against the service name it
    // connected to (dovecot / postfix), which no mail certificate is issued for,
    // so every login is refused and nothing on screen says why.
    error_log('vexlyx roundcube: ROUNDCUBE_MAIL_TLS_PEER_NAME is empty, so the mail certificate will be '
        . 'verified against the "dovecot"/"postfix" service names instead of the public mail hostname, and '
        . 'IMAP/SMTP connections will be rejected. Set VEXLYX_MAIL_HOSTNAME (the installer defaults it to '
        . 'mail.$VEXLYX_DOMAIN), or set ROUNDCUBE_MAIL_TLS_VERIFY=false for local development only.');
}

$config['imap_conn_options'] = ['ssl' => $mail_tls_options];
$config['smtp_conn_options'] = ['ssl' => $mail_tls_options];
