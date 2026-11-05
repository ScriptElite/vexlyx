"""Symlink-safe project file IO (#193).

A project directory is the checkout of whatever repository its owner connected,
and git preserves symlinks. The system-layer scripts below run as root inside a
container that bind-mounts the whole host checkout at the same absolute path,
so a link named `Dockerfile` used to turn `dockerfile-get` into an arbitrary
host-file read and `dockerfile-save` into an arbitrary root-file overwrite. The
same applied to the generated `deploy/docker-compose.yml` and `deploy/nginx.conf`.

These tests drive the real commands and the real generator functions against a
planted link, and pin the two behaviours that must not regress: ordinary files
still round-trip, and a link that stays *inside* the project (a repo sharing one
Dockerfile) is still read.
"""

import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BUILD_MANAGER = REPO_ROOT / "system" / "python" / "build_manager.py"
SECRET_TEXT = "-----BEGIN FAKE PRIVATE KEY----- must never reach the panel\n"
SAVED_DOCKERFILE = "FROM node:20-alpine\nEXPOSE 3000\n"


def _load_docker_manager():
    spec = importlib.util.spec_from_file_location(
        "docker_manager_symlink_safe", REPO_ROOT / "system" / "python" / "docker_manager.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


docker_manager = _load_docker_manager()


def run_build_manager(command: str, payload: dict) -> tuple[int, dict, str]:
    """Invoke build_manager.py the way the API does: JSON payload on stdin."""
    body = {"command": command, **payload}
    proc = subprocess.run(
        [sys.executable, str(BUILD_MANAGER)],
        input=json.dumps(body),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    lines = [line.strip() for line in proc.stdout.strip().splitlines() if line.strip()]
    try:
        parsed = json.loads(lines[-1]) if lines else {}
    except json.JSONDecodeError:
        parsed = {"raw": proc.stdout}
    return proc.returncode, parsed, proc.stderr


def symlinks_supported() -> bool:
    # Windows only allows symlink() with developer rights; CI is Linux.
    try:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.txt"
            source.write_text("x", encoding="utf-8")
            os.symlink(source, Path(tmp) / "link.txt")
            return True
    except (OSError, NotImplementedError):
        return False


CAN_SYMLINK = symlinks_supported()


class DockerfileProjectWorkspace(unittest.TestCase):
    """Shared layout: project/ is the workspace, outside/ stands in for the rest
    of the host mount the panel container can reach."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.project = root / "project"
        self.outside = root / "outside"
        self.project.mkdir()
        self.outside.mkdir()
        self.secret = self.outside / "panel-source.js"
        self.secret.write_text(SECRET_TEXT, encoding="utf-8")

    def plant_escaping_link(self, name: str = "Dockerfile") -> Path:
        link = self.project / name
        os.symlink(self.secret, link)
        return link


@unittest.skipUnless(CAN_SYMLINK, "platform does not allow creating symlinks")
class DockerfileGetTest(DockerfileProjectWorkspace):
    def test_a_link_out_of_the_project_discloses_nothing(self):
        self.plant_escaping_link()
        code, result, stderr = run_build_manager("dockerfile-get", {"projectDir": str(self.project)})
        self.assertEqual(code, 0, stderr)
        self.assertEqual(result["dockerfile"], "")
        # The parsed directives come from the same read, so a link that leaked
        # would show its FROM/EXPOSE here too.
        self.assertIsNone(result["baseImage"])
        self.assertEqual(result["exposedPorts"], [])

    def test_an_ordinary_dockerfile_is_still_read(self):
        (self.project / "Dockerfile").write_text(SAVED_DOCKERFILE, encoding="utf-8")
        code, result, stderr = run_build_manager("dockerfile-get", {"projectDir": str(self.project)})
        self.assertEqual(code, 0, stderr)
        self.assertEqual(result["dockerfile"], SAVED_DOCKERFILE)
        self.assertEqual(result["exposedPorts"], [3000])

    def test_a_link_to_a_file_inside_the_project_is_still_read(self):
        shared = self.project / "docker"
        shared.mkdir()
        (shared / "Dockerfile.prod").write_text(SAVED_DOCKERFILE, encoding="utf-8")
        os.symlink(shared / "Dockerfile.prod", self.project / "Dockerfile")
        code, result, stderr = run_build_manager("dockerfile-get", {"projectDir": str(self.project)})
        self.assertEqual(code, 0, stderr)
        self.assertEqual(result["dockerfile"], SAVED_DOCKERFILE)

    def test_a_linked_dockerignore_out_of_the_project_discloses_nothing(self):
        # Dockerfile stays a regular file here so the command succeeds; the
        # escape under test is the .dockerignore link.
        (self.project / "Dockerfile").write_text(SAVED_DOCKERFILE, encoding="utf-8")
        self.plant_escaping_link(".dockerignore")
        code, result, stderr = run_build_manager("dockerfile-get", {"projectDir": str(self.project)})
        self.assertEqual(code, 0, stderr)
        self.assertEqual(result["dockerignore"], "")
        self.assertEqual(result["dockerfile"], SAVED_DOCKERFILE)


@unittest.skipUnless(CAN_SYMLINK, "platform does not allow creating symlinks")
class DockerfileSaveTest(DockerfileProjectWorkspace):
    def test_saving_refuses_to_write_through_a_link(self):
        link = self.plant_escaping_link()
        code, result, stderr = run_build_manager(
            "dockerfile-save", {"projectDir": str(self.project), "dockerfile": SAVED_DOCKERFILE}
        )
        self.assertEqual(code, 1, stderr)
        self.assertEqual(result["code"], "UNSAFE_DOCKERFILE_LINK")
        self.assertEqual(self.secret.read_text(encoding="utf-8"), SECRET_TEXT)
        self.assertTrue(link.is_symlink())

    def test_saving_an_ordinary_file_still_round_trips(self):
        code, result, stderr = run_build_manager(
            "dockerfile-save",
            {"projectDir": str(self.project), "dockerfile": SAVED_DOCKERFILE, "dockerignore": "node_modules\n"},
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual((self.project / "Dockerfile").read_text(encoding="utf-8"), SAVED_DOCKERFILE)
        self.assertEqual(result["exposedPorts"], [3000])
        code, fetched, stderr = run_build_manager("dockerfile-get", {"projectDir": str(self.project)})
        self.assertEqual(code, 0, stderr)
        self.assertEqual(fetched["dockerignore"], "node_modules\n")

    def test_saving_over_an_existing_file_keeps_its_inode(self):
        target = self.project / "Dockerfile"
        target.write_text("FROM old\n", encoding="utf-8")
        before = target.stat().st_ino
        code, _, stderr = run_build_manager(
            "dockerfile-save", {"projectDir": str(self.project), "dockerfile": SAVED_DOCKERFILE}
        )
        self.assertEqual(code, 0, stderr)
        self.assertEqual(target.stat().st_ino, before)

    def test_saving_through_a_link_named_dockerignore_is_refused(self):
        self.plant_escaping_link(".dockerignore")
        code, result, stderr = run_build_manager(
            "dockerfile-save", {"projectDir": str(self.project), "dockerignore": "secret\n"}
        )
        self.assertEqual(code, 1, stderr)
        self.assertEqual(result["code"], "UNSAFE_DOCKERIGNORE_LINK")
        self.assertEqual(self.secret.read_text(encoding="utf-8"), SECRET_TEXT)


@unittest.skipUnless(CAN_SYMLINK, "platform does not allow creating symlinks")
class GeneratedDeployFileTest(unittest.TestCase):
    TEMPLATES = REPO_ROOT / "system" / "templates" / "docker-compose"
    NGINX_TEMPLATES = REPO_ROOT / "system" / "templates" / "nginx"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.deploy = root / "project" / "deploy"
        self.deploy.mkdir(parents=True)
        self.secret = root / "outside" / "docker-compose.prod.yml"
        self.secret.parent.mkdir(parents=True)
        self.secret.write_text(SECRET_TEXT, encoding="utf-8")

    def render_compose(self):
        docker_manager.generate_compose_file(
            compose_dir=self.deploy,
            template_path=self.TEMPLATES / "node.yml",
            image_name="example:latest",
            service_name="abc123",
            hostname="app.example.test",
            host_port=8100,
            container_port=3000,
            memory_limit="512m",
            env_vars={},
            extra_placeholders={"deploy_dir": self.deploy.resolve().as_posix()},
        )

    def assert_refused(self, generate) -> None:
        """Run a generator that must refuse and pin the code it reported."""
        out = io.StringIO()
        with self.assertRaises(SystemExit), contextlib.redirect_stdout(out):
            generate()
        reported = json.loads(out.getvalue().strip().splitlines()[-1])
        self.assertEqual(reported["code"], "UNSAFE_DEPLOY_FILE")

    def test_compose_generation_refuses_a_linked_target(self):
        os.symlink(self.secret, self.deploy / "docker-compose.yml")
        self.assert_refused(self.render_compose)
        self.assertEqual(self.secret.read_text(encoding="utf-8"), SECRET_TEXT)

    def test_nginx_generation_refuses_a_linked_target(self):
        os.symlink(self.secret, self.deploy / "nginx.conf")
        self.assert_refused(
            lambda: docker_manager.generate_nginx_conf(
                self.deploy, self.NGINX_TEMPLATES / "spa.conf.template"
            )
        )
        self.assertEqual(self.secret.read_text(encoding="utf-8"), SECRET_TEXT)

    def test_regular_generated_files_are_written(self):
        self.render_compose()
        compose = (self.deploy / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("example:latest", compose)
        self.assertNotIn("{{image_name}}", compose)
        self.assertNotIn("{{hostname}}", compose)
        conf = docker_manager.generate_nginx_conf(self.deploy, self.NGINX_TEMPLATES / "spa.conf.template")
        self.assertIn("location", conf.read_text(encoding="utf-8"))

    def test_rewriting_a_generated_file_keeps_its_inode(self):
        # A deployed container bind-mounts deploy/nginx.conf as a single file,
        # so an in-place rewrite must not swap the inode.
        conf = docker_manager.generate_nginx_conf(self.deploy, self.NGINX_TEMPLATES / "spa.conf.template")
        before = conf.stat().st_ino
        docker_manager.generate_nginx_conf(self.deploy, self.NGINX_TEMPLATES / "spa.conf.template")
        self.assertEqual(conf.stat().st_ino, before)


if __name__ == "__main__":
    unittest.main()
