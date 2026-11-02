"""Regression test: a custom Dockerfile build must not require nixpacks.

`cmd_build()` used to resolve the nixpacks binary before it looked for a
Dockerfile, so a project shipping its own Dockerfile failed with
NIXPACKS_NOT_FOUND on hosts where Docker is installed but nixpacks is not --
even though that path runs `docker build` and never touches nixpacks.

The nixpacks lookup now happens only after the Dockerfile branch returns.
This test simulates the exact host: a working `docker` on PATH, no nixpacks
resolvable anywhere, then drives `cmd_build()` end to end and asserts the
image build completes and nixpacks is never consulted.

The lookup helper is patched by name so the same test runs on branches that
predate the find_nixpacks_binary()/get_nixpacks_binary() split.
"""

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


PYTHON_DIR = Path(__file__).resolve().parents[1] / "system" / "python"


def load_build_manager():
    path = PYTHON_DIR / "build_manager.py"
    spec = importlib.util.spec_from_file_location("build_manager_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def make_fake_docker(bin_dir: Path) -> Path:
    """Create a `docker` executable that succeeds and echoes its arguments.

    The fake keeps the test hermetic: no Docker daemon or image pulls, while
    still exercising the real subprocess path (`Popen` + `stream_with_deadline`).
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        script = bin_dir / "docker.cmd"
        script.write_text(
            "@echo off\r\n"
            "echo fake-docker build ok\r\n"
            "echo args: %*\r\n"
            "exit /b 0\r\n",
            encoding="utf-8",
        )
        return script

    script = bin_dir / "docker"
    script.write_text(
        "#!/bin/sh\n"
        "echo 'fake-docker build ok'\n"
        "echo \"args: $*\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return script


class TestDockerfileBuildWithoutNixpacks(unittest.TestCase):
    def test_dockerfile_build_succeeds_when_nixpacks_is_absent(self):
        build_manager = load_build_manager()

        # Older branches only have get_nixpacks_binary(); this PR's branch
        # splits out find_nixpacks_binary(). Patch whichever exists so the
        # absence of nixpacks is modelled on every branch.
        lookup_name = (
            "find_nixpacks_binary"
            if hasattr(build_manager, "find_nixpacks_binary")
            else "get_nixpacks_binary"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_dir = root / "project"
            project_dir.mkdir()
            (project_dir / "Dockerfile").write_text(
                "FROM python:3.11-slim\n"
                "WORKDIR /app\n"
                "COPY . .\n"
                'CMD ["python", "-c", "print(\'hi\')"]\n',
                encoding="utf-8",
            )

            fake_docker = make_fake_docker(root / "bin")
            image_name = "vexlyx-nixpacks-absent-test"

            # Docker is available: the fake `docker` is first on PATH, so
            # get_docker_binary()'s `shutil.which("docker")` resolves to it.
            old_path = os.environ.get("PATH", "")
            os.environ["PATH"] = str(fake_docker.parent) + os.pathsep + old_path

            stdout = io.StringIO()
            try:
                with mock.patch.object(
                    build_manager, lookup_name, return_value=None
                ) as nixpacks_lookup, mock.patch.object(
                    build_manager, "get_docker_binary", wraps=build_manager.get_docker_binary
                ) as docker_lookup, redirect_stdout(stdout):
                    try:
                        build_manager.cmd_build(
                            {
                                "projectDir": str(project_dir),
                                "imageName": image_name,
                            }
                        )
                    except SystemExit as exc:
                        self.fail(
                            "Dockerfile build must not depend on nixpacks, but "
                            f"cmd_build() exited with {exc.code}. Output:\n"
                            f"{stdout.getvalue()}"
                        )
            finally:
                os.environ["PATH"] = old_path

            output = stdout.getvalue()
            messages = [
                json.loads(line)
                for line in output.splitlines()
                if line.strip()
            ]
            self.assertTrue(messages, f"cmd_build() produced no output:\n{output}")

            # The nixpacks lookup must never run on the Dockerfile path.
            if nixpacks_lookup.called:
                self.fail(
                    f"cmd_build() resolved {lookup_name}() before the Dockerfile "
                    "branch; a Dockerfile build must not require nixpacks. "
                    f"Output:\n{output}"
                )

            # Log lines are JSON, so parsing them unescapes the backslashes in
            # Windows paths before we assert on them.
            logs = [m["log"] for m in messages if "log" in m]

            # Docker was actually resolved and executed (`shutil.which` may
            # report a different extension case, e.g. docker.CMD).
            docker_lookup.assert_called_once()
            running = [m for m in logs if m.startswith("Running: ")]
            self.assertEqual(len(running), 1, f"Missing docker invocation. Output:\n{output}")
            invocation = running[0][len("Running: "):].lower()
            self.assertIn(str(fake_docker).lower(), invocation)
            self.assertIn("build", invocation)
            self.assertIn(f"-t {image_name}".lower(), invocation)
            self.assertIn("-f", invocation)

            # The Dockerfile branch streamed the docker build and finished.
            self.assertTrue(
                any("Building Docker image from custom Dockerfile" in m for m in logs),
                f"Missing Dockerfile build log. Output:\n{output}",
            )
            self.assertIn("fake-docker build ok", logs)

            self.assertEqual(
                messages[-1],
                {"done": True, "imageName": image_name},
                f"Unexpected final message. Output:\n{output}",
            )


if __name__ == "__main__":
    unittest.main()
