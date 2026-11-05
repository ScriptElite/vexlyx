"""The deploy hostname never reaches the Traefik rule as free text (#192).

`generate_compose_file()` substitutes the resolved hostname into

    - "traefik.http.routers.<service>.rule=Host(`{{hostname}}`)"

in eight compose templates. That is a double-quoted YAML label whose value is
Traefik rule source, so a backtick closes `Host()` and reopens it, and a quote
plus a newline closes the label and adds another. Measured on the QA box before
the guard existed, a crafted `domain` produced a manifest `docker compose
config` accepted with `Host(`app.example.com`) or Host(`victim.example.org`)`
and with an extra `traefik.services.stolen` label — a project claiming hostnames
the panel never granted it, or pointing a router at another tenant's container.

These tests drive the real generator. Legitimate values — including the
`{slug}.{base_domain}` shapes the panel itself builds and the wildcard the
panel's own domain schema accepts — must still generate a file unchanged.
"""

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "docker_manager_hostname", REPO_ROOT / "system" / "python" / "docker_manager.py"
)
docker_manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docker_manager)

TEMPLATE_DIR = REPO_ROOT / "system" / "templates" / "docker-compose"
TEMPLATE = TEMPLATE_DIR / "node.yml"

GOOD = [
    "app.example.com",
    "example.com",
    "app.vexlyx.localhost",  # what a default install generates
    "my-app.qa.atlantiqs.org",  # what the QA panel generates
    "app.127.0.0.1",  # a dev install whose BASE_DOMAIN is an address
    "192.0.2.1",
    "*.example.com",  # the wildcard the panel's own HostnameSchema allows
    "App.Example.COM",
]

BAD = {
    "an extra Host() clause": "app.example.com`) or Host(`victim.example.org",
    "an extra label": 'app.example.com"\n      - "traefik.services.stolen=x',
    "a service key": 'app.example.com"\n    volumes:\n      - "/:/host #',
    "a single quote": "app.example.com'",
    "a backslash": "app.example.com\\",
    "a path": "../../etc/shadow",
    "a scheme": "http://app.example.com",
    "a port": "app.example.com:8080",
    "a space": "app example.com",
    "a trailing newline": "app.example.com\n",
    "a carriage return": "app.example.com\r\n",
    "a tab": "app\t.example.com",
    "non-ascii": "ünïcode.example.com",
    "empty": "",
    "too long": "a" * 254,
}


class GeneratorHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.deploy = Path(self._tmp.name) / "project" / "deploy"
        self.deploy.mkdir(parents=True)

    def generate(self, hostname):
        """Call the real generator; returns (exit-json or None, compose path)."""
        out = io.StringIO()
        compose = self.deploy / "docker-compose.yml"
        try:
            with contextlib.redirect_stdout(out):
                docker_manager.generate_compose_file(
                    compose_dir=self.deploy,
                    template_path=TEMPLATE,
                    image_name="example:latest",
                    service_name="abc123",
                    hostname=hostname,
                    host_port=8100,
                    container_port=3000,
                    memory_limit="512m",
                    env_vars={},
                    extra_placeholders={"deploy_dir": self.deploy.resolve().as_posix()},
                )
            return None, compose
        except SystemExit:
            return json.loads(out.getvalue().strip().splitlines()[-1]), compose

    def rule_lines(self, compose_path):
        text = compose_path.read_text(encoding="utf-8")
        return [line.strip() for line in text.splitlines() if ".rule=" in line]


class GoodHostnameTest(GeneratorHarness):
    def test_every_accepted_shape_generates_the_expected_rule(self):
        for hostname in GOOD:
            with self.subTest(hostname=hostname):
                reported, compose = self.generate(hostname)
                self.assertIsNone(reported)
                self.assertEqual(
                    self.rule_lines(compose),
                    [
                        '- "traefik.http.routers.abc123.rule=Host(`%s`)"' % hostname,
                        '- "traefik.http.routers.abc123-secure.rule=Host(`%s`)"' % hostname,
                    ],
                )

    def test_the_rest_of_the_manifest_is_unchanged_by_the_guard(self):
        _, compose = self.generate("app.example.com")
        body = compose.read_text(encoding="utf-8")
        self.assertIn('name: "vexlyx-abc123"', body)
        self.assertIn('- "8100:3000"', body)
        self.assertIn('image: "example:latest"', body)
        self.assertEqual(body.count("traefik.enable=true"), 1)


class BadHostnameTest(GeneratorHarness):
    def test_every_rejected_shape_refuses_and_writes_nothing(self):
        for label, hostname in BAD.items():
            with self.subTest(case=label):
                reported, compose = self.generate(hostname)
                self.assertIsNotNone(reported, "generator accepted %r" % hostname)
                self.assertEqual(reported["code"], "INVALID_HOSTNAME")
                self.assertFalse(compose.exists())

    def test_a_refusal_does_not_touch_an_existing_manifest(self):
        _, compose = self.generate("app.example.com")
        before = compose.read_text(encoding="utf-8")
        reported, _ = self.generate("app.example.com`) or Host(`victim.example.org")
        self.assertEqual(reported["code"], "INVALID_HOSTNAME")
        self.assertEqual(compose.read_text(encoding="utf-8"), before)


class AssertHostnameTest(unittest.TestCase):
    def assert_refused(self, hostname):
        out = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(out):
            docker_manager.assert_hostname_is_rule_safe(hostname)
        self.assertEqual(json.loads(out.getvalue().strip())["code"], "INVALID_HOSTNAME")

    def test_accepts_names_and_addresses(self):
        for hostname in GOOD:
            with self.subTest(hostname=hostname):
                docker_manager.assert_hostname_is_rule_safe(hostname)

    def test_refuses_everything_else(self):
        for label, hostname in BAD.items():
            with self.subTest(case=label):
                self.assert_refused(hostname)

    def test_a_trailing_newline_is_not_allowed_by_the_anchor(self):
        # re.match with `$` would accept "name\n"; fullmatch must not.
        self.assert_refused("app.example.com\n")

    def test_the_guard_refuses_a_non_string(self):
        for value in (None, 8080, {"a": "b"}):
            with self.subTest(value=value):
                self.assert_refused(value)


class TemplateSinkTest(unittest.TestCase):
    """The guard's character set has to match the text the value lands in."""

    # Plain literals rather than a regex: the invariant is about exact
    # characters in the template, and a stray backtick anywhere else in the
    # label would reopen the rule even with the guard in place.
    PLACEHOLDER = "{{hostname}}"
    RULE = "Host(`{{hostname}}`)"
    LABEL_OPEN = '- "traefik.http.routers.{{service_name}}'
    LABEL_CLOSE = '`)"'

    def test_every_template_places_the_hostname_in_one_backtick_rule(self):
        templates = sorted(TEMPLATE_DIR.glob("*.yml"))
        self.assertGreaterEqual(len(templates), 1)
        for template in templates:
            lines = [line.strip() for line in template.read_text(encoding="utf-8").splitlines()]
            hits = [line for line in lines if self.PLACEHOLDER in line]
            self.assertEqual(len(hits), 2, template.name)
            for line in hits:
                self.assertEqual(line.count(self.PLACEHOLDER), 1, f"{template.name}: {line}")
                self.assertIn(self.RULE, line)
                self.assertTrue(line.startswith(self.LABEL_OPEN), f"{template.name}: {line}")
                self.assertTrue(line.endswith(self.LABEL_CLOSE), f"{template.name}: {line}")
                self.assertNotIn("`", line.replace(self.RULE, ""), f"{template.name}: {line}")


if __name__ == "__main__":
    unittest.main()
