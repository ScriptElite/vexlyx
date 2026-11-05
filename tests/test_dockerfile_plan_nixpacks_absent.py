"""Regression test (#222): a Dockerfile plan must not require nixpacks.

`cmd_plan()` resolved the nixpacks binary four lines after reading the payload,
before it knew whether the project used nixpacks at all. A repository that ships
its own Dockerfile answers from `parse_dockerfile_info()` and never calls
`nixpacks plan`, so on a host that has Docker but not nixpacks the request died
with NIXPACKS_NOT_FOUND — and it died before the Dockerfile branch, which is why
the same defect's fix in `cmd_build()` could not save a deploy: a deploy detects
first (`apps/api/src/modules/build/service.ts`, "Phase 1 — detect framework")
and only then builds.

The lookup now sits after the Dockerfile branch returns, so these tests pin the
ordering rather than the messaging:

* a Dockerfile project is planned with nixpacks deliberately unresolvable, and
  the resolver is never consulted;
* a project with no Dockerfile still consults it, and its failure still reaches
  the caller as one error document — the guard was moved, not removed;
* a missing project directory is reported as PROJECT_DIR_NOT_FOUND, because the
  directory check now runs before anything looks for a binary.
"""

import importlib.util
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


PYTHON_DIR = Path(__file__).resolve().parents[1] / "system" / "python"

DOCKERFILE = (
    "FROM node:20-slim\n"
    "WORKDIR /app\n"
    "EXPOSE 3001\n"
    'CMD ["node", "server.js"]\n'
)


def load_build_manager():
    path = PYTHON_DIR / "build_manager.py"
    spec = importlib.util.spec_from_file_location("build_manager_plan_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def nixpacks_lookup_name(build_manager) -> str:
    """Branches that split the resolver call it find_nixpacks_binary()."""
    if hasattr(build_manager, "find_nixpacks_binary"):
        return "find_nixpacks_binary"
    return "get_nixpacks_binary"


def documents(output: str) -> list:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


class TestDockerfilePlanWithoutNixpacks(unittest.TestCase):
    def run_plan(self, payload, lookup_factory):
        """Drive cmd_plan() with the nixpacks resolver and the subprocess layer pinned.

        `lookup_factory` receives the module under test so a case can raise its own
        `fail()` rather than an imitation of it.
        """
        build_manager = load_build_manager()
        stdout = io.StringIO()
        with mock.patch.object(
            build_manager,
            nixpacks_lookup_name(build_manager),
            side_effect=lookup_factory(build_manager),
        ) as lookup, mock.patch.object(build_manager, "run_bounded") as bounded, \
                redirect_stdout(stdout):
            exit_code = None
            try:
                build_manager.cmd_plan(payload)
            except SystemExit as exc:
                exit_code = exc.code
        return documents(stdout.getvalue()), exit_code, stdout.getvalue(), lookup, bounded

    def test_dockerfile_plan_succeeds_when_nixpacks_is_absent(self):
        def forbidden(_build_manager):
            def raise_forbidden():
                raise AssertionError(
                    "cmd_plan() resolved the nixpacks binary before the Dockerfile "
                    "branch; a Dockerfile plan must not require nixpacks."
                )
            return raise_forbidden

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")

            messages, exit_code, output, lookup, bounded = self.run_plan(
                {"projectDir": str(project_dir)}, forbidden
            )

        self.assertIsNone(exit_code, f"cmd_plan() exited for a Dockerfile project. Output:\n{output}")
        lookup.assert_not_called()
        bounded.assert_not_called()
        self.assertEqual(len(messages), 1, f"Expected one plan document. Output:\n{output}")
        plan = messages[0]
        self.assertEqual(plan["framework"], "dockerfile")
        self.assertEqual(plan["detectedType"], "DOCKER")
        self.assertTrue(plan["isDockerfile"])
        # A Dockerfile owns its own install/build/start; nothing is proposed.
        self.assertIsNone(plan["installCmd"])
        self.assertIsNone(plan["buildCmd"])
        self.assertIsNone(plan["startCmd"])
        self.assertEqual(plan["exposedPorts"], [3001])
        self.assertEqual(plan["baseImage"], "node:20-slim")

    def test_plan_without_a_dockerfile_still_consults_the_resolver(self):
        def absent(build_manager):
            def raise_absent():
                build_manager.fail("Nixpacks binary not found", "NIXPACKS_NOT_FOUND")
            return raise_absent

        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / "project"
            project_dir.mkdir()
            (project_dir / "package.json").write_text('{"name": "app"}', encoding="utf-8")

            messages, exit_code, output, lookup, bounded = self.run_plan(
                {"projectDir": str(project_dir)}, absent
            )

        lookup.assert_called_once()
        bounded.assert_not_called()
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(messages), 1, f"Expected one error document. Output:\n{output}")
        self.assertEqual(messages[0]["code"], "NIXPACKS_NOT_FOUND")

    def test_missing_project_directory_is_reported_before_any_lookup(self):
        def forbidden(_build_manager):
            def raise_forbidden():
                raise AssertionError(
                    "cmd_plan() looked for a nixpacks binary for a directory that does "
                    "not exist; the directory check must come first."
                )
            return raise_forbidden

        with tempfile.TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "not-cloned-yet"

            messages, exit_code, output, lookup, _ = self.run_plan(
                {"projectDir": str(missing)}, forbidden
            )

        lookup.assert_not_called()
        self.assertEqual(exit_code, 1)
        self.assertEqual(len(messages), 1, f"Expected one error document. Output:\n{output}")
        self.assertEqual(messages[0]["code"], "PROJECT_DIR_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
