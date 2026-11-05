"""Behavioral regressions against real Dovecot, including offline upgrades.

Build with: docker build -t vexlyx-dovecot:credentials-test docker/dovecot
Run with: python -m unittest tests.test_mail_credential_security -v
Uses isolated Docker volumes/containers; never writes deployment credentials.
"""

import imaplib
import json
import ssl
import subprocess
import tempfile
import time
import unittest
import uuid
from pathlib import Path


IMAGE = "vexlyx-dovecot:credentials-test"
STATE_ROOT = "/var/lib/vexlyx-mail/dovecot"
GENERATION = "a" * 32
USERS = f"{STATE_ROOT}/generations/{GENERATION}/users"
GUARD = "/usr/local/bin/users-security.sh"
PUBLISHED = (
    "{ARGON2ID}$argon2id$v=19$m=65536,t=3,p=1$U+cApES5CNwhZn7jxTvr0w$"
    "c/Fm2zGrJFBvSQ8IsnQk1oJmS+TsCZOGPOzXc0iIUoE"
)


def docker(*args, input=None, check=True, timeout=60):
    result = subprocess.run(
        ["docker", *args], input=input.encode("utf-8") if input is not None else None,
        capture_output=True, timeout=timeout,
    )
    # Keep fixture files byte-exact: Windows text pipes otherwise turn LF into CRLF.
    result.stdout = result.stdout.decode("utf-8")
    result.stderr = result.stderr.decode("utf-8")
    if check and result.returncode:
        # Do not put passwords/hashes from argv or stdin in failure messages.
        raise AssertionError(f"Docker command failed ({result.returncode}): {result.stderr}")
    return result


def initialize_state(container):
    from system.python.mail_state import activation
    docker("exec", container, "mkdir", "-p", f"{STATE_ROOT}/generations/{GENERATION}")
    docker("exec", "-i", container, "sh", "-c", f"cat > {STATE_ROOT}/active.conf",
           input=activation("dovecot", GENERATION))


def row(address, hash_value):
    return f"{address}:{hash_value}:5000:5000::::userdb_quota_rule=*:storage=1024M\n"


class TestCredentialBuildContexts(unittest.TestCase):
    def test_dkim_private_keys_are_not_tracked(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["git", "ls-files", "--cached", "-z", "--", "docker/postfix/opendkim/keys"],
            cwd=root, capture_output=True, check=True,
        )
        tracked_keys = [
            path.decode("utf-8") for path in result.stdout.split(b"\0")
            if path.endswith(b".private")
        ]
        self.assertEqual(tracked_keys, [], "DKIM private keys must remain untracked runtime state")

    def test_no_dkim_key_files_are_tracked_at_all(self):
        # Filtering on .private leaves the public half of a key pair through: a
        # tracked default.txt keeps shipping a developer's domain to every
        # install, .gitignore cannot hide it, and the legacy-state migrator
        # sweeps it into a customer's mail state as if it were real.
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run(
            ["git", "ls-files", "--cached", "-z", "--", "docker/postfix/opendkim/keys"],
            cwd=root, capture_output=True, check=True,
        )
        tracked = [path.decode("utf-8") for path in result.stdout.split(b"\0") if path]
        self.assertEqual(
            tracked, [],
            "docker/postfix/opendkim/keys is runtime state and must hold no tracked file",
        )

    def test_runtime_credentials_and_backups_are_excluded_from_build_contexts(self):
        root = Path(__file__).resolve().parent.parent
        for ignore_file, relative_config in (
            (root / ".dockerignore", "docker/dovecot/config"),
            (root / "docker/dovecot/.dockerignore", "config"),
        ):
            with self.subTest(context=str(ignore_file.parent)), tempfile.TemporaryDirectory() as temporary:
                context = Path(temporary)
                (context / ".dockerignore").write_bytes(ignore_file.read_bytes())
                config = context / relative_config
                config.mkdir(parents=True)
                (config / "users").write_text("runtime-test-data")
                (config / "users.before-remediation.test").write_text("backup-test-data")
                (context / "included.txt").write_text("build-context-test")
                docker("build", "-q", "-f", "-", str(context), input=(
                    f"FROM {IMAGE}\nCOPY . /probe/\n"
                    f"RUN test -f /probe/included.txt && test ! -e /probe/{relative_config}\n"
                ))


class TestMailCredentialSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        docker("image", "inspect", IMAGE)
        cls.good = docker("run", "--rm", "--entrypoint", "doveadm", IMAGE,
                          "-c", "/dev/null", "pw", "-s", "ARGON2ID", "-p", "private-test-password").stdout.strip()
        cls.resalted = docker("run", "--rm", "--entrypoint", "doveadm", IMAGE,
                              "-c", "/dev/null", "pw", "-s", "ARGON2ID", "-p", "vexlyx-dev").stdout.strip()

    def setUp(self):
        self.prefix = "vexlyx-credential-test-" + uuid.uuid4().hex[:10]
        self.volume = self.prefix + "-users"
        self.containers = []
        docker("volume", "create", self.volume)
        self.addCleanup(lambda: docker("volume", "rm", self.volume, check=False))
        self.box = self.prefix + "-offline"
        self.addCleanup(lambda: docker("rm", "-f", self.box, check=False))
        docker("run", "-d", "--name", self.box, "--mount", self.mount,
               "--entrypoint", "sh", IMAGE, "-c", "sleep 3600")
        initialize_state(self.box)
        self.addCleanup(self.remove_servers)

    @property
    def mount(self):
        return f"type=volume,src={self.volume},dst={STATE_ROOT}"

    def remove_servers(self):
        for name in reversed(self.containers):
            docker("rm", "-f", name, check=False)

    def write(self, content):
        docker("exec", "-i", self.box, "sh", "-c", f"cat > {USERS}", input=content)

    def read(self):
        return docker("exec", self.box, "cat", USERS).stdout

    def guard(self, action="check", check=True):
        return docker("exec", self.box, GUARD, action, USERS, check=check)

    def start(self, seed=None):
        name = self.prefix + "-server-" + str(len(self.containers))
        args = ["run", "-d", "--name", name, "--mount", self.mount,
                "-p", "127.0.0.1::993"]
        if seed is not None:
            args += ["-e", f"VEXLYX_SEED_DEV_FIXTURES={seed}"]
        docker(*args, IMAGE)
        self.containers.append(name)
        return name

    def connect(self, name):
        context = ssl._create_unverified_context()
        state = json.loads(docker("inspect", name).stdout)[0]
        port = int(state["NetworkSettings"]["Ports"]["993/tcp"][0]["HostPort"])
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                client = imaplib.IMAP4_SSL("127.0.0.1", port, ssl_context=context, timeout=2)
                # Dovecot deliberately delays failed authentication responses.
                client.sock.settimeout(15)
                return client
            except (OSError, EOFError, imaplib.IMAP4.abort):
                time.sleep(0.2)
        self.fail("Isolated IMAPS server did not become ready")

    def assert_blocked(self, name, reason):
        result = docker("wait", name, timeout=20)
        self.assertNotEqual(result.stdout.strip(), "0")
        result = docker("logs", name)
        logs = result.stdout + result.stderr
        self.assertIn(reason, logs)
        self.assertNotIn("Starting Dovecot IMAP", logs)
        self.assertNotIn(PUBLISHED, logs)

    def test_published_hash_really_matches_public_password(self):
        docker("exec", self.box, "doveadm", "-c", "/dev/null", "pw", "-t", PUBLISHED, "-p", "vexlyx-dev")

    def test_fresh_image_defaults_to_empty_and_rejects_public_login(self):
        self.write("")
        name = self.start()
        with self.connect(name) as client:
            self.assertEqual(self.read(), "")
            for address in ("test@vexlyx.local", "admin@vexlyx.local"):
                with self.assertRaises(imaplib.IMAP4.error):
                    client.login(address, "vexlyx-dev")
        mode = docker("exec", self.box, "stat", "-c", "%a:%U:%G", USERS).stdout.strip()
        self.assertEqual(mode, "640:root:dovecot")

    def test_production_blocks_legacy_hash_even_on_another_address(self):
        original = row("customer@example.org", PUBLISHED)
        self.write(original)
        self.assert_blocked(self.start("false"), "Refusing production startup")
        self.assertEqual(self.read(), original)

    def test_production_blocks_resalted_fixtures_and_crlf(self):
        self.write(row("ADMIN@vexlyx.local", self.resalted).replace("\n", "\r\n"))
        self.assertNotEqual(self.guard(check=False).returncode, 0)
        self.assert_blocked(self.start("false"), "Refusing production startup")

    def test_published_hash_revocation_survives_encoding_changes(self):
        for hash_value in (PUBLISHED.removeprefix("{ARGON2ID}"), PUBLISHED.replace("t=3,p=1", "p=1,t=3")):
            with self.subTest():
                self.write(row("copied@example.org", hash_value))
                self.assertNotEqual(self.guard(check=False).returncode, 0)

    def test_invalid_flag_fails_instead_of_seeding(self):
        self.assert_blocked(self.start("FALSE"), "must be true or false")

    def test_rotated_fixture_and_unrelated_mailbox_survive_cleanup(self):
        safe = row("test@vexlyx.local", self.good) + row("customer@example.org", self.good)
        original = row("admin@vexlyx.local", self.resalted) + row("copied@example.org", PUBLISHED) + safe
        self.write(original)
        self.guard("remediate")
        self.assertEqual(self.read(), safe)
        backup = docker("exec", self.box, "sh", "-c", f"cat {USERS}.before-remediation.*").stdout
        self.assertEqual(backup, original)
        mode = docker("exec", self.box, "sh", "-c", f"stat -c %a {USERS}.before-remediation.*").stdout.strip()
        self.assertEqual(mode, "600")
        self.guard()
        # A second cleanup must not alter clean state or create more backups.
        self.guard("remediate")
        count = docker("exec", self.box, "sh", "-c", f"ls {USERS}.before-remediation.* | wc -l").stdout.strip()
        self.assertEqual(count, "1")
        name = self.start("false")
        with self.connect(name) as client:
            self.assertEqual(client.login("customer@example.org", "private-test-password")[0], "OK")
            self.assertEqual(client.select("INBOX")[0], "OK")
        with self.connect(name) as client:
            self.assertEqual(client.login("test@vexlyx.local", "private-test-password")[0], "OK")
        with self.connect(name) as client:
            with self.assertRaises(imaplib.IMAP4.error):
                client.login("test@vexlyx.local", "vexlyx-dev")

    def test_unverifiable_fixture_aborts_cleanup_without_changing_original(self):
        original = row("copied@example.org", PUBLISHED) + row("admin@vexlyx.local", "{UNKNOWN}hash")
        self.write(original)
        self.assertNotEqual(self.guard("remediate", check=False).returncode, 0)
        self.assertEqual(self.read(), original)
        leftovers = docker("exec", self.box, "sh", "-c", f"find {STATE_ROOT} -name 'users.*'").stdout
        self.assertEqual(leftovers, "")

    def test_backup_failure_leaves_original_untouched(self):
        original = row("test@vexlyx.local", PUBLISHED) + row("customer@example.org", self.good)
        self.write(original)
        # Fail only backup creation, after validation and clean staging succeeded.
        docker("exec", "-i", self.box, "sh", "-c", "mkdir /failure; cat > /failure/mktemp; chmod +x /failure/mktemp",
               input='#!/bin/sh\ncase "$1" in *.before-remediation.*) exit 1 ;; esac\nexec /bin/mktemp "$@"\n')
        result = docker("exec", "-e", "PATH=/failure:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                        self.box, GUARD, "remediate", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.read(), original)

    def test_unavailable_verifier_fails_closed(self):
        original = row("test@vexlyx.local", self.good)
        self.write(original)
        docker("exec", "-i", self.box, "sh", "-c", "mkdir /failure; cat > /failure/doveadm; chmod +x /failure/doveadm",
               input="#!/bin/sh\nexit 75\n")
        result = docker("exec", "-e", "PATH=/failure:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                        self.box, GUARD, "check", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.read(), original)

    def test_symlink_and_directory_users_files_are_rejected(self):
        docker("exec", self.box, "sh", "-c", f"touch /tmp/other; ln -s /tmp/other {USERS}")
        self.assertNotEqual(self.guard(check=False).returncode, 0)
        self.assert_blocked(self.start("false"), "non-regular mailbox users file")
        docker("exec", self.box, "sh", "-c", f"rm {USERS}; mkdir {USERS}")
        self.assert_blocked(self.start("false"), "non-regular mailbox users file")

    def test_partial_dev_state_seeds_independently_without_resetting_password(self):
        # A substring address must not suppress the missing test fixture.
        self.write(row("admin@vexlyx.local", self.good).rstrip("\n") + "\n" + row("prefix-test@vexlyx.local", self.good).rstrip("\n"))
        name = self.start("true")
        with self.connect(name) as client:
            self.assertEqual(client.login("test@vexlyx.local", "vexlyx-dev")[0], "OK")
        with self.connect(name) as client:
            self.assertEqual(client.login("admin@vexlyx.local", "private-test-password")[0], "OK")
        before = self.read()
        docker("restart", name)
        with self.connect(name) as client:
            self.assertEqual(client.login("test@vexlyx.local", "vexlyx-dev")[0], "OK")
        self.assertEqual(self.read(), before)
        docker("stop", name)
        self.assert_blocked(self.start("false"), "Refusing production startup")

    def test_remediation_refuses_running_dovecot(self):
        self.write(row("customer@example.org", self.good))
        name = self.start("false")
        with self.connect(name):
            result = docker("exec", name, GUARD, "remediate", check=False)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
