"""ssl_manager.py takes its request on stdin, so a private key need not be an
argument (#190).

`apps/api/src/modules/domains/ssl-service.ts` used to spawn the helper as
`[script, command, JSON.stringify(payload)]`, and for `save_custom` that
payload is the certificate and private key a user just uploaded, so the key sat
in the process command line - visible to `ps` and in `/proc/<pid>/cmdline` for
as long as the helper ran.

The helper has long accepted `{"command": ..., "payload": ...}` on stdin
whenever it is given no argument (`main()` at the bottom of
`system/python/ssl_manager.py`), which is what the API now uses. These tests
drive the real script both ways over a payload that contains a private key, so
the transport the API relies on is pinned rather than assumed, and the argv
form the CLI and `tests/test_ssl_management.py` still use keeps working.
"""

import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = ROOT_DIR / "system" / "python" / "ssl_manager.py"

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
except ImportError:  # the helper answers these commands only when it has it
    x509 = None


def make_pair():
    """A throwaway self-signed certificate and its key, in memory only."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "stdin-ssl.vexlyx.localhost")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    return cert_pem, key_pem


def one_document(stdout: str) -> dict:
    lines = [line for line in stdout.splitlines() if line.strip()]
    assert len(lines) == 1, f"expected exactly one JSON document, got: {stdout!r}"
    return json.loads(lines[0])


@unittest.skipIf(x509 is None, "cryptography is not installed")
class StdinTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cert_pem, cls.key_pem = make_pair()

    def stdin_command(self) -> list:
        """The invocation the API now makes: the script and nothing else."""
        return [sys.executable, str(SCRIPT)]

    def run_stdin(self, document: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            self.stdin_command(),
            input=document,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def run_argv(self, command: str, payload: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), command, json.dumps(payload)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    def test_validate_pair_over_stdin_answers_the_same_as_over_argv(self):
        payload = {"certificate": self.cert_pem, "privateKey": self.key_pem}
        stdin_proc = self.run_stdin(json.dumps({"command": "validate_pair", "payload": payload}))
        self.assertEqual(stdin_proc.returncode, 0, stdin_proc.stderr)
        argv_proc = self.run_argv("validate_pair", payload)
        self.assertEqual(argv_proc.returncode, 0, argv_proc.stderr)
        self.assertEqual(one_document(stdin_proc.stdout), one_document(argv_proc.stdout))
        self.assertTrue(one_document(stdin_proc.stdout).get("success"), one_document(stdin_proc.stdout))

    def test_a_key_reaches_the_helper_without_appearing_in_its_arguments(self):
        document = json.dumps({
            "command": "validate_pair",
            "payload": {"certificate": self.cert_pem, "privateKey": self.key_pem},
        })
        # The key is in the request...
        self.assertIn("PRIVATE KEY", document)
        # ...and the request is the only place it travels: the command line the
        # helper is started with carries the interpreter and the script alone,
        # which is what keeps it out of ps and /proc/<pid>/cmdline.
        command_line = " ".join(self.stdin_command())
        self.assertNotIn("PRIVATE KEY", command_line)
        self.assertNotIn(self.key_pem, command_line)
        # A vacuous pass is the failure mode here, so the helper has to have
        # actually read the key off stdin.
        proc = self.run_stdin(document)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(one_document(proc.stdout).get("success"), proc.stdout)

    def test_a_mismatched_pair_is_still_reported_over_stdin(self):
        other_cert, _ = make_pair()
        proc = self.run_stdin(json.dumps({
            "command": "validate_pair",
            "payload": {"certificate": other_cert, "privateKey": self.key_pem},
        }))
        result = one_document(proc.stdout)
        self.assertFalse(result.get("success"), result)

    def test_an_unknown_command_on_stdin_is_one_document_and_a_failure(self):
        proc = self.run_stdin(json.dumps({"command": "not_a_command", "payload": {}}))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertFalse(one_document(proc.stdout).get("success"))
        self.assertIn("not_a_command", one_document(proc.stdout).get("error", ""))

    def test_malformed_stdin_is_one_document_and_a_failure(self):
        proc = self.run_stdin("this is not json")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertFalse(one_document(proc.stdout).get("success"))

    def test_an_empty_stdin_document_does_not_try_to_read_the_command_line(self):
        proc = self.run_stdin(json.dumps({"payload": {"certificate": self.cert_pem}}))
        self.assertEqual(proc.returncode, 1, proc.stderr)
        result = one_document(proc.stdout)
        self.assertFalse(result.get("success"), result)
        self.assertIn("Unknown command", result.get("error", ""))


if __name__ == "__main__":
    unittest.main()
