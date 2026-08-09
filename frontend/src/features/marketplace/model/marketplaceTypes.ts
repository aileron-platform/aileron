export type MarketplaceProvider = 'claude-code' | 'codex';

export type MarketplaceImportProvider = MarketplaceProvider | 'all';

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
  | 'dependency-payload';

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
  | 'marketplace.user_copy.unsupported_resource';

export type MarketplaceValidationSeverity = 'error' | 'warning' | 'info' | 'none';

export type MarketplaceSourceType = 'created' | 'imported' | 'cloned';
export type MarketplaceLifecycleStatus = 'draft' | 'ready';

export type MarketplaceImportVariantStatus =
  | 'new-family'
  | 'add-variant'
  | 'duplicate-variant'
  | 'unrelated-duplicate'
  | 'invalid';

export type MarketplaceFeatureKey = 'mcp' | 'commands' | 'hooks' | 'agentsMd' | 'agents' | 'outputStyle' | 'skills';

export type MarketplaceSortKey = 'updatedAt' | 'displayName' | 'provider' | 'validationSeverity';

export type MarketplaceSortDirection = 'asc' | 'desc';

export interface MarketplaceValidationResult {
  severity: Exclude<MarketplaceValidationSeverity, 'none'>;
  code: string;
  messageKey: string;
  filePath?: string;
  details?: Record<string, unknown>;
}

export interface MarketplaceProviderVariant {
  provider: MarketplaceProvider;
  packageId: string;
  displayName: string;
  registryPath?: string;
  revision?: string;
  importedAt?: string;
}

export interface MarketplacePackageSummary {
  provider: MarketplaceProvider;
  packageType: MarketplacePackageType;
  packageId: string;
  displayName: string;
  version?: string;
  description?: string;
  category?: string;
  tags: string[];
  sourceType: MarketplaceSourceType;
  indexedResourceNames: string[];
  validationSeverity: MarketplaceValidationSeverity;
  lifecycleStatus: MarketplaceLifecycleStatus;
  registryPath: string;
  revision: string;
  updatedAt: string;
  familyId?: string;
  familyDisplayName?: string;
  sourceIdentity?: string;
  variants: MarketplaceProviderVariant[];
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
  provider?: MarketplaceProvider | 'all';
  packageType?: MarketplacePackageType | 'all';
  category?: string;
  features?: MarketplaceFeatureKey[];
  validationSeverity?: MarketplaceValidationSeverity | 'all';
  sourceType?: MarketplaceSourceType | 'all';
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
  sourceTypes: MarketplaceSourceType[];
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
  provider?: MarketplaceProvider;
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
  provider?: MarketplaceProvider;
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

export interface MarketplaceCreateRequest {
  provider: MarketplaceProvider;
  packageId: string;
  displayName: string;
  description?: string;
}

export interface MarketplaceDeleteRequest {
  provider: MarketplaceProvider;
  packageId: string;
  revision: string;
}

export interface MarketplaceDeleteResult {
  deleted: boolean;
  revision?: string;
  errorCode?: string;
}

export interface MarketplacePluginInstallRequest {
  provider: MarketplaceProvider;
  packageId: string;
  revision: string;
  workspaceId: string;
}

export interface MarketplaceUserCopyPreflightRequest {
  provider: MarketplaceProvider;
  packageId: string;
  revision: string;
  workspaceId: string;
}

export interface MarketplaceUserCopyOverwriteApproval {
  targetIdentity: string;
  expectedRevision: string;
}

export interface MarketplaceUserCopyApplyRequest
  extends MarketplaceUserCopyPreflightRequest {
  expectedSourceDigest: string;
  expectedMaterializationDigest: string;
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
  resourceType: MarketplaceUserCopyResourceType | null;
  resourceId: string | null;
  sourceLocator: string | null;
  targetLocator: string | null;
  errorCode: MarketplaceUserCopyBlockingCode;
}

export type MarketplaceUserCopyPreflightStatus =
  | 'ready'
  | 'confirmation-required'
  | 'blocked';

export interface MarketplaceUserCopyPreflightResult {
  status: MarketplaceUserCopyPreflightStatus;
  provider: MarketplaceProvider;
  packageId: string;
  workspaceId: string;
  sourceDigest: string;
  profileDigest: string;
  materializationDigest: string;
  resources: MarketplaceUserCopyResource[];
  conflicts: MarketplaceUserCopyConflict[];
  blockingIssues: MarketplaceUserCopyBlockingIssue[];
}

export interface MarketplaceUserCopyApplyResult {
  status: 'completed';
  operationId: string;
  provider: MarketplaceProvider;
  packageId: string;
  workspaceId: string;
  createdCount: number;
  mergedCount: number;
  unchangedCount: number;
  overwrittenCount: number;
}

export type MarketplacePluginCommandStage =
  | 'marketplace-add'
  | 'plugin-install'
  | 'marketplace-list'
  | 'plugin-list'
  | 'completed';

export interface MarketplacePluginCommandResult {
  operationId: string;
  status: 'installed' | 'failed';
  provider: MarketplaceProvider;
  packageId: string;
  marketplaceId: string;
  workspaceId: string;
  stage: MarketplacePluginCommandStage;
  exitCode: number | null;
  cliMessage: string | null;
  stdout: string | null;
  stderr: string | null;
  truncated: boolean;
}

export interface MarketplaceImportSource {
  provider: MarketplaceImportProvider;
  sourceKind: 'git' | 'local';
  source: string;
}

export interface MarketplaceImportUploadResult {
  source: MarketplaceImportSource;
  fileName: string;
}

export interface MarketplaceImportCandidate {
  id: string;
  provider: MarketplaceProvider;
  packageId: string;
  displayName: string;
  familyId?: string;
  familyDisplayName?: string;
  sourceIdentity?: string;
  sourcePath: string;
  sourceMetadata?: Record<string, unknown>;
  duplicate: boolean;
  duplicateAction: 'skip' | 'overwrite' | 'import-as-new';
  newPackageId?: string;
  localRevision?: string;
  variantStatus: MarketplaceImportVariantStatus;
  variants: MarketplaceProviderVariant[];
  validationSeverity: MarketplaceValidationSeverity;
  validationResults: MarketplaceValidationResult[];
}

export interface MarketplaceImportResult {
  imported: MarketplacePackageSummary[];
  skipped: MarketplaceImportCandidate[];
  failed: Array<MarketplaceImportCandidate & { errorCode: string }>;
  warnings: MarketplaceValidationResult[];
}

export interface MarketplaceExportRequest {
  provider: MarketplaceProvider;
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
