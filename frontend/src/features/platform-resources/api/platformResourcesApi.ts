import { apiClient } from '@/shared/api/apiClient';
import type {
  KnowledgeBaseQuotaResponse,
  PlatformKnowledgeBaseSummary,
  PlatformResourceKind,
  PlatformResourceListQuery,
  PlatformResourceCapacityTrend,
  PlatformResourceOwnerCandidate,
  PlatformResourceOwnerReassignment,
  PlatformResourcePage,
  PlatformResourceSummary,
  PlatformResourceRange,
  PlatformResourceStatisticsSummary,
  PlatformResourceTrend,
  PlatformWorkspaceSummary,
  WorkspaceCapacityExpansionRequest,
  WorkspaceCapacityExpansionResponse,
} from '../model/platformResourceTypes';

interface UserCandidateResponse {
  items?: Array<{
    id: string;
    username?: string | null;
    displayName?: string | null;
  }>;
}

const getWithSignal = <T>(path: string, signal?: AbortSignal): Promise<T> => (
  signal ? apiClient.get<T>(path, { signal }) : apiClient.get<T>(path)
);

const buildListQuery = (query: PlatformResourceListQuery): string => {
  const params = [
    `q=${encodeURIComponent(query.q)}`,
    `page=${query.page}`,
    `pageSize=${query.pageSize}`,
  ];
  const optionalEntries = {
    health: query.health,
    visibility: query.visibility,
    indexingHealth: query.indexingHealth,
    capacityRisk: query.capacityRisk,
    sort: query.sort,
    order: query.order,
  };
  Object.entries(optionalEntries).forEach(([key, value]) => {
    if (value) params.push(`${key}=${encodeURIComponent(value)}`);
  });
  return params.join('&');
};

const statisticsPath = (
  kind: PlatformResourceKind,
  metric: 'summary' | 'resource-trend' | 'capacity-trend',
  range: PlatformResourceRange,
  refresh: boolean,
): string => (
  `/platform-resources/${kind}/statistics/${metric}?range=${range}&refresh=${String(refresh)}`
);

export const getPlatformResourceSummary = (
  kind: PlatformResourceKind,
  range: PlatformResourceRange,
  refresh = false,
  signal?: AbortSignal,
): Promise<PlatformResourceStatisticsSummary> => (
  getWithSignal(statisticsPath(kind, 'summary', range, refresh), signal)
);

export const getPlatformResourceResourceTrend = (
  kind: PlatformResourceKind,
  range: PlatformResourceRange,
  refresh = false,
  signal?: AbortSignal,
): Promise<PlatformResourceTrend> => (
  getWithSignal(statisticsPath(kind, 'resource-trend', range, refresh), signal)
);

export const getPlatformResourceCapacityTrend = (
  kind: PlatformResourceKind,
  range: PlatformResourceRange,
  refresh = false,
  signal?: AbortSignal,
): Promise<PlatformResourceCapacityTrend> => (
  getWithSignal(statisticsPath(kind, 'capacity-trend', range, refresh), signal)
);

export const listPlatformWorkspaces = (
  query: PlatformResourceListQuery,
  signal?: AbortSignal,
): Promise<PlatformResourcePage<PlatformWorkspaceSummary>> => (
  getWithSignal(`/platform-resources/workspaces?${buildListQuery(query)}`, signal)
);

export const listPlatformKnowledgeBases = (
  query: PlatformResourceListQuery,
  signal?: AbortSignal,
): Promise<PlatformResourcePage<PlatformKnowledgeBaseSummary>> => (
  getWithSignal(`/platform-resources/knowledge-bases?${buildListQuery(query)}`, signal)
);

export const searchPlatformResourceOwnerCandidates = async (
  query: string,
  signal?: AbortSignal,
): Promise<PlatformResourceOwnerCandidate[]> => {
  const response = await getWithSignal<UserCandidateResponse>(
    `/users?query=${encodeURIComponent(query)}&limit=8`,
    signal,
  );
  return (response.items ?? []).map(candidate => ({
    id: candidate.id,
    username: candidate.username ?? '',
    displayName: candidate.displayName ?? candidate.username ?? candidate.id,
  }));
};

export const reassignPlatformResourceOwner = (
  kind: PlatformResourceKind,
  resourceId: string,
  payload: PlatformResourceOwnerReassignment,
): Promise<PlatformResourceSummary> => (
  apiClient.post(
    `/platform-resources/${kind}/${encodeURIComponent(resourceId)}/owner-reassignment`,
    payload,
  )
);

export const updatePlatformKnowledgeBaseQuota = (
  knowledgeBaseId: string,
  quotaBytes: number | null,
): Promise<KnowledgeBaseQuotaResponse> => (
  apiClient.put(
    `/platform-resources/knowledge-bases/${encodeURIComponent(knowledgeBaseId)}/quota`,
    { quotaBytes },
  )
);

export const requestWorkspaceCapacityExpansion = (
  workspaceId: string,
  payload: WorkspaceCapacityExpansionRequest,
): Promise<WorkspaceCapacityExpansionResponse> => (
  apiClient.post(
    `/platform-resources/workspaces/${encodeURIComponent(workspaceId)}/capacity-expansions`,
    payload,
  )
);

export const getWorkspaceCapacityExpansion = (
  workspaceId: string,
  requestId: string,
  signal?: AbortSignal,
): Promise<WorkspaceCapacityExpansionResponse> => (
  getWithSignal(
    `/platform-resources/workspaces/${encodeURIComponent(workspaceId)}/capacity-expansions/${encodeURIComponent(requestId)}`,
    signal,
  )
);
