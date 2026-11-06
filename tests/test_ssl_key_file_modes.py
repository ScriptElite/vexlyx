"""Private keys land 0600 and a deleted certificate takes its copies with it (#195).

`system/python/ssl_manager.py` wrote every PEM with `Path.write_text()`, so a
private key got the process umask — 0644 in the API image, which runs as root
with umask 0022 — while `mail_tls_manager.py:62-63` had been writing the key it
extracts from the same `acme.json` as 0600 all along. `generate_self_signed()`
also leaves a second pair under the bare hostname as a convenience copy, which
nothing ever removed.

Everything here runs the real script in a temporary working directory, because
`get_certs_dir()` resolves `docker/traefik/certs` relative to the cwd — so the
repo's own tracked certs directory is never touched.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPT = ROOT_DIR / "system" / "python" / "ssl_manager.py"

POSIX = os.name == "posix"


def mode_of(path: Path) -> int:
    return path.stat().st_mode & 0o777


class SslKeyFileModeTest(unittest.TestCase):
    def setUp(self):
        self.workdir = Path(tempfile.mkdtemp(prefix="vexlyx-195-"))
        self.certs = self.workdir / "docker" / "traefik" / "certs"

    def tearDown(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    def run_manager(self, command: str, payload: dict) -> dict:
        """Invoke the helper the way the API does now: script only, request on
        stdin (`system/python/ssl_manager.py:main()`)."""
        document = json.dumps({"command": command, "payload": payload})
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=document,
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=str(self.workdir),
        )
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, f"expected one document, got: {proc.stdout!r} {proc.stderr!r}")
        result = json.loads(lines[0])
        self.assertEqual(proc.returncode, 0, f"{command} failed: {result.get('error')} {proc.stderr}")
        return result

    def make_pair(self, hostname="modes-ssl.vexlyx.localhost", domain_id="d-modes"):
        """Generate a pair through the helper and return its PEM text."""
        return self.run_manager("generate_self_signed", {
            "hostname": hostname,
            "domainId": domain_id,
            "days": 90,
        })

    # -- the modes themselves -------------------------------------------------

    @unittest.skipUnless(POSIX, "file modes are a POSIX concern")
    def test_a_generated_private_key_is_owner_readable_only(self):
        self.make_pair()
        key = self.certs / "domain-d-modes.key"
        cert = self.certs / "domain-d-modes.crt"
        self.assertTrue(key.exists(), sorted(p.name for p in self.certs.iterdir()))
        self.assertEqual(mode_of(key), 0o600, "a private key must not be readable by anyone else")
        # The certificate is public and Traefik is not the only thing that may
        # want to read it, so it deliberately keeps its old 0644.
        self.assertEqual(mode_of(cert), 0o644)

    @unittest.skipUnless(POSIX, "file modes are a POSIX concern")
    def test_the_convenience_copy_of_a_key_is_not_world_readable_either(self):
        self.make_pair()
        self.assertEqual(mode_of(self.certs / "modes-ssl.vexlyx.localhost.key"), 0o600)
        self.assertEqual(mode_of(self.certs / "modes-ssl.vexlyx.localhost.crt"), 0o644)

    @unittest.skipUnless(POSIX, "file modes are a POSIX concern")
    def test_an_uploaded_key_is_owner_readable_only(self):
        pair = self.make_pair(domain_id="d-source")
        saved = self.run_manager("save_custom", {
            "domainId": "d-upload",
            "certificate": pair["certPem"],
            "privateKey": pair["keyPem"],
        })
        self.assertTrue(saved["success"], saved)
        self.assertEqual(mode_of(Path(saved["keyPath"])), 0o600)
        self.assertEqual(mode_of(Path(saved["certPath"])), 0o644)

    @unittest.skipUnless(POSIX, "file modes are a POSIX concern")
    def test_rewriting_a_key_that_was_world_readable_tightens_it(self):
        """What an existing install sees: the file it already had is fixed by
        the next write, not left at 0644 because the name was taken."""
        self.certs.mkdir(parents=True)
        stale = self.certs / "domain-d-upload.key"
        stale.write_text("old\n", encoding="utf-8")
        os.chmod(stale, 0o644)
        self.assertEqual(mode_of(stale), 0o644)

        pair = self.make_pair(domain_id="d-source")
        self.run_manager("save_custom", {
            "domainId": "d-upload",
            "certificate": pair["certPem"],
            "privateKey": pair["keyPem"],
        })
        self.assertEqual(mode_of(stale), 0o600)

    @unittest.skipUnless(POSIX, "file modes are a POSIX concern")
    def test_a_created_certs_directory_has_no_group_or_other_bits(self):
        self.assertFalse(self.certs.exists())
        self.make_pair()
        self.assertEqual(mode_of(self.certs), 0o700)

    def test_the_written_file_keeps_its_contents_and_leaves_no_temporary_behind(self):
        pair = self.make_pair(domain_id="d-round")
        key = self.certs / "domain-d-round.key"
        self.assertEqual(key.read_text(encoding="utf-8"), pair["keyPem"])
        # The write goes through a temporary file in the same directory, so a
        # reader never sees half a key — but it must not leave the temp either.
        residue = [p.name for p in self.certs.iterdir() if p.name.startswith(".")]
        self.assertEqual(residue, [], residue)

    # -- the convenience copies on deletion -----------------------------------

    def test_deleting_a_certificate_takes_the_convenience_copies_with_it(self):
        self.make_pair(hostname="gone-ssl.vexlyx.localhost", domain_id="d-gone")
        self.assertTrue((self.certs / "gone-ssl.vexlyx.localhost.key").exists())

        result = self.run_manager("delete_cert", {
            "domainId": "d-gone",
            "hostname": "gone-ssl.vexlyx.localhost",
        })
        self.assertTrue(result["deleted"], result)
        self.assertEqual(len(result["copiesRemoved"]), 2, result)
        self.assertEqual(sorted(p.name for p in self.certs.iterdir()), [])

    def test_a_wildcard_domains_copy_is_found_under_its_cleaned_name(self):
        self.make_pair(hostname="*.wild-ssl.vexlyx.localhost", domain_id="d-wild")
        self.assertTrue((self.certs / "wildcard.wild-ssl.vexlyx.localhost.key").exists())

        result = self.run_manager("delete_cert", {
            "domainId": "d-wild",
            "hostname": "*.wild-ssl.vexlyx.localhost",
        })
        self.assertEqual(len(result["copiesRemoved"]), 2, result)
        self.assertFalse((self.certs / "wildcard.wild-ssl.vexlyx.localhost.key").exists())

    def test_a_caller_that_sends_no_hostname_changes_nothing_but_the_pair(self):
        """The API half of this fix reaches an install only when its image is
        rebuilt, so the helper's old behaviour has to stay correct on its own."""
        self.make_pair(hostname="old-api.vexlyx.localhost", domain_id="d-old")
        result = self.run_manager("delete_cert", {"domainId": "d-old"})
        self.assertTrue(result["deleted"], result)
        self.assertEqual(result["copiesRemoved"], [], result)
        self.assertTrue((self.certs / "old-api.vexlyx.localhost.key").exists())

    def test_a_copy_that_belongs_to_someone_else_is_left_alone(self):
        self.make_pair(hostname="ours.vexlyx.localhost", domain_id="d-ours")
        # Something else owns what is under those names now — an operator's
        # file, or an older pair from before a re-upload. Deleting this domain
        # must not reach them, because the copy rule is only safe if it proves
        # the bytes are actually this certificate's.
        foreign = {}
        for name in ("crt", "key"):
            path = self.certs / f"ours.vexlyx.localhost.{name}"
            path.write_text(
                f"-----BEGIN FOREIGN {name.upper()}-----\nnot ours\n-----END FOREIGN {name.upper()}-----\n",
                encoding="utf-8",
            )
            foreign[name] = path.read_text(encoding="utf-8")

        result = self.run_manager("delete_cert", {
            "domainId": "d-ours",
            "hostname": "ours.vexlyx.localhost",
        })
        self.assertTrue(result["deleted"], result)
        self.assertEqual(result["copiesRemoved"], [], result)
        for name in ("crt", "key"):
            path = self.certs / f"ours.vexlyx.localhost.{name}"
            self.assertTrue(path.exists(), str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), foreign[name])

    def test_only_a_copy_whose_bytes_match_is_removed(self):
        """Each name is judged on its own content, so a stale private key that
        happens to sit under this domain's hostname is not deleted with the
        certificate copy that genuinely does belong to it."""
        pair = self.make_pair(hostname="mixed.vexlyx.localhost", domain_id="d-mixed")
        key_copy = self.certs / "mixed.vexlyx.localhost.key"
        key_copy.write_text(pair["certPem"], encoding="utf-8")  # not this key

        result = self.run_manager("delete_cert", {
            "domainId": "d-mixed",
            "hostname": "mixed.vexlyx.localhost",
        })
        self.assertEqual(
            [Path(p).name for p in result["copiesRemoved"]],
            ["mixed.vexlyx.localhost.crt"],
            result,
        )
        self.assertTrue(key_copy.exists(), "the helper must delete only what it recognises")
        self.assertEqual(key_copy.read_text(encoding="utf-8"), pair["certPem"])

    def test_deleting_a_certificate_never_touches_another_domains_files(self):
        """A hostname-shaped name is only a copy when the content says so, and
        no other domain's own pair (which lives under `domain-<id>`) is in
        reach of a delete for this one."""
        self.make_pair(hostname="alpha.vexlyx.localhost", domain_id="d-alpha")
        self.make_pair(hostname="beta.vexlyx.localhost", domain_id="d-beta")
        before = {p.name: p.read_bytes() for p in self.certs.iterdir()}

        result = self.run_manager("delete_cert", {
            "domainId": "d-alpha",
            "hostname": "alpha.vexlyx.localhost",
        })
        self.assertTrue(result["deleted"], result)
        self.assertEqual(
            sorted(p.name for p in self.certs.iterdir()),
            ["beta.vexlyx.localhost.crt", "beta.vexlyx.localhost.key",
             "domain-d-beta.crt", "domain-d-beta.key"],
            result,
        )
        for name in ("domain-d-beta.crt", "domain-d-beta.key",
                     "beta.vexlyx.localhost.crt", "beta.vexlyx.localhost.key"):
            self.assertEqual((self.certs / name).read_bytes(), before[name], name)


if __name__ == "__main__":
    unittest.main()
