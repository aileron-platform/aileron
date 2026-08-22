export type MarketplaceTargetClient = 'claude-code' | 'codex';
export type MarketplacePackageFormat =
  | 'codex-native'
  | 'claude-native'
  | 'agent-plugin/1.0.0';
export type MarketplaceTargetClient = 'claude-code' | 'codex';

export type MarketplaceImportTargetClient = MarketplaceTargetClient | 'all';

export type MarketplacePackageType = 'plugin';

export type MarketplaceDeliveryMethod = 'plugin' | 'user-copy';

export type MarketplaceResourceType =
  | 'instructions'
  | 'skill'
  | 'subagent'
  | 'agent'
  | 'command'
  | 'output-style'
  | 'prompt'
  | 'rule'
  | 'mcp'
  | 'hook'
  | 'lsp'
  | 'app'
  | 'dependency-payload';

export type MarketplaceUserCopyResourceType =
  | 'instructions'
  | 'skill'
  | 'subagent'
  | 'command'
  | 'output-style'
  | 'prompt'
  | 'rule'
  | 'mcp'
  | 'hook'
  | 'dependency-payload'
  | 'extension'
  | 'component';

export type MarketplaceUserCopyBlockingCode =
  | 'marketplace.user_copy.inventory_unavailable'
  | 'marketplace.user_copy.duplicate_target'
  | 'marketplace.user_copy.dependency_payload_unprojectable'
  | 'marketplace.user_copy.effective_identity_conflict'
  | 'marketplace.user_copy.profile_empty'
  | 'marketplace.user_copy.target_not_writable'
  | 'marketplace.user_copy.target_unsafe'
  | 'marketplace.user_copy.target_document_invalid'
  | 'marketplace.user_copy.profile_invalid'
  | 'marketplace.user_copy.source_reference_invalid'
  | 'marketplace.user_copy.source_not_allowed'
  | 'marketplace.user_copy.source_document_invalid'
  | 'marketplace.user_copy.source_missing'
  | 'marketplace.user_copy.duplicate_resource_id'
  | 'marketplace.user_copy.unsupported_resource'
  | 'marketplace.user_copy.projection_not_supported';

export type MarketplaceValidationSeverity = 'error' | 'warning' | 'info' | 'none';
export type MarketplaceAuthoringCapability = 'read-write' | 'read-only' | 'unsupported';
export type MarketplaceAuthoringFeature =
  | 'basic'
  | 'agentsMd'
  | 'hooks'
  | 'mcp'
  | 'agents'
  | 'commands'
  | 'outputStyle'
  | 'skills'
  | 'files';

export type MarketplaceImportVariantStatus =
  | 'new-family'
  | 'add-variant'
  | 'duplicate-variant'
  | 'unrelated-duplicate'
  | 'invalid';

export type MarketplaceFeatureKey = 'mcp' | 'commands' | 'hooks' | 'agentsMd' | 'agents' | 'outputStyle' | 'skills';

export type MarketplaceSortKey = 'updatedAt' | 'displayName' | 'targetClient' | 'validationSeverity';

export type MarketplaceSortDirection = 'asc' | 'desc';

export interface MarketplaceValidationResult {
  severity: Exclude<MarketplaceValidationSeverity, 'none'>;
  code: string;
  messageKey: string;
  filePath?: string;
  details?: Record<string, unknown>;
}

export interface MarketplacePackageVariant {
  targetClient: MarketplaceTargetClient;
  packageFormat: MarketplacePackageFormat;
  packageId: string;
  displayName: string;
  registryPath?: string;
  revision?: string;
  importedAt?: string;
}

export interface MarketplacePackageSummary {
  targetClient: MarketplaceTargetClient;
  packageFormat: MarketplacePackageFormat;
  catalogPluginId: string;
  userCopyTargetClient: MarketplaceTargetClient;
  packageType: MarketplacePackageType;
  packageId: string;
  displayName: string;
  version?: string;
  description?: string;
  category?: string;
  tags: string[];
  indexedResourceNames: string[];
  validationSeverity: MarketplaceValidationSeverity;
  authoringCapabilities: Record<MarketplaceAuthoringFeature, MarketplaceAuthoringCapability>;
  registryPath: string;
  revision: string;
  updatedAt: string;
  familyId?: string;
  familyDisplayName?: string;
  sourceIdentity?: string;
  variants: MarketplacePackageVariant[];
}

export interface MarketplaceFeatureContentItem {
  id: string;
  name: string;
  description?: string;
  path?: string;
  content?: string;
  data?: Record<string, unknown>;
  ownerFilePath?: string;
  baseEntryFingerprint?: string;
}

export interface MarketplacePackageDetail extends MarketplacePackageSummary {
  catalogMetadata: Record<string, unknown>;
  manifestMetadata: Record<string, unknown>;
  metadataConflict?: boolean;
  validationResults: MarketplaceValidationResult[];
}

export interface MarketplaceListQuery {
  q?: string;
  targetClient?: MarketplaceTargetClient | 'all';
  packageType?: MarketplacePackageType | 'all';
  category?: string;
  features?: MarketplaceFeatureKey[];
  validationSeverity?: MarketplaceValidationSeverity | 'all';
  updatedFrom?: string;
  updatedTo?: string;
  sort?: MarketplaceSortKey;
  direction?: MarketplaceSortDirection;
  page: number;
  pageSize: number;
}

export interface MarketplaceListResult {
  items: MarketplacePackageSummary[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  categories: string[];
  validationSeverities: MarketplaceValidationSeverity[];
}

export type MarketplaceActivityAction =
  | 'import'
  | 'install'
  | 'copy'
  | 'delete';

export type MarketplaceActivityStatus = 'succeeded' | 'failed';

export interface MarketplaceActivityRecord {
  id: string;
  action: MarketplaceActivityAction;
  packageFormat?: MarketplacePackageFormat;
  targetClient?: MarketplaceTargetClient;
  packageId?: string;
  operationId?: string;
  workspaceId?: string;
  marketplaceId?: string;
  status: MarketplaceActivityStatus;
  errorCode?: string;
  createdAt: string;
}

export interface MarketplaceActivityListQuery {
  page: number;
  pageSize: number;
  workspaceId?: string;
  packageFormat?: MarketplacePackageFormat;
  targetClient?: MarketplaceTargetClient;
  packageId?: string;
  action?: MarketplaceActivityAction;
  status?: MarketplaceActivityStatus;
}

export interface MarketplaceActivityListResult {
  items: MarketplaceActivityRecord[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface MarketplaceActivityDetail extends MarketplaceActivityRecord {
  workspaceIdSnapshot?: string;
  catalogPluginId?: string;
  releaseRevision?: string;
  profileDigest?: string;
  projectionDigest?: string;
  materializationDigest?: string;
  projectedCount?: number;
  skippedCount?: number;
  conflictCount?: number;
  createdCount?: number;
  mergedCount?: number;
  unchangedCount?: number;
  overwrittenCount?: number;
  targetLocators: string[];
  diagnosticCodes: string[];
  commands: MarketplacePluginCliCommand[];
}

export interface MarketplaceCreateRequest {
  packageFormat: MarketplacePackageFormat;
  targetClients: MarketplaceTargetClient[];
  packageId: string;
  displayName: string;
  version: string;
  description?: string;
}

export interface MarketplacePackageFormatOption {
  packageFormat: MarketplacePackageFormat;
  targetClients: MarketplaceTargetClient[];
  authoringCapabilities: Record<MarketplaceAuthoringFeature, MarketplaceAuthoringCapability>;
  defaultVersion: string;
}

export interface MarketplaceDeleteRequest {
  targetClient: MarketplaceTargetClient;
  packageFormat: MarketplacePackageFormat;
  packageId: string;
}

export interface MarketplaceDeleteResult {
  deleted: boolean;
  revision?: string;
  errorCode?: string;
}

export interface MarketplacePluginInstallRequest {
  targetClient: MarketplaceTargetClient;
  packageFormat: MarketplacePackageFormat;
  packageId: string;
  version: string;
  workspaceId: string;
}

export interface MarketplaceUserCopyPreflightRequest {
  packageFormat: MarketplacePackageFormat;
  targetClient: MarketplaceTargetClient;
  catalogPluginId: string;
  releaseRevision: string;
  workspaceId: string;
}

export interface MarketplaceUserCopyOverwriteApproval {
  targetIdentity: string;
  expectedRevision: string;
}

export interface MarketplaceUserCopyApplyRequest
  extends MarketplaceUserCopyPreflightRequest {
  expectedProfileDigest: string;
  expectedSourceDigest: string;
  expectedProjectionDigest: string;
  expectedMaterializationDigest: string;
  acceptPartialCopy: boolean;
  overwriteApprovals: MarketplaceUserCopyOverwriteApproval[];
}

export interface MarketplaceUserCopyResource {
  resourceType: MarketplaceUserCopyResourceType;
  resourceId: string;
  sourceLocator: string;
  targetLocator: string;
  operation: 'create' | 'merge' | 'unchanged';
}

export interface MarketplaceUserCopyConflict {
  resourceType: MarketplaceUserCopyResourceType;
  resourceId: string;
  sourceLocator: string;
  targetLocator: string;
  targetIdentity: string;
  baselineRevision: string;
  incomingDigest: string;
  overwritable: true;
}

export interface MarketplaceUserCopyBlockingIssue {
  resourceType: string | null;
  resourceId: string | null;
  sourceLocator: string | null;
  targetLocator: string | null;
  errorCode: MarketplaceUserCopyBlockingCode;
}

export interface MarketplaceSkippedUserCopyResource {
  code: string;
  resourceType: string;
  resourceId: string;
  sourceLocator: string;
}

export type MarketplaceUserCopyPreflightStatus =
  | 'ready'
  | 'confirmation-required'
  | 'blocked';

export interface MarketplaceUserCopyPreflightResult {
  status: MarketplaceUserCopyPreflightStatus;
  packageFormat: MarketplacePackageFormat;
  targetClient: MarketplaceTargetClient;
  catalogPluginId: string;
  releaseRevision: string;
  workspaceId: string;
  sourceDigest: string;
  profileDigest: string;
  projectionDigest: string;
  materializationDigest: string;
  resources: MarketplaceUserCopyResource[];
  skippedResources: MarketplaceSkippedUserCopyResource[];
  conflicts: MarketplaceUserCopyConflict[];
  blockingIssues: MarketplaceUserCopyBlockingIssue[];
}

export interface MarketplaceUserCopyApplyResult {
  status: 'completed';
  operationId: string;
  packageFormat: MarketplacePackageFormat;
  targetClient: MarketplaceTargetClient;
  catalogPluginId: string;
  releaseRevision: string;
  workspaceId: string;
  createdCount: number;
  mergedCount: number;
  unchangedCount: number;
  overwrittenCount: number;
  skippedCount: number;
}

export type MarketplacePluginCommandStage =
  | 'marketplace-add'
  | 'plugin-install'
  | 'plugin-enable'
  | 'marketplace-list'
  | 'plugin-list'
  | 'completed';

export interface MarketplacePluginCliCommand {
  sequence: number;
  stage: MarketplacePluginCommandStage;
  argvDisplay: string;
  exitCode: number | null;
  startedAt: string;
  endedAt: string;
  stdout: string | null;
  stderr: string | null;
  stdoutOriginalByteCount: number;
  stderrOriginalByteCount: number;
  truncated: boolean;
}

export interface MarketplacePluginCommandResult {
  operationId: string;
  status: 'installed' | 'failed';
  targetClient: MarketplaceTargetClient;
  packageId: string;
  version: string;
  marketplaceId: string;
  workspaceId: string;
  stage: MarketplacePluginCommandStage;
  exitCode: number | null;
  cliMessage: string | null;
  stdout: string | null;
  stderr: string | null;
  truncated: boolean;
  commands: MarketplacePluginCliCommand[];
  warnings: Array<
    | 'marketplace.install.state-unconfirmed'
    | 'marketplace.install.command-timeout'
    | 'marketplace.install.audit-persistence-failed'
  >;
}

export interface MarketplaceImportSource {
  targetClient: MarketplaceImportTargetClient;
  sourceKind: 'git' | 'local';
  source: string;
}

export interface MarketplaceImportUploadResult {
  source: MarketplaceImportSource;
  fileName: string;
}

export interface MarketplaceImportCandidate {
  id: string;
  targetClient: MarketplaceTargetClient;
  packageFormat: MarketplacePackageFormat;
  packageId: string;
  version: string;
  displayName: string;
  familyId?: string;
  familyDisplayName?: string;
  sourceIdentity?: string;
  sourcePath: string;
  sourceMetadata?: Record<string, unknown>;
  duplicate: boolean;
  localRevision?: string;
  variantStatus: MarketplaceImportVariantStatus;
  variants: MarketplacePackageVariant[];
  validationSeverity: MarketplaceValidationSeverity;
  validationResults: MarketplaceValidationResult[];
  import?: MarketplaceImportMetadata;
}

export interface MarketplaceImportMetadata {
  version: string;
  overwrite: boolean;
}

export interface MarketplaceImportResult {
  imported: MarketplacePackageSummary[];
  failed: Array<MarketplaceImportCandidate & {
    errorCode: string;
    stage: string;
    source?: string;
    destination?: string;
    category: string;
  }>;
  warnings: MarketplaceValidationResult[];
}

export interface MarketplaceExportRequest {
  targetClient: MarketplaceTargetClient;
  packageFormat: MarketplacePackageFormat;
  packageId: string;
  revision: string;
}

export interface MarketplaceRegistrySettings {
  displayName: string;
  rootPath: string;
  status: 'uninitialized' | 'ready' | 'busy' | 'error';
  description?: string;
  maintainerName: string;
  maintainerEmail: string;
  remoteUrl?: string;
  branch?: string;
}

export interface MarketplaceRegistryRootMetadataSavePayload {
  name: string;
  owner: {
    name: string;
    email: string;
  };
  description: string;
}
