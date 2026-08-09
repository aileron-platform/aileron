import type { OperationId } from '@/shared/authorization/operationIds';
import type { ResourceAccessRole } from '@/shared/authorization/resourceAccessRole';
import type { ResourceAccessSource } from '@/shared/authorization/resourceAuthorization';

export type KnowledgeBaseShareTargetType = 'user' | 'user_group';
export type KnowledgeBaseVisibility = 'private' | 'public';
export type KnowledgeBaseAttachmentStatus = 'active' | 'pending' | 'pending_removal';

export interface KnowledgeBaseSummary {
  id: string;
  slug: string;
  name: string;
  description?: string | null;
  ownerId: string;
  currentSizeBytes: number;
  quotaBytes: number | null;
  effectiveQuotaBytes: number;
  quotaSource: 'custom' | 'platform_default';
  utilizationPercent: number | null;
  ownerQuotaUsedBytes: number;
  ownerEffectiveQuotaBytes: number;
  versionControlEnabled?: boolean;
  gitLfsEnabled?: boolean;
  gitDefaultBranch?: string;
  gitLastCommitSha?: string | null;
  lastIndexedAt?: string | null;
  lastIndexStatus?: string | null;
  lastIndexError?: string | null;
  accessRole: ResourceAccessRole;
  accessSource: ResourceAccessSource;
  accessSources: ResourceAccessSource[];
  visibility: KnowledgeBaseVisibility;
  allowedOperations: OperationId[];
  createdAt: string;
  updatedAt: string;
}

export type KnowledgeBaseDetail = KnowledgeBaseSummary;

export interface KnowledgeBaseShareSummary {
  id: string;
  kbId: string;
  targetType: KnowledgeBaseShareTargetType;
  targetId: string;
  targetLabel: string;
  role: Exclude<ResourceAccessRole, 'owner'>;
  grantedById: string;
  createdAt: string;
}

export interface KnowledgeBaseShareCreatePayload {
  targetType: KnowledgeBaseShareTargetType;
  targetId: string;
  role: Exclude<ResourceAccessRole, 'owner'>;
}

export interface KnowledgeBaseShareUpdatePayload {
  role: Exclude<ResourceAccessRole, 'owner'>;
}

export interface KnowledgeBaseWorkspaceUsageItem {
  attachmentId: string;
  workspaceId: string;
  workspaceName: string;
  mountAlias: string;
  attachmentStatus: KnowledgeBaseAttachmentStatus;
}

export interface KnowledgeBaseWorkspaceUsageResponse {
  visibleItems: KnowledgeBaseWorkspaceUsageItem[];
  hiddenWorkspaceCount: number;
  attachmentCount: number;
}

export interface KnowledgeBaseListResponse {
  items: KnowledgeBaseSummary[];
}

export interface KnowledgeBaseShareListResponse {
  items: KnowledgeBaseShareSummary[];
}

export interface KnowledgeBaseCreatePayload {
  name: string;
  slug: string;
  description?: string;
}

export interface KnowledgeBaseUpdatePayload {
  name?: string;
  description?: string;
}

export interface KnowledgeBaseVisibilityUpdatePayload {
  visibility: KnowledgeBaseVisibility;
}
