"use client";

import { useState, useMemo } from "react";
import { toast } from "sonner";
import {
  Mailbox as MailboxIcon,
  Plus,
  Search,
  Copy,
  Check,
  KeyRound,
  Trash2,
  AlertTriangle,
  Settings2,
  Inbox,
  Send,
  ShieldAlert,
  Palmtree,
} from "lucide-react";
import { VacationResponderDialog } from "./VacationResponderDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useMail } from "@/hooks/useMail";
import { useMailboxes } from "@/hooks/useMailboxes";
import { useUsage } from "@/hooks/useUsage";
import { QuotaBadge, isQuotaAtLimit } from "@/components/quota/QuotaBadge";
import { cn } from "@/lib/utils";
import type { MailboxResponse, QuotaPreset } from "@vexlyx/shared";

const QUOTA_PRESETS: { value: QuotaPreset; label: string }[] = [
  { value: 256, label: "256 MB" },
  { value: 512, label: "512 MB" },
  { value: 1024, label: "1 GB" },
  { value: 5120, label: "5 GB" },
  { value: 10240, label: "10 GB" },
  { value: 0, label: "Unlimited" },
];

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 MB";
  const mb = bytes / (1024 * 1024);
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  return `${(mb / 1024).toFixed(2)} GB`;
}

function quotaLabel(quota: number): string {
  return QUOTA_PRESETS.find((q) => q.value === quota)?.label ?? `${quota} MB`;
}

interface ClientSetupField {
  key: string;
  label: string;
  value: string;
  /** What the app's own dropdown has to be set to for this value to work. */
  hint?: string;
  /** False for values that are a dropdown choice rather than text to paste. */
  copyable?: boolean;
}

export function buildClientSetupSections(host: string, address: string): {
  title: string;
  icon: typeof Inbox;
  fields: ClientSetupField[];
  note?: string;
}[] {
  return [
    {
      title: "Incoming Mail (IMAP)",
      icon: Inbox,
      fields: [
        { key: "imap-host", label: "Server / Hostname", value: host },
        {
          key: "imap-port",
          label: "Port (SSL/TLS)",
          value: "993",
          hint: "Connection security: SSL/TLS — encrypted from the first byte.",
        },
        {
          key: "imap-port-starttls",
          label: "Port (STARTTLS)",
          value: "143",
          hint: "Connection security: STARTTLS — starts plain and upgrades before the password.",
        },
        {
          key: "imap-auth",
          label: "Authentication",
          value: "Normal password",
          copyable: false,
          hint: "The server offers PLAIN and LOGIN, and only once the connection is encrypted.",
        },
        { key: "imap-username", label: "Username", value: address },
      ],
    },
    {
      title: "Outgoing Mail (SMTP)",
      icon: Send,
      fields: [
        { key: "smtp-host", label: "Server / Hostname", value: host },
        {
          key: "smtp-port",
          label: "Port (STARTTLS)",
          value: "587",
          hint: "Connection security: STARTTLS. Left on \"None\", the server refuses the password and the app reports \"Must issue a STARTTLS command first\".",
        },
        {
          key: "smtp-auth",
          label: "Authentication",
          value: "Normal password",
          copyable: false,
          hint: "The server offers PLAIN and LOGIN, and only once the connection is encrypted.",
        },
        { key: "smtp-username", label: "Username", value: address },
      ],
      note: "587 with STARTTLS is the only submission port Vexlyx listens on. Port 465 (implicit TLS) and plain port 25 are not offered to mail clients.",
    },
  ];
}

export function ClientSetupSections({ host, address }: { host: string; address: string }) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const copy = (value: string, key: string) => {
    void navigator.clipboard.writeText(value);
    setCopiedKey(key);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopiedKey(null), 2000);
  };

  return (
    <>
      {buildClientSetupSections(host, address).map((section) => (
        <div key={section.title} className="space-y-2">
          <h4 className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
            <section.icon className="h-3.5 w-3.5 text-muted-foreground" />
            {section.title}
          </h4>
          <div className="overflow-hidden rounded-md border border-border">
            {section.fields.map((field, idx) => (
              <div
                key={field.key}
                className={cn(
                  "flex items-center justify-between gap-2 px-3 py-2",
                  idx !== 0 && "border-t border-border",
                )}
              >
                <div className="min-w-0">
                  <p className="text-xs text-muted-foreground">{field.label}</p>
                  <code className="block truncate font-mono text-sm text-foreground">{field.value}</code>
                  {field.hint && <p className="mt-1 text-xs leading-snug text-muted-foreground">{field.hint}</p>}
                </div>
                {field.copyable !== false && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0"
                    onClick={() => copy(field.value, field.key)}
                  >
                    {copiedKey === field.key ? (
                      <Check className="h-3.5 w-3.5 text-emerald-500" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </Button>
                )}
              </div>
            ))}
          </div>
          {section.note && <p className="text-xs leading-snug text-muted-foreground">{section.note}</p>}
        </div>
      ))}
    </>
  );
}

export function MailboxesPanel() {
  const { domains } = useMail();
  const {
    mailboxes,
    isLoading,
    refresh,
    createMailbox,
    deleteMailbox,
    updateQuota,
    resetPassword,
  } = useMailboxes();
  const { usage, isLoading: isUsageLoading } = useUsage();

  const [searchQuery, setSearchQuery] = useState("");

  // Create mailbox dialog state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [localPart, setLocalPart] = useState("");
  const [domainId, setDomainId] = useState<string>("");
  const [quota, setQuota] = useState<QuotaPreset>(1024);

  // One-time password reveal dialog state
  const [revealedPassword, setRevealedPassword] = useState<{ address: string; password: string } | null>(null);
  const [copiedPassword, setCopiedPassword] = useState(false);

  // Reset password confirm state
  const [resetTarget, setResetTarget] = useState<MailboxResponse | null>(null);
  const [isResetting, setIsResetting] = useState(false);

  // Delete confirm state
  const [deleteTarget, setDeleteTarget] = useState<MailboxResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Vacation responder dialog state
  const [vacationTarget, setVacationTarget] = useState<MailboxResponse | null>(null);

  const [updatingQuotaId, setUpdatingQuotaId] = useState<string | null>(null);

  // Mail client setup dialog state
  const [setupTarget, setSetupTarget] = useState<MailboxResponse | null>(null);
  const clientHost =
    process.env.NEXT_PUBLIC_MAIL_HOSTNAME ||
    (typeof window !== "undefined" ? window.location.hostname : "your-server");

  const filteredMailboxes = useMemo(() => {
    if (!searchQuery.trim()) return mailboxes;
    const q = searchQuery.toLowerCase();
    return mailboxes.filter((m) => m.address.toLowerCase().includes(q));
  }, [mailboxes, searchQuery]);

  const copyPassword = (password: string) => {
    void navigator.clipboard.writeText(password);
    setCopiedPassword(true);
    toast.success("Copied to clipboard");
    setTimeout(() => setCopiedPassword(false), 2000);
  };

  const resetCreateForm = () => {
    setLocalPart("");
    setDomainId("");
    setQuota(1024);
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domainId) {
      toast.error("Please select a domain");
      return;
    }
    setIsCreating(true);
    try {
      const { mailbox, password } = await createMailbox({ localPart, domainId, quota });
      setIsCreateOpen(false);
      resetCreateForm();
      setRevealedPassword({ address: mailbox.address, password });
      toast.success(`Mailbox ${mailbox.address} created`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create mailbox");
    } finally {
      setIsCreating(false);
    }
  };

  const handleResetPassword = async () => {
    if (!resetTarget) return;
    setIsResetting(true);
    try {
      const { password } = await resetPassword(resetTarget.id);
      setRevealedPassword({ address: resetTarget.address, password });
      toast.success(`Password reset for ${resetTarget.address}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to reset password");
    } finally {
      setIsResetting(false);
      setResetTarget(null);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await deleteMailbox(deleteTarget.id);
      toast.success(`Mailbox ${deleteTarget.address} deleted`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete mailbox");
    } finally {
      setIsDeleting(false);
      setDeleteTarget(null);
    }
  };

  const handleQuotaChange = async (mailbox: MailboxResponse, next: QuotaPreset) => {
    setUpdatingQuotaId(mailbox.id);
    try {
      await updateQuota(mailbox.id, next);
      toast.success(`Quota updated for ${mailbox.address}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update quota");
    } finally {
      setUpdatingQuotaId(null);
    }
  };

  return (
    <div className="space-y-4">
      <Card className="border border-border bg-card">
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative w-full sm:max-w-sm">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Filter mailboxes by address…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            <div className="flex items-center gap-3">
              <QuotaBadge label="Mailboxes" usage={usage?.mailbox} isLoading={isUsageLoading} />
              <Button
                size="sm"
                className="gap-2"
                onClick={() => setIsCreateOpen(true)}
                disabled={domains.length === 0 || isQuotaAtLimit(usage?.mailbox)}
                title={isQuotaAtLimit(usage?.mailbox) ? "You've reached your mailbox limit" : undefined}
              >
                <Plus className="h-4 w-4" />
                Create Mailbox
              </Button>
            </div>
          </div>

          {domains.length === 0 && !isLoading && (
            <p className="mt-3 text-xs text-muted-foreground">
              Add a virtual domain in the Domains &amp; DKIM tab before creating mailboxes.
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="border border-border bg-card">
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : filteredMailboxes.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border py-12 text-center">
              <MailboxIcon className="h-10 w-10 text-muted-foreground opacity-50" />
              <h3 className="mt-4 text-base font-semibold text-foreground">
                No Mailboxes Yet
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Create a mailbox to enable IMAP login and mail delivery for an address.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Address</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Usage</TableHead>
                  <TableHead>Quota</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredMailboxes.map((mailbox) => {
                  const quotaBytes = mailbox.quota * 1024 * 1024;
                  const pct = mailbox.quota === 0 ? 0 : Math.min(100, (mailbox.usedBytes / quotaBytes) * 100);
                  const barColor =
                    mailbox.quota !== 0 && pct >= 90
                      ? "bg-rose-500"
                      : mailbox.quota !== 0 && pct >= 70
                        ? "bg-amber-500"
                        : "bg-emerald-500";

                  return (
                    <TableRow key={mailbox.id}>
                      <TableCell>
                        <div className="flex items-center gap-2 font-medium text-foreground">
                          <MailboxIcon className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>{mailbox.address}</span>
                          {mailbox.vacationEnabled && (
                            <Badge
                              variant="outline"
                              className="gap-1 border-indigo-500/20 bg-indigo-500/10 text-[10px] text-indigo-600 dark:text-indigo-400 py-0 px-1.5"
                            >
                              <Palmtree className="h-2.5 w-2.5" />
                              Auto-reply
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={cn(
                            mailbox.status === "ACTIVE"
                              ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "border-amber-500/20 bg-amber-500/10 text-amber-600 dark:text-amber-400",
                          )}
                        >
                          {mailbox.status}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="w-32 space-y-1">
                          <div className="flex items-center justify-between text-xs text-muted-foreground">
                            <span>{formatBytes(mailbox.usedBytes)}</span>
                            {mailbox.quota !== 0 && <span>{pct.toFixed(0)}%</span>}
                          </div>
                          {mailbox.quota !== 0 && (
                            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                              <div
                                className={cn("h-full rounded-full transition-all", barColor)}
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Select
                          value={String(mailbox.quota)}
                          onValueChange={(val) => handleQuotaChange(mailbox, Number(val) as QuotaPreset)}
                          disabled={updatingQuotaId === mailbox.id}
                        >
                          <SelectTrigger size="sm" className="w-28">
                            <SelectValue>{quotaLabel(mailbox.quota)}</SelectValue>
                          </SelectTrigger>
                          <SelectContent>
                            {QUOTA_PRESETS.map((preset) => (
                              <SelectItem key={preset.value} value={String(preset.value)}>
                                {preset.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className={cn(
                              "h-8 w-8",
                              mailbox.vacationEnabled
                                ? "text-indigo-600 hover:text-indigo-600 dark:text-indigo-400"
                                : "text-muted-foreground",
                            )}
                            aria-label="Vacation auto-responder"
                            onClick={() => setVacationTarget(mailbox)}
                          >
                            <Palmtree className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground"
                            aria-label="Mail client setup"
                            onClick={() => setSetupTarget(mailbox)}
                          >
                            <Settings2 className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground"
                            aria-label="Reset password"
                            onClick={() => setResetTarget(mailbox)}
                          >
                            <KeyRound className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-rose-600 hover:text-rose-600 dark:text-rose-400"
                            aria-label="Delete mailbox"
                            onClick={() => setDeleteTarget(mailbox)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Mail Client Setup Dialog */}
      <Dialog open={!!setupTarget} onOpenChange={(open) => !open && setSetupTarget(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-indigo-500" />
              Mail Client Setup
            </DialogTitle>
            <DialogDescription>
              Use these settings to add <span className="font-medium text-foreground">{setupTarget?.address}</span> to
              any email app (Outlook, Thunderbird, Apple Mail, a phone's mail app, etc.).
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            {setupTarget && <ClientSetupSections host={clientHost} address={setupTarget.address} />}

            <div className="flex items-start gap-2 rounded-md border border-border bg-muted/50 p-3 text-xs text-muted-foreground">
              <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>
                Password: use the one shown when this mailbox was created, or click Reset Password below to get a
                new one — Vexlyx never stores or re-displays it.
              </span>
            </div>

            {process.env.NODE_ENV === "development" && (
              <div className="flex items-start gap-2 rounded-md border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400">
                <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  Local development uses a self-signed TLS certificate, so mail apps may show a certificate-trust
                  warning on first connect.
                </span>
              </div>
            )}
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                if (setupTarget) setResetTarget(setupTarget);
                setSetupTarget(null);
              }}
              className="gap-2"
            >
              <KeyRound className="h-4 w-4" />
              Reset Password
            </Button>
            <Button onClick={() => setSetupTarget(null)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Mailbox Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MailboxIcon className="h-5 w-5 text-indigo-500" />
              Create Mailbox
            </DialogTitle>
            <DialogDescription>
              Provisions a new virtual mailbox and syncs it into Dovecot for IMAP access.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreate} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="localPart">Address</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="localPart"
                  required
                  placeholder="jane"
                  value={localPart}
                  onChange={(e) => setLocalPart(e.target.value.toLowerCase())}
                  className="flex-1"
                />
                <span className="text-sm text-muted-foreground">@</span>
                <Select value={domainId} onValueChange={setDomainId}>
                  <SelectTrigger className="flex-1">
                    <SelectValue placeholder="Select domain" />
                  </SelectTrigger>
                  <SelectContent>
                    {domains.map((d) => (
                      <SelectItem key={d.domainId} value={d.domainId}>
                        {d.hostname}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="quota">Storage Quota</Label>
              <Select value={String(quota)} onValueChange={(val) => setQuota(Number(val) as QuotaPreset)}>
                <SelectTrigger id="quota" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {QUOTA_PRESETS.map((preset) => (
                    <SelectItem key={preset.value} value={String(preset.value)}>
                      {preset.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <DialogFooter className="gap-2 sm:gap-0">
              <Button type="button" variant="outline" onClick={() => setIsCreateOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={isCreating}>
                {isCreating ? "Creating…" : "Create Mailbox"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* One-time Password Reveal Dialog */}
      <Dialog open={!!revealedPassword} onOpenChange={(open) => !open && setRevealedPassword(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <KeyRound className="h-5 w-5 text-emerald-500" />
              Mailbox Password
            </DialogTitle>
            <DialogDescription>
              Password for <span className="font-medium text-foreground">{revealedPassword?.address}</span>.
              This is shown only once — copy it now, it cannot be retrieved later.
            </DialogDescription>
          </DialogHeader>

          <div className="flex items-center gap-2 rounded-md border border-border bg-muted/50 p-3">
            <code className="flex-1 break-all font-mono text-sm text-foreground">
              {revealedPassword?.password}
            </code>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={() => revealedPassword && copyPassword(revealedPassword.password)}
            >
              {copiedPassword ? (
                <Check className="h-4 w-4 text-emerald-500" />
              ) : (
                <Copy className="h-4 w-4" />
              )}
            </Button>
          </div>

          <div className="flex items-start gap-2 rounded-md border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>Store this password securely. Vexlyx does not keep a copy of it.</span>
          </div>

          <DialogFooter>
            <Button onClick={() => setRevealedPassword(null)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset Password Confirm Dialog */}
      <Dialog open={!!resetTarget} onOpenChange={(open) => !open && setResetTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset Mailbox Password</DialogTitle>
            <DialogDescription>
              This generates a new random password for{" "}
              <span className="font-medium text-foreground">{resetTarget?.address}</span> and invalidates
              the current one immediately. Any signed-in mail clients will need to be updated.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setResetTarget(null)} disabled={isResetting}>
              Cancel
            </Button>
            <Button onClick={handleResetPassword} disabled={isResetting}>
              {isResetting ? "Resetting…" : "Reset Password"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm Dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
              <Trash2 className="h-5 w-5" />
              Delete Mailbox
            </DialogTitle>
            <DialogDescription>
              This permanently deletes{" "}
              <span className="font-medium text-foreground">{deleteTarget?.address}</span> and its stored
              email. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isDeleting}
            >
              {isDeleting ? "Deleting…" : "Delete Mailbox"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Vacation Responder Dialog */}
      <VacationResponderDialog
        mailbox={vacationTarget}
        open={!!vacationTarget}
        onOpenChange={(open) => !open && setVacationTarget(null)}
        onSuccess={refresh}
      />
    </div>
  );
}
