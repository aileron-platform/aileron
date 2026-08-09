export type PlatformResourceKind = 'workspaces' | 'knowledge-bases';
export type PlatformResourceRange = '7d' | '30d' | '90d';
export type PlatformResourceStorageKind = 'workspace_data' | 'runtime_home' | 'knowledge_base';
export type PlatformResourceCapacityRisk = 'normal' | 'warning' | 'critical' | 'unknown' | 'stale';

export interface PlatformResourceOwner {
  id: string;
  username: string;
  displayName: string | null;
  avatarUrl: string | null;
}

export interface PlatformWorkspaceSummary {
  id: string;
  name: string;
  owner: PlatformResourceOwner;
  runtimeStatus: string | null;
  workspaceData: PlatformResourceCapacitySnapshot | null;
  runtimeHome: PlatformResourceCapacitySnapshot | null;
  capacityRisk: PlatformResourceCapacityRisk;
  provisioner: 'docker' | 'kubernetes';
}

export interface PlatformKnowledgeBaseSummary {
  id: string;
  name: string;
  owner: PlatformResourceOwner;
  visibility: 'private' | 'public';
  currentSizeBytes: number;
  quotaBytes: number | null;
  effectiveQuotaBytes: number;
  quotaSource: 'custom' | 'platform_default';
  utilizationPercent: number;
  capacityRisk: PlatformResourceCapacityRisk;
  indexingHealth: 'success' | 'processing' | 'failure' | 'never_indexed';
}

export interface PlatformResourceCapacitySnapshot {
  usedBytes: number | null;
  allocatedBytes: number | null;
  hostAvailableBytes?: number | null;
  utilizationPercent: number | null;
  risk: PlatformResourceCapacityRisk;
  measuredAt: string | null;
  expansionSupported?: boolean;
}

export type PlatformResourceSummary =
  | PlatformWorkspaceSummary
  | PlatformKnowledgeBaseSummary;

export interface PlatformResourcePage<T extends PlatformResourceSummary> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
}

export interface PlatformResourceListQuery {
  q: string;
  page: number;
  pageSize: number;
  health?: string;
  visibility?: string;
  indexingHealth?: string;
  capacityRisk?: PlatformResourceCapacityRisk;
  sort?: 'name' | 'created_at' | 'used_bytes' | 'utilization';
  order?: 'asc' | 'desc';
}

export interface PlatformResourceMetric {
  value: number;
  previousValue: number | null;
  changePercent: number | null;
}

export interface PlatformResourceStatisticsMetadata {
  range: PlatformResourceRange;
  timeZone: string;
  calculatedAt: string;
  collectionStartedAt: string | null;
  isStale: boolean;
  refreshInProgress?: boolean;
}

export interface PlatformResourceStatisticsSummary extends PlatformResourceStatisticsMetadata {
  metrics: {
    total: PlatformResourceMetric;
    active: PlatformResourceMetric;
    usedBytes: PlatformResourceMetric;
    nearLimit: PlatformResourceMetric;
  };
  distributions: Array<{ key: string; count: number }>;
}

export interface PlatformResourceTrendPoint {
  date: string;
  total: number;
  created: number;
  active: number;
  deleted: number;
}

export interface PlatformResourceTrend extends PlatformResourceStatisticsMetadata {
  points: PlatformResourceTrendPoint[];
}

export interface PlatformResourceCapacityTrendPoint {
  date: string;
  usedBytes: number;
  allocatedBytes: number | null;
  unknownCount: number;
  staleCount: number;
}

export interface PlatformResourceCapacityTrend extends PlatformResourceStatisticsMetadata {
  points: PlatformResourceCapacityTrendPoint[];
}

export interface WorkspaceCapacityExpansionRequest {
  storageKind: Extract<PlatformResourceStorageKind, 'workspace_data' | 'runtime_home'>;
  requestedBytes: number;
}

export interface WorkspaceCapacityExpansionResponse {
  requestId: string;
  workspaceId: string;
  phase: 'pending' | 'applying' | 'completed' | 'failed';
  storageKind: WorkspaceCapacityExpansionRequest['storageKind'];
  previousBytes: number;
  requestedBytes: number;
  errorCode?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeBaseQuotaResponse {
  knowledgeBaseId: string;
  currentSizeBytes: number;
  quotaBytes: number | null;
  effectiveQuotaBytes: number;
  quotaSource: 'custom' | 'platform_default';
}

export interface PlatformResourceOwnerCandidate {
  id: string;
  username: string;
  displayName: string;
}

export interface PlatformResourceOwnerReassignment {
  targetUserId: string;
  reason: string;
}
