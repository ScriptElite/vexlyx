import { afterEach, describe, expect, it, vi } from "vitest";
import Fastify, { type FastifyReply, type FastifyRequest, type FastifyInstance } from "fastify";
import cookie from "@fastify/cookie";
import * as argon2 from "argon2";

process.env.DATABASE_URL ??= "postgresql://user:pass@localhost:5432/vexlyx_test";
process.env.SESSION_SECRET ??= "test-session-secret-at-least-32-characters-long";

// Duplicates SESSION_COOKIE from plugins/auth.ts on purpose: importing it here
// would evaluate config/env.ts before the two defaults above run, since static
// imports are hoisted. If the real name changes the cookie assertions fail loudly.
const SESSION_COOKIE = "vexlyx_session";

// One shared spy: buildApp() resets the module registry (so env flags re-read),
// which would otherwise give every import a fresh mock function.
const { notifyUser } = vi.hoisted(() => ({ notifyUser: vi.fn() }));
vi.mock("../system-email/notifier.js", () => ({ notifyUser }));

const OLD_PASSWORD = "correct-horse-battery-staple";
const NEW_PASSWORD = "an-entirely-different-password";

type Row = Record<string, unknown>;

const openApps: FastifyInstance[] = [];

afterEach(async () => {
  for (const app of openApps.splice(0)) await app.close();
  // buildApp() rewrites these per test; don't leak the last value into another file.
  delete process.env.ALLOW_REGISTRATION;
  delete process.env.REQUIRE_ADMIN_2FA;
});

function makeUser(overrides: Row): Row {
  return {
    id: "u1",
    email: "ada@example.com",
    name: "Ada",
    role: "USER",
    resellerId: null,
    maxProjects: 5,
    maxDomains: 5,
    maxDatabases: 3,
    maxMailboxes: 10,
    maxSubAccounts: 0,
    permissions: [],
    totpEnabled: false,
    createdAt: new Date("2026-01-01T00:00:00.000Z"),
    ...overrides,
  };
}

/** Mirrors Prisma's `select`, which is what keeps `password` out of responses. */
function project(row: Row, select?: Record<string, boolean>): Row {
  if (!select) return { ...row };
  const out: Row = {};
  for (const key of Object.keys(select)) {
    if (key in row) out[key] = row[key];
  }
  return out;
}

/** The `session:<id>` key name is shared by create/destroy; asserted via redis state below. */
const sessionKey = (id: string) => `session:${id}`;

/** The argument of a mock's first call; throws instead of asserting on undefined. */
function firstArg<A>(mock: { mock: { calls: [A][] } }): A {
  const call = mock.mock.calls[0];
  if (!call) throw new Error("expected the mock to have been called");
  return call[0];
}

function cookieValue(res: { headers: Record<string, unknown> }, name: string): string | undefined {
  const raw = res.headers["set-cookie"];
  const list = Array.isArray(raw) ? raw : raw ? [raw] : [];
  for (const entry of list) {
    const [pair] = String(entry).split(";");
    const [key, value] = String(pair).split("=");
    if (String(key).trim() === name) return String(value).trim();
  }
  return undefined;
}

function setCookieHeaders(res: { headers: Record<string, unknown> }): string[] {
  const raw = res.headers["set-cookie"];
  return Array.isArray(raw) ? raw.map(String) : raw ? [String(raw)] : [];
}

interface BuildOptions {
  users?: Row[];
  allowRegistration?: boolean;
  requireAdmin2FA?: boolean;
}

async function buildApp(options: BuildOptions = {}) {
  const users: Row[] = (options.users ?? []).map((row) => ({ ...row }));
  const sessionRows: Array<{ id: string; userId: string }> = [];
  const redisStore = new Map<string, string>();

  const findUnique = vi.fn(async (args: { where: { email?: string; id?: string }; select?: Record<string, boolean> }) => {
    const row = args.where.email
      ? users.find((user) => user.email === args.where.email)
      : users.find((user) => user.id === args.where.id);
    return row ? project(row, args.select) : null;
  });

  let seq = users.length;
  const create = vi.fn(async (args: { data: Row; select?: Record<string, boolean> }) => {
    seq += 1;
    const row = makeUser({ id: `u${seq}`, ...args.data });
    users.push(row);
    return project(row, args.select);
  });

  const count = vi.fn(async () => users.length);

  const update = vi.fn(async (args: { where: { id: string }; data: Row }) => {
    const row = users.find((user) => user.id === args.where.id);
    if (!row) throw new Error("updated user does not exist");
    Object.assign(row, args.data);
    return row;
  });

  const sessionCreate = vi.fn(async (args: { data: { id: string; userId: string } }) => {
    sessionRows.push({ id: args.data.id, userId: args.data.userId });
    return args.data;
  });
  const sessionFindMany = vi.fn(async (args: { where: { userId: string; id?: { not?: string } } }) =>
    sessionRows
      .filter((row) => row.userId === args.where.userId && row.id !== args.where.id?.not)
      .map((row) => ({ id: row.id })),
  );
  const sessionDeleteMany = vi.fn(async (args: { where: { id: { in: string[] } } }) => {
    let deleted = 0;
    for (const id of args.where.id.in) {
      const index = sessionRows.findIndex((row) => row.id === id);
      if (index >= 0) {
        sessionRows.splice(index, 1);
        deleted += 1;
      }
    }
    return { count: deleted };
  });
  const sessionDelete = vi.fn(async (args: { where: { id: string } }) => {
    const index = sessionRows.findIndex((row) => row.id === args.where.id);
    if (index < 0) throw new Error("session row already gone");
    return sessionRows.splice(index, 1)[0];
  });

  const redis = {
    get: vi.fn(async (key: string) => redisStore.get(key) ?? null),
    set: vi.fn(async (key: string, value: string) => {
      redisStore.set(key, value);
      return "OK";
    }),
    del: vi.fn(async (...keys: string[]) => {
      let removed = 0;
      for (const key of keys) if (redisStore.delete(key)) removed += 1;
      return removed;
    }),
  };

  // Stands in for the session lookup in plugins/auth.ts: a cookie that maps to a
  // live `session:<id>` entry authenticates as that user, anything else is 401.
  const requireAuth = async (request: FastifyRequest, reply: FastifyReply) => {
    const sessionId = request.cookies[SESSION_COOKIE];
    const raw = sessionId ? redisStore.get(sessionKey(sessionId)) : undefined;
    if (!raw) {
      return reply.status(401).send({ error: "Authentication required", code: "UNAUTHORIZED", details: {} });
    }
    const session = JSON.parse(raw) as { userId: string };
    Object.assign(request, { userId: session.userId });
  };

  notifyUser.mockClear();
  vi.resetModules();
  process.env.ALLOW_REGISTRATION = String(options.allowRegistration ?? true);
  process.env.REQUIRE_ADMIN_2FA = String(options.requireAdmin2FA ?? false);

  const { authRoutes } = await import("./routes.js");
  const { errorHandlerPlugin } = await import("../../plugins/error-handler.js");

  const app = Fastify();
  await app.register(cookie);
  app.decorate("prisma", {
    user: { findUnique, count, create, update },
    session: { create: sessionCreate, findMany: sessionFindMany, deleteMany: sessionDeleteMany, delete: sessionDelete },
    passwordResetToken: {
      findUnique: vi.fn(async () => null),
      create: vi.fn(async () => undefined),
      deleteMany: vi.fn(async () => ({ count: 0 })),
    },
  } as never);
  app.decorate("redis", redis as never);
  app.decorate("requireAuth", requireAuth as never);
  await app.register(errorHandlerPlugin);
  await app.register(authRoutes, { prefix: "/api/auth" });
  openApps.push(app);

  return {
    app,
    users,
    sessionRows,
    redisStore,
    calls: { findUnique, create, count, update, sessionCreate, sessionFindMany, sessionDeleteMany, sessionDelete, redis },
  };
}

async function signIn(app: FastifyInstance, email: string, password: string): Promise<string> {
  const res = await app.inject({ method: "POST", url: "/api/auth/login", payload: { email, password } });
  expect(res.statusCode).toBe(200);
  const sessionId = cookieValue(res, SESSION_COOKIE);
  if (!sessionId) throw new Error("login did not issue a session cookie");
  return sessionId;
}

const hashed = (password: string) => argon2.hash(password, { type: argon2.argon2id });

describe("POST /api/auth/register", () => {
  it("refuses everything when ALLOW_REGISTRATION is off, without creating a session", async () => {
    const { app, users, calls } = await buildApp({ allowRegistration: false });

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/register",
      payload: { email: "ada@example.com", name: "Ada", password: OLD_PASSWORD, confirmPassword: OLD_PASSWORD },
    });

    expect(res.statusCode).toBe(403);
    expect(res.json().code).toBe("REGISTRATION_DISABLED");
    expect(users).toHaveLength(0);
    expect(calls.create).not.toHaveBeenCalled();
    expect(setCookieHeaders(res)).toHaveLength(0);
  }, 30_000);

  it("promotes the first account to ADMIN and signs it in", async () => {
    const { app, redisStore, calls } = await buildApp();

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/register",
      payload: { email: "ada@example.com", name: "Ada", password: OLD_PASSWORD, confirmPassword: OLD_PASSWORD },
    });

    expect(res.statusCode).toBe(201);
    expect(res.json().user.role).toBe("ADMIN");
    expect(firstArg(calls.create).data.role).toBe("ADMIN");

    const sessionId = cookieValue(res, SESSION_COOKIE);
    expect(sessionId).toBeTruthy();
    expect(redisStore.get(sessionKey(sessionId!))).toContain("u1");
    const [cookieHeader] = setCookieHeaders(res);
    expect(cookieHeader).toMatch(/HttpOnly/);
    expect(cookieHeader).toMatch(/SameSite=Lax/);
    expect(cookieHeader).toMatch(/Path=\//);
  }, 30_000);

  it("keeps every later account a plain USER", async () => {
    const { app, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "first@example.com", password: await hashed(OLD_PASSWORD) })],
    });

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/register",
      payload: { email: "ada@example.com", name: "Ada", password: OLD_PASSWORD, confirmPassword: OLD_PASSWORD },
    });

    expect(res.statusCode).toBe(201);
    expect(res.json().user.role).toBe("USER");
    expect(firstArg(calls.create).data.role).toBe("USER");
  }, 30_000);

  it("stores an argon2id hash, never the password itself", async () => {
    const { app, users, calls } = await buildApp();

    await app.inject({
      method: "POST",
      url: "/api/auth/register",
      payload: { email: "ada@example.com", name: "Ada", password: OLD_PASSWORD, confirmPassword: OLD_PASSWORD },
    });

    const stored = String(firstArg(calls.create).data.password);
    expect(stored).not.toBe(OLD_PASSWORD);
    expect(stored).toMatch(/^\$argon2id\$/);
    expect(await argon2.verify(stored, OLD_PASSWORD)).toBe(true);
    expect(users[0]!.password).toBe(stored);
  }, 30_000);

  it("answers 409 EMAIL_EXISTS for a taken email without signing the caller in", async () => {
    const { app, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", password: await hashed(OLD_PASSWORD) })],
    });

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/register",
      payload: { email: "ada@example.com", name: "Impostor", password: NEW_PASSWORD, confirmPassword: NEW_PASSWORD },
    });

    expect(res.statusCode).toBe(409);
    expect(res.json().code).toBe("EMAIL_EXISTS");
    expect(calls.create).not.toHaveBeenCalled();
    expect(calls.sessionCreate).not.toHaveBeenCalled();
    expect(setCookieHeaders(res)).toHaveLength(0);
  }, 30_000);

  it("rejects mismatched confirmation before touching the database", async () => {
    const { app, calls } = await buildApp();

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/register",
      payload: { email: "ada@example.com", name: "Ada", password: OLD_PASSWORD, confirmPassword: "typo" },
    });

    expect(res.statusCode).toBe(400);
    expect(res.json().code).toBe("VALIDATION_ERROR");
    expect(calls.count).not.toHaveBeenCalled();
    expect(calls.create).not.toHaveBeenCalled();
  }, 30_000);
});

describe("POST /api/auth/login", () => {
  it("issues a session for the right password and returns public fields only", async () => {
    const { app, redisStore, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", password: await hashed(OLD_PASSWORD) })],
    });

    const res = await app.inject({ method: "POST", url: "/api/auth/login", payload: { email: "ada@example.com", password: OLD_PASSWORD } });

    expect(res.statusCode).toBe(200);
    expect(res.json().user).toMatchObject({ id: "u1", email: "ada@example.com", role: "USER" });
    expect(res.json().user).not.toHaveProperty("password");
    const sessionId = cookieValue(res, SESSION_COOKIE);
    expect(redisStore.has(sessionKey(sessionId!))).toBe(true);
    expect(calls.sessionCreate).toHaveBeenCalledTimes(1);
  }, 30_000);

  it("gives a wrong password and an unknown email the identical answer, and no session", async () => {
    const { app, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", password: await hashed(OLD_PASSWORD) })],
    });

    const wrongPassword = await app.inject({ method: "POST", url: "/api/auth/login", payload: { email: "ada@example.com", password: "guess-i" } });
    const unknownEmail = await app.inject({ method: "POST", url: "/api/auth/login", payload: { email: "nobody@example.com", password: "guess-i" } });

    expect(wrongPassword.statusCode).toBe(401);
    expect(unknownEmail.statusCode).toBe(401);
    expect(unknownEmail.json()).toEqual(wrongPassword.json());
    expect(unknownEmail.json().code).toBe("INVALID_CREDENTIALS");
    expect(calls.sessionCreate).not.toHaveBeenCalled();
    expect(setCookieHeaders(wrongPassword)).toHaveLength(0);
    expect(setCookieHeaders(unknownEmail)).toHaveLength(0);
  }, 30_000);

  it("returns a 2FA challenge instead of a session when TOTP is enabled", async () => {
    const { app, redisStore, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", totpEnabled: true, password: await hashed(OLD_PASSWORD) })],
    });

    const res = await app.inject({ method: "POST", url: "/api/auth/login", payload: { email: "ada@example.com", password: OLD_PASSWORD } });

    expect(res.statusCode).toBe(202);
    expect(res.json()).toEqual({ requires2FA: true, challengeToken: expect.stringMatching(/^[0-9a-f]{64}$/) });
    expect(setCookieHeaders(res)).toHaveLength(0);
    expect(calls.sessionCreate).not.toHaveBeenCalled();
    const keys = [...redisStore.keys()];
    expect(keys).toHaveLength(1);
    expect(keys[0]).toContain(res.json().challengeToken);
    expect(keys.some((key) => key.startsWith("session:"))).toBe(false);
  }, 30_000);

  it("blocks an admin without TOTP when REQUIRE_ADMIN_2FA is on, but lets users through", async () => {
    const { app, calls } = await buildApp({
      requireAdmin2FA: true,
      users: [
        makeUser({ id: "u1", email: "admin@example.com", name: "Root", role: "ADMIN", password: await hashed(OLD_PASSWORD) }),
        makeUser({ id: "u2", email: "ada@example.com", password: await hashed(OLD_PASSWORD) }),
      ],
    });

    const admin = await app.inject({ method: "POST", url: "/api/auth/login", payload: { email: "admin@example.com", password: OLD_PASSWORD } });
    const user = await app.inject({ method: "POST", url: "/api/auth/login", payload: { email: "ada@example.com", password: OLD_PASSWORD } });

    expect(admin.statusCode).toBe(403);
    expect(admin.json().code).toBe("ADMIN_2FA_REQUIRED");
    expect(setCookieHeaders(admin)).toHaveLength(0);
    expect(calls.sessionCreate).toHaveBeenCalledTimes(1);
    expect(user.statusCode).toBe(200);
  }, 30_000);
});

describe("POST /api/auth/logout", () => {
  it("drops the session from redis and Postgres and expires the cookie", async () => {
    const { app, redisStore, sessionRows, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", password: await hashed(OLD_PASSWORD) })],
    });
    const sessionId = await signIn(app, "ada@example.com", OLD_PASSWORD);
    expect(redisStore.has(sessionKey(sessionId))).toBe(true);

    const res = await app.inject({ method: "POST", url: "/api/auth/logout", headers: { cookie: `${SESSION_COOKIE}=${sessionId}` } });

    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ message: "Logged out" });
    expect(redisStore.has(sessionKey(sessionId))).toBe(false);
    expect(sessionRows).toHaveLength(0);
    expect(calls.redis.del).toHaveBeenCalledWith(sessionKey(sessionId));
    const [cleared] = setCookieHeaders(res).filter((entry) => entry.startsWith(`${SESSION_COOKIE}=`));
    expect(cleared).toBeDefined();
    expect(cleared).toMatch(/Max-Age=0|Expires=Thu, 01 Jan 1970/i);
  }, 30_000);

  it("still answers cleanly when there is no session cookie to destroy", async () => {
    const { app, calls } = await buildApp();

    const res = await app.inject({ method: "POST", url: "/api/auth/logout" });

    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ message: "Logged out" });
    expect(calls.redis.del).not.toHaveBeenCalled();
    expect(calls.sessionDelete).not.toHaveBeenCalled();
  }, 30_000);
});

describe("GET /api/auth/me", () => {
  it("rejects an absent or already-destroyed session before loading the user", async () => {
    const { app, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", password: await hashed(OLD_PASSWORD) })],
    });
    const sessionId = await signIn(app, "ada@example.com", OLD_PASSWORD);
    await app.inject({ method: "POST", url: "/api/auth/logout", headers: { cookie: `${SESSION_COOKIE}=${sessionId}` } });
    calls.findUnique.mockClear();

    const stale = await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie: `${SESSION_COOKIE}=${sessionId}` } });
    const anonymous = await app.inject({ method: "GET", url: "/api/auth/me" });

    expect(stale.statusCode).toBe(401);
    expect(anonymous.statusCode).toBe(401);
    expect(stale.json().code).toBe("UNAUTHORIZED");
    expect(calls.findUnique).not.toHaveBeenCalled();
  }, 30_000);

  it("returns the signed-in user without the password hash", async () => {
    const { app } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", name: "Ada", password: await hashed(OLD_PASSWORD) })],
    });
    const sessionId = await signIn(app, "ada@example.com", OLD_PASSWORD);

    const res = await app.inject({ method: "GET", url: "/api/auth/me", headers: { cookie: `${SESSION_COOKIE}=${sessionId}` } });

    expect(res.statusCode).toBe(200);
    expect(res.json().user).toMatchObject({ id: "u1", email: "ada@example.com", name: "Ada", totpEnabled: false });
    expect(res.json().user).not.toHaveProperty("password");
  }, 30_000);
});

describe("POST /api/auth/change-password", () => {
  it("replaces the hash, notifies, and ends every other session but the caller's", async () => {
    const { app, users, redisStore, sessionRows, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", name: "Ada", password: await hashed(OLD_PASSWORD) })],
    });
    const current = await signIn(app, "ada@example.com", OLD_PASSWORD);
    const other = await signIn(app, "ada@example.com", OLD_PASSWORD);
    expect(sessionRows).toHaveLength(2);

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/change-password",
      headers: { cookie: `${SESSION_COOKIE}=${current}` },
      payload: { currentPassword: OLD_PASSWORD, newPassword: NEW_PASSWORD, confirmNewPassword: NEW_PASSWORD },
    });

    expect(res.statusCode).toBe(200);
    expect(res.json()).toEqual({ message: "Password changed" });

    const stored = String(users[0]!.password);
    expect(stored).not.toBe(OLD_PASSWORD);
    expect(await argon2.verify(stored, NEW_PASSWORD)).toBe(true);
    expect(await argon2.verify(stored, OLD_PASSWORD)).toBe(false);
    expect(notifyUser).toHaveBeenCalledWith("password_changed", "ada@example.com", { name: "Ada" });

    expect(firstArg(calls.sessionFindMany).where).toEqual({ userId: "u1", id: { not: current } });
    expect(redisStore.has(sessionKey(current))).toBe(true);
    expect(redisStore.has(sessionKey(other))).toBe(false);
    expect(sessionRows).toEqual([{ id: current, userId: "u1" }]);
  }, 30_000);

  it("keeps the old password working if the current one is wrong, and changes nothing", async () => {
    const { app, users, redisStore, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", password: await hashed(OLD_PASSWORD) })],
    });
    const sessionId = await signIn(app, "ada@example.com", OLD_PASSWORD);
    const before = String(users[0]!.password);

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/change-password",
      headers: { cookie: `${SESSION_COOKIE}=${sessionId}` },
      payload: { currentPassword: "not-the-password", newPassword: NEW_PASSWORD, confirmNewPassword: NEW_PASSWORD },
    });

    expect(res.statusCode).toBe(401);
    expect(res.json().code).toBe("INVALID_CREDENTIALS");
    expect(String(users[0]!.password)).toBe(before);
    expect(calls.update).not.toHaveBeenCalled();
    expect(calls.sessionFindMany).not.toHaveBeenCalled();
    expect(notifyUser).not.toHaveBeenCalled();
    expect(redisStore.has(sessionKey(sessionId))).toBe(true);
  }, 30_000);

  it("rejects mismatched confirmation without verifying the current password", async () => {
    const { app, calls } = await buildApp({
      users: [makeUser({ id: "u1", email: "ada@example.com", password: await hashed(OLD_PASSWORD) })],
    });
    const sessionId = await signIn(app, "ada@example.com", OLD_PASSWORD);

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/change-password",
      headers: { cookie: `${SESSION_COOKIE}=${sessionId}` },
      payload: { currentPassword: OLD_PASSWORD, newPassword: NEW_PASSWORD, confirmNewPassword: "typo" },
    });

    expect(res.statusCode).toBe(400);
    expect(res.json().code).toBe("VALIDATION_ERROR");
    expect(calls.update).not.toHaveBeenCalled();
    expect(calls.sessionFindMany).not.toHaveBeenCalled();
  }, 30_000);

  it("requires authentication", async () => {
    const { app, calls } = await buildApp();

    const res = await app.inject({
      method: "POST",
      url: "/api/auth/change-password",
      payload: { currentPassword: OLD_PASSWORD, newPassword: NEW_PASSWORD, confirmNewPassword: NEW_PASSWORD },
    });

    expect(res.statusCode).toBe(401);
    expect(res.json().code).toBe("UNAUTHORIZED");
    expect(calls.update).not.toHaveBeenCalled();
  }, 30_000);
});

describe("GET /api/auth/config", () => {
  it("mirrors the registration and admin-2FA flags so the dashboard can hide the form", async () => {
    const open = await buildApp({ allowRegistration: true, requireAdmin2FA: true });
    const closed = await buildApp({ allowRegistration: false });

    expect((await open.app.inject({ method: "GET", url: "/api/auth/config" })).json()).toEqual({
      allowRegistration: true,
      requireAdmin2FA: true,
    });
    expect((await closed.app.inject({ method: "GET", url: "/api/auth/config" })).json()).toEqual({
      allowRegistration: false,
      requireAdmin2FA: false,
    });
  }, 30_000);
});
