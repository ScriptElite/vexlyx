# Next.js Runtime Deployment (F2.1)

> **Feature:** F2.1 — Next.js Deployment  
> **Status:** Completed  
> **Package:** System Layer (`build_manager.py`, `docker_manager.py`, `next.yml`), Fastify API (`modules/build`)

---

## 1. Overview

Vexlyx provides zero-config, native runtime deployment for **Next.js** applications. It supports modern Next.js features including:
- **Server-Side Rendering (SSR)** & React Server Components (RSC)
- **API Routes & Route Handlers** (`/api/...`, `app/api/...`)
- **Static Site Generation (SSG)** & Incremental Static Regeneration (ISR)
- **Next.js Image Optimization** (`next/image`)
- **Build Caching**: Preserves `.next/cache`, `node_modules/.cache`, and package manager cache for fast redeployments
- **Dual-Phase Environment Variable Injection**: Inlines `NEXT_PUBLIC_*` variables at build time and injects all encrypted variables at runtime in Docker containers.

---

## 2. Architecture & Execution Flow

```
┌─────────────────────────┐
│ Git Connect / Workspace │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│ Framework Detection Heuristics (`build_manager.py plan`)│
│  - next.config.js / mjs / ts / cjs                     │
│  - package.json -> dependencies.next                    │
│  - lockfile detection (npm, pnpm, yarn, bun)           │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│ Build Phase (`nixpacks build`)                          │
│  - Build command: `npm run build` / lockfile override   │
│  - Build cache key: `vexlyx-<projectId>`                │
│  - Build-time env vars: `--env NEXT_PUBLIC_*=...`       │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│ Deploy Phase (`docker_manager.py deploy`)               │
│  - Template: `system/templates/docker-compose/next.yml` │
│  - HOST=0.0.0.0, HOSTNAME=0.0.0.0, PORT=3000           │
│  - NEXT_TELEMETRY_DISABLED=1                            │
│  - Traefik dynamic router & load balancer              │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Auto-Detection Heuristics

When `nixpacks plan` runs on a project repository, Vexlyx inspects the workspace for Next.js indicators:

1. **Config File Presence**:
   - `next.config.js`
   - `next.config.mjs`
   - `next.config.ts`
   - `next.config.cjs`
2. **Package Dependency**:
   - `package.json` with `"next"` listed under `dependencies` or `devDependencies`
3. **Lockfile & Command Resolution**:
   - `pnpm-lock.yaml` → `pnpm run build` / `pnpm run start`
   - `yarn.lock` → `yarn build` / `yarn start`
   - `bun.lockb` or `bun.lock` → `bun run build` / `bun run start`
   - `package-lock.json` / default → `npm run build` / `npm run start`

When detected:
- Framework is identified as `nextjs` (displayed as `Next.js`).
- Database `project.type` is automatically aligned to `NEXTJS`.
- Build logs record: `[vexlyx] Detected framework: Next.js`.

---

## 4. Build Caching & Environment Variables

### Build Caching
Nixpacks is executed with:
```bash
nixpacks build <projectDir> --name <imageName> --cache-key vexlyx-<projectId>
```
This ensures `.next/cache` and `node_modules/.cache` are preserved across redeployments, cutting build times by 50-80% on subsequent commits.

### Environment Variable Injection
Next.js distinguishes between client-side build-time variables and runtime server-side variables:
1. **Build Time**: All decrypted project environment variables (especially `NEXT_PUBLIC_*`) are passed via `--env KEY=VALUE` to `nixpacks build`.
2. **Runtime**: All environment variables are injected into the container via the generated `docker-compose.yml` `environment:` block.

---

## 5. Container & Compose Template (`next.yml`)

Next.js 13+ servers bind to `localhost` by default unless `HOSTNAME=0.0.0.0` or `HOST=0.0.0.0` is provided. The `next.yml` template ensures proper container network bridging:

```yaml
services:
  app:
    image: "{{image_name}}"
    restart: unless-stopped
    environment:
      PORT: "{{container_port}}"
      HOST: "0.0.0.0"
      HOSTNAME: "0.0.0.0"
      NODE_ENV: production
      NEXT_TELEMETRY_DISABLED: "1"
{{env_block}}
    ports:
      - "{{host_port}}:{{container_port}}"
    deploy:
      resources:
        limits:
          memory: "{{memory_limit}}"
    healthcheck:
      test: ["CMD", "node", "-e", "const socket=require('net').connect({{container_port}},require('os').hostname(),()=>{socket.end();process.exit(0)});socket.on('error',()=>process.exit(1))"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.{{service_name}}.rule=Host(`{{hostname}}`)"
      - "traefik.http.routers.{{service_name}}.entrypoints=web"
      - "traefik.http.services.{{service_name}}.loadbalancer.server.port={{container_port}}"
```

The probe uses Node's built-in TCP client, which is guaranteed to exist in a
Next.js runtime image. It does not require optional utilities such as `wget` or
`curl`; missing those utilities would otherwise mark a working container as
unhealthy and cause Traefik to remove its route.

---

## 6. How to Test

Run the automated test suite:
```bash
python tests/test_nextjs_runtime.py
```

Expected output:
```
=== Running Next.js Runtime (F2.1) Automated Test Suite ===
Testing Next.js detection via config files...
  [PASS] Auto-detected via next.config.js
  [PASS] Auto-detected via next.config.mjs
  [PASS] Auto-detected via next.config.ts
  [PASS] Auto-detected via next.config.cjs
Testing Next.js detection via package.json dependencies...
  [PASS] Auto-detected via package.json dependencies
Testing package manager lockfile resolution for Next.js...
  [PASS] pnpm-lock.yaml -> build: 'pnpm run build', start: 'pnpm run start'
  [PASS] yarn.lock -> build: 'yarn build', start: 'yarn start'
  [PASS] bun.lockb -> build: 'bun run build', start: 'bun run start'
  [PASS] package-lock.json -> build: 'npm run build', start: 'npm run start'
Testing next.yml template rendering & parameters...
  [PASS] next.yml rendered correctly with all variables & labels

[SUCCESS] ALL NEXT.JS RUNTIME TESTS PASSED SUCCESSFULLY!
```
