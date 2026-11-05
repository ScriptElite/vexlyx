# Custom Dockerfile Runtime Deployment (F2.5)

> **Feature:** F2.5 — Custom Dockerfile Deployment  
> **Status:** Completed  
> **Package:** System Layer (`build_manager.py`, `docker_manager.py`, `docker.yml`), Fastify API (`modules/dockerfile`, `modules/build`), Dashboard (`components/projects/DockerfilePanel`), Shared (`schemas/dockerfile`)

---

## 1. Overview

Vexlyx enables developers to deploy custom containerized applications using an explicit **Dockerfile** and optional **`.dockerignore`**, offering maximum flexibility for bespoke stacks, multi-stage pipelines, and custom base images (Alpine, Debian, Scratch, Ubuntu, etc.).

Key capabilities include:
- **Priority Detection**: If a project contains a `Dockerfile` (or is created as type `DOCKER`), Vexlyx automatically prioritizes native `docker build` over standard buildpack heuristics.
- **Native `docker build` Pipeline**: Executes `docker build --progress=plain -t <imageName> -f Dockerfile .` with live step-by-step log streaming via WebSockets.
- **Build-time Argument Injection**: Injects all project environment variables automatically as `--build-arg KEY=VAL`.
- **Automatic `.dockerignore` Support**: Placed directly in the project directory so Docker excludes sensitive or unneeded build artifacts (`node_modules`, `.git`, `.env`).
- **Smart Directive Parsing**: Automatically parses `FROM`, `EXPOSE` port(s), `HEALTHCHECK`, and `ENTRYPOINT`/`CMD` from the Dockerfile.
- **Port Auto-Wiring**: Uses the first exposed port (e.g. `8080`, `3000`, `80`) to configure Traefik reverse proxy routing and container ports.
- **Interactive Code Editor**: High-contrast, monospace editor with line numbers, template insertion, and file upload capabilities in the dashboard.
- **Pre-configured Starter Presets**: 1-click starter templates for **Node.js (Multi-stage)**, **Python (FastAPI / Uvicorn)**, **Go (Alpine Minimal)**, **Rust (Slim Binary)**, **Static Website / SPA (Nginx)**, **Bun**, and **PHP 8.3**.

---

## 2. Architecture & Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│ Git Repository or Dashboard Dockerfile Editor / Upload      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ Framework Detection & Directive Inspection                  │
│  (`build_manager.py plan` / `dockerfile-get`)               │
│  - Checks for Dockerfile, dockerfile, Dockerfile.prod       │
│  - Extracts `FROM <base_image>`                             │
│  - Extracts `EXPOSE <port>` (e.g. 8080, 3000/tcp)          │
│  - Extracts `HEALTHCHECK` directive                         │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ Native Docker Build Phase (`build_manager.py build`)        │
│  - Command: `docker build --progress=plain -t <img_name> .` │
│  - Build args: `--build-arg KEY=VAL` from environment vars  │
│  - Build context: Full project root with `.dockerignore`    │
│  - Streams step logs line-by-line via Socket.io to panel    │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ Container Orchestration (`docker_manager.py deploy`)        │
│  - Template: `system/templates/docker-compose/docker.yml`   │
│  - Target port: Auto-detected EXPOSE port (or user override)│
│  - Traefik Router & Service load balancer configured        │
│  - Health check probe enabled on container network          │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. System Layer Details

### 1. Directive Parsing (`parse_dockerfile_info`)
Located in `system/python/build_manager.py`:
- **`FROM`**: Resolves base image for inspection in the dashboard.
- **`EXPOSE`**: Handles single or multiple space-delimited ports, including protocol notations (e.g. `EXPOSE 80/tcp 443/tcp 3000` -> `[80, 443, 3000]`).
- **`HEALTHCHECK`**: Extracts custom container health checks.
- **`ENTRYPOINT` & `CMD`**: Identifies runtime process instructions.

### 2. Native `docker build` Execution
When `find_dockerfile(project_path)` resolves a Dockerfile:
1. `docker build` is executed with `--progress=plain` for clean, unbuffered logging.
2. Build-time environment variables are mapped to `--build-arg`.
3. Standard output and error streams are captured, parsed, and pushed to `log_line(...)`.
4. Successful build signals `{"done": true, "imageName": image_name}`.

### 3. Dockerfile CRUD Commands
- **`dockerfile-get`**:
  ```json
  { "command": "dockerfile-get", "projectDir": "/var/vexlyx/projects/<id>" }
  ```
  Returns `{ success, hasDockerfile, hasDockerignore, dockerfile, dockerignore, exposedPorts, healthCheck, baseImage }`.

- **`dockerfile-save`**:
  ```json
  { "command": "dockerfile-save", "projectDir": "/var/vexlyx/projects/<id>", "dockerfile": "...", "dockerignore": "..." }
  ```
  Safely writes files to disk, parses directives, and returns status metadata.

### 4. Docker Compose Template (`docker.yml`)
Located at `system/templates/docker-compose/docker.yml`:
```yaml
name: "vexlyx-{{service_name}}"

services:
  app:
    image: "{{image_name}}"
    restart: unless-stopped
    environment:
      PORT: "{{container_port}}"
      HOST: "0.0.0.0"
{{env_block}}
    ports:
      - "{{host_port}}:{{container_port}}"
    deploy:
      resources:
        limits:
          memory: "{{memory_limit}}"
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

Vexlyx does not inject a health check into custom Dockerfile deployments.
Custom images are not guaranteed to contain `wget`, `curl`, Node.js, Python, or
another probing tool. If the Dockerfile defines `HEALTHCHECK`, Docker preserves
and uses that image-level check; otherwise Traefik routes to the running
container without an invented dependency.

### 5. Volumes

The template declares no `volumes:` key, so the only storage a Docker project can
have is whatever its image declares with `VOLUME`. Compose creates an anonymous
volume for each such path on the first deploy and reattaches it on every later one,
because the deploy command is:

```
docker compose up -d --force-recreate --pull missing    # docker_manager.py:889
```

`--force-recreate` rebuilds the container but is not `--renew-anon-volumes` (`-V`),
which is what would discard the anonymous volume. The result, measured on a live
server with a two-tag probe image:

| action | container | anonymous volume | contents of the `VOLUME` path |
| --- | --- | --- | --- |
| first deploy of `v1` | new | created, initialised from the image | `v1` |
| the app writes `upload.txt` into the path | — | same volume | kept |
| redeploy after the image becomes `v2` | recreated | **same volume, reattached** | still `v1`, and `upload.txt` is still there — the `v2` file baked into the image is masked |
| **Remove** (`down --volumes --remove-orphans`, `docker_manager.py:1027`) | destroyed | **deleted** | gone, including the user's writes |
| next deploy | new | new volume, initialised from the image | `v2` |

Two consequences operators hit in practice:

- **Anything written into a `VOLUME` path by the image at build time only reaches the
  site when the volume is new.** A WordPress theme or core files baked into an image
  that declares `VOLUME /var/www/html` will not update on redeploy; the push succeeds,
  the container is replaced, and the site keeps serving the first version. The fix is
  in the image, not the platform: an entrypoint that refreshes baked-in content into
  the mounted path on start (see the workaround in #157).
- **`Remove` names the volumes but not what is inside them.** The confirmation dialog
  says it will "remove associated volumes" and that "your source code and deployment
  history will remain intact" (`ContainerControls.tsx:327`) — both true, and both
  beside the point: what goes with the volume is the runtime data, the uploads,
  installed plugins and databases the site has accumulated. Stop, start and redeploy
  all keep that volume; Remove is the one action that destroys it, and it is the only
  way to make baked-in image content arrive.

Named volumes, a dashboard view of the anonymous volume, and a separate "delete data"
action are the feature half of #157 and are not implemented. A volume that was
reattached across a `--force-recreate` was also observed to survive its own
`down --volumes` as an orphan, so `docker volume prune` may be needed to reclaim the
disk after a removal.

---

## 4. API Endpoints

All endpoints are authenticated with session cookies (`app.requireAuth`):

### 1. `GET /api/projects/:id/dockerfile`
Returns current `Dockerfile`, `.dockerignore`, and parsed metadata:
```json
{
  "hasDockerfile": true,
  "hasDockerignore": true,
  "filename": "Dockerfile",
  "dockerfile": "FROM node:20-alpine\nWORKDIR /app\n...",
  "dockerignore": "node_modules\n.git\n.env\n",
  "exposedPorts": [3000],
  "healthCheck": null,
  "baseImage": "node:20-alpine",
  "entrypoint": null,
  "cmd": "[\"npm\", \"start\"]"
}
```

### 2. `PUT /api/projects/:id/dockerfile`
Saves or updates `Dockerfile` and `.dockerignore` content, auto-updating the project's internal port if `syncPort` is requested:
```json
{
  "dockerfile": "FROM python:3.11-slim\nWORKDIR /app\nEXPOSE 8080\n...",
  "dockerignore": ".venv\n__pycache__\n",
  "syncPort": true,
  "port": 8080
}
```

### 3. `GET /api/projects/:id/dockerfile/templates`
Returns the catalog of 7 production-grade starter templates (Node.js, Python FastAPI, Go, Rust, Nginx SPA, Bun, PHP 8.3).

---

## 5. Dashboard User Interface

The `DockerfilePanel` (`components/projects/DockerfilePanel.tsx`) provides:
1. **Interactive Tabs**: Seamless switching between `Dockerfile` and `.dockerignore`.
2. **Monospace Code Editor**: Dark theme code editor with dynamic line numbers and character counters.
3. **Template Selector**: Dropdown to insert pre-configured templates with one click.
4. **File Upload**: Direct file picker for uploading existing `Dockerfile` or `.dockerignore` files.
5. **Directive Banner**: Displays detected Base Image, Exposed Port(s), and Health Check status.
6. **Container Port Field**: Real-time port configuration synced with Traefik routing.
7. **Save & Quick Deploy**: Trigger immediate build execution with live terminal log streaming.

---

## 6. How to Test

Run the automated test suite:

```bash
# Custom Dockerfile runtime tests
python tests/test_dockerfile_runtime.py


# Dockerfile builds must not require nixpacks (also runs in CI)
python -m unittest tests.test_dockerfile_build_nixpacks_absent -v

# Multi-project isolation verification
python tests/test_multi_project_isolation.py

# Full monorepo verification
pnpm typecheck
pnpm lint
pnpm build
```
