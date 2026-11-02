#!/usr/bin/env python3
"""
docker_manager.py -- System-layer script for Vexlyx Docker container lifecycle.

Called by the API service via child_process.spawn with a JSON payload on stdin.
Writes JSON results to stdout and exits with code 0 on success, 1 on error.

Commands:
  deploy    -- Generate docker-compose.yml for the project then `docker compose up -d`.
               Returns: { containerId, hostPort, hostname }
  start     -- `docker compose start` in the project deploy dir.
  stop      -- `docker compose stop` in the project deploy dir.
  restart   -- `docker compose restart` in the project deploy dir.
  remove    -- `docker compose down --volumes --remove-orphans` in the project deploy dir.
  status    -- Inspect running container and return container status.
  logs      -- `docker compose logs --tail=N` in the project deploy dir.
  system_df -- `docker system df` disk-usage breakdown by category (F5.15).
  cleanup   -- `docker container prune` + `docker image prune -a` (F5.15).
  image_id  -- Resolve the current image ID for a tag, or null (F5.15).
  remove_image -- `docker image rm <id>`, no-ops if the image is in use (F5.15).
  exec      -- Execute a command inside a project's running container (F5.28).
               Returns: { exitCode, output, timedOut, containerId }

Port allocation strategy:
  Each project gets a unique host port derived from a configurable range (default 8100-8999).
  The port is deterministically derived from the project ID hash so re-deploys reuse the same port.
  Users can override via the `hostPort` payload field.

Never run this script as root.
Requires Docker CLI (docker compose v2) to be installed and available in PATH.
"""

import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Stream encoding
# ---------------------------------------------------------------------------

if hasattr(sys.stdin, "reconfigure"):
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def respond(data: dict) -> None:
    print(json.dumps(data), flush=True)


def log_line(message: str) -> None:
    print(json.dumps({"log": message}), flush=True)


def fail(message: str, code: str = "DOCKER_ERROR") -> None:
    print(json.dumps({"error": message, "code": code}), flush=True)
    sys.exit(1)


def require_field(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not value or not isinstance(value, str):
        fail(f"Missing required field: {field}", "INVALID_PAYLOAD")
    return value  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# PHP-FPM docroot ownership (#151)
#
# This script runs as root, so a project directory it (or the API) creates is
# root:root 0755 -- but PHP-FPM in the vexlyx-php-fpm and wordpress images runs
# as www-data, so a self-installing app (a Duplicator migration) cannot create
# files in its own docroot. Deploys hand the directory PHP serves to uid 82.
# apps/api/src/utils/phpRuntimeOwnership.ts defines the same identity for the
# File Manager; a test keeps the two in step.
# ---------------------------------------------------------------------------

PHP_FPM_UID = 82
PHP_FPM_GID = 82

# WordPress keeps only wp-content on the host; these are the folders it writes.
WORDPRESS_WRITABLE_DIRS = ("plugins", "themes", "uploads")


def assert_deploy_dir_is_not_a_symlink(compose_dir: Path) -> None:
    """The deploy/ directory is panel-owned and written to as root. PHP owns
    the project directory around it, so refuse to write through a link that
    application code could have swapped in for it."""
    if compose_dir.is_symlink():
        fail(
            f"{compose_dir} is a symbolic link; refusing to deploy through it",
            "UNSAFE_DEPLOY_DIR",
        )


def _chown_directory_no_follow(path: Path, uid: int, gid: int) -> None:
    # Opening the directory with O_NOFOLLOW and changing the open descriptor
    # means a symlink planted by the application cannot redirect the chown to
    # another path, even between the check and the change.
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fchown(fd, uid, gid)
    finally:
        os.close(fd)


def hand_docroot_to_php(project_dir: Path, project_type: str, php_no_build: bool, chown=None) -> list:
    """Make the directories PHP-FPM writes to owned by its user.

    Non-recursive on purpose: it changes the docroot directory itself (so PHP
    can create, rename and delete entries in it), not the tens of thousands of
    files a migrated site may hold, and never the panel-owned deploy/.
    Idempotent; returns the directories changed. Without root (development) it
    does nothing.
    """
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        if chown is None:
            return []
    apply = chown or _chown_directory_no_follow

    targets = []
    if php_no_build:
        if os.path.lexists(Path(project_dir) / ".git"):
            # A git checkout keeps a root-owned root. The panel runs git as
            # root, and git refuses a repository whose directory another user
            # owns ("dubious ownership"), which would break every pull and
            # auto-deploy. safe.directory is no answer either: with PHP owning
            # the root it could replace .git, whose hooks and config run as
            # root on the next pull. So PHP cannot write to the root of such a
            # site; see docs/dev/no-build-php-hosting.md.
            log_line("[vexlyx] Git-connected project: leaving its root owned by root (PHP cannot write to the site root)")
            return []
        targets.append(Path(project_dir))
    elif project_type.upper() == "WORDPRESS":
        wp_content = Path(project_dir) / "wp-content"
        targets.append(wp_content)
        targets.extend(wp_content / name for name in WORDPRESS_WRITABLE_DIRS)

    changed = []
    for target in targets:
        if target.is_symlink() or not target.is_dir():
            continue
        try:
            apply(target, PHP_FPM_UID, PHP_FPM_GID)
        except OSError as exc:
            log_line(f"[vexlyx] Could not make {target.name} writable for PHP: {exc}")
            continue
        changed.append(target)
    return changed


# ---------------------------------------------------------------------------
# Bounded subprocess execution (#52)
#
# Every external command is time-limited so a hung docker/nixpacks/mysqldump
# cannot wedge a build or deploy forever (the API side only has a backstop
# watchdog; killing this script would orphan the grandchild process, so the
# limit has to be enforced here). Values are seconds.
# ---------------------------------------------------------------------------

QUICK_TIMEOUT = 30        # inspect / ps / network checks
LOGS_TIMEOUT = 60         # one-shot `compose logs`
DF_TIMEOUT = 120          # `docker system df`
PRUNE_TIMEOUT = 600       # container / image prune
COMPOSE_TIMEOUT = 1800    # `compose up/build/down` - image pulls can be slow

def _group_popen_kwargs() -> dict:
    """Run the child in its own process group so the whole tree can be killed."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def kill_process_tree(proc: "subprocess.Popen") -> None:
    """Kill the process and everything it started.

    Killing only the direct child leaves grandchildren (e.g. what nixpacks or
    docker spawn) running and still holding our output pipe open, which would
    keep the deadline from ever being honoured.
    """
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=15,
            )
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def run_bounded(
    timeout: int, cmd: list, *, fatal: bool = True, **kwargs
) -> "subprocess.CompletedProcess":
    """subprocess.run with a hard time limit that also kills the child's tree.

    A timeout normally ends the script with COMMAND_TIMEOUT. Pass fatal=False for
    best-effort cleanup steps: the timeout is logged and a result with return
    code 124 is returned, so the steps after it still run.
    """
    check = kwargs.pop("check", False)
    input_data = kwargs.pop("input", None)
    if kwargs.pop("capture_output", False):
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE
    if input_data is not None:
        kwargs["stdin"] = subprocess.PIPE

    with subprocess.Popen(cmd, **_group_popen_kwargs(), **kwargs) as proc:
        try:
            stdout, stderr = proc.communicate(input_data, timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_process_tree(proc)
            proc.communicate()
            if not fatal:
                log_line(f"[vexlyx] Skipped: `{' '.join(str(c) for c in cmd[:3])}` timed out after {timeout}s")
                return subprocess.CompletedProcess(cmd, 124, "", "timed out")
            fail(
                f"`{' '.join(str(c) for c in cmd[:4])}` timed out after {timeout}s",
                "COMMAND_TIMEOUT",
            )
            raise  # unreachable - fail() exits
        returncode = proc.poll()
    if check and returncode:
        raise subprocess.CalledProcessError(returncode, cmd, stdout, stderr)
    return subprocess.CompletedProcess(cmd, returncode, stdout, stderr)


def stream_with_deadline(proc: "subprocess.Popen", timeout: int, on_line) -> bool:
    """Feed proc.stdout lines to on_line; kill proc if it outlives `timeout`.

    Returns True when the deadline killed the process.
    """
    timed_out = threading.Event()

    def _kill() -> None:
        timed_out.set()
        kill_process_tree(proc)

    timer = threading.Timer(timeout, _kill)
    timer.daemon = True
    timer.start()
    try:
        if proc.stdout:
            for raw_line in proc.stdout:
                on_line(raw_line)
        proc.wait()
    finally:
        timer.cancel()
    return timed_out.is_set()


def get_docker_binary() -> str:
    binary = shutil.which("docker")
    if binary:
        return binary
    fail(
        "Docker CLI not found in PATH. Install Docker Engine or Docker Desktop.",
        "DOCKER_NOT_FOUND",
    )
    return "docker"  # unreachable


# Project containers join APPS_NETWORK (with Traefik and the database servers
# customer databases live on). PANEL_NETWORK carries Redis, the API, the panel
# database, mail and DNS and must never appear in a project's compose file.
APPS_NETWORK = "vexlyx-apps"
PANEL_NETWORK = "traefik-net"


def ensure_network(docker_bin: str, name: str) -> None:
    """Ensure the external bridge network `name` exists in Docker."""
    res = run_bounded(
        QUICK_TIMEOUT,
        [docker_bin, "network", "inspect", name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        log_line(f"[vexlyx] Creating Docker network: {name}")
        run_bounded(
            QUICK_TIMEOUT,
            [docker_bin, "network", "create", name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )


def ensure_apps_network(docker_bin: str) -> None:
    ensure_network(docker_bin, APPS_NETWORK)


def run_compose(
    compose_dir: str,
    args: list[str],
    docker_bin: str,
    capture: bool = False,
) -> subprocess.CompletedProcess[str] | None:
    """Run `docker compose <args>` in compose_dir. Streams stdout if not capture mode."""
    if not Path(compose_dir).is_dir():
        fail(
            f"Compose directory does not exist: {compose_dir}",
            "COMPOSE_DIR_NOT_FOUND",
        )

    cmd = [docker_bin, "compose"] + args
    if capture:
        return run_bounded(
            COMPOSE_TIMEOUT,
            cmd,
            cwd=compose_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    proc = subprocess.Popen(
        cmd,
        **_group_popen_kwargs(),
        cwd=compose_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    def _emit(line: str) -> None:
        stripped = line.rstrip("\r\n")
        if stripped:
            log_line(stripped)

    if stream_with_deadline(proc, COMPOSE_TIMEOUT, _emit):
        fail(
            f"`docker compose {' '.join(args)}` timed out after {COMPOSE_TIMEOUT}s",
            "COMMAND_TIMEOUT",
        )
    if proc.returncode != 0:
        fail(
            f"`docker compose {' '.join(args)}` failed with exit code {proc.returncode}",
            "COMPOSE_NONZERO_EXIT",
        )
    return None


def derive_host_port(project_id: str, port_start: int, port_end: int) -> int:
    """
    Deterministically derive a host port from project_id so re-deploys reuse
    the same port without needing a port database.
    """
    h = int(hashlib.sha256(project_id.encode()).hexdigest(), 16)
    port_range = port_end - port_start + 1
    return port_start + (h % port_range)


def slugify(name: str) -> str:
    """Convert a project name to a Docker-safe service/router name."""
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return re.sub(r"-+", "-", slug).strip("-") or "app"


def get_templates_dir() -> Path:
    """Find the system/templates/docker-compose directory."""
    script_dir = Path(__file__).resolve().parent
    # script is at system/python/docker_manager.py → templates at system/templates/
    candidates = [
        script_dir.parent / "templates" / "docker-compose",
        Path(os.getcwd()) / "system" / "templates" / "docker-compose",
        Path(os.getcwd()) / "../../system" / "templates" / "docker-compose",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    fail(
        "Cannot find system/templates/docker-compose directory.",
        "TEMPLATES_DIR_NOT_FOUND",
    )
    return candidates[0]  # unreachable


def get_nginx_templates_dir() -> Path:
    """Find the system/templates/nginx directory (F5.7)."""
    script_dir = Path(__file__).resolve().parent
    candidates = [
        script_dir.parent / "templates" / "nginx",
        Path(os.getcwd()) / "system" / "templates" / "nginx",
        Path(os.getcwd()) / "../../system" / "templates" / "nginx",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    fail(
        "Cannot find system/templates/nginx directory.",
        "NGINX_TEMPLATES_DIR_NOT_FOUND",
    )
    return candidates[0]  # unreachable


def primary_service_name(project_type: str, compose_dir: str | Path | None = None) -> str:
    """
    Return the Docker Compose service name that fronts HTTP traffic for a
    project type -- used by status/logs/container-id lookups (F5.7).

    Most templates have a single "app" service. WORDPRESS always splits into
    a PHP-FPM "app" service and an nginx "web" service. PHP does too, but
    only for no-build deploys (F5.21) -- a Nixpacks-built PHP project is a
    single "app" container. Since project_type alone can't disambiguate the
    two PHP cases after the fact, inspect the already-generated compose file
    for a top-level "web:" service key when compose_dir is available.
    """
    project_type_upper = project_type.upper()
    if project_type_upper == "WORDPRESS":
        return "web"
    if project_type_upper == "PHP" and compose_dir:
        compose_file = Path(compose_dir) / "docker-compose.yml"
        if compose_file.is_file():
            try:
                content = compose_file.read_text(encoding="utf-8")
            except OSError:
                content = ""
            if re.search(r"(?m)^\s{2}web:\s*$", content):
                return "web"
    return "app"


def pick_template(project_type: str) -> str:
    """Return the template filename for a given project type."""
    mapping = {
        "NODEJS": "node.yml",
        "NEXTJS": "next.yml",
        "PYTHON": "python.yml",
        "REACT": "static.yml",
        "STATIC": "static.yml",
        "PHP": "php.yml",
        "WORDPRESS": "wordpress.yml",
        "DOCKER": "docker.yml",
    }
    return mapping.get(project_type.upper(), "node.yml")


def default_container_port(project_type: str) -> int:
    """Return the expected internal container port for a project type."""
    mapping = {
        "NODEJS": 3000,
        "NEXTJS": 3000,
        "PYTHON": 8000,
        "REACT": 80,
        "STATIC": 80,
        "PHP": 80,
        "WORDPRESS": 80,
        "DOCKER": 3000,
    }
    return mapping.get(project_type.upper(), 3000)


def build_env_block(env_vars: dict[str, str], indent: int = 6) -> str:
    """Format env vars as indented YAML key-value pairs for the compose template."""
    if not env_vars:
        return ""
    pad = " " * indent
    lines = [f"{pad}{k}: {json.dumps(str(v))}" for k, v in env_vars.items()]
    return "\n".join(lines)


def generate_compose_file(
    compose_dir: Path,
    template_path: Path,
    image_name: str,
    service_name: str,
    hostname: str,
    host_port: int,
    container_port: int,
    memory_limit: str,
    env_vars: dict[str, str],
    extra_placeholders: dict[str, str] | None = None,
) -> None:
    template = template_path.read_text(encoding="utf-8")
    env_block = build_env_block(env_vars)
    content = (
        template
        .replace("{{image_name}}", image_name)
        .replace("{{service_name}}", service_name)
        .replace("{{hostname}}", hostname)
        .replace("{{host_port}}", str(host_port))
        .replace("{{container_port}}", str(container_port))
        .replace("{{memory_limit}}", memory_limit)
        .replace("{{env_block}}", env_block)
    )
    for key, value in (extra_placeholders or {}).items():
        content = content.replace(f"{{{{{key}}}}}", value)
    compose_dir.mkdir(parents=True, exist_ok=True)
    (compose_dir / "docker-compose.yml").write_text(content, encoding="utf-8")


def generate_nginx_conf(
    compose_dir: Path,
    template_path: Path,
    placeholders: dict[str, str] | None = None,
) -> Path:
    """Copy a nginx/*.conf.template into the project's deploy dir (F5.7),
    substituting any {{placeholder}} tokens (F5.21 -- needed so each
    project's nginx addresses its own container by its unique name rather
    than the ambiguous, Compose-auto-aliased bare service name; see
    app_upstream in cmd_deploy)."""
    content = render_nginx_conf(template_path, placeholders)
    compose_dir.mkdir(parents=True, exist_ok=True)
    dest = compose_dir / "nginx.conf"
    dest.write_text(content, encoding="utf-8")
    return dest


def render_nginx_conf(template_path: Path, placeholders: dict[str, str] | None = None) -> str:
    content = template_path.read_text(encoding="utf-8")
    for key, value in (placeholders or {}).items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def refresh_nginx_conf_for(project_dir: Path, project_type: str, project_id: str, php_no_build: bool) -> str:
    """Re-render the nginx.conf of an already-deployed site that serves its
    project directory (no-build static/React and no-build PHP), so a template
    change reaches it without a redeploy.

    Rewritten in place -- the container bind-mounts that single file, so it
    must keep its inode -- and only when the content differs. Returns
    "updated", "unchanged" or "skipped" (never deployed, another type, or a
    symlink where a regular file or the deploy directory should be).
    """
    compose_dir = Path(project_dir) / "deploy"
    conf = compose_dir / "nginx.conf"
    if compose_dir.is_symlink() or conf.is_symlink() or not conf.is_file():
        return "skipped"

    project_type = project_type.upper()
    if project_type in ("STATIC", "REACT"):
        template, placeholders = "spa.conf.template", {}
    elif project_type == "PHP" and php_no_build:
        upstream = f"vexlyx-{slugify(project_id[:12])}-app-1"
        template, placeholders = "php.conf.template", {"app_upstream": upstream}
    else:
        return "skipped"

    rendered = render_nginx_conf(get_nginx_templates_dir() / template, placeholders)
    if conf.read_text(encoding="utf-8") == rendered:
        return "unchanged"
    conf.write_text(rendered, encoding="utf-8")
    return "updated"


def compose_has_service(compose_dir: str | Path, service: str) -> bool:
    """True when the project's generated compose file declares `service`."""
    compose_file = Path(compose_dir) / "docker-compose.yml"
    if not compose_file.is_file():
        return False
    try:
        content = compose_file.read_text(encoding="utf-8")
    except OSError:
        return False
    return re.search(r"(?m)^\s{2}%s:\s*$" % re.escape(service), content) is not None


def service_container_id(compose_dir: str, docker_bin: str, service: str) -> str | None:
    """Return the short container ID of a named Compose service, or None."""
    if not Path(compose_dir).is_dir() or not (Path(compose_dir) / "docker-compose.yml").is_file():
        return None

    result = run_bounded(
        QUICK_TIMEOUT,
        [docker_bin, "compose", "ps", "-q", service],
        cwd=compose_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    container_id = result.stdout.strip()
    return container_id if container_id else None


def get_container_id(compose_dir: str, docker_bin: str, project_type: str = "NODEJS") -> str | None:
    """Return the short container ID of the primary (Traefik-facing) service, or None."""
    return service_container_id(
        compose_dir,
        docker_bin,
        primary_service_name(project_type, compose_dir),
    )


# Every compose template names the service that runs application code "app".
APP_SERVICE_NAME = "app"


def app_container_id(compose_dir: str, docker_bin: str, project_type: str = "NODEJS") -> str | None:
    """
    Return the short container ID of the *application* service (F5.28).

    Exec must not reuse the HTTP-facing lookup: WORDPRESS and no-build PHP
    front a PHP-FPM "app" service with an nginx "web" service, so a command
    like `php wp-cron.php` would otherwise be handed to nginx and fail. Falls
    back to the HTTP-facing container only for a compose file that declares
    no "app" service at all.
    """
    if compose_has_service(compose_dir, APP_SERVICE_NAME):
        return service_container_id(compose_dir, docker_bin, APP_SERVICE_NAME)
    return get_container_id(compose_dir, docker_bin, project_type)


# ---------------------------------------------------------------------------
# Post-deploy routable reachability check (#202)
# ---------------------------------------------------------------------------

ROUTABLE_PROBE_ATTEMPTS = 3
ROUTABLE_PROBE_TIMEOUT_SECONDS = 3.0
ROUTABLE_PROBE_RETRY_DELAY_SECONDS = 1.5


def container_routable_ip(docker_bin: str, container_id: str) -> str | None:
    """The address Traefik connects to: this container's IP on APPS_NETWORK."""
    if not container_id:
        return None
    result = run_bounded(
        QUICK_TIMEOUT,
        [
            docker_bin,
            "inspect",
            "--format",
            "{{json .NetworkSettings.Networks}}",
            container_id,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    try:
        attachment = json.loads(result.stdout or "{}").get(APPS_NETWORK) or {}
    except (json.JSONDecodeError, AttributeError):
        return None
    return (attachment.get("IPAddress") or "").strip() or None


def container_declares_healthcheck(docker_bin: str, container_id: str) -> bool:
    """True when the image ships a HEALTHCHECK, in which case Docker is already
    grading the container and the panel's health badge (#202) reports the verdict."""
    if not container_id:
        return False
    result = run_bounded(
        QUICK_TIMEOUT,
        [
            docker_bin,
            "inspect",
            "--format",
            "{{if .Config.Healthcheck}}1{{else}}0{{end}}",
            container_id,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode == 0 and result.stdout.strip() == "1"


def port_is_listening(address: str, port: int, timeout: float) -> bool:
    """One TCP connect attempt. Nothing inside the image is required, which is
    what makes this usable on a Dockerfile project's arbitrary base image."""
    try:
        with socket.create_connection((address, port), timeout):
            return True
    except OSError:
        return False


def probe_routable_listen(
    docker_bin: str, container_id: str, port: int
) -> tuple[str | None, bool | None]:
    """
    Ask the same question the router asks, from the host.

    A loopback-only bind answers `127.0.0.1` and nothing on this address, which
    is the 502-while-the-container-runs case #202 is about. Retries cover an app
    that is still binding the port when the container first comes up.

    Returns (address, reachable), or (None, None) when the container has no
    APPS_NETWORK address to probe.
    """
    address = container_routable_ip(docker_bin, container_id)
    if not address:
        return None, None
    for attempt in range(ROUTABLE_PROBE_ATTEMPTS):
        if port_is_listening(address, port, ROUTABLE_PROBE_TIMEOUT_SECONDS):
            return address, True
        if attempt + 1 < ROUTABLE_PROBE_ATTEMPTS:
            time.sleep(ROUTABLE_PROBE_RETRY_DELAY_SECONDS)
    return address, False


def routable_check_log(
    address: str | None, reachable: bool | None, port: int, hostname: str
) -> str:
    if address is None:
        return f"Routable check skipped: container is not attached to {APPS_NETWORK}"
    if reachable:
        return f"Routable check {address}:{port} answered — Traefik can reach this container"
    return (
        f"WARNING: nothing answers on {address}:{port}, the address Traefik connects to, so "
        f"{hostname} returns 502 even though the container is running. The app is most likely "
        "bound to 127.0.0.1; bind it to $HOSTNAME or 0.0.0.0 instead."
    )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_deploy(payload: dict) -> None:
    """
    Generate a docker-compose.yml for the project and start the container.

    Required payload fields:
      projectId    -- project database ID
      projectName  -- project name (used for hostname slug)
      projectDir   -- absolute path to the deploy directory
      imageName    -- Docker image name built by Nixpacks (F1.4)
      projectType  -- e.g. NODEJS, PYTHON, STATIC
      baseDomain   -- base domain for Traefik hostname (e.g. vexlyx.localhost)
      memoryLimit  -- Docker memory limit (e.g. 128m)
      portRangeStart -- start of host-port range
      portRangeEnd   -- end of host-port range

    Optional payload fields:
      hostPort     -- override dynamic port assignment
      containerPort -- override default container port
      domain       -- fully custom hostname override
      envVars      -- dict of env var key->value to inject
      staticRoot   -- (STATIC/REACT, F5.7) host dir to bind-mount as the nginx webroot;
                      defaults to projectDir when omitted (no-build case)

    Returns: { containerId, hostPort, hostname }
    """
    project_id = require_field(payload, "projectId")
    project_name = require_field(payload, "projectName")
    project_dir = require_field(payload, "projectDir")
    image_name = require_field(payload, "imageName")
    project_type = payload.get("projectType", "NODEJS")
    base_domain = payload.get("baseDomain", "vexlyx.localhost")
    memory_limit = payload.get("memoryLimit", "512m")
    port_start = int(payload.get("portRangeStart", 8100))
    port_end = int(payload.get("portRangeEnd", 8999))
    env_vars: dict[str, str] = payload.get("envVars", {})
    docker_bin = get_docker_binary()

    # Ensure network exists
    ensure_apps_network(docker_bin)

    # Resolve ports
    host_port = int(payload["hostPort"]) if payload.get("hostPort") else derive_host_port(project_id, port_start, port_end)
    container_port = int(payload["containerPort"]) if payload.get("containerPort") else default_container_port(project_type)

    # Resolve hostname
    slug = slugify(project_name)
    hostname = payload.get("domain") or f"{slug}.{base_domain}"

    # Sanitize service name (Traefik router names must be alphanumeric + hyphens)
    service_name = slugify(project_id[:12])

    # F5.21 fix: Compose auto-aliases a service by its bare name ("app") on
    # every network it joins, including the shared external vexlyx-apps --
    # so with 2+ two-container (app+web) projects deployed at once, "app"
    # resolves ambiguously and nginx can randomly proxy PHP requests to a
    # DIFFERENT project's php-fpm container. Confirmed live: two no-build PHP
    # deploys on the same host caused requests to alternate between the two
    # projects' "app" containers. Compose's default container-naming scheme
    # (<compose-project-name>-<service>-<replica>) is unique per project, so
    # nginx must address that instead of the bare service name.
    app_upstream = f"vexlyx-{service_name}-app-1"

    # Resolve template
    templates_dir = get_templates_dir()
    template_file = templates_dir / pick_template(project_type)
    if not template_file.is_file():
        fail(f"Template not found: {template_file}", "TEMPLATE_NOT_FOUND")

    compose_dir = Path(project_dir) / "deploy"
    assert_deploy_dir_is_not_a_symlink(compose_dir)
    extra_placeholders: dict[str, str] = {}
    project_type_upper = project_type.upper()
    extra_placeholders["deploy_dir"] = compose_dir.resolve().as_posix()

    # F5.7 — STATIC/REACT: bind-mount content + generate SPA-fallback nginx config
    if project_type_upper in ("STATIC", "REACT"):
        static_root = payload.get("staticRoot") or project_dir
        extra_placeholders["static_root"] = Path(static_root).resolve().as_posix()
        nginx_conf_path = generate_nginx_conf(
            compose_dir, get_nginx_templates_dir() / "spa.conf.template"
        )
        extra_placeholders["nginx_conf_path"] = nginx_conf_path.resolve().as_posix()

    # F5.7 — WORDPRESS: generate fastcgi nginx config + map DB_* env vars to WORDPRESS_DB_*
    if project_type_upper == "WORDPRESS":
        nginx_conf_path = generate_nginx_conf(
            compose_dir,
            get_nginx_templates_dir() / "wordpress.conf.template",
            {"app_upstream": app_upstream},
        )
        extra_placeholders["nginx_conf_path"] = nginx_conf_path.resolve().as_posix()
        extra_placeholders["wp_db_host"] = env_vars.get("DB_HOST", "")
        extra_placeholders["wp_db_name"] = env_vars.get("DB_NAME", "")
        extra_placeholders["wp_db_user"] = env_vars.get("DB_USER", "")
        extra_placeholders["wp_db_password"] = env_vars.get("DB_PASSWORD", "")
        extra_placeholders["wp_db_prefix"] = env_vars.get("DB_PREFIX", "wp_")

    # F5.21 — PHP with no composer.json/buildCmd: the API service signals this
    # by passing staticRoot (same convention as STATIC/REACT no-build) instead
    # of leaving it unset for a Nixpacks-built PHP deploy. Swap in the
    # two-container php-no-build.yml template + a generic PHP-FPM nginx config.
    php_no_build = project_type_upper == "PHP" and bool(payload.get("staticRoot"))
    if php_no_build:
        template_file = templates_dir / "php-no-build.yml"
        if not template_file.is_file():
            fail(f"Template not found: {template_file}", "TEMPLATE_NOT_FOUND")
        php_root = payload.get("staticRoot") or project_dir
        extra_placeholders["php_root"] = Path(php_root).resolve().as_posix()
        extra_placeholders["php_fpm_image"] = payload.get("phpFpmImage") or "vexlyx-php-fpm:8.3"
        nginx_conf_path = generate_nginx_conf(
            compose_dir,
            get_nginx_templates_dir() / "php.conf.template",
            {"app_upstream": app_upstream},
        )
        extra_placeholders["nginx_conf_path"] = nginx_conf_path.resolve().as_posix()

    for handed_over in hand_docroot_to_php(Path(project_dir), project_type_upper, php_no_build):
        log_line(f"[vexlyx] {handed_over.name} is now writable by PHP-FPM (uid {PHP_FPM_UID})")

    log_line(f"[vexlyx] Generating docker-compose.yml in {compose_dir}")
    generate_compose_file(
        compose_dir=compose_dir,
        template_path=template_file,
        image_name=image_name,
        service_name=service_name,
        hostname=hostname,
        host_port=host_port,
        container_port=container_port,
        memory_limit=memory_limit,
        env_vars=env_vars,
        extra_placeholders=extra_placeholders,
    )

    log_line(f"[vexlyx] Starting container: image={image_name} port={host_port} hostname={hostname}")
    # --pull missing: reuse local Nixpacks-built images as-is, but still fetch fixed
    # images (nginx:alpine, wordpress:php8.3-fpm-alpine) on their first deploy.
    run_compose(str(compose_dir), ["up", "-d", "--force-recreate", "--pull", "missing"], docker_bin)

    # Retrieve the container ID
    container_id = get_container_id(str(compose_dir), docker_bin, project_type) or ""
    log_line(f"[vexlyx] Container started: id={container_id[:12] if container_id else 'unknown'}")

    # An image that declares no HEALTHCHECK leaves Docker with nothing to grade, so
    # a container that binds only 127.0.0.1 deploys as a silent 502. Probe the
    # address the router uses instead, and say so in the log the user reads (#202).
    if container_id and not container_declares_healthcheck(docker_bin, container_id):
        address, reachable = probe_routable_listen(docker_bin, container_id, container_port)
        log_line(f"[vexlyx] {routable_check_log(address, reachable, container_port, hostname)}")

    respond({
        "done": True,
        "containerId": container_id,
        "hostPort": host_port,
        "hostname": hostname,
    })


def cmd_start(payload: dict) -> None:
    project_dir = require_field(payload, "projectDir")
    docker_bin = get_docker_binary()
    compose_dir = str(Path(project_dir) / "deploy")
    if not Path(compose_dir).is_dir():
        fail(f"Deploy directory not found: {compose_dir}", "NOT_DEPLOYED")
    log_line("[vexlyx] Starting container…")
    run_compose(compose_dir, ["start"], docker_bin)
    respond({"done": True})


def cmd_stop(payload: dict) -> None:
    project_dir = require_field(payload, "projectDir")
    docker_bin = get_docker_binary()
    compose_dir = str(Path(project_dir) / "deploy")
    if not Path(compose_dir).is_dir():
        fail(f"Deploy directory not found: {compose_dir}", "NOT_DEPLOYED")
    log_line("[vexlyx] Stopping container…")
    run_compose(compose_dir, ["stop"], docker_bin)
    # Verify every service, including sidecars, before a caller can overwrite files.
    try:
        containers = subprocess.run(
            [docker_bin, "compose", "ps", "--all", "--quiet"],
            cwd=compose_dir, capture_output=True, text=True, timeout=30,
        )
        if containers.returncode != 0:
            fail("Could not list containers after stop", "CONTAINER_STOP_UNCONFIRMED")
        container_ids = containers.stdout.split()
        if container_ids:
            states = subprocess.run(
                [docker_bin, "inspect", "--type", "container", "--format", "{{.State.Status}}", *container_ids],
                capture_output=True, text=True, timeout=30,
            )
            statuses = states.stdout.split()
            if (states.returncode != 0 or len(statuses) != len(container_ids)
                    or any(status not in ("exited", "created", "dead") for status in statuses)):
                fail("Containers are not confirmed stopped", "CONTAINER_STOP_UNCONFIRMED")
    except (OSError, subprocess.TimeoutExpired):
        fail("Could not verify stopped containers", "CONTAINER_STOP_UNCONFIRMED")
    respond({"done": True})


# States in which a container may still be writing to its volumes/bind mounts.
ACTIVE_CONTAINER_STATES = ("running", "restarting", "paused")


def list_project_containers(docker_bin: str, compose_project: str) -> list[tuple[str, str]]:
    """(id, state) of every container of a compose project, found by label."""
    result = subprocess.run(
        [
            docker_bin, "ps", "--all",
            "--filter", f"label=com.docker.compose.project={compose_project}",
            "--format", "{{.ID}} {{.State}}",
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        fail("Could not list project containers", "CONTAINER_STOP_UNCONFIRMED")
    containers = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            containers.append((parts[0], parts[1].lower()))
    return containers


def cmd_stop_by_project(payload: dict) -> None:
    """
    Stop every container of a project by its identity, without needing the
    project workspace directory (it may already have been removed while a
    container survived a failed teardown). Verifies nothing is left running.
    """
    project_id = require_field(payload, "projectId")
    docker_bin = get_docker_binary()
    compose_project = f"vexlyx-{slugify(project_id[:12])}"

    try:
        containers = list_project_containers(docker_bin, compose_project)
        active = [cid for cid, state in containers if state in ACTIVE_CONTAINER_STATES]
        if active:
            log_line(f"[vexlyx] Stopping {len(active)} container(s) of {compose_project}…")
            stopped = subprocess.run(
                [docker_bin, "stop", *active],
                capture_output=True, text=True, timeout=120,
            )
            if stopped.returncode != 0:
                fail("Could not stop project containers", "CONTAINER_STOP_UNCONFIRMED")
            still_active = [
                cid for cid, state in list_project_containers(docker_bin, compose_project)
                if state in ACTIVE_CONTAINER_STATES
            ]
            if still_active:
                fail("Containers are not confirmed stopped", "CONTAINER_STOP_UNCONFIRMED")
    except (OSError, subprocess.TimeoutExpired):
        fail("Could not verify stopped containers", "CONTAINER_STOP_UNCONFIRMED")
    respond({"done": True})


def cmd_restart(payload: dict) -> None:
    project_dir = require_field(payload, "projectDir")
    docker_bin = get_docker_binary()
    compose_dir = str(Path(project_dir) / "deploy")
    if not Path(compose_dir).is_dir():
        fail(f"Deploy directory not found: {compose_dir}", "NOT_DEPLOYED")
    log_line("[vexlyx] Restarting container…")
    run_compose(compose_dir, ["restart"], docker_bin)
    respond({"done": True})


def cmd_remove(payload: dict) -> None:
    project_dir = require_field(payload, "projectDir")
    docker_bin = get_docker_binary()
    compose_dir = str(Path(project_dir) / "deploy")
    if not Path(compose_dir).is_dir():
        respond({"done": True})
        return
    log_line("[vexlyx] Removing container (down --volumes --remove-orphans)…")
    run_compose(compose_dir, ["down", "--volumes", "--remove-orphans"], docker_bin)
    respond({"done": True})


def cmd_status(payload: dict) -> None:
    project_dir = require_field(payload, "projectDir")
    project_type = payload.get("projectType", "NODEJS")
    docker_bin = get_docker_binary()
    compose_dir = str(Path(project_dir) / "deploy")

    if not Path(compose_dir).is_dir():
        respond({"containerStatus": "not_found", "containerHealth": None, "containerId": None})
        return

    container_id = get_container_id(compose_dir, docker_bin, project_type)
    if not container_id:
        respond({"containerStatus": "not_found", "containerHealth": None, "containerId": None})
        return

    # Both fields in one inspect: .State.Status alone calls a failing-healthcheck
    # container a healthy deployment (#202).
    result = run_bounded(
        QUICK_TIMEOUT,
        [
            docker_bin,
            "inspect",
            "--format",
            "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}",
            container_id,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        respond({"containerStatus": "unknown", "containerHealth": None, "containerId": container_id})
        return

    status, _, health = result.stdout.strip().partition("|")
    respond(
        {
            "containerStatus": status.strip() or "unknown",
            # An empty health means the image has no HEALTHCHECK, not that a probe failed.
            "containerHealth": health.strip() or None,
            "containerId": container_id,
        }
    )


def cmd_logs(payload: dict) -> None:
    project_dir = require_field(payload, "projectDir")
    project_type = payload.get("projectType", "NODEJS")
    tail = int(payload.get("tail", 100))
    docker_bin = get_docker_binary()
    compose_dir = str(Path(project_dir) / "deploy")

    if not Path(compose_dir).is_dir():
        respond({"logs": "No runtime logs available. Container has not been deployed yet."})
        return

    result = run_bounded(
        LOGS_TIMEOUT,
        [docker_bin, "compose", "logs", f"--tail={tail}", "--no-log-prefix", primary_service_name(project_type, compose_dir)],
        cwd=compose_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0 and not result.stdout.strip() and not result.stderr.strip():
        respond({"logs": "No runtime logs available."})
        return

    respond({"logs": result.stdout.strip() or result.stderr.strip()})


def parse_docker_size(text: str) -> int:
    """
    Parse a Docker human-readable size string (e.g. "1.2GB", "512kB", "0B")
    into bytes. Docker formats `system df` sizes with decimal (1000-based)
    units via go-units, so we mirror that here rather than using 1024-based
    binary units.
    """
    text = text.strip()
    if not text or text == "N/A":
        return 0
    match = re.match(r"^([\d.]+)\s*([a-zA-Z]*)$", text)
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {
        "B": 1,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
    }
    return int(value * multipliers.get(unit, 1))


def cmd_system_df(payload: dict) -> None:
    """
    Disk-usage breakdown by category (F5.15), via `docker system df`.

    Returns: { categories: [{ type, total, active, sizeBytes, reclaimableBytes }] }
    """
    docker_bin = get_docker_binary()
    result = run_bounded(
        DF_TIMEOUT,
        [docker_bin, "system", "df", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        fail(
            f"`docker system df` failed: {result.stderr.strip()}",
            "SYSTEM_DF_FAILED",
        )
        return

    categories = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        # Reclaimable is formatted as "1.2GB (85%)" -- take the size part only.
        reclaimable_raw = row.get("Reclaimable", "0B").split(" ")[0]
        categories.append({
            "type": row.get("Type", "unknown"),
            "total": int(row.get("TotalCount", 0) or 0),
            "active": int(row.get("Active", 0) or 0),
            "sizeBytes": parse_docker_size(row.get("Size", "0B")),
            "reclaimableBytes": parse_docker_size(reclaimable_raw),
        })

    respond({"categories": categories})


def cmd_cleanup(payload: dict) -> None:
    """
    Reclaim disk space (F5.15): `docker container prune` then
    `docker image prune -a`. Never touches volumes or build cache, and never
    removes an image/container currently in use -- Docker's own prune
    semantics already guarantee that.

    Returns: { done, containersRemoved, imagesRemoved, reclaimedBytes }
    """
    docker_bin = get_docker_binary()

    log_line("[vexlyx] Pruning stopped containers…")
    container_result = run_bounded(
        PRUNE_TIMEOUT,
        [docker_bin, "container", "prune", "-f"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if container_result.returncode != 0:
        fail(
            f"`docker container prune` failed: {container_result.stderr.strip()}",
            "CONTAINER_PRUNE_FAILED",
        )
        return

    log_line("[vexlyx] Pruning unused images…")
    image_result = run_bounded(
        PRUNE_TIMEOUT,
        [docker_bin, "image", "prune", "-a", "-f"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if image_result.returncode != 0:
        fail(
            f"`docker image prune` failed: {image_result.stderr.strip()}",
            "IMAGE_PRUNE_FAILED",
        )
        return

    containers_removed = len(re.findall(r"^[0-9a-f]{12,64}$", container_result.stdout, re.MULTILINE))
    images_removed = len(re.findall(r"^deleted:", image_result.stdout, re.MULTILINE | re.IGNORECASE))

    def extract_reclaimed(text: str) -> int:
        match = re.search(r"Total reclaimed space:\s*(.+)", text)
        return parse_docker_size(match.group(1)) if match else 0

    reclaimed_bytes = extract_reclaimed(container_result.stdout) + extract_reclaimed(image_result.stdout)

    log_line(f"[vexlyx] Cleanup complete — reclaimed {reclaimed_bytes} bytes")
    respond({
        "done": True,
        "containersRemoved": containers_removed,
        "imagesRemoved": images_removed,
        "reclaimedBytes": reclaimed_bytes,
    })


def cmd_image_id(payload: dict) -> None:
    """Resolve the current image ID for a tag (F5.15). Returns { imageId } or { imageId: None }."""
    image_name = require_field(payload, "imageName")
    docker_bin = get_docker_binary()
    result = run_bounded(
        QUICK_TIMEOUT,
        [docker_bin, "image", "inspect", "--format", "{{.Id}}", image_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    respond({"imageId": result.stdout.strip() if result.returncode == 0 else None})


def cmd_remove_image(payload: dict) -> None:
    """
    Remove a single image by ID (F5.15), used after a redeploy is confirmed
    healthy. No `-f`: if the image is still referenced by any container
    (including the just-replaced one, briefly, or an unrelated project
    sharing a base image), Docker refuses and we treat that as a no-op
    rather than an error -- that refusal *is* the "never remove an image in
    use" safety guarantee.

    Returns: { done: true, removed: bool }
    """
    image_id = require_field(payload, "imageId")
    docker_bin = get_docker_binary()
    result = run_bounded(
        PRUNE_TIMEOUT,
        [docker_bin, "image", "rm", image_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        log_line(f"[vexlyx] Skipped removing image {image_id[:19]} (still in use)")
        respond({"done": True, "removed": False})
        return

    respond({"done": True, "removed": True})


def cmd_logs_follow(payload: dict) -> None:
    project_dir = require_field(payload, "projectDir")
    project_type = payload.get("projectType", "NODEJS")
    tail = int(payload.get("tail", 100))
    docker_bin = get_docker_binary()
    compose_dir = str(Path(project_dir) / "deploy")

    if not Path(compose_dir).is_dir():
        fail("No runtime logs available. Container has not been deployed yet.", "DEPLOY_DIR_NOT_FOUND")
        return

    proc = subprocess.Popen(
        [docker_bin, "compose", "logs", "--follow", f"--tail={tail}", "--no-log-prefix", primary_service_name(project_type, compose_dir)],
        cwd=compose_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    try:
        if proc.stdout:
            for line in iter(proc.stdout.readline, ""):
                text = line.rstrip("\r\n")
                if text:
                    print(json.dumps({"log": text, "stream": "stdout"}), flush=True)
    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


# --- F5.28 exec tuning -------------------------------------------------------
# Env marker stamped on every task exec; children inherit it, which is how a
# timed-out command is located and stopped inside the container.
EXEC_TASK_ENV = "VEXLYX_TASK_ID"
# Read granularity for exec output — bounded so a noisy command cannot make the
# host-side Python process buffer unbounded output in memory.
READ_CHUNK_BYTES = 64 * 1024
# Seconds the in-container kill gets before the local docker exec is dropped.
KILL_GRACE_SECONDS = 10


def cmd_exec(payload: dict) -> None:
    """
    Execute a command inside a project's running container (F5.28).

    Required payload fields:
      projectDir  -- absolute path to the deploy directory
      projectType -- e.g. NODEJS, PYTHON, STATIC
      shellCommand -- command string to execute
      timeout     -- hard timeout in seconds (1-3600)
      outputLimit -- max output bytes to capture (default 65536)

    Returns: { exitCode, output, timedOut, containerId }
    """
    project_dir = require_field(payload, "projectDir")
    project_type = payload.get("projectType", "NODEJS")
    command = require_field(payload, "shellCommand")
    timeout = int(payload.get("timeout", 300))
    output_limit = int(payload.get("outputLimit", 65536))

    if timeout < 1 or timeout > 3600:
        fail("Timeout must be between 1 and 3600 seconds", "INVALID_TIMEOUT")

    docker_bin = get_docker_binary()
    compose_dir = str(Path(project_dir) / "deploy")

    if not Path(compose_dir).is_dir() or not (Path(compose_dir) / "docker-compose.yml").is_file():
        fail("Project not deployed (no compose directory)", "NOT_DEPLOYED")

    # The *application* container, not the HTTP-facing one: WORDPRESS and
    # no-build PHP front their PHP-FPM service with nginx, which cannot run
    # the project's commands.
    container_id = app_container_id(compose_dir, docker_bin, project_type)
    if not container_id:
        fail("No running container found for this project", "NO_CONTAINER")

    # Unique marker for this exec's process tree. Children inherit their
    # environment, so on timeout we can find and stop the command *inside* the
    # container — killing only the local `docker exec` client would leave the
    # command running while its run row is already marked TIMEOUT.
    task_marker = os.urandom(16).hex()

    # Use sh -c to support shell features; command is passed as argv[2] (not interpolated)
    cmd = [docker_bin, "exec", "-e", f"{EXEC_TASK_ENV}={task_marker}", container_id, "sh", "-c", command]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except Exception as e:
        fail(f"Failed to start docker exec: {e}", "EXEC_SPAWN_ERROR")

    # Captured output, hard-capped at output_limit bytes.
    output = bytearray()
    timed_out = False

    def kill_in_container() -> None:
        """TERM then KILL every process carrying this exec's env marker."""
        kill_script = (
            'pids="";'
            "for p in /proc/[0-9]*; do "
            'if tr "\\0" "\\n" < "$p/environ" 2>/dev/null | grep -qx "%s=%s"; then '
            'pids="$pids ${p#/proc/}"; fi; done; '
            "for pid in $pids; do kill -TERM $pid 2>/dev/null; done; "
            "sleep 1; "
            "for pid in $pids; do kill -KILL $pid 2>/dev/null; done"
        ) % (EXEC_TASK_ENV, task_marker)
        try:
            subprocess.run(
                [docker_bin, "exec", container_id, "sh", "-c", kill_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=KILL_GRACE_SECONDS + 10,
            )
        except Exception as e:
            print(f"docker exec timeout-kill failed: {e}", file=sys.stderr, flush=True)

    def on_deadline() -> None:
        nonlocal timed_out
        timed_out = True
        # Stop the command inside the container first, then drop the local
        # client so the read loop below gets EOF (the deadline stays armed
        # until the command has actually stopped).
        kill_in_container()
        try:
            proc.terminate()
        except Exception:
            pass

    timer = threading.Timer(timeout, on_deadline)
    timer.start()

    try:
        if proc.stdout:
            while True:
                try:
                    # Fixed-size chunked reads: a command like
                    # `head -c 1000000000 /dev/zero` must never be buffered
                    # whole, only its first output_limit bytes are kept.
                    chunk = proc.stdout.read1(READ_CHUNK_BYTES)
                except (OSError, ValueError):
                    break  # pipe torn down
                if not chunk:
                    break  # EOF — the exec client is gone, the command stopped
                room = output_limit - len(output)
                if room > 0:
                    output.extend(chunk[: min(room, len(chunk))])
                # Beyond the cap the stream keeps being drained and dropped,
                # so the deadline still fires for a loud command that sleeps.
    finally:
        timer.cancel()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=5)
            except Exception:
                pass

    exit_code = proc.returncode

    respond({
        "exitCode": exit_code,
        "output": output.decode("utf-8", errors="replace").rstrip("\n"),
        "timedOut": timed_out,
        "containerId": container_id,
    })


def cmd_refresh_nginx_conf(payload: dict) -> None:
    """Re-render a deployed site's nginx.conf from the current template and,
    if it changed and the site is running, reload nginx (which keeps serving
    the old config if the new one fails its own test).

    Payload: projectDir, projectType, projectId, phpNoBuild.
    """
    project_dir = require_field(payload, "projectDir")
    project_type = require_field(payload, "projectType")
    project_id = require_field(payload, "projectId")
    php_no_build = bool(payload.get("phpNoBuild"))

    outcome = refresh_nginx_conf_for(Path(project_dir), project_type, project_id, php_no_build)
    reloaded = False
    if outcome == "updated":
        docker_bin = get_docker_binary()
        compose_dir = str(Path(project_dir) / "deploy")
        service = "web" if project_type.upper() == "PHP" else "app"
        container_id = service_container_id(compose_dir, docker_bin, service)
        if container_id:
            result = run_bounded(
                QUICK_TIMEOUT,
                [docker_bin, "exec", container_id, "nginx", "-s", "reload"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            reloaded = result.returncode == 0
            if not reloaded:
                log_line(f"[vexlyx] nginx reload failed: {(result.stderr or '').strip()[:200]}")
    log_line(f"[vexlyx] nginx.conf {outcome}" + (", nginx reloaded" if reloaded else ""))
    respond({"done": True, "outcome": outcome, "reloaded": reloaded})


# ---------------------------------------------------------------------------
# Moving already-deployed projects onto the apps network
# ---------------------------------------------------------------------------

PANEL_NETWORK_NAME_LINE = re.compile(
    r"^(\s+name:\s*[\"']?)" + re.escape(PANEL_NETWORK) + r"([\"']?\s*)$", re.MULTILINE
)


def rewrite_compose_network(compose_file: Path) -> bool:
    """Point a generated compose file's external network at APPS_NETWORK.

    Returns True when the file changed. Only the `name:` line of the external
    network is touched, so everything else in the file stays as deployed.
    """
    # Read bytes so a CRLF file keeps its line endings.
    original = compose_file.read_bytes().decode("utf-8")
    updated = PANEL_NETWORK_NAME_LINE.sub(lambda m: m.group(1) + APPS_NETWORK + m.group(2), original)
    if updated == original:
        return False
    # A temp file in the same directory plus os.replace keeps a crash from
    # leaving a half-written compose file behind.
    fd, tmp_name = tempfile.mkstemp(dir=compose_file.parent, prefix=".compose-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
        os.replace(tmp_name, compose_file)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return True


def container_networks(docker_bin: str, container_id: str) -> dict[str, list[str]]:
    """Map of network name -> aliases for one container."""
    res = run_bounded(
        QUICK_TIMEOUT,
        [docker_bin, "inspect", "--format", "{{json .NetworkSettings.Networks}}", container_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        fail(f"Could not inspect container {container_id}", "NETWORK_INSPECT_FAILED")
    attached = json.loads(res.stdout.strip() or "{}")
    return {name: list((info or {}).get("Aliases") or []) for name, info in attached.items()}


def move_container_to_apps_network(docker_bin: str, container_id: str) -> str:
    """Attach a container to APPS_NETWORK and detach it from PANEL_NETWORK.

    Works on running and stopped containers alike without restarting either
    (a stopped container keeps the move and comes back on the new network).
    The container is connected to the new network before it leaves the old
    one, so it is never unreachable. Returns "moved" or "unchanged".
    """
    networks = container_networks(docker_bin, container_id)
    if PANEL_NETWORK not in networks:
        return "unchanged"

    if APPS_NETWORK not in networks:
        command = [docker_bin, "network", "connect"]
        for alias in networks[PANEL_NETWORK]:
            # Docker adds the short container id as an alias by itself.
            if not container_id.startswith(alias):
                command += ["--alias", alias]
        command += [APPS_NETWORK, container_id]
        connected = run_bounded(
            QUICK_TIMEOUT, command, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        if connected.returncode != 0:
            fail(
                f"Could not connect {container_id} to {APPS_NETWORK}: {(connected.stderr or '').strip()[:200]}",
                "NETWORK_CONNECT_FAILED",
            )

    detached = run_bounded(
        QUICK_TIMEOUT,
        [docker_bin, "network", "disconnect", PANEL_NETWORK, container_id],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if detached.returncode != 0:
        fail(
            f"Could not disconnect {container_id} from {PANEL_NETWORK}: {(detached.stderr or '').strip()[:200]}",
            "NETWORK_DISCONNECT_FAILED",
        )
    return "moved"


def reload_running_web_containers(docker_bin: str, compose_project: str) -> int:
    """Make each running nginx "web" container of a project re-resolve its upstream.

    nginx resolves `fastcgi_pass <app container>` once, at startup. After the
    app container changes network it has a new address, and nginx keeps
    sending PHP requests to the old one until it is reloaded. Stopped web
    containers resolve afresh when they start, so only running ones are
    touched. A reload that fails falls back to a restart; if that fails too
    the project fails (the caller's marker file is then not written and the
    next installer run retries). Returns how many containers were reloaded.
    """
    reloaded = 0
    for container_id, state in list_project_containers(docker_bin, compose_project):
        if state != "running":
            continue
        labelled = run_bounded(
            QUICK_TIMEOUT,
            [docker_bin, "inspect", "--format", '{{index .Config.Labels "com.docker.compose.service"}}', container_id],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if labelled.returncode != 0 or labelled.stdout.strip() != "web":
            continue
        reload_result = run_bounded(
            QUICK_TIMEOUT,
            [docker_bin, "exec", container_id, "nginx", "-s", "reload"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if reload_result.returncode != 0:
            log_line(f"[vexlyx] nginx reload failed in {container_id}, restarting it: {(reload_result.stderr or '').strip()[:200]}")
            restart_result = run_bounded(
                QUICK_TIMEOUT * 2,
                [docker_bin, "restart", container_id],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            if restart_result.returncode != 0:
                fail(
                    f"Could not reload or restart the web container {container_id}: {(restart_result.stderr or '').strip()[:200]}",
                    "WEB_RELOAD_FAILED",
                )
        reloaded += 1
    return reloaded


def cmd_migrate_network(payload: dict) -> None:
    """Move one deployed project from the panel network to the apps network.

    Rewrites the project's compose file and moves each of its containers in
    place, so a running site keeps serving and a stopped one stays stopped.
    Safe to repeat. Payload: projectId, projectDir.
    """
    project_id = require_field(payload, "projectId")
    project_dir = require_field(payload, "projectDir")
    docker_bin = get_docker_binary()
    ensure_apps_network(docker_bin)

    compose_project = f"vexlyx-{slugify(project_id[:12])}"
    moved = 0
    for container_id, _state in list_project_containers(docker_bin, compose_project):
        if move_container_to_apps_network(docker_bin, container_id) == "moved":
            moved += 1

    # Runs on every call, not only when something moved: a reload that failed
    # on an earlier run must still be retried once the containers have moved.
    reloaded = reload_running_web_containers(docker_bin, compose_project)

    compose_file = Path(project_dir) / "deploy" / "docker-compose.yml"
    rewritten = compose_file.is_file() and rewrite_compose_network(compose_file)

    log_line(f"[vexlyx] {compose_project}: {moved} container(s) moved to {APPS_NETWORK}, {reloaded} web container(s) reloaded, compose file {'updated' if rewritten else 'unchanged'}")
    respond({"done": True, "containersMoved": moved, "webReloaded": reloaded, "composeRewritten": bool(rewritten)})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMANDS = {
    "deploy": cmd_deploy,
    "start": cmd_start,
    "stop": cmd_stop,
    "stop_by_project": cmd_stop_by_project,
    "restart": cmd_restart,
    "remove": cmd_remove,
    "status": cmd_status,
    "logs": cmd_logs,
    "logs_follow": cmd_logs_follow,
    "system_df": cmd_system_df,
    "cleanup": cmd_cleanup,
    "image_id": cmd_image_id,
    "remove_image": cmd_remove_image,
    "exec": cmd_exec,
    "refresh_nginx_conf": cmd_refresh_nginx_conf,
    "migrate_network": cmd_migrate_network,
}


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        fail("No input received on stdin", "NO_INPUT")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON payload: {exc}", "INVALID_JSON")
        return

    command = payload.get("command")
    if command not in COMMANDS:
        fail(
            f"Unknown command '{command}'. Valid: {', '.join(COMMANDS)}",
            "UNKNOWN_COMMAND",
        )
        return

    COMMANDS[command](payload)


if __name__ == "__main__":
    main()
