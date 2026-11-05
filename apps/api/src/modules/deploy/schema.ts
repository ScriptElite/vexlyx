import { z } from "zod";
import { HostnameSchema, IPV4_REGEX } from "@vexlyx/shared";

// The deploy `domain` override is written into the project's Traefik rule as
// Host(`value`), so it has to be a name the panel would itself route on: the
// same validator the domains module uses, plus a bare IPv4 for installs that
// address the panel by address. docker_manager.py re-checks at write time,
// because that is the process that produces the file (#192).
const DomainOverrideSchema = z
  .union([HostnameSchema, z.string().regex(IPV4_REGEX, "domain must be an IPv4 address")])
  .optional();

export const DeployBodySchema = z.object({
  domain: DomainOverrideSchema,
});

export type DeployBody = z.infer<typeof DeployBodySchema>;

export const ContainerActionBodySchema = z.object({
  action: z.enum(["start", "stop", "restart", "remove"]),
});

export type ContainerActionBody = z.infer<typeof ContainerActionBodySchema>;

export const LogsQuerySchema = z.object({
  tail: z.coerce.number().int().min(1).max(5000).default(100),
});

export type LogsQuery = z.infer<typeof LogsQuerySchema>;
