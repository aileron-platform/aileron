import type { OperationId } from '@/shared/authorization/operationIds';
import type { ResourceAccessRole } from '@/shared/authorization/resourceAccessRole';
import type { ResourceAccessSource } from '@/shared/authorization/resourceAuthorization';

export type BrowserContainerStatus = 'stopped' | 'starting' | 'running' | 'error' | 'restarting';
export type WorkspaceKnowledgeBaseAttachmentStatus =
  | 'active'
  | 'pending'
  | 'pending_removal';
export type WorkspaceKnowledgeBaseMountSyncStatus =
  | 'ready'
  | 'syncing'
  | 'degraded';

export interface WorkspaceKnowledgeBaseCandidateSummary {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
}

export interface WorkspaceKnowledgeBaseAttachmentSummary {
  id: string;
  kbId: string;
  name: string;
  slug: string;
  mountAlias: string;
  status: WorkspaceKnowledgeBaseAttachmentStatus;
  attachedById?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface WorkspaceKnowledgeBaseMountSync {
  status: WorkspaceKnowledgeBaseMountSyncStatus;
  desiredRevision: number;
  observedRevision: number;
  lastKnownGoodRevision: number;
  errorCode: string | null;
  compensating: boolean;
}

export interface WorkspaceKnowledgeBaseAttachmentListResponse {
  items: WorkspaceKnowledgeBaseAttachmentSummary[];
  knowledgeBaseMountSync: WorkspaceKnowledgeBaseMountSync;
}

export interface WorkspaceKnowledgeBaseAttachmentMutationResponse {
  attachment: WorkspaceKnowledgeBaseAttachmentSummary;
  knowledgeBaseMountSync: WorkspaceKnowledgeBaseMountSync;
}

export interface WorkspaceKnowledgeBaseMountSyncResponse {
  knowledgeBaseMountSync: WorkspaceKnowledgeBaseMountSync;
}

export interface WorkspaceKnowledgeBaseAttachmentCreatePayload {
  kbId: string;
  mountAlias: string;
}

export interface WorkspaceKnowledgeBaseAttachmentUpdatePayload {
  mountAlias: string;
}

export type WorkspaceComponentPhase =
  | 'Disabled'
  | 'Stopped'
  | 'Pending'
  | 'Starting'
  | 'Restarting'
  | 'Running'
  | 'Stopping'
  | 'Error';

export type WorkspaceBootstrapPhase = 'Pending' | 'Running' | 'Succeeded' | 'Error';

export interface WorkspaceBootstrapStatusResponse {
  desiredRevision: number;
  observedRevision: number;
  phase: WorkspaceBootstrapPhase;
  errorCode?: string | null;
  lastTransitionAt?: string | null;
}

export interface WorkspaceComponentStatusResponse {
  desiredRevision: number;
  observedRevision: number;
  phase: WorkspaceComponentPhase;
  ready: boolean;
  terminalReady?: boolean;
  workloadId?: string | null;
  reason: string;
  errorCode?: string | null;
  lastTransitionAt?: string | null;
  lastSeen?: string | null;
  lastRestartRequestedAt?: string | null;
}

export interface WorkspaceComponentsResponse {
  runtime?: WorkspaceComponentStatusResponse;
  browser?: WorkspaceComponentStatusResponse;
  canvas?: WorkspaceComponentStatusResponse;
}

export type BrowserConnectivityState =
  | 'pending'
  | 'ready'
  | 'degraded'
  | 'not_ready'
  | 'unavailable';

export interface BrowserConnectivityProjectionResponse {
  contractVersion: 'browser-connectivity/v1';
  state: BrowserConnectivityState;
  admission: 'allowed' | 'denied';
  observedBrowserGeneration?: string | null;
  profileRevision?: string | null;
  credentialRevision?: string | null;
  acceptedAt?: string | null;
  expiresAt?: string | null;
  reason?: string | null;
  errorCode?: string | null;
  lastTransitionAt?: string | null;
  backendState: BrowserConnectivityState;
  backendAcceptedAt?: string | null;
  backendExpiresAt?: string | null;
  backendReason?: string | null;
  backendErrorCode?: string | null;
  frontendState: BrowserConnectivityState;
  frontendAcceptedAt?: string | null;
  frontendExpiresAt?: string | null;
  frontendReason?: string | null;
  frontendErrorCode?: string | null;
}

export interface WorkspaceRuntimeStatus {
  status: string;
  containerId?: string | null;
  runtimeUrl: string;
  browserUrl: string;
  canvasUrl: string;
  lastSeen?: string | null;
  browserContainerId?: string | null;
  browserStatus?: BrowserContainerStatus;
  browserCreatedAt?: string | null;
  browserLastSeen?: string | null;
  canvasContainerId?: string | null;
  canvasStatus?: 'stopped' | 'starting' | 'running' | 'error' | 'restarting';
  canvasCreatedAt?: string | null;
  canvasLastSeen?: string | null;
  canvasType?: 'html' | 'nextjs' | 'default';
  canvasManifestStatus?: 'missing' | 'valid' | 'invalid';
  canvasLastSyncAt?: string | null;
  canvasLastResetAt?: string | null;
}

export type FirewallEgressMode = 'blocked' | 'allowlist' | 'unrestricted';

export interface FirewallRuleResponse {
  egressMode: FirewallEgressMode;
  allowedDomains: string[];
}

export interface FirewallConfigResponse {
  workspace?: FirewallRuleResponse | null;
  browser?: FirewallRuleResponse | null;
}

export interface FirewallResourceResponse {
  revision: number;
  observedRevision: number;
  syncStatus: 'pending' | 'applying' | 'applied' | 'error' | 'unavailable';
  errorCode?: string | null;
  workspace: FirewallRuleResponse;
  browser: FirewallRuleResponse;
}

export interface WorkspaceDetailResponse {
  id: string;
  name: string;
  description?: string | null;
  accessRole: ResourceAccessRole;
  accessSource: ResourceAccessSource;
  accessSources: ResourceAccessSource[];
  allowedOperations: OperationId[];
  runtimeAccessRevision?: number;
  runtimeAccessObservedRevision?: number;
  owner?: {
    id: string;
    displayName: string;
    avatarUrl?: string | null;
    username?: string;
    email?: string;
  };
  gitUrl?: string | null;
  branch?: string;
  runtime?: string;
  provisioner?: 'docker' | 'kubernetes';
  targetNamespace?: string | null;
  overallPhase?: string;
  agenticTools?: string[];
  runtimeStatus: WorkspaceRuntimeStatus;
  browserConnectivity?: BrowserConnectivityProjectionResponse;
  bootstrap?: WorkspaceBootstrapStatusResponse;
  components?: WorkspaceComponentsResponse;
  firewallAvailable?: boolean;
  firewallUnavailableReason?: string | null;
  firewall?: FirewallConfigResponse | null;
  preferredCli?: string;
  fallbackEnabled?: boolean;
  workspacePath?: string;
  worktreeSubdir?: string;
  createdAt?: string;
  updatedAt?: string;
  runtimeJob?: unknown;
}

export interface WorkspaceSensitiveEnvVar {
  key: string;
  isConfigured: boolean;
}

export interface WorkspaceSensitiveSettingsResponse {
  setupScript?: string | null;
  envVars: WorkspaceSensitiveEnvVar[];
  acpCliArgs: string[];
}

export interface WorkspaceSensitiveSettingsReplacePayload {
  setupScript?: string | null;
  envVars?: Array<{ key: string; value: string }> | null;
  acpCliArgs?: string[] | null;
}

export type WorkspaceShareTargetType = 'user' | 'user_group';

export interface WorkspaceShareResponse {
  id: string;
  targetType: WorkspaceShareTargetType;
  targetId: string;
  targetLabel: string;
  role: Exclude<ResourceAccessRole, 'owner'>;
  grantedBy: {
    id: string;
    displayName: string;
    avatarUrl?: string | null;
    username?: string;
    email?: string;
  };
  createdAt: string;
  updatedAt?: string | null;
}

export interface WorkspaceShareListResponse {
  items: WorkspaceShareResponse[];
}

export interface RuntimeFileContentResponse {
  path: string;
  content: string;
  encoding: string;
  size: number;
  lastModified: string;
  revision?: string;
  language?: string | null;
}

export interface RuntimeDuplicateResponse {
  destinationPath: string;
}

export interface RuntimeSaveFileResponse {
  revision: string;
}

export interface RuntimeBatchDeleteResponse {
  deleted: string[];
  failed: string[];
}

export interface RuntimeDeleteResponse {
  deleted: string[];
  warnings: string[];
}
