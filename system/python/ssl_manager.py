#!/usr/bin/env python3
"""
ssl_manager.py -- System-layer script for Vexlyx SSL/TLS Certificate Management (F3.4).

Manages SSL certificates for Traefik v3:
- Generates self-signed development/test certificates with SANs.
- Validates PEM certificate and private key pairing.
- Reads and parses Traefik acme.json Let's Encrypt certificate storage.
- Parses X.509 certificate metadata (expiration, issuer, SANs, serial).
- Stores and deletes custom TLS certificate files.

Called by Fastify API or CLI via stdin JSON or command-line arguments.
Outputs structured JSON responses on stdout.
"""

import base64
import datetime
import json
import os
import sys
import tempfile
from pathlib import Path

# Ensure site-packages from all known local and system Python environments are in sys.path
if sys.platform == "win32":
    known_site_packages = [
        Path.cwd() / "apps" / "api" / "Python" / "pythoncore-3.14-64" / "Lib" / "site-packages",
        Path.cwd() / "Python" / "pythoncore-3.14-64" / "Lib" / "site-packages",
        Path.cwd().parent / "apps" / "api" / "Python" / "pythoncore-3.14-64" / "Lib" / "site-packages",
        Path.cwd().parent.parent / "apps" / "api" / "Python" / "pythoncore-3.14-64" / "Lib" / "site-packages",
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Python\pythoncore-3.14-64\Lib\site-packages")),
        Path(os.path.expandvars(r"%USERPROFILE%\AppData\Local\Python\pythoncore-3.14-64\Lib\site-packages")),
        Path(os.path.expandvars(r"%APPDATA%\Python\Python314\site-packages")),
    ]
    for sp in known_site_packages:
        if sp.exists() and str(sp) not in sys.path:
            sys.path.insert(0, str(sp))

# Optional cryptography import with graceful fallback
try:
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtensionOID, NameOID
    HAVE_CRYPTO = True
except Exception as e:
    HAVE_CRYPTO = False


# ---------------------------------------------------------------------------
# Stream Encoding Configuration
# ---------------------------------------------------------------------------

if hasattr(sys.stdin, "reconfigure"):
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def respond(data: dict) -> None:
    print(json.dumps(data), flush=True)


# ---------------------------------------------------------------------------
# File Writing
# ---------------------------------------------------------------------------

# In the shipped stack the only thing that reads a key here is Traefik, and both
# its container and the API that spawns this helper run as root, so 0600 costs
# nothing (#195). A certificate is public, so it keeps 0644 and any other tooling
# can still read it.
PRIVATE_KEY_MODE = 0o600
CERTIFICATE_MODE = 0o644
# The directory is created with no group or other bits. It is not chmod'd later:
# an existing install's directory only ever leaks file *names*, and tightening a
# directory other tooling may already traverse is a wider decision than this fix.
CERTS_DIR_MODE = 0o700


def atomic_write(path: Path, content: bytes, mode: int) -> None:
    """Write through a temporary file in the same directory, set the mode on it,
    then move it into place.

    The mode is applied before the content is reachable under its real name, so
    a private key is never briefly world-readable on its way to 0600 — which a
    `write_text()` followed by `chmod()` would have been. Same shape as
    `mail_tls_manager.py:32`, which has written its keys this way all along.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def get_certs_dir() -> Path:
    candidates = [
        Path.cwd() / "docker" / "traefik" / "certs",
        Path.cwd().parent / "docker" / "traefik" / "certs",
        Path.cwd().parent.parent / "docker" / "traefik" / "certs",
    ]
    for c in candidates:
        if c.exists():
            return c
    target = Path.cwd() / "docker" / "traefik" / "certs"
    target.mkdir(parents=True, exist_ok=True, mode=CERTS_DIR_MODE)
    return target


def convenience_copy_name(hostname: str) -> str:
    """The stem `generate_self_signed()` uses for the <host>.crt/.key pair it
    writes next to a domain's own pair, and the stem a deletion has to look for.
    One rule for both, because a drift between them would leave a private key
    behind on the host after its certificate was deleted (#195)."""
    return hostname.replace("*.", "wildcard.").replace(":", "_").replace("/", "_")


def get_acme_file() -> Path:
    candidates = [
        Path.cwd() / "docker" / "traefik" / "acme.json",
        Path.cwd().parent / "docker" / "traefik" / "acme.json",
        Path.cwd().parent.parent / "docker" / "traefik" / "acme.json",
    ]
    for c in candidates:
        if c.exists():
            return c
    return Path.cwd() / "docker" / "traefik" / "acme.json"


# ---------------------------------------------------------------------------
# Certificate Generation (Self-Signed / Dev)
# ---------------------------------------------------------------------------

def generate_self_signed(hostname: str, sans: list = None, days_valid: int = 90, domain_id: str = None) -> dict:
    if not HAVE_CRYPTO:
        return {"success": False, "error": "cryptography package is required"}

    sans = sans or []
    certs_dir = get_certs_dir()
    clean_host = convenience_copy_name(hostname)

    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Vexlyx Self-Signed Authority"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Security"),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    expiry = now + datetime.timedelta(days=days_valid)

    # Build SANs list
    san_entries = [x509.DNSName(hostname)]
    for s in sans:
        if s and s != hostname:
            san_entries.append(x509.DNSName(s))

    cert_builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(expiry)
        .add_extension(
            x509.SubjectAlternativeName(san_entries),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
    )

    certificate = cert_builder.sign(key, hashes.SHA256(), default_backend())

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    if domain_id:
        cert_file = certs_dir / f"domain-{domain_id}.crt"
        key_file = certs_dir / f"domain-{domain_id}.key"
    else:
        cert_file = certs_dir / f"{clean_host}.crt"
        key_file = certs_dir / f"{clean_host}.key"

    atomic_write(cert_file, cert_pem.encode("utf-8"), CERTIFICATE_MODE)
    atomic_write(key_file, key_pem.encode("utf-8"), PRIVATE_KEY_MODE)

    # If domain_id was given, also write clean_host file as convenience
    if domain_id:
        try:
            atomic_write(certs_dir / f"{clean_host}.crt", cert_pem.encode("utf-8"), CERTIFICATE_MODE)
            atomic_write(certs_dir / f"{clean_host}.key", key_pem.encode("utf-8"), PRIVATE_KEY_MODE)
        except Exception:
            pass

    serial_hex = f"{certificate.serial_number:X}"

    return {
        "success": True,
        "certPath": str(cert_file),
        "keyPath": str(key_file),
        "certPem": cert_pem,
        "keyPem": key_pem,
        "commonName": hostname,
        "issuer": "Vexlyx Self-Signed Authority",
        "sans": [s for s in [hostname] + sans if s],
        "validFrom": now.isoformat(),
        "validTo": expiry.isoformat(),
        "daysRemaining": days_valid,
        "serialNumber": serial_hex,
    }


# ---------------------------------------------------------------------------
# Certificate Parsing & Validation
# ---------------------------------------------------------------------------

def parse_cert_pem(cert_pem_content: str) -> dict:
    if not HAVE_CRYPTO:
        return {"success": False, "error": "cryptography package is required"}

    try:
        cert_bytes = cert_pem_content.strip().encode("utf-8")
        cert = x509.load_pem_x509_certificate(cert_bytes, default_backend())

        common_name = ""
        for attr in cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME):
            common_name = attr.value

        issuer_str = ""
        for attr in cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME):
            issuer_str = attr.value
        if not issuer_str:
            for attr in cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME):
                issuer_str = attr.value
        if not issuer_str:
            issuer_str = "Unknown Issuer"

        sans = []
        try:
            ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
            sans = ext.value.get_values_for_type(x509.DNSName)
        except Exception:
            pass

        now = datetime.datetime.now(datetime.timezone.utc)
        # Handle naive vs aware datetimes
        valid_from = cert.not_valid_before_utc if hasattr(cert, "not_valid_before_utc") else cert.not_valid_before.replace(tzinfo=datetime.timezone.utc)
        valid_to = cert.not_valid_after_utc if hasattr(cert, "not_valid_after_utc") else cert.not_valid_after.replace(tzinfo=datetime.timezone.utc)

        delta = valid_to - now
        days_remaining = int(delta.total_seconds() / 86400)
        is_expired = delta.total_seconds() <= 0
        is_expiring_soon = 0 < days_remaining <= 7

        serial_hex = f"{cert.serial_number:X}"

        return {
            "success": True,
            "commonName": common_name,
            "issuer": issuer_str,
            "sans": sans,
            "validFrom": valid_from.isoformat(),
            "validTo": valid_to.isoformat(),
            "daysRemaining": days_remaining,
            "isExpired": is_expired,
            "isExpiringSoon": is_expiring_soon,
            "serialNumber": serial_hex,
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to parse certificate: {str(e)}"}


def validate_key_pair(cert_pem_content: str, key_pem_content: str) -> dict:
    if not HAVE_CRYPTO:
        return {"success": False, "error": "cryptography package is required"}

    try:
        cert = x509.load_pem_x509_certificate(cert_pem_content.strip().encode("utf-8"), default_backend())
        key = serialization.load_pem_private_key(key_pem_content.strip().encode("utf-8"), password=None, backend=default_backend())

        cert_pub_numbers = cert.public_key().public_numbers()
        key_pub_numbers = key.public_key().public_numbers()

        if cert_pub_numbers != key_pub_numbers:
            return {"success": False, "error": "Private key does not match the certificate's public key."}

        meta = parse_cert_pem(cert_pem_content)
        return {
            "success": True,
            "valid": True,
            "certificate": meta,
        }
    except Exception as e:
        return {"success": False, "error": f"Validation failed: {str(e)}"}


# ---------------------------------------------------------------------------
# Read Traefik ACME storage (acme.json)
# ---------------------------------------------------------------------------

def read_acme_storage() -> dict:
    acme_path = get_acme_file()
    if not acme_path.exists():
        return {"success": True, "certificates": []}

    try:
        content = acme_path.read_text(encoding="utf-8").strip()
        if not content or content == "{}":
            return {"success": True, "certificates": []}

        data = json.loads(content)
        parsed_certs = []

        for resolver_name, resolver_data in data.items():
            if not isinstance(resolver_data, dict):
                continue
            certs = resolver_data.get("Certificates", [])
            for c in certs:
                domain_info = c.get("domain", {})
                main_domain = domain_info.get("main", "")
                san_domains = domain_info.get("sans", [])
                cert_b64 = c.get("certificate", "")

                if not cert_b64:
                    continue

                try:
                    cert_pem = base64.b64decode(cert_b64).decode("utf-8")
                    meta = parse_cert_pem(cert_pem) if HAVE_CRYPTO else {}
                    meta["mainDomain"] = main_domain
                    meta["sans"] = san_domains or meta.get("sans", [])
                    meta["resolver"] = resolver_name
                    parsed_certs.append(meta)
                except Exception as ex:
                    parsed_certs.append({
                        "mainDomain": main_domain,
                        "sans": san_domains,
                        "error": str(ex),
                    })

        return {"success": True, "certificates": parsed_certs}
    except Exception as e:
        return {"success": False, "error": f"Failed reading acme.json: {str(e)}"}


# ---------------------------------------------------------------------------
# Save & Delete Custom Certificates
# ---------------------------------------------------------------------------

def save_custom_certificate(domain_id: str, cert_pem: str, key_pem: str) -> dict:
    check = validate_key_pair(cert_pem, key_pem)
    if not check.get("success"):
        return check

    certs_dir = get_certs_dir()
    cert_file = certs_dir / f"domain-{domain_id}.crt"
    key_file = certs_dir / f"domain-{domain_id}.key"

    try:
        atomic_write(cert_file, cert_pem.strip().encode("utf-8"), CERTIFICATE_MODE)
        atomic_write(key_file, key_pem.strip().encode("utf-8"), PRIVATE_KEY_MODE)

        parsed = parse_cert_pem(cert_pem)
        return {
            "success": True,
            "certPath": str(cert_file),
            "keyPath": str(key_file),
            "certificate": parsed,
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to save certificate files: {str(e)}"}


def delete_custom_certificate(domain_id: str, hostname: str = None) -> dict:
    certs_dir = get_certs_dir()
    cert_file = certs_dir / f"domain-{domain_id}.crt"
    key_file = certs_dir / f"domain-{domain_id}.key"

    # Read the pair before unlinking it: the convenience copies are matched
    # against this content, so a <host>.crt/.key that is not a copy of *this*
    # certificate is left alone.
    content = {}
    for f in (cert_file, key_file):
        try:
            content[f] = f.read_bytes()
        except OSError:
            content[f] = None

    deleted = False
    for f in [cert_file, key_file]:
        if f.exists():
            try:
                f.unlink()
                deleted = True
            except Exception:
                pass

    # `generate_self_signed()` also writes <clean_host>.crt/.key as a convenience
    # copy, and until now nothing ever removed them (#195). Two guards: the
    # caller has to say which hostname it is deleting, because those names come
    # from the hostname and a caller that predates this change sends none; and
    # the copy has to match the file being deleted, because without a domain id
    # `generate_self_signed()` writes those very names as its primary output and
    # something else may own what is here.
    copies_removed = []
    if hostname:
        clean_host = convenience_copy_name(hostname)
        for source, copy in (
            (cert_file, certs_dir / f"{clean_host}.crt"),
            (key_file, certs_dir / f"{clean_host}.key"),
        ):
            if content[source] is None or not copy.exists():
                continue
            try:
                if copy.read_bytes() != content[source]:
                    continue
                copy.unlink()
                copies_removed.append(str(copy))
            except Exception:
                pass

    return {"success": True, "deleted": deleted, "copiesRemoved": copies_removed}


# ---------------------------------------------------------------------------
# Main CLI Dispatcher
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        try:
            data = json.load(sys.stdin)
            cmd = data.get("command")
            payload = data.get("payload", {})
        except Exception as e:
            respond({"success": False, "error": f"Invalid JSON stdin: {e}"})
            sys.exit(1)
    else:
        cmd = sys.argv[1]
        try:
            payload = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        except Exception:
            payload = {}

    if cmd == "generate_self_signed":
        res = generate_self_signed(
            hostname=payload.get("hostname", "localhost"),
            sans=payload.get("sans", []),
            days_valid=payload.get("days", 90),
            domain_id=payload.get("domainId"),
        )
        respond(res)
    elif cmd == "parse_cert":
        res = parse_cert_pem(payload.get("certificate", ""))
        respond(res)
    elif cmd == "validate_pair":
        res = validate_key_pair(
            payload.get("certificate", ""),
            payload.get("privateKey", ""),
        )
        respond(res)
    elif cmd == "save_custom":
        res = save_custom_certificate(
            domain_id=payload.get("domainId", ""),
            cert_pem=payload.get("certificate", ""),
            key_pem=payload.get("privateKey", ""),
        )
        respond(res)
    elif cmd == "delete_cert":
        res = delete_custom_certificate(
            domain_id=payload.get("domainId", ""),
            hostname=payload.get("hostname"),
        )
        respond(res)
    elif cmd == "read_acme":
        res = read_acme_storage()
        respond(res)
    else:
        respond({"success": False, "error": f"Unknown command: {cmd}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
