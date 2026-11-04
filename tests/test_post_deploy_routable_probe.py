"""The post-deploy probe has to ask from where the panel actually stands (#202).

A deploy used to be finished the moment Docker said the process was up. A container
whose app binds `127.0.0.1` keeps its process up, answers loopback, and accepts
nothing from outside -- so the deploy log read Success while the domain read 502.

`cmd_deploy` now probes that once the container is up, and only for images that
declare no HEALTHCHECK: Docker already grades everything else and the panel shows
that verdict, so probing those again would slow a good deploy without telling
anyone anything new.

Where the probe comes from is the whole design. `docker_manager.py` runs inside the
API container, which is on `traefik-net` and `vexlyx_default` and deliberately never
on `vexlyx-apps` -- the isolation that keeps customer projects away from panel
services. A socket opened from that namespace to a container's `vexlyx-apps` address
is dropped by Docker's inter-bridge firewall, so probing the apps IP times out for a
perfectly healthy app and blames it (#207's first cut, caught on the QA box with a
nginx bound to 0.0.0.0). The published host port goes the other way: the kernel
DNATs it to that same routable address, so a loopback-only bind refuses it and a
correct one answers -- the question we actually need asked, from a place that can
ask it.

Run with: python tests/test_post_deploy_routable_probe.py
"""

import importlib.util
import json
import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent

spec = importlib.util.spec_from_file_location(
    "docker_manager_routable", ROOT / "system" / "python" / "docker_manager.py"
)
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)


def inspect_output(payload, returncode=0):
    """What one `docker inspect --format` call answers."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.CompletedProcess([], returncode, text, "")


def route_table(default_gateway=None, extra=()):
    """Write a /proc/net/route-shaped file and return its path.

    Fields are Iface, Destination, Gateway, Flags, ..., and every address is
    little-endian hex: 010011AC is 172.17.0.1, 00000000 is the default route.
    """
    lines = ["Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT"]
    if default_gateway:
        lines.append(f"eth0\t00000000\t{default_gateway}\t0003\t0\t0\t0\t00000000\t0\t0\t0")
    for destination, gateway in extra:
        lines.append(f"eth0\t{destination}\t{gateway}\t0001\t0\t0\t0\tFFFFFFFF\t0\t0\t0")
    temp = tempfile.NamedTemporaryFile("w", suffix="_route", delete=False)
    temp.write("\n".join(lines) + "\n")
    temp.close()
    return temp.name


class HostGatewayTest(unittest.TestCase):
    def test_it_decodes_the_default_route_little_endian(self):
        # 172.18.0.1 is 010012AC reversed byte by byte.
        path = route_table("010012AC")
        self.addCleanup(os.unlink, path)
        self.assertEqual(dm.host_gateway_address(path), "172.18.0.1")

    def test_it_uses_the_default_route_not_a_network_destination(self):
        path = route_table("010012AC", extra=[("001420AC", "010012AC"), ("000000FF", "00000000")])
        self.addCleanup(os.unlink, path)
        self.assertEqual(dm.host_gateway_address(path), "172.18.0.1")

    def test_a_route_table_without_a_default_route_gives_no_address(self):
        path = route_table(None, extra=[("000000FF", "010012AC")])
        self.addCleanup(os.unlink, path)
        self.assertIsNone(dm.host_gateway_address(path))

    def test_a_missing_or_unreadable_route_file_is_no_address_rather_than_a_crash(self):
        # This runs inside whatever container the panel spawned it from; failing to
        # read /proc/net/route must skip the check, never break a finished deploy.
        self.assertIsNone(dm.host_gateway_address("/proc/no/such/route"))
        self.assertIsNone(dm.host_gateway_address("not-hex-at-all"))

    def test_an_unparsable_gateway_hex_is_no_address(self):
        path = route_table("ZZZZZZZZ")
        self.addCleanup(os.unlink, path)
        self.assertIsNone(dm.host_gateway_address(path))


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
        # A port nothing holds open: the answer a loopback-only bind gives the
        # published port the kernel forwards to its routable address.
        free = socket.socket()
        free.bind(("127.0.0.1", 0))
        closed_port = free.getsockname()[1]
        free.close()
        self.assertFalse(dm.port_is_listening("127.0.0.1", closed_port, 2))

    def test_a_socket_that_never_answers_is_not_listening(self):
        # Unroutable addresses blackhole instead of refusing, which is what the
        # apps-network probe did from the API container. Timeouts are answers too.
        self.assertFalse(dm.port_is_listening("192.0.2.1", 80, 0.25))


class PublishedPortProbeTest(unittest.TestCase):
    def test_it_gives_a_starting_app_more_than_one_chance(self):
        with mock.patch.object(
            dm, "host_gateway_address", return_value="172.18.0.1"
        ), mock.patch.object(
            dm, "port_is_listening", side_effect=[False, False, True]
        ) as probe, mock.patch.object(
            dm, "ROUTABLE_PROBE_RETRY_DELAY_SECONDS", 0
        ):
            address, reachable = dm.probe_published_port(8899)
        self.assertEqual((address, reachable), ("172.18.0.1", True))
        self.assertEqual(probe.call_count, 3)
        self.assertEqual(probe.call_args[0][:2], ("172.18.0.1", 8899))

    def test_a_port_that_never_answers_comes_back_unreachable_not_raised(self):
        # This line runs inside a finished deploy; raising here would turn a
        # warning into a failed deployment.
        with mock.patch.object(
            dm, "host_gateway_address", return_value="172.18.0.1"
        ), mock.patch.object(
            dm, "port_is_listening", return_value=False
        ), mock.patch.object(
            dm, "ROUTABLE_PROBE_RETRY_DELAY_SECONDS", 0
        ):
            address, reachable = dm.probe_published_port(8899)
        self.assertEqual((address, reachable), ("172.18.0.1", False))

    def test_a_first_attempt_that_answers_skips_the_retries(self):
        with mock.patch.object(
            dm, "host_gateway_address", return_value="172.18.0.1"
        ), mock.patch.object(
            dm, "port_is_listening", return_value=True
        ) as probe:
            self.assertEqual(dm.probe_published_port(80), ("172.18.0.1", True))
            self.assertEqual(probe.call_count, 1)

    def test_nothing_is_probed_without_a_gateway(self):
        with mock.patch.object(
            dm, "host_gateway_address", return_value=None
        ), mock.patch.object(dm, "port_is_listening") as probe:
            self.assertEqual(dm.probe_published_port(8899), (None, None))
            self.assertEqual(probe.call_count, 0)

    def test_a_port_number_is_required_to_probe_anything(self):
        with mock.patch.object(dm, "port_is_listening") as probe:
            self.assertEqual(dm.probe_published_port(0), (None, None))
            self.assertEqual(probe.call_count, 0)


class RoutableCheckLogTest(unittest.TestCase):
    def test_the_warning_names_the_published_port_and_the_bind_fix(self):
        line = dm.routable_check_log("172.18.0.1", False, 8899, "app.example.com")
        self.assertIn("172.18.0.1:8899", line)
        self.assertIn("502", line)
        self.assertIn("127.0.0.1", line)
        self.assertIn("app.example.com", line)
        self.assertTrue(line.startswith("WARNING"))

    def test_the_warning_does_not_claim_to_have_used_the_routers_own_address(self):
        # The published port stands in for the router's path; saying it probed the
        # address Traefik connects to would be a lie a future reader debugs against.
        line = dm.routable_check_log("172.18.0.1", False, 8899, "app.example.com")
        self.assertNotIn("the address Traefik connects to", line)

    def test_a_reachable_container_is_reported_plainly(self):
        line = dm.routable_check_log("172.18.0.1", True, 8899, "app.example.com")
        self.assertIn("172.18.0.1:8899", line)
        self.assertNotIn("WARNING", line)

    def test_no_gateway_is_reported_as_skipped_not_as_a_failure(self):
        line = dm.routable_check_log(None, None, 8899, "app.example.com")
        self.assertIn("skipped", line)
        self.assertNotIn("WARNING", line)
        self.assertNotIn("502", line)


class NamespaceRegressionTest(unittest.TestCase):
    """Pins the mistake #207's first cut made, so it cannot come back silently."""

    def setUp(self):
        self.source = (ROOT / "system" / "python" / "docker_manager.py").read_text(
            encoding="utf-8"
        ).replace("\r\n", "\n")
        deploy = self.source.split("def cmd_deploy", 1)[1].split("\ndef cmd_start", 1)[0]
        self.check = deploy.split("container_declares_healthcheck", 1)[1].split("respond({", 1)[0]

    def test_the_probe_never_targets_the_apps_network_address(self):
        # container_networks() reads that address for a different job (moving a
        # deployed project onto APPS_NETWORK); the probe must not start using it.
        self.assertNotIn("container_routable_ip", self.source)
        self.assertNotIn("container_networks", self.check)

    def test_the_deploy_still_probes_only_images_docker_cannot_grade(self):
        self.assertIn("def container_declares_healthcheck", self.source)


class DeployWiringTest(unittest.TestCase):
    def setUp(self):
        source = (ROOT / "system" / "python" / "docker_manager.py").read_text(
            encoding="utf-8"
        ).replace("\r\n", "\n")
        self.deploy = source.split("def cmd_deploy", 1)[1].split("\ndef cmd_start", 1)[0]
        self.check = self.deploy.split("container_declares_healthcheck", 1)[1].split(
            "respond({", 1
        )[0]

    def test_the_probe_targets_the_port_published_for_the_container(self):
        self.assertIn("probe_published_port(host_port)", self.deploy)

    def test_it_only_runs_for_images_docker_cannot_grade(self):
        self.assertIn("if container_id and not container_declares_healthcheck(", self.deploy)

    def test_the_verdict_is_logged_for_the_user_to_read(self):
        self.assertIn("log_line(f\"[vexlyx] {routable_check_log(", self.check)

    def test_the_check_can_never_fail_a_finished_deploy(self):
        self.assertNotIn("fail(", self.check)


if __name__ == "__main__":
    unittest.main(verbosity=2)
