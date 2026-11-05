"""Verify the shipped Roundcube clients against a disposable adversarial PKI.

Based on the TLS matrix from #103 by umair-sajjad, adapted to the settings used by
docker/roundcube/config/local.inc.php (ROUNDCUBE_MAIL_TLS_VERIFY / ROUNDCUBE_MAIL_TLS_PEER_NAME).
Requires Docker and the pinned Roundcube image. No production services/data are used.
"""

import json
import os
import socket
import ssl
import subprocess
import tempfile
import threading
import unittest
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IMAGE = "roundcube/roundcubemail:1.6.18-apache"
PEER = "mail.roundcube-test.example"


def docker(*args, input=None, check=True, env=None):
    result = subprocess.run(["docker", *args], input=input, capture_output=True,
                            text=True, encoding="utf-8", timeout=90, env=env)
    if check and result.returncode:
        raise AssertionError(f"Docker command failed: {result.stderr}")
    return result


class MailEndpoint:
    """A single-connection mail peer recording whether AUTH follows TLS checks."""

    def __init__(self, fixtures, certificate, protocol, plaintext=False):
        self.protocol = protocol
        self.plaintext = plaintext
        self.auth = []
        self.sni = []
        self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.context.load_cert_chain(fixtures / f"{certificate}.crt", fixtures / f"{certificate}.key")
        self.context.set_servername_callback(lambda connection, name, context: self.sni.append(name))
        self.socket = socket.socket()
        self.socket.bind(("0.0.0.0", 0))
        self.socket.listen(1)
        self.socket.settimeout(8)
        self.port = self.socket.getsockname()[1]
        self.thread = threading.Thread(target=self.serve, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.socket.close()
        self.thread.join(timeout=8)
        if self.thread.is_alive():
            raise AssertionError("Test mail endpoint did not terminate")

    def serve(self):
        connection = stream = None
        try:
            connection, _ = self.socket.accept()
            connection.settimeout(6)
            if self.plaintext:
                banner = (b"* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] plaintext peer\r\n"
                          if self.protocol == "imap" else b"220 plaintext ESMTP peer\r\n")
                connection.sendall(banner)
                data = connection.recv(4096)
                if b"fixture-password" in data or b"LOGIN " in data or b"AUTH " in data:
                    self.auth.append(False)
                return
            connection = self.context.wrap_socket(connection, server_side=True)
            if self.protocol == "imap":
                stream = connection.makefile("rwb", buffering=0)
                stream.write(b"* OK [CAPABILITY IMAP4rev1 AUTH=PLAIN] TLS test peer\r\n")
                while line := stream.readline():
                    tag, command, *_ = line.decode().strip().split(" ")
                    if command.upper() in ("LOGIN", "AUTHENTICATE"):
                        self.auth.append(True)
                        stream.write(f"{tag} OK logged in\r\n".encode())
                    elif command.upper() == "CAPABILITY":
                        stream.write(f"* CAPABILITY IMAP4rev1 AUTH=PLAIN\r\n{tag} OK capability\r\n".encode())
                    elif command.upper() == "LOGOUT":
                        stream.write(f"* BYE closing\r\n{tag} OK logout\r\n".encode())
                        break
                    else:
                        stream.write(f"{tag} OK\r\n".encode())
            else:
                stream = connection.makefile("rwb", buffering=0)
                stream.write(b"220 mail.roundcube-test.example ESMTP\r\n")
                while line := stream.readline():
                    command = line.split(b" ", 1)[0].strip().upper()
                    if command in (b"EHLO", b"HELO"):
                        stream.write(b"250-test peer\r\n")
                        stream.write(b"250 AUTH PLAIN LOGIN\r\n")
                    elif command == b"AUTH":
                        if len(line.strip().split()) < 3:
                            stream.write(b"334 continue\r\n")
                            stream.readline()
                        self.auth.append(True)
                        stream.write(b"235 authenticated\r\n")
                    elif command == b"QUIT":
                        stream.write(b"221 goodbye\r\n")
                        break
                    else:
                        stream.write(b"502 unsupported\r\n")
        except (OSError, ValueError):
            # Rejected certificates cause expected TLS alerts/connection closure.
            pass
        finally:
            if stream:
                stream.close()
            if connection:
                connection.close()


class TestRoundcubeTls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name = "vexlyx-roundcube-tls-" + uuid.uuid4().hex[:10]
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.addClassCleanup(lambda: docker("rm", "-fv", cls.name, check=False))
        host = ["--add-host", "host.docker.internal:host-gateway"] if os.name != "nt" else []
        docker("run", "-d", "--name", cls.name, *host, "--entrypoint", "sh", IMAGE, "-c", "sleep 3600")
        docker("exec", cls.name, "mkdir", "-p", "/test")
        for source, target in (
            (ROOT / "docker/roundcube/config/local.inc.php", "/test/local.inc.php"),
            (ROOT / "tests/roundcube-tls/probe.php", "/test/probe.php"),
            (ROOT / "tests/roundcube-tls/certificates.sh", "/test/certificates.sh"),
        ):
            docker("cp", str(source), f"{cls.name}:{target}")
        docker("exec", cls.name, "sh", "-c", "sed -i 's/\r$//' /test/certificates.sh; sh /test/certificates.sh")
        docker("cp", f"{cls.name}:/fixtures/.", cls.temporary.name)
        cls.fixtures = Path(cls.temporary.name)

    def environment(self, values):
        return [argument for key, value in values.items() for argument in ("-e", f"{key}={value}")]

    def config(self, values, check=True):
        return docker("exec", *self.environment(values), self.name, "php", "-r",
                      "$config=[]; require '/test/local.inc.php'; echo json_encode($config);", check=check)

    def config_and_log(self, values):
        """The same config load, with whatever PHP writes to the error log captured."""
        result = docker("exec", *self.environment(values), self.name, "php",
                        "-d", "error_log=/dev/stderr", "-d", "log_errors=1", "-r",
                        "$config=[]; require '/test/local.inc.php'; echo json_encode($config);")
        return json.loads(result.stdout), result.stderr

    def probe(self, endpoint, development=False):
        values = {"ROUNDCUBE_MAIL_TLS_PEER_NAME": PEER}
        if development:
            values = {"ROUNDCUBE_MAIL_TLS_VERIFY": "false"}
        result = docker("exec", *self.environment(values), self.name, "php", "-d",
                        "openssl.cafile=/fixtures/ca.crt", "/test/probe.php",
                        endpoint.protocol, "host.docker.internal", str(endpoint.port))
        return json.loads(result.stdout)

    def test_default_settings_verify_both_servers(self):
        config = json.loads(self.config({"ROUNDCUBE_MAIL_TLS_PEER_NAME": PEER}).stdout)
        for key in ("imap_conn_options", "smtp_conn_options"):
            self.assertEqual(config[key]["ssl"], {
                "verify_peer": True, "verify_peer_name": True, "allow_self_signed": False,
                "peer_name": PEER,
            })

    def test_verification_is_relaxed_only_by_the_exact_value_false(self):
        relaxed = json.loads(self.config({"ROUNDCUBE_MAIL_TLS_VERIFY": "false"}).stdout)
        self.assertFalse(relaxed["imap_conn_options"]["ssl"]["verify_peer"])
        self.assertTrue(relaxed["smtp_conn_options"]["ssl"]["allow_self_signed"])
        # A typo or unexpected value must keep verification on (fail closed).
        for value in ("FALSE", "False", "0", "no", "off", "", "true"):
            with self.subTest(value=value):
                config = json.loads(self.config({"ROUNDCUBE_MAIL_TLS_VERIFY": value}).stdout)
                self.assertTrue(config["imap_conn_options"]["ssl"]["verify_peer"])
                self.assertTrue(config["smtp_conn_options"]["ssl"]["verify_peer_name"])
                self.assertFalse(config["smtp_conn_options"]["ssl"]["allow_self_signed"])

    def test_nothing_set_means_verification_is_on(self):
        config = json.loads(self.config({}).stdout)
        self.assertTrue(config["imap_conn_options"]["ssl"]["verify_peer"])

    def test_blank_peer_name_stays_secure_and_explains_itself(self):
        # Absent, empty and whitespace-only all mean "no name to check against". That
        # keeps verification on, which is correct, and used to be the one misconfiguration
        # of this file that produced no message anywhere an operator would look.
        for values in ({}, {"ROUNDCUBE_MAIL_TLS_PEER_NAME": ""}, {"ROUNDCUBE_MAIL_TLS_PEER_NAME": "   "}):
            with self.subTest(values=values):
                config, log = self.config_and_log(values)
                for key in ("imap_conn_options", "smtp_conn_options"):
                    self.assertTrue(config[key]["ssl"]["verify_peer"])
                    self.assertTrue(config[key]["ssl"]["verify_peer_name"])
                    self.assertFalse(config[key]["ssl"]["allow_self_signed"])
                    self.assertNotIn("peer_name", config[key]["ssl"])
                self.assertIn("ROUNDCUBE_MAIL_TLS_PEER_NAME", log)
                self.assertIn("VEXLYX_MAIL_HOSTNAME", log)

        # A real peer name, and the development posture that has no name to check,
        # both stay quiet: the line is a diagnosis of a mismatch, not a banner.
        for values in ({"ROUNDCUBE_MAIL_TLS_PEER_NAME": PEER},
                       {"ROUNDCUBE_MAIL_TLS_VERIFY": "false"},
                       {"ROUNDCUBE_MAIL_TLS_VERIFY": "false", "ROUNDCUBE_MAIL_TLS_PEER_NAME": ""}):
            with self.subTest(quiet=values):
                _, log = self.config_and_log(values)
                self.assertNotIn("is empty", log)

    def test_whitespace_around_the_peer_name_is_not_part_of_the_name(self):
        config, log = self.config_and_log({"ROUNDCUBE_MAIL_TLS_PEER_NAME": f"  {PEER}  "})
        for key in ("imap_conn_options", "smtp_conn_options"):
            self.assertEqual(config[key]["ssl"]["peer_name"], PEER)
        self.assertNotIn("is empty", log)

    def test_imap_certificate_validation_and_credentials(self):
        self.assert_certificate_matrix("imap")

    def test_smtp_certificate_validation_and_credentials(self):
        self.assert_certificate_matrix("smtp")

    def assert_certificate_matrix(self, protocol):
        for certificate in ("trusted", "wrong-host", "expired", "untrusted", "self-signed"):
            with self.subTest(certificate=certificate), MailEndpoint(self.fixtures, certificate, protocol) as endpoint:
                result = self.probe(endpoint)
                self.assertEqual(result["ok"], certificate == "trusted", result)
                self.assertEqual(endpoint.auth, [True] if certificate == "trusted" else [])
                self.assertIn(PEER, endpoint.sni)

    def test_development_self_signed_connections_still_work(self):
        for protocol in ("imap", "smtp"):
            with self.subTest(protocol=protocol), MailEndpoint(self.fixtures, "self-signed", protocol) as endpoint:
                self.assertTrue(self.probe(endpoint, development=True)["ok"])
                self.assertEqual(endpoint.auth, [True])

    def test_plaintext_mail_peers_never_receive_credentials(self):
        for protocol in ("imap", "smtp"):
            with self.subTest(protocol=protocol), MailEndpoint(self.fixtures, "trusted", protocol, plaintext=True) as endpoint:
                self.assertFalse(self.probe(endpoint)["ok"])
                self.assertEqual(endpoint.auth, [])

    def test_production_compose_overrides_development_insecurity(self):
        environment = os.environ | {"VEXLYX_MAIL_HOSTNAME": PEER, "VEXLYX_DOMAIN": "panel.roundcube-test.example",
                                    "POSTGRES_PASSWORD": "test", "MYSQL_ROOT_PASSWORD": "test", "MYSQL_PASSWORD": "test",
                                    "REDIS_PASSWORD": "test",
                                    "SESSION_SECRET": "test", "ENCRYPTION_KEY": "test", "VEXLYX_MAIL_DOMAIN": "roundcube-test.example",
                                    "VEXLYX_BASE_DOMAIN": "roundcube-test.example"}
        development = json.loads(docker("compose", "-f", str(ROOT / "docker-compose.yml"),
                                        "config", "--format", "json", env=environment).stdout)["services"]["roundcube"]
        production = json.loads(docker("compose", "-f", str(ROOT / "docker-compose.yml"),
                                       "-f", str(ROOT / "docker-compose.prod.yml"),
                                       "config", "--format", "json", env=environment).stdout)["services"]["roundcube"]
        self.assertEqual(development["environment"]["ROUNDCUBE_MAIL_TLS_VERIFY"], "false")
        self.assertEqual(production["environment"]["ROUNDCUBE_MAIL_TLS_VERIFY"], "true")
        self.assertEqual(production["environment"]["ROUNDCUBE_MAIL_TLS_PEER_NAME"], PEER)

if __name__ == "__main__":
    unittest.main(verbosity=2)
