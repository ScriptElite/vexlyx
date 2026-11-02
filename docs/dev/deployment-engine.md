# F1.5 — Docker Deployment Engine

## What This Feature Does

Manages the container deployment lifecycle for Vexlyx projects. After Nixpacks builds a Docker image (F1.4), the deployment engine generates a tailored `docker-compose.yml` file, starts the container using Docker Compose, configures Traefik reverse-proxy routing labels, dynamically allocates host ports, enforces memory limits, handles container lifecycle actions (start, stop, restart, remove), and provides runtime logs.

---

## Architecture

```
Dashboard (BuildPanel.tsx / ContainerControls.tsx / useDeploy.ts)
    │
    │  POST /api/projects/:id/deploy
    │  POST /api/projects/:id/container/:action  (start | stop | restart | remove)
    │  GET  /api/projects/:id/container/status
    │  GET  /api/projects/:id/logs?tail=N
    ▼
API (apps/api/src/modules/deploy/)
    ├── routes.ts   — Fastify route handlers with authentication & input validation
    ├── service.ts  — Business logic, Docker manager execution, Project DB updates
    └── schema.ts   — DeployBodySchema, ContainerActionBodySchema, LogsQuerySchema
         │
         │  stdin: JSON payload { command: "deploy" | "start" | "stop" | "restart" | "remove" | "status" | "logs", ... }
         │  stdout: JSON results / log streaming
         ▼
    system/python/docker_manager.py
         ├── cmd_deploy()  — Generates compose file from template & runs `docker compose up -d`
         ├── cmd_start()   — `docker compose start`
         ├── cmd_stop()    — `docker compose stop`
         ├── cmd_restart() — `docker compose restart`
         ├── cmd_remove()  — `docker compose down --volumes --remove-orphans`
         ├── cmd_status()  — `docker inspect` to verify container state
         └── cmd_logs()    — `docker compose logs --tail=N`
              │
              ├── system/templates/docker-compose/node.yml
              ├── system/templates/docker-compose/python.yml
              └── system/templates/docker-compose/static.yml
```

---

## Deployment Lifecycle & Pipeline

1. **Build & Deploy Pipeline**:
   - `BuildService` runs Nixpacks plan and image build (`QUEUED` → `BUILDING`).
   - When image build completes, it automatically transitions to `DEPLOYING`.
   - `runDockerDeploy()` runs `docker_manager.py deploy`:
     - Selects the appropriate compose template (`node.yml`, `python.yml`, or `static.yml`).
     - Substitutes template tokens: `image_name`, `service_name`, `hostname`, `host_port`, `container_port`, `memory_limit`, and `env_block`.
     - Writes `docker-compose.yml` in `{PROJECTS_DIR}/{projectId}/deploy/`.
     - Executes `docker compose up -d --force-recreate --pull never`.
     - Resolves container ID and verifies container startup.
     - If the image declares no `HEALTHCHECK`, connects from the host to the container's `vexlyx-apps` address on the port the Traefik router upstreams to, and logs the answer — `Routable check <ip>:<port> answered`, or a `WARNING` naming that address and the bind fix (#202). It needs nothing inside the image, so it works on any base image, and it never fails the deploy: an app bound to `127.0.0.1` keeps its process up and answers nothing on the routable address, which is exactly the 502-while-"Running" case. Images that do declare a healthcheck are left to Docker's own verdict, which `GET /api/projects/:id/container/status` already reports.
   - Updates `Project` record in PostgreSQL (`containerId`, `containerStatus`, `internalPort`, `deployedDomain`, `deployedAt`, `status = ACTIVE`).
   - Marks `Deployment` record as `RUNNING`.

2. **Container Lifecycle Management**:
   - **Start**: `POST /api/projects/:id/container/start` → sets project status to `ACTIVE`.
   - **Stop**: `POST /api/projects/:id/container/stop` → sets project status to `STOPPED`.
   - **Restart**: `POST /api/projects/:id/container/restart` → restarts container and sets status to `ACTIVE`.
   - **Remove**: `POST /api/projects/:id/container/remove` → destroys container & volumes, clears container metadata, and sets status to `STOPPED`.

3. **Runtime Logs**:
   - `GET /api/projects/:id/logs?tail=100` retrieves stdout & stderr output from the running container.

---

## Key Files

| File | Role |
|------|------|
| [`apps/api/src/modules/deploy/routes.ts`](../apps/api/src/modules/deploy/routes.ts) | Fastify routes for deploy, lifecycle actions, container status, and runtime logs |
| [`apps/api/src/modules/deploy/service.ts`](../apps/api/src/modules/deploy/service.ts) | `DeployService` class and subprocess helpers for `docker_manager.py` |
| [`apps/api/src/modules/deploy/schema.ts`](../apps/api/src/modules/deploy/schema.ts) | Zod request validation schemas (`DeployBodySchema`, `ContainerActionBodySchema`, `LogsQuerySchema`) |
| [`system/python/docker_manager.py`](../system/python/docker_manager.py) | Python daemon script handling compose generation, Docker CLI execution, and log retrieval |
| [`system/templates/docker-compose/node.yml`](../system/templates/docker-compose/node.yml) | Docker Compose template for Node.js and Next.js applications |
| [`system/templates/docker-compose/python.yml`](../system/templates/docker-compose/python.yml) | Docker Compose template for Python WSGI/ASGI applications |
| [`system/templates/docker-compose/static.yml`](../system/templates/docker-compose/static.yml) | Docker Compose template for static React/HTML sites |
| [`packages/shared/src/schemas/projects.ts`](../packages/shared/src/schemas/projects.ts) | Shared `DeployBodySchema` and `ContainerActionSchema` |
| [`packages/shared/src/types/index.ts`](../packages/shared/src/types/index.ts) | Extended `Project` type with container fields (`containerId`, `containerStatus`, etc.) |
| [`apps/dashboard/src/hooks/useDeploy.ts`](../apps/dashboard/src/hooks/useDeploy.ts) | React hooks: `useContainerAction`, `useContainerStatus`, `useContainerLogs` |
| [`apps/dashboard/src/components/projects/ContainerControls.tsx`](../apps/dashboard/src/components/projects/ContainerControls.tsx) | Live container status badge (including Docker's unhealthy/starting states), start/stop/restart/remove action buttons, endpoint link, and runtime log viewer |

---

## Database Model Changes

The following fields were added to the `Project` model in `apps/api/prisma/schema.prisma`:

| Column | Type | Description |
|--------|------|-------------|
| `containerId` | `String?` | Docker container ID of the running container |
| `containerStatus` | `String?` | Last known status reported by Docker (e.g. `running`, `exited`) |
| `internalPort` | `Int?` | Host-side port dynamically allocated for this container (8100–8999) |
| `deployedDomain` | `String?` | Traefik hostname (e.g. `{project-name}.{BASE_DOMAIN}`) |
| `deployedAt` | `DateTime?` | Timestamp of the most recent successful deployment |

---

## Environment Variables

| Variable | Default (dev) | Description |
|----------|---------------|-------------|
| `BASE_DOMAIN` | `vexlyx.localhost` | Base domain used to generate Traefik routing hostnames: `{name}.{BASE_DOMAIN}` |
| `DEPLOY_MEMORY_LIMIT` | `512m` | Default memory limit passed to Docker container resource limits |
| `DEPLOY_PORT_RANGE_START` | `8100` | Start of host-port range for dynamic allocation |
| `DEPLOY_PORT_RANGE_END` | `8999` | End of host-port range for dynamic allocation |

---

## API Reference

### `POST /api/projects/:id/deploy`
Triggers container deployment for the built Docker image.
- **Request Body**: `{ domain?: string }` (optional domain override)
- **Response**:
  ```json
  {
    "containerId": "a1b2c3d4e5f6",
    "internalPort": 8142,
    "deployedDomain": "my-app.vexlyx.localhost",
    "containerStatus": "running"
  }
  ```

### `POST /api/projects/:id/container/:action`
Executes a lifecycle action on the project container.
- **URL Parameter**: `action` — `"start"` | `"stop"` | `"restart"` | `"remove"`
- **Response**:
  ```json
  {
    "message": "Container restart completed successfully",
    "containerStatus": "running"
  }
  ```

### `GET /api/projects/:id/container/status`
Returns real-time container status from Docker inspect.
- **Response**:
  ```json
  {
    "containerStatus": "running",
    "containerHealth": "healthy",
    "containerId": "a1b2c3d4e5f6"
  }
  ```

  `containerHealth` is Docker's own `HEALTHCHECK` verdict — `healthy`, `unhealthy` or
  `starting` — and `null` when the image declares no healthcheck. It is read live and not
  stored on `Project`, because `.State.Status` alone only says the process is up: an app
  bound to `127.0.0.1` instead of `$HOST` keeps reporting `running` while its domain returns
  502 (#202).

  What the probe asks comes from the compose template, and every template now asks the
  question Traefik asks: *is something answering on the container's own routable address*.
  That address is what Docker writes next to the container's name in `/etc/hosts`, so the
  probes resolve `os.hostname()` / `gethostname()` / `$HOSTNAME` rather than `127.0.0.1` —
  loopback stays reachable when an app binds only loopback, which is exactly how a 502 site
  used to pass its own healthcheck. They stop at the TCP layer (`net.connect`,
  `socket.create_connection`, `fsockopen`, `nc -z`) because a project has no guaranteed
  index route, and each one uses a tool its image is certain to ship: the Nixpacks images
  carry no `wget`, and busybox resolves `localhost` to `::1` first, so an HTTP-level probe
  could call a correctly bound app unhealthy (#202).

### `GET /api/projects/:id/logs?tail=100`
Fetches runtime logs from the container.
- **Response**:
  ```json
  {
    "logs": "Server listening on port 3000\nConnected to database\n"
  }
  ```

---

## How to Test

1. **Verify Full Build + Deploy Pipeline**:
   - Go to a project with a connected git repository.
   - Click "Deploy" in the Deployments panel.
   - Observe status progression: `QUEUED` → `BUILDING` → `DEPLOYING` → `RUNNING`.
   - Verify that Live Container card updates with container ID, host port, and endpoint domain.

2. **Test Container Lifecycle**:
   - Click "Stop" → container status updates to "Stopped", status badge turns gray.
   - Click "Start" → container restarts, status badge turns green ("Running").
   - Click "Restart" → container restarts smoothly.
   - Click "Runtime Logs" → terminal viewer opens displaying runtime stdout/stderr.
   - Click "Remove" → confirmation dialog opens; on confirm, container and volumes are deleted and status resets to "Not Deployed".
