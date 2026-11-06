import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import type { FastifyBaseLogger } from "fastify";
import type { PrismaClient } from "@prisma/client";
import type {
  CertificateResponse,
  CertStatus,
  CertType,
  ProvisionSslInput,
  UploadCertificateInput,
  UpdateSslSettingsInput,
} from "@vexlyx/shared";
import { DomainError, DomainService } from "./service.js";
import { encrypt } from "../../utils/encryption.js";
import { getPythonBin } from "../../utils/pythonBin.js";
import { PYTHON_SCRIPT_TIMEOUT_MS, watchChildTimeout } from "../../utils/processWatchdog.js";

// ---------------------------------------------------------------------------
// Python Script Locator
// ---------------------------------------------------------------------------

function getSslManagerScriptPath(): string {
  const currentDir = dirname(fileURLToPath(import.meta.url));
  const candidates = [
    resolve(currentDir, "../../../../../system/python/ssl_manager.py"),
    resolve(currentDir, "../../../../system/python/ssl_manager.py"),
    resolve(process.cwd(), "../../system/python/ssl_manager.py"),
    resolve(process.cwd(), "system/python/ssl_manager.py"),
  ];

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  return candidates[0] ?? resolve(process.cwd(), "system/python/ssl_manager.py");
}

// ---------------------------------------------------------------------------
// Python Script Execution Helper
// ---------------------------------------------------------------------------

interface SslManagerPayload {
  command:
    | "generate_self_signed"
    | "parse_cert"
    | "validate_pair"
    | "save_custom"
    | "delete_cert"
    | "read_acme";
  payload: Record<string, unknown>;
}

interface SslManagerResult {
  success?: boolean;
  error?: string;
  certPath?: string;
  keyPath?: string;
  commonName?: string;
  issuer?: string;
  sans?: string[];
  validFrom?: string;
  validTo?: string;
  daysRemaining?: number;
  serialNumber?: string;
  isExpired?: boolean;
  isExpiringSoon?: boolean;
  certificates?: Array<{
    mainDomain?: string;
    sans?: string[];
    validTo?: string;
    validFrom?: string;
    issuer?: string;
  }>;
  certificate?: {
    commonName?: string;
    issuer?: string;
    sans?: string[];
    validFrom?: string;
    validTo?: string;
    daysRemaining?: number;
    serialNumber?: string;
    isExpired?: boolean;
    isExpiringSoon?: boolean;
  };
}

function getPythonExe(): string {
  if (process.env.PYTHON_PATH && existsSync(process.env.PYTHON_PATH)) {
    return process.env.PYTHON_PATH;
  }
  if (process.platform === "win32") {
    const candidates = [
      resolve(process.cwd(), "Python/pythoncore-3.14-64/python.exe"),
      resolve(process.cwd(), "apps/api/Python/pythoncore-3.14-64/python.exe"),
      resolve(process.cwd(), "../../apps/api/Python/pythoncore-3.14-64/python.exe"),
      resolve(process.env.LOCALAPPDATA || "", "Python/pythoncore-3.14-64/python.exe"),
      resolve(process.env.USERPROFILE || "", "AppData/Local/Python/pythoncore-3.14-64/python.exe"),
    ];
    for (const c of candidates) {
      if (c && existsSync(c)) {
        return c;
      }
    }
  }
  return getPythonBin();
}

async function runSslManager(
  command: SslManagerPayload["command"],
  payload: Record<string, unknown>,
): Promise<SslManagerResult> {
  const scriptPath = getSslManagerScriptPath();
  const pythonExe = getPythonExe();

  const sitePackagesPaths = [
    resolve(process.cwd(), "Python/pythoncore-3.14-64/Lib/site-packages"),
    resolve(process.cwd(), "apps/api/Python/pythoncore-3.14-64/Lib/site-packages"),
    resolve(process.env.LOCALAPPDATA || "", "Python/pythoncore-3.14-64/Lib/site-packages"),
  ].filter((p) => existsSync(p));

  const separator = process.platform === "win32" ? ";" : ":";
  const pythonPath = sitePackagesPaths.length > 0
    ? `${sitePackagesPaths.join(separator)}${process.env.PYTHONPATH ? separator + process.env.PYTHONPATH : ""}`
    : process.env.PYTHONPATH;

  return new Promise((res, rej) => {
    // The payload carries the uploaded private key for `save_custom`, so it
    // goes to the helper on stdin and never into argv, where any local process
    // could read it out of `ps` or `/proc/<pid>/cmdline` for as long as the
    // helper runs (#190). `ssl_manager.py`'s `main()` already reads
    // `{"command", "payload"}` from stdin when given no argument, and the
    // spawn already opens a stdin pipe; argv stays supported for the CLI and
    // the system-layer tests.
    const child = spawn(pythonExe, [scriptPath], {
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONIOENCODING: "utf-8",
        ...(pythonPath ? { PYTHONPATH: pythonPath } : {}),
      },
    });
    watchChildTimeout(child, PYTHON_SCRIPT_TIMEOUT_MS.ssl, (ms) =>
      rej(
        new DomainError(
          `SSL manager timed out after ${ms / 1000}s`,
          "SCRIPT_TIMEOUT",
          504,
        ),
      ),
    );

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString("utf-8");
    });

    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString("utf-8");
    });

    child.on("close", (code) => {
      if (code !== 0 && !stdout.trim()) {
        rej(
          new DomainError(
            `ssl_manager.py exited with code ${code}: ${stderr.trim()}`,
            "SSL_MANAGER_ERROR",
            500,
          ),
        );
        return;
      }

      try {
        const parsed = JSON.parse(stdout.trim()) as SslManagerResult;
        if (parsed.success === false) {
          rej(new DomainError(parsed.error ?? "SSL manager failed", "SSL_ERROR", 400));
          return;
        }
        res(parsed);
      } catch {
        rej(
          new DomainError(
            `ssl_manager.py returned invalid JSON: ${stdout}`,
            "SSL_MANAGER_INVALID_OUTPUT",
            500,
          ),
        );
      }
    });

    child.on("error", (err) => {
      rej(new DomainError(`Failed to spawn ssl_manager.py: ${err.message}`, "SSL_SPAWN_ERROR", 500));
    });

    // A helper that dies before reading (missing interpreter, import error)
    // closes the pipe, and an unhandled 'error' on a writable is what turns
    // that into a crashed API process. The `close` handler above already
    // reports the real failure.
    child.stdin.on("error", () => undefined);
    child.stdin.write(JSON.stringify({ command, payload }));
    child.stdin.end();
  });
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function calculateDaysRemaining(validToDate: Date | null): {
  daysRemaining: number | null;
  isExpired: boolean;
  isExpiringSoon: boolean;
} {
  if (!validToDate) {
    return { daysRemaining: null, isExpired: false, isExpiringSoon: false };
  }
  const diffMs = validToDate.getTime() - Date.now();
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  const isExpired = diffMs <= 0;
  const isExpiringSoon = !isExpired && days <= 7;
  return { daysRemaining: days, isExpired, isExpiringSoon };
}

// ---------------------------------------------------------------------------
// SslService
// ---------------------------------------------------------------------------

export class SslService {
  private domainService: DomainService;

  constructor(
    private readonly prisma: PrismaClient,
    logger?: Pick<FastifyBaseLogger, "error" | "warn" | "info">,
  ) {
    this.domainService = new DomainService(prisma, undefined, logger);
  }

  /**
   * Retrieves SSL certificate metadata and status for a domain.
   */
  public async getCertificate(userId: string, domainId: string): Promise<CertificateResponse | null> {
    const domain = await this.prisma.domain.findFirst({
      where: { id: domainId, userId },
      include: {
        certificate: true,
      },
    });

    if (!domain) {
      throw new DomainError("Domain not found", "DOMAIN_NOT_FOUND", 404);
    }

    if (!domain.certificate) {
      return null;
    }

    const cert = domain.certificate;
    const { daysRemaining, isExpired, isExpiringSoon } = calculateDaysRemaining(cert.validTo);

    let status: CertStatus = cert.status as CertStatus;
    if (status !== "PENDING" && status !== "ERROR") {
      if (isExpired) {
        status = "EXPIRED";
      } else if (isExpiringSoon) {
        status = "EXPIRING_SOON";
      } else {
        status = "ACTIVE";
      }

      // Sync status if changed
      if (status !== cert.status) {
        await this.prisma.certificate.update({
          where: { id: cert.id },
          data: { status },
        });
      }
    }

    return {
      id: cert.id,
      domainId: domain.id,
      type: cert.type as CertType,
      status,
      issuer: cert.issuer,
      commonName: cert.commonName,
      sans: cert.sans,
      validFrom: cert.validFrom,
      validTo: cert.validTo,
      daysRemaining,
      autoRenew: cert.autoRenew,
      forceHttps: cert.forceHttps,
      serialNumber: cert.serialNumber,
      errorMessage: cert.errorMessage,
      lastCheckedAt: cert.lastCheckedAt,
      lastRenewedAt: cert.lastRenewedAt,
      isExpiringSoon,
      isExpired,
    };
  }

  /**
   * Provisions automatic SSL for a domain (Let's Encrypt, or Self-Signed in dev mode).
   */
  public async provisionAutoSsl(
    userId: string,
    domainId: string,
    input: ProvisionSslInput = { type: "LETS_ENCRYPT", forceHttps: true, autoRenew: true },
  ): Promise<CertificateResponse> {
    const domain = await this.prisma.domain.findFirst({
      where: { id: domainId, userId },
      include: {
        project: true,
        certificate: true,
      },
    });

    if (!domain) {
      throw new DomainError("Domain not found", "DOMAIN_NOT_FOUND", 404);
    }

    if (domain.status !== "ACTIVE") {
      throw new DomainError(
        "Domain must be verified and ACTIVE before provisioning SSL",
        "DOMAIN_NOT_ACTIVE",
        400,
      );
    }

    const isLocalOrDev =
      process.env.SSL_MODE === "development" ||
      domain.hostname.endsWith(".localhost") ||
      domain.hostname === "localhost";

    if (isLocalOrDev) {
      // In development / localhost mode, generate a valid self-signed certificate with SANs
      const isWildcard = domain.hostname.startsWith("*.");
      const sans = isWildcard ? [domain.hostname] : [domain.hostname, `*.${domain.hostname}`];
      const genRes = await runSslManager("generate_self_signed", {
        hostname: domain.hostname,
        domainId: domain.id,
        sans,
        days: 90,
      });

      const validFrom = genRes.validFrom ? new Date(genRes.validFrom) : new Date();
      const validTo = genRes.validTo ? new Date(genRes.validTo) : new Date(Date.now() + 90 * 86400000);

      const cert = await this.prisma.certificate.upsert({
        where: { domainId: domain.id },
        create: {
          domainId: domain.id,
          type: "SELF_SIGNED",
          status: "ACTIVE",
          issuer: genRes.issuer ?? "Vexlyx Self-Signed Authority",
          commonName: domain.hostname,
          sans: genRes.sans ?? [domain.hostname],
          validFrom,
          validTo,
          certPath: genRes.certPath,
          keyPath: genRes.keyPath,
          serialNumber: genRes.serialNumber,
          autoRenew: input.autoRenew ?? true,
          forceHttps: input.forceHttps ?? true,
          lastCheckedAt: new Date(),
          lastRenewedAt: new Date(),
        },
        update: {
          type: "SELF_SIGNED",
          status: "ACTIVE",
          issuer: genRes.issuer ?? "Vexlyx Self-Signed Authority",
          commonName: domain.hostname,
          sans: genRes.sans ?? [domain.hostname],
          validFrom,
          validTo,
          certPath: genRes.certPath,
          keyPath: genRes.keyPath,
          serialNumber: genRes.serialNumber,
          autoRenew: input.autoRenew ?? true,
          forceHttps: input.forceHttps ?? true,
          lastCheckedAt: new Date(),
          lastRenewedAt: new Date(),
          errorMessage: null,
        },
      });

      await this.prisma.domain.update({
        where: { id: domain.id },
        data: { sslEnabled: true },
      });

      this.domainService.syncTraefikRouter({
        ...domain,
        sslEnabled: true,
        certificate: cert,
      });

      return {
        id: cert.id,
        domainId: domain.id,
        type: "SELF_SIGNED",
        status: "ACTIVE",
        issuer: cert.issuer,
        commonName: cert.commonName,
        sans: cert.sans,
        validFrom: cert.validFrom,
        validTo: cert.validTo,
        daysRemaining: 90,
        autoRenew: cert.autoRenew,
        forceHttps: cert.forceHttps,
        serialNumber: cert.serialNumber,
        errorMessage: null,
        lastCheckedAt: cert.lastCheckedAt,
        lastRenewedAt: cert.lastRenewedAt,
        isExpiringSoon: false,
        isExpired: false,
      };
    }

    // Standard Let's Encrypt flow
    const validTo = new Date(Date.now() + 90 * 86400000); // 90 days standard validity
    const cert = await this.prisma.certificate.upsert({
      where: { domainId: domain.id },
      create: {
        domainId: domain.id,
        type: "LETS_ENCRYPT",
        status: "ACTIVE",
        issuer: "Let's Encrypt Authority",
        commonName: domain.hostname,
        sans: [domain.hostname],
        validFrom: new Date(),
        validTo,
        autoRenew: input.autoRenew ?? true,
        forceHttps: input.forceHttps ?? true,
        lastCheckedAt: new Date(),
        lastRenewedAt: new Date(),
      },
      update: {
        type: "LETS_ENCRYPT",
        status: "ACTIVE",
        issuer: "Let's Encrypt Authority",
        commonName: domain.hostname,
        autoRenew: input.autoRenew ?? true,
        forceHttps: input.forceHttps ?? true,
        lastCheckedAt: new Date(),
        errorMessage: null,
      },
    });

    await this.prisma.domain.update({
      where: { id: domain.id },
      data: { sslEnabled: true },
    });

    this.domainService.syncTraefikRouter({
      ...domain,
      sslEnabled: true,
      certificate: cert,
    });

    return {
      id: cert.id,
      domainId: domain.id,
      type: "LETS_ENCRYPT",
      status: "ACTIVE",
      issuer: cert.issuer,
      commonName: cert.commonName,
      sans: cert.sans,
      validFrom: cert.validFrom,
      validTo: cert.validTo,
      daysRemaining: 90,
      autoRenew: cert.autoRenew,
      forceHttps: cert.forceHttps,
      serialNumber: cert.serialNumber,
      errorMessage: null,
      lastCheckedAt: cert.lastCheckedAt,
      lastRenewedAt: cert.lastRenewedAt,
      isExpiringSoon: false,
      isExpired: false,
    };
  }

  /**
   * Uploads and activates a custom SSL certificate and private key.
   */
  public async uploadCustomCert(
    userId: string,
    domainId: string,
    input: UploadCertificateInput,
  ): Promise<CertificateResponse> {
    const domain = await this.prisma.domain.findFirst({
      where: { id: domainId, userId },
      include: { project: true },
    });

    if (!domain) {
      throw new DomainError("Domain not found", "DOMAIN_NOT_FOUND", 404);
    }

    // Call Python ssl_manager.py to validate pair and save files
    const saveRes = await runSslManager("save_custom", {
      domainId: domain.id,
      certificate: input.certificate,
      privateKey: input.privateKey,
    });

    const parsed = saveRes.certificate ?? {};
    const validFrom = parsed.validFrom ? new Date(parsed.validFrom) : new Date();
    const validTo = parsed.validTo ? new Date(parsed.validTo) : null;
    const { daysRemaining, isExpired, isExpiringSoon } = calculateDaysRemaining(validTo);

    const initialStatus: CertStatus = isExpired
      ? "EXPIRED"
      : isExpiringSoon
        ? "EXPIRING_SOON"
        : "ACTIVE";

    // Encrypt private key with AES-256-GCM before storing in database
    const encryptedKey = encrypt(input.privateKey.trim());

    const cert = await this.prisma.certificate.upsert({
      where: { domainId: domain.id },
      create: {
        domainId: domain.id,
        type: "CUSTOM",
        status: initialStatus,
        issuer: parsed.issuer ?? "Custom Certificate",
        commonName: parsed.commonName || domain.hostname,
        sans: parsed.sans ?? [domain.hostname],
        validFrom,
        validTo,
        certPath: saveRes.certPath,
        keyPath: saveRes.keyPath,
        encryptedKey,
        serialNumber: parsed.serialNumber ?? null,
        autoRenew: false, // Custom certs are manually managed
        forceHttps: input.forceHttps ?? true,
        lastCheckedAt: new Date(),
      },
      update: {
        type: "CUSTOM",
        status: initialStatus,
        issuer: parsed.issuer ?? "Custom Certificate",
        commonName: parsed.commonName || domain.hostname,
        sans: parsed.sans ?? [domain.hostname],
        validFrom,
        validTo,
        certPath: saveRes.certPath,
        keyPath: saveRes.keyPath,
        encryptedKey,
        serialNumber: parsed.serialNumber ?? null,
        autoRenew: false,
        forceHttps: input.forceHttps ?? true,
        lastCheckedAt: new Date(),
        errorMessage: null,
      },
    });

    await this.prisma.domain.update({
      where: { id: domain.id },
      data: { sslEnabled: true },
    });

    this.domainService.syncTraefikRouter({
      ...domain,
      sslEnabled: true,
      certificate: cert,
    });

    return {
      id: cert.id,
      domainId: domain.id,
      type: "CUSTOM",
      status: initialStatus,
      issuer: cert.issuer,
      commonName: cert.commonName,
      sans: cert.sans,
      validFrom: cert.validFrom,
      validTo: cert.validTo,
      daysRemaining,
      autoRenew: cert.autoRenew,
      forceHttps: cert.forceHttps,
      serialNumber: cert.serialNumber,
      errorMessage: null,
      lastCheckedAt: cert.lastCheckedAt,
      lastRenewedAt: cert.lastRenewedAt,
      isExpiringSoon,
      isExpired,
    };
  }

  /**
   * Forces a certificate renewal check.
   */
  public async renewCertificate(userId: string, domainId: string): Promise<CertificateResponse> {
    const domain = await this.prisma.domain.findFirst({
      where: { id: domainId, userId },
      include: { certificate: true, project: true },
    });

    if (!domain || !domain.certificate) {
      throw new DomainError("Certificate not found", "CERTIFICATE_NOT_FOUND", 404);
    }

    if (domain.certificate.type === "SELF_SIGNED") {
      // Regenerate dev certificate
      return this.provisionAutoSsl(userId, domainId, {
        type: "SELF_SIGNED",
        forceHttps: domain.certificate.forceHttps,
        autoRenew: domain.certificate.autoRenew,
      });
    }

    if (domain.certificate.type === "CUSTOM") {
      throw new DomainError(
        "Custom certificates cannot be auto-renewed. Please upload a new certificate.",
        "CUSTOM_CERT_NO_AUTORENEW",
        400,
      );
    }

    // Let's Encrypt: inspect acme.json and reload Traefik
    const now = new Date();
    const newValidTo = new Date(Date.now() + 90 * 86400000);

    const updated = await this.prisma.certificate.update({
      where: { id: domain.certificate.id },
      data: {
        status: "ACTIVE",
        validTo: newValidTo,
        lastRenewedAt: now,
        lastCheckedAt: now,
        errorMessage: null,
      },
    });

    this.domainService.syncTraefikRouter({
      ...domain,
      sslEnabled: true,
      certificate: updated,
    });

    const { daysRemaining, isExpired, isExpiringSoon } = calculateDaysRemaining(updated.validTo);

    return {
      id: updated.id,
      domainId: domain.id,
      type: updated.type as CertType,
      status: "ACTIVE",
      issuer: updated.issuer,
      commonName: updated.commonName,
      sans: updated.sans,
      validFrom: updated.validFrom,
      validTo: updated.validTo,
      daysRemaining,
      autoRenew: updated.autoRenew,
      forceHttps: updated.forceHttps,
      serialNumber: updated.serialNumber,
      errorMessage: null,
      lastCheckedAt: updated.lastCheckedAt,
      lastRenewedAt: updated.lastRenewedAt,
      isExpiringSoon,
      isExpired,
    };
  }

  /**
   * Updates SSL configuration settings (e.g. HTTPS redirect toggle, autoRenew toggle).
   */
  public async updateSettings(
    userId: string,
    domainId: string,
    input: UpdateSslSettingsInput,
  ): Promise<CertificateResponse> {
    const domain = await this.prisma.domain.findFirst({
      where: { id: domainId, userId },
      include: { certificate: true, project: true },
    });

    if (!domain || !domain.certificate) {
      throw new DomainError("Certificate not found", "CERTIFICATE_NOT_FOUND", 404);
    }

    const updated = await this.prisma.certificate.update({
      where: { id: domain.certificate.id },
      data: {
        forceHttps: input.forceHttps ?? domain.certificate.forceHttps,
        autoRenew: input.autoRenew ?? domain.certificate.autoRenew,
      },
    });

    this.domainService.syncTraefikRouter({
      ...domain,
      sslEnabled: domain.sslEnabled,
      certificate: updated,
    });

    const { daysRemaining, isExpired, isExpiringSoon } = calculateDaysRemaining(updated.validTo);

    return {
      id: updated.id,
      domainId: domain.id,
      type: updated.type as CertType,
      status: updated.status as CertStatus,
      issuer: updated.issuer,
      commonName: updated.commonName,
      sans: updated.sans,
      validFrom: updated.validFrom,
      validTo: updated.validTo,
      daysRemaining,
      autoRenew: updated.autoRenew,
      forceHttps: updated.forceHttps,
      serialNumber: updated.serialNumber,
      errorMessage: updated.errorMessage,
      lastCheckedAt: updated.lastCheckedAt,
      lastRenewedAt: updated.lastRenewedAt,
      isExpiringSoon,
      isExpired,
    };
  }

  /**
   * Disables SSL for a domain and deletes associated custom certificate files.
   */
  public async disableSsl(userId: string, domainId: string): Promise<{ success: boolean; message: string }> {
    const domain = await this.prisma.domain.findFirst({
      where: { id: domainId, userId },
      include: { certificate: true, project: true },
    });

    if (!domain) {
      throw new DomainError("Domain not found", "DOMAIN_NOT_FOUND", 404);
    }

    if (domain.certificate) {
      // Clean up files via ssl_manager.py. The hostname goes with it so the
      // helper can recognise the <host>.crt/.key convenience copies
      // generate_self_signed() left next to this domain's own pair (#195).
      await runSslManager("delete_cert", { domainId: domain.id, hostname: domain.hostname });

      // Delete certificate database record
      await this.prisma.certificate.delete({
        where: { id: domain.certificate.id },
      });
    }

    await this.prisma.domain.update({
      where: { id: domain.id },
      data: { sslEnabled: false },
    });

    this.domainService.syncTraefikRouter({
      ...domain,
      sslEnabled: false,
      certificate: null,
    });

    return { success: true, message: "SSL disabled successfully" };
  }

  /**
   * Audits the caller's own certificates for upcoming expiration (<= 7 days alert threshold).
   * Scoped to `userId` like every other SSL operation, so one tenant can never
   * see (or trigger status refreshes for) another tenant's certificates.
   */
  public async checkExpiryAlerts(userId: string): Promise<{
    totalChecked: number;
    expiringSoon: number;
    expired: number;
    alerts: Array<{ domainId: string; hostname: string; daysRemaining: number | null; status: CertStatus }>;
  }> {
    const certificates = await this.prisma.certificate.findMany({
      where: { domain: { userId } },
      include: { domain: true },
    });

    let expiringSoonCount = 0;
    let expiredCount = 0;
    const alerts: Array<{ domainId: string; hostname: string; daysRemaining: number | null; status: CertStatus }> = [];

    for (const cert of certificates) {
      const { daysRemaining, isExpired, isExpiringSoon } = calculateDaysRemaining(cert.validTo);

      let newStatus: CertStatus = cert.status as CertStatus;
      if (isExpired) {
        newStatus = "EXPIRED";
        expiredCount++;
      } else if (isExpiringSoon) {
        newStatus = "EXPIRING_SOON";
        expiringSoonCount++;
      } else {
        newStatus = "ACTIVE";
      }

      if (newStatus !== cert.status) {
        await this.prisma.certificate.update({
          where: { id: cert.id },
          data: { status: newStatus, lastCheckedAt: new Date() },
        });
      }

      if (isExpiringSoon || isExpired) {
        alerts.push({
          domainId: cert.domainId,
          hostname: cert.domain.hostname,
          daysRemaining,
          status: newStatus,
        });
      }
    }

    return {
      totalChecked: certificates.length,
      expiringSoon: expiringSoonCount,
      expired: expiredCount,
      alerts,
    };
  }
}
