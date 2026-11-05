#!/usr/bin/env python3
"""
build_manager.py — System-layer script for Vexlyx Nixpacks build operations.

Called by the API service via child_process.spawn with a JSON payload on stdin.
Writes JSON results to stdout and exits with code 0 on success, 1 on error.

Commands:
  plan   — Run `nixpacks plan` to detect the framework and proposed build command.
           Returns a single JSON object: { framework, buildCmd }.

  build  — Run `nixpacks build` to create a Docker image.
           Streams log lines as newline-delimited JSON: { log: "..." }
           Ends with: { done: true, imageName: "..." }

Never run this script as root.
Requires `nixpacks` to be installed and available in PATH.
"""

import base64
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tarfile
import threading
import zipfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Ensure standard streams use UTF-8 on all platforms (especially Windows)
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


def respond(data: dict) -> None:
    """Write a JSON result to stdout and flush."""
    print(json.dumps(data), flush=True)


def log_line(message: str) -> None:
    """Emit a single log line as newline-delimited JSON for streaming."""
    print(json.dumps({"log": message}), flush=True)


def fail(message: str, code: str = "BUILD_ERROR") -> None:
    """Write a JSON error to stdout and exit 1."""
    print(json.dumps({"error": message, "code": code}), flush=True)
    sys.exit(1)


def require_field(payload: dict, field: str) -> str:
    value = payload.get(field)
    if not value or not isinstance(value, str):
        fail(f"Missing required field: {field}", "INVALID_PAYLOAD")
    return value  # type: ignore[return-value]  — fail() exits


def get_nixpacks_binary() -> str:
    """Find nixpacks in PATH or common install directories."""
    binary = shutil.which("nixpacks")
    if binary:
        return binary

    # Check common user installation directories
    home = Path.home()
    candidates = [
        home / ".nixpacks" / "bin" / ("nixpacks.exe" if sys.platform == "win32" else "nixpacks"),
        Path("/usr/local/bin/nixpacks"),
        Path("/usr/bin/nixpacks"),
        Path("C:/Program Files/nixpacks/nixpacks.exe"),
    ]

    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())

    if sys.platform == "win32":
        install_cmd = "PowerShell: irm https://nixpacks.com/install.ps1 | iex"
    else:
        install_cmd = "curl -sSL https://nixpacks.com/install.sh | sh"

# ---------------------------------------------------------------------------
# Bounded subprocess execution (#52)
#
# Every external command is time-limited so a hung docker/nixpacks/mysqldump
# cannot wedge a build or deploy forever (the API side only has a backstop
# watchdog; killing this script would orphan the grandchild process, so the
# limit has to be enforced here). Values are seconds.
# ---------------------------------------------------------------------------

PLAN_TIMEOUT = 120        # `nixpacks plan`
QUICK_TIMEOUT = 120       # docker create / cp / rm / rmi
BUILD_TIMEOUT = 3600      # `docker build` / `nixpacks build`
DB_TRANSFER_TIMEOUT = 1800  # mysqldump / mysql import

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
    """Find docker binary in PATH or common install directories."""
    binary = shutil.which("docker")
    if binary:
        return binary

    # Check common locations
    candidates = [
        Path("/usr/bin/docker"),
        Path("/usr/local/bin/docker"),
        Path("C:/Program Files/Docker/Docker/resources/bin/docker.exe"),
        Path("C:/Program Files/Docker/Docker/resources/docker.exe"),
    ]
    for c in candidates:
        if c.is_file():
            return str(c.resolve())

    fail("Docker CLI not found in PATH. Install Docker Engine or Docker Desktop.", "DOCKER_NOT_FOUND")
    return "docker"


def get_docker_binary() -> str:
    binary = shutil.which("docker")
    if binary:
        return binary
    fail("Docker CLI not found in PATH. Install Docker Engine or Docker Desktop.", "DOCKER_NOT_FOUND")
    return "docker"  # unreachable


def find_dockerfile(project_dir: Path) -> Path | None:
    """Find Dockerfile in project directory (case-insensitive on Linux/Windows)."""
    candidates = ["Dockerfile", "dockerfile", "Dockerfile.prod", "Dockerfile.app"]
    for candidate in candidates:
        p = project_dir / candidate
        if p.is_file():
            return p
    return None


def parse_dockerfile_info(dockerfile_path: Path | None) -> dict:
    """
    Parse Dockerfile directives:
    - exposedPorts: list of integers
    - healthCheck: string
    - baseImage: string
    - entrypoint: string
    - cmd: string
    - envKeys: list of strings
    """
    if not dockerfile_path or not dockerfile_path.is_file():
        return {
            "hasDockerfile": False,
            "baseImage": None,
            "exposedPorts": [],
            "healthCheck": None,
            "entrypoint": None,
            "cmd": None,
            "envKeys": [],
        }

    try:
        content = dockerfile_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        content = ""

    base_image = None
    exposed_ports: list[int] = []
    health_check = None
    entrypoint = None
    cmd = None
    env_keys: list[str] = []

    for line in content.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith("#"):
            continue

        # FROM <image>
        if line_clean.upper().startswith("FROM "):
            parts = line_clean.split(None, 2)
            if len(parts) >= 2 and not base_image:
                base_image = parts[1]

        # EXPOSE <port> [<port> ...]
        if line_clean.upper().startswith("EXPOSE "):
            ports_part = line_clean[7:].strip()
            for token in ports_part.split():
                token_clean = token.split("/")[0].strip()
                if token_clean.isdigit():
                    port_num = int(token_clean)
                    if port_num not in exposed_ports:
                        exposed_ports.append(port_num)

        # HEALTHCHECK
        if line_clean.upper().startswith("HEALTHCHECK "):
            health_check = line_clean[12:].strip()

        # ENTRYPOINT
        if line_clean.upper().startswith("ENTRYPOINT "):
            entrypoint = line_clean[11:].strip()

        # CMD
        if line_clean.upper().startswith("CMD "):
            cmd = line_clean[4:].strip()

        # ENV
        if line_clean.upper().startswith("ENV "):
            env_part = line_clean[4:].strip()
            if "=" in env_part:
                k = env_part.split("=")[0].strip()
                if k and k not in env_keys:
                    env_keys.append(k)
            else:
                k = env_part.split(None, 1)[0].strip()
                if k and k not in env_keys:
                    env_keys.append(k)

    return {
        "hasDockerfile": True,
        "baseImage": base_image,
        "exposedPorts": exposed_ports,
        "healthCheck": health_check,
        "entrypoint": entrypoint,
        "cmd": cmd,
        "envKeys": env_keys,
    }


# ---------------------------------------------------------------------------
# Node.js & React / Vite Framework Helpers (F2.3)
# ---------------------------------------------------------------------------

def detect_node_version(project_dir: Path, env_vars: dict | None = None) -> str | None:
    """
    Detect Node.js version requested by project (e.g. '18', '20', '22').
    Checks:
    1. env_vars['NIXPACKS_NODE_VERSION'] or env_vars['NODE_VERSION']
    2. .nvmrc file
    3. .node-version file
    4. package.json -> engines.node
    """
    if env_vars:
        if env_vars.get("NIXPACKS_NODE_VERSION"):
            return str(env_vars["NIXPACKS_NODE_VERSION"]).strip()
        if env_vars.get("NODE_VERSION"):
            return str(env_vars["NODE_VERSION"]).strip()

    # 1. .nvmrc
    nvmrc = project_dir / ".nvmrc"
    if nvmrc.is_file():
        try:
            content = nvmrc.read_text(encoding="utf-8").strip()
            m = re.search(r"v?(\d+(?:\.\d+)?)", content)
            if m:
                return m.group(1)
        except Exception:
            pass

    # 2. .node-version
    node_ver_file = project_dir / ".node-version"
    if node_ver_file.is_file():
        try:
            content = node_ver_file.read_text(encoding="utf-8").strip()
            m = re.search(r"v?(\d+(?:\.\d+)?)", content)
            if m:
                return m.group(1)
        except Exception:
            pass

    # 3. package.json engines.node
    pkg_json = project_dir / "package.json"
    if pkg_json.is_file():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
            engines = data.get("engines", {})
            node_engine = engines.get("node")
            if node_engine:
                m = re.search(r"(\d+(?:\.\d+)?)", str(node_engine))
                if m:
                    return m.group(1)
        except Exception:
            pass

    return None


def detect_vite_project(project_dir: Path, plan: dict) -> tuple[str, str | None, str | None, str] | None:
    """
    Detect Vite-based projects (React, Vue, Svelte, or Vanilla/Static Vite).
    Resolves build command and appropriate static start command (npx --yes serve -s dist -l 80).
    """
    vite_config_candidates = [
        "vite.config.js",
        "vite.config.ts",
        "vite.config.mjs",
        "vite.config.cjs",
        "vite.config.mts",
        "vite.config.cts",
    ]
    has_vite_config = any((project_dir / cfg).is_file() for cfg in vite_config_candidates)

    has_vite_dep = False
    has_react_dep = False
    has_vue_dep = False
    has_svelte_dep = False
    has_start_script = False

    pkg_json_path = project_dir / "package.json"
    if pkg_json_path.is_file():
        try:
            pkg = json.loads(pkg_json_path.read_text(encoding="utf-8"))
            deps = pkg.get("dependencies", {})
            dev_deps = pkg.get("devDependencies", {})
            scripts = pkg.get("scripts", {})
            all_deps = {**deps, **dev_deps}

            if "vite" in all_deps or "@vitejs/plugin-react" in all_deps or "@vitejs/plugin-react-swc" in all_deps or "@vitejs/plugin-vue" in all_deps:
                has_vite_dep = True
            if "react" in all_deps or "react-dom" in all_deps or "@vitejs/plugin-react" in all_deps or "@vitejs/plugin-react-swc" in all_deps:
                has_react_dep = True
            if "vue" in all_deps or "@vitejs/plugin-vue" in all_deps or "@vitejs/plugin-vue-jsx" in all_deps:
                has_vue_dep = True
            if "svelte" in all_deps or "@sveltejs/vite-plugin-svelte" in all_deps:
                has_svelte_dep = True
            if "start" in scripts:
                has_start_script = True
        except Exception:
            pass

    if has_vite_config or has_vite_dep:
        # Resolve package manager for build command
        pkg_mgr = "npm"
        if (project_dir / "pnpm-lock.yaml").is_file():
            pkg_mgr = "pnpm"
        elif (project_dir / "yarn.lock").is_file():
            pkg_mgr = "yarn"
        elif (project_dir / "bun.lockb").is_file() or (project_dir / "bun.lock").is_file():
            pkg_mgr = "bun"

        default_build = "yarn build" if pkg_mgr == "yarn" else f"{pkg_mgr} run build"

        phases = plan.get("phases", {})
        build_phase = phases.get("build", {})
        build_cmd = None
        if isinstance(build_phase, dict):
            cmds = build_phase.get("cmds", [])
            if cmds:
                build_cmd = " && ".join(cmds)
        if not build_cmd:
            build_cmd = default_build

        # Resolve start command:
        # 1. If nixpacks plan already resolved a start command (e.g. Caddy), use it
        # 2. If package.json has a "start" script, use package manager start command
        # 3. For static/Vite sites, use "npx --yes serve -s dist -l 80" so container serves built static files on port 80
        start_section = plan.get("start", {})
        start_cmd = start_section.get("cmd") if isinstance(start_section, dict) else None

        if not start_cmd:
            if has_start_script:
                start_cmd = "yarn start" if pkg_mgr == "yarn" else f"{pkg_mgr} run start"
            else:
                start_cmd = "npx --yes serve -s dist -l 80"

        # Determine exact framework and project type
        if has_react_dep:
            framework = "react"
            project_type = "REACT"
        elif has_vue_dep:
            framework = "vue"
            project_type = "STATIC"
        elif has_svelte_dep:
            framework = "svelte"
            project_type = "STATIC"
        else:
            framework = "vite"
            project_type = "STATIC"

        return (framework, build_cmd, start_cmd, project_type)

    return None


def detect_static_project(project_dir: Path, plan: dict) -> tuple[str, str | None, str | None, str] | None:
    """
    Detect plain static HTML/CSS/JS websites without frameworks.
    """
    if (project_dir / "index.html").is_file() and not (project_dir / "package.json").is_file():
        start_section = plan.get("start", {})
        start_cmd = start_section.get("cmd") if isinstance(start_section, dict) else None
        if not start_cmd:
            start_cmd = "npx --yes serve -s . -l 80"
        return ("static", None, start_cmd, "STATIC")
    return None


# ---------------------------------------------------------------------------
# Python Framework & Version Helpers (F2.2)
# ---------------------------------------------------------------------------

def detect_python_version(project_dir: Path, env_vars: dict | None = None) -> str | None:
    """
    Detect Python version requested by project (e.g. '3.10', '3.11', '3.12').
    Checks:
    1. env_vars['NIXPACKS_PYTHON_VERSION'] or env_vars['PYTHON_VERSION']
    2. .python-version file
    3. runtime.txt file
    4. pyproject.toml
    """
    if env_vars:
        if env_vars.get("NIXPACKS_PYTHON_VERSION"):
            return str(env_vars["NIXPACKS_PYTHON_VERSION"]).strip()
        if env_vars.get("PYTHON_VERSION"):
            return str(env_vars["PYTHON_VERSION"]).strip()

    # 1. .python-version
    py_version_file = project_dir / ".python-version"
    if py_version_file.is_file():
        try:
            content = py_version_file.read_text(encoding="utf-8").strip()
            m = re.search(r"(\d+\.\d+(?:\.\d+)?)", content)
            if m:
                ver = m.group(1)
                parts = ver.split(".")
                return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else ver
        except Exception:
            pass

    # 2. runtime.txt
    runtime_file = project_dir / "runtime.txt"
    if runtime_file.is_file():
        try:
            content = runtime_file.read_text(encoding="utf-8").strip()
            m = re.search(r"(\d+\.\d+(?:\.\d+)?)", content)
            if m:
                ver = m.group(1)
                parts = ver.split(".")
                return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else ver
        except Exception:
            pass

    # 3. pyproject.toml
    pyproject_file = project_dir / "pyproject.toml"
    if pyproject_file.is_file():
        try:
            content = pyproject_file.read_text(encoding="utf-8")
            m = re.search(r'(?:python|requires-python)\s*=\s*["\']([^"\']+)["\']', content, re.IGNORECASE)
            if m:
                raw_ver = m.group(1)
                vm = re.search(r"(\d+\.\d+)", raw_ver)
                if vm:
                    return vm.group(1)
        except Exception:
            pass

    return None


def find_django_wsgi_module(project_dir: Path) -> str:
    """Find the Django wsgi module name (e.g. 'mysite.wsgi' or 'config.wsgi')."""
    # Check if manage.py specifies DJANGO_SETTINGS_MODULE
    manage_py = project_dir / "manage.py"
    if manage_py.is_file():
        try:
            content = manage_py.read_text(encoding="utf-8")
            m = re.search(r"DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([^'\"]+)\.settings['\"]", content)
            if m:
                pkg_name = m.group(1).strip()
                if (project_dir / pkg_name / "wsgi.py").is_file():
                    return f"{pkg_name}.wsgi"
        except Exception:
            pass

    # Search subdirectories for wsgi.py
    ignore_dirs = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", "static", "staticfiles", "media"}
    for child in project_dir.iterdir():
        if child.is_dir() and child.name not in ignore_dirs and not child.name.startswith("."):
            if (child / "wsgi.py").is_file():
                return f"{child.name}.wsgi"

    if (project_dir / "wsgi.py").is_file():
        return "wsgi"

    return "wsgi"


def find_flask_entrypoint(project_dir: Path) -> str:
    """Auto-detect Flask app entrypoint (e.g. 'app:app', 'main:app', 'wsgi:app')."""
    candidates = [
        ("app.py", "app:app"),
        ("main.py", "main:app"),
        ("wsgi.py", "wsgi:app"),
        ("application.py", "application:app"),
        ("src/app.py", "src.app:app"),
        ("src/main.py", "src.main:app"),
        ("api/index.py", "api.index:app"),
        ("api/app.py", "api.app:app"),
    ]
    for rel_path, entry in candidates:
        if (project_dir / rel_path).is_file():
            return entry

    return "app:app"


def find_fastapi_entrypoint(project_dir: Path) -> str:
    """Auto-detect FastAPI app entrypoint (e.g. 'main:app', 'app.main:app', 'app:app')."""
    candidates = [
        ("main.py", "main:app"),
        ("app/main.py", "app.main:app"),
        ("app.py", "app:app"),
        ("src/main.py", "src.main:app"),
        ("src/app.py", "src.app:app"),
        ("api/index.py", "api.index:app"),
        ("api/main.py", "api.main:app"),
    ]
    for rel_path, entry in candidates:
        if (project_dir / rel_path).is_file():
            return entry

    return "main:app"


def detect_python_project(project_dir: Path, plan: dict) -> tuple[str, str | None, str | None, str] | None:
    """
    Detect Python framework (Django, Flask, FastAPI, generic Python),
    suggested build command, start command, and 'PYTHON' project type.
    """
    deps_text = ""
    req_file = project_dir / "requirements.txt"
    if req_file.is_file():
        try:
            deps_text += "\n" + req_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

    pyproject_file = project_dir / "pyproject.toml"
    if pyproject_file.is_file():
        try:
            deps_text += "\n" + pyproject_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

    pipfile = project_dir / "Pipfile"
    if pipfile.is_file():
        try:
            deps_text += "\n" + pipfile.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

    setup_py = project_dir / "setup.py"
    if setup_py.is_file():
        try:
            deps_text += "\n" + setup_py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass

    deps_lower = deps_text.lower()

    has_manage_py = (project_dir / "manage.py").is_file()
    has_django_dep = bool(re.search(r"\bdjango\b", deps_lower))
    has_fastapi_dep = bool(re.search(r"\bfastapi\b", deps_lower))
    has_flask_dep = bool(re.search(r"\bflask\b", deps_lower))

    providers = plan.get("providers") or []
    plan_is_python = any("python" in str(p).lower() for p in providers) or "python" in str(plan.get("language", "")).lower()

    # 1. Django
    if has_manage_py or has_django_dep:
        wsgi_module = find_django_wsgi_module(project_dir)
        build_cmd = "python manage.py collectstatic --noinput" if has_manage_py else None
        start_cmd = f"gunicorn {wsgi_module}:application --bind 0.0.0.0:${{PORT:-8000}} --workers 2"
        return ("django", build_cmd, start_cmd, "PYTHON")

    # 2. FastAPI
    if has_fastapi_dep:
        entrypoint = find_fastapi_entrypoint(project_dir)
        start_cmd = f"uvicorn {entrypoint} --host 0.0.0.0 --port ${{PORT:-8000}} --workers 2"
        return ("fastapi", None, start_cmd, "PYTHON")

    # 3. Flask
    if has_flask_dep:
        entrypoint = find_flask_entrypoint(project_dir)
        start_cmd = f"gunicorn -w 2 -b 0.0.0.0:${{PORT:-8000}} {entrypoint}"
        return ("flask", None, start_cmd, "PYTHON")

    # 4. Generic Python
    has_py_files = bool(list(project_dir.glob("*.py"))) or req_file.is_file() or pyproject_file.is_file() or (project_dir / "runtime.txt").is_file() or (project_dir / ".python-version").is_file()

    if plan_is_python or has_py_files:
        start_cmd = None
        if (project_dir / "main.py").is_file():
            start_cmd = "python main.py"
        elif (project_dir / "app.py").is_file():
            start_cmd = "python app.py"
        elif (project_dir / "wsgi.py").is_file():
            start_cmd = "gunicorn wsgi:application"
        return ("python", None, start_cmd, "PYTHON")

    return None


# ---------------------------------------------------------------------------
# PHP & WordPress Framework & Version Helpers (F2.4)
# ---------------------------------------------------------------------------

def detect_php_version(project_dir: Path, env_vars: dict | None = None) -> str | None:
    """
    Detect PHP version requested by project (e.g. '8.1', '8.2', '8.3').
    Checks:
    1. env_vars['NIXPACKS_PHP_VERSION'] or env_vars['PHP_VERSION']
    2. .php-version file
    3. runtime.txt file
    4. composer.json -> require.php
    """
    if env_vars:
        if env_vars.get("NIXPACKS_PHP_VERSION"):
            return str(env_vars["NIXPACKS_PHP_VERSION"]).strip()
        if env_vars.get("PHP_VERSION"):
            return str(env_vars["PHP_VERSION"]).strip()

    # 1. .php-version
    php_version_file = project_dir / ".php-version"
    if php_version_file.is_file():
        try:
            content = php_version_file.read_text(encoding="utf-8").strip()
            m = re.search(r"(\d+\.\d+)", content)
            if m:
                return m.group(1)
        except Exception:
            pass

    # 2. runtime.txt (e.g. 'php-8.2' or '8.3')
    runtime_file = project_dir / "runtime.txt"
    if runtime_file.is_file():
        try:
            content = runtime_file.read_text(encoding="utf-8").strip()
            m = re.search(r"php[-:]?(\d+\.\d+)", content, re.IGNORECASE)
            if m:
                return m.group(1)
            m2 = re.search(r"(\d+\.\d+)", content)
            if m2:
                return m2.group(1)
        except Exception:
            pass

    # 3. composer.json require.php
    composer_file = project_dir / "composer.json"
    if composer_file.is_file():
        try:
            data = json.loads(composer_file.read_text(encoding="utf-8"))
            req = data.get("require", {})
            php_req = req.get("php")
            if php_req:
                m = re.search(r"(\d+\.\d+)", str(php_req))
                if m:
                    return m.group(1)
        except Exception:
            pass

    return None


def detect_php_project(project_dir: Path, plan: dict) -> tuple[str, str | None, str | None, str] | None:
    """
    Detect PHP framework (WordPress, Laravel, Symfony, generic PHP),
    suggested build command, start command, and project type (PHP or WORDPRESS).
    """
    is_wp = (
        (project_dir / "wp-config.php").is_file()
        or (project_dir / "wp-login.php").is_file()
        or (project_dir / "wp-content").is_dir()
        or (project_dir / "wp-includes").is_dir()
        or (project_dir / "wp-config-sample.php").is_file()
    )
    if is_wp:
        return ("wordpress", None, None, "WORDPRESS")

    composer_data = {}
    composer_file = project_dir / "composer.json"
    if composer_file.is_file():
        try:
            composer_data = json.loads(composer_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    req_deps = {**composer_data.get("require", {}), **composer_data.get("require-dev", {})}
    req_keys_lower = {k.lower(): v for k, v in req_deps.items()}

    # 1. Laravel
    has_artisan = (project_dir / "artisan").is_file()
    has_laravel_dep = "laravel/framework" in req_keys_lower or "illuminate/foundation" in req_keys_lower
    if has_artisan or has_laravel_dep:
        build_cmd = "composer install --no-dev --optimize-autoloader" if composer_file.is_file() else None
        return ("laravel", build_cmd, None, "PHP")

    # 2. Symfony
    has_console = (project_dir / "bin" / "console").is_file()
    has_symfony_dep = any("symfony/" in k for k in req_keys_lower)
    if has_console or (has_symfony_dep and (project_dir / "public" / "index.php").is_file()):
        build_cmd = "composer install --no-dev --optimize-autoloader" if composer_file.is_file() else None
        return ("symfony", build_cmd, None, "PHP")

    # 3. Generic PHP / Composer
    has_php_files = bool(list(project_dir.glob("*.php"))) or (project_dir / "public" / "index.php").is_file() or (project_dir / "src" / "index.php").is_file()
    providers = plan.get("providers") or []
    plan_is_php = any("php" in str(p).lower() for p in providers) or "php" in str(plan.get("language", "")).lower()

    if plan_is_php or composer_file.is_file() or has_php_files:
        build_cmd = "composer install --no-dev" if composer_file.is_file() else None
        return ("php", build_cmd, None, "PHP")

    return None


def safe_extract_zip(zip_path: Path, target_dir: Path) -> int:
    """Safely extracts a ZIP archive into target_dir preventing path traversal."""
    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    resolved_target = target_dir.resolve()

    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            dest = (target_dir / member.filename).resolve()
            if not str(dest).startswith(str(resolved_target)):
                continue
            if member.is_dir():
                dest.mkdir(parents=True, exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
    return count


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def detect_framework_and_commands(project_dir: Path, plan: dict) -> tuple[str, str | None, str | None, str | None]:
    """
    Detect the project framework, suggested build command, start command,
    and normalized project type based on file heuristics and Nixpacks plan.
    """
    # Detect package manager for Node/JS projects
    pkg_mgr = "npm"
    if (project_dir / "pnpm-lock.yaml").is_file():
        pkg_mgr = "pnpm"
    elif (project_dir / "yarn.lock").is_file():
        pkg_mgr = "yarn"
    elif (project_dir / "bun.lockb").is_file() or (project_dir / "bun.lock").is_file():
        pkg_mgr = "bun"

    default_build = "yarn build" if pkg_mgr == "yarn" else f"{pkg_mgr} run build"
    default_start = "yarn start" if pkg_mgr == "yarn" else f"{pkg_mgr} run start"

    # 0. Custom Dockerfile check (F2.5 - Highest priority)
    dockerfile_p = find_dockerfile(project_dir)
    if dockerfile_p:
        return ("dockerfile", None, None, "DOCKER")

    # 1. Direct Next.js heuristic check
    is_nextjs = False
    next_config_candidates = [
        "next.config.js",
        "next.config.mjs",
        "next.config.ts",
        "next.config.cjs",
    ]
    for cfg in next_config_candidates:
        if (project_dir / cfg).is_file():
            is_nextjs = True
            break

    pkg_json_path = project_dir / "package.json"
    if not is_nextjs and pkg_json_path.is_file():
        try:
            pkg = json.loads(pkg_json_path.read_text(encoding="utf-8"))
            deps = pkg.get("dependencies", {})
            dev_deps = pkg.get("devDependencies", {})
            if "next" in deps or "next" in dev_deps:
                is_nextjs = True
        except Exception:
            pass

    if is_nextjs:
        phases = plan.get("phases", {})
        build_phase = phases.get("build", {})
        build_cmd = None
        if isinstance(build_phase, dict):
            cmds = build_phase.get("cmds", [])
            if cmds:
                build_cmd = " && ".join(cmds)
        if not build_cmd:
            build_cmd = default_build

        start_section = plan.get("start", {})
        start_cmd = start_section.get("cmd") if isinstance(start_section, dict) else None
        if not start_cmd:
            start_cmd = default_start

        return ("nextjs", build_cmd, start_cmd, "NEXTJS")

    # 2. Direct Vite / React / Vue / Static heuristic check (F2.3)
    vite_result = detect_vite_project(project_dir, plan)
    if vite_result:
        v_framework, v_build_cmd, v_start_cmd, v_type = vite_result
        return (v_framework, v_build_cmd, v_start_cmd, v_type)

    # 3. Python (Django / Flask / FastAPI / Python) check (F2.2)
    py_result = detect_python_project(project_dir, plan)
    if py_result:
        py_framework, py_build_cmd, py_start_cmd, py_type = py_result
        return (py_framework, py_build_cmd, py_start_cmd, py_type)

    # 4. PHP / WordPress / Laravel / Symfony check (F2.4)
    php_result = detect_php_project(project_dir, plan)
    if php_result:
        php_framework, php_build_cmd, php_start_cmd, php_type = php_result
        return (php_framework, php_build_cmd, php_start_cmd, php_type)

    # 5. Plain Static HTML/CSS/JS check
    static_result = detect_static_project(project_dir, plan)
    if static_result:
        s_framework, s_build_cmd, s_start_cmd, s_type = static_result
        return (s_framework, s_build_cmd, s_start_cmd, s_type)

    # 6. Generic Node / Frontend build tools (Gulp, Webpack, etc.) & Nixpacks fallback
    providers = plan.get("providers") or []
    provider_name = providers[0] if len(providers) > 0 else None
    variables = plan.get("variables") or {}
    metadata = variables.get("NIXPACKS_METADATA")

    framework = (
        provider_name
        or metadata
        or plan.get("language")
        or plan.get("provider")
        or "unknown"
    )
    if isinstance(framework, dict):
        framework = framework.get("name", "unknown")

    build_cmd = None
    phases = plan.get("phases", {})
    build_phase = phases.get("build", {})
    if isinstance(build_phase, dict):
        cmds = build_phase.get("cmds", [])
        if cmds:
            build_cmd = " && ".join(cmds)

    start_section = plan.get("start", {})
    start_cmd = start_section.get("cmd") if isinstance(start_section, dict) else None

    # Check Gulp / Webpack / generic frontend build manifests
    has_gulp = (project_dir / "gulpfile.js").is_file() or (project_dir / "gulpfile.ts").is_file()
    has_webpack = (project_dir / "webpack.config.js").is_file() or (project_dir / "webpack.config.ts").is_file()
    if has_gulp:
        framework = "gulp"
    elif has_webpack:
        framework = "webpack"

    # Map detected framework to standard ProjectType if possible
    fw_lower = str(framework).lower()
    detected_type = None
    if "next" in fw_lower:
        detected_type = "NEXTJS"
    elif "react" in fw_lower or "vite" in fw_lower:
        detected_type = "REACT"
    elif "gulp" in fw_lower or "webpack" in fw_lower or "static" in fw_lower or "html" in fw_lower:
        detected_type = "STATIC"
    elif "node" in fw_lower or "javascript" in fw_lower or "typescript" in fw_lower:
        detected_type = "NODEJS"
    elif "python" in fw_lower or "django" in fw_lower or "flask" in fw_lower or "fastapi" in fw_lower:
        detected_type = "PYTHON"
    elif "wordpress" in fw_lower:
        detected_type = "WORDPRESS"
    elif "php" in fw_lower or "laravel" in fw_lower or "symfony" in fw_lower:
        detected_type = "PHP"

    # For Node/JS/TS/Static projects, resolve start_cmd and align static builds
    pkg_json_path = project_dir / "package.json"
    if pkg_json_path.is_file():
        try:
            pkg = json.loads(pkg_json_path.read_text(encoding="utf-8"))
            scripts = pkg.get("scripts", {})
            has_start_script = "start" in scripts
            has_build_script = "build" in scripts

            if not build_cmd and has_build_script:
                build_cmd = default_build

            if not start_cmd:
                if has_start_script:
                    start_cmd = default_start
                elif has_build_script or has_gulp or has_webpack:
                    # Frontend/static build tool with no server start script
                    start_cmd = 'if [ -d dist ]; then npx --yes serve -s dist -l 80; elif [ -d build ]; then npx --yes serve -s build -l 80; elif [ -d out ]; then npx --yes serve -s out -l 80; elif [ -d public ]; then npx --yes serve -s public -l 80; else npx --yes serve -s . -l 80; fi'
                    detected_type = "STATIC"
                elif (project_dir / "server.js").is_file():
                    start_cmd = "node server.js"
                elif (project_dir / "app.js").is_file():
                    start_cmd = "node app.js"
                elif (project_dir / "index.js").is_file():
                    start_cmd = "node index.js"
                elif pkg.get("main"):
                    start_cmd = f"node {pkg['main']}"
        except Exception:
            pass

    return (str(framework), build_cmd, start_cmd, detected_type)


def derive_install_cmd(project_dir: Path, detected_type: str | None) -> str | None:
    """
    Propose the Nixpacks install command for a project from its lockfiles.

    Shared by cmd_plan, so the dashboard can show what auto-detection picks,
    and by cmd_build, where an explicit payload override wins and this only
    fills the gap. Returning None leaves Nixpacks' own provider default in
    charge, which is the correct answer for a plain npm project.
    """
    # Python builds need a venv plus setuptools pinned below 70 — the image's
    # default toolchain breaks older requirements files without it.
    if detected_type == "PYTHON":
        if (project_dir / "requirements.txt").is_file():
            return "python -m venv --copies /opt/venv && . /opt/venv/bin/activate && pip install 'setuptools<70' && pip install -r requirements.txt"
        if (project_dir / "pyproject.toml").is_file():
            return "python -m venv --copies /opt/venv && . /opt/venv/bin/activate && pip install 'setuptools<70' && pip install ."
        return None

    if (project_dir / "bun.lockb").is_file() or (project_dir / "bun.lock").is_file():
        return "bun install"
    if (project_dir / "pnpm-lock.yaml").is_file():
        return "pnpm install"
    if (project_dir / "yarn.lock").is_file():
        return "yarn install"
    return None


def cmd_plan(payload: dict) -> None:
    """
    Detect the framework and proposed build command for a project directory.

    Payload fields:
      projectDir — absolute path to the cloned project source
      envVars    — optional dict of environment variables

    Returns a single JSON object:
      { framework: string, buildCmd: string | null, startCmd: string | null,
        installCmd: string | null, detectedType: string | null }
    """
    project_dir = require_field(payload, "projectDir")
    env_vars = payload.get("envVars")
    project_path = Path(project_dir)

    if not project_path.is_dir():
        fail(
            f"Project directory does not exist: {project_dir}",
            "PROJECT_DIR_NOT_FOUND",
        )

    # If project contains a Dockerfile, handle plan directly without invoking nixpacks
    dockerfile_p = find_dockerfile(project_path)
    if dockerfile_p:
        df_info = parse_dockerfile_info(dockerfile_p)
        respond({
            "framework": "dockerfile",
            # A Dockerfile owns its own dependency step; Nixpacks is never
            # invoked, so there is no install command to propose.
            "installCmd": None,
            "buildCmd": None,
            "startCmd": None,
            "detectedType": "DOCKER",
            "isDockerfile": True,
            "exposedPorts": df_info.get("exposedPorts", []),
            "healthCheck": df_info.get("healthCheck"),
            "baseImage": df_info.get("baseImage"),
            "entrypoint": df_info.get("entrypoint"),
            "cmd": df_info.get("cmd"),
        })
        return

    # Resolved only after the Dockerfile branch has returned: a project that owns
    # its Dockerfile never calls nixpacks and must not need it installed (#222).
    nixpacks_bin = get_nixpacks_binary()

    cmd = [nixpacks_bin, "plan", project_dir, "--format", "json"]

    # Detect python version and propagate to nixpacks plan
    py_ver = detect_python_version(project_path, env_vars if isinstance(env_vars, dict) else None)
    if py_ver:
        cmd += ["--env", f"NIXPACKS_PYTHON_VERSION={py_ver}"]

    # Detect node version and propagate to nixpacks plan
    node_ver = detect_node_version(project_path, env_vars if isinstance(env_vars, dict) else None)
    if not node_ver and ((project_path / "vite.config.js").is_file() or (project_path / "vite.config.ts").is_file() or (project_path / "next.config.js").is_file() or (project_path / "next.config.mjs").is_file() or (project_path / "next.config.ts").is_file()):
        node_ver = "20"

    if node_ver:
        cmd += ["--env", f"NIXPACKS_NODE_VERSION={node_ver}"]

    # Detect php version and propagate to nixpacks plan
    php_ver = detect_php_version(project_path, env_vars if isinstance(env_vars, dict) else None)
    if php_ver:
        cmd += ["--env", f"NIXPACKS_PHP_VERSION={php_ver}"]

    if isinstance(env_vars, dict):
        for k, v in env_vars.items():
            if k and v is not None and k not in ("NIXPACKS_PYTHON_VERSION", "NIXPACKS_NODE_VERSION", "NIXPACKS_PHP_VERSION"):
                cmd += ["--env", f"{k}={v}"]

    result = run_bounded(
        PLAN_TIMEOUT,
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    plan = {}
    if result.returncode == 0:
        raw_output = result.stdout.strip()
        if raw_output:
            try:
                plan = json.loads(raw_output)
            except json.JSONDecodeError:
                plan = {}

    framework, build_cmd, start_cmd, detected_type = detect_framework_and_commands(
        project_path, plan
    )

    if result.returncode != 0 and framework == "unknown":
        error_output = (result.stderr or result.stdout or "").strip()
        fail(f"nixpacks plan failed:\n{error_output}", "NIXPACKS_PLAN_FAILED")

    respond({
        "framework": framework,
        "installCmd": derive_install_cmd(project_path, detected_type),
        "buildCmd": build_cmd,
        "startCmd": start_cmd,
        "detectedType": detected_type,
    })


def cmd_build(payload: dict) -> None:
    """
    Build a Docker image for a project using Nixpacks.

    Payload fields:
      projectDir — absolute path to the cloned project source
      imageName  — Docker image name/tag (e.g. vexlyx-<projectId>)
      installCmd — optional install command override (passed via --install-cmd)
      buildCmd   — optional build command override (passed via --build-cmd)
      startCmd   — optional start command override (passed via --start-cmd)
      cacheKey   — optional cache key for incremental builds (passed via --cache-key)
      envVars    — optional dict of environment variables to pass to build phase

    Streams log lines as: { "log": "<line>" }
    Ends with:            { "done": true, "imageName": "<imageName>" }
    """
    project_dir = require_field(payload, "projectDir")
    image_name = require_field(payload, "imageName")
    install_cmd = payload.get("installCmd")
    build_cmd = payload.get("buildCmd")
    start_cmd = payload.get("startCmd")
    cache_key = payload.get("cacheKey")
    env_vars = payload.get("envVars")

    # nixpacks is only needed on the nixpacks build path below. Resolving it
    # here would fail Dockerfile builds (NIXPACKS_NOT_FOUND) on hosts that
    # have Docker but not nixpacks, even though that path never uses it.

    project_path = Path(project_dir)
    if not project_path.is_dir():
        fail(
            f"Project directory does not exist: {project_dir}",
            "PROJECT_DIR_NOT_FOUND",
        )

    # 1. Custom Dockerfile build (F2.5)
    dockerfile_p = find_dockerfile(project_path)
    if dockerfile_p:
        docker_bin = get_docker_binary()
        log_line(f"[vexlyx] Building Docker image from custom Dockerfile: {dockerfile_p.name}")
        log_line(f"[vexlyx] Build context: {project_dir}")

        docker_build_args = [
            docker_bin,
            "build",
            "--progress=plain",
            "-t",
            image_name,
            "-f",
            str(dockerfile_p.resolve()),
        ]

        if isinstance(env_vars, dict):
            for k, v in env_vars.items():
                if k and v is not None:
                    docker_build_args += ["--build-arg", f"{k}={v}"]

        docker_build_args.append(str(project_path.resolve()))

        log_line(f"Running: {' '.join(docker_build_args)}")

        proc = subprocess.Popen(
            docker_build_args,
            **_group_popen_kwargs(),
            cwd=str(project_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        def _emit_build_line(raw_line: str) -> None:
            for part in (p.strip() for p in raw_line.replace("\r", "\n").split("\n")):
                if part:
                    log_line(part)

        if stream_with_deadline(proc, BUILD_TIMEOUT, _emit_build_line):
            fail(
                f"docker build timed out after {BUILD_TIMEOUT}s",
                "COMMAND_TIMEOUT",
            )

        if proc.returncode != 0:
            fail(
                f"docker build failed with exit code {proc.returncode}",
                "DOCKER_BUILD_FAILED",
            )

        print(json.dumps({"done": True, "imageName": image_name}), flush=True)
        return

    nixpacks_bin = get_nixpacks_binary()

    # Auto-resolve start_cmd, build_cmd, and install_cmd if not provided
    detected_fw, detected_build, detected_start, detected_type = detect_framework_and_commands(project_path, {})
    if not start_cmd and detected_start:
        start_cmd = detected_start
    if not build_cmd and detected_build:
        build_cmd = detected_build

    # Fallback only (F5.21): a composer-less PHP/WORDPRESS project now takes
    # the no-build path (docker_manager.py's php-no-build.yml / official
    # WordPress image) and never reaches cmd_build at all -- the API service
    # skips calling it, same as it already does for STATIC/REACT no-build.
    # This still fires for the narrow case of a user explicitly forcing a
    # build override on a composer-less PHP project: Nixpacks' own PHP
    # provider only recognizes a project as PHP when a composer.json is
    # present -- unlike our own detect_php_project(), which also accepts
    # bare .php files with no framework/dependencies. Without this, such a
    # forced build fails nixpacks with "unable to generate a build plan".
    # Bridge the gap with an empty composer.json so nixpacks can build it.
    if detected_type in ("PHP", "WORDPRESS") and not (project_path / "composer.json").is_file():
        (project_path / "composer.json").write_text("{}\n", encoding="utf-8")
        log_line("[vexlyx] No composer.json found — created a minimal one so Nixpacks can build this PHP project")

    # For Python projects, ensure setuptools<70 is installed into venv
    if not install_cmd:
        install_cmd = derive_install_cmd(project_path, detected_type)

    cmd = [nixpacks_bin, "build", project_dir, "--name", image_name]

    if cache_key:
        cmd += ["--cache-key", str(cache_key)]

    if install_cmd:
        cmd += ["--install-cmd", install_cmd]

    if build_cmd:
        cmd += ["--build-cmd", build_cmd]

    if start_cmd:
        cmd += ["--start-cmd", start_cmd]

    # Detect runtime versions and ensure they are passed
    py_ver = detect_python_version(Path(project_dir), env_vars if isinstance(env_vars, dict) else None)
    node_ver = detect_node_version(Path(project_dir), env_vars if isinstance(env_vars, dict) else None)
    if not node_ver and (detected_type in ("REACT", "NEXTJS") or detected_fw in ("vite", "react")):
        node_ver = "20"

    php_ver = detect_php_version(Path(project_dir), env_vars if isinstance(env_vars, dict) else None)
    if not php_ver and (detected_type in ("PHP", "WORDPRESS") or detected_fw in ("php", "laravel", "symfony", "wordpress")):
        php_ver = "8.2"

    merged_env_vars = dict(env_vars) if isinstance(env_vars, dict) else {}
    if py_ver and "NIXPACKS_PYTHON_VERSION" not in merged_env_vars:
        merged_env_vars["NIXPACKS_PYTHON_VERSION"] = py_ver
    if node_ver and "NIXPACKS_NODE_VERSION" not in merged_env_vars:
        merged_env_vars["NIXPACKS_NODE_VERSION"] = node_ver
    if php_ver and "NIXPACKS_PHP_VERSION" not in merged_env_vars:
        merged_env_vars["NIXPACKS_PHP_VERSION"] = php_ver

    # For PHP & WordPress applications, ensure pretty URLs/permalinks fallback is configured
    if (detected_type in ("PHP", "WORDPRESS") or detected_fw in ("php", "laravel", "symfony", "wordpress")) and "NIXPACKS_PHP_FALLBACK_PATH" not in merged_env_vars:
        merged_env_vars["NIXPACKS_PHP_FALLBACK_PATH"] = "/index.php"

    if (project_path / "public").is_dir() and "NIXPACKS_PHP_ROOT_DIR" not in merged_env_vars and detected_fw in ("laravel", "symfony"):
        merged_env_vars["NIXPACKS_PHP_ROOT_DIR"] = "/app/public"

    for k, v in merged_env_vars.items():
        if k and v is not None:
            cmd += ["--env", f"{k}={v}"]

    log_line(f"Running: {' '.join(cmd)}")

    proc = subprocess.Popen(
        cmd,
        **_group_popen_kwargs(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,  # line-buffered
    )

    # Stream combined output line by line, splitting both \r and \n from progress lines
    def _emit_nixpacks_line(raw_line: str) -> None:
        for part in (p.strip() for p in raw_line.replace("\r", "\n").split("\n")):
            if part:
                log_line(part)

    if stream_with_deadline(proc, BUILD_TIMEOUT, _emit_nixpacks_line):
        fail(
            f"nixpacks build timed out after {BUILD_TIMEOUT}s",
            "COMMAND_TIMEOUT",
        )

    if proc.returncode != 0:
        fail(
            f"nixpacks build failed with exit code {proc.returncode}",
            "NIXPACKS_BUILD_FAILED",
        )

    # Signal successful completion
    print(json.dumps({"done": True, "imageName": image_name}), flush=True)


# ---------------------------------------------------------------------------
# Static build-output extraction (F5.7)
# ---------------------------------------------------------------------------

STATIC_OUTPUT_DIR_CANDIDATES = ["dist", "build", "out", "public"]


def cmd_extract_static_output(payload: dict) -> None:
    """
    Pull a STATIC/REACT project's built output directory out of a throwaway
    Nixpacks-built image, then discard the image -- the image itself is never
    deployed; only its build output is served (by a fixed nginx:alpine).

    Payload fields:
      projectDir -- absolute path to the project source
      imageName  -- the Nixpacks image built by a prior `build` command

    Returns: { success: true, staticOutputDir: "<projectDir>/deploy/static-output" }
    """
    project_dir = Path(require_field(payload, "projectDir"))
    image_name = require_field(payload, "imageName")
    docker_bin = get_docker_binary()

    output_dir = project_dir / "deploy" / "static-output"
    if output_dir.is_dir():
        shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    create_result = run_bounded(
        QUICK_TIMEOUT,
        [docker_bin, "create", image_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if create_result.returncode != 0:
        fail(
            f"Failed to create container from {image_name}: {create_result.stderr.strip()}",
            "STATIC_EXTRACT_CREATE_FAILED",
        )
        return

    container_id = create_result.stdout.strip()
    copied = False
    try:
        for candidate in STATIC_OUTPUT_DIR_CANDIDATES:
            cp_result = run_bounded(
                QUICK_TIMEOUT,
                [docker_bin, "cp", f"{container_id}:/app/{candidate}/.", str(output_dir)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if cp_result.returncode == 0:
                log_line(f"[vexlyx] Extracted static build output from /app/{candidate}")
                copied = True
                break
    finally:
        # Best effort and independent: a timed-out `rm` must not skip the `rmi`.
        run_bounded(QUICK_TIMEOUT, [docker_bin, "rm", "-f", container_id], fatal=False, capture_output=True)
        run_bounded(QUICK_TIMEOUT, [docker_bin, "rmi", "-f", image_name], fatal=False, capture_output=True)

    if not copied:
        fail(
            f"Could not find a build output directory ({', '.join(STATIC_OUTPUT_DIR_CANDIDATES)}) in {image_name}",
            "STATIC_EXTRACT_NO_OUTPUT_DIR",
        )
        return

    respond({"success": True, "staticOutputDir": str(output_dir.resolve())})


# ---------------------------------------------------------------------------
# WordPress One-Click Scaffolding & Asset Upload Commands (F2.4)
# ---------------------------------------------------------------------------

def cmd_wordpress_install(payload: dict) -> None:
    """
    Scaffold a WordPress project's wp-content directory (F5.7).

    WordPress core now ships inside the official wordpress:php8.3-fpm-alpine
    image (see system/templates/docker-compose/wordpress.yml); only
    wp-content is user data that lives on the host. DB credentials are no
    longer written to a host-side wp-config.php -- they flow into the
    container purely as WORDPRESS_DB_* environment variables at deploy time.
    """
    project_dir = require_field(payload, "projectDir")
    target_path = Path(project_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    (target_path / "wp-content" / "plugins").mkdir(parents=True, exist_ok=True)
    (target_path / "wp-content" / "themes").mkdir(parents=True, exist_ok=True)
    (target_path / "wp-content" / "uploads").mkdir(parents=True, exist_ok=True)

    respond({
        "success": True,
        "projectDir": str(target_path.resolve()),
        "wpContentDir": str((target_path / "wp-content").resolve()),
    })


def cmd_wordpress_upload(payload: dict) -> None:
    """
    Upload and safely extract a plugin or theme ZIP archive into WordPress wp-content.
    """
    project_dir = require_field(payload, "projectDir")
    asset_type = require_field(payload, "assetType")  # 'plugin' or 'theme'
    target_path = Path(project_dir)

    if not target_path.is_dir():
        fail(f"Project directory does not exist: {project_dir}", "PROJECT_DIR_NOT_FOUND")

    subfolder = "plugins" if asset_type == "plugin" else "themes"
    dest_dir = target_path / "wp-content" / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_path = payload.get("zipPath")
    zip_base64 = payload.get("zipBase64")

    extracted_count = 0
    if zip_path and Path(zip_path).is_file():
        extracted_count = safe_extract_zip(Path(zip_path), dest_dir)
    elif zip_base64:
        # Write base64 buffer to temporary zip and extract
        temp_zip = dest_dir / f"tmp_upload_{secrets.token_hex(8)}.zip"
        try:
            temp_zip.write_bytes(base64.b64decode(zip_base64))
            extracted_count = safe_extract_zip(temp_zip, dest_dir)
        finally:
            if temp_zip.is_file():
                temp_zip.unlink(missing_ok=True)
    else:
        fail("Missing required zipPath or zipBase64 field", "INVALID_PAYLOAD")

    respond({
        "success": True,
        "assetType": asset_type,
        "extractedFiles": extracted_count,
        "targetDir": str(dest_dir.resolve()),
    })


def cmd_wordpress_status(payload: dict) -> None:
    """
    Inspect WordPress installation status, plugins, and themes.

    F5.7: WordPress core no longer lives on the host (it ships inside the
    wordpress:php8.3-fpm-alpine image), so "installed" is judged by whether
    wp-content has been scaffolded, and coreVersion can't be read from a
    host file anymore -- it requires a live container query, out of scope
    here, so it's reported as "unknown".
    """
    project_dir = require_field(payload, "projectDir")
    target_path = Path(project_dir)

    is_installed = (target_path / "wp-content" / "plugins").is_dir()
    core_version = "unknown"

    plugins: list[str] = []
    plugins_dir = target_path / "wp-content" / "plugins"
    if plugins_dir.is_dir():
        for item in plugins_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                plugins.append(item.name)
            elif item.is_file() and item.suffix == ".php" and item.name != "index.php":
                plugins.append(item.stem)

    themes: list[str] = []
    themes_dir = target_path / "wp-content" / "themes"
    if themes_dir.is_dir():
        for item in themes_dir.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                themes.append(item.name)

    respond({
        "installed": is_installed,
        "coreVersion": core_version,
        "plugins": plugins,
        "themes": themes,
    })


# ---------------------------------------------------------------------------
# Custom Dockerfile Management Commands (F2.5)
# ---------------------------------------------------------------------------

def cmd_dockerfile_get(payload: dict) -> None:
    """
    Read Dockerfile and .dockerignore content, parsed exposed ports,
    and health check details from a project directory.
    """
    project_dir = require_field(payload, "projectDir")
    target_path = Path(project_dir)
    dockerfile_p = find_dockerfile(target_path)
    dockerignore_p = target_path / ".dockerignore"

    df_content = ""
    if dockerfile_p and dockerfile_p.is_file():
        try:
            df_content = dockerfile_p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    di_content = ""
    if dockerignore_p.is_file():
        try:
            di_content = dockerignore_p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            pass

    df_info = parse_dockerfile_info(dockerfile_p) if dockerfile_p else {}

    respond({
        "success": True,
        "hasDockerfile": bool(dockerfile_p and dockerfile_p.is_file()),
        "hasDockerignore": dockerignore_p.is_file(),
        "dockerfile": df_content,
        "dockerignore": di_content,
        "filename": dockerfile_p.name if dockerfile_p else "Dockerfile",
        "exposedPorts": df_info.get("exposedPorts", []),
        "healthCheck": df_info.get("healthCheck"),
        "baseImage": df_info.get("baseImage"),
        "entrypoint": df_info.get("entrypoint"),
        "cmd": df_info.get("cmd"),
    })


def cmd_dockerfile_save(payload: dict) -> None:
    """
    Safely write or update Dockerfile and .dockerignore in project directory,
    and parse the updated directives.
    """
    project_dir = require_field(payload, "projectDir")
    target_path = Path(project_dir)
    target_path.mkdir(parents=True, exist_ok=True)

    dockerfile_content = payload.get("dockerfile")
    dockerignore_content = payload.get("dockerignore")

    dockerfile_p = target_path / "Dockerfile"
    dockerignore_p = target_path / ".dockerignore"

    if dockerfile_content is not None:
        dockerfile_p.write_text(dockerfile_content, encoding="utf-8")

    if dockerignore_content is not None:
        dockerignore_p.write_text(dockerignore_content, encoding="utf-8")

    df_info = parse_dockerfile_info(dockerfile_p)

    respond({
        "success": True,
        "hasDockerfile": dockerfile_p.is_file(),
        "hasDockerignore": dockerignore_p.is_file(),
        "exposedPorts": df_info.get("exposedPorts", []),
        "healthCheck": df_info.get("healthCheck"),
        "baseImage": df_info.get("baseImage"),
        "entrypoint": df_info.get("entrypoint"),
        "cmd": df_info.get("cmd"),
    })


# ---------------------------------------------------------------------------
# WordPress Export (F2.8)
# ---------------------------------------------------------------------------

def cmd_wordpress_export(payload: dict) -> None:
    """
    Export a WordPress project (F5.7: wp-content + a fresh DB dump only --
    core is reproducible from the wordpress:php8.3-fpm-alpine image and
    doesn't need to be exported). DB credentials come directly from the
    payload (the API resolves them from the project's linked F2.6 Database
    record) since there is no host-side wp-config.php to parse anymore.
    """
    project_dir = Path(require_field(payload, "projectDir"))
    export_dir = Path(require_field(payload, "exportDir"))
    tar_path = Path(require_field(payload, "tarPath"))
    db_name = require_field(payload, "dbName")
    db_user = require_field(payload, "dbUser")
    db_password = payload.get("dbPassword", "")
    db_host = require_field(payload, "dbHost")

    wp_content_dir = project_dir / "wp-content"
    if not wp_content_dir.is_dir():
        fail(f"wp-content directory not found: {wp_content_dir}", "WP_DIR_NOT_FOUND")

    export_dir.mkdir(parents=True, exist_ok=True)

    # Dump database
    sql_path = export_dir / "database.sql"
    try:
        mysqldump_cmd = [
            "mysqldump",
            f"--host={db_host}",
            f"--user={db_user}",
            f"--password={db_password}",
            "--single-transaction",
            "--routines",
            "--triggers",
            db_name,
        ]
        result = run_bounded(DB_TRANSFER_TIMEOUT, mysqldump_cmd, capture_output=True)
        if result.returncode == 0:
            sql_path.write_bytes(result.stdout)
        else:
            fail(f"mysqldump failed: {result.stderr.decode(errors='replace')}", "WP_DB_DUMP_FAILED")
            return
    except FileNotFoundError:
        fail("mysqldump is not installed or not in PATH", "WP_MYSQLDUMP_NOT_FOUND")
        return

    # Create tar.gz: wp-content + SQL dump
    with tarfile.open(tar_path, "w:gz") as tar:
        tar.add(wp_content_dir, arcname="wp-content")
        tar.add(sql_path, arcname="database.sql")

    respond({"success": True, "tarPath": str(tar_path)})


# ---------------------------------------------------------------------------
# WordPress Import (F2.8)
# ---------------------------------------------------------------------------

def cmd_wordpress_import(payload: dict) -> None:
    """
    Import a WordPress export (F5.7: restores wp-content + the DB dump only;
    core comes from the wordpress:php8.3-fpm-alpine image). DB credentials
    come from the payload (the API resolves them from the project's linked
    F2.6 Database record) -- no wp-config.php is written; the container
    picks up WORDPRESS_DB_* env vars at deploy time instead.
    """
    project_dir = Path(require_field(payload, "projectDir"))
    tar_path_str = require_field(payload, "tarPath")
    tar_path = Path(tar_path_str)

    db_name = require_field(payload, "dbName")
    db_user = require_field(payload, "dbUser")
    db_password = payload.get("dbPassword", "")
    db_host = require_field(payload, "dbHost")

    if not tar_path.is_file():
        fail(f"Uploaded archive not found: {tar_path}", "WP_TAR_NOT_FOUND")

    if not tarfile.is_tarfile(str(tar_path)):
        fail("Uploaded file is not a valid tar archive", "WP_INVALID_TAR")

    # Extract
    extract_tmp = tar_path.parent / "extracted"
    extract_tmp.mkdir(parents=True, exist_ok=True)
    extract_tmp_resolved = extract_tmp.resolve()

    with tarfile.open(tar_path, "r:gz") as tar:
        # Security: prevent tar-slip, symlink escapes, absolute paths, and parent traversal
        safe_members = []
        for m in tar.getmembers():
            if m.issym() or m.islnk():
                continue
            name = m.name.replace("\\", "/")
            if name.startswith("/") or "\0" in name or ".." in name.split("/"):
                continue
            dest_path = (extract_tmp / name).resolve()
            try:
                dest_path.relative_to(extract_tmp_resolved)
            except ValueError:
                continue
            safe_members.append(m)

        tar.extractall(path=extract_tmp, members=safe_members)

    # Move extracted wp-content into the project's wp-content dir
    wp_content_dest = project_dir / "wp-content"
    files_src = extract_tmp / "wp-content"
    if not files_src.is_dir():
        # Backward-compat: older exports (pre-F5.7) tarred the whole
        # project under "files", with wp-content nested inside it.
        legacy_src = extract_tmp / "files" / "wp-content"
        files_src = legacy_src if legacy_src.is_dir() else extract_tmp
    shutil.copytree(str(files_src), str(wp_content_dest), dirs_exist_ok=True)

    # Import SQL dump if present
    sql_candidates = list(extract_tmp.glob("**/*.sql"))
    if sql_candidates:
        sql_file = sql_candidates[0]
        try:
            mysql_cmd = [
                "mysql",
                f"--host={db_host}",
                f"--user={db_user}",
                f"--password={db_password}",
                db_name,
            ]
            with open(sql_file, "rb") as sql_in:
                run_bounded(DB_TRANSFER_TIMEOUT, mysql_cmd, stdin=sql_in, check=True)
        except Exception as e:
            fail(f"SQL import failed: {e}", "WP_SQL_IMPORT_FAILED")

    # Clean up temp extraction
    shutil.rmtree(str(extract_tmp), ignore_errors=True)

    respond({"success": True})


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMANDS = {
    "plan": cmd_plan,
    "build": cmd_build,
    "extract-static-output": cmd_extract_static_output,
    "wordpress-install": cmd_wordpress_install,
    "wordpress-upload": cmd_wordpress_upload,
    "wordpress-status": cmd_wordpress_status,
    "wordpress-export": cmd_wordpress_export,
    "wordpress-import": cmd_wordpress_import,
    "dockerfile-get": cmd_dockerfile_get,
    "dockerfile-save": cmd_dockerfile_save,
}


def main() -> None:
    raw = sys.stdin.read().strip()
    if not raw:
        fail("No input received on stdin", "NO_INPUT")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON payload: {exc}", "INVALID_JSON")
        return  # unreachable — fail() exits; here for type checker

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

