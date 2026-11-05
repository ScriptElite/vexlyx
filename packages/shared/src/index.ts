/** Current version of the Vexlyx platform */
export const VEXLYX_VERSION = "0.4.7";

/** Application name constant used across both frontend and backend */
export const APP_NAME = "Vexlyx";

export {
  RegisterSchema,
  LoginSchema,
  ChangePasswordSchema,
  TwoFactorChallengeSchema,
  VerifyTotpSetupSchema,
  DisableTwoFactorSchema,
  ForgotPasswordSchema,
  ResetPasswordSchema,
} from "./schemas/auth.js";
export type {
  RegisterInput,
  LoginInput,
  ChangePasswordInput,
  TwoFactorChallengeInput,
  VerifyTotpSetupInput,
  DisableTwoFactorInput,
  ForgotPasswordInput,
  ResetPasswordInput,
} from "./schemas/auth.js";

export {
  ProjectTypeSchema,
  ProjectStatusSchema,
  CreateProjectSchema,
  UpdateProjectSchema,
  ProjectListQuerySchema,
  ConnectRepoSchema,
  TriggerBuildSchema,
  DeploymentStatusSchema,
  DeployBodySchema,
  ContainerActionSchema,
} from "./schemas/projects.js";
export type {
  CreateProjectInput,
  UpdateProjectInput,
  ProjectListQuery,
  ConnectRepoInput,
  GitMetadata,
  TriggerBuildInput,
  DeployBody,
  ContainerAction,
} from "./schemas/projects.js";

export {
  EnvVarKeySchema,
  EnvVarValueSchema,
  SetEnvVarSchema,
  BulkSetEnvVarsSchema,
  ImportEnvFileSchema,
} from "./schemas/env.js";
export type {
  SetEnvVarInput,
  BulkSetEnvVarsInput,
  ImportEnvFileInput,
} from "./schemas/env.js";

export { SaveDockerfileSchema } from "./schemas/dockerfile.js";
export type {
  SaveDockerfileInput,
  DockerfileTemplate,
  DockerfileStatus,
} from "./schemas/dockerfile.js";

export {
  DatabaseTypeEnum,
  DatabaseNameSchema,
  CreateDatabaseSchema,
  DatabaseListQuerySchema,
} from "./schemas/databases.js";
export type {
  DatabaseType,
  CreateDatabaseInput,
  DatabaseListQuery,
  DatabaseDetail,
  AdminerAvailability,
  DatabaseListResponse,
  DatabaseConnectionTestResult,
} from "./schemas/databases.js";

export {
  GitHubCommitAuthorSchema,
  GitHubCommitSchema,
  GitHubRepositorySchema,
  GitHubPushPayloadSchema,
  GitHubPingPayloadSchema,
} from "./schemas/webhooks.js";
export type {
  GitHubPushPayload,
  GitHubPingPayload,
  GitHubWebhookResponse,
  RotateWebhookSecretResponse,
} from "./schemas/webhooks.js";

export {
  DomainStatusSchema,
  DnsModeSchema,
  SetDnsModeSchema,
  HostnameSchema,
  CreateDomainSchema,
  UpdateDomainSchema,
  DomainListQuerySchema,
  isWildcardHostname,
  getParentDomain,
  isSubdomain,
} from "./schemas/domains.js";
export type {
  DomainStatus,
  UpdateDomainInput,
  DnsMode,
  SetDnsModeInput,
  DnsDelegationCheckResponse,
  CreateDomainInput,
  DomainListQuery,
  DomainVerificationInstructions,
  DomainVerificationResult,
  DomainResponse,
} from "./schemas/domains.js";

export {
  DnsRecordTypeSchema,
  DnsRecordNameSchema,
  CreateDnsRecordSchema,
  UpdateDnsRecordSchema,
  ImportZoneFileSchema,
  generateZoneFile,
  parseZoneFile,
  IPV4_REGEX,
  IPV6_REGEX,
  DNS_NAME_REGEX,
} from "./schemas/dns.js";
export type {
  DnsRecordType,
  CreateDnsRecordInput,
  UpdateDnsRecordInput,
  ImportZoneFileInput,
  DnsRecordResponse,
  DnsResolverCheck,
  DnsPropagationResponse,
  GenerateZoneOptions,
  ParsedDnsRecord,
} from "./schemas/dns.js";
export {
  CertTypeSchema,
  CertStatusSchema,
  UploadCertificateSchema,
  ProvisionSslSchema,
  UpdateSslSettingsSchema,
} from "./schemas/ssl.js";
export type {
  CertType,
  CertStatus,
  UploadCertificateInput,
  ProvisionSslInput,
  UpdateSslSettingsInput,
  CertificateResponse,
} from "./schemas/ssl.js";

export {
  ImapStatusSchema,
  SmtpStatusSchema,
  WebmailStatusSchema,
  DkimRecordSchema,
  MailAuthCheckSchema,
  MailAuthStatusSchema,
  VirtualDomainSchema,
  RequiredMailRecordSchema,
  SendTestEmailSchema,
  TestEmailResultSchema,
  SyncVirtualDomainsSchema,
  QueueMessageSchema,
  QueueListResponseSchema,
  QueueActionResultSchema,
  DeliveryLogEntrySchema,
  DeliveryLogResponseSchema,
  DeliveryLogFilterSchema,
  DkimKeyStatusSchema,
  DkimKeySchema,
  DkimRotateResponseSchema,
  WebmailLoginActivitySchema,
  WebmailActivityResponseSchema,
} from "./schemas/mail.js";
export type {
  ImapStatusResponse,
  SmtpStatusResponse,
  WebmailStatusResponse,
  DkimRecordResponse,
  MailAuthCheck,
  MailAuthStatusResponse,
  VirtualDomain,
  RequiredMailRecordResponse,
  SendTestEmailInput,
  TestEmailResultResponse,
  SyncVirtualDomainsInput,
  QueueMessage,
  QueueListResponse,
  QueueActionResult,
  DeliveryLogEntry,
  DeliveryLogResponse,
  DeliveryLogFilterInput,
  DkimKey,
  DkimRotateResponse,
  WebmailLoginActivity,
  WebmailActivityResponse,
} from "./schemas/mail.js";

export {
  MailboxStatusSchema,
  QuotaPresetSchema,
  CreateMailboxSchema,
  UpdateMailboxQuotaSchema,
  MailboxListQuerySchema,
  MailboxSchema,
  MailboxPasswordResultSchema,
} from "./schemas/mailbox.js";
export type {
  MailboxStatus,
  QuotaPreset,
  CreateMailboxInput,
  UpdateMailboxQuotaInput,
  MailboxListQuery,
  MailboxResponse,
  MailboxPasswordResult,
} from "./schemas/mailbox.js";

export {
  AliasDestinationSchema,
  CreateAliasSchema,
  UpdateAliasDestinationsSchema,
  AliasListQuerySchema,
  AliasSchema,
} from "./schemas/alias.js";
export type {
  CreateAliasInput,
  UpdateAliasDestinationsInput,
  AliasListQuery,
  AliasResponse,
} from "./schemas/alias.js";

export {
  VacationResponderSchema,
  UpdateVacationResponderSchema,
} from "./schemas/vacation.js";
export type {
  VacationResponderResponse,
  UpdateVacationResponderInput,
} from "./schemas/vacation.js";

export {
  ServerMetricsSchema,
  ContainerMetricSchema,
  MetricSnapshotSchema,
  AlertThresholdSchema,
  MetricsRangeSchema,
  MetricsQuerySchema,
  ThresholdConfigSchema,
} from "./schemas/monitoring.js";
export type {
  ServerMetrics,
  ContainerMetric,
  MetricSnapshot,
  AlertThreshold,
  MetricsRange,
  MetricsQuery,
  ThresholdConfig,
} from "./schemas/monitoring.js";

export type {
  User,
  Role,
  ApiError,
  Project,
  ProjectType,
  ProjectStatus,
  PaginatedProjects,
  Deployment,
  DeploymentStatus,
  PaginatedDeployments,
  BuildPlan,
  EnvVar,
  DecryptedEnvVar,
} from "./types/index.js";

export {
  FileNodeSchema,
  ListFilesQuerySchema,
  ReadFileQuerySchema,
  WriteFileBodySchema,
  DeleteNodeBodySchema,
  RenameBodySchema,
  MkdirBodySchema,
  CopyBodySchema,
  MoveBodySchema,
  SftpUserSchema,
  SftpAddSshKeyBodySchema,
} from "./schemas/files.js";
export type { FileNode, SftpUser, SftpAddSshKeyBody } from "./schemas/files.js";

export {
  BackupStatusSchema,
  BackupTriggerSchema,
  BackupItemTypeSchema,
  BackupManifestDnsRecordSchema,
  BackupManifestSchema,
  BackupSnapshotSchema,
  RestoreItemSchema,
  BackupSettingsSchema,
  UpdateBackupSettingsSchema,
} from "./schemas/backups.js";
export type {
  BackupStatus,
  BackupTrigger,
  BackupItemType,
  BackupManifest,
  BackupSnapshotResponse,
  RestoreItemInput,
  BackupSettingsResponse,
  UpdateBackupSettingsInput,
} from "./schemas/backups.js";

export {
  CleanupStatusSchema,
  CleanupTriggerSchema,
  DiskUsageCategorySchema,
  DiskUsageResponseSchema,
  CleanupRunSchema,
  CleanupSettingsSchema,
  UpdateCleanupSettingsSchema,
} from "./schemas/cleanup.js";
export type {
  CleanupStatus,
  CleanupTrigger,
  DiskUsageCategory,
  DiskUsageResponse,
  CleanupRunResponse,
  CleanupSettingsResponse,
  UpdateCleanupSettingsInput,
} from "./schemas/cleanup.js";

// NOTE: scheduled-task schemas are intentionally NOT re-exported here —
// CLAUDE.md forbids adding barrel exports. Import them from
// "@vexlyx/shared/schemas/scheduledTasks" instead.

export {
  FirewallProtocolSchema,
  FirewallActionSchema,
  FirewallPolicySchema,
  FirewallRuleSchema,
  CreateFirewallRuleSchema,
  FirewallSettingsSchema,
  UpdateFirewallSettingsSchema,
  FirewallStatusSchema,
} from "./schemas/firewall.js";
export type {
  FirewallProtocol,
  FirewallAction,
  FirewallPolicy,
  FirewallRuleResponse,
  CreateFirewallRuleInput,
  FirewallSettingsResponse,
  UpdateFirewallSettingsInput,
  FirewallStatusResponse,
} from "./schemas/firewall.js";

export {
  ServiceNameSchema,
  ServiceRuntimeStatusSchema,
  ServiceActionSchema,
  ServiceStatusSchema,
  ServicesStatusSchema,
  ServiceLogsResponseSchema,
} from "./schemas/serviceStatus.js";
export type {
  ServiceName,
  ServiceRuntimeStatus,
  ServiceAction,
  ServiceStatusResponse,
  ServicesStatusResponse,
  ServiceLogsResponse,
} from "./schemas/serviceStatus.js";

export {
  DnsRecordSuggestionSchema,
  DnsOnboardingInfoSchema,
  DnsResolverCheckSchema,
  DnsRecordVerificationSchema,
  DnsVerificationResponseSchema,
} from "./schemas/dnsOnboarding.js";
export type {
  DnsRecordSuggestion,
  DnsOnboardingInfoResponse,
  DnsResolverCheckResult,
  DnsRecordVerification,
  DnsVerificationResponse,
} from "./schemas/dnsOnboarding.js";

export {
  SystemSettingsSchema,
  UpdateSystemSettingsSchema,
} from "./schemas/systemSettings.js";
export type {
  SystemSettingsResponse,
  UpdateSystemSettingsInput,
} from "./schemas/systemSettings.js";

export {
  DashboardStatsSchema,
  ActivityTypeSchema,
  ActivityItemSchema,
  DashboardSummaryResponseSchema,
} from "./schemas/dashboard.js";
export type {
  DashboardStats,
  ActivityType,
  ActivityItem,
  DashboardSummaryResponse,
} from "./schemas/dashboard.js";

export {
  RoleSchema,
  PermissionSchema,
  UserResponseSchema,
  QuotaUsageSchema,
  UsageSummarySchema,
  CreateSubAccountSchema,
  UpdateUserRoleSchema,
  UpdateUserQuotasSchema,
  UpdateUserPermissionsSchema,
} from "./schemas/users.js";
export type {
  RoleInput,
  Permission,
  UserResponse,
  QuotaUsage,
  UsageSummary,
  CreateSubAccountInput,
  UpdateUserRoleInput,
  UpdateUserQuotasInput,
  UpdateUserPermissionsInput,
} from "./schemas/users.js";

export {
  AUDIT_ACTIONS,
  AuditLogEntrySchema,
  AuditLogListResponseSchema,
  AuditLogQuerySchema,
} from "./schemas/audit-log.js";
export type {
  AuditAction,
  AuditLogEntry,
  AuditLogListResponse,
  AuditLogQuery,
} from "./schemas/audit-log.js";

export {
  GitHubAccountTypeSchema,
  GitHubRepositorySelectionSchema,
  GitHubConnectionStatusSchema,
  GitHubAppStatusSchema,
  ConfigureGitHubAppSchema,
  GitHubInstallationSchema,
  GitHubSelectableRepositorySchema,
  GitHubRepositoryListQuerySchema,
  GitHubRepositoryListSchema,
  GitHubBranchSchema,
  ConnectGitHubRepositorySchema,
  GitHubCallbackQuerySchema,
} from "./schemas/github.js";
export type {
  GitHubAppStatus,
  ConfigureGitHubAppInput,
  GitHubInstallation,
  GitHubRepository,
  GitHubRepositoryListQuery,
  GitHubRepositoryList,
  GitHubBranch,
  ConnectGitHubRepositoryInput,
  GitHubCallbackQuery,
} from "./schemas/github.js";

export {
  SystemEmailTestSchema,
  SYSTEM_EMAIL_EVENTS,
} from "./schemas/systemEmail.js";
export type {
  SystemEmailTestInput,
  SystemEmailEvent,
  SystemEmailStatusResponse,
  SystemEmailDnsRecord,
} from "./schemas/systemEmail.js";
