import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { describe, beforeEach, expect, it, vi } from "vitest";
import type { PrismaClient } from "@prisma/client";

process.env.DATABASE_URL ??= "postgresql://user:pass@localhost:5432/vexlyx_test";
process.env.SESSION_SECRET ??= "test-session-secret-at-least-32-characters-long";

const spawned: { file: string; args: string[] }[] = [];
const stdinDocuments: string[] = [];

// Stands in for `ssl_manager.py`: it records what was put on the command line
// and what arrived on stdin, and answers with the JSON document the helper
// would print. The answer is scheduled rather than triggered by stdin, so a
// caller that still passes the payload in argv fails the assertions below
// instead of hanging.
vi.mock("node:child_process", () => ({
  spawn: (file: string, args: string[]) => {
    spawned.push({ file, args });
    const child = Object.assign(new EventEmitter(), {
      stdin: new PassThrough(),
      stdout: new PassThrough(),
      stderr: new PassThrough(),
      kill: () => true,
    });
    child.stdin.on("data", (chunk: Buffer) => {
      stdinDocuments.push(chunk.toString("utf-8"));
    });
    setImmediate(() => {
      child.stdout.end(
        JSON.stringify({
          success: true,
          certPath: "/etc/traefik/certs/domain-d1.crt",
          keyPath: "/etc/traefik/certs/domain-d1.key",
          certificate: {
            issuer: "Test CA",
            commonName: "app.example.com",
            sans: ["app.example.com"],
            serialNumber: "01",
            validFrom: new Date().toISOString(),
            validTo: new Date(Date.now() + 86_400_000).toISOString(),
          },
        }),
      );
      child.emit("close", 0);
    });
    return child;
  },
}));

const { SslService } = await import("./ssl-service.js");

const PRIVATE_KEY = [
  "-----BEGIN PRIVATE KEY-----",
  "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJTUt9Us8cKj",
  "-----END PRIVATE KEY-----",
].join("\n");

function fixture() {
  const prisma = {
    domain: {
      findFirst: vi.fn().mockResolvedValue({
        id: "d1",
        hostname: "app.example.com",
        userId: "u1",
        status: "ACTIVE",
        sslEnabled: false,
        // No project: syncTraefikRouter then only unlinks a route file that
        // does not exist here, instead of writing one.
        project: null,
        certificate: null,
      }),
      update: vi.fn().mockResolvedValue(undefined),
    },
    certificate: {
      upsert: vi.fn().mockImplementation(({ create }) => Promise.resolve({ id: "c1", ...create })),
    },
  };
  return { prisma, service: new SslService(prisma as unknown as PrismaClient) };
}

describe("ssl_manager.py invocation (#190)", () => {
  const upload = (service: ReturnType<typeof fixture>["service"]) =>
    service.uploadCustomCert("u1", "d1", {
      certificate: "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
      privateKey: PRIVATE_KEY,
      forceHttps: true,
    });

  // The mock accumulates for the whole module, so each test starts from an
  // empty record; otherwise this would assert on the previous test's call.
  beforeEach(() => {
    spawned.length = 0;
    stdinDocuments.length = 0;
  });

  it("passes the payload on stdin and nothing but the script on the command line", async () => {
    const { service } = fixture();

    await upload(service);

    expect(spawned).toHaveLength(1);
    const call = spawned[0];
    if (!call) throw new Error("the helper was never spawned");
    expect(call.args).toHaveLength(1);
    expect(call.args[0]).toMatch(/ssl_manager\.py$/);

    expect(stdinDocuments).toHaveLength(1);
    const document = JSON.parse(stdinDocuments[0] ?? "") as {
      command: string;
      payload: Record<string, unknown>;
    };
    expect(document.command).toBe("save_custom");
    expect(document.payload.domainId).toBe("d1");
    expect(document.payload.privateKey).toBe(PRIVATE_KEY);
  });

  it("keeps the private key out of every argument the helper is started with", async () => {
    const { service } = fixture();

    await upload(service);

    expect(spawned).toHaveLength(1);
    const call = spawned[0];
    if (!call) throw new Error("the helper was never spawned");
    // The whole invocation, the way `ps` and /proc/<pid>/cmdline show it.
    const commandLine = [call.file, ...call.args].join(" ");
    expect(commandLine).not.toContain("PRIVATE KEY");
    expect(commandLine).not.toContain(PRIVATE_KEY);
    for (const arg of call.args) expect(arg).not.toMatch(/BEGIN (RSA )?PRIVATE KEY/);
  });
});
