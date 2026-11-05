"""Installer output: no error-looking noise on a healthy first install (#133, #134, #135)."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


STEPS = Path(__file__).resolve().parent.parent / "system" / "scripts" / "install" / "steps"


def acme_store(mains: tuple[str, ...]) -> str:
    """A stand-in for Traefik's acme.json.

    Two properties matter, and the first version of this fixture had neither:
    the file is multi-line (a single line forces the reader to consume all of it,
    so no early exit and no broken pipe), and it is far bigger than the ~64 KiB
    kernel pipe buffer — which is what made #184 fire on any real panel.
    """
    entries = ",\n".join(
        "    {\n      \"domain\": {\n        \"main\": \"%s\"\n      }\n    }" % main for main in mains
    )
    pad = ",\n".join('    "%s"' % ("a" * 44) for _ in range(9000))
    return (
        "{\n"
        '  "account": {},\n'
        '  "certificates": [\n'
        f"{entries}\n"
        "  ],\n"
        '  "padding": [\n'
        f"{pad}\n"
        "  ]\n"
        "}\n"
    )


def read_step(name: str) -> str:
    return (STEPS / name).read_text(encoding="utf-8")


def certificate_check_block(summary: str) -> str:
    """The real certificate helpers, exactly as written in the step file."""
    start = summary.index("read_acme_store() {")
    return summary[start:summary.index("log_info", start)].strip()


class InstallerOutputTest(unittest.TestCase):
    def test_locally_built_mail_images_are_built_before_services_start(self) -> None:
        images = read_step("10-images.sh")
        self.assertRegex(images, r"build dashboard api postfix dovecot")

    def test_corepack_download_prompt_is_disabled(self) -> None:
        runtime = read_step("04-runtime.sh")
        prompt = runtime.index("COREPACK_ENABLE_DOWNLOAD_PROMPT=0")
        self.assertLess(prompt, runtime.index("corepack prepare"))

    def test_summary_waits_for_certificates_before_warning(self) -> None:
        summary = read_step("16-summary.sh")
        wait = summary.index("until ")
        warning = summary.index("No Let's Encrypt certificate detected")
        self.assertLess(wait, warning)
        self.assertIn("api.${VEXLYX_DOMAIN}", summary)

    def test_certificate_check_does_not_pipe_into_an_early_exiting_grep(self) -> None:
        """The #184 guard, on the source itself.

        `cat | grep -Eq` is the shape that broke: grep exits at its first match,
        the writer then takes SIGPIPE, and the `set -o pipefail` at the top of the
        step converts that signal into a failed check — so a server holding real
        certificates reported that it held none.
        """
        block = certificate_check_block(read_step("16-summary.sh"))
        self.assertNotIn("grep", block)
        self.assertIn("|| true", block)

    def test_certificate_check_reads_a_store_larger_than_the_pipe_buffer(self) -> None:
        """Executes the step file's real helpers under the step file's own pipefail."""
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash is required")
        block = certificate_check_block(read_step("16-summary.sh"))

        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            bin_dir.mkdir()
            store = Path(tmp) / "acme.json"
            # `cat`, like the shipped command, because the failure under test is
            # the producer being killed by SIGPIPE — a shell builtin writing the
            # same bytes survives it and would test nothing.
            (bin_dir / "docker").write_text(
                "#!/usr/bin/env bash\n"
                "# Stands in for `docker compose ... exec -T traefik cat acme.json`.\n"
                'exec cat "${VEXLYX_FAKE_ACME_STORE}"\n',
                encoding="utf-8",
                newline="\n",
            )
            (bin_dir / "docker").chmod(0o755)

            script = (
                "set -euo pipefail\n"  # line 2 of 16-summary.sh
                "COMPOSE=(docker compose)\n"
                f"{block}\n"
                "store=\"$(read_acme_store)\"\n"
                "printf 'size=%s\\n' \"${#store}\"\n"
                "printf 'missing=%s\\n' \"$(missing_certificates \"${store}\" | tr '\\n' ',')\"\n"
            )
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
            env["VEXLYX_DOMAIN"] = "panel.example.com"

            cases = (
                # Both panel names certified -> nothing missing, even though the
                # reader quits long before the padding arrives.
                (("panel.example.com", "api.panel.example.com"), ""),
                # Only the apex name certified -> the API hostname is reported on
                # its own instead of warning about both.
                (("panel.example.com",), "api.panel.example.com"),
                # Nothing certified for this panel -> both names reported.
                (("other.example.org",), "panel.example.com,api.panel.example.com"),
            )
            for mains, expected in cases:
                with self.subTest(mains=mains):
                    store.write_text(acme_store(mains), encoding="utf-8")
                    self.assertGreater(store.stat().st_size, 100_000, "fixture must exceed the pipe buffer")
                    env["VEXLYX_FAKE_ACME_STORE"] = str(store)
                    result = subprocess.run(
                        [bash, "-c", script],
                        capture_output=True, text=True, env=env, check=False, cwd=tmp,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                    reported = result.stdout.split("size=")[1].split()[0]
                    self.assertGreater(int(reported), 100_000)
                    missing = result.stdout.split("missing=")[1].strip().rstrip(",")
                    self.assertEqual(missing, expected)

    def test_the_old_shape_reports_a_present_certificate_as_missing(self) -> None:
        """The fixture has to be able to catch #184, or the tests above are theatre.

        This is the command the step file used to ship: `cat` piped into `grep
        -Eq`, run under `set -euo pipefail`. It has to fail on a store that does
        contain the hostname. If it instead reports the certificate present, this
        platform never delivered the broken pipe and the assertion is skipped
        rather than silently passing.
        """
        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash is required")
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "acme.json"
            store.write_text(acme_store(("panel.example.com", "api.panel.example.com")), encoding="utf-8")
            script = (
                "set -euo pipefail\n"
                f'cat "{store}" | grep -Eq "\\"main\\": ?\\"panel.example.com\\""'
            )
            result = subprocess.run([bash, "-c", script], capture_output=True, text=True, check=False)
            if result.returncode == 0:
                self.skipTest("this platform does not kill the writer on a closed pipe; "
                              "the SIGPIPE false negative cannot be reproduced here")
            self.assertEqual(result.returncode, 141, "expected the pipeline to fail via SIGPIPE (141)")

    def test_certificate_check_accepts_the_compact_acme_json_spacing(self) -> None:
        """`"main":"host"` stays matched, as the old `"main\": ?\""` regex allowed."""
        summary = read_step("16-summary.sh")
        block = certificate_check_block(summary)
        self.assertIn("acme_store_has_certificate_for", block)

        bash = shutil.which("bash")
        if not bash:
            self.skipTest("bash is required")
        script = (
            "set -euo pipefail\n"
            "COMPOSE=(docker compose)\n"
            f"{block}\n"
            "acme_store_has_certificate_for '{\"certificates\":[{\"main\":\"panel.example.com\"}]}' "
            "panel.example.com && echo compact-found\n"
            "acme_store_has_certificate_for '{\"certificates\":[{\"main\": \"panel.example.com\"}]}' "
            "panel.example.com && echo spaced-found\n"
        )
        result = subprocess.run([bash, "-c", script], capture_output=True, text=True, check=False)
        self.assertEqual(result.stdout.split(), ["compact-found", "spaced-found"], result.stderr)


if __name__ == "__main__":
    unittest.main()
