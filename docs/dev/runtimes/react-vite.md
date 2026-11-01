# React (Vite) Runtime Deployment (F2.3)

> **Feature:** F2.3 — React (Vite) Static Deployment  
> **Status:** Completed  
> **Package:** System Layer (`build_manager.py`, `docker_manager.py`, `static.yml`), Fastify API (`modules/build`)

---

## 1. Overview

Vexlyx provides zero-config, native runtime deployment for **React applications built with Vite** and modern static Single Page Applications (SPAs). It supports:
- **Zero-Config Framework Auto-Detection**: Detects `vite.config.*` files and package dependencies (`vite`, `react`, `@vitejs/plugin-react`, `@vitejs/plugin-react-swc`).
- **SPA Client-Side Routing Fallback**: Configures high-performance static web serving (Caddy/Nginx) with `try_files {path} /index.html`, ensuring client routers (React Router, TanStack Router) work flawlessly on page refresh.
- **Lockfile & Package Manager Resolution**: Auto-selects build commands for `pnpm`, `yarn`, `bun`, and `npm`.
- **Node.js Version Pinning**: Respects `.nvmrc`, `.node-version`, `package.json` (`engines.node`), or project environment variables (`NODE_VERSION` / `NIXPACKS_NODE_VERSION`).
- **Build-Time Environment Variable Injection**: Injects all project environment variables (especially `VITE_*`) during the `nixpacks build` phase, embedding them into the static bundle.
- **Traefik Reverse-Proxy Integration**: Automatically provisions routing, healthchecks, and internal container port `80` load balancing.

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
│  - vite.config.js / ts / mjs / cjs / mts / cts              │
│  - package.json -> vite + react / @vitejs/plugin-react      │
│  - Lockfile detection (npm, pnpm, yarn, bun)                │
│  - Node version: .nvmrc / .node-version / engines.node      │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Build Phase (`nixpacks build`)                              │
│  - Build command: `npm run build` / lockfile override       │
│  - Output directory: `dist/`                                │
│  - Build cache key: `vexlyx-<projectId>`                    │
│  - Build-time env vars: `--env VITE_*=...`                  │
└────────────┬────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│ Deploy Phase (`docker_manager.py deploy`)                   │
│  - Template: `system/templates/docker-compose/static.yml`   │
│  - PORT=80, HOST=0.0.0.0                                    │
│  - Caddy static web server with `try_files {path} /index.html`
│  - Traefik dynamic router & load balancer on port 80        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Auto-Detection Heuristics

When `build_manager.py plan` executes, Vexlyx inspects the workspace for Vite configurations and framework dependencies:

1. **Config File Presence**:
   - `vite.config.js`, `vite.config.ts`, `vite.config.mjs`, `vite.config.cjs`, `vite.config.mts`, `vite.config.cts`
2. **Framework Differentiation**:
   - **React**: `"react"`, `"react-dom"`, `"@vitejs/plugin-react"`, or `"@vitejs/plugin-react-swc"` in `dependencies` / `devDependencies` → Framework: `react` (displayed as `React (Vite)`), Project Type: `REACT`.
   - **Vue**: `"vue"`, `"@vitejs/plugin-vue"` → Framework: `vue` (displayed as `Vue (Vite)`), Project Type: `STATIC`.
   - **Svelte**: `"svelte"`, `"@sveltejs/vite-plugin-svelte"` → Framework: `svelte` (displayed as `Svelte (Vite)`), Project Type: `STATIC`.
   - **Vanilla / Multi-Page Vite**: Plain Vite without React/Vue/Svelte → Framework: `vite` (displayed as `Vite (Static)`), Project Type: `STATIC`.
3. **Lockfile & Command Resolution**:
   - `pnpm-lock.yaml` → `pnpm run build` (install: `pnpm install`)
   - `yarn.lock` → `yarn build` (install: `yarn install`)
   - `bun.lockb` or `bun.lock` → `bun run build` (install: `bun install`)
   - `package-lock.json` / default → `npm run build` (install: `npm ci` / `npm install`)
4. **Start Command Resolution**:
   - If Nixpacks provides a Caddy static web server start command, it is used.
   - If `package.json` contains a `"start"` script, it uses the package manager start command.
   - Otherwise, it falls back to `npx --yes serve -s dist -l 80` to reliably serve the built static assets on port 80.

When detected:
- Framework is identified and displayed in build logs.
- Database `project.type` is automatically aligned to `REACT` or `STATIC`.
- Build logs record: `[vexlyx] Detected framework: [Display Name]`.

---

## 4. SPA Client-Side Routing & Web Server

Vite builds static assets into the `dist/` directory. For client-side Single Page Applications (React Router, etc.), navigation to subpaths (e.g., `/dashboard`, `/settings`, `/profile`) must serve `index.html` when requested directly or refreshed.

Nixpacks provisions a static web server (Caddy) with the following configuration:

```caddy
:{$PORT:3000} {
    root * ../app/{$NIXPACKS_SPA_OUTPUT_DIR}
    encode gzip
    file_server
    try_files {path} /index.html
}
```

This guarantees:
1. Direct asset requests (`/assets/index-abc.js`, `/favicon.svg`, `.css`) are served directly.
2. Missing non-file paths are routed to `/index.html` with status 200, allowing the client-side router to mount the appropriate route.
3. Responses are compressed with gzip for optimal performance.

---

## 5. Build-Time Environment Variable Injection (`VITE_*`)

Vite processes environment variables at **build time** (`npm run build`). Only variables prefixed with `VITE_` (or custom configured prefixes) are exposed to client bundle code via `import.meta.env.VITE_*`.

Vexlyx handles this transparently:
1. **Decryption**: Before triggering `nixpacks build`, all project environment variables are fetched and decrypted by `EnvService`.
2. **Build-Time Injection**: Every variable is forwarded to Nixpacks via `--env KEY=VALUE`.
3. **Runtime Injection**: All variables are also placed in the container's `docker-compose.yml` environment block for server-rendered or API-proxied static workflows.

---

## 6. Container & Compose Template (`static.yml`)

The static container runs with internal port `80`:

```yaml
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
    healthcheck:
      test: ["CMD-SHELL", "nc -z -w 3 $${HOSTNAME} 80"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
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

## 7. How to Test

Run the automated test suite:
```bash
python tests/test_react_runtime.py
```

Expected output:
```
=== Running React (Vite) Runtime (F2.3) Automated Test Suite ===
Testing React (Vite) detection via config files...
  [PASS] Auto-detected via vite.config.js
  [PASS] Auto-detected via vite.config.ts
  [PASS] Auto-detected via vite.config.mjs
  [PASS] Auto-detected via vite.config.cjs
  [PASS] Auto-detected via vite.config.mts
  [PASS] Auto-detected via vite.config.cts
Testing React (Vite) detection via package.json dependencies...
  [PASS] Auto-detected via deps: ['vite', 'react']
  [PASS] Auto-detected via deps: ['@vitejs/plugin-react', 'react']
  [PASS] Auto-detected via deps: ['@vitejs/plugin-react-swc', 'react-dom']
Testing package manager lockfile resolution for React (Vite)...
  [PASS] pnpm-lock.yaml -> build: 'pnpm run build'
  [PASS] yarn.lock -> build: 'yarn build'
  [PASS] bun.lockb -> build: 'bun run build'
  [PASS] bun.lock -> build: 'bun run build'
  [PASS] package-lock.json -> build: 'npm run build'
Testing Node.js version detection (.nvmrc, .node-version, engines.node, env vars)...
  [PASS] .nvmrc 'v20.12.0' -> 20.12
  [PASS] .node-version '18.19.0' -> 18.19
  [PASS] package.json engines.node '>=22.0.0' -> 22.0
  [PASS] env_vars NODE_VERSION / NIXPACKS_NODE_VERSION -> respected
Testing plain static HTML website auto-detection...
  [PASS] Plain static HTML/CSS site detected -> framework: 'static', type: 'STATIC'
Testing static.yml template rendering & Traefik configuration...
  [PASS] static.yml rendered correctly with port 80 and Traefik load balancer
Testing Nixpacks Vite plan & Caddy SPA client-side fallback...
  [PASS] Nixpacks Caddyfile configured with SPA fallback 'try_files {path} /index.html' on 'dist/'

[SUCCESS] ALL REACT (VITE) RUNTIME TESTS PASSED SUCCESSFULLY!
```

---

## 8. How to Extend

- **Custom Output Directory**: If a Vite app outputs to `build/` or `out/` instead of `dist/`, set the environment variable `NIXPACKS_SPA_OUTPUT_DIR=build` in the project settings.
- **Custom Base Path**: For apps hosted on sub-paths (e.g. `base: '/app/'` in `vite.config.ts`), Traefik router rules can be mapped to path prefixes in future domain updates.
- **Plain Static HTML Websites**: Plain HTML/CSS sites (without `package.json`) are automatically detected as `static` (`STATIC` project type) and served identically with port 80 web server.
