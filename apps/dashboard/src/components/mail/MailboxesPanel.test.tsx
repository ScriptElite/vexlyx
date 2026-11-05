import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { buildClientSetupSections, ClientSetupSections } from "./MailboxesPanel";

// Rendered here, not re-derived: the panel's own modules are mocked away so
// importing the component drags in nothing that needs a live API.
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
vi.mock("./VacationResponderDialog", () => ({ VacationResponderDialog: () => null }));

const sections = buildClientSetupSections("mail.example.com", "postmaster@example.com");
const incoming = sections.find((s) => s.title.includes("IMAP"))!;
const outgoing = sections.find((s) => s.title.includes("SMTP"))!;

const portRows = (section: (typeof sections)[number]) =>
  section.fields.filter((f) => f.label.startsWith("Port"));

describe("buildClientSetupSections", () => {
  it("offers exactly the ports Vexlyx publishes", () => {
    // docker-compose.yml publishes 25/587 for Postfix and 143/993 for Dovecot;
    // nothing else can appear here or a client is sent to a closed port.
    expect(portRows(incoming).map((f) => f.value)).toEqual(["993", "143"]);
    expect(portRows(outgoing).map((f) => f.value)).toEqual(["587"]);
  });

  it("states which connection security each port needs, matched to the port", () => {
    // 993 is Dovecot's imaps listener with ssl = yes; 143 and 587 upgrade first.
    expect(portRows(incoming).map((f) => f.hint)).toEqual([
      expect.stringContaining("SSL/TLS"),
      expect.stringContaining("STARTTLS"),
    ]);
    for (const row of [...portRows(incoming), ...portRows(outgoing)]) {
      expect(row.hint).toMatch(/Connection security: (SSL\/TLS|STARTTLS)/);
    }
  });

  it("names the authentication mechanism the server offers", () => {
    // dovecot main.conf: auth_mechanisms = plain login
    for (const section of [incoming, outgoing]) {
      const auth = section.fields.find((f) => f.label === "Authentication");
      expect(auth?.value).toBe("Normal password");
      expect(auth?.hint).toMatch(/PLAIN and LOGIN/);
    }
  });

  it("warns that 587 refuses a password before TLS, in the server's own words", () => {
    // master.cf submission: -o smtpd_tls_security_level=encrypt
    const smtpPort = portRows(outgoing)[0];
    expect(smtpPort.hint).toContain("Must issue a STARTTLS command first");
  });

  it("says that 465 is not offered instead of leaving the client to guess", () => {
    expect(outgoing.note).toMatch(/465/);
    expect(outgoing.note).toMatch(/not offered/i);
    expect(outgoing.note).toContain("587");
  });

  it("keeps every copyable value a single paste-ready token", () => {
    // The button copies field.value straight into a host/port field, so prose
    // there would be a silent bug in the one thing the dialog is for.
    for (const section of [incoming, outgoing]) {
      for (const field of section.fields.filter((f) => f.copyable !== false)) {
        expect(field.value).not.toMatch(/\s/);
      }
    }
    expect(incoming.fields.find((f) => f.key === "imap-host")?.value).toBe("mail.example.com");
    expect(outgoing.fields.find((f) => f.key === "smtp-username")?.value).toBe("postmaster@example.com");
  });
});

describe("ClientSetupSections", () => {
  it("renders the security, authentication and 465 copy", () => {
    const { container } = render(
      <ClientSetupSections host="mail.example.com" address="postmaster@example.com" />,
    );
    expect(screen.getAllByText("Normal password")).toHaveLength(2);
    // getByText throws when the string is not in the DOM, which is the assertion.
    expect(screen.getByText(/Must issue a STARTTLS command first/)).toBeTruthy();
    expect(screen.getByText(/Port 465 \(implicit TLS\) and plain port 25 are not offered/)).toBeTruthy();
    // One copy button per paste-ready row (4 incoming + 3 outgoing); the two
    // Authentication rows have none.
    expect(container.querySelectorAll("button")).toHaveLength(7);
  });
});
