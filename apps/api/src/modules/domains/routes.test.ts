import { describe, it, expect, vi, afterEach } from "vitest";
import Fastify from "fastify";
import type { PrismaClient } from "@prisma/client";

process.env.DATABASE_URL ??=
  "postgresql://user:pass@localhost:5432/vexlyx_test";
process.env.SESSION_SECRET ??=
  "test-session-secret-at-least-32-characters-long";
const { domainRoutes } = await import("./routes.js");
const { DomainService, DomainError } = await import("./service.js");
const { SslService } = await import("./ssl-service.js");

afterEach(() => vi.restoreAllMocks());

async function appFixture() {
  const app = Fastify();
  app.decorate("prisma", {} as PrismaClient);
  app.decorate("requireAuth", async (request, reply) => {
    if (request.headers.authorization !== "test-session") {
      return reply
        .status(401)
        .send({ error: "Unauthorized", code: "UNAUTHORIZED", details: {} });
    }
    request.userId = "u1";
  });
  await app.register(domainRoutes, { prefix: "/api/domains" });
  return app;
}

describe("PATCH /api/domains/:id", () => {
  it("requires authentication", async () => {
    const update = vi.spyOn(DomainService.prototype, "update");
    const app = await appFixture();
    try {
      const response = await app.inject({
        method: "PATCH",
        url: "/api/domains/d1",
        payload: { projectId: "p1" },
      });
      expect(response.statusCode).toBe(401);
      expect(update).not.toHaveBeenCalled();
    } finally {
      await app.close();
    }
  });

  it("validates the payload before updating", async () => {
    const update = vi.spyOn(DomainService.prototype, "update");
    const app = await appFixture();
    try {
      const response = await app.inject({
        method: "PATCH",
        url: "/api/domains/d1",
        headers: { authorization: "test-session" },
        payload: {},
      });
      expect(response.statusCode).toBe(400);
      expect(update).not.toHaveBeenCalled();
    } finally {
      await app.close();
    }
  });

  it("updates using the authenticated user", async () => {
    const update = vi
      .spyOn(DomainService.prototype, "update")
      .mockResolvedValue({ id: "d1", projectId: null } as never);
    const app = await appFixture();
    try {
      const response = await app.inject({
        method: "PATCH",
        url: "/api/domains/d1",
        headers: { authorization: "test-session" },
        payload: { projectId: null },
      });
      expect(response.statusCode).toBe(200);
      expect(response.json()).toEqual({ id: "d1", projectId: null });
      expect(update).toHaveBeenCalledWith("u1", "d1", { projectId: null });
    } finally {
      await app.close();
    }
  });

  it("returns the domain error without exposing other users' domains", async () => {
    vi.spyOn(DomainService.prototype, "update").mockRejectedValue(
      new DomainError("Domain not found", "DOMAIN_NOT_FOUND", 404),
    );
    const app = await appFixture();
    try {
      const response = await app.inject({
        method: "PATCH",
        url: "/api/domains/d1",
        headers: { authorization: "test-session" },
        payload: { projectId: "p1" },
      });
      expect(response.statusCode).toBe(404);
      expect(response.json()).toEqual({
        error: "Domain not found",
        code: "DOMAIN_NOT_FOUND",
        details: {},
      });
    } finally {
      await app.close();
    }
  });
});

describe("GET /api/domains/ssl/alerts", () => {
  it("requires authentication", async () => {
    const check = vi.spyOn(SslService.prototype, "checkExpiryAlerts");
    const app = await appFixture();
    try {
      const response = await app.inject({ method: "GET", url: "/api/domains/ssl/alerts" });
      expect(response.statusCode).toBe(401);
      expect(check).not.toHaveBeenCalled();
    } finally {
      await app.close();
    }
  });

  it("scopes the audit to the authenticated user", async () => {
    const result = { totalChecked: 0, expiringSoon: 0, expired: 0, alerts: [] };
    const check = vi.spyOn(SslService.prototype, "checkExpiryAlerts").mockResolvedValue(result);
    const app = await appFixture();
    try {
      const response = await app.inject({
        method: "GET",
        url: "/api/domains/ssl/alerts",
        headers: { authorization: "test-session" },
      });
      expect(response.statusCode).toBe(200);
      expect(response.json()).toEqual(result);
      expect(check).toHaveBeenCalledWith("u1");
    } finally {
      await app.close();
    }
  });
});

describe("POST /api/domains/:id/verify — HTTPS after verification (#161)", () => {
  const verified = {
    verified: true,
    status: "ACTIVE" as const,
    message: "Domain verified successfully. Traefik traffic routing is active.",
    expectedRecord: { recordName: "_vexlyx-challenge", recordValue: "token" },
    detectedRecords: ["token"],
  };

  const unverified = { ...verified, verified: false, status: "PENDING" as const };

  /** The domain row as it reads *after* verification, minus what each case varies. */
  const domainRow = (over: Record<string, unknown> = {}) => ({
    id: "d1",
    hostname: "app.customer.com",
    sslEnabled: false,
    ...over,
  });

  async function verifyCall() {
    const app = await appFixture();
    try {
      return await app.inject({
        method: "POST",
        url: "/api/domains/d1/verify",
        headers: { authorization: "test-session" },
      });
    } finally {
      await app.close();
    }
  }

  function stub(over: Record<string, unknown> = {}) {
    const verify = vi.spyOn(DomainService.prototype, "verify").mockResolvedValue(verified as never);
    const get = vi
      .spyOn(DomainService.prototype, "getById")
      .mockResolvedValue(domainRow(over) as never);
    const provision = vi
      .spyOn(SslService.prototype, "provisionAutoSsl")
      .mockResolvedValue({ id: "c1" } as never);
    return { verify, get, provision };
  }

  it("provisions the certificate instead of leaving the domain on plain HTTP", async () => {
    const { provision } = stub();
    const response = await verifyCall();

    expect(response.statusCode).toBe(200);
    // The same defaults the manual "Provision SSL" action applies.
    expect(provision).toHaveBeenCalledWith("u1", "d1", {
      type: "LETS_ENCRYPT",
      forceHttps: true,
      autoRenew: true,
    });
    expect(response.json().message).not.toBe(verified.message);
    expect(response.json().message).toContain("HTTPS");
  });

  it("does not order a certificate for a wildcard hostname", async () => {
    // The resolver is HTTP-01 only, so `*.example.com` can never be issued;
    // ordering it anyway would fail and retry against Let's Encrypt's limits.
    const { provision } = stub({ hostname: "*.customer.com" });
    const response = await verifyCall();

    expect(response.statusCode).toBe(200);
    expect(provision).not.toHaveBeenCalled();
    expect(response.json().message).toBe(verified.message);
  });

  it("does not order a second certificate for a domain that already has one", async () => {
    const { provision } = stub({ sslEnabled: true });
    await verifyCall();

    expect(provision).not.toHaveBeenCalled();
  });

  it("leaves SSL alone when the domain did not verify", async () => {
    const verify = vi
      .spyOn(DomainService.prototype, "verify")
      .mockResolvedValue(unverified as never);
    const get = vi.spyOn(DomainService.prototype, "getById");
    const provision = vi.spyOn(SslService.prototype, "provisionAutoSsl");

    const response = await verifyCall();

    expect(response.statusCode).toBe(200);
    expect(verify).toHaveBeenCalled();
    expect(get).not.toHaveBeenCalled();
    expect(provision).not.toHaveBeenCalled();
    expect(response.json()).toEqual(unverified);
  });

  it("still reports a successful verification when the certificate cannot be ordered", async () => {
    // Verification is already committed at this point; a failed certificate
    // order must not rewrite it as an error the operator then acts on.
    stub();
    vi.spyOn(SslService.prototype, "provisionAutoSsl").mockRejectedValue(new Error("helper unavailable"));

    const response = await verifyCall();

    expect(response.statusCode).toBe(200);
    expect(response.json().verified).toBe(true);
    expect(response.json().message).toBe(verified.message);
  });
});
