"""The post-deploy probe asks the question Traefik asks (#202).

A deploy used to be finished the moment Docker said the process was up. A container
whose app binds `127.0.0.1` keeps its process up, answers loopback, and serves
nothing on the address the router connects to -- so the deploy log read Success
while the domain read 502.

`cmd_deploy` now probes that address from the host once the container is up, and
only for images that declare no HEALTHCHECK: Docker already grades everything else
and the panel shows that verdict, so probing those again would just slow a good
deploy down without telling anyone anything new.

Run with: python tests/test_post_deploy_routable_probe.py
"""

import importlib.util
import json
import socket
import subprocess
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
APPS = "vexlyx-apps"

spec = importlib.util.spec_from_file_location(
    "docker_manager_routable", ROOT / "system" / "python" / "docker_manager.py"
)
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)


def inspect_output(payload, returncode=0):
    """What one `docker inspect --format` call answers."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess([], returncode, text, "")


class RoutableAddressTest(unittest.TestCase):
    def test_it_reads_the_apps_network_address(self):
        with mock.patch.object(
            dm,
            "run_bounded",
            return_value=inspect_output({APPS: {"IPAddress": "172.20.0.8"}, "bridge": {}}),
        ):
            self.assertEqual(dm.container_routable_ip("docker", "abc123"), "172.20.0.8")

    def test_a_container_on_another_network_has_nothing_to_probe(self):
        with mock.patch.object(
            dm, "run_bounded", return_value=inspect_output({"bridge": {"IPAddress": "172.17.0.2"}})
        ):
            self.assertIsNone(dm.container_routable_ip("docker", "abc123"))

    def test_an_empty_ip_address_field_is_not_an_address(self):
        # Docker reports "" for a container attached to a network it has not
        # finished joining; connecting to "" would probe the wrong thing.
        with mock.patch.object(
            dm, "run_bounded", return_value=inspect_output({APPS: {"IPAddress": ""}})
        ):
            self.assertIsNone(dm.container_routable_ip("docker", "abc123"))

    def test_a_failed_or_unparseable_inspect_is_no_address_rather_than_a_crash(self):
        for result in (
            inspect_output("not json at all", returncode=0),
            inspect_output({}, returncode=1),
        ):
            with self.subTest(result=result.stdout), mock.patch.object(
                dm, "run_bounded", return_value=result
            ):
                self.assertIsNone(dm.container_routable_ip("docker", "abc123"))

    def test_no_container_means_no_inspect_call(self):
        with mock.patch.object(dm, "run_bounded") as bounded:
            self.assertIsNone(dm.container_routable_ip("docker", ""))
            self.assertEqual(bounded.call_count, 0)


class HealthcheckGateTest(unittest.TestCase):
    def test_an_image_that_declares_a_healthcheck_is_left_to_docker(self):
        with mock.patch.object(
            dm, "run_bounded", return_value=inspect_output("1\n")
        ):
            self.assertTrue(dm.container_declares_healthcheck("docker", "abc123"))

    def test_an_image_with_no_healthcheck_is_the_one_this_probe_covers(self):
        with mock.patch.object(
            dm, "run_bounded", return_value=inspect_output("0\n")
        ):
            self.assertFalse(dm.container_declares_healthcheck("docker", "abc123"))

    def test_a_failed_inspect_does_not_claim_a_healthcheck(self):
        with mock.patch.object(
            dm, "run_bounded", return_value=inspect_output("1", returncode=1)
        ):
            self.assertFalse(dm.container_declares_healthcheck("docker", "abc123"))


class PortListeningTest(unittest.TestCase):
    def setUp(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]

    def tearDown(self):
        self.sock.close()

    def test_a_listening_socket_answers(self):
        self.assertTrue(dm.port_is_listening("127.0.0.1", self.port, 2))

    def test_a_refused_connection_is_not_listening(self):
        # A port nothing holds open: the same answer a loopback-only bind gives
        # the routable address.
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        closed_port = free.getsockname()[1]
        free.close()
        self.assertFalse(dm.port_is_listening("127.0.0.1", closed_port, 2))


class ProbeRetryTest(unittest.TestCase):
    def test_it_gives_a_starting_app_more_than_one_chance(self):
        with mock.patch.object(
            dm, "container_routable_ip", return_value="172.20.0.8"
        ), mock.patch.object(
            dm, "port_is_listening", side_effect=[False, False, True]
        ) as probe, mock.patch.object(
            dm, "ROUTABLE_PROBE_RETRY_DELAY_SECONDS", 0
        ):
            address, reachable = dm.probe_routable_listen("docker", "abc123", 3000)
        self.assertEqual((address, reachable), ("172.20.0.8", True))
        self.assertEqual(probe.call_count, 3)
        self.assertEqual(probe.call_args[0][:2], ("172.20.0.8", 3000))

    def test_an_address_that_never_answers_comes_back_unreachable_not_raised(self):
        # This line runs inside a finished deploy; raising here would turn a
        # warning into a failed deployment.
        with mock.patch.object(
            dm, "container_routable_ip", return_value="172.20.0.8"
        ), mock.patch.object(
            dm, "port_is_listening", return_value=False
        ), mock.patch.object(
            dm, "ROUTABLE_PROBE_RETRY_DELAY_SECONDS", 0
        ):
            address, reachable = dm.probe_routable_listen("docker", "abc123", 3000)
        self.assertEqual((address, reachable), ("172.20.0.8", False))

    def test_a_first_attempt_that_answers_skips_the_retries(self):
        with mock.patch.object(
            dm, "container_routable_ip", return_value="172.20.0.8"
        ), mock.patch.object(
            dm, "port_is_listening", return_value=True
        ) as probe:
            self.assertEqual(dm.probe_routable_listen("docker", "abc123", 80), ("172.20.0.8", True))
            self.assertEqual(probe.call_count, 1)

    def test_nothing_is_probed_without_an_address(self):
        with mock.patch.object(
            dm, "container_routable_ip", return_value=None
        ), mock.patch.object(dm, "port_is_listening") as probe:
            self.assertEqual(dm.probe_routable_listen("docker", "abc123", 3000), (None, None))
            self.assertEqual(probe.call_count, 0)


class RoutableCheckLogTest(unittest.TestCase):
    def test_the_warning_names_the_address_the_router_uses_and_the_fix(self):
        line = dm.routable_check_log("172.20.0.8", False, 3000, "app.example.com")
        self.assertIn("172.20.0.8:3000", line)
        self.assertIn("502", line)
        self.assertIn("127.0.0.1", line)
        self.assertIn("app.example.com", line)
        self.assertTrue(line.startswith("WARNING"))

    def test_a_reachable_container_is_reported_plainly(self):
        self.assertEqual(
            dm.routable_check_log("172.20.0.8", True, 80, "app.example.com"),
            "Routable check 172.20.0.8:80 answered — Traefik can reach this container",
        )

    def test_a_container_on_the_wrong_network_is_reported_as_skipped(self):
        self.assertIn(APPS, dm.routable_check_log(None, None, 80, "app.example.com"))


class DeployWiringTest(unittest.TestCase):
    def setUp(self):
        source = (ROOT / "system" / "python" / "docker_manager.py").read_text(
            encoding="utf-8"
        ).replace("\r\n", "\n")
        self.deploy = source.split("def cmd_deploy", 1)[1].split("\ndef cmd_start", 1)[0]
        self.check = self.deploy.split("container_declares_healthcheck", 1)[1].split(
            "respond({", 1
        )[0]

    def test_the_probe_targets_the_port_the_router_upstreams_to(self):
        self.assertIn("probe_routable_listen(docker_bin, container_id, container_port)", self.deploy)

    def test_it_only_runs_for_images_docker_cannot_grade(self):
        self.assertIn("if container_id and not container_declares_healthcheck(", self.deploy)

    def test_the_verdict_is_logged_for_the_user_to_read(self):
        self.assertIn("log_line(f\"[vexlyx] {routable_check_log(", self.check)

    def test_the_check_can_never_fail_a_finished_deploy(self):
        self.assertNotIn("fail(", self.check)

    def test_a_reachable_container_does_not_print_a_warning(self):
        self.assertNotIn("WARNING", dm.routable_check_log("172.20.0.8", True, 80, "x.example.com"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
