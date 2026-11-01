"""Where each project container's healthcheck points.

#202: an app that binds 127.0.0.1 instead of $HOST answers a loopback probe
while its domain returns 502, because Traefik connects to the container's
*routable* address -- the IP Docker writes next to the container's own name in
/etc/hosts. Every project template therefore probes that address.

The rest of the lesson is that a probe must use a tool the image really ships
and must not confuse "answered HTTP" with "listening". Verified on live
containers: the Nixpacks images carry no wget (busybox also resolves
``localhost`` to ::1 first, so an app bound to IPv4 loopback looked unhealthy),
and nginx:alpine's busybox wget exits 1 on any failure, which made the old
``test $? -ne 4`` guard impossible to trip.
"""

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "system" / "templates" / "docker-compose"

spec = importlib.util.spec_from_file_location("docker_manager_healthcheck", ROOT / "system" / "python" / "docker_manager.py")
docker_manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docker_manager)

ROUTABLE_MARKERS = (
    "require('os').hostname()",   # node.yml, next.yml
    "socket.gethostname()",       # python.yml
    "gethostname()",              # php.yml
    "$${HOSTNAME}",               # static.yml, wordpress.yml, php-no-build.yml
)
LOOPBACK_MARKERS = ("127.0.0.1", "localhost")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def probe_of(compose_text: str) -> str:
    """The healthcheck's test line, or "" when the service declares none."""
    match = re.search(r"^\s*test: \[.*$", compose_text, re.M)
    return match.group(0) if match else ""


def render(template: Path, tmp: str) -> str:
    docker_manager.generate_compose_file(
        compose_dir=Path(tmp),
        template_path=template,
        image_name="example:latest",
        service_name="abc123",
        hostname="app.example.test",
        host_port=8100,
        container_port=3000,
        memory_limit="512m",
        env_vars={},
        extra_placeholders={
            "deploy_dir": tmp, "static_root": tmp, "php_root": tmp,
            "nginx_conf_path": tmp + "/nginx.conf", "php_fpm_image": "php:8",
            "wp_db_host": "h", "wp_db_name": "n", "wp_db_user": "u",
            "wp_db_password": "p", "wp_db_prefix": "wp_",
        },
    )
    return read(Path(tmp) / "docker-compose.yml")


TEMPLATES_WITH_PROBES = [t for t in sorted(TEMPLATES.glob("*.yml")) if probe_of(read(t))]


class ProbeTargetTest(unittest.TestCase):
    def test_every_template_but_the_custom_dockerfile_is_probed(self) -> None:
        unprobed = {t.name for t in sorted(TEMPLATES.glob("*.yml"))} - {t.name for t in TEMPLATES_WITH_PROBES}
        # A user's own Dockerfile may define its own HEALTHCHECK, so the panel
        # declares none and the badge honestly says "no probe" instead of
        # guessing. See containerHealth = null in #202.
        self.assertEqual(unprobed, {"docker.yml"})

    def test_every_probe_asks_the_container_routable_address(self) -> None:
        for template in TEMPLATES_WITH_PROBES:
            with self.subTest(template=template.name):
                probe = probe_of(read(template))
                self.assertTrue(any(marker in probe for marker in ROUTABLE_MARKERS), probe)

    def test_no_probe_still_trusts_loopback(self) -> None:
        for template in TEMPLATES_WITH_PROBES:
            with self.subTest(template=template.name):
                probe = probe_of(read(template))
                for marker in LOOPBACK_MARKERS:
                    self.assertNotIn(marker, probe)

    def test_generated_compose_files_keep_the_target(self) -> None:
        for template in TEMPLATES_WITH_PROBES:
            with self.subTest(template=template.name), tempfile.TemporaryDirectory() as tmp:
                probe = probe_of(render(template, tmp))
                self.assertTrue(any(marker in probe for marker in ROUTABLE_MARKERS), probe)
                for marker in LOOPBACK_MARKERS:
                    self.assertNotIn(marker, probe)


class ProbeShapeTest(unittest.TestCase):
    """Why each template picks the tool it picks."""

    def test_node_probes_resolve_by_syscall_because_next_overrides_the_hostname_env(self) -> None:
        # next.yml injects HOSTNAME: "0.0.0.0" for Next.js itself, so $HOSTNAME
        # in that container is a bind address, not a name to look up.
        for name in ("node.yml", "next.yml"):
            with self.subTest(template=name):
                self.assertIn("require('os').hostname()", probe_of(read(TEMPLATES / name)))
        self.assertIn('HOSTNAME: "0.0.0.0"', read(TEMPLATES / "next.yml"))

    def test_shell_probes_escape_the_dollar_for_compose(self) -> None:
        # Compose substitutes $VAR from its own environment at parse time; $$ is
        # how a literal dollar survives into the container's shell.
        for name in ("static.yml", "wordpress.yml", "php-no-build.yml"):
            with self.subTest(template=name):
                self.assertIn("$${HOSTNAME}", probe_of(read(TEMPLATES / name)))

    def test_nginx_probes_do_not_read_http_status(self) -> None:
        # nginx answering 502 because PHP-FPM died still means Traefik can reach
        # the container; conflating the two would hide which half is broken.
        for name in ("static.yml", "wordpress.yml", "php-no-build.yml"):
            with self.subTest(template=name):
                self.assertIn("nc -z", probe_of(read(TEMPLATES / name)))

    def test_python_and_php_probe_with_the_runtime_their_image_guarantees(self) -> None:
        self.assertIn('"CMD", "python", "-c"', probe_of(read(TEMPLATES / "python.yml")))
        self.assertIn('"CMD", "php", "-r"', probe_of(read(TEMPLATES / "php.yml")))
        for name in ("python.yml", "php.yml", "node.yml", "next.yml"):
            with self.subTest(template=name):
                self.assertNotIn("wget", probe_of(read(TEMPLATES / name)))
                self.assertNotIn("curl", probe_of(read(TEMPLATES / name)))

if __name__ == "__main__":
    unittest.main()
