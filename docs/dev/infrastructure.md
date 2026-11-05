# Infrastructure — Docker Compose Dev Environment

`docker-compose.yml` originally ran three services (PostgreSQL, Redis, Traefik); it now runs nine, one per infrastructure piece the panel depends on:

| Service | Image | Purpose |
|---|---|---|
| `postgres` | `postgres:16-alpine` | Primary database (see [Database](database.md)) |
| `mysql` | `mysql:8.0` | Optional database type for [user-provisioned databases](database-provisioning.md) |
| `redis` | `redis:7-alpine` | Sessions, caching, BullMQ queues |
| `adminer` | `adminer:4` | Dev-only raw DB browser — gated behind `--profile debug` in production |
| `traefik` | `traefik:v3.6` | Reverse proxy, automatic Let's Encrypt HTTPS, per-domain dynamic routing |
| `coredns` | `coredns/coredns:1.11.3` | Authoritative DNS for domains in [Hosted DNS mode](dns-management.md) |
| `postfix` | `vexlyx-postfix` (custom) | Outbound/inbound SMTP — see [Postfix](email/postfix.md) |
| `dovecot` | `vexlyx-dovecot` (custom) | IMAP + mailbox storage — see [Dovecot](email/dovecot.md) |
| `roundcube` | `roundcube/roundcubemail:1.6.18-apache` | Webmail — see [Webmail](email/webmail.md) |

All services have health checks and persistent volumes. Two more images are built locally at install time rather than pulled — `vexlyx-ufw-helper` (see [Firewall](firewall.md)) and `vexlyx-php-fpm` (see [No-build PHP hosting](no-build-php-hosting.md)) — see `system/scripts/install/steps/10-images.sh`.

## Quick Start

```bash
# Start all infrastructure services
docker-compose up -d

# Verify everything is healthy
docker-compose ps

# Follow logs from all services
docker-compose logs -f

# Stop services (data persists)
docker-compose down

# Stop and destroy all data
docker-compose down -v
```

## Services

### PostgreSQL 16

| Property | Value |
|----------|-------|
| Image | `postgres:16-alpine` |
| Port | `5432` (bound to `127.0.0.1` only) |
| User | `vexlyx` |
| Password | `vexlyx_dev` |
| Database | `vexlyx_dev` |
| Volume | `vexlyx_postgres_data` |

**Connection string:** `postgresql://vexlyx:vexlyx_dev@localhost:5432/vexlyx_dev`

The Postgres, MySQL and Redis dev ports are published on loopback only (`127.0.0.1`), because their dev credentials are well known and must not be reachable from the LAN (#56). The Postgres and MySQL passwords default to the dev values but can be overridden with `POSTGRES_PASSWORD`, `MYSQL_ROOT_PASSWORD` and `MYSQL_PASSWORD` in a root `.env`; keep `apps/api/.env` in sync. MySQL is pinned to `mysql:8.0`, where `--default-authentication-plugin=mysql_native_password` is still required for older client drivers; it must be revisited before moving to 8.4+.

### Redis 7

| Property | Value |
|----------|-------|
| Image | `redis:7-alpine` |
| Port | `6379` (bound to `127.0.0.1` only in development; not published in production) |
| Authentication | `requirepass` from `REDIS_PASSWORD` (dev default `vexlyx_dev`; production requires a generated value) |
| Max memory | `256mb` |
| Eviction | `noeviction` — `--maxmemory-policy` on the `redis-server` command line in `docker-compose.yml`. Sessions, queued jobs and single-use tokens must never be silently evicted, so a full instance refuses writes instead of dropping keys |
| Persistence | AOF (`appendonly yes`) plus the default RDB snapshot schedule (`save 3600 1 300 100 60 10000`), which the command line does not override |
| Volume | `vexlyx_redis_data` |

**Connection string:** `redis://:vexlyx_dev@localhost:6379` (development). Production uses `redis://:<REDIS_PASSWORD>@redis:6379`, set by `docker-compose.prod.yml`.

**Usage in Vexlyx:**
- **Sessions** — the custom session plugin (`apps/api/src/plugins/auth.ts`, not a third-party auth library) stores signed session tokens here, keyed `session:<id>`, with a 24-hour TTL
- **Caching** — one entry: the 6-hour "is a newer Vexlyx release available" lookup keyed `system:update-info` (`apps/api/src/modules/system/update-service.ts:11-12`). API responses are not cached here
- **Queues** — BullMQ background job processing (see below)
- **Locks and one-shot values** — a scheduled-task run claims a per-task lock so it never overlaps its predecessor (`apps/api/src/modules/scheduled-tasks/service.ts:371`), each GitHub webhook delivery is claimed once for 24 hours under `github:webhook-delivery:<id>` (`apps/api/src/modules/webhooks/delivery.ts:3-18`), and GitHub's single-use OAuth `state`, 2FA challenge tokens and password-reset send throttles are short-TTL Redis values
- **Rate limiting** — not in Redis. `@fastify/rate-limit` runs on its default in-process store (`apps/api/src/modules/auth/routes.ts:20-24`), so the login and registration counters are per-process and start over when the API restarts

**Test connectivity:**
```bash
docker exec vexlyx-redis sh -c 'REDISCLI_AUTH="$REDIS_PASSWORD" redis-cli ping'
# Returns: PONG
```

### Traefik v3

| Property | Value |
|----------|-------|
| Image | `traefik:v3.6` (bumped from `v3.4` — see the [installer reference](installer.md#bugs-found-during-the-real-install-and-their-fixes) for why) |
| HTTP/HTTPS Ports | `80` / `443` |
| Dashboard | `http://localhost:8080` |
| Docker provider | Enabled (`exposedByDefault: false`) |

**Dashboard:** Open `http://localhost:8080` in your browser to view the Traefik dashboard. This shows all configured routers, services, and middlewares.

**Configuration files:**
- Static config: `docker/traefik/traefik.yml` (dev) / `traefik.prod.yml.tmpl` (production)
- Dynamic configs: `docker/traefik/dynamic/` — one YAML file per verified custom domain
  (`domain-{domainId}.yml`, written by `DomainService.syncTraefikRouter()`) plus a couple of
  static routes (e.g. webmail). See [Custom domains](domains.md) and
  [Domain routing](domain-routing.md).

## Redis Client (API)

The Redis client is registered as a Fastify plugin and available on every request via `app.redis`.

**File:** `apps/api/src/config/redis.ts`

```ts
// Access Redis from any route handler
app.get("/example", async (request, reply) => {
  await app.redis.set("key", "value");
  const value = await app.redis.get("key");
  return { value };
});
```

**Configuration:**
- Uses `ioredis` with `maxRetriesPerRequest: null` (required by BullMQ)
- Lazy connect — doesn't block startup if Redis is temporarily unavailable
- Graceful disconnect on server shutdown

## BullMQ Queues (API)

Background job queues are registered as a Fastify plugin and available via `app.queues`.

**File:** `apps/api/src/config/queue.ts`

### Current Queues

| Queue Name | Worker | Purpose |
|------------|--------|---------|
| Build queue | Yes | Nixpacks/Docker build + deploy jobs, one per push or manual trigger — see [Nixpacks build integration](build-system.md) |
| Backup queue | Yes | Scheduled (daily, cron-configurable) and manual backup snapshots — see [Backup system](backup-system.md) |
| Cleanup queue | Yes | Scheduled and manual Docker image/container pruning — see [Docker cleanup](docker-cleanup.md) |
| Metrics queue | Yes | 60-second resource-usage snapshots — see [Monitoring](monitoring.md) |

Each is registered the same way the original `test-ping` example queue was — see `apps/api/src/modules/{build,backups,cleanup,monitoring}/routes.ts` for the current call sites.

### Adding a New Queue

1. Open `apps/api/src/config/queue.ts`
2. Inside `queuePlugin`, create a new queue and worker:

```ts
const deployQueue = createQueue("deploy");
queues.set("deploy", deployQueue);

const deployWorker = createWorker(
  "deploy",
  async (job) => {
    // Process deployment job
    app.log.info({ jobId: job.id, data: job.data }, "Processing deployment");
  },
  app,
);
workers.push(deployWorker);
```

3. Enqueue a job from any route:

```ts
app.post("/deploy", async (request, reply) => {
  const queue = app.queues.get("deploy");
  await queue?.add("start-deploy", { projectId: "abc123" });
  return { status: "queued" };
});
```

## System Script Time Limits (#52)

Every external command run by `system/python/*.py` is time-limited, so a hung `docker compose`, `nixpacks`, `git`, `mysqldump` or `chpasswd` cannot wedge a build/deploy request or a BullMQ job (and leak an orphaned process) forever. There are two layers:

| Layer | Where | Behaviour |
|-------|-------|-----------|
| Script (the real limit) | `run_bounded()` and `stream_with_deadline()` in `docker_manager.py` / `build_manager.py`; `timeout=` on the calls in `git`, `backup`, `postfix`, `sftp` and `service_status` managers | Kills the actual child process and reports `COMMAND_TIMEOUT` as a normal script error |
| API backstop | `watchChildTimeout()` + `PYTHON_SCRIPT_TIMEOUT_MS` in `apps/api/src/utils/processWatchdog.ts`, armed at every direct `spawn(getPythonBin(), …)` | Rejects with `SCRIPT_TIMEOUT` (504) and `SIGKILL`s the script if it is still running a little after its own limit |

Why both: killing only the Python script would orphan the `docker`/`nixpacks` grandchild, so the script has to enforce its own limits; the API backstop covers a script that is itself stuck (e.g. blocked reading a pipe).

**Killing the whole tree.** A deadline that only kills the direct child is not enough: a grandchild (what `nixpacks` or `docker` start) can survive and keep the output pipe open, so the reader would still block. Every bounded command and every streamed build/compose run therefore starts in its own process group (`start_new_session`, or `CREATE_NEW_PROCESS_GROUP` on Windows) and the deadline kills the group (`kill_process_tree`: `killpg`, or `taskkill /T /F` on Windows). `database_manager.py` applies the same rule to `docker exec` (120 s). Managers that call `subprocess.run(..., timeout=)` directly (`sftp`, `backup`, `service_status`, `postfix`, `git`) turn a `TimeoutExpired` into a normal `COMMAND_TIMEOUT` error instead of a traceback.

**Coverage.** The backstop is armed at every launch of a Python manager script: the build, deploy, database, dockerfile, git, sftp and wordpress services, and also backups (2 h), cleanup (22 min), firewall (3 min), monitoring (90 s), service status (5 min), SSL (15 min) and the postfix/dovecot/webmail managers (5 min). A guard test (`processWatchdog.test.ts`) recognises a launch whether the interpreter is written inline or held in a variable (`pythonBin`, `pythonExe`), so a new launcher without a watchdog fails the suite. The only unbounded stream is `logs/service.ts` (`docker compose logs --follow`), which has its own kill on client disconnect.

**Cleanup steps are best-effort.** Commands that clean up after a build (`docker rm`, `docker rmi` during static extraction) use `run_bounded(..., fatal=False)`: a timeout is logged and the next step still runs, instead of ending the script and skipping image removal.

**Backstop sizing.** The API backstop for a script must cover the *sum* of the commands that script runs sequentially, not just one command's limit: static output extraction runs `docker create`, up to four `docker cp` attempts and two cleanups (120 s each), so its backstop (`staticExtract`) is 900 s. A script-side limit still applies to each command individually.

Limits (seconds, script side): quick docker inspect/ps/network 30, one-shot logs 60, `docker system df` 120, prune 600, `docker compose up/start/stop/down` 1800, `nixpacks plan` 120, docker create/cp/rm 120, `docker build`/`nixpacks build` 3600, mysqldump/import 1800, git clone/fetch 900, sftp user commands 60, service status 30. The API backstops are each slightly higher (`PYTHON_SCRIPT_TIMEOUT_MS`).

Intentionally unbounded: `docker compose logs --follow` (`logs_follow` / `logs/service.ts`) is a live stream that ends when the client disconnects.

Raise a limit only in code (the constants are at the top of each manager and in `processWatchdog.ts`) — there are no env vars for them on purpose. Tests: `tests/test_subprocess_timeouts.py`, `apps/api/src/utils/processWatchdog.test.ts`.

## Environment Variables

`DATABASE_URL` and `REDIS_URL` are the two this doc originally covered; every other infrastructure
service (MySQL, mail, webmail, firewall helper, DNS nameservers, ...) has its own env vars in the
same schema now — see [API Setup](api-setup.md#environment-variables) or
`apps/api/src/config/env.ts` directly for the current full list.

## How to Extend

- **Add a Docker service:** Add to `docker-compose.yml`, include health check and persistent volume
- **Add a Traefik route:** Create a YAML file in `docker/traefik/dynamic/`
- **Add a BullMQ queue:** Follow the pattern in `queue.ts` — create queue + worker, add to maps
- **Use Redis for caching:** Use `app.redis.set/get` with TTL via `app.redis.setex(key, ttl, value)`
