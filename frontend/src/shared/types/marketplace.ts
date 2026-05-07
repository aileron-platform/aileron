export type MarketplaceProvider = 'claude-code' | 'codex' | 'gemini';

export type MarketplacePackageType = 'plugin' | 'extension';

export type MarketplaceValidationSeverity = 'error' | 'warning' | 'info' | 'none';

export type MarketplaceSourceType = 'created' | 'imported' | 'cloned';

export type MarketplaceFeatureKey = 'mcp' | 'commands' | 'hooks' | 'agentsMd' | 'agents' | 'outputStyle' | 'skills';

export type MarketplaceSortKey = 'updatedAt' | 'displayName' | 'provider' | 'validationSeverity';

export type MarketplaceSortDirection = 'asc' | 'desc';

export type MarketplacePermission =
  | 'marketplace.view'
  | 'marketplace.edit'
  | 'marketplace.delete'
  | 'marketplace.export'
  | 'marketplace.import'
  | 'marketplace.install'
  | 'marketplace.registry.manage';

export interface MarketplaceValidationResult {
  severity: Exclude<MarketplaceValidationSeverity, 'none'>;
  code: string;
  messageKey: string;
  filePath?: string;
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
  registryPath: string;
  revision: string;
  updatedAt: string;
}

export interface MarketplaceFeatureContentItem {
  id: string;
  name: string;
  description?: string;
  path?: string;
  content?: string;
  data?: Record<string, unknown>;
}

export interface MarketplaceFeatureContent {
  agentsMd?: string;
  hooks: MarketplaceFeatureContentItem[];
  mcpServers: MarketplaceFeatureContentItem[];
  agents: MarketplaceFeatureContentItem[];
  commands: MarketplaceFeatureContentItem[];
  outputStyles: MarketplaceFeatureContentItem[];
  skills: MarketplaceFeatureContentItem[];
  policies?: MarketplaceFeatureContentItem[];
}

export interface MarketplacePackageFile {
  path: string;
  content: string;
  binary: boolean;
  mimeType?: string;
  size: number;
}

export interface MarketplacePackageDetail extends MarketplacePackageSummary {
  catalogMetadata: Record<string, unknown>;
  manifestMetadata: Record<string, unknown>;
  metadataConflict?: boolean;
  readmeMarkdown?: string;
  featureContent: MarketplaceFeatureContent;
  packageFiles: MarketplacePackageFile[];
  validationResults: MarketplaceValidationResult[];
  activity: MarketplaceActivityRecord[];
}

export interface MarketplacePackageSaveRequest {
  provider: MarketplaceProvider;
  packageId: string;
  revision: string;
  listing?: Record<string, unknown>;
  manifest?: Record<string, unknown>;
  readmeMarkdown?: string;
  packageFiles?: MarketplacePackageFile[];
}

export interface MarketplacePackageSaveResult {
  package: MarketplacePackageDetail;
  revision: string;
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

export interface MarketplaceActivityRecord {
  id: string;
  action: 'import' | 'install' | 'delete';
  provider?: MarketplaceProvider;
  packageId?: string;
  status: 'success' | 'failed';
  errorCode?: string;
  createdAt: string;
}

export interface MarketplaceCliPreflight {
  provider: MarketplaceProvider;
  available: boolean;
  version?: string;
  executablePath?: string;
  capabilities: {
    supportsUserScope: boolean;
    supportsMarketplaceAdd: boolean;
    supportsExtensionInstall: boolean;
  };
  errorCode?: string;
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

export interface MarketplaceInstallRequest {
  provider: MarketplaceProvider;
  packageId: string;
  revision: string;
  workspaceId: string;
}

export interface MarketplaceInstallResult {
  status:
    | 'success'
    | 'failed'
    | 'timeout'
    | 'validation'
    | 'cliUnavailable'
    | 'cliVersionUnsupported'
    | 'cliCapabilityMissing'
    | 'runtimeUnavailable';
  provider: MarketplaceProvider;
  packageId: string;
  workspaceId: string;
  errorCode?: string;
  stdout?: string;
  stderr?: string;
  truncated?: boolean;
}

export interface MarketplaceImportSource {
  provider: MarketplaceProvider;
  sourceKind: 'git' | 'local';
  source: string;
  ref?: string;
}

export interface MarketplaceImportUploadResult {
  source: MarketplaceImportSource;
  fileName: string;
}

export interface MarketplaceImportBranchesResult {
  branches: string[];
}

export interface MarketplaceImportCandidate {
  id: string;
  provider: MarketplaceProvider;
  packageId: string;
  displayName: string;
  sourcePath: string;
  duplicate: boolean;
  duplicateAction: 'skip' | 'overwrite' | 'import-as-new';
  newPackageId?: string;
  localRevision?: string;
  validationSeverity: MarketplaceValidationSeverity;
  validationResults: MarketplaceValidationResult[];
}

export interface MarketplaceImportRequest {
  source: MarketplaceImportSource;
  candidates: MarketplaceImportCandidate[];
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

export interface MarketplaceRegistryGitStatus {
  branch: string;
  isGitRepo: boolean;
  staged: MarketplaceRegistryGitFileChange[];
  unstaged: MarketplaceRegistryGitFileChange[];
  untracked: MarketplaceRegistryGitFileChange[];
  stagedCount: number;
  unstagedCount: number;
  untrackedCount: number;
}

export interface MarketplaceRegistryGitFileChange {
  path: string;
  status: string;
  type: 'added' | 'modified' | 'deleted' | 'renamed' | 'copied' | 'typechange' | 'unmerged' | 'untracked';
  oldPath?: string | null;
}

export interface MarketplaceRegistryGitDiff {
  path: string;
  patch: string;
  diff: string;
  binary: boolean;
  commitId?: string | null;
  head?: 'WORKTREE' | 'INDEX' | null;
}

export interface MarketplaceRegistryGitCommitSummary {
  id: string;
  message: string;
  author: string;
  email?: string | null;
  timestamp: string;
  additions: number;
  deletions: number;
  filesChanged: number;
}

export interface MarketplaceRegistryGitCommitList {
  page: number;
  pageSize: number;
  total: number;
  items: MarketplaceRegistryGitCommitSummary[];
}

export interface MarketplaceRegistryGitCommitFiles {
  commitId: string;
  files: MarketplaceRegistryGitFileChange[];
}

export interface MarketplaceRegistryGitOperationResult {
  success: boolean;
  messageKey: string;
  repository?: MarketplaceRegistryRepositoryStatus | null;
  errorCode?: string | null;
}

export interface MarketplaceRegistrySshKey {
  exists: boolean;
  publicKey?: string | null;
  fingerprint?: string | null;
  algorithm?: string | null;
  createdAt?: string | null;
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
  gitUserName?: string;
  gitUserEmail?: string;
}

export interface MarketplaceRegistryRepositoryStatus {
  isGitRepo: boolean;
  currentBranch?: string | null;
  remoteUrl?: string | null;
  hasOrigin: boolean;
  hasLocalContent: boolean;
  canCloneSafely: boolean;
  canInitSafely: boolean;
  cloneBlockedReason?: string | null;
}


export interface MarketplaceRegistryRootMetadataSavePayload {
  name: string;
  owner: {
    name: string;
    email: string;
  };
  description: string;
}
