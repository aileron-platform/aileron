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
  accessRole: KnowledgeBaseRole;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeBaseDetail extends KnowledgeBaseSummary {}

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
}
