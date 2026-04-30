export type KnowledgeBaseRole = 'owner' | 'manager' | 'editor' | 'viewer';
export type KnowledgeBaseAttachmentMode = 'rw' | 'ro';

export interface KnowledgeBaseSummary {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  ownerId: string;
  currentSizeBytes: number;
  quotaBytes?: number | null;
  versionControlEnabled?: boolean;
  gitLfsEnabled?: boolean;
  gitDefaultBranch?: string;
  gitLastCommitSha?: string | null;
  wikiInitializedAt?: string | null;
  lastIndexedAt?: string | null;
  lastIndexStatus?: string | null;
  lastIndexError?: string | null;
  accessRole: KnowledgeBaseRole;
  createdAt: string;
  updatedAt: string;
}

export type KnowledgeBaseDetail = KnowledgeBaseSummary;

export interface KnowledgeBaseShareSummary {
  id: string;
  kbId: string;
  userId: string;
  role: Exclude<KnowledgeBaseRole, 'owner'>;
  grantedById: string;
  createdAt: string;
}

export interface KnowledgeBaseShareCreatePayload {
  userId: string;
  role: Exclude<KnowledgeBaseRole, 'owner'>;
}

export interface KnowledgeBaseShareUpdatePayload {
  role: Exclude<KnowledgeBaseRole, 'owner'>;
}

export interface KnowledgeBaseAttachmentSummary {
  id: string;
  workspaceId: string;
  workspaceName: string;
  kbId: string;
  mountAlias: string;
  mode: KnowledgeBaseAttachmentMode;
  attachedById: string;
  createdAt: string;
  updatedAt?: string | null;
}

export interface WorkspaceKnowledgeBaseAttachmentSummary {
  id: string;
  kbId: string;
  name: string;
  slug: string;
  role?: KnowledgeBaseRole | null;
  mountAlias: string;
  mode: KnowledgeBaseAttachmentMode;
  attachedById: string;
  createdAt: string;
  updatedAt?: string | null;
}

export interface KnowledgeBaseAttachmentCreatePayload {
  workspaceId: string;
  mountAlias?: string;
  mode: KnowledgeBaseAttachmentMode;
}

export interface KnowledgeBaseAttachmentUpdatePayload {
  mountAlias?: string;
  mode?: KnowledgeBaseAttachmentMode;
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBaseSummary[];
}

export interface KnowledgeBaseShareListResponse {
  items: KnowledgeBaseShareSummary[];
}

export interface KnowledgeBaseAttachmentListResponse {
  items: KnowledgeBaseAttachmentSummary[];
}

export interface KnowledgeBaseCreatePayload {
  name: string;
  slug: string;
  description?: string;
  quotaBytes?: number | null;
}

export interface KnowledgeBaseUpdatePayload {
  name?: string;
  description?: string;
  quotaBytes?: number | null;
}

export interface KnowledgeBaseGitRepositoryStatus {
  isGitRepo: boolean;
  currentBranch?: string | null;
  remoteUrl?: string | null;
  hasOrigin: boolean;
  hasLocalContent: boolean;
  canCloneSafely: boolean;
  canInitSafely: boolean;
  cloneBlockedReason?: string | null;
}

export interface KnowledgeBaseGitEnablePayload {
  defaultBranch?: string;
  initialMessage?: string;
}

export interface KnowledgeBaseGitLfsEnablePayload {
  patterns?: string[];
}

export interface KnowledgeBaseVersionControlStatus {
  branch: string;
  ahead: number;
  behind: number;
  detached: boolean;
  hasConflicts: boolean;
  stagedCount: number;
  unstagedCount: number;
  untrackedCount: number;
  lastFetchedAt?: string | null;
}

export interface KnowledgeBaseGraphNode {
  id: string;
  label: string;
  type: string;
  path: string;
  sources: string[];
  outboundCount: number;
  inboundCount: number;
  degree: number;
  metadata?: Record<string, unknown>;
}

export interface KnowledgeBaseGraphEdgeReason {
  type: 'direct_wikilink' | 'source_overlap' | 'common_neighbor' | 'type_affinity' | string;
  weight: number;
  details?: Record<string, unknown>;
}

export interface KnowledgeBaseGraphEdge {
  id: string;
  source: string;
  target: string;
  weight: number;
  reasons: KnowledgeBaseGraphEdgeReason[];
}

export interface KnowledgeBaseGraphResponse {
  kbId: string;
  generatedAt: string;
  nodes: KnowledgeBaseGraphNode[];
  edges: KnowledgeBaseGraphEdge[];
}
