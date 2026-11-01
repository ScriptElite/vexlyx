# Python Runtime Deployment (F2.2)

> **Feature:** F2.2 — Python (Django/Flask/FastAPI) Deployment  
> **Status:** Completed  
> **Package:** System Layer (`build_manager.py`, `docker_manager.py`, `python.yml`), Fastify API (`modules/build`)

---

## 1. Overview

Vexlyx provides zero-config, native runtime deployment for **Python web applications**, including:
- **Django**: Auto-detects WSGI modules, runs `python manage.py collectstatic --noinput`, and boots `gunicorn <module>.wsgi:application`.
- **Flask**: Auto-detects WSGI entry points (`app:app`, `main:app`, `wsgi:app`, `application:app`) and runs `gunicorn`.
- **FastAPI**: Auto-detects ASGI entry points (`main:app`, `app.main:app`, `app:app`) and runs `uvicorn` with multiple workers.
- **Python Version Pinning**: Automatically respects `.python-version`, `runtime.txt`, `pyproject.toml`, or project environment variables (`PYTHON_VERSION` / `NIXPACKS_PYTHON_VERSION`) to pin Python to 3.10, 3.11, 3.12, or any custom version.
- **Dual-Phase Environment Injection**: Injects all encrypted project environment variables during both Nixpacks image builds and Docker Compose runtime.

---

## 2. Architecture & Execution Flow

```
┌─────────────────────────┐
│ Git Connect / Workspace │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Framework Detection Heuristics (`build_manager.py plan`)    │
│  - Django: manage.py, requirements.txt, pyproject.toml      │
│  - Flask: flask in deps, app.py / main.py / wsgi.py         │
│  - FastAPI: fastapi in deps, main.py / app/main.py          │
│  - Version Pinning: .python-version, runtime.txt, pyproject │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Build Phase (`nixpacks build`)                              │
│  - Build command (Django): python manage.py collectstatic   │
│  - Start command override: gunicorn / uvicorn               │
│  - Cache key: `vexlyx-<projectId>`                          │
│  - Environment variables: `--env NIXPACKS_PYTHON_VERSION=…` │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Deploy Phase (`docker_manager.py deploy`)                   │
│  - Template: `system/templates/docker-compose/python.yml`   │
│  - HOST=0.0.0.0, PORT=8000, PYTHONUNBUFFERED=1              │
│  - GUNICORN_CMD_ARGS=--bind=0.0.0.0:8000                   │
│  - Traefik dynamic router & load balancer on port 8000      │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Framework Auto-Detection Heuristics

When `build_manager.py plan` executes, Vexlyx inspects the repository files and dependencies (`requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.py`):

### 1. Django
- **Detection**: Presence of `manage.py` OR `django` in dependency manifests.
- **WSGI Resolution**:
  - Scans `manage.py` for `DJANGO_SETTINGS_MODULE` (e.g. `mysite.settings` → `mysite.wsgi`).
  - Scans first-level directories for `wsgi.py` (e.g. `config/wsgi.py` → `config.wsgi`, `mysite/wsgi.py` → `mysite.wsgi`).
  - Root `wsgi.py` → `wsgi`.
- **Suggested Build Command**: `python manage.py collectstatic --noinput` (if `manage.py` exists).
- **Suggested Start Command**: `gunicorn <module>.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2`.
- **Identified Framework**: `django` (displayed as `Django`), Project Type: `PYTHON`.

### 2. Flask
- **Detection**: `flask` in dependency manifests, or Python files using Flask.
- **Entrypoint Discovery**:
  - `app.py` → `app:app`
  - `main.py` → `main:app`
  - `wsgi.py` → `wsgi:app`
  - `application.py` → `application:app`
  - `src/app.py` → `src.app:app`
  - `src/main.py` → `src.main:app`
- **Suggested Start Command**: `gunicorn -w 2 -b 0.0.0.0:${PORT:-8000} <entrypoint>`.
- **Identified Framework**: `flask` (displayed as `Flask`), Project Type: `PYTHON`.

### 3. FastAPI
- **Detection**: `fastapi` in dependency manifests.
- **Entrypoint Discovery**:
  - `main.py` → `main:app`
  - `app/main.py` → `app.main:app`
  - `app.py` → `app:app`
  - `src/main.py` → `src.main:app`
  - `src/app.py` → `src.app:app`
- **Suggested Start Command**: `uvicorn <entrypoint> --host 0.0.0.0 --port ${PORT:-8000} --workers 2`.
- **Identified Framework**: `fastapi` (displayed as `FastAPI`), Project Type: `PYTHON`.

### 4. Generic Python
- **Detection**: Repositories containing `requirements.txt`, `pyproject.toml`, or `.py` files without specific web frameworks.
- **Suggested Start Command**: `python main.py` or `python app.py`.
- **Identified Framework**: `python` (displayed as `Python`), Project Type: `PYTHON`.

---

## 4. Python Version Selection (3.10, 3.11, 3.12)

Vexlyx inspects the following sources (in priority order) to resolve the exact Python version:
1. **Environment Variables**: Project setting `PYTHON_VERSION` or `NIXPACKS_PYTHON_VERSION` (e.g. `3.11`, `3.12`).
2. **`.python-version` File**: Text containing version (e.g. `3.11.8` → normalized to `3.11`).
3. **`runtime.txt` File**: Heroku-style version file (e.g. `python-3.12.2` → normalized to `3.12`).
4. **`pyproject.toml`**: `requires-python = ">=3.10"` or `python = "^3.11"`.

The resolved version is passed to Nixpacks via `--env NIXPACKS_PYTHON_VERSION=<version>` during both `plan` and `build` operations.

---

## 5. Container & Compose Template (`python.yml`)

The Python container runs with internal port `8000` by default:

```yaml
services:
  app:
    image: "{{image_name}}"
    restart: unless-stopped
    environment:
      PORT: "{{container_port}}"
      HOST: "0.0.0.0"
      FLASK_RUN_HOST: "0.0.0.0"
      FLASK_RUN_PORT: "{{container_port}}"
      UVICORN_HOST: "0.0.0.0"
      UVICORN_PORT: "{{container_port}}"
      GUNICORN_CMD_ARGS: "--bind=0.0.0.0:{{container_port}}"
      PYTHONUNBUFFERED: "1"
{{env_block}}
    ports:
      - "{{host_port}}:{{container_port}}"
    deploy:
      resources:
        limits:
          memory: "{{memory_limit}}"
    healthcheck:
      test: ["CMD", "python", "-c", "import socket; socket.create_connection((socket.gethostname(), {{container_port}}), 5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{{service_name}}.rule=Host(`{{hostname}}`)"
      - "traefik.http.routers.{{service_name}}.entrypoints=web"
      - "traefik.http.services.{{service_name}}.loadbalancer.server.port={{container_port}}"

networks:
  default:
    external: true
    name: vexlyx-apps
```

---

## 6. How to Test

Run the automated test suite:
```bash
python tests/test_python_runtime.py
```

Expected output:
```
=== Running Python Runtime (F2.2) Automated Test Suite ===
Testing Django framework auto-detection & WSGI resolution...
  [PASS] Django with mysite/wsgi.py detected -> collectstatic & gunicorn mysite.wsgi:application
  [PASS] Django with config/wsgi.py in pyproject.toml detected -> gunicorn config.wsgi:application
Testing Flask framework auto-detection & entrypoint discovery...
  [PASS] Flask auto-detected with entrypoint 'app.py' -> 'app:app'
  [PASS] Flask auto-detected with entrypoint 'main.py' -> 'main:app'
  [PASS] Flask auto-detected with entrypoint 'wsgi.py' -> 'wsgi:app'
  [PASS] Flask auto-detected with entrypoint 'application.py' -> 'application:app'
Testing FastAPI framework auto-detection & entrypoint discovery...
  [PASS] FastAPI auto-detected with entrypoint 'main.py' -> 'main:app'
  [PASS] FastAPI auto-detected with entrypoint 'app.py' -> 'app:app'
  [PASS] FastAPI auto-detected with entrypoint 'app/main.py' -> 'app.main:app'
Testing Python version detection (3.10, 3.11, 3.12)...
  [PASS] .python-version '3.11.8' -> 3.11
  [PASS] runtime.txt 'python-3.12.2' -> 3.12
  [PASS] pyproject.toml 'requires-python = ">=3.10"' -> 3.10
  [PASS] env_vars PYTHON_VERSION '3.12' -> 3.12
Testing python.yml template rendering & parameters...
  [PASS] python.yml rendered correctly with all variables & Traefik labels

[SUCCESS] ALL PYTHON RUNTIME TESTS PASSED SUCCESSFULLY!
```

---

## 7. How to Extend

- **Adding Celery / Background Workers**: Extend `python.yml` with an optional `worker` service sharing the application image and database/Redis connections.
- **ASGI Django (Daphne/Uvicorn)**: If `asgi.py` is present and websocket support is needed, the `start_cmd` can be configured as `daphne -b 0.0.0.0 -p 8000 <module>.asgi:application`.
- **Custom WSGI/ASGI Servers**: Users can provide manual start command overrides via the dashboard Build Panel or `startCmd` project setting.
