# FEATURES.md

> **Project:** Vexlyx
> **Type:** Open-Source Hybrid Hosting Control Panel
> **Last Updated:** 2026-09-09

---

## How to Use This File

This document is the **single source of truth** for all Vexlyx features. 

- **For You:** Before asking Claude to work on a feature, copy the relevant section from this file and paste it into your prompt.
- **For Claude/AI:** Read this file first to understand the project state, then read the specific feature section you're asked to implement.
- **For Other Devs:** This file shows exactly what's built, what's pending, and where to start.

**Status Legend:**
- `🔴 NOT STARTED` — Feature not yet implemented
- `🟡 IN PROGRESS` — Currently being worked on
- `🟢 COMPLETED` — Feature implemented and tested
- `⚪ PLANNED` — Planned for future but not prioritized

---

## Project Status Dashboard

| Phase | Status | Progress |
|-------|--------|----------|
| Phase 0: Foundation | 🟢 COMPLETED | 100% (7/7) |
| Phase 1: Project Deployment | 🟢 COMPLETED | 100% (8/8) |
| Phase 2: Multi-Runtime Support | 🟢 COMPLETED | 100% (8/8) |
| Phase 3: Domain & DNS | 🟢 COMPLETED | 100% (5/5) |
| Phase 4: Email Server | 🟢 COMPLETED | 100% (8/8) |
| Phase 5: System & Administration | 🟡 IN PROGRESS | 85% (29/34) |
| Phase 6: Ecosystem & Launch | 🟡 IN PROGRESS | 67% (2/3) |

**Overall Completion:** 92% (67/73 features)

---

## Phase 0: Foundation

### F0.1 — Monorepo Setup
**Status:** 🟢 COMPLETED

**Description:**
Initialize the Vexlyx monorepo using Turborepo with three workspaces: `apps/dashboard` (Next.js), `apps/api` (Fastify), and `packages/shared` (shared types and Zod schemas). Configure TypeScript, ESLint, Prettier, and Git hooks.

**Acceptance Criteria:**
- [x] `pnpm-workspace.yaml` configured with three packages
- [x] Turborepo pipeline configured for `build`, `dev`, `lint`, `test`
- [x] Root `package.json` with shared dev dependencies
- [x] `.gitignore` excludes `node_modules`, `.turbo`, `dist`, `.env`
- [x] README.md with setup instructions

**Test Plan:**
1. Run `pnpm install` — all dependencies install without errors
2. Run `pnpm dev` — Turborepo starts all apps in parallel
3. Run `pnpm build` — all packages build successfully
4. Run `pnpm lint` — no linting errors across all packages

**Developer Docs:**
- **Location:** `docs/dev/monorepo.md`
- **Contents:** Workspace structure, dependency management, adding new packages, build pipeline explanation

**Files to Create:**
- `package.json` (root)
- `pnpm-workspace.yaml`
- `turbo.json`
- `.gitignore`
- `README.md`
- `tsconfig.json` (root)

---

### F0.2 — Next.js Dashboard Scaffold
**Status:** 🟢 COMPLETED

**Description:**
Set up the Next.js 15 dashboard app with App Router, TypeScript, Tailwind CSS 4, and shadcn/ui. Configure the basic layout with sidebar navigation, header, and main content area.

**Acceptance Criteria:**
- [x] Next.js 15 installed with App Router
- [x] Tailwind CSS 4 configured with custom theme tokens
- [x] shadcn/ui initialized with base components (Button, Card, Separator, Sheet, Skeleton)
- [x] Root layout with sidebar + header structure
- [x] Dashboard home page with placeholder widgets
- [x] Dark mode support via `next-themes`
- [x] Responsive design (mobile sidebar toggle)

**Test Plan:**
1. `pnpm dev` starts dashboard on `http://localhost:3000`
2. Sidebar navigation renders on desktop
3. Mobile hamburger menu toggles sidebar
4. Dark mode toggle works across all pages
5. No console errors or hydration mismatches

**Developer Docs:**
- **Location:** `docs/dev/dashboard-setup.md`
- **Contents:** Component architecture, shadcn/ui usage guide, theme system, adding new pages

**Files to Create:**
- `apps/dashboard/package.json`
- `apps/dashboard/next.config.js`
- `apps/dashboard/tailwind.config.ts`
- `apps/dashboard/app/layout.tsx`
- `apps/dashboard/app/page.tsx`
- `apps/dashboard/components/ui/*` (shadcn components)
- `apps/dashboard/components/layout/Sidebar.tsx`
- `apps/dashboard/components/layout/Header.tsx`
- `apps/dashboard/lib/utils.ts`

---

### F0.3 — Fastify API Scaffold
**Status:** 🟢 COMPLETED

**Description:**
Set up the Fastify backend API with TypeScript, Zod validation, and a modular plugin architecture. Configure health check endpoint, error handling, and logging.

**Acceptance Criteria:**
- [x] Fastify 5.x installed with TypeScript
- [x] Zod for runtime validation
- [x] Modular route structure (`src/modules/*/routes.ts`)
- [x] Global error handler with consistent response format
- [x] Health check endpoint `GET /health` returns `{ status: "ok" }`
- [x] Pino logger configured
- [x] Environment variable validation via Zod

**Test Plan:**
1. `pnpm dev` starts API on `http://localhost:5000`
2. `GET /health` returns `200 OK` with JSON response
3. Invalid route returns `404` with consistent error shape
4. Server error returns `500` with error code and message

**Developer Docs:**
- **Location:** `docs/dev/api-setup.md`
- **Contents:** Route registration pattern, error handling conventions, adding new modules, environment variables

**Files to Create:**
- `apps/api/package.json`
- `apps/api/src/index.ts`
- `apps/api/src/config/env.ts`
- `apps/api/src/plugins/error-handler.ts`
- `apps/api/src/modules/health/routes.ts`
- `apps/api/tsconfig.json`

---

### F0.4 — Prisma Schema & Database
**Status:** 🟢 COMPLETED

**Description:**
Design and implement the complete Prisma schema for Vexlyx. Set up PostgreSQL via Docker Compose for local development. Run initial migration and generate Prisma Client.

**Acceptance Criteria:**
- [x] Complete Prisma schema with all models (User, Project, Domain, Database, Mailbox, Deployment, etc.)
- [x] All enums defined (Role, ProjectType, Status, etc.)
- [x] Relations properly configured with foreign keys
- [x] Docker Compose includes PostgreSQL 16 service
- [x] Initial migration created and applied
- [x] Prisma Client generated and exported from `apps/api/src/config/database.ts`
- [x] Seed script creates admin user for development

**Test Plan:**
1. `docker-compose up postgres` starts PostgreSQL
2. `pnpm db:migrate` applies all migrations
3. `pnpm db:seed` creates admin user
4. `pnpm db:studio` opens Prisma Studio showing all tables
5. Querying `User` table returns seeded admin user

**Developer Docs:**
- **Location:** `docs/dev/database.md`
- **Contents:** Schema overview, migration workflow, seeding, querying patterns, adding new models

**Files Created:**
- `apps/api/prisma/schema.prisma`
- `apps/api/prisma/migrations/`
- `apps/api/prisma/seed.ts`
- `apps/api/src/config/database.ts`
- `docker-compose.yml` (root)

---

### F0.5 — Redis & Docker Compose Dev Environment
**Status:** 🟢 COMPLETED

**Description:**
Set up the complete Docker Compose development environment with PostgreSQL, Redis, and Traefik. Configure Redis for sessions, caching, and BullMQ queues.

**Acceptance Criteria:**
- [x] Docker Compose includes PostgreSQL 16, Redis 7, and Traefik v3 services
- [x] Redis client configured in API with connection pooling
- [x] Redis used for session storage
- [x] BullMQ configured for background job processing
- [x] Traefik dashboard accessible on `localhost:8080`
- [x] Persistent volumes for PostgreSQL and Redis data
- [x] Health checks for all services

**Test Plan:**
1. `docker-compose up -d` starts all services
2. `redis-cli ping` returns `PONG`
3. BullMQ queue can add and process a test job
4. Traefik dashboard shows services on `http://localhost:8080`
5. Data persists after `docker-compose down && docker-compose up`

**Developer Docs:**
- **Location:** `docs/dev/infrastructure.md`
- **Contents:** Docker services overview, Redis usage patterns, BullMQ queue setup, Traefik routing basics

**Files Created:**
- `docker-compose.yml`
- `apps/api/src/config/redis.ts`
- `apps/api/src/config/queue.ts`
- `apps/api/src/config/env.ts` (modified — added `REDIS_URL`)
- `docker/traefik/traefik.yml`
- `docker/traefik/dynamic/`

---

### F0.6 — Authentication System
**Status:** 🟢 COMPLETED

**Description:**
Implement complete authentication with custom session-based auth (Lucia Auth was deprecated March 2025). Support email/password registration and login. Use Argon2id for password hashing. Session-based auth with HTTP-only cookies stored in Redis.

**Acceptance Criteria:**
- [x] `POST /api/auth/register` — creates user, hashes password with Argon2id
- [x] `POST /api/auth/login` — validates credentials, creates session
- [x] `POST /api/auth/logout` — destroys session
- [x] `GET /api/auth/me` — returns current user
- [x] Session stored in Redis with TTL
- [x] CSRF protection via SameSite=Lax cookies
- [x] Rate limiting: 5 login attempts per 15 minutes per IP
- [x] Frontend login/register forms with validation
- [x] Protected routes redirect to login
- [x] Auth hook (`useAuth`) in React

**Test Plan:**
1. Register new user → user created in database with hashed password
2. Login with correct credentials → session cookie set, redirected to dashboard
3. Login with wrong password → `401` error, rate limit counter increments
4. Access `/dashboard` without auth → redirect to `/login`
5. Logout → session destroyed, redirect to `/login`
6. `GET /api/auth/me` with valid session → returns user object
7. `GET /api/auth/me` without session → returns `401`

**Developer Docs:**
- **Location:** `docs/dev/authentication.md`
- **Contents:** Custom auth setup, session flow, password hashing, protected routes, frontend auth hooks

**Files Created:**
- `apps/api/src/modules/auth/routes.ts`
- `apps/api/src/modules/auth/service.ts`
- `apps/api/src/modules/auth/schema.ts`
- `apps/api/src/plugins/auth.ts`
- `apps/dashboard/src/app/(auth)/layout.tsx`
- `apps/dashboard/src/app/(auth)/login/page.tsx`
- `apps/dashboard/src/app/(auth)/register/page.tsx`
- `apps/dashboard/src/components/auth/LoginForm.tsx`
- `apps/dashboard/src/components/auth/RegisterForm.tsx`
- `apps/dashboard/src/lib/api.ts`
- `apps/dashboard/src/hooks/useAuth.ts`


---

### F0.7 — Shared Package (Types & Schemas)
**Status:** 🟢 COMPLETED

**Description:**
Create the shared package containing Zod schemas and TypeScript types used by both frontend and backend. This ensures type safety across the monorepo.

**Acceptance Criteria:**
- [x] Zod schemas for all API inputs (auth, projects, domains, etc.)
- [x] TypeScript types inferred from Zod schemas
- [x] Package builds and exports correctly
- [x] Both dashboard and api import from `@vexlyx/shared`
- [x] No circular dependencies

**Test Plan:**
1. `pnpm build` in `packages/shared` succeeds
2. Import `LoginSchema` from `@vexlyx/shared` in both apps
3. TypeScript compiles without errors in both apps
4. Zod schema validates correct and incorrect data properly

**Developer Docs:**
- **Location:** `docs/dev/shared-package.md`
- **Contents:** Adding new schemas, type inference, validation patterns

**Files Created:**
- `packages/shared/src/schemas/auth.ts`
- `packages/shared/src/types/index.ts`
- `packages/shared/src/index.ts` (updated)
- `packages/shared/package.json` (updated — added zod peer dep)

**Files Modified:**
- `apps/api/src/modules/auth/schema.ts` (now re-exports from `@vexlyx/shared`)
- `apps/dashboard/src/hooks/useAuth.ts` (imports `User` from `@vexlyx/shared`)

---

## Phase 1: Project Deployment

### F1.1 — Project CRUD API
**Status:** 🟢 COMPLETED

**Description:**
Build the complete project management API. Users can create, read, update, and delete hosting projects. Each project has a name, type, git URL, and status.

**Acceptance Criteria:**
- [x] `GET /api/projects` — list user's projects with pagination
- [x] `POST /api/projects` — create new project
- [x] `GET /api/projects/:id` — get single project details
- [x] `PUT /api/projects/:id` — update project settings
- [x] `DELETE /api/projects/:id` — delete project and cleanup resources
- [x] Projects are scoped to the authenticated user
- [x] Validation via Zod schemas from shared package
- [x] Soft delete (mark as deleted, cleanup async)

**Test Plan:**
1. Create project → returns 201 with project data
2. List projects → returns only current user's projects
3. Get project by ID → returns correct project
4. Update project name → returns updated project
5. Delete project → returns 204, project marked deleted
6. Access other user's project → returns 403

**Developer Docs:**
- **Location:** `docs/dev/projects-api.md`

**Files Created:**
- `apps/api/src/modules/projects/routes.ts`
- `apps/api/src/modules/projects/service.ts`
- `apps/api/src/modules/projects/schema.ts`
- `packages/shared/src/schemas/projects.ts`

**Files Modified:**
- `packages/shared/src/index.ts` (exports project schemas/types)
- `packages/shared/src/types/index.ts` (added Project, ProjectType, ProjectStatus, PaginatedProjects)
- `apps/api/prisma/schema.prisma` (added `deletedAt` to Project)
- `apps/api/src/index.ts` (registered `/api/projects` routes)

---

### F1.2 — Project Dashboard UI
**Status:** 🟢 COMPLETED

**Description:**
Build the project management interface in the dashboard. List view with cards/table, create project modal, and project detail page.

**Acceptance Criteria:**
- [x] `/projects` page lists all user projects in a card grid
- [x] "New Project" button opens creation modal
- [x] Modal has form: name, type (select), git URL (optional)
- [x] Project cards show status badge, type icon, last deployed
- [x] Clicking card navigates to `/projects/[id]`
- [x] Empty state for new users
- [x] Real-time status updates via polling (30s interval)

**Test Plan:**
1. Create project via modal → appears in list immediately
2. Navigate to project detail → shows correct project info
3. Delete project from detail page → returns to list, project removed
4. Empty state shown when no projects exist

**Developer Docs:**
- **Location:** `docs/dev/projects-ui.md`

**Files Created:**
- `apps/dashboard/src/app/(panel)/projects/page.tsx`
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx`
- `apps/dashboard/src/components/projects/ProjectCard.tsx`
- `apps/dashboard/src/components/projects/ProjectList.tsx`
- `apps/dashboard/src/components/projects/CreateProjectModal.tsx`
- `apps/dashboard/src/hooks/useProjects.ts`
- `apps/dashboard/src/components/ui/dialog.tsx` (shadcn)
- `apps/dashboard/src/components/ui/select.tsx` (shadcn)
- `apps/dashboard/src/components/ui/badge.tsx` (shadcn)

---

### F1.3 — Git Repository Integration
**Status:** 🟢 COMPLETED

**Description:**
Allow users to connect GitHub/GitLab repositories to projects. Clone repos, detect branch, and store connection metadata.

**Acceptance Criteria:**
- [x] Git URL validation (supports GitHub, GitLab, Bitbucket — HTTPS and SSH formats)
- [x] `git clone` executed in project workspace (via Python git_manager.py)
- [x] Branch selection (default: main/master)
- [x] Webhook URL generation for auto-deploy (secret stored; delivery wired in F2.7)
- [x] SSH key generation for private repos (Ed25519, key on disk, public key in DB)
- [x] Store repo metadata in database (gitUrl, branch, webhookSecret, sshPublicKey, sshPrivateKeyPath)

**Test Plan:**
1. Add GitHub URL to project → repo clones successfully
2. Private repo → uses SSH key, clone succeeds
3. Invalid URL → returns validation error
4. Webhook URL accessible and displayed in GitSettings UI

**Developer Docs:**
- **Location:** `docs/dev/git-integration.md`

**Files Created:**
- `apps/api/src/modules/git/schema.ts`
- `apps/api/src/modules/git/service.ts`
- `apps/api/src/modules/git/routes.ts`
- `system/python/git_manager.py`
- `apps/dashboard/src/hooks/useGitSettings.ts`
- `apps/dashboard/src/components/projects/GitSettings.tsx`
- `apps/api/prisma/migrations/20260829183245_add_git_fields_to_project/migration.sql`

**Files Modified:**
- `apps/api/prisma/schema.prisma` (added `webhookSecret`, `sshPublicKey`, `sshPrivateKeyPath` to Project)
- `apps/api/src/config/env.ts` (added `PROJECTS_DIR`, `SSH_KEYS_DIR`, `API_BASE_URL`)
- `apps/api/src/index.ts` (registered `gitRoutes` at `/api/projects`)
- `apps/api/.env.example` (documented new env vars)
- `packages/shared/src/schemas/projects.ts` (added `ConnectRepoSchema`, `GitMetadata`)
- `packages/shared/src/index.ts` (exported new types)
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx` (added `<GitSettings />`)

---

### F1.4 — Nixpacks Build Integration
**Status:** 🟢 COMPLETED

**Description:**
Integrate Nixpacks for zero-configuration builds. Auto-detect framework from source code and generate Docker images.

**Acceptance Criteria:**
- [x] Nixpacks CLI installed / verified on server
- [x] `nixpacks plan` execution to detect framework
- [x] `nixpacks build` generates Docker image
- [x] Build logs stored and polled progressively by frontend (Socket.io streaming in F1.6)
- [x] Build queue managed via BullMQ and Redis
- [x] Support for custom build commands override (Build Settings panel in F5.34)

**Test Plan:**
1. Node.js project → Nixpacks detects, builds successfully
2. Python project → Nixpacks detects, builds successfully
3. Next.js project → SSR build works
4. Build logs appear in real-time in dashboard (via polling)
5. Failed build → shows error logs, status = failed

**Developer Docs:**
- **Location:** `docs/dev/build-system.md`

**Files Created:**
- `apps/api/src/modules/build/schema.ts`
- `apps/api/src/modules/build/service.ts`
- `apps/api/src/modules/build/routes.ts`
- `system/python/build_manager.py`
- `apps/dashboard/src/hooks/useBuild.ts`
- `apps/dashboard/src/components/projects/BuildPanel.tsx`
- `docs/dev/build-system.md`

**Files Modified:**
- `packages/shared/src/schemas/projects.ts` (added `TriggerBuildSchema`, `DeploymentStatusSchema`)
- `packages/shared/src/types/index.ts` (added `Deployment`, `DeploymentStatus`, `PaginatedDeployments`)
- `packages/shared/src/index.ts` (exported new schemas and types)
- `apps/api/src/config/env.ts` (added `NIXPACKS_IMAGE_PREFIX`)
- `apps/api/src/config/queue.ts` (refactored `createQueue`, `createWorker`, and queue registry)
- `apps/api/src/index.ts` (registered `buildRoutes` at `/api/projects`)
- `apps/api/.env.example` (documented `NIXPACKS_IMAGE_PREFIX`)
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx` (added `<BuildPanel />`)

---

### F1.5 — Docker Deployment Engine
**Status:** 🟢 COMPLETED

**Description:**
Generate and manage Docker Compose files per project. Deploy containers, manage networks, and integrate with Traefik for routing.

**Acceptance Criteria:**
- [x] Docker Compose template generation per project type
- [x] Container lifecycle management (start, stop, restart, remove)
- [x] Traefik labels auto-generated for routing
- [x] Environment variables injected into containers
- [x] Health checks configured
- [x] Container logs accessible via API
- [x] Resource limits (CPU, memory) per container

**Test Plan:**
1. Deploy Node.js app → container starts, accessible via domain
2. Deploy static site → Nginx serves files correctly
3. Stop container → app unreachable, status = stopped
4. Restart container → app back online
5. Environment variables → accessible inside container
6. Traefik routes → correct domain points to correct container

**Developer Docs:**
- **Location:** `docs/dev/deployment-engine.md`

**Files Created:**
- `apps/api/src/modules/deploy/service.ts`
- `apps/api/src/modules/deploy/routes.ts`
- `apps/api/src/modules/deploy/schema.ts`
- `system/python/docker_manager.py`
- `system/templates/docker-compose/node.yml`
- `system/templates/docker-compose/static.yml`
- `system/templates/docker-compose/python.yml`
- `apps/dashboard/src/hooks/useDeploy.ts`
- `apps/dashboard/src/components/projects/ContainerControls.tsx`
- `docs/dev/deployment-engine.md`
- `apps/api/prisma/migrations/20260830083857_add_container_fields_to_project/migration.sql`

**Files Modified:**
- `apps/api/prisma/schema.prisma` (added container fields to Project)
- `apps/api/src/config/env.ts` (added `BASE_DOMAIN`, `DEPLOY_MEMORY_LIMIT`, and port range)
- `apps/api/.env.example` (documented new deploy env vars)
- `apps/api/src/index.ts` (registered `deployRoutes` at `/api/projects`)
- `apps/api/src/modules/build/service.ts` (chained container deploy to build worker)
- `apps/api/src/modules/projects/service.ts` (included container fields in `PROJECT_SELECT`)
- `packages/shared/src/schemas/projects.ts` (added `DeployBodySchema`, `ContainerActionSchema`)
- `packages/shared/src/types/index.ts` (added container fields to `Project` type)
- `packages/shared/src/index.ts` (exported new schemas and types)
- `apps/dashboard/src/components/projects/BuildPanel.tsx` (added `onDeploySuccess` callback)
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx` (integrated `ContainerControls`)

---

### F1.6 — Real-Time Logs
**Status:** 🟢 COMPLETED

**Description:**
Stream build and runtime logs from Docker containers to the frontend dashboard in real-time using Socket.io.

**Acceptance Criteria:**
- [x] Socket.io server integrated with Fastify
- [x] Build logs streamed during `nixpacks build`
- [x] Runtime logs streamed from running containers
- [x] Log history persisted (last 1000 lines, frontend cap)
- [x] Frontend terminal-like viewer (styled pre, no extra dep)
- [x] Filter logs by stream (stdout/stderr)
- [x] Auto-scroll with pause option

**Test Plan:**
1. Start deployment → build logs appear in real-time
2. Container running → runtime logs stream continuously
3. Disconnect/reconnect → resumes from last known position
4. 1000+ lines → older lines truncated, recent preserved
5. Filter stderr → only error lines shown

**Developer Docs:**
- **Location:** `docs/dev/realtime-logs.md`

**Files to Create:**
- `apps/api/src/plugins/socket.ts`
- `apps/api/src/modules/logs/service.ts`
- `apps/dashboard/components/projects/LogViewer.tsx`

---

### F1.7 — Environment Variables Management
**Status:** 🟢 COMPLETED

**Description:**
Allow users to set environment variables per project. Variables are encrypted at rest and injected into containers at runtime.

**Acceptance Criteria:**
- [x] `POST /api/projects/:id/env` — add/update env vars
- [x] `GET /api/projects/:id/env` — list env vars (values masked)
- [x] `DELETE /api/projects/:id/env/:key` — remove env var
- [x] Values encrypted with AES-256-GCM
- [x] Injected into Docker containers on deployment
- [x] Frontend UI with key-value editor
- [x] Support for `.env` file import

**Test Plan:**
1. Add env var → stored encrypted in database
2. List env vars → keys visible, values masked as `••••`
3. Deploy app → env vars accessible inside container
4. Update env var → new value used on next deployment
5. Import .env file → all vars parsed and stored

**Developer Docs:**
- **Location:** `docs/dev/environment-variables.md`

**Files Created:**
- `packages/shared/src/schemas/env.ts`
- `apps/api/src/utils/encryption.ts`
- `apps/api/src/modules/env/schema.ts`
- `apps/api/src/modules/env/service.ts`
- `apps/api/src/modules/env/routes.ts`
- `apps/dashboard/src/hooks/useEnvVars.ts`
- `apps/dashboard/src/components/projects/EnvVarEditor.tsx`
- `docs/dev/environment-variables.md`

**Files Modified:**
- `packages/shared/src/types/index.ts`
- `packages/shared/src/index.ts`
- `apps/api/src/config/env.ts`
- `apps/api/.env.example`
- `apps/api/src/index.ts`
- `apps/api/src/modules/deploy/service.ts`
- `apps/api/src/modules/build/service.ts`
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx`

---

### F1.8 — Project Detail Page: Tabbed Sections
**Status:** 🟢 COMPLETED

**Description:**
`apps/dashboard/src/app/(panel)/projects/[id]/page.tsx` currently renders 14 distinct sections stacked vertically with no grouping — Overview info, Repository, Configuration, Metadata, `GitSettings`, `ContainerControls`, `EnvVarEditor`, `DatabasePanel`, `DomainPanel`, `FileManagerCard`, `SftpPanel`, `WordPressPanel`/`DockerfilePanel` (conditional), and `BuildPanel` (deployments) — in that order. This makes the page a very long scroll with no way to jump to what you need, and buries important panels (env vars, deployments) below less-frequently-used ones (SFTP, files).

**Acceptance Criteria:**
- [x] Project detail page is reorganized into tabs (Overview, Deploy/Build, Environment, Database, Domains, Files, Git & Advanced) using the existing shadcn `Tabs` component (already used elsewhere, e.g. the Mail page)
- [x] Each existing panel component (`GitSettings`, `ContainerControls`, `EnvVarEditor`, `DatabasePanel`, `DomainPanel`, `FileManagerCard`, `SftpPanel`, `WordPressPanel`, `DockerfilePanel`, `BuildPanel`) moves into the appropriate tab without behavior changes
- [x] Overview tab keeps the at-a-glance info (type/status/repo/config/metadata) so users don't lose the summary view
- [x] Active tab persists across a page refresh via a `?tab=<slug>` URL query param so a direct link to "the env vars tab" is shareable
- [x] No regression to any existing panel's functionality — this is a layout change only

**Test Plan:**
1. Open a project → tabs are visible, Overview shows the summary info
2. Switch tabs → each panel renders and functions exactly as before (deploy, edit env vars, manage domains, etc.)
3. Refresh the page while on a non-default tab → still on that tab
4. WordPress/Dockerfile-specific panels (inside the Git & Advanced tab) only show for those project types

**Developer Docs:**
- **Location:** `docs/dev/project-detail-page.md`

**Files Modified:**
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx`

---

## Phase 2: Multi-Runtime Support

### F2.1 — Next.js Deployment
**Status:** 🟢 COMPLETED

**Description:**
Support deploying Next.js applications with SSR, API routes, and static generation.

**Acceptance Criteria:**
- [x] Auto-detection via `next.config.*` or `package.json` dependency
- [x] Build command: `npm run build`
- [x] Start command: `npm run start`
- [x] SSR works (not just static export)
- [x] API routes functional
- [x] Image optimization via Next.js Image component
- [x] Build output cached for faster redeploys

**Test Plan:**
1. Deploy Next.js app with SSR → pages render server-side
2. API route `/api/hello` → returns JSON response
3. Image component → images optimized and served
4. Re-deploy → build cache used, faster build time

**Developer Docs:**
- **Location:** `docs/dev/runtimes/nextjs.md`

**Files Created:**
- `system/templates/docker-compose/next.yml`
- `tests/test_nextjs_runtime.py`
- `docs/dev/runtimes/nextjs.md`

**Files Modified:**
- `system/python/docker_manager.py`
- `system/python/build_manager.py`
- `apps/api/src/modules/build/service.ts`

---

### F2.2 — Python (Django/Flask/FastAPI) Deployment
**Status:** 🟢 COMPLETED

**Description:**
Support deploying Python web applications. Auto-detect framework and configure appropriate WSGI/ASGI server.

**Acceptance Criteria:**
- [x] Auto-detection via `requirements.txt` or `pyproject.toml`
- [x] Django: `gunicorn` + `manage.py collectstatic`
- [x] Flask: `gunicorn` with auto-detected entry point
- [x] FastAPI: `uvicorn` with auto-detected app instance
- [x] Static files served via Nginx sidecar
- [x] Python version selection (3.10, 3.11, 3.12)

**Test Plan:**
1. Deploy Django app → admin panel accessible
2. Deploy Flask app → routes work correctly
3. Deploy FastAPI app → auto-docs at `/docs`
4. Static files → CSS/JS served correctly

**Developer Docs:**
- **Location:** `docs/dev/runtimes/python.md`

**Files Created:**
- `tests/test_python_runtime.py`
- `docs/dev/runtimes/python.md`

**Files Modified:**
- `system/python/build_manager.py`
- `apps/api/src/modules/build/service.ts`

---

### F2.3 — React (Vite) Static Deployment
**Status:** 🟢 COMPLETED

**Description:**
Support deploying React applications built with Vite as static sites.

**Acceptance Criteria:**
- [x] Auto-detection via `vite.config.*`
- [x] Build command: `npm run build`
- [x] Output served from `dist/` folder via Nginx / Caddy static web server
- [x] SPA routing support (fallback to index.html)
- [x] Environment variable injection at build time

**Test Plan:**
1. Deploy Vite React app → loads correctly
2. Client-side routing → `/about` works on refresh
3. Build-time env vars → replaced in built files

**Developer Docs:**
- **Location:** `docs/dev/runtimes/react-vite.md`

**Files Created:**
- `tests/test_react_runtime.py`
- `docs/dev/runtimes/react-vite.md`

**Files Modified:**
- `system/python/build_manager.py`
- `system/templates/docker-compose/static.yml`
- `apps/api/src/modules/build/service.ts`

---

### F2.4 — PHP & WordPress Deployment
**Status:** 🟢 COMPLETED

**Description:**
Support deploying modern & traditional PHP applications (Laravel, Symfony, generic PHP) and one-click WordPress installation with Nginx + PHP-FPM container orchestration, multi-version PHP support (8.1, 8.2, 8.3), automated core scaffolding, secure salt generation, wp-config.php auto-wiring, permalinks rewrites, and plugin/theme file uploads.

**Acceptance Criteria:**
- [x] PHP-FPM + Nginx container setup
- [x] Multiple PHP versions (8.1, 8.2, 8.3)
- [x] WordPress one-click installer
- [x] Auto-download WordPress core
- [x] wp-config.php auto-generation with DB credentials
- [x] Plugin/theme upload via file manager
- [x] Permalink support

**Test Plan:**
1. Deploy PHP app → executes correctly
2. One-click WordPress → site loads, admin accessible
3. Upload plugin → appears in WordPress admin
4. Permalinks → pretty URLs work

**Developer Docs:**
- **Location:** `docs/dev/runtimes/php-wordpress.md`

**Files Created:**
- `system/templates/docker-compose/php.yml`
- `system/templates/docker-compose/wordpress.yml`
- `apps/api/src/modules/wordpress/schema.ts`
- `apps/api/src/modules/wordpress/service.ts`
- `apps/api/src/modules/wordpress/routes.ts`
- `apps/dashboard/src/components/projects/WordPressPanel.tsx`
- `tests/test_php_wordpress_runtime.py`
- `docs/dev/runtimes/php-wordpress.md`

**Files Modified:**
- `system/python/build_manager.py`
- `system/python/docker_manager.py`
- `apps/api/src/modules/build/service.ts`
- `apps/api/src/index.ts`
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx`
- `tests/test_multi_project_isolation.py`

---

### F2.5 — Custom Dockerfile Deployment
**Status:** 🟢 COMPLETED

**Description:**
Allow users to provide their own Dockerfile for maximum flexibility. Includes interactive Dockerfile and .dockerignore code editor, 1-click starter presets (Node.js, Python, Go, Rust, Static Nginx, Bun, PHP 8.3), native `docker build` execution with real-time log streaming, build argument injection, automatic `EXPOSE` port detection, custom health checks, and Traefik load balancer orchestration.

**Acceptance Criteria:**
- [x] Dockerfile upload or inline editor
- [x] `docker build` from provided Dockerfile
- [x] `.dockerignore` support
- [x] Build context from project files
- [x] Health check configuration
- [x] Exposed port auto-detection or manual specification

**Test Plan:**
1. Upload custom Dockerfile → builds successfully
2. Invalid Dockerfile → build fails with clear error
3. `.dockerignore` → excluded files not in build context

**Developer Docs:**
- **Location:** `docs/dev/runtimes/custom-dockerfile.md`

**Files Created:**
- `system/templates/docker-compose/docker.yml`
- `packages/shared/src/schemas/dockerfile.ts`
- `apps/api/src/modules/dockerfile/schema.ts`
- `apps/api/src/modules/dockerfile/service.ts`
- `apps/api/src/modules/dockerfile/routes.ts`
- `apps/dashboard/src/components/projects/DockerfilePanel.tsx`
- `tests/test_dockerfile_runtime.py`
- `docs/dev/runtimes/custom-dockerfile.md`

**Files Modified:**
- `system/python/build_manager.py`
- `system/python/docker_manager.py`
- `packages/shared/src/index.ts`
- `apps/api/src/modules/build/service.ts`
- `apps/api/src/index.ts`
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx`
- `tests/test_multi_project_isolation.py`


---

### F2.6 — Database Provisioning (MySQL/PostgreSQL)
**Status:** 🟢 COMPLETED

**Description:**
Allow users to create databases per project or standalone. Manage database users, passwords, connections, and live testing. Includes PostgreSQL 16 and MySQL 8.0 support, automatic strong password generation with AES-256-GCM encryption at rest, connection string generation (internal Docker and host), automatic project environment variable injection, and Adminer web GUI integration.

**Acceptance Criteria:**
- [x] `POST /api/databases` — create database + user
- [x] `GET /api/databases` — list user's databases
- [x] `DELETE /api/databases/:id` — drop database and user
- [x] Auto-generated strong passwords
- [x] Connection string provided to user
- [x] Database accessible only from project containers
- [x] phpMyAdmin/Adminer integration for MySQL

**Test Plan:**
1. Create MySQL DB → database and user created
2. Connect from app → connection successful
3. Delete DB → database dropped, user removed
4. phpMyAdmin / Adminer → accessible via panel, shows correct DBs

**Developer Docs:**
- **Location:** `docs/dev/database-provisioning.md`

**Files Created:**
- `system/python/database_manager.py`
- `packages/shared/src/schemas/databases.ts`
- `apps/api/src/modules/databases/schema.ts`
- `apps/api/src/modules/databases/service.ts`
- `apps/api/src/modules/databases/routes.ts`
- `apps/dashboard/src/app/(panel)/databases/page.tsx`
- `apps/dashboard/src/components/projects/DatabasePanel.tsx`
- `tests/test_database_provisioning.py`
- `docs/dev/database-provisioning.md`

**Files Modified:**
- `docker-compose.yml`
- `packages/shared/src/index.ts`
- `apps/api/src/config/env.ts`
- `apps/api/.env.example`
- `apps/api/src/index.ts`
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx`

---

### F2.7 — GitHub Webhook Auto-Deploy
**Status:** 🟢 COMPLETED

**Description:**
Automatically redeploy projects when code is pushed to connected GitHub repositories.

**Acceptance Criteria:**
- [x] Webhook endpoint `POST /api/webhooks/github`
- [x] Signature verification with GitHub secret
- [x] Filter by branch (only deploy configured branch)
- [x] Queue deployment via BullMQ
- [x] Deployment status shown in dashboard
- [x] Support for pull request previews (optional)

**Test Plan:**
1. Push to main branch → webhook received, deployment queued
2. Push to other branch → ignored (if not configured)
3. Invalid signature → webhook rejected with 401
4. Deployment → new code live within 2 minutes

**Developer Docs:**
- **Location:** `docs/dev/github-webhooks.md`

**Files Created:**
- `packages/shared/src/schemas/webhooks.ts`
- `apps/api/src/modules/webhooks/schema.ts`
- `apps/api/src/modules/webhooks/service.ts`
- `apps/api/src/modules/webhooks/routes.ts`
- `tests/test_github_webhooks.py`
- `docs/dev/github-webhooks.md`

**Files Modified:**
- `packages/shared/src/schemas/projects.ts`
- `packages/shared/src/index.ts`
- `apps/api/src/modules/git/service.ts`
- `apps/api/src/modules/git/routes.ts`
- `apps/api/src/modules/build/service.ts`
- `apps/api/src/index.ts`
- `apps/dashboard/src/hooks/useGitSettings.ts`
- `apps/dashboard/src/components/projects/GitSettings.tsx`
- `apps/dashboard/src/components/projects/BuildPanel.tsx`

---

### F2.8 — File Manager & SFTP Access
**Status:** 🟢 COMPLETED

**Description:**
Web-based file manager embedded in the project detail page and a dedicated full-screen editor. Users can browse, edit, upload, download, rename, move, copy and delete their project files directly from the dashboard. A CodeMirror 6 editor handles in-browser editing with syntax highlighting. WordPress projects gain one-click export (files + DB as `.tar.gz`) and import (extract + SQL restore + wp-config update). Each Vexlyx user can provision a chrooted SFTP account (one per user, scoped to all their projects) with password-based and SSH-key-based authentication.

**Acceptance Criteria:**
- [x] `GET  /api/files/:id/list` — lazy-load directory tree (depth 1–3)
- [x] `GET  /api/files/:id/read` — read file content (≤ 2 MB)
- [x] `POST /api/files/:id/write` — atomic save (temp-file + rename)
- [x] `DELETE /api/files/:id/delete` — delete file or folder recursively
- [x] `POST /api/files/:id/rename` — rename / move within project
- [x] `POST /api/files/:id/mkdir` — create directory
- [x] `POST /api/files/:id/copy` — copy file or directory
- [x] `POST /api/files/:id/move` — move file or directory
- [x] `GET  /api/files/:id/download` — stream file as download
- [x] `POST /api/files/:id/create` — create file without overwriting (returns 409 on collision)
- [x] `POST /api/files/:id/upload` — multipart upload, max 100 MB per file
- [x] Path-traversal protection: `safePath()` + symlink escape guard
- [x] Blocks writes to `.env` / `wp-config.php` via extension blocklist
- [x] `GET  /api/projects/:id/wordpress/export` — tar.gz stream (files + mysqldump)
- [x] `POST /api/projects/:id/wordpress/import` — upload + extract + SQL + wp-config
- [x] `POST /api/sftp/provision` — create chrooted Linux user + sshd_config Match block
- [x] `GET  /api/sftp/credentials` — return stored (decrypted) connection details with dynamic host
- [x] `POST /api/sftp/rotate-password` — generate new password, update chpasswd
- [x] `POST /api/sftp/add-ssh-key` — append to authorized_keys
- [x] `DELETE /api/sftp/disable` — lock the Linux account (`usermod --lock`)
- [x] `POST /api/sftp/enable` — unlock the Linux account (`usermod --unlock`) & sync projects
- [x] Passwords encrypted at rest with AES-256-GCM
- [x] `FileManagerCard` compact widget on project detail page (5 recent files + Open button)
- [x] Full-screen two-pane file manager at `/projects/:id/files`
- [x] CodeMirror 6 editor with auto language detection + Ctrl+S save
- [x] Drag-and-drop upload dropzone (100 MB limit enforced client-side)
- [x] `SftpPanel` card: provision, show credentials, rotate password, add SSH key, disable, enable

**Test Plan:**
1. Browse project directory → tree loads lazily on folder expand
2. Click a `.php` / `.ts` / `.yaml` file → opens in CodeMirror with correct syntax highlighting
3. Edit file → Ctrl+S → toast "File saved"
4. Upload a 1 MB file via drag-and-drop → file appears in tree after refresh
5. Attempt path like `../../etc/passwd` → API returns 403
6. Attempt write to `.env` → API returns 403
7. WordPress export → `wp-export-*.tar.gz` downloads with SQL dump inside
8. WordPress import (valid archive) → files extracted, SQL restored, wp-config updated
9. Provision SFTP → credentials shown; `sftp username@host` connects, chroot holds
10. Add SSH key → key appears; password-less login works
11. Rotate password → old password rejected, new one works
12. Disable SFTP → `usermod --lock` prevents all logins

**Developer Docs:**
- **Location:** `docs/dev/file-manager-sftp.md`

**Files Created:**
- `packages/shared/src/schemas/files.ts`
- `apps/api/src/modules/files/schema.ts`
- `apps/api/src/modules/files/service.ts`
- `apps/api/src/modules/files/routes.ts`
- `apps/api/src/modules/sftp/schema.ts`
- `apps/api/src/modules/sftp/service.ts`
- `apps/api/src/modules/sftp/routes.ts`
- `system/python/sftp_manager.py`
- `apps/dashboard/src/components/files/FileTree.tsx`
- `apps/dashboard/src/components/files/FileEditor.tsx`
- `apps/dashboard/src/components/files/UploadDropzone.tsx`
- `apps/dashboard/src/components/projects/FileManagerCard.tsx`
- `apps/dashboard/src/components/projects/SftpPanel.tsx`
- `apps/dashboard/src/components/ui/dropdown-menu.tsx`
- `apps/dashboard/src/app/(standalone)/layout.tsx`
- `apps/dashboard/src/app/(standalone)/projects/[id]/files/page.tsx`
- `apps/api/src/types/stream.d.ts`
- `tests/test_file_manager_sftp.py`
- `docs/dev/file-manager-sftp.md`

**Files Modified:**
- `packages/shared/src/index.ts`
- `apps/api/prisma/schema.prisma` — added `SftpUser` model
- `apps/api/src/config/env.ts` — added `FILE_UPLOAD_MAX_MB`, `SFTP_HOST`, `SFTP_PORT`
- `apps/api/src/index.ts` — registered `@fastify/multipart`, `fileRoutes`, `sftpRoutes`
- `apps/api/src/modules/wordpress/schema.ts` — added `WordPressImportSchema`
- `apps/api/src/modules/wordpress/service.ts` — added `exportSite`, `importSite`, `saveTempUpload`
- `apps/api/src/modules/wordpress/routes.ts` — added export + import routes
- `system/python/build_manager.py` — added `wordpress-export`, `wordpress-import` commands
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx` — renders `FileManagerCard`, `SftpPanel`
- `apps/dashboard/src/components/projects/WordPressPanel.tsx` — export/import buttons + dialog

---

## Phase 3: Domain & DNS


### F3.1 — Custom Domain Management
**Status:** 🟢 COMPLETED

**Description:**
Allow users to attach custom domains to projects. Validate domain ownership and configure routing.

**Acceptance Criteria:**
- [x] `POST /api/domains` — add domain to project
- [x] `PATCH /api/domains/:id` — assign, move, or unassign an existing owned domain without deleting DNS, certificates, or mail (issue #14)
- [x] Domain cards provide project assignment; project tabs offer to attach existing owned domains and confirm moves
- [x] Domain validation via DNS TXT record
- [x] `GET /api/domains` — list domains
- [x] `DELETE /api/domains/:id` — remove domain
- [x] Traefik router auto-configuration
- [x] Domain status tracking (pending, active, error)

**Test Plan:**
1. Add domain → validation instructions shown
2. Add TXT record → validation passes, status = active
3. Visit domain → loads correct project
4. Remove domain → routing removed, DNS cleaned up

**Developer Docs:**
- **Location:** `docs/dev/domains.md`

**Files Created:**
- `packages/shared/src/schemas/domains.ts`
- `apps/api/src/modules/domains/schema.ts`
- `apps/api/src/modules/domains/service.ts`
- `apps/api/src/modules/domains/routes.ts`
- `apps/dashboard/src/hooks/useDomains.ts`
- `apps/dashboard/src/components/projects/DomainPanel.tsx`
- `apps/dashboard/src/app/(panel)/domains/page.tsx`
- `tests/test_custom_domains.py`
- `docs/dev/domains.md`

**Files Modified:**
- `packages/shared/src/index.ts`
- `apps/api/prisma/schema.prisma`
- `apps/api/src/index.ts`
- `apps/dashboard/src/app/(panel)/projects/[id]/page.tsx`

---

### F3.2 — Subdomain Support
**Status:** 🟢 COMPLETED

**Description:**
Support subdomains pointing to different projects or paths within the same server.

**Acceptance Criteria:**
- [x] `api.domain.com` → API project
- [x] `blog.domain.com` → blog project
- [x] `app.domain.com` → main app
- [x] Wildcard subdomain support (`*.domain.com`)
- [x] Subdomain management UI

**Test Plan:**
1. Add subdomain → routes to correct project
2. Wildcard subdomain → any subdomain works
3. Remove subdomain → routing removed

**Developer Docs:**
- **Location:** `docs/dev/subdomains.md`

**Files Created:**
- `apps/dashboard/src/components/domains/SubdomainModal.tsx`
- `tests/test_subdomains.py`
- `docs/dev/subdomains.md`

**Files Modified:**
- `packages/shared/src/schemas/domains.ts`
- `packages/shared/src/index.ts`
- `apps/api/prisma/schema.prisma`
- `apps/api/src/modules/domains/service.ts`
- `apps/api/src/modules/domains/routes.ts`
- `apps/dashboard/src/hooks/useDomains.ts`
- `apps/dashboard/src/app/(panel)/domains/page.tsx`
- `apps/dashboard/src/components/projects/DomainPanel.tsx`

---

### F3.3 — DNS Record Management
**Status:** 🟢 COMPLETED

**Description:**
Full DNS zone management for domains hosted on Vexlyx nameservers.

**Acceptance Criteria:**
- [x] Support for A, AAAA, CNAME, MX, TXT, NS, SRV records
- [x] DNS zone file generation
- [x] BIND9 or CoreDNS integration
- [x] Record validation (IP format, hostname, etc.)
- [x] TTL configuration per record
- [x] DNS propagation status
- [x] Import/export zone files

**Test Plan:**
1. Add A record → resolves correctly
2. Add MX record → email routing works
3. Add TXT record → SPF/DKIM validation passes
4. Export zone file → contains all records
5. Import zone file → records created correctly

**Developer Docs:**
- **Location:** `docs/dev/dns-management.md`

**Files Created:**
- `packages/shared/src/schemas/dns.ts`
- `docker/coredns/Corefile`
- `docker/coredns/zones/.gitkeep`
- `system/python/dns_manager.py`
- `apps/api/src/modules/domains/dns-service.ts`
- `apps/dashboard/src/hooks/useDnsRecords.ts`
- `apps/dashboard/src/app/(panel)/domains/[id]/dns/page.tsx`
- `apps/dashboard/src/components/domains/DnsManagementModal.tsx`
- `tests/test_dns_management.py`
- `docs/dev/dns-management.md`

**Files Modified:**
- `packages/shared/src/index.ts`
- `docker-compose.yml`
- `apps/api/prisma/schema.prisma`
- `apps/api/src/modules/domains/schema.ts`
- `apps/api/src/modules/domains/routes.ts`
- `apps/api/src/plugins/auth.ts`
- `apps/dashboard/src/app/(panel)/domains/page.tsx`

---

### F3.4 — SSL Certificate Management
**Status:** 🟢 COMPLETED

**Description:**
Automatic SSL certificate provisioning via Let's Encrypt through Traefik.

**Acceptance Criteria:**
- [x] Auto SSL for all domains via Traefik certresolver
- [x] Wildcard SSL support
- [x] Certificate expiry monitoring
- [x] Auto-renewal before expiry
- [x] Manual certificate upload (for custom certs)
- [x] SSL status shown per domain

**Test Plan:**
1. Add domain → SSL certificate auto-generated within 60 seconds
2. Visit `https://domain.com` → valid certificate
3. Wildcard domain → `*.domain.com` covered
4. Expiry alert → notification 7 days before expiry

**Developer Docs:**
- **Location:** `docs/dev/ssl-management.md`

**Files Created:**
- `packages/shared/src/schemas/ssl.ts`
- `system/python/ssl_manager.py`
- `apps/api/src/modules/domains/ssl-service.ts`
- `apps/dashboard/src/hooks/useDomainSsl.ts`
- `apps/dashboard/src/app/(panel)/domains/[id]/ssl/page.tsx`
- `tests/test_ssl_management.py`
- `docs/dev/ssl-management.md`

**Files Modified:**
- `docker-compose.yml`
- `docker/traefik/traefik.yml`
- `.gitignore`
- `apps/api/prisma/schema.prisma`
- `apps/api/src/modules/domains/schema.ts`
- `apps/api/src/modules/domains/service.ts`
- `apps/api/src/modules/domains/routes.ts`
- `packages/shared/src/schemas/domains.ts`
- `packages/shared/src/index.ts`
- `apps/dashboard/src/app/(panel)/domains/page.tsx`
- `FEATURES.md`


---

### F3.5 — Domain, DNS Zone & Backup UX Polish
**Status:** 🟢 COMPLETED

**Description:**
Follow-up polish pass after a manual UX/responsiveness review. Domain cards and DNS zone management are functionally responsive already (`apps/dashboard/src/app/(panel)/domains/page.tsx` uses `grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3`; the DNS records table at `domains/[id]/dns/page.tsx:692` is already wrapped in `overflow-x-auto`), but a few rough edges remained from the audit, plus two additional overflow/data-duplication bugs found via live testing during this pass.

**Acceptance Criteria:**
- [x] Domain filter `Select` triggers use responsive width classes (`w-full sm:w-35`/`sm:w-37.5`/`sm:w-40`) instead of fixed pixel widths
- [x] The DNS Verification Ownership dialog's TXT record grid was restructured into stacked label:value rows (rather than a literal `grid-cols-3` reflow, which would separate labels from values); the SRV form's `grid-cols-3` was verified to fit fine at 360px and left unchanged
- [x] Manual pass at 360px/768px/1024px widths confirms no overflow or unreadable truncation on `/domains`, `/domains/[id]/dns`, and their dialogs
- [x] (Found via live testing) Domain card action row no longer overflows into the neighboring grid card when a non-`ACTIVE` domain's "Verify" button is present — split into two rows
- [x] (Found via live testing) DNS records table Name column no longer duplicates the domain hostname for the auto-created verification TXT record, and the DNS toolbar (filter pills/search/"Recommended Defaults") wraps instead of overflowing the card

**Test Plan:**
1. Resize browser to 360px width → domain filter bar and DNS-instructions dialogs remain usable, no horizontal page scroll
2. Resize to tablet width (768px) → domain cards reflow to 2 columns, DNS table scrolls horizontally within its own container, not the page

**Developer Docs:**
- **Location:** `docs/dev/dns-management.md` (appended "Responsive Design Notes (F3.5)" section — `docs/dev/domains-dns.md` referenced in the original spec doesn't exist; DNS docs already live in `dns-management.md`)

**Files Modified:**
- `apps/dashboard/src/app/(panel)/domains/page.tsx`
- `apps/dashboard/src/app/(panel)/domains/[id]/dns/page.tsx`
- `docs/dev/dns-management.md`
- `FEATURES.md`

---

## Phase 4: Email Server

### F4.1 — Postfix SMTP Server
**Status:** 🟢 COMPLETED

**Description:**
Install and configure Postfix for outgoing email (SMTP).

**Acceptance Criteria:**
- [x] Postfix installed and running on host
- [x] Port 25 and 587 open
- [x] Virtual domain configuration
- [x] Relay restrictions (no open relay)
- [x] TLS encryption enforced
- [x] DKIM signing via OpenDKIM

**Test Plan:**
1. Send email via SMTP → delivered successfully
2. TLS required → plaintext connection rejected
3. Open relay test → relay denied for unauthorized IPs

**Developer Docs:**
- **Location:** `docs/dev/email/postfix.md`

**Files Created:**
- `packages/shared/src/schemas/mail.ts`
- `docker/postfix/Dockerfile`
- `docker/postfix/main.cf`
- `docker/postfix/master.cf`
- `docker/postfix/opendkim.conf`
- `docker/postfix/entrypoint.sh`
- `docker/postfix/config/virtual_domains`
- `docker/postfix/config/virtual_mailbox_maps`
- `system/python/postfix_manager.py`
- `system/scripts/setup-postfix.sh`
- `apps/api/src/modules/mail/schema.ts`
- `apps/api/src/modules/mail/service.ts`
- `apps/api/src/modules/mail/routes.ts`
- `apps/dashboard/src/hooks/useMail.ts`
- `apps/dashboard/src/app/(panel)/mail/page.tsx`
- `tests/test_postfix_smtp.py`
- `docs/dev/email/postfix.md`

**Files Modified:**
- `docker-compose.yml`
- `packages/shared/src/index.ts`
- `apps/api/src/index.ts`
- `FEATURES.md`

---

### F4.2 — Dovecot IMAP Server
**Status:** 🟢 COMPLETED

**Description:**
Install and configure Dovecot for incoming email (IMAP).

**Acceptance Criteria:**
- [x] Dovecot installed and running on host
- [x] Port 143 and 993 open
- [x] Virtual mailbox configuration
- [x] Maildir format storage
- [x] Quota management
- [x] SSL/TLS on port 993

**Test Plan:**
1. Connect via IMAPS → login successful
2. Retrieve emails → inbox loads correctly
3. Quota exceeded → rejection with clear message

**Developer Docs:**
- **Location:** `docs/dev/email/dovecot.md`

**Files Created:**
- `docker/dovecot/Dockerfile`
- `docker/dovecot/dovecot.conf`
- `docker/dovecot/entrypoint.sh`
- `docker/dovecot/config/users`
- `system/python/dovecot_manager.py`
- `system/scripts/setup-dovecot.sh`
- `tests/test_dovecot_imap.py`
- `docs/dev/email/dovecot.md`

**Files Modified:**
- `docker-compose.yml`
- `docker/postfix/main.cf`
- `docker/postfix/entrypoint.sh`
- `packages/shared/src/schemas/mail.ts`
- `packages/shared/src/index.ts`
- `apps/api/src/config/env.ts`
- `apps/api/src/modules/mail/service.ts`
- `apps/api/.env.example`
- `apps/dashboard/src/hooks/useMail.ts`
- `apps/dashboard/src/app/(panel)/mail/page.tsx`
- `.gitignore`
- `FEATURES.md`

---

### F4.3 — Mailbox Management UI
**Status:** 🟢 COMPLETED

**Description:**
Dashboard interface for creating and managing email mailboxes.

**Acceptance Criteria:**
- [x] `POST /api/mailboxes` — create mailbox
- [x] `GET /api/mailboxes` — list mailboxes
- [x] `DELETE /api/mailboxes/:id` — delete mailbox
- [x] Quota configuration per mailbox
- [x] Password reset functionality
- [x] Mailbox usage statistics

**Test Plan:**
1. Create mailbox → can login via IMAP
2. Send email to mailbox → appears in inbox
3. Delete mailbox → emails inaccessible
4. Quota set → enforced by Dovecot

**Developer Docs:**
- **Location:** `docs/dev/email/mailbox-management.md`

**Files Created:**
- `apps/api/src/modules/mailboxes/routes.ts`
- `apps/api/src/modules/mailboxes/service.ts`
- `apps/api/src/modules/mailboxes/schema.ts`
- `packages/shared/src/schemas/mailbox.ts`
- `apps/dashboard/src/hooks/useMailboxes.ts`
- `apps/dashboard/src/components/mail/MailboxesPanel.tsx`
- `apps/dashboard/src/components/ui/tabs.tsx`
- `apps/dashboard/src/components/ui/table.tsx`
- `docs/dev/email/mailbox-management.md`

**Files Modified:**
- `apps/api/src/index.ts`
- `apps/api/src/modules/mail/service.ts`
- `packages/shared/src/index.ts`
- `apps/dashboard/src/app/(panel)/mail/page.tsx`
- `system/python/dovecot_manager.py`
- `system/python/postfix_manager.py`
- `docker/postfix/entrypoint.sh`
- `FEATURES.md`

---

### F4.4 — Webmail (Roundcube)
**Status:** 🟢 COMPLETED

**Description:**
Deploy Roundcube as a Docker container for web-based email access.

**Acceptance Criteria:**
- [x] Roundcube Docker container running
- [x] Proxied via Traefik at `webmail.vexlyx.localhost` (single shared instance, same tier as `adminer`)
- [x] Auto-configured with Dovecot/Postfix settings (no config changes needed on either)
- [x] Multiple mailbox support (any Dovecot mailbox can log in)
- [x] Compose, reply, forward functionality (Roundcube core)
- [x] Address book (Roundcube core)
- [x] Attachment support (Roundcube core)

**Test Plan:**
1. Access webmail → login page loads
2. Login → inbox displays emails
3. Compose email → sends successfully
4. Attachment upload/download → works correctly

**Developer Docs:**
- **Location:** `docs/dev/email/webmail.md`

**Files Created:**
- `system/python/webmail_manager.py`
- `docker/traefik/dynamic/webmail.yml`
- `docker/roundcube/config/local.inc.php`
- `apps/dashboard/src/hooks/useWebmail.ts`
- `apps/dashboard/src/components/mail/WebmailPanel.tsx`
- `docs/dev/email/webmail.md`

**Files Modified:**
- `docker-compose.yml`
- `packages/shared/src/schemas/mail.ts`
- `packages/shared/src/index.ts`
- `apps/api/src/config/env.ts`
- `apps/api/.env.example`
- `apps/api/src/modules/mail/service.ts`
- `apps/api/src/modules/mail/routes.ts`
- `apps/dashboard/src/app/(panel)/mail/page.tsx`
- `FEATURES.md`

---

### F4.5 — SPF, DKIM, DMARC Auto-Configuration
**Status:** 🟢 COMPLETED

**Description:**
Automatically generate and manage email authentication DNS records.

**Acceptance Criteria:**
- [x] SPF record auto-generated per domain
- [x] DKIM key pair generation
- [x] DKIM public key in DNS TXT record
- [x] DMARC policy record generation
- [x] Email deliverability score monitoring (internal 0-100 score, no external API)
- [x] DNS records updated when mail domain added (triggered on first mailbox creation)

**Test Plan:**
1. Add mail domain → SPF, DKIM, DMARC records created
2. Send email → passes SPF/DKIM/DMARC checks
3. Mail-Tester score → 9/10 or higher (verify manually via mail-tester.com; Vexlyx's own score is internal-only and DB-based, see docs)

**Developer Docs:**
- **Location:** `docs/dev/email/authentication.md`

**Files Created:**
- `docs/dev/email/authentication.md`
- `tests/test_mail_authentication.py`

**Files Modified:**
- `apps/api/src/modules/domains/dns-service.ts`
- `apps/api/src/modules/mail/service.ts`
- `apps/api/src/modules/mail/routes.ts`
- `apps/api/src/modules/mail/schema.ts`
- `apps/api/src/modules/mailboxes/service.ts`
- `packages/shared/src/schemas/mail.ts`
- `packages/shared/src/index.ts`
- `apps/dashboard/src/hooks/useMail.ts`
- `apps/dashboard/src/app/(panel)/mail/page.tsx`
- `FEATURES.md`

---

### F4.6 — Email Forwarding & Aliases
**Status:** 🟢 COMPLETED

**Description:**
Support email forwarding and alias creation.

**Acceptance Criteria:**
- [x] Create alias `sales@domain.com` → forwards to `user@domain.com`
- [x] Multiple destination addresses per alias
- [x] Catch-all alias support
- [x] Alias management UI

> Vacation auto-responder split out to F4.7 (requires Dovecot Pigeonhole/Sieve, not yet installed).

**Test Plan:**
1. Create alias → email forwarded correctly
2. Catch-all → unmatched emails forwarded to admin

**Developer Docs:**
- **Location:** `docs/dev/email/aliases.md`

---

### F4.7 — Vacation Auto-Responder
**Status:** 🟢 COMPLETED

**Description:**
Per-mailbox vacation/out-of-office auto-reply, powered by Dovecot Pigeonhole (Sieve) and LMTP delivery handoff from Postfix.

**Acceptance Criteria:**
- [x] Dovecot Pigeonhole (Sieve) installed and wired into the mail stack
- [x] Per-mailbox vacation message configuration UI
- [x] Auto-reply sent once per sender within a configurable interval

**Test Plan:**
1. Enable vacation responder on a mailbox → sender receives one auto-reply
2. Second message from same sender within interval → no duplicate auto-reply

**Developer Docs:**
- **Location:** `docs/dev/email/vacation-responder.md`

**Files Created:**
- `packages/shared/src/schemas/vacation.ts`
- `apps/api/src/modules/vacation/schema.ts`
- `apps/api/src/modules/vacation/service.ts`
- `apps/api/src/modules/vacation/routes.ts`
- `apps/dashboard/src/hooks/useVacationResponder.ts`
- `apps/dashboard/src/components/mail/VacationResponderDialog.tsx`
- `docs/dev/email/vacation-responder.md`
- `tests/test_vacation_responder.py`

**Files Modified:**
- `apps/api/prisma/schema.prisma`
- `packages/shared/src/schemas/mailbox.ts`
- `packages/shared/src/index.ts`
- `docker/dovecot/Dockerfile`
- `docker/dovecot/dovecot.conf`
- `docker/postfix/main.cf`
- `system/python/dovecot_manager.py`
- `system/scripts/setup-dovecot.sh`
- `apps/api/src/index.ts`
- `apps/api/src/modules/mailboxes/service.ts`
- `apps/dashboard/src/components/mail/MailboxesPanel.tsx`
- `FEATURES.md`

---

### F4.8 — Mail Page: Production-Grade Operations (Queue, Bounces, DKIM Rotation)
**Status:** 🟢 COMPLETED

**Description:**
Phase 4 (F4.1-F4.7) covers the mail *provisioning* side well (mailboxes, aliases, vacation, DKIM/SPF/DMARC status badges, storage-usage bars already exist and look fine — see `apps/dashboard/src/components/mail/MailboxesPanel.tsx`), but the mail page had none of the day-2 *operations* tooling an admin needs to run a real mail server. F4.8 adds a Queue view (list/delete/flush/hold/release via `postqueue`/`postsuper`), a Delivery Log view (tails Postfix's `maillog_file`, filterable by domain/mailbox/status), DKIM key rotation (new selector/key while the previous one stays valid in DNS), and recent Roundcube login activity on the Webmail tab.

Queue and Delivery Log expose server-wide data across every tenant, so both are gated to `ADMIN` role only (`requireRole("ADMIN")`), matching the existing pattern for other server-wide infra views (`/api/backups`, `/api/firewall`, `/api/services`). DKIM rotation and webmail activity stay scoped to the requesting user's own domains/mailboxes.

Comparable tools (Mailcow, cPanel/WHM) all expose: a mail queue manager (list/hold/delete/flush, `postqueue -p`-backed in Postfix's case), a delivery/bounce log viewer, and DKIM key rotation (not just one-shot generation) as core "day-2" admin features.

**Acceptance Criteria:**
- [x] New "Queue" view: lists messages currently in the Postfix queue (`postqueue -p` via `postfix_manager.py`), with delete/flush/hold/release actions
- [x] New "Delivery Log" view: tails/searches recent Postfix delivery and bounce events (success/deferred/bounced) per domain or mailbox
- [x] DKIM section gains a "Rotate key" action (generate a new key, publish new DNS record, keep the old one valid until DNS propagates), not just first-time generate
- [x] Webmail tab shows something more useful than a status badge — recent Roundcube login activity per mailbox, queried from Roundcube's own SQLite database
- [x] All new endpoints follow the existing `mail` module's error-handling and auth patterns

**Test Plan:**
1. Send a test email to an unreachable domain → it appears in the Queue view as deferred, then in the Delivery Log as bounced once retries are exhausted ✅ — verified against the live `vexlyx-postfix` container
2. Manually flush the queue → message delivery is retried immediately ✅ — `postsuper -r`/`postqueue -f` verified
3. Rotate DKIM for a domain → new selector/key published, old key still validates in-flight signed mail until DNS updates propagate ✅ — verified `SigningTable` repoints to the new selector while the old selector's `KeyTable` entry, key files, and DNS record are left untouched
4. Webmail tab shows more than just "running" — last-login per mailbox, queried live from Roundcube's SQLite `users` table ✅

No automated test suite exists in this repo yet (no Vitest anywhere in either app) — standing one up was scoped out of this feature per user decision; all verification above was manual/live-container. Follow-up: introduce Vitest and add coverage for the new service methods, routes, hooks, and panels.

**Developer Docs:**
- **Location:** `docs/dev/email/mail-operations.md`

**Files Created:**
- `apps/dashboard/src/hooks/useQueue.ts`
- `apps/dashboard/src/hooks/useDeliveryLog.ts`
- `apps/dashboard/src/components/mail/QueuePanel.tsx`
- `apps/dashboard/src/components/mail/DeliveryLogPanel.tsx`
- `docs/dev/email/mail-operations.md`

**Files Modified:**
- `apps/api/prisma/schema.prisma` (new `DkimKey` model + `DkimKeyStatus` enum)
- `docker/postfix/main.cf` (`maillog_file`), `docker/postfix/Dockerfile`, `docker/postfix/entrypoint.sh` (log dir/file setup)
- `docker-compose.yml` (bind-mount `./docker/mail-data/logs:/var/log/postfix`)
- `system/python/postfix_manager.py` (queue list/delete/flush/hold/release, delivery log tail/filter, DKIM rotation)
- `system/python/webmail_manager.py` (recent login activity via PHP/SQLite — the Roundcube image has no `sqlite3` CLI)
- `packages/shared/src/schemas/mail.ts`, `packages/shared/src/index.ts` (new Zod schemas/types)
- `apps/api/src/modules/mail/schema.ts`, `service.ts`, `routes.ts` (new endpoints)
- `apps/dashboard/src/hooks/useMail.ts`, `useWebmail.ts` (rotateDkim, webmail activity)
- `apps/dashboard/src/components/mail/WebmailPanel.tsx` (activity list)
- `apps/dashboard/src/app/(panel)/mail/page.tsx` (Queue/Delivery Log tabs, DKIM rotate dialog, ADMIN-gated tab visibility)

---

## Phase 5: System & Administration

### F5.1 — One-Line Server Installer
**Status:** 🟢 COMPLETED

**Description:**
Automated, idempotent installation script that sets up Vexlyx on a fresh Ubuntu 24.04 server via `curl -fsSL https://vexlyx.atlantiqs.org/install.sh | bash`. `install.sh` is a thin bootstrap that clones/updates the repo into `/opt/vexlyx` and hands off to `system/scripts/install/run.sh`, which runs 16 numbered, independently-idempotent steps covering package/Docker/Node/Python installation, config collection, secret generation, building the panel, and bringing up every service (Postgres/MySQL/Redis, Traefik with real Let's Encrypt certs, CoreDNS, Postfix/Dovecot/Roundcube, and the dashboard/API themselves) behind a hardened `docker-compose.prod.yml` overlay, finishing with UFW configuration. DNS is served via CoreDNS (not BIND9 — see F3.3, which already made that call) as Docker containers rather than bare-metal services, since the existing mail-management code (`postfix_manager.py`/`dovecot_manager.py`) is hardwired to `docker exec` against containers.

**Acceptance Criteria:**
- [x] `curl -fsSL https://vexlyx.atlantiqs.org/install.sh | bash` installs everything
- [x] Installs Docker, Docker Compose, Node.js, Python
- [x] Configures PostgreSQL, Redis, Traefik
- [x] Sets up Postfix, Dovecot, CoreDNS (supersedes BIND9 per F3.3's implementation choice)
- [x] Creates admin user
- [x] Generates SSL certificate for panel domain
- [x] Configures firewall (UFW)
- [x] Idempotent (can run multiple times safely)

**Test Plan:**
1. Fresh Ubuntu server → script completes without errors
2. Visit `https://panel.domain.com` → login page loads over a real Let's Encrypt cert, login works
3. All services running → `docker compose -f docker-compose.yml -f docker-compose.prod.yml ps` shows all healthy
4. Re-run script → no errors, no duplicate config/rules/containers

Validated end-to-end on a real Ubuntu EC2 instance through to a working login, a deployed WordPress project, and a verified custom domain. See `docs/dev/installer.md`'s Testing section for the full list of bugs this surfaced (in the installer itself, in Dockerfiles, and a few pre-existing application bugs unrelated to F5.1) and how each was fixed.

**Developer Docs:**
- **Location:** `docs/dev/installer.md`

**Files Created:**
- `install.sh`
- `system/scripts/install/{lib.sh,config.sh,run.sh}`
- `system/scripts/install/steps/01-preflight.sh` … `16-summary.sh`
- `docker-compose.prod.yml`
- `docker/traefik/traefik.prod.yml.tmpl`
- `apps/api/Dockerfile`
- `apps/dashboard/Dockerfile`
- `apps/api/prisma/create-admin.ts`
- `apps/dashboard/public/.gitkeep`
- `.dockerignore`
- `docs/dev/installer.md`

**Files Modified:**
- `docker-compose.yml` (Traefik `v3.4` → `v3.6` for Docker 29+ API compatibility; removed the ineffective `DOCKER_API_VERSION` env var)
- `docker/postfix/entrypoint.sh`, `docker/dovecot/entrypoint.sh` (production hostname override, `VEXLYX_SEED_DEV_FIXTURES` gate on dev-only mailbox seeding)
- `apps/dashboard/next.config.ts` (`output: "standalone"`)
- `apps/api/src/config/env.ts`, `apps/api/src/plugins/auth.ts` (`COOKIE_DOMAIN` for cross-subdomain session sharing)
- `apps/api/package.json`, `apps/api/.env.example`
- `package.json` (`engines.node` → `>=22`)
- `.gitignore`
- `README.md`, `DEV.md` (Node 22+ prerequisite, real repo URL)
- `system/python/build_manager.py` (pre-existing `null`/`None` Python bug, unrelated to F5.1, surfaced by first real-world use)
- `apps/dashboard/src/components/projects/EnvVarEditor.tsx` (autocomplete attributes, unrelated to F5.1, surfaced by first real-world use)
- `apps/dashboard/src/app/(standalone)/projects/[id]/files/page.tsx`, `apps/dashboard/src/components/files/UploadDropzone.tsx`, `apps/dashboard/src/components/projects/FileManagerCard.tsx` (pre-existing F2.8 ESLint errors blocking the first-ever production `next build`)

---

### F5.2 — Resource Monitoring
**Status:** 🟢 COMPLETED

**Description:**
Monitor server and container resource usage (CPU, RAM, Disk, Network) with real-time Socket.io push, BullMQ background collection, historical persistence in PostgreSQL, and threshold alerts.

**Acceptance Criteria:**
- [x] Server-level metrics (CPU, RAM, Disk, Uptime)
- [x] Per-container metrics
- [x] Real-time graphs in dashboard (live gauges via Socket.io + area chart)
- [x] Historical data (1h, 24h, 7d, 30d) stored as 60-second snapshots
- [x] Alert thresholds (CPU > 80%, RAM > 85%, Disk > 90%) — sonner toast + animated badge
- [x] Custom collector (`system_monitor.py`) using psutil + `docker stats`

**Test Plan:**
1. Dashboard shows current CPU/RAM usage ✅ — live SVG gauges, Socket.io push every 5s
2. Container metrics → accurate per-project usage ✅ — `docker stats --no-stream` parser
3. High CPU alert → notification sent ✅ — sonner toast + ThresholdAlertBadge
4. Historical graph → shows trend ✅ — recharts area chart with 1h/24h/7d/30d selector

**Developer Docs:**
- **Location:** `docs/dev/monitoring.md`

**Files Created:**
- `packages/shared/src/schemas/monitoring.ts`
- `system/python/system_monitor.py`
- `apps/api/src/modules/monitoring/schema.ts`
- `apps/api/src/modules/monitoring/service.ts`
- `apps/api/src/modules/monitoring/socket.ts`
- `apps/api/src/modules/monitoring/routes.ts`
- `apps/dashboard/src/hooks/useMonitoring.ts`
- `apps/dashboard/src/components/monitoring/ResourceGauge.tsx`
- `apps/dashboard/src/components/monitoring/UsageBar.tsx`
- `apps/dashboard/src/components/monitoring/MetricHistoryChart.tsx`
- `apps/dashboard/src/components/monitoring/ContainerMetricsTable.tsx`
- `apps/dashboard/src/components/monitoring/ThresholdAlertBadge.tsx`
- `apps/dashboard/src/components/monitoring/MonitoringPage.tsx`
- `apps/dashboard/src/app/(panel)/monitoring/page.tsx`
- `docs/dev/monitoring.md`

**Files Modified:**
- `packages/shared/src/index.ts`
- `apps/api/prisma/schema.prisma` (added `MetricSnapshot` model)
- `apps/api/src/index.ts` (registered `monitoringRoutes`)
- `apps/dashboard/src/components/layout/Sidebar.tsx` (added Monitoring nav item)
- `FEATURES.md`

---


### F5.3 — Backup System
**Status:** 🟢 COMPLETED

**Description:**
Automated and on-demand full-system backups (projects, databases, mail, DNS) with configurable schedule, retention, and per-item restore.

**Acceptance Criteria:**
- [x] Daily automated backups at configurable time — `BackupSettings` singleton row, editable from the dashboard, re-schedules the BullMQ job immediately
- [x] On-demand backup trigger — "Backup Now" button, `POST /api/backups`
- [x] Backup includes: files, databases, mailboxes, DNS zones — full-system snapshot per run
- [x] Backup compression (tar.gz) — one `<snapshotId>.tar.gz` per snapshot
- [x] Retention policy (keep last 7 daily, 4 weekly) — configurable, defaults match; `applyRetention()` runs after every backup
- [ ] Remote backup to S3/MinIO (optional) — deferred; local disk (`BACKUPS_DIR`) only in this pass
- [x] One-click restore from backup — per-item restore (project/database/mail domain/DNS zone) from any completed snapshot, behind a destructive confirmation dialog

**Test Plan:**
1. Trigger backup → archive created successfully ✅ — verified end-to-end via live API (manual trigger → `COMPLETED` snapshot → archive file on disk)
2. Scheduled backup → runs automatically at set time ✅ — BullMQ `upsertJobScheduler` with cron pattern, re-armed on settings change
3. Restore backup → project fully restored ✅ — verified round-trip: seeded a DB row, backed up, corrupted the row, restored, confirmed original value came back
4. Retention → old backups auto-deleted ✅ — `applyRetention()` grandfather-father-son rotation, deletes both DB row and archive file

**Developer Docs:**
- **Location:** `docs/dev/backup-system.md`

**Files Created:**
- `packages/shared/src/schemas/backups.ts`
- `system/python/backup_manager.py`
- `apps/api/src/modules/backups/schema.ts`
- `apps/api/src/modules/backups/service.ts`
- `apps/api/src/modules/backups/socket.ts`
- `apps/api/src/modules/backups/routes.ts`
- `apps/dashboard/src/hooks/useBackups.ts`
- `apps/dashboard/src/components/backups/BackupsPage.tsx`
- `apps/dashboard/src/components/backups/BackupList.tsx`
- `apps/dashboard/src/components/backups/BackupDetail.tsx`
- `apps/dashboard/src/components/backups/RestoreConfirmDialog.tsx`
- `apps/dashboard/src/components/backups/TriggerBackupButton.tsx`
- `apps/dashboard/src/components/backups/BackupSettingsCard.tsx`
- `apps/dashboard/src/app/(panel)/backups/page.tsx`
- `docs/dev/backup-system.md`

**Files Modified:**
- `packages/shared/src/index.ts`
- `apps/api/prisma/schema.prisma` (added `BackupSnapshot`, `BackupSettings` models + `BackupStatus`/`BackupTrigger` enums)
- `apps/api/src/config/env.ts` (added `BACKUPS_DIR`, `BACKUP_SCHEDULE_CRON`, `BACKUP_RETENTION_DAILY`, `BACKUP_RETENTION_WEEKLY`)
- `apps/api/src/index.ts` (registered `backupRoutes`)
- `apps/dashboard/src/components/layout/Sidebar.tsx` (added Backups nav item)
- `FEATURES.md`

---

### F5.4 — Firewall Management
**Status:** 🟢 COMPLETED

**Description:**
Web-based UFW firewall management.

**Acceptance Criteria:**
- [x] List current firewall rules
- [x] Add new rules (port, protocol, source IP)
- [x] Delete rules
- [x] Default policy configuration
- [x] Rule validation (prevent locking out)
- [x] Apply changes with confirmation

**Test Plan:**
1. View rules → shows current UFW status
2. Add rule → port opens, traffic allowed
3. Delete rule → port closed
4. Invalid rule → error, not applied

**Developer Docs:**
- **Location:** `docs/dev/firewall.md`

---

### F5.5 — User Roles & Permissions
**Status:** 🟢 COMPLETED

**Description:**
Role-based access control with Admin, User, and Reseller roles.

**Acceptance Criteria:**
- [x] Admin: full access, manage users, system settings
- [x] User: manage own projects, domains, databases
- [x] Reseller: create sub-accounts, allocate resources
- [x] Role assignment UI
- [x] Permission middleware on API routes
- [x] Resource quotas per role

**Test Plan:**
1. Admin creates user → user can login and create projects
2. User tries admin endpoint → 403 Forbidden
3. Reseller creates sub-account → sub-account works independently
4. Quota exceeded → creation blocked with clear message

**Developer Docs:**
- **Location:** `docs/dev/roles-permissions.md`

---

### F5.6 — Service Status Dashboard
**Status:** 🟢 COMPLETED

**Description:**
Real-time status of all system services.

**Acceptance Criteria:**
- [x] Postfix status (running/stopped/error)
- [x] Dovecot status
- [x] BIND9/CoreDNS status
- [x] Docker daemon status
- [x] PostgreSQL status
- [x] Redis status
- [x] Start/stop/restart controls
- [x] Service logs viewer

**Test Plan:**
1. Dashboard shows all services green
2. Stop Postfix → status changes to red
3. Restart Postfix → status back to green
4. View logs → shows recent service logs

**Developer Docs:**
- **Location:** `docs/dev/service-status.md`

---

### F5.7 — Fast Static & WordPress Serving (No-Build Deploy Path)
**Status:** 🟢 COMPLETED

**Description:**
STATIC/REACT and WORDPRESS project types currently deploy through the exact same path as Node/Python apps: a full Nixpacks build produces a custom Docker image per deploy (`system/templates/docker-compose/static.yml` and `wordpress.yml` both use `image: "{{image_name}}"`, a Nixpacks-built image — confirmed by reading the current templates and `docker_manager.py`). For a plain HTML/static site this means running a full image build (slow, and a heavier image than needed) just to serve files that need no compilation at all — noticed directly while testing F5.3 backups against `backup-test-app` (a single `index.html`).

**Competitor research (2026):** Coolify's dedicated "Static" buildpack packages files straight into a plain Nginx image with **no framework build step**, and for pure static content its docs recommend an even lighter path — a minimal `nginx-static` image with the project directory bind-mounted in, no build stage at all. CapRover follows the same idea: static sites are served by bundling files into a lightweight Nginx image rather than going through its normal app-build pipeline. Neither Coolify nor CapRover run WordPress through a custom per-deploy build either — WordPress ships as a one-click catalog template built on the official `wordpress` Docker Hub image, parameterized with DB credentials, not compiled per install. Across all three major self-hosted PaaS competitors (Coolify, CapRover, Dokploy), the pattern is consistent: **build once (or never) for content that doesn't need it; only run a real build step for projects that actually declare one** (e.g. a Vite `buildCmd`).

**Proposed plan for Vexlyx:**
1. **STATIC/REACT with no `buildCmd`:** skip Nixpacks entirely. Serve directly from a fixed, pre-pulled `nginx:alpine` image with the project's `PROJECTS_DIR/<id>` directory bind-mounted read-only as the web root. No image build step — deploy becomes "start a container," not "build then start."
2. **STATIC/REACT with a `buildCmd` (e.g. Vite):** run the build in an ephemeral Nixpacks/Node builder container that writes its output (e.g. `dist/`) back to disk, then discard the builder and serve the result the same fixed-`nginx:alpine` way as (1). The custom image is never the long-lived container.
3. **WORDPRESS:** replace the Nixpacks-built PHP-FPM image with the official `wordpress:php8.3-fpm-alpine` + `nginx:alpine` pair, wired to the database already provisioned by F2.6 via env vars — same idea as competitors' one-click WordPress templates. No per-install build step.
4. Keep the existing per-project container + Traefik router model (matches Vexlyx's multi-tenant isolation story) — this only replaces the "build a custom image" step with "start a fixed image" step for these two project types. A shared static-file container serving multiple projects via vhosts (lower footprint at scale, weaker isolation) is a further optimization competitors also use, but is out of scope here — flagged as a possible future iteration, not required for this feature.
5. Update `system/templates/docker-compose/static.yml` and `wordpress.yml` to reference the fixed images instead of `{{image_name}}`, and update `docker_manager.py`'s `cmd_deploy` to skip the Nixpacks build call for these two paths.

**Acceptance Criteria:**
- [x] STATIC/REACT project with no `buildCmd` deploys without any Nixpacks build step (bind-mounted `nginx:alpine`)
- [x] STATIC/REACT project with a `buildCmd` still runs the build, but the served container uses the fixed lightweight image, not the Nixpacks output image
- [x] WORDPRESS deploys using the official `wordpress` + `nginx:alpine` images, wired to an F2.6-provisioned database, with no custom build step
- [x] Deploy time for a plain static site drops from a full Nixpacks build to low single-digit seconds
- [x] Resulting container image size for static sites drops to roughly the size of `nginx:alpine` plus site content, not a full Nixpacks-built image
- [x] Existing SPA fallback (index.html routing) and env-var-at-build-time behavior from F2.3 still work (SPA fallback is now a first-party generated `nginx.conf`, since Nixpacks never exposed one)
- [x] Existing WordPress one-click installer, plugin/theme upload, and export/import from F2.4/F2.8 still work against the new image pair (reworked to a wp-content-only persistence model — see dev docs)

**Test Plan:**
1. Deploy a plain HTML project → no Nixpacks build runs, container starts in seconds
2. Deploy a Vite React project with `buildCmd` set → build still runs once, served container is the lightweight image
3. Time a static deploy before/after → confirm meaningful reduction
4. `docker images` before/after → confirm static site images are near `nginx:alpine` size, not a full Nixpacks image
5. One-click WordPress install → still works end-to-end (site loads, admin accessible, DB connected)
6. Re-run F2.8's WordPress export/import test → still passes against the new image pair

**Developer Docs:**
- **Location:** `docs/dev/fast-static-wordpress-serving.md`

---

### F5.8 — Admin/Reseller Direct User Provisioning & Logout
**Status:** 🟢 COMPLETED

**Description:**
Closes gaps found while testing F5.5: there was no way to log out of the dashboard at all, and public self-registration was on by default with no way for an ADMIN or RESELLER to create accounts directly instead.

**Acceptance Criteria:**
- [x] `ALLOW_REGISTRATION` defaults to `false` (closed panel) — `/register` shows an "ask your administrator" message instead of the form when disabled, and the login page hides the "Create one" link, both driven by a new public `GET /api/auth/config` endpoint
- [x] ADMIN can create a user of any role (USER/RESELLER/ADMIN) directly from `/users` via a "New User" dialog
- [x] RESELLER's existing "New Sub-account" flow is unchanged (forced USER role, `maxSubAccounts` quota-checked)
- [x] Header has a working account menu with a "Log out" action that clears the session and redirects to `/login`

**Test Plan:**
1. Fresh install (`ALLOW_REGISTRATION` unset) → `/register` shows the disabled message; `/login` has no register link
2. Set `ALLOW_REGISTRATION=true` → both reappear; `POST /api/auth/register` succeeds
3. As ADMIN, create a RESELLER and a plain USER via "New User" → both appear correctly on `/users`
4. As RESELLER, create sub-accounts until `maxSubAccounts` is hit → blocked with `QUOTA_EXCEEDED`
5. Click the account menu → "Log out" → session cleared, redirected to `/login`

**Developer Docs:**
- **Location:** `docs/dev/roles-permissions.md` (appended)

---

### F5.9 — Onboarding: DNS Records & Public IP Visibility
**Status:** 🟢 COMPLETED — the original application-record flow was verified live on `panel.mindgera.site`; issue #40 extends the installer and dashboard checklist with the hosted-mail A/MX records and custom mail hostname/domain support

**Description:**
Neither the installer nor the dashboard ever tells the installing admin what DNS records to create or what IP to point them at. Confirmed by code audit: `system/scripts/install/config.sh` only prompts for the single panel domain (`VEXLYX_DOMAIN`); `steps/16-summary.sh` prints a generic "make sure your domain points here" warning without stating the server's actual public IP or listing the other hostnames that need records (`webmail.<domain>` for Roundcube, a wildcard `*.<domain>` for deployed project subdomains since `BASE_DOMAIN` defaults to the same zone as the panel — see `docker-compose.prod.yml`'s `BASE_DOMAIN: ${VEXLYX_DOMAIN}`). No code anywhere in the repo currently detects/exposes the server's public IP.

**Acceptance Criteria:**
- [x] Installer detects the server's public IP (e.g. via a simple external lookup, or the primary route's source address) and prints it plainly at the end of setup
- [x] Installer lists every DNS record the admin needs to create: panel, API, webmail and project-wildcard A records, plus `A <VEXLYX_MAIL_HOSTNAME> -> <ip>` and `MX <VEXLYX_MAIL_DOMAIN> -> <VEXLYX_MAIL_HOSTNAME>` (priority 10) for inbound hosted mail — the `api.<domain>` record remains explicit whenever `VEXLYX_BASE_DOMAIN` differs from `VEXLYX_DOMAIN`
- [x] The same information is available post-install in the dashboard (F5.11 Settings page) — `GET /api/system/dns-info` + the DNS Records & Public IP card, plus a live "Verify DNS" check
- [x] Works whether the panel domain and the deployed-app base domain are the same zone (default) or configured separately (`VEXLYX_BASE_DOMAIN`)
- [x] Custom `VEXLYX_MAIL_HOSTNAME` and `VEXLYX_MAIL_DOMAIN` values are preserved in installer output and Settings; inbound routing is kept separate from panel SPF/DKIM/DMARC guidance

**Test Plan:**
1. Run the installer against a fresh server → output clearly lists the IP and every required DNS record before finishing — ✅ verified on `panel.mindgera.site`
2. Skip DNS setup, finish install anyway → dashboard Settings page still shows the same records/IP for later reference — ✅ verified
3. Point DNS as instructed → panel, api, webmail, and a deployed test project's subdomain all resolve and load correctly — ✅ verified (`panel.mindgera.site`, `api.panel.mindgera.site`, `static-app.panel.mindgera.site` all serve real, trusted HTTPS)
4. Exercise default and custom mail hostname/domain configurations → installer output and `GET /api/system/dns-info` contain the expected mail-host A and priority-10 mail-domain MX records; A/MX verification uses the matching DNS lookup type — covered by automated installer and API tests

**Developer Docs:**
- **Location:** `docs/dev/dns-onboarding.md`

---

### F5.10 — Fix Production Subdomain Routing (Traefik HTTPS)
**Status:** 🟢 COMPLETED — verified live on `panel.mindgera.site`: a fresh deploy with no custom domain gets a working `-secure` router and serves trusted HTTPS on its default subdomain

**Description:**
Deployed project subdomains don't work in production (reported against `panel.mindgera.site`). Root cause confirmed by code audit: `docker/traefik/traefik.prod.yml.tmpl` sets a **global** HTTP→HTTPS redirect on the `web` entrypoint, but the deployed-project compose templates (`system/templates/docker-compose/{next,node,php,static,python,wordpress,docker}.yml`) only define a router on the `web` entrypoint — no `websecure` router, no TLS/certresolver. So every request to a default `{slug}.<BASE_DOMAIN>` subdomain gets redirected to HTTPS, where no matching router exists, and the connection dead-ends (this is very likely also the "redirects me to localhost" symptom, since the browser is left with no working route and falls back to whatever it was last showing). Only custom `Domain` records (F3.1/F3.2, which do get `docker/traefik/dynamic/domain-*.yml` with both entrypoints + TLS) work today. Separately, `ContainerControls.tsx:257` and `WordPressPanel.tsx:205` hardcode a `http://localhost:${internalPort}` "view" link, which is actively misleading once the project is reachable at a real subdomain on a remote server.

**Acceptance Criteria:**
- [x] Every deployed-project compose template gets a `websecure` router with TLS/certresolver, mirroring what `Domain` records already receive, so the default `{slug}.<BASE_DOMAIN>` subdomain works over HTTPS out of the box — verified live: `static-app.panel.mindgera.site` (STATIC) and `test-wordpress.panel.mindgera.site` (WORDPRESS) both serve trusted HTTPS with real Let's Encrypt certs
- [x] `docker_manager.py`'s router-label generation is updated consistently across all project types (NODEJS/NEXTJS/PYTHON/REACT/STATIC/PHP/WORDPRESS/DOCKER) — template-only change (`docker_manager.py` does plain string substitution, no per-type Python logic); rendering verified locally for node/next/python/php/static/wordpress/docker templates, and live for STATIC + WORDPRESS
- [x] The "view project" link in the dashboard uses the real `deployedDomain` (or the custom `Domain`, if one is attached) instead of `localhost:<internalPort>`
- [x] Existing custom-`Domain` routing (F3.1/F3.2) is unaffected — verified live: `html.mindgera.site` (a custom `Domain` attached to the static-app project) serves trusted HTTPS correctly alongside the project's own default subdomain

**Test Plan:**
1. Deploy a fresh project with no custom domain attached → its default subdomain loads over HTTPS with a valid cert — ✅ verified
2. Click "View" in the dashboard from a non-local machine → opens the real subdomain, not `localhost` — ✅ verified
3. Attach a custom `Domain` to a project → still works exactly as before — ✅ verified (`html.mindgera.site`)

**Developer Docs:**
- **Location:** `docs/dev/domain-routing.md`

---

### F5.11 — Panel Settings Page
**Status:** 🟢 COMPLETED — verified live on `panel.mindgera.site`: Account, Change Password, and DNS Records & Public IP cards all confirmed working in-browser, including Verify DNS

**Description:**
The Sidebar has always linked to `/settings` (`apps/dashboard/src/components/layout/Sidebar.tsx`), but no page was ever built — it 404s today. Build the real page: account info (name/email), change-password, and (once F5.9 lands) the DNS records/public-IP reference info so an admin can look it up again after the installer output has scrolled away.

**Acceptance Criteria:**
- [x] `/settings` renders instead of 404ing
- [x] Shows the logged-in user's name/email and lets them change their password — `POST /api/auth/change-password` fully tested (wrong current password, mismatched confirm, no auth, success + old password rejected + new password works)
- [x] Once F5.9 ships, shows the server's public IP and the required DNS records for reference — ADMIN-only card, reuses F5.9's `GET /api/system/dns-info`
- [x] UX follow-up (user-requested): a setup blurb explains what to do with the records, and a "Verify DNS" button live-checks propagation via `POST /api/system/dns-info/verify` (cross-resolver DNS lookups, same pattern as F3.3's domain propagation check) — verified locally against a real resolvable hostname (`one.one.one.one` → `1.1.1.1`)
- [x] Linked correctly from the Sidebar (already wired, just needs a page)

**Test Plan:**
1. Click "Settings" in the sidebar → real page loads, no 404 — ✅ verified live
2. Change password → can log in with the new password, old one rejected — ✅ verified (both locally via curl and confirmed by the user in-browser)
3. After F5.9 ships → DNS/IP reference section shows accurate, current values — ✅ verified live on `panel.mindgera.site`

**Developer Docs:**
- **Location:** `docs/dev/settings-page.md`

---

### F5.12 — Consistent Refresh Button Animation (Design System Enforcement)
**Status:** 🟢 COMPLETED

**Description:**
CLAUDE.md's design system mandates a dedicated `isRefreshing` state with `animate-spin` on the `RefreshCw`/`RotateCw` icon for 500-600ms on every refresh action, but a full-repo audit found at least 4 different patterns in actual use:
1. Correct pattern (dedicated state + timeout): most pages (`databases/page.tsx`, `projects/page.tsx`, `BuildPanel.tsx`, `ContainerControls.tsx`, `DatabasePanel.tsx`, `EnvVarEditor.tsx`, `GitSettings.tsx`, `domains/page.tsx`, `domains/[id]/dns/page.tsx`, `domains/[id]/ssl/page.tsx`, `DnsManagementModal.tsx`, `mail/page.tsx`, `WebmailPanel.tsx`).
2. Spins for the real (variable) network duration instead of a fixed 500-600ms: `MonitoringPage.tsx:220-222` (bound to react-query's `isFetching`), `FileTree.tsx:305,347`, `FileManagerCard.tsx:22,46`, `SftpPanel.tsx:71,80`.
3. No spin animation at all: `app/(standalone)/projects/[id]/files/page.tsx:362`.
4. Wrong icon (`RotateCw` instead of the app's `RefreshCw`) and/or wrong timeout (500ms instead of 600ms): `ContainerControls.tsx:196`, `WordPressPanel.tsx:118`, `DockerfilePanel.tsx:84`.
5. `GitSettings.tsx:324,436` uses `RefreshCw` for "Generate/Regenerate" buttons with no spin binding at all (swaps to `Loader2` instead) — a third distinct pattern for a refresh-shaped action.

**Acceptance Criteria:**
- [x] A single shared helper/hook (`useRefreshAnimation()` in `apps/dashboard/src/hooks/useRefreshAnimation.ts`, plus a `refreshIconClassName()` companion for the icon classes) encapsulates the "set isRefreshing, animate-spin, clear after 600ms (floor, even if the real fetch finishes faster)" pattern
- [x] Every refresh-shaped button in the dashboard is migrated to use it, including the 4 categories of offenders listed above — both component-owned `isRefreshing` state (17 files) and data-hook-owned state like `useDomains`/`useMail`/`useWebmail` etc. (7 hooks + their consumers)
- [x] `RefreshCw` is used consistently for "refresh/reload data" actions; `RotateCw`/`Loader2` are reserved for genuinely different actions — `GitSettings.tsx`'s "Generate/Regenerate SSH Key" and "Regenerate Secret" buttons (mutation actions, not refreshes) now use `KeyRound`/`RotateCw` idle icons with a `Loader2` swap while pending, instead of `RefreshCw`
- [x] Manual click-through of every page confirms a consistent ~600ms spin feel regardless of actual network latency — verified live (databases/projects/domains/monitoring refresh buttons, GitSettings KeyRound/RotateCw idle icons)

**Test Plan:**
1. Throttle network to "Slow 3G" in devtools → every refresh button still only spins for ~600ms visually (the underlying fetch continues in the background), not the full slow-network duration
2. Click every refresh-shaped button across the app → same icon, same animation duration everywhere

**Developer Docs:**
- **Location:** `docs/dev/design-system.md` ("Refresh Buttons" section)

**Developer Docs:**
- **Location:** `docs/dev/design-system.md` (append "Refresh Buttons" section)

---

### F5.13 — Monitoring: Per-Core CPU & Configurable Timezone
**Status:** 🟢 COMPLETED

**Description:**
Two related gaps found during review:
- **CPU cores**: `system/python/system_monitor.py` only ever collects an aggregate `psutil.cpu_percent(interval=interval)` (line 77) into a single `cpuPercent` field (`MetricSnapshot.cpuPercent` in `schema.prisma`) — there is no per-core breakdown and no core-count field anywhere in the schema or API, so the dashboard has no way to show individual core load even if it wanted to.
- **Timezone**: nothing in the repo is timezone-aware. Every displayed timestamp uses `toLocaleString(undefined, …)` (browser-default, unlabeled) across `databases/page.tsx`, `domains/page.tsx`, `domains/[id]/ssl/page.tsx`, `projects/[id]/page.tsx`, `BuildPanel.tsx`, `BackupList.tsx`, `BackupDetail.tsx`, etc. The backup schedule cron (`BackupSettings.scheduleCron`) is passed to BullMQ's repeatable job with no `tz` option (`apps/api/src/modules/backups/service.ts`), so "0 3 * * *" silently means "3am in whatever timezone the API server's OS is set to" — and the UI (`BackupSettingsCard.tsx`) labels it "daily at 3am" with no qualifier, which is confusing for a server in a different timezone than the admin.

**Acceptance Criteria:**
- [x] `system_monitor.py` collects per-core percentages (`psutil.cpu_percent(percpu=True)`) and core count — live-only (per user decision, not persisted to `MetricSnapshot`/history), exposed via the existing `ServerMetrics` payload (`cpuPerCore`, `cpuCoreCount`)
- [x] Monitoring dashboard shows a per-core breakdown (`PerCoreCpuBars.tsx`, one bar per core) alongside the existing aggregate CPU gauge
- [x] A server-timezone setting is added — new `SystemSettings` singleton model (per user decision, not folded into `BackupSettings`), defaulting to `Intl.DateTimeFormat().resolvedOptions().timeZone`, overridable from the Settings page (F5.11)'s new "Server Timezone" card
- [x] The backup cron schedule is passed to BullMQ with an explicit `tz` option matching the configured timezone (`backups/scheduler.ts` re-upserts immediately on a timezone change), and `BackupSettingsCard.tsx` states which timezone "3am" refers to
- [x] Displayed timestamps across the dashboard respect the configured timezone — full sweep (per user decision) of all 11 files found using `toLocaleString`/`toLocaleDateString`/`toLocaleTimeString`, now routed through `lib/datetime.ts` + `useTimezone()`

**Follow-up (user-confirmed live via a monitoring screenshot):** the monitoring page rendered correctly with no per-core bars — confirmed as the expected fallback (psutil not installed on this dev box), not a bug. Two fixes applied:
- `system/scripts/install/steps/04-runtime.sh` now `pip3 install`s `psutil` alongside the existing `cryptography` — previously nothing in the installer actually installed it despite `system_monitor.py`'s own docstring calling it required/preferred, so every fresh production install was silently running the degraded `/proc`-parsing fallback (no per-core data) unless someone installed it by hand.
- `MonitoringPage.tsx` now shows a muted "Per-core breakdown unavailable — install `psutil`..." hint instead of silently hiding the section, but only when `cpuCoreCount > 1` (i.e. the server genuinely has multiple cores and the fallback engaged) — avoids a misleading hint on an actual single-core box.

**Test Plan:**
1. Monitoring page shows N per-core bars matching the server's actual core count — first checked with psutil absent (dev box, pre-existing condition): `GET /api/monitoring/server` correctly returned `cpuCoreCount: 8` with `cpuPerCore` as a single-element fallback array, `PerCoreCpuBars` correctly stayed hidden and the new "install psutil" hint rendered instead — confirmed live via a `/monitoring` screenshot (no per-core bars, page otherwise fully intact). After `pip install psutil` + a clean restart of the API dev process (a set of stale orphaned `tsx watch` processes from earlier in this session were holding the pre-install environment — killed and relaunched fresh), `GET /api/monitoring/server` returned real per-core data: `cpuPerCore: [0, 0, 38.5, 7.7, 8.3, 7.7, 8.3, 0]`, 8 independent values matching `cpuCoreCount: 8`. `system/python/system_monitor.py` invoked directly also confirmed correct psutil-path output.
2. Set the timezone via `PUT /api/system/settings` → verified live: rejects an invalid tz (400, `VALIDATION_ERROR`), accepts `Europe/London` (200), API stayed up (uptime kept climbing, no restart) confirming the immediate BullMQ re-upsert didn't crash the process. Reset back to the auto-detected `Asia/Karachi` afterward.
3. Confirmed existing aggregate CPU/RAM/disk charts are unaffected — `pnpm typecheck`/`pnpm lint`/`pnpm build` pass clean across `@vexlyx/shared`, `@vexlyx/api`, `@vexlyx/dashboard`; `/settings` and `/monitoring` confirmed live via browser screenshot (user-provided) showing the page fully intact — gauges, historical chart, container table all rendering correctly alongside the new per-core section.

**Developer Docs:**
- **Location:** `docs/dev/monitoring.md` (append "Per-Core CPU & Timezone" section)

---

### F5.14 — Fix Backup Failure Diagnostics ("exited with code 2 and no output")
**Status:** 🟢 COMPLETED

**Description:**
Reported live: a backup run shows `Backups: FAILED — Backup script exited with code 2 and no output`. Root-caused by code audit: `system/python/backup_manager.py` never calls `sys.exit(2)` itself — its only intentional exit path is `sys.exit(1)` inside `fail()`, always preceded by a JSON print to stdout. Exit code 2 with **zero** stdout means the Python interpreter/process died *before* any Python code ran — almost certainly the OS-level "can't open file '<path>': No such file or directory" (errno 2) from a misresolved `PYTHON_BIN`/script path (`apps/api/src/modules/backups/service.ts`'s `getBackupScriptPath()` falls back to a guessed path if none of its candidates exist), or a wrong/missing Python interpreter. Separately, `service.ts` *does* capture the child process's stderr but only logs it at `logger.debug` — it's never included in the `BackupError` message actually shown to the user (`"Backup script exited with code ${code} and no output"`), so the real cause is invisible to whoever's looking at the failure in the dashboard.

**Acceptance Criteria:**
- [x] `service.ts`'s error message includes captured stderr when present, instead of the generic "no output" message
- [x] Confirm (in the actual failing environment) whether `PYTHON_BIN`/the resolved script path is correct; fix the path-resolution fallback or document the required `PYTHON_BIN` setting if not — confirmed live on 13.51.200.65 (post-reinstall) that both resolve correctly; couldn't reproduce the original misconfig, so `PYTHON_BIN` was added to `env.ts`/`.env.example` as documented override rather than changing the (working) fallback logic
- [x] Add a startup/health check (e.g. on API boot, or as part of the installer) that verifies the configured Python interpreter and `backup_manager.py` path are both resolvable, failing loudly at startup rather than silently at the next scheduled backup
- [x] Re-run a scheduled and a manual backup successfully after the fix — triggered `POST /api/backups` on the live server (13.51.200.65) as ADMIN, snapshot `cmtw2ej7r000xn11s21x7ummp` reached `COMPLETED` in ~2s with a full manifest (2 projects, 1 MySQL DB, 1 DNS zone) and no error

**Test Plan:**
1. Reproduce locally by pointing `PYTHON_BIN` at a nonexistent path → confirm the new error message shows the real stderr instead of "no output"
2. Fix the actual misconfiguration on the affected server → next backup run succeeds
3. Trigger a manual backup from the dashboard → completes with `COMPLETED` status

**Developer Docs:**
- **Location:** `docs/dev/backup-system.md` (append "Troubleshooting" section)

---

### F5.15 — Docker Image/Container Cleanup & Disk Reclamation
**Status:** 🟢 COMPLETED

**Description:**
Every redeploy leaves the previous build's Docker image and layers on disk — confirmed by audit: `docker_manager.py`'s `cmd_deploy` uses `docker compose up -d --force-recreate --pull never` (replaces the container but never removes the old image), and `cmd_remove` only runs `docker compose down --volumes --remove-orphans` (no `docker image rm`, no pruning). There is no scheduled or manual cleanup job anywhere in the repo, and no disk-usage-by-category breakdown (images/volumes/containers) in the monitoring module — so disk fills up silently over time with no visibility or way to reclaim it from the panel.

Comparable tools all solve this: **Coolify** runs configurable automated cleanup (by disk-usage threshold or cron) that removes stopped containers/unused images/build cache, skipping cleanup during an active deploy; **Dokploy** exposes 5 discrete ops (clean unused images/volumes/stopped containers/builder cache/all) runnable manually or via a daily cron; **CapRover** ships a manual "Disk Clean-Up" action (`docker container prune` + `docker image prune --all`).

**Acceptance Criteria:**
- [x] Monitoring/Settings page shows a disk-usage breakdown by category (images, containers, volumes, build cache) — e.g. via `docker system df`
- [x] A manual "Clean up" action in the dashboard runs the equivalent of `docker container prune` + `docker image prune -a` (skipping images belonging to currently-running containers)
- [x] An optional scheduled cleanup job (cron, mirroring the existing `BackupSettings.scheduleCron` pattern), off by default
- [x] Redeploying a project optionally removes the previous image after the new one is confirmed healthy (not immediately, to allow rollback)
- [x] Cleanup never removes an image/container currently in use by a running project

**Test Plan:**
1. Redeploy a project several times → confirm old images accumulate (reproducing the current bug) before the fix
2. Run "Clean up" from the dashboard → disk usage drops, running projects unaffected
3. Enable the scheduled cleanup → runs automatically on schedule, same safety guarantees
4. Disk-usage breakdown reflects real `docker system df` numbers

**Developer Docs:**
- **Location:** `docs/dev/docker-cleanup.md`

---

### F5.16 — Dashboard Home Page: Real Widgets
**Status:** 🟢 COMPLETED

**Description:**
`apps/dashboard/src/app/(panel)/dashboard/page.tsx` is a pure stub today — confirmed by its own doc comment: "Currently uses placeholder data with loading skeletons. Will be connected to real API data in Phase 1." It's 4 `StatCard`s all hardcoded to `value="0"` plus a static "Getting Started" box — no charts, no recent activity, no quick actions, no real data fetching at all, which is why it "looks static."

**Acceptance Criteria:**
- [x] Stat tiles show real counts (projects, domains, databases, mailboxes) fetched from the existing list endpoints, not hardcoded zeros
- [x] A resource-usage widget (CPU/RAM/disk) reusing data already collected by F5.2's monitoring, so the home page reflects real server health at a glance
- [x] A "recent activity" feed (recent deployments, recent backups, recent domain/SSL status changes) — reusing existing `Deployment`/`BackupSnapshot` data
- [x] Quick-action buttons (e.g. "New Project", "New Domain") for common tasks
- [x] "Getting Started" box only shows for genuinely empty accounts (zero projects), not unconditionally

**Test Plan:**
1. Fresh account with nothing created → stat tiles show real zeros, "Getting Started" box shows
2. Account with projects/domains/databases → stat tiles show accurate counts, resource widget shows live server data, recent activity reflects real recent actions
3. Quick actions navigate to the right creation flows

**Developer Docs:**
- **Location:** `docs/dev/dashboard-home.md`

---

### F5.17 — Two-Factor Authentication (2FA/TOTP)
**Status:** 🟢 COMPLETED

**Description:**
Competitor audit (F5.5 follow-up): Plesk, cPanel/WHM, and CapRover all support 2FA on login, tied to their access-control system — Vexlyx currently has none, at any role. Given Vexlyx's ADMIN role has unrestricted access (including firewall and backups), this is a meaningfully higher-value security feature than for a typical SaaS app.

**Acceptance Criteria:**
- [x] TOTP-based 2FA (compatible with standard authenticator apps), optional per-user, enforceable-by-policy for ADMIN (e.g. an env flag requiring it for the ADMIN role specifically)
- [x] Setup flow: QR code + manual secret entry, backup/recovery codes shown once
- [x] Login flow: password, then TOTP challenge if enabled, before session creation
- [x] Works alongside the existing Argon2id + Redis session auth (`apps/api/src/plugins/auth.ts`) without replacing it

**Test Plan:**
1. Enable 2FA on an account → login requires password + valid TOTP code
2. Wrong/expired TOTP code → login rejected, no session created
3. Recovery code → works once, then is invalidated
4. Account without 2FA enabled → unaffected, logs in as before

**Developer Docs:**
- **Location:** `docs/dev/two-factor-auth.md`

---

### F5.18 — Audit Log
**Status:** 🟢 COMPLETED

**Description:**
Competitor audit: Dokploy ships audit logs as a first-class access-control feature; cPanel/WHM has detailed action logging. Vexlyx has none — no record of who changed a role, deleted a user, modified a firewall rule, or restored a backup, beyond each individual module's own DB rows (e.g. `FirewallRule.createdBy`). With F5.5-F5.8's admin/reseller user-management now live, this gap is more pressing — an ADMIN can silently change any user's role or delete any account with no trail.

Scope was extended slightly beyond the original criteria (with sign-off) to also cover create/delete for projects, domains, databases, and mailboxes — not just the 5 originally-listed action types.

**Acceptance Criteria:**
- [x] New `AuditLog` table: actor (userId), action, target (type + id), metadata (before/after where relevant), timestamp
- [x] Logged at minimum: role changes, quota changes, user creation/deletion, firewall rule/policy changes, backup restore/delete
- [x] Admin-only `/audit-log` view (table, filterable by actor/action/date)
- [x] Does not log request bodies containing secrets (passwords, DB credentials, encrypted env vars)

**Test Plan:**
1. Admin changes a user's role → entry appears with old/new role, correct actor
2. Reseller deletes their own sub-account → entry appears attributed to the reseller, not the admin
3. Firewall rule added/removed → entry appears
4. `/audit-log` page paginates and filters correctly

**Developer Docs:**
- **Location:** `docs/dev/audit-log.md`

---

### F5.19 — Fine-Grained Custom Permissions
**Status:** 🟢 COMPLETED

**Description:**
Competitor audit: Vexlyx's RBAC is fixed (ADMIN/RESELLER/USER, no per-permission toggles), while WHM (ACL templates per reseller), Plesk (Service/Reseller Plan permission properties, independent of resource limits), and Dokploy (25+ resource categories × CRUD+Deploy/Cancel/Restore, Enterprise tier) all let an admin grant a sub-account/reseller a specific subset of capabilities rather than an all-or-nothing role. Coolify, by contrast, is also fixed-role and has open community requests (coollabsio/coolify#2378, #5293) for exactly this — confirming it's a recognized gap across the market, not just Vexlyx.

**Acceptance Criteria:**
- [ ] A permission model beyond the 3 fixed roles — e.g. a `Permission` enum (canManageFirewall, canManageBackups, canCreateSubAccounts, canManageDns, …) assignable per-user by an ADMIN, layered on top of the existing role (role sets sane defaults, permissions can narrow or extend within role boundaries)
- [ ] `requireRole` middleware (`apps/api/src/plugins/auth.ts`) gains a `requirePermission` counterpart, or is extended to check both
- [ ] UI on `/users` edit dialog to toggle individual permissions for a user
- [ ] Backward compatible: existing ADMIN/RESELLER/USER behavior is the default when no custom permissions are set

**Test Plan:**
1. Admin grants a USER `canManageDns` without full RESELLER role → that user can manage DNS but not create sub-accounts or see other users
2. Revoke a permission → immediately enforced on next request (same DB-lookup pattern as `requireRole`)
3. Default (no custom permissions set) → behaves identically to current F5.5/F5.8 behavior

**Developer Docs:**
- **Location:** `docs/dev/fine-grained-permissions.md`

---

### F5.20 — Reseller Overselling Mode for Quotas
**Status:** 🟢 COMPLETED

**Description:**
Competitor audit: WHM's "Overselling" feature lets a reseller nominally assign sub-accounts more resources than the reseller's own cap, while WHM enforces the reseller's real limit against actual aggregate *usage* rather than the nominal sum — standard practice in reseller hosting, since most sub-accounts never use their full allocation. Vexlyx's current model (`apps/api/src/utils/quota.ts`) is the simpler, non-overselling case: a reseller's `maxSubAccounts` and other quotas are flat caps with no allocation/usage distinction. This is a legitimate, deliberately simpler v1 — this task tracks the natural v2 once real reseller usage patterns are known.

**Acceptance Criteria:**
- [x] Optional "overselling" mode per reseller (off by default, matching current behavior)
- [x] When enabled, a reseller can set sub-account quotas that nominally sum above their own limit
- [x] Enforcement switches from "nominal sum ≤ reseller limit" to "actual aggregate usage ≤ reseller limit" at resource-creation time
- [x] Clear UI indication when a reseller is in oversold territory (nominal > limit) so they understand the risk

**Test Plan:**
1. Reseller with `maxProjects: 10` creates 3 sub-accounts each with `maxProjects: 5` (nominal sum 15 > 10) — allowed once overselling is on
2. Actual project creation across those sub-accounts still blocked once real aggregate usage hits 10
3. Overselling off (default) → nominal-sum behavior unchanged from today

**Developer Docs:**
- **Location:** `docs/dev/reseller-overselling.md`

---

### F5.21 — No-Build PHP Hosting (File-Manager-First, Traditional-Panel Style)

**Status:** 🟢 COMPLETED — verified live in two passes: (1) a synthetic composer-less `index.php` project deployed in seconds with no Nixpacks build, confirmed read-write vs read-only mounts, confirmed `composer.json` projects still build via Nixpacks unaffected; (2) a real ~26k-file Duplicator WordPress migration surfaced and fixed four additional bugs the synthetic test missed — nginx's 60s `fastcgi_read_timeout` too short for real extraction, a `wp-login.php` HTTPS redirect loop (PHP never saw `$_SERVER['HTTPS']` behind Traefik's TLS termination), a cross-project request-routing bug (Compose's `app`/`web` service-name aliases collide on the shared `traefik-net` when 2+ projects run at once), and pretty permalinks (`/about-page/`) 404ing because `location /` hard-404'd instead of falling back to `index.php`. All four fixed in the templates and confirmed working end-to-end afterward, including real page content rendering correctly — see `docs/dev/no-build-php-hosting.md`

**Description:**
F5.7 gave STATIC/REACT and WORDPRESS a no-build deploy path, but plain PHP projects were left out of scope and still go through Nixpacks unconditionally — even for a project that's just a handful of `.php` files with no Composer dependencies, which is architecturally identical to a no-`buildCmd` static site. This surfaced directly while helping a user deploy a Duplicator (WordPress migration) backup: it's an `installer.php` + a site archive `.zip`, no `composer.json`, no `index.php`. Nixpacks' own PHP provider detects a project as PHP only when it finds a `composer.json` **or** an `index.php` (confirmed against the official docs — see sources), so `nixpacks build` failed outright with "unable to generate a build plan" even though Vexlyx's own (more lenient) framework detection had already classified it as PHP. As an immediate stopgap (not a real fix), `build_manager.py`'s `cmd_build` now auto-writes an empty `composer.json` when a PHP/WordPress project has none, purely so Nixpacks' detection succeeds — this should be reconsidered/removed once real no-build PHP hosting ships, since the correct fix is skipping the build entirely, not tricking Nixpacks into running one.

The user's underlying ask: why can't a plain PHP site work the way it does on Hestia/CyberPanel/cPanel — drop files in the File Manager, no build step, just running PHP immediately?

**Competitor research (2026):**
- **CapRover**: `captain-definition` supports an `imageName` field that points straight at a pre-built image (e.g. `php:apache`) and skips the build step entirely — CapRover's own docs frame this as the standard way to deploy an app "using a pre-built image," no Dockerfile or build config needed. ([One-Click Apps | CapRover](https://caprover.com/docs/one-click-apps))
- **Coolify**: has an explicit "Static Site" toggle (served by Nginx, no build) for SPA/HTML content, but plain PHP without a `composer.json` is a known rough edge — the community workaround is a custom Dockerfile with a conditional `composer install` rather than any first-party no-build PHP mode. ([Deploy A PHP Application With Coolify](https://www.raqmedia.com/deploy-a-php-application-with-coolify/), [Applications | Coolify Docs](https://coolify.io/docs/applications))
- **Dokploy**: offers Nixpacks, Buildpacks, and Dockerfile build types, but its own docs caution that Nixpacks/buildpacks are resource-heavy to run on the server and recommend a Dockerfile with a pre-built image for production — i.e. even Dokploy's own guidance leans toward "don't build on every deploy" for anything that doesn't need to. ([Build Type | Dokploy](https://docs.dokploy.com/docs/core/applications/build-type))
- **HestiaCP / CyberPanel** (the actual reference point the user compared us to): neither has a "build" concept at all for PHP. Both run a persistent nginx/OpenLiteSpeed + PHP-FPM pool per domain on the host; the File Manager just writes files into the docroot and the already-running PHP-FPM pool picks them up immediately. This is a fundamentally different architecture (shared host-level runtime, not per-project containers) but it's the UX bar being compared against. ([HestiaCP vs CyberPanel 2026](https://panelica.com/blog/cyberpanel-vs-hestiacp-2026))
- **Nixpacks PHP provider detection**: officially documented as composer.json-or-index.php only — confirms the root cause above. ([PHP | Nixpacks](https://nixpacks.com/docs/providers/php))

**Proposed plan (for whoever picks this up):**
1. Extend F5.7's already-built no-build pattern to plain PHP: when a PHP project has no `buildCmd` and no `composer.json`, skip Nixpacks entirely and bind-mount the project directory read-only into a fixed `php:8.3-fpm-alpine` + `nginx:alpine` pair — the same two-container shape F5.7 already built for WordPress (`system/templates/docker-compose/wordpress.yml`, `primary_service_name()` in `docker_manager.py`, the `system/templates/nginx/*.template` generation machinery), generalized instead of WordPress-specific.
2. PHP projects that do have a `composer.json`/real dependencies keep going through Nixpacks exactly as today — same "build only when there's actually something to build" distinction F5.7 already draws for static sites with vs without a `buildCmd`.
3. Remove the stopgap auto-`composer.json` injection in `cmd_build` once this ships (or keep it only as a last-resort fallback for the Nixpacks-build path, not the primary fix).
4. Open design question to resolve during planning: does this replace the PHP project type's behavior outright (auto-detected), or is it a separate mode/toggle? Lean toward auto-detected (mirrors the STATIC/REACT buildCmd-presence check) unless research turns up a reason users need to force one path or the other.

**Acceptance Criteria:**
- [x] PHP project with no `composer.json` and no `buildCmd` deploys without any Nixpacks build step
- [x] PHP project with a `composer.json`/dependencies still builds via Nixpacks as today
- [x] A Duplicator-style migration package (arbitrary `.php` entry file + assets, no `composer.json`) deploys and runs correctly with zero manual intervention
- [x] Stopgap `composer.json` auto-injection in `cmd_build` is demoted to a fallback (only fires if a build is explicitly forced on a composer-less PHP project)

**Test Plan:**
1. Upload a single `index.php` with no `composer.json` → deploys in low single-digit seconds, no Nixpacks build logged
2. Upload a Duplicator backup (`installer.php` + archive `.zip`, no `composer.json`) → deploys without needing a manually-added `composer.json`; `installer.php` runs
3. Deploy an existing PHP project with `composer.json` (e.g. Laravel) → still builds via Nixpacks, unaffected

**Developer Docs:**
- **Location:** `docs/dev/no-build-php-hosting.md`

---

### F5.22 — Clarify "Manage DNS" as an Optional Alternative, Not a Required Step
**Status:** 🟢 COMPLETED

**Description:**
Found live while testing custom domain attachment on `panel.mindgera.site`: after attaching a domain to a project (F3.1 — TXT verification + an A record pointed at the server, entirely self-serve at the user's existing registrar/DNS provider), the `/domains` list page shows a "Manage DNS" button on every domain card, styled and positioned identically to "Manage SSL" (`apps/dashboard/src/app/(panel)/domains/page.tsx:646-668`) — as if both are required follow-up steps. Clicking it lands on `/domains/[id]/dns`, which is actually a **separate, optional feature** (F3.3): fully delegating the domain's authoritative DNS hosting to Vexlyx's own CoreDNS (`ns1.vexlyx.com`/`ns2.vexlyx.com`, `domains/[id]/dns/page.tsx:497-510`). A user who just wants to point one subdomain at their project — keeping DNS at their existing registrar, which already works correctly via the A/TXT records — has no reason to ever touch this, but the UI gives no indication it's optional. Confirmed via user feedback: "why I show the NS panel if here I just want to add a domain, not manage the domain's [name]server."

**Acceptance Criteria:**
- [x] "Manage DNS" is visually/textually distinguished from required setup steps — e.g. relabeled (something like "Host DNS on Vexlyx") and/or an "optional" badge or tooltip explaining what it actually does before the user clicks in
- [x] The DNS zone page itself (`domains/[id]/dns/page.tsx`) gets a brief explanatory note at the top clarifying this delegates the *entire domain's* DNS hosting to Vexlyx and is unrelated to whether the attached project routes correctly (which A/TXT records at any provider already handle)
- [x] No functional change to either flow — both F3.1 (self-serve A/TXT) and F3.3 (CoreDNS zone hosting) keep working exactly as they do today; this is a clarity/labeling fix only

**Test Plan:**
1. Attach a domain to a project, verify it, add the A record at an external registrar → domain routes correctly without ever visiting `/domains/[id]/dns`
2. Visit `/domains` → the DNS-hosting button reads as clearly optional/alternative, not a required next step
3. Visit `/domains/[id]/dns` directly → explanatory copy makes clear this is "become the nameserver" territory, distinct from the simpler per-domain A/TXT setup

**Developer Docs:**
- **Location:** `docs/dev/dns-management.md` (§9 "Two DNS Modes" — the standalone `docs/dev/domains-dns.md` proposed originally didn't exist; F3.3's DNS zone hosting doc already covers this exact page and was the natural home for the distinction)

---

### F5.23 — System Transactional Email (Panel-to-User Notifications)
**Status:** 🟢 COMPLETED

**Description:**
Surfaced while planning F5.18 (Audit Log): Vexlyx has no way to email its own panel users for critical/informational events (password reset, security alerts like a new-role/2FA change, quota-warning notices, backup-failure notices, audit events, etc.). This is distinct from the existing `docker/postfix` stack (F4.1, completed), which is customer-facing mail *hosting* — it lets Vexlyx-hosted domains send/receive mail via their own mailboxes, with no involvement from the Vexlyx application itself. There is currently no password-reset flow, no email-verification flow, and no notification/email-template model in the schema at all — this would need to be built from scratch, not just wired up.

**Research findings (2026):**
- No existing code sends outbound app email today. Existing `SMTP_HOST`/`IMAP_HOST` env vars (`apps/api/src/modules/mail/service.ts`) are only used to health-check the Postfix/Dovecot containers for the customer mail-hosting feature, unrelated to this.
- Two viable delivery approaches, either is reasonable:
  1. **Reuse the existing Postfix instance as an internal relay** — submit via port 587 from a dedicated internal sender identity/domain (e.g. `noreply@panel.<host-domain>`) with its own DKIM key via the existing OpenDKIM milter setup. No new dependency, no third-party account, but self-hosted deliverability (SPF/DKIM/DMARC, IP reputation) is entirely on the operator.
  2. **Third-party transactional provider** (Resend, Postmark, SES, etc.) — better out-of-the-box deliverability, but is a new dependency requiring user confirmation per CLAUDE.md §6, an API key/secret to manage, and a per-install config step.
- `User` model (`apps/api/prisma/schema.prisma:142`) has no `resetToken`, `emailVerified`, or similar fields; no `Notification`/`EmailTemplate` model exists anywhere in the schema.

**Acceptance Criteria:**
- [x] Decide delivery mechanism (internal Postfix relay vs. third-party provider) — needs explicit user sign-off given CLAUDE.md's "no new dependencies without confirming" rule
- [x] Password-reset flow (request → emailed token → reset), since none exists today
- [x] Critical/security notifications: role change, 2FA enabled/disabled (once F5.17 ships), backup failure (new login from unrecognized location deferred — needs login history)
- [x] Quota-warning notification (approaching/at plan limits)
- [x] Simple email template system (plain layout + subject/body per event type), no marketing/HTML-builder scope
- [x] Per-install SMTP/provider configuration (env vars, documented in `.env.example` per CLAUDE.md §14 process)
- [x] Does not duplicate or interfere with the existing customer mail-hosting stack (F4.1)

**Test Plan:**
1. Trigger password reset → email received with working, single-use, expiring token
2. Admin changes another user's role → that user receives a notification email
3. Reseller quota nears limit → warning email sent once, not spammed on every request
4. Existing customer mail hosting (F4.1) continues to function unaffected

**Developer Docs:**
- **Location:** `docs/dev/system-transactional-email.md`

---

### F5.24 — File Manager: Permissions (chmod) & Archive Extract/Compress

**Status:** 🟢 COMPLETED

**Description:**
Surfaced directly while live-testing F5.21 against a real Duplicator (WordPress migration) package: Duplicator's own `installer.php` handles its archive's extraction internally, but the File Manager itself (`apps/api/src/modules/files/`, `FileManagerCard.tsx` / the standalone `/projects/[id]/files` page) has no way to extract an arbitrary uploaded `.zip`/`.tar.gz` on the server, or to change a file/folder's permissions. Confirmed by reading `apps/api/src/modules/files/routes.ts`: today's routes are `list`, `read`, `create`, `write`, `delete`, `rename`, `mkdir`, `copy`, `move`, `download`, `upload` — no `extract`/`compress`, no `chmod`. For any uploaded archive that *isn't* a self-extracting installer (a plain site backup `.zip`, a theme/plugin `.zip`, a Composer vendor dump, etc.) the only way to get its contents onto disk today is to unzip it locally first and re-upload every file individually. Permissions matter for the same class of workflow: some installers/frameworks expect a config file at `640`/`600` or a writable `storage/`/`uploads/` directory at `755`, and there's currently no way to fix that without shell access to the host.

**Competitor research (2026):**
- **cPanel**: File Manager natively supports Zip, gzipped tar (`.tar.gz`), and bzip2 tar (`.tar.bz2`) — both "Compress" and "Extract" are first-class toolbar actions. Permissions are editable per file/folder via a "Change Permissions" dialog (owner/group/other read/write/execute checkboxes, i.e. GUI chmod), though cPanel's own GUI does **not** support recursive chmod through a folder (that needs SSH/`chmod -R`). ([cPanel File Manager guide](https://cpanelreview.com/index.php/2026/04/30/cpanel-file-manager-complete-guide/), [InMotion: Change File Permissions in cPanel](https://www.inmotionhosting.com/support/edu/cpanel/change-file-permissions/))
- **Plesk**: File Manager has both "Change Permissions" (full CHMOD editor: owner/group/other × read/write/execute) and archive handling — select an uploaded `.zip` and click "Extract Files"; select files/folders and click "Add to Archive" to compress. ([Plesk: Changing File and Directory Access Permissions](https://docs.plesk.com/en-US/obsidian/administrator-guide/website-management/websites-and-domains/website-content/changing-file-and-directory-access-permissions-in-file-manager.70738/), [Plesk: Working with Archive Files](https://docs.plesk.com/en-US/obsidian/extensions-guide/plesk-features-available-for-extensions/manage-files/working-with-archive-files.79667/))
- **HestiaCP** (the reference panel F5.21 itself was benchmarked against): notably does **not** have a permissions/chmod option in its File Manager GUI at all — confirmed by multiple open forum threads of users asking for it. This is a real gap even in the "traditional panel" comparison class, not just a Vexlyx omission — worth building past it rather than matching it. ([Hestia forum: Change File and Folder Permissions through File Manager](https://forum.hestiacp.com/t/change-file-and-folder-permissions-through-file-manager/15789))
- **CyberPanel**: recommends using its File Manager specifically to upload *and extract* archives, to avoid the file-ownership/permission mismatches that SFTP/SSH-based uploads can cause on a multi-tenant box — i.e. treats archive extraction as the safer default path, not an edge case. ([CyberPanel community: fixing permission/user-group problems](https://community.cyberpanel.net/t/tutorial-how-to-fix-permission-and-user-group-problem-on-cyberpanel/14138))
- **CapRover / Coolify / Dokploy**: none of the three PaaS competitors ship a general-purpose file manager with chmod or archive support — deploys are git-push or image-based, not file-drop, so there's no real comparison point here. This reinforces that the right reference class for this feature is the traditional hosting panels above (cPanel/Plesk/HestiaCP/CyberPanel), same framing F5.21 itself used.

**Proposed plan (for whoever picks this up):**
1. **Permissions**: add `POST /api/files/:id/chmod` (`FileService.chmod(userId, projectId, path, mode, recursive?)`) using Node's built-in `fs.promises.chmod` — no new dependency needed. UI: a "Permissions" dialog off the file/folder context menu (owner/group/other × read/write/execute checkboxes, matching cPanel/Plesk's model) plus a raw octal input (`755`, `644`, etc.) for power users. Non-recursive by default; an explicit "Apply to contents" checkbox for folders, mirroring how cPanel/Plesk gate recursive chmod behind an extra confirmation since it's the more dangerous option.
2. **Extract**: add `POST /api/files/:id/extract` (`.zip` at minimum; `.tar`/`.tar.gz` as a stretch goal) that unpacks an uploaded archive into the current directory (or a chosen destination) server-side.
3. **Compress**: add `POST /api/files/:id/compress` to zip a selection of files/folders — useful for the export/backup half of the same workflow.
4. **Open question needing user sign-off before implementation** (per CLAUDE.md §6, "no new dependencies without confirming"): extract/compress needs real zip handling, which Node's stdlib doesn't provide beyond gzip. Two reasonable paths — shell out to the host's `zip`/`unzip` CLI binaries (no new npm dependency, consistent with how `docker_manager.py`/`build_manager.py` already shell out to `docker`/`nixpacks`/`git`, but adds `zip`/`unzip` to the installer's prerequisite checks) vs. an npm package (`adm-zip`/`yazl`+`yauzl`/`archiver` — a genuinely new dependency). Lean toward shelling out, for consistency with the existing system-layer pattern, but this is exactly the kind of call CLAUDE.md says to confirm first rather than assume.
5. Path-traversal safety matters more here than for existing routes: `extract` must resolve every entry inside the archive through the same `safePath` guard (`apps/api/src/modules/files/schema.ts`) already used elsewhere, rejecting any entry whose path would escape the project root (a malicious/zip-slip archive) — worth a dedicated test case, not just a general note.

**Acceptance Criteria:**
- [x] File/folder permissions are viewable and editable from the File Manager UI (octal + checkbox editor), non-recursive by default
- [x] An uploaded `.zip` can be extracted into the current directory from the File Manager, with no shell/SSH access needed (also `.tar`, `.tar.gz`, `.tar.bz2`)
- [x] A selection of files/folders can be compressed into a `.zip` from the File Manager
- [x] Archive extraction is hardened against zip-slip / path traversal (whole archive rejected if any entry would land outside the project root; links, size and ratio limits enforced)
- [x] No new dependency (npm package or system binary) is added without explicit user confirmation, per CLAUDE.md §6 — archives use the Python standard library

**Test Plan:**
1. Upload a `.zip` containing a small site → Extract → files appear in the correct directory with correct contents
2. Upload a deliberately malicious "zip-slip" archive (entries with `../../` paths) → extraction is rejected, nothing is written outside the project root
3. Select several files/folders → Compress → resulting `.zip` downloads and contains exactly the selected content
4. Set a file to `644` and a folder to `755` via the permissions dialog → confirm via `stat`/`ls -la` on the host that the mode actually changed
5. Attempt a recursive chmod on a folder → requires the explicit "apply to contents" confirmation, doesn't silently recurse

**Developer Docs:**
- **Location:** `docs/dev/file-manager-permissions-archives.md`

---

### F5.25 — Per-Domain DNS Mode: Connect-Only vs. Hosted on Vexlyx
**Status:** 🟢 COMPLETED

**Description:**
F5.22 only relabeled the DNS-hosting UI; nothing was gated. A user who just connects a domain to a project (DNS stays at their registrar, A/TXT records already route it) still saw DNS records, nameserver badges and the DNS manager, and every domain got a TXT `DnsRecord` row and CoreDNS zone file it never used. Each domain now has a persisted `dnsMode` (`CONNECTED` default, or `MANAGED`). DNS hosting is a deliberate opt-in: point nameservers at Vexlyx, pass a delegation check, then enable.

**Acceptance Criteria:**
- [x] `Domain.dnsMode` (`CONNECTED` | `MANAGED`), default `CONNECTED`; migration backfills `MANAGED` for domains with any record beyond the verification TXT
- [x] Connect-only domains create no `DnsRecord` rows and no CoreDNS zone file
- [x] All `/api/domains/:id/dns*` endpoints return 409 `DNS_NOT_MANAGED` unless the domain is `MANAGED`
- [x] `POST /:id/dns-mode/check` (NS delegation check) and `PATCH /:id/dns-mode`; enabling requires a verified domain and delegated nameservers; disabling is blocked while mailboxes exist
- [x] `/domains` and the SSL page show DNS-hosting UI only for `MANAGED` domains; `/domains/[id]/dns` shows an opt-in flow for connected domains and a "Stop hosting DNS" action for managed ones
- [x] Instructions modal shared between `/domains` and the project domain tab (TXT + A record), so they can't drift
- [x] Nameservers configurable via `DNS_NAMESERVERS` instead of hard-coded

**Test Plan:**
1. Add a domain → no DNS button, no zone file, `GET /api/domains/:id/dns` returns 409
2. Visit `/domains/[id]/dns` → opt-in view (nameservers, check, enable)
3. Delegate NS + enable → records/zone file appear, DNS button shows
4. Stop hosting → zone file removed, UI hides DNS features, records kept for re-enable

**Developer Docs:**
- **Location:** `docs/dev/dns-management.md` (§9)

---

### F5.26 — Mail Auth Records for Connect-Only Domains
**Status:** 🟢 COMPLETED

**Description:**
Follow-up to F5.25. Mail (F4.5) still wrote MX/SPF/DMARC/DKIM `DnsRecord` rows for connect-only (`CONNECTED`) domains and scored deliverability from them, so a domain whose DNS lives at the user's registrar could show "Excellent, 100/100" while none of the records existed publicly. Connected domains now show the records to add at their registrar and are scored from live public DNS. Managed domains are unchanged.

**Acceptance Criteria:**
- [x] No `DnsRecord` rows or zone file are written by mail setup or DKIM generation/rotation for `CONNECTED` domains
- [x] `requiredRecords` (MX/SPF/DMARC/DKIM) returned for connected domains from a single shared builder also used to seed managed zones
- [x] Deliverability score for connected domains comes from live lookups against public resolvers; DKIM must match the generated public key
- [x] `POST /api/mail/auth/:domainId/check` and a "Check records" button
- [x] Rotate-key dialog warns that the new record must be added at the registrar

**Test Plan:**
1. Connected domain with a mailbox → registrar table shows all records "Not found", score low
2. Add the records at a real/mock DNS → "Check records" flips them to "Live", score rises
3. Managed domain (e.g. `mindgera.site`) behaves exactly as before

**Developer Docs:**
- **Location:** `docs/dev/email/authentication.md` ("Connect-only domains")

---

### F5.27 — Public Authoritative DNS & Zero-Downtime Nameserver Migration
**Status:** 🟢 COMPLETED

**Description:**
Hosted DNS (F5.25) could not actually serve the internet: CoreDNS was bound to loopback and its Corefile forwards unmatched queries, so exposing it would create an open resolver. Managed zones also seeded their default A record from an unset `SERVER_IP`, giving `127.0.0.1`. And a live domain had a gap between switching nameservers and the zone existing, because hosting could only be enabled after delegation.

**Acceptance Criteria:**
- [x] `docker/coredns/Corefile.public`: authoritative-only (no `forward`), selectable via `VEXLYX_COREFILE`; bind address selectable via `VEXLYX_DNS_BIND` (default stays loopback)
- [x] Nameservers configurable via `DNS_NAMESERVERS`, passed through `docker-compose.prod.yml`
- [x] Default records use `PUBLIC_IP` (falling back to `SERVER_IP`) instead of `127.0.0.1`
- [x] "Prepare zone before switching" (`skipDelegationCheck`): load and test the zone before changing nameservers; still requires a verified domain
- [x] Managed domains not yet delegated show a "Not live yet" banner with the nameservers to set
- [x] Zone generator fixed for real-world zones: CNAME/MX/NS/SRV targets written as absolute names, long TXT (DKIM) split into <=255-byte strings without doubled quotes, zone's own apex NS records used instead of hard-coded defaults; all hosted zones are rebuilt on API start

**Test Plan:**
1. Enable hosting with `VEXLYX_DNS_BIND`/`VEXLYX_COREFILE` set; `dig @<server-ip> example.com` answers, `dig @<server-ip> google.com` is refused
2. Prepare the zone on a live domain, verify records with `dig @<server-ip>`, then switch nameservers at the registrar

**Developer Docs:**
- **Location:** `docs/dev/dns-management.md` (§9, "Public authoritative DNS")

---

### F5.28 — Scheduled Tasks (Cron Jobs)
**Status:** 🟢 COMPLETED

**Description:**
Users cannot schedule recurring work for their projects. A Laravel app needs `php artisan schedule:run` every minute, a WordPress site needs `wp-cron.php` triggered on a real schedule instead of on page views, and a Node or Python app often needs a nightly cleanup or report script. Today the only options are an external cron service or shell access to the host, and the panel deliberately gives users neither. The platform already schedules its own work with BullMQ (backups F5.3, Docker cleanup F5.15, both timezone-aware per F5.13), runs each project in its own container, and can email users (F5.23), so this feature adds a user-facing version of the same machinery: a command run **inside a project's container** on a cron schedule, with run history, a "Run now" button and failure emails.

**Competitor research (2026):**
- **cPanel**: a Cron Jobs page with common-interval presets and a free-form 5-field editor. Output of each run is emailed to the account by default, which is also its biggest annoyance (users silence it with `>/dev/null 2>&1`); the contact address is configurable. ([cPanel cron email behaviour](https://www.inmotionhosting.com/support/email/cron-job-email.md))
- **Plesk**: "Scheduled Tasks" with three task types (run a command, fetch a URL, run a PHP script) and a notification choice per task: do not notify, errors only, every time. ([Plesk: scheduling tasks](https://www.plesk.com/kb/docs/scheduling-tasks-4/))
- **HestiaCP**: a basic Cron section (add a command and a schedule, with simple presets); no run history, no output capture, no failure notification. ([Hestia cron guide](https://fornex.com/help/cron-hestia-cp/))
- **Coolify**: Scheduled Tasks on an application or service, each with a name, command, 5-field cron or named frequency, timeout and target container; runs the command in a shell inside the running container. ([Coolify docs](https://coolify.io/docs/core/automation/scheduled-tasks/overview))
- **Dokploy**: Schedule Jobs with four scopes (application, compose, server, Dokploy itself); application and compose jobs use `docker exec`, and every run writes a log entry with its output and status. ([Dokploy docs](https://docs.dokploy.com/docs/core/schedule-jobs))
- **Takeaway**: the traditional panels offer presets and email but little observability; the PaaS tools run commands inside containers with a timeout and per-run logs. Vexlyx can combine both: Plesk-style presets and "errors only" notification on top of Coolify/Dokploy-style container execution and run history. Where it can differ: runs never touch the host, failures email **once per streak** instead of on every run, and the schedule respects the server timezone setting.

**Proposed plan (for whoever picks this up):**
1. **Data model** (one Prisma migration): `ScheduledTask` (`id`, `projectId`, `userId`, `name`, `command`, `schedule` (5-field cron), `timeoutSeconds` default 300, `enabled` default true, `notifyOnFailure` default true, `consecutiveFailures`, `lastRunAt`, timestamps; cascades with the project) and `ScheduledTaskRun` (`taskId`, `trigger` SCHEDULED or MANUAL, `status` RUNNING/SUCCESS/FAILED/TIMEOUT/SKIPPED, `exitCode`, `output` capped at 64 KB, `startedAt`, `finishedAt`; only the latest 50 runs per task are kept).
2. **Module** `apps/api/src/modules/scheduled-tasks/` (`routes.ts`, `service.ts`, `schema.ts`, `scheduler.ts`) following the existing layering; Zod schemas shared via `packages/shared/src/schemas/scheduledTasks.ts`. Endpoints: list/create/update/delete under `/api/projects/:id/scheduled-tasks`, `POST .../:taskId/run` (run now), `GET .../:taskId/runs`.
3. **Scheduling** mirrors `backups/scheduler.ts` and `cleanup/scheduler.ts`: one BullMQ `upsertJobScheduler` per task (`scheduled-task:<id>`) with `tz` from the F5.13 system timezone. All schedulers are re-armed on API boot, removed on disable or delete, and re-upserted when the timezone changes. Missed runs while the API was down are not back-filled (documented).
4. **Execution goes through the Python system layer**, never from a route: add an `exec` action to `system/python/docker_manager.py` that runs `docker exec <container> sh -c <command>` with the command passed as an argument list (never interpolated into a host shell), a hard timeout, and an output cap. The container name is resolved at run time from the project (the `vexlyx-<service_name>-app-1` convention already used there), so a redeploy that replaces the container does not break the task.
5. **Guards**: a Redis lock per task so a run never overlaps its predecessor (the new run is recorded as SKIPPED); a run is SKIPPED when the project is not running; minimum interval of one minute (6-field seconds expressions are rejected); command length capped at 2,000 characters; timeout 1 to 3,600 seconds.
6. **Authorization and limits**: owners manage tasks of their own projects, resellers those of their sub-accounts, admins all (the same ownership scoping as projects). New nullable quota `maxScheduledTasks` on `User` through the F5.20 quota machinery (`assertUnderQuota`, `notifyQuotaThreshold`). Every create/update/delete/run-now is written to the audit log (F5.18).
7. **Failure emails (F5.23)**: new `scheduled_task_failed` event, sent after 3 consecutive failures and not again until the task succeeds once. A per-task toggle turns it off.
8. **UI**: a "Scheduled Tasks" panel on the project detail page next to the other panels (`apps/dashboard/src/components/projects/`): list with enable switch, last status and next run; create/edit dialog with presets (every minute, hourly, daily, weekly) plus a custom cron field that previews the next runs and labels the timezone; "Run now"; a run-history drawer showing output in the always-dark terminal style from the design system. Skeleton loading, empty state with a CTA, confirmation before delete, refresh button with the `isRefreshing` animation.
9. **Presets for common stacks**: Laravel (`php artisan schedule:run`, every minute) and WordPress (`php wp-cron.php`, every 5 minutes; a note recommends setting `DISABLE_WP_CRON`). Confirm in the actual runtime images which binaries exist (for example `wp`) before shipping a preset that needs them.
10. **Out of scope for the first version**: fetch-URL tasks (webhook style), host-level "server tasks" for admins, second-level schedules, job chaining or dependencies, per-run environment overrides, and importing an existing crontab. Track as follow-ups.

**Risks to handle in the implementation:**
- Users run arbitrary commands: contained to their own container and its resource limits; never `docker exec` on a container the user does not own (ownership check on every run, including scheduled ones).
- Output can contain secrets: shown only to the project's owner (and admins), size-capped, never written to the application log at info level.
- Many tasks firing in the same minute: BullMQ worker concurrency cap, and the one-minute minimum interval.
- Daylight-saving transitions: rely on the cron library's `tz` handling and document that a 02:30 job may skip or repeat once a year.

**Acceptance Criteria:**
- [x] A user can create, edit, enable/disable and delete scheduled tasks for their own project, with a 5-field cron expression and a command that runs inside the project's container
- [x] Tasks run on schedule in the configured server timezone (F5.13) and survive an API restart and a project redeploy
- [x] "Run now" executes a task immediately and the result appears in its run history
- [x] Each run records status, exit code, duration and capped output; only the latest 50 runs per task are kept
- [x] Runs are bounded by a timeout, never overlap for the same task, and are SKIPPED (not failed) when the project is not running
- [x] Commands execute through the Python system layer with an argument list, never through a host shell, and only in the owning project's container
- [x] Authorization: users see and manage only their own tasks, resellers their sub-accounts', admins all; unauthenticated calls return 401 and other users' tasks return 403/404
- [x] `maxScheduledTasks` quota enforced and shown like the other quotas, with F5.23 warnings at 80% and 100%
- [x] Failure email after 3 consecutive failures, sent once per failure streak, with a per-task opt-out
- [x] Create, update, delete and run-now are written to the audit log
- [x] Cron expressions faster than once a minute, invalid expressions and over-long commands are rejected with clear errors

**Test Plan:**
1. Create a task `echo hello` every minute on a running project → after a minute a run appears with status SUCCESS and output `hello`
2. Create a task that sleeps longer than its timeout → run recorded as TIMEOUT and the process is gone from the container
3. Create a task that exits non-zero three times in a row → exactly one failure email; succeed once, then fail three times again → a second email
4. Stop the project → the next run is SKIPPED; start it again → runs resume without editing the task
5. Redeploy the project (new container) → the task still runs in the new container
6. Restart the API → schedules are restored; change the server timezone → next-run times shift accordingly
7. As another user, call the endpoints for the first user's project → 403/404; signed out → 401
8. Submit `* * * * * *` (seconds) and a 5,000-character command → both rejected
9. Hit the `maxScheduledTasks` quota → creation refused with `QUOTA_EXCEEDED`

**Developer Docs:**
- **Location:** `docs/dev/scheduled-tasks.md`
- **Contents:** data model, how scheduling and execution work (BullMQ to Python `exec`), guards and limits, how the timezone is applied, how to add a preset, how to test

**Files to Create:**
- `apps/api/src/modules/scheduled-tasks/{routes,service,schema,scheduler}.ts`
- `packages/shared/src/schemas/scheduledTasks.ts`
- `apps/api/prisma/migrations/<timestamp>_add_scheduled_tasks/migration.sql`
- `apps/dashboard/src/components/projects/ScheduledTasksPanel.tsx` and `src/hooks/useScheduledTasks.ts`

---

### F5.29 — GitHub Integration (Connect Your GitHub Account, Pick a Repo, Auto-Deploy)
**Status:** 🟢 COMPLETED

**Description:**
Connecting a repository today is manual and per project (F1.3, F2.7): the user pastes a Git URL, copies a generated SSH deploy key into the repository's settings on GitHub, then copies the webhook URL and secret into GitHub as well, and repeats all of it for every project. There is no way to sign in to GitHub from Vexlyx, so users cannot browse their repositories, private repositories need a deploy key each, and a mistyped URL is only discovered when the clone fails. This feature adds a first-class GitHub connection: the operator creates a GitHub App for the install once (one click), each user installs it on their GitHub account or organization, and from then on projects are created by **picking a repository and branch from a list**. Cloning uses short-lived tokens, and push-to-deploy webhooks are delivered by the App with nothing to copy by hand. The existing manual Git URL flow stays as the fallback for GitLab, Bitbucket, Gitea and self-hosted Git servers.

**Competitor research (2026):**
- **Coolify**: a "GitHub App" source that gives access to one repository, selected repositories or all repositories of an account or organization, with automatic deployments and pull-request events through one integration. It is created through GitHub's app **manifest flow** (permissions, webhook, credentials and callback are filled in automatically), with a manual path only for GitHub Enterprise or custom permissions; on a self-hosted instance the App can be made available system-wide to every team. Deploy keys remain available as the alternative. ([Coolify: Set up a GitHub App](https://coolify.io/docs/applications/sources/github/app), [Coolify: CI/CD with Git providers](https://coolify.io/docs/applications/ci-cd))
- **Dokploy**: supports GitHub, GitLab, Bitbucket and Gitea as providers (its exact GitHub setup should be re-checked in its own docs before implementation). ([comparison](https://use-apify.com/blog/coolify-vs-dokploy-2026))
- **GitHub's own guidance**: GitHub Apps are generally preferred over OAuth apps. Installation tokens carry only the permissions the app declared and only the repositories the installer selected, they expire after a short time (currently 1 hour) while OAuth tokens stay valid until revoked, and an App keeps working if the person who installed it leaves the organization. ([GitHub Apps vs OAuth apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps))
- **Traditional panels (cPanel, Plesk, HestiaCP)**: Git support is "clone a URL (with a deploy key)", the same model Vexlyx has today; none of them offers a GitHub account connection or repository picker.
- **Takeaway**: the self-hosted PaaS tools that users compare Vexlyx with already offer "connect GitHub, pick a repo". A GitHub App with a manifest-based setup is the established, least-privilege way to do it. Vexlyx can differ by keeping the manual flow fully working beside it, and by storing no long-lived GitHub token anywhere.

**Implementation:**
1. **GitHub App per install, created from a manifest.** An ADMIN opens Settings → GitHub and clicks "Create GitHub App". The API serves the manifest (name `Vexlyx (<panel domain>)`, homepage, OAuth callback and webhook URLs built from `API_BASE_URL`, never from request headers) and GitHub redirects back with a code that the API exchanges for the App's id, slug, private key, client secret and webhook secret. A "Use an existing GitHub App" manual form is the fallback for custom setups.
2. **Minimal permissions**: Repository contents (read), Metadata (read); optionally Commit statuses or Deployments (write) as a later step for reporting deploy results on commits. Subscribed events: `push`, `installation`, `installation_repositories`.
3. **Data model** (one Prisma migration): `GitHubApp` singleton (`appId`, `slug`, `clientId`, and `privateKey`, `clientSecret`, `webhookSecret` encrypted with the existing AES-256-GCM helper in `utils/encryption.ts`); `GitHubInstallation` (`installationId`, account identity, repository selection, owner and lifecycle state); and on `Project` the optional GitHub installation, repository identity, connection state and disconnect reason. A project with these set is connected through GitHub; without them it behaves exactly as today.
4. **Linking an installation**: a user clicks "Connect GitHub", is sent to the App's installation page with a random, single-use `state` (stored in Redis, bound to their session, short TTL) and returns to the OAuth callback. The API proves the installation belongs to that user by checking it against `GET /user/installations` with the temporary user-to-server token, because the `installation_id` in the redirect can be forged. Users only ever see and use installations they linked themselves.
5. **Tokens**: the API signs a short-lived RS256 JWT with the App's private key using Node's built-in `crypto` (no new dependency), exchanges it for an installation token (about one hour), and caches it only in process memory until shortly before expiry. No GitHub token is stored in Redis, the database or on disk.
6. **Cloning without leaking the token**: the token is passed to `system/python/git_manager.py` on stdin like the rest of its payload and used for the clone and pull through a one-shot credential header or `GIT_ASKPASS`, so the remote URL stored in `.git/config` stays token-free. Builds (F1.4) and redeploys call the same path to fetch a fresh token each time.
7. **Webhooks**: one App-level endpoint `POST /api/webhooks/github-app` verifies `x-hub-signature-256` with the App's webhook secret using the existing timing-safe verifier, de-duplicates on `x-github-delivery`, then looks up projects by numeric installation and repository IDs and queues matching-branch deployments. The per-project webhook route from F2.7 stays for manual projects. `installation` and `installation_repositories` events keep access and suspension state in sync; an uninstall disconnects affected projects without stopping their running containers.
8. **Repository picker API**: `GET /api/github/installations`, paginated/searchable `GET /api/github/installations/:id/repositories`, and `GET .../repositories/:repoId/branches`; `POST /api/projects/:id/git/connect-github` revalidates access, records the repository and runs the first clone. All routes are scoped to the caller's own installations.
9. **UI**: a Settings → GitHub card (admin: create/replace the App and see its status; every user: connect, list and disconnect their installations); an "Import from GitHub" tab in the project creation flow with a searchable repository list and a branch select; in `GitSettings.tsx` a connected project shows `owner/repo`, the branch and "Connected via GitHub", hides the SSH key and webhook sections, and offers "Switch to manual URL". Empty and error states explain what to do when the install has no public HTTPS panel URL (GitHub cannot reach `localhost`), with a pointer to a tunnel for local development.
10. **Audit log** (F5.18) entries for creating or replacing the App, linking or unlinking an installation, and connecting a project to a repository. Secrets and tokens are never part of audit metadata or logs.
11. **Out of scope for the first version**: GitLab, Bitbucket and Gitea account connections (the provider interface should be shaped so they can follow), pull-request preview deployments, GitHub Enterprise Server base-URL support beyond the manual App form, writing commit statuses or deployments back to GitHub, and bulk-creating a project per repository. Track as follow-ups.

**Risks to handle in the implementation:**
- Stolen or forged `installation_id` in the setup redirect: verify ownership as described in step 4; reject and audit mismatches.
- App private key and webhook secret are high-value: encrypt at rest, never return them from any API response, and keep them out of logs and error messages.
- Webhook replay or forgery: signature check on the raw body, delivery-id de-duplication, and the existing branch filter.
- A user must not deploy a repository they cannot access: repository selection is always resolved through the user's own installation, and the repository id is re-checked at clone time.
- GitHub API rate limits and large accounts: paginate, search server-side, and cache repository lists for a short time.
- Operators without a public HTTPS URL cannot receive webhooks: detect this up front and say so instead of failing silently.

**Acceptance Criteria:**
- [x] An admin can create the GitHub App for the install from Settings with one click (manifest flow), or enter an existing App's credentials; its private key, client secret and webhook secret are stored encrypted and never returned by the API
- [x] A user can connect their own GitHub account or organization to the panel and disconnect it again; other users cannot see or use that installation
- [x] Creating or editing a project offers a searchable list of the repositories the installation can access, with a branch selector, and connecting performs the first clone with no SSH key or URL typing
- [x] Private repositories work without a per-repository deploy key
- [x] Cloning, pulling and building use short-lived installation tokens fetched on demand; no GitHub token is persisted in the database or on disk, and the stored remote URL contains no credentials
- [x] Pushing to the connected branch triggers a deployment through the App webhook with no manual webhook setup; pushes to other branches are ignored, and a repeated delivery id is processed once
- [x] Webhook requests with a missing or invalid signature are rejected with 401
- [x] Uninstalling the App, removing a repository from it, or suspending it disconnects the affected projects cleanly without stopping their running containers, and the dashboard says why
- [x] Projects connected the manual way (Git URL, SSH key, per-project webhook) keep working unchanged
- [x] Forged or mismatched installation ids in the setup redirect are rejected
- [x] Linking, unlinking, App creation and repository connection are written to the audit log
- [x] Unauthenticated calls return 401 and calls for another user's installation or repository return 403/404

**Test Plan:**
1. As admin, click "Create GitHub App" on a server with a public HTTPS panel URL → GitHub shows the pre-filled manifest, and after confirming, Settings shows the App as connected
2. As a user, connect a GitHub account → the account appears; as a second user, it does not
3. Create a project via "Import from GitHub", choose a private repository and a branch → it clones and builds with no deploy key
4. Push a commit to that branch → a deployment starts within seconds; push to another branch → no deployment
5. Replay the same webhook delivery → processed once; send it with a wrong signature → 401
6. Inspect the cloned project's `.git/config` and the database → no token anywhere
7. Remove the repository from the installation on GitHub → the project shows "disconnected", its container keeps running, and switching to the manual URL flow works
8. Tamper with `installation_id` in the setup redirect → linking is rejected
9. Run the same flow on a server without a public HTTPS URL → the card explains why GitHub cannot be connected instead of failing
10. Existing manual-flow project → still deploys on its own webhook exactly as before

**Developer Docs:**
- **Location:** `docs/dev/github-integration.md`
- **Contents:** App creation and permissions, the linking and verification flow, token lifecycle, webhook handling, how repository selection is authorized, how to add another Git provider, how to test locally with a tunnel

**Files to Create:**
- `apps/api/src/modules/github/{client,routes,service,schema,tokens}.ts`
- `apps/api/src/modules/webhooks/github-app.ts` (App webhook handler reusing `WebhookService`)
- `packages/shared/src/schemas/github.ts`
- `apps/api/prisma/migrations/<timestamp>_add_github_integration/migration.sql`
- `apps/dashboard/src/components/settings/GitHubCard.tsx`, `src/components/projects/GitHubRepoPicker.tsx`, `src/hooks/useGitHub.ts`
- `apps/api/src/modules/github/tokens.test.ts`
- `tests/test_github_app_git_credentials.py`
- `docs/dev/github-integration.md`

---

### F5.30 — Redis Instances
**Status:** 🔴 NOT STARTED

**Description:**
Users can create PostgreSQL and MySQL databases (F2.6) but have no key-value store: an app that needs a cache, a session store or a job queue (BullMQ, Sidekiq, Celery, Laravel queues) has to bundle its own Redis in its project or go without. This feature lets a user create a **Redis instance** from the dashboard: a dedicated, password-protected Redis container with a memory limit that their projects reach over the internal Docker network, with a ready-to-paste connection URL. It is a standalone feature with its own module, table, manager script, quota and UI, and does not depend on any other database feature.

**Why a container per instance (not a shared server):** Redis has no real multi-tenancy. Logical databases (0-15) share one memory pool, one CPU thread and one set of dangerous commands (`FLUSHALL`, `CONFIG`, `KEYS`, `DEBUG`), and one tenant can evict or wipe another's keys. PostgreSQL and MySQL are shared because a per-database user is a real isolation boundary there; for Redis the boundary is the container. The panel's own `vexlyx-redis` (sessions, BullMQ queues, rate limits, `allkeys-lru` eviction) must **never** be used for tenant data.

**Competitor research (2026):**
- **Coolify**: one-click Redis (and the Redis-compatible Dragonfly and KeyDB) as a standalone container with its own volume; default port 6379. Database-aware scheduled backups exist for PostgreSQL, MySQL, MariaDB, MongoDB and ClickHouse but, per its docs, not for the Redis family, which only get persistent storage. It also states a one-click database is not a managed cluster (no replication or failover). ([Coolify: choose a database](https://coolify.io/docs/databases/choose-a-database), [Coolify: backups](https://coolify.io/docs/knowledge-base/databases/backups))
- **Dokploy**: Redis is created like any other database service with a name, password and image, a Docker volume at `/data`, optional memory and CPU limits and reservations, and an optional external port; its docs advise setting `maxmemory` and an eviction policy so Redis cannot consume the host's memory, and keeping databases on internal networks where possible. ([Dokploy databases](https://docs.dokploy.com/docs/core/databases), [Redis page (mirror)](https://www.mintlify.com/Dokploy/dokploy/databases/redis))
- **cPanel / Plesk / HestiaCP**: no managed Redis for users out of the box (MySQL/MariaDB and PostgreSQL only); caching on those panels usually means a host-level Redis the user cannot manage themselves.
- **Takeaway**: the PaaS tools treat Redis as "one container per instance with limits and an internal address", which is also the only safe model here. Where Vexlyx can differ: a hard per-instance memory cap by default, no public port unless explicitly opted in later, and quota and usage shown next to the user's other databases.
- **Licensing note**: Redis moved to RSALv2/SSPL from 7.4 and added AGPLv3 with 8.0; Valkey is the BSD-licensed fork of Redis 7.2.4. The implementation must choose and document one pinned image line (for example a BSD-licensed Redis 7.2.x or Valkey) rather than pull `latest`. ([Redis licensing summary](https://www.infoq.com/news/2025/05/redis-agpl-license))

**Proposed plan (for whoever picks this up):**
1. **Data model** (own migration, own table; does **not** extend `DatabaseType` or the `Database` model): `RedisInstance` (`id`, `userId`, `projectId?`, `name` unique per user, `containerName`, `imageTag`, `memoryLimitMb`, `evictionPolicy`, `persistence` NONE/RDB/AOF, `passwordEncrypted` (AES-256-GCM via `utils/encryption.ts`), `status` CREATING/RUNNING/STOPPED/ERROR/DELETED, timestamps).
2. **Module** `apps/api/src/modules/redis/` (`routes.ts`, `service.ts`, `schema.ts`), schemas shared via `packages/shared/src/schemas/redis.ts`. Endpoints under `/api/redis`: create, list, get, start/stop/restart, update limits, rotate password, delete, and `GET /:id/stats`.
3. **System layer**: a new `system/python/redis_manager.py`, following `database_manager.py` (JSON on stdin, JSON on stdout, strict identifier validation, argument lists only, a hard timeout). It starts `redis-server` with `--requirepass`, `--maxmemory`, `--maxmemory-policy`, `--appendonly`/`--save` from the settings, a Docker memory limit slightly above `maxmemory`, a named volume at `/data`, a restart policy, and a healthcheck. The password is passed through an environment file or config mount, never on a command line visible in `ps`.
4. **Network**: instances join the same internal Docker network project containers use (the F2.6 "accessible only from project containers" model) and publish **no** host port. The connection URL uses the container hostname: `redis://:<password>@<container>:6379`. Public exposure is explicitly out of scope for the first version.
5. **Safe defaults**: default `memoryLimitMb` 64, admin-configurable maximum (`REDIS_MAX_MEMORY_MB`), `evictionPolicy` default `noeviction` for queues with an `allkeys-lru` preset for caches, persistence default RDB, `protected-mode` on, dangerous administrative commands disabled for the instance.
6. **Linking to a project**: optionally set `REDIS_URL` in the project's environment variables (F1.7) from the instance, so the next deploy picks it up; unlinking removes it.
7. **Usage and limits**: new nullable quota `maxRedisInstances` on `User` through the F5.20 quota machinery (`assertUnderQuota`, F5.23 warnings via `notifyQuotaThreshold`); list and detail show memory used vs limit, key count and uptime from `INFO`, refreshed on demand.
8. **UI**: a "Redis" page next to Databases: list with status, memory and a "Create instance" dialog (name, version, memory, preset: cache/queue/persistent), detail page with connection URL (password revealed on demand, copy button), start/stop/restart, change limits, rotate password, and delete with typed-name confirmation. Skeletons, empty state with CTA, refresh button animation per the design system.
9. **Lifecycle and safety**: deleting an instance removes the container and volume after confirmation; an instance that exceeds its memory limit is restarted by Docker, not left to starve the host; admins see all instances and can stop any of them. Create, delete, rotate and limit changes are written to the audit log (F5.18); the password never appears in logs, audit metadata or list responses.
10. **Out of scope for the first version**: public host port / TLS, replication, Sentinel or cluster mode, a built-in web browser for keys, and scheduled backups of Redis data (RDB file download from the volume is a possible follow-up).

**Risks to handle in the implementation:**
- Sharing the panel's own Redis with tenants would let a tenant read or evict sessions and queues; the manager must never address `vexlyx-redis`.
- A user with no memory cap can exhaust the host: always set both `maxmemory` and a Docker limit, and cap the admin maximum.
- Passwords on command lines leak through `ps` and Docker inspect; pass them through a file or environment source that is not logged.
- Container-name collisions across users (the F5.21 "bare service name" bug class): always use a unique, Compose-independent container name.
- Orphaned containers and volumes when a delete half-fails (the F5.21 teardown bug class): tear down both and log, without making the instance undeletable.
- The image line has a licence decision attached; do not float on `latest`.

**Acceptance Criteria:**
- [ ] A user can create, list, start, stop, restart and delete Redis instances from the dashboard and API, each running in its own container with a password
- [ ] Each instance has an enforced memory limit (`maxmemory` plus a Docker limit) and a chosen eviction policy and persistence mode
- [ ] The connection URL works from a project container on the internal network and the instance publishes no host port
- [ ] The panel's own Redis is never reachable through this feature
- [ ] The password is encrypted at rest, can be rotated, and is never returned by list endpoints or written to logs or the audit log
- [ ] `maxRedisInstances` quota enforced and shown like the other quotas, with F5.23 warnings at 80% and 100%
- [ ] Users see and manage only their own instances; admins see all; unauthenticated calls return 401 and other users' instances return 403/404
- [ ] Deleting an instance removes its container and volume; a failed teardown is reported but does not leave the instance stuck
- [ ] Create, update, rotate and delete are written to the audit log
- [ ] The image is pinned to a documented version line, and the licence choice is recorded in the docs
- [ ] The feature works with PostgreSQL/MySQL provisioning (F2.6) untouched, and can ship without any other new database feature

**Test Plan:**
1. Create an instance with 64 MB → container running, `redis-cli -a <password> ping` from a project container returns PONG
2. Connect without the password or from the host → refused or unreachable
3. Fill it past 64 MB with the `noeviction` policy → writes fail with an OOM error, the host is unaffected; with `allkeys-lru` → old keys are evicted
4. Rotate the password → the old password stops working, the new one works
5. Stop and start → data survives with RDB persistence, is gone with persistence NONE
6. Delete → container and volume are removed and the name can be reused
7. As another user, call the endpoints for the first user's instance → 403/404; signed out → 401
8. Reach the quota → creation refused with `QUOTA_EXCEEDED`
9. Confirm `vexlyx-redis` (the panel's) is untouched and still serving sessions throughout

**Developer Docs:**
- **Location:** `docs/dev/redis-instances.md`
- **Contents:** isolation model and why a container per instance, data model, lifecycle, limits and eviction presets, networking and the connection URL, licence decision, how to test, how to extend

**Files to Create:**
- `system/python/redis_manager.py`
- `apps/api/src/modules/redis/{routes,service,schema}.ts`
- `packages/shared/src/schemas/redis.ts`
- `apps/api/prisma/migrations/<timestamp>_add_redis_instances/migration.sql`
- `apps/dashboard/src/app/(panel)/redis/page.tsx`, `src/components/redis/*`, `src/hooks/useRedis.ts`

---

### F5.31 — MongoDB Databases
**Status:** 🔴 NOT STARTED

**Description:**
Users can create PostgreSQL and MySQL databases (F2.6) but not a document database. Node.js, Python and PHP apps built on MongoDB (Mongoose, Prisma with MongoDB, PyMongo) have to bundle their own MongoDB container or use an external service. This feature lets a user create a **MongoDB database** from the dashboard: a database and a dedicated database user with a generated password on a MongoDB server managed by the panel, a connection string for their projects, and clean removal. It is a standalone feature with its own module, table, manager script, quota and UI, and does not depend on the Redis feature or any other database feature.

**Isolation model:** one shared `mongod` container with authentication enabled, and one database plus one user per created database, where the user holds the `readWrite` role on that database only. This mirrors how F2.6 isolates PostgreSQL and MySQL tenants, and avoids running one memory-hungry `mongod` per user (WiredTiger's cache defaults to roughly half of available RAM, so each extra process would otherwise compete for the host's memory). The WiredTiger cache is capped and the container gets a Docker memory limit.

**Competitor research (2026):**
- **Coolify**: one-click MongoDB as its own container (default port 27017), and database-aware scheduled backups for MongoDB (together with PostgreSQL, MySQL, MariaDB and ClickHouse) to local storage or an S3-compatible bucket. Its docs state a one-click database is not a managed cluster. ([Coolify: choose a database](https://coolify.io/docs/databases/choose-a-database), [Coolify: backups](https://coolify.io/docs/knowledge-base/databases/backups))
- **Dokploy**: MongoDB created like any other database service, with a Docker volume at `/data/db`, optional memory and CPU limits, an optional external port and an optional single-member replica set (`rs0`) for apps that need transactions; connection strings differ for internal and external access. ([Dokploy databases](https://docs.dokploy.com/docs/core/databases), [MongoDB page (mirror)](https://www.mintlify.com/Dokploy/dokploy/databases/mongodb))
- **cPanel / Plesk / HestiaCP**: MySQL/MariaDB and PostgreSQL only for end users; MongoDB is not part of the standard user-facing database offer.
- **Takeaway**: PaaS panels give MongoDB its own container per resource; traditional panels do not offer it at all. Vexlyx can offer it with per-user databases on one managed server (cheaper on RAM and consistent with F2.6), internal-only by default, with the backup integration (F5.3) as the differentiator.
- **Licensing question that needs a decision before building**: MongoDB Community Server is published under the Server Side Public License (SSPL), which is not OSI-approved and contains a clause aimed at offering the database's functionality to third parties as a service. Running an unmodified `mongod` for your own users on your own server is likely fine, but a panel that exposes "create a MongoDB database" to other people is exactly the situation to have reviewed. The maintainers must record a decision in the docs, and consider wire-compatible alternatives (for example FerretDB, Apache-2.0, backed by PostgreSQL) as a follow-up or a swap-in. Do not assume either way.

**Proposed plan (for whoever picks this up):**
1. **Data model** (own migration, own table; does **not** extend `DatabaseType` or the `Database` model, so Adminer and the SQL tooling are untouched): `MongoDatabase` (`id`, `userId`, `projectId?`, `name`, `dbUser`, `passwordEncrypted` (AES-256-GCM via `utils/encryption.ts`), `status`, timestamps; unique `(userId, name)`; the real database name is namespaced so two users can never collide).
2. **Module** `apps/api/src/modules/mongodb/` (`routes.ts`, `service.ts`, `schema.ts`), schemas shared via `packages/shared/src/schemas/mongodb.ts`. Endpoints under `/api/mongodb`: create, list, get, delete, rotate password, test connection, and `GET /:id/stats` (size, collections, indexes from `dbStats`).
3. **Server container**: a `mongodb` service in `docker-compose.yml` (pinned image line, auth enabled, named volume, healthcheck, WiredTiger cache cap, Docker memory limit, internal network only, no published port), with the root credentials generated once by the installer into the secrets file like the Postgres and MySQL passwords, and the installer step idempotent on re-runs and upgrades.
4. **System layer**: a new `system/python/mongodb_manager.py`, following `database_manager.py` (strict identifier validation, JSON in and out, a hard timeout). It runs `mongosh` through `docker exec` with the script and credentials passed as data, never concatenated into a shell string, to create the database and user (`createUser` with `readWrite` on that database only), drop both on delete, change the password, and report stats. Root credentials stay inside the API/manager and are never returned.
5. **Connection string**: `mongodb://<user>:<password>@mongodb:27017/<db>?authSource=<db>` for the internal network. No host port in the first version.
6. **Linking to a project**: optionally set `MONGODB_URL` in the project's environment variables (F1.7) from the database.
7. **Backups (F5.3)**: include MongoDB databases in snapshots with `mongodump --archive --gzip` for the one database (via `docker exec`, streamed like the existing SQL dumps) and restore with `mongorestore`, so users do not get a database that silently falls outside backups.
8. **Limits**: new nullable quota `maxMongoDatabases` on `User` through the F5.20 quota machinery with F5.23 warnings; an optional per-database size limit is a follow-up.
9. **UI**: a "MongoDB" page next to Databases: list, "Create database" dialog (name, optional project to link), a detail page with the connection string (password revealed on demand, copy button), size and collection count, rotate password, test connection, and delete with typed-name confirmation. Skeletons, empty state with CTA, refresh animation per the design system.
10. **Audit log** (F5.18) entries for create, delete and password rotation; passwords never appear in logs, audit metadata or list responses.
11. **Out of scope for the first version**: public host port or TLS, a web admin UI such as mongo-express (Adminer does not cover MongoDB), replica sets and sharding, per-user server instances, and importing an existing dump from the UI.

**Risks to handle in the implementation:**
- The `mongod` root credentials give access to every tenant: keep them out of API responses, logs, error messages, the process list and the project containers' environment.
- Script injection through names or passwords into `mongosh --eval`: validate identifiers strictly, pass values as data (for example through stdin or `--eval` with JSON-encoded arguments), never string-concatenate.
- Memory pressure from a shared server: cap the WiredTiger cache and the container, and surface usage to admins.
- Data directory growth with no per-database quota: show size per database and plan the follow-up limit.
- A database that survives a half-failed delete (user dropped but data kept, or the reverse): make delete idempotent and re-runnable.
- The licence question above.

**Acceptance Criteria:**
- [ ] A user can create, list, delete, test and rotate the password of MongoDB databases from the dashboard and API; each gets its own database and a user limited to that database
- [ ] The MongoDB server requires authentication and publishes no host port; the connection string works from a project container on the internal network
- [ ] One user's credentials cannot read or list another user's database
- [ ] Root credentials are generated once by the installer, never returned by the API and never present in logs, audit metadata or project environments
- [ ] Database and user names are validated and cannot inject script into the manager
- [ ] The password is encrypted at rest, can be rotated, and is never returned by list endpoints
- [ ] MongoDB databases are included in backup snapshots and can be restored (F5.3)
- [ ] `maxMongoDatabases` quota enforced and shown like the other quotas, with F5.23 warnings at 80% and 100%
- [ ] Users see and manage only their own databases; admins see all; unauthenticated calls return 401 and other users' databases return 403/404
- [ ] Deleting a database drops both the database and its user, and can be retried safely after a partial failure
- [ ] Create, delete and rotate are written to the audit log
- [ ] The licensing decision for MongoDB is recorded in the docs before release
- [ ] PostgreSQL/MySQL provisioning (F2.6) is untouched, and the feature ships without requiring any other new database feature

**Test Plan:**
1. Create a database → server shows the database and a user with only `readWrite` on it
2. From a project container, connect with the connection string and insert and read a document → works
3. Connect with the user to a different database or run `show dbs` for others → denied
4. Connect without credentials, and from the host → refused or unreachable
5. Rotate the password → old password fails, new one works
6. Create a snapshot and restore it after dropping the data → documents are back
7. Create a database named with quotes, `$`, `;` or JS injection → rejected by validation
8. Delete → database and user are gone and the name can be reused; interrupt a delete mid-way and retry → completes
9. As another user, call the endpoints for the first user's database → 403/404; signed out → 401
10. Reach the quota → creation refused with `QUOTA_EXCEEDED`

**Developer Docs:**
- **Location:** `docs/dev/mongodb-databases.md`
- **Contents:** isolation model, data model, installer and compose changes, manager script and how scripts are passed safely, backups, licensing decision, limits, how to test, how to extend

**Files to Create:**
- `system/python/mongodb_manager.py`
- `apps/api/src/modules/mongodb/{routes,service,schema}.ts`
- `packages/shared/src/schemas/mongodb.ts`
- `apps/api/prisma/migrations/<timestamp>_add_mongodb_databases/migration.sql`
- `apps/dashboard/src/app/(panel)/mongodb/page.tsx`, `src/components/mongodb/*`, `src/hooks/useMongoDb.ts`

---

### F5.32 — Anonymous Usage Statistics (Opt-In Telemetry)
**Status:** 🔴 NOT STARTED

**Description:**
Vexlyx is self-hosted, so the maintainers have no way to know how many installs exist, which versions are in use, or whether a release was adopted: the only signals are GitHub stars and clones, docs traffic, and (once releases exist) download and image-pull counts, none of which measures real installs. This feature adds **opt-in, anonymous, transparent** usage statistics: an admin can choose to let their panel send a small, fixed, documented payload once a day, which lets the project count active installs and see the version spread. It is off until an admin turns it on, shows exactly what it would send, and can be switched off at any time or forced off by the operator. It never sends anything that identifies a person, a domain, a server or a project.

**Design principles (non-negotiable):**
1. **Opt-in, never opt-out.** The default is off; nothing is sent until an admin explicitly enables it.
2. **Transparent.** The exact payload is visible in the dashboard before and after enabling, and the schema is published in the docs. The payload is built from an allow-list of fields, so adding a field requires a code change, a schema version bump and a docs update.
3. **Anonymous by construction.** No emails, names, hostnames, domains, IP addresses, project or repository names, secrets, logs or error messages. Counts are bucketed, not exact.
4. **Operator stays in control.** A hard off-switch (`VEXLYX_TELEMETRY=off`), respect for the `DO_NOT_TRACK=1` convention, and a configurable collector URL for operators who want to inspect or redirect the traffic.
5. **Never breaks the panel.** Short timeout, no retries beyond the next scheduled run, no effect on any request, and silent in the logs apart from one debug line.

**What is sent (schema v1):**

| Field | Example | Notes |
| --- | --- | --- |
| `schemaVersion` | `1` | Bumped whenever the field list changes |
| `installId` | random UUID v4 | Generated only when telemetry is first enabled; not derived from hardware, hostname, domain or IP; resettable |
| `vexlyxVersion` | `0.3.1` | From `VEXLYX_VERSION` |
| `nodeMajor`, `os`, `arch` | `22`, `linux`, `x64` | Runtime environment only |
| `environment` | `production` | `production` only; development and test installs never send |
| `counts` | `{ "users": "2-5", "projects": "6-20", "domains": "1", ... }` | Buckets `0`, `1`, `2-5`, `6-20`, `21-100`, `>100` for users, projects, domains, databases and mailboxes |
| `features` | `{ "githubIntegration": true, "systemEmail": "bundled" }` | A few booleans/enums about which optional features are configured, never their settings |

**Proposed plan (for whoever picks this up):**
1. **Data model** (one Prisma migration): a `TelemetrySettings` singleton row (`enabled` default false, `installId` nullable, `decidedAt`, `decidedById`, `promptDismissedAt`, `lastSentAt`, `lastStatus`), following the singleton pattern used by `BackupSettings` and `CleanupSettings`.
2. **Module** `apps/api/src/modules/telemetry/` (`routes.ts`, `service.ts`, `schema.ts`, `scheduler.ts`), with the payload schema shared via `packages/shared/src/schemas/telemetry.ts`. ADMIN-only endpoints: `GET /api/telemetry` (status, whether the operator forced it off, last result and the **exact payload that would be sent**), `PUT /api/telemetry` (`{ enabled }`), `POST /api/telemetry/reset-id`.
3. **Payload builder** is a pure function over counts the service reads from the database, using the bucket table above; unit tests assert the output contains only allow-listed keys and that no value from the database (an email, a hostname, a project name) can appear in it.
4. **Scheduling** mirrors `backups/scheduler.ts`: one BullMQ job scheduler, daily at a minute derived from the install id (so installs do not all ping at once), with the first send shortly after enabling. One `POST` with a 5-second timeout; any failure is recorded in `lastStatus` and not retried until the next run. Never sends when `NODE_ENV` is not `production`, or when disabled.
5. **Operator controls** (validated in `env.ts`, documented in `.env.example` and the docs): `VEXLYX_TELEMETRY` (`off` forces it off and hides the prompt; `on` pre-enables it for operators who consent through configuration management; unset leaves the choice to the admin), `DO_NOT_TRACK=1` forces it off, and `TELEMETRY_URL` points at a different collector.
6. **Installer** asks once during an interactive install, with the default "No": "Share anonymous usage statistics to help the project? (y/N)". Non-interactive installs pass `VEXLYX_TELEMETRY`; the summary states the current setting and how to change it. Re-running the installer never flips an earlier choice.
7. **UI**: a "Usage statistics" card in Settings (admin only) with the on/off switch, a "See exactly what is sent" panel showing the live payload and when it was last sent, "Reset install ID", and a link to the privacy page. A one-time dismissible prompt for admins on first login, with "No thanks" as prominent as "Share", and no repeated nagging after dismissal.
8. **Audit log** (F5.18): `telemetry.enabled`, `telemetry.disabled`, `telemetry.id_reset`.
9. **Collector** (separate small service run by the maintainers, specified here and implemented outside this repo or under `tools/`): `POST /v1/ping` validating the published schema, storing only `installId`, first and last seen, version and the bucketed values, discarding IP addresses and user agents at the edge, rate-limited per install id. It publishes aggregates only: active installs over 7 and 30 days, installs by version, and a trend line. A reference implementation and the deployment notes live in the docs so the numbers can be audited.
10. **Docs and privacy**: `docs/dev/telemetry.md` and a short public privacy page covering the schema, what is never collected, retention (for example, an install not seen for 90 days is dropped), how to opt out, and how to ask for an install id to be deleted.
11. **Out of scope for the first version**: crash or error reporting, feature-click analytics, per-user tracking of any kind, and an "update available" check. The update check is a natural follow-up that can reuse the same endpoint, but it must stay separate from statistics and be just as transparent.

**Risks to handle in the implementation:**
- Scope creep in the payload: the allow-list and schema-version rule exist so that nobody quietly adds fields; reviewers should treat a payload change like a privacy change.
- A stable `installId` is pseudonymous: generate it only after consent, make it resettable, and delete the row on disable if the operator asks.
- Opt-in will undercount: the collector's numbers are a lower bound, and the docs and public page must say so rather than present them as exact.
- Outbound calls from a server that otherwise sends nothing: the `off` switch, the `TELEMETRY_URL` override and the payload preview exist so operators can verify this themselves.
- The collector becomes a piece of infrastructure to run and secure: keep it tiny, stateless where possible, and separate from the panel's own services.

**Acceptance Criteria:**
- [ ] Nothing is sent by a fresh install, an upgraded install or a development environment until an admin explicitly enables statistics
- [ ] An admin can enable and disable statistics from Settings, see the exact payload that would be sent, and reset the install id
- [ ] `VEXLYX_TELEMETRY=off` and `DO_NOT_TRACK=1` force statistics off regardless of the stored choice and hide the prompt; the dashboard says why it is off
- [ ] The payload contains only the allow-listed fields of the published schema, with bucketed counts, and no email, name, hostname, domain, IP address, project or repository name, secret or log text
- [ ] The install id is a random UUID created only after consent and is deleted or regenerated on reset
- [ ] Sends are limited to one a day, time out after 5 seconds, never retry in a loop and never affect request handling or startup
- [ ] The installer asks once with default "No" and never changes an earlier choice on re-run
- [ ] Enabling, disabling and resetting are written to the audit log
- [ ] Only admins can read or change the setting; unauthenticated calls return 401 and non-admins 403
- [ ] The schema, the privacy page and the collector's retention rules are documented before the feature is released
- [ ] A reference collector exists and publishes aggregate numbers only

**Test Plan:**
1. Fresh install, never touching the setting, wait past the schedule → no outbound request to the collector
2. Enable in Settings → the payload preview matches what the collector receives, field for field
3. Add users, projects and domains containing recognisable strings (an email, a hostname) → none of those strings appear in the sent payload, only buckets
4. Set `VEXLYX_TELEMETRY=off` → the switch is disabled with an explanation and nothing is sent; same with `DO_NOT_TRACK=1`
5. Point `TELEMETRY_URL` at an unreachable address → the panel keeps working, `lastStatus` shows the failure and no retry storm occurs
6. Reset the install id → the next ping carries a new id
7. Disable → no further sends, and the stored id is removed
8. As a non-admin and signed out, call the endpoints → 403 and 401
9. Run the installer non-interactively with no variable → statistics stay off; interactively answering "y" → on, and a re-run does not ask again or flip it
10. Run in `NODE_ENV=development` with statistics enabled → nothing is sent

**Developer Docs:**
- **Location:** `docs/dev/telemetry.md`
- **Contents:** principles, schema v1 and how to change it, consent flow, scheduler and failure behaviour, operator controls, collector specification and retention, privacy notice, how to test

**Files to Create:**
- `apps/api/src/modules/telemetry/{routes,service,schema,scheduler,payload}.ts` (and `payload.test.ts`)
- `packages/shared/src/schemas/telemetry.ts`
- `apps/api/prisma/migrations/<timestamp>_add_telemetry_settings/migration.sql`
- `apps/dashboard/src/components/settings/TelemetryCard.tsx`, `src/hooks/useTelemetry.ts`
- `docs/dev/telemetry.md` and a public privacy page

---

### F5.33 — In-Panel Update Notifications
**Status:** 🟢 COMPLETED

**Description:**
An administrator should not have to re-run the installer on a hunch to learn that a fix exists. The API compares `VEXLYX_VERSION` with the newest stable GitHub release, caches the result in Redis, and the dashboard shows admins a dismissible banner with links to the release notes and the upgrade guide. It is display-only — nothing is downloaded or installed automatically — and is deliberately separate from opt-in telemetry (F5.32), which stays off until an admin enables it.

**Acceptance Criteria:**
- [x] `GET /api/system/update` returns the current and latest versions, update availability, release URL, publish time, and whether the check ran or failed (ADMIN only; 401/403 otherwise)
- [x] A successful check is cached for 6 hours, a failed one for 1 hour, and a GitHub outage never fails the request
- [x] `UPDATE_CHECK_ENABLED=false` performs no outbound call; `UPDATE_CHECK_REPO` changes the source repository for forks
- [x] Prerelease and draft releases are never offered; comparison handles the `v` prefix, build metadata and prerelease ordering
- [x] The dashboard shows the banner to admins only, remembers dismissal per version, and links to the release notes and upgrade guide

**Test Plan:**
1. Publish a newer tag → an admin sees the banner within the cache window; a non-admin never does
2. Dismiss the banner → it stays hidden for that version and reappears for the next release
3. Block outbound access to `api.github.com` → the panel keeps working, the notice stays hidden, one warning is logged
4. Set `UPDATE_CHECK_ENABLED=false` → no request to GitHub; the endpoint reports `checkEnabled: false`

**Developer Docs:**
- **Location:** `docs/dev/system-updates.md`
- **Contents:** flow, caching/failure behaviour, version comparison rules, operator controls, how to test

**Files:**
- `apps/api/src/modules/system/update-service.ts` (and `update-service.test.ts`), `routes.ts`
- `apps/api/src/utils/version.ts` (and `version.test.ts`)
- `packages/shared/src/schemas/systemUpdate.ts`
- `apps/dashboard/src/hooks/useSystemUpdate.ts`, `src/components/layout/UpdateBanner.tsx`

---

### F5.34 — Per-Project Build Settings in the Dashboard
**Status:** 🟡 IN PROGRESS

**Description:**
A deploy that Nixpacks misreads has no way out from the panel. The columns and the `PUT /api/projects/:id` fields for `buildCmd`, `startCmd` and `port` already existed, but nothing in the dashboard exposed them, so a user whose repository needs `pnpm install --frozen-lockfile`, a monorepo `filter`, or a port other than the detected one had to delete the project or shell out to the API. Worse, `build_manager.py` accepted an install command and passed `--install-cmd` to Nixpacks, but the API never put `installCmd` in the payload, so the flag was dead code end to end.

This feature gives a project a **Build Settings** card on the Deploy tab with the same shape Vercel and Dokploy use: one field per command, blank means auto-detection, a **Detect** button that runs `nixpacks plan` over the current source and shows what would be used, and an explicit reset back to auto. Detection stays in `build_manager.py` — the API only shuttles its answer, so the panel can never disagree with a real build.

**Acceptance Criteria:**
- [x] `Project.installCmd` column and migration, nullable, `null` meaning "derive it from the source"
- [x] `installCmd` accepted by create/update and by `POST /build` as a one-off override (500-char cap, same as the other commands)
- [x] The build worker resolves install → build → start as *this run → project setting → detection* and sends the result in the payload, so `--install-cmd` finally reaches Nixpacks
- [x] `derive_install_cmd()` in `build_manager.py` is shared by `cmd_plan` and `cmd_build`, so the plan and the build cannot drift
- [x] `GET /api/projects/:id/build-plan` returns the detected framework and commands without building anything (owner-only, `400 PROJECT_NOT_CLONED` with no source)
- [x] A Build Settings panel on the project Deploy tab: install/build/start/port fields pre-filled from the project, `Auto`/`Custom` badge per field, detected value shown as the placeholder, **Save**, **Save & Deploy**, and **Auto** to clear every override
- [x] A field the user did not touch is left out of the write, so saving build commands cannot overwrite a port the Dockerfile panel synced from `EXPOSE`
- [ ] Version selectors (Node, Python, PHP, Ruby) that emit `NIXPACKS_*_VERSION` build-time variables per project
- [ ] Nixpacks cache directory, `--config-path`, base image override and per-project build RAM limit
- [ ] Registry credentials and build/start hooks (out of scope for slice 1 of #200)

**Test Plan:**
1. pnpm-lock repository, all fields blank → the build log names no install command and Nixpacks picks `pnpm install`
2. **Detect** → the Install field placeholder shows the command derived from the lockfile
3. Type `pnpm install --frozen-lockfile`, **Save & Deploy** → the log opens with `[vexlyx] Install command: pnpm install --frozen-lockfile` and `nixpacks build` receives `--install-cmd`
4. **Auto** → every badge returns to `Auto`, and the next deploy is stored with `installCmd: null`
5. Save only a build command on a Dockerfile project whose port came from `EXPOSE` → the stored port is unchanged
6. Another user's project id → `403` on `PUT`, `GET /build-plan` and `POST /build`, and nothing is spawned
7. Project with no source on disk → `400 PROJECT_NOT_CLONED` with a message pointing at git, File Manager or WordPress
8. Command longer than 500 characters → rejected by validation before anything is written

**Developer Docs:**
- **Location:** `docs/dev/build-system.md`
- **Contents:** override resolution order, the plan/build payload shapes, the detection endpoint, the panel's save rules, how to test

**Files:**
- `apps/api/prisma/migrations/<timestamp>_add_project_install_cmd/migration.sql`
- `apps/api/src/modules/projects/service.ts`, `apps/api/src/modules/build/{routes,schema,service}.ts` (and `installCmd.test.ts`)
- `apps/api/src/modules/webhooks/{service,github-app}.ts` (GitHub deploys carry the stored override)
- `packages/shared/src/schemas/projects.ts`, `packages/shared/src/types/index.ts` (`BuildPlan`)
- `system/python/build_manager.py` (`derive_install_cmd()`) and `tests/test_build_install_command.py`
- `apps/dashboard/src/components/projects/BuildSettingsPanel.tsx` (and `.test.tsx`), `src/app/(panel)/projects/[id]/page.tsx`

Tracked in #200.

---

## Phase 6: Ecosystem & Launch

### F6.1 — Complete Documentation
**Status:** 🟢 COMPLETED

**Description:**
VitePress documentation site covering installation, development, and API reference.

**Acceptance Criteria:**
- [x] Installation guide (bare metal, Docker)
- [x] Developer guide (local setup, contributing)
- [x] API reference (auto-generated from OpenAPI)
- [x] Feature documentation for every released feature
- [x] Troubleshooting guide
- [x] Changelog
- [x] Hosted at `docs.vexlyx.atlantiqs.org`

**Test Plan:**
1. New developer reads guide → sets up local env successfully
2. API reference → all endpoints documented
3. Search → finds relevant docs

**Developer Docs:**
- **Location:** `docs/README.md`

---

### F6.2 — CI/CD Pipeline
**Status:** 🟢 COMPLETED

**Description:**
GitHub Actions for testing, building, and releasing Vexlyx.

**Acceptance Criteria:**
- [x] Lint check on PR
- [x] Type check on PR
- [x] Unit tests on PR
- [x] Build check on PR
- [x] Auto-release on tag push
- [x] Docker image build and push
- [x] Changelog generation

**Test Plan:**
1. Open PR → all checks pass
2. Push tag → release created, Docker image built
3. Merge PR → auto-deploy to staging (optional)

**Developer Docs:**
- **Location:** `docs/dev/ci-cd.md`

---

### F6.3 — Community & Support
**Status:** 🔴 NOT STARTED

**Description:**
Set up community channels and support infrastructure.

**Acceptance Criteria:**
- [ ] Discord server with channels: general, support, dev, showcase
- [ ] GitHub Discussions enabled
- [ ] Issue templates (bug, feature, question)
- [ ] `CONTRIBUTING.md` guide
- [ ] `SECURITY.md` with disclosure process
- [ ] Demo video (2-3 minutes)

**Test Plan:**
1. New user joins Discord → gets welcome message
2. Open issue → template guides report
3. Contribution PR → follows guidelines

**Developer Docs:**
- **Location:** `docs/community.md`

---

## Feature Request Template

When adding a new feature to this document, use this template:

```markdown
### FX.X — Feature Name
**Status:** 🔴 NOT STARTED

**Description:**
[Clear description of what this feature does]

**Acceptance Criteria:**
- [ ] [Specific, testable requirement]
- [ ] [Specific, testable requirement]

**Test Plan:**
1. [Step-by-step test procedure]
2. [Expected result]

**Developer Docs:**
- **Location:** `docs/dev/feature-name.md`
- **Contents:** [What the docs should cover]

**Files to Create:**
- `path/to/file.ts`
```

---

*This file is maintained by the project owner and updated after each feature completion. Last update: 2026-08-28*
