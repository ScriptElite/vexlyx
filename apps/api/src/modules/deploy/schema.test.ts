import { describe, expect, it } from "vitest";

import { DeployBodySchema } from "./schema.js";

// #192: this value is written into the project's Traefik rule as Host(`value`),
// so anything that can close that rule or the YAML label around it must not
// reach docker_manager.py.
const INJECTIONS: Record<string, string> = {
  "extra Host() clause": "app.example.com`) or Host(`victim.example.org",
  "extra label": 'app.example.com"\n      - "traefik.http.services.stolen.loadbalancer.server.url=http://other:3000',
  "service key": 'app.example.com"\n    volumes:\n      - "/:/host #',
  "path": "../../etc/shadow",
  "url": "http://app.example.com",
  "space": "app example.com",
  "unicode": "ünïcode.example.com",
};

function accepted(domain?: string): boolean {
  const body = domain === undefined ? {} : { domain };
  return DeployBodySchema.safeParse(body).success;
}

describe("DeployBodySchema.domain", () => {
  it("allows omitting the override entirely", () => {
    expect(accepted(undefined)).toBe(true);
  });

  it.each([
    "app.example.com",
    "example.com",
    "app.vexlyx.localhost",
    "*.example.com",
    "App.Example.COM",
    "192.0.2.1",
    "10.0.0.5",
  ])("accepts the hostname or address %s", (domain) => {
    expect(accepted(domain)).toBe(true);
  });

  it.each(Object.entries(INJECTIONS))("rejects %s", (_label, domain) => {
    expect(accepted(domain)).toBe(false);
  });

  it("rejects a name longer than the 253-character limit", () => {
    const label = "a".repeat(63);
    const domain = `${label}.${label}.${label}.${label}.${label}.com`;
    expect(domain.length).toBeGreaterThan(253);
    expect(accepted(domain)).toBe(false);
  });

  it("rejects a bare IPv6 literal, which the rule cannot match anyway", () => {
    expect(accepted("::1")).toBe(false);
  });

  it("normalises the override the way the domains module stores it", () => {
    expect(DeployBodySchema.parse({ domain: " App.Example.COM " }).domain).toBe("app.example.com");
  });
});
