import { apiClient } from '@/shared/api/apiClient';
import { normalizeResourceAuthorization } from '@/shared/authorization/resourceAuthorization';
import type {
  KnowledgeBaseCreatePayload,
  KnowledgeBaseDetail,
  KnowledgeBaseShareCreatePayload,
  KnowledgeBaseShareListResponse,
  KnowledgeBaseShareTargetType,
  KnowledgeBaseSummary,
  KnowledgeBaseShareSummary,
  KnowledgeBaseShareUpdatePayload,
  KnowledgeBaseUpdatePayload,
  KnowledgeBaseVisibilityUpdatePayload,
  KnowledgeBaseWorkspaceUsageResponse,
} from '@/features/knowledge-base/model/knowledgeBaseTypes';
import type {
  FileConflictBatchResult,
  FileConflictExecutionRequest,
  FileConflictPreflightRequest,
  FileConflictPreflightResponse,
} from '@/shared/components/file-workbench';

interface UserShareCandidateResponse {
  items?: Array<{
    id: string;
    email: string;
    username?: string | null;
    displayName?: string | null;
  }>;
}

interface GroupShareCandidateResponse {
  items?: Array<{
    id: string;
    name: string;
  }>;
}

export interface KnowledgeBaseShareCandidate {
  id: string;
  label: string;
  description?: string;
}

type KnowledgeBaseAuthorizationResponse = Omit<
  KnowledgeBaseDetail,
  'accessRole' | 'accessSource' | 'accessSources' | 'allowedOperations'
> & {
  accessRole?: unknown;
  accessSource?: unknown;
  accessSources?: unknown;
  allowedOperations?: unknown;
};

const normalizeKnowledgeBaseAuthorizationResponse = (
  response: KnowledgeBaseAuthorizationResponse,
): KnowledgeBaseDetail => {
  const authorization = normalizeResourceAuthorization(response);
  if (!authorization) {
    throw Object.assign(new Error('KB_ACCESS_DENIED'), {
      errorCode: 'KB_ACCESS_DENIED',
    });
  }

  return {
    ...response,
    ...authorization,
  };
};

export interface KnowledgeBaseFileConflictPayload {
  files?: File[];
  sourcePath?: string;
  entryType?: 'file' | 'directory';
  content?: string;
}

interface KnowledgeBaseArchiveDownloadRequest {
  paths: string[];
  archiveName?: string;
  archiveFormat?: 'zip';
}

interface KnowledgeBaseArchiveDownloadAcceptedResponse {
  operationId: string;
  status: 'pending' | 'running';
  message: string;
  startedAt: string;
}

interface KnowledgeBaseArchiveDownloadResult {
  archiveName: string;
  size: number;
  downloadUrl: string;
  expiresAt: string;
}

interface KnowledgeBaseArchiveDownloadStatusResponse {
  operationId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'expired';
  progress: number;
  message: string;
  startedAt: string;
  completedAt?: string | null;
  error?: string | null;
  result?: KnowledgeBaseArchiveDownloadResult | null;
}

export async function listKnowledgeBases(): Promise<KnowledgeBaseSummary[]> {
  const response = await apiClient.get<{
    items?: KnowledgeBaseAuthorizationResponse[];
  }>('/knowledge-bases');
  return (response.items ?? []).flatMap((item) => {
    const authorization = normalizeResourceAuthorization(item);
    return authorization
      ? [{ ...item, ...authorization }]
      : [];
  });
}

export async function getKnowledgeBase(kbId: string): Promise<KnowledgeBaseDetail> {
  const detail = await apiClient.get<KnowledgeBaseAuthorizationResponse>(
    `/knowledge-bases/${kbId}`,
  );
  return normalizeKnowledgeBaseAuthorizationResponse(detail);
}

export async function createKnowledgeBase(payload: KnowledgeBaseCreatePayload): Promise<KnowledgeBaseDetail> {
  const created = await apiClient.post<KnowledgeBaseAuthorizationResponse>(
    '/knowledge-bases',
    payload,
  );
  return normalizeKnowledgeBaseAuthorizationResponse(created);
}

export async function updateKnowledgeBase(
  kbId: string,
  payload: KnowledgeBaseUpdatePayload,
): Promise<KnowledgeBaseDetail> {
  const updated = await apiClient.patch<KnowledgeBaseAuthorizationResponse>(
    `/knowledge-bases/${kbId}`,
    payload,
  );
  return normalizeKnowledgeBaseAuthorizationResponse(updated);
}

export async function updateKnowledgeBaseVisibility(
  kbId: string,
  payload: KnowledgeBaseVisibilityUpdatePayload,
): Promise<KnowledgeBaseDetail> {
  const updated = await apiClient.patch<KnowledgeBaseAuthorizationResponse>(
    `/knowledge-bases/${kbId}/visibility`,
    payload,
  );
  return normalizeKnowledgeBaseAuthorizationResponse(updated);
}

export async function deleteKnowledgeBase(
  kbId: string,
  confirmationName: string,
): Promise<KnowledgeBaseDetail> {
  return apiClient.delete<KnowledgeBaseDetail>(
    `/knowledge-bases/${kbId}`,
    undefined,
    { confirmationName },
  );
}

export async function startKnowledgeBaseArchiveDownload(
  kbId: string,
  request: KnowledgeBaseArchiveDownloadRequest,
): Promise<KnowledgeBaseArchiveDownloadAcceptedResponse> {
  return apiClient.post<KnowledgeBaseArchiveDownloadAcceptedResponse>(`/knowledge-bases/${kbId}/files/archive`, {
    paths: request.paths,
    archiveName: request.archiveName,
    archiveFormat: request.archiveFormat ?? 'zip',
  });
}

export async function fetchKnowledgeBaseArchiveDownloadStatus(
  kbId: string,
  operationId: string,
): Promise<KnowledgeBaseArchiveDownloadStatusResponse> {
  return apiClient.get<KnowledgeBaseArchiveDownloadStatusResponse>(
    `/knowledge-bases/${kbId}/files/archive/${encodeURIComponent(operationId)}`,
  );
}

export async function downloadKnowledgeBaseArchiveBlob(
  _kbId: string,
  downloadUrl: string,
): Promise<Blob> {
  return apiClient.getBlob(downloadUrl);
}

export async function preflightKnowledgeBaseFileConflicts(
  kbId: string,
  request: FileConflictPreflightRequest,
  options: { signal: AbortSignal },
): Promise<FileConflictPreflightResponse> {
  return apiClient.post<FileConflictPreflightResponse>(
    `/knowledge-bases/${kbId}/files/conflicts/preflight`,
    request,
    options,
  );
}

export async function executeKnowledgeBaseFileConflictOperation(
  kbId: string,
  request: FileConflictExecutionRequest<KnowledgeBaseFileConflictPayload>,
  options: { signal: AbortSignal },
): Promise<FileConflictBatchResult> {
  const path = `/knowledge-bases/${kbId}/files/${request.operation}`;
  if (request.operation === 'upload') {
    const formData = new FormData();
    formData.append('targetPath', request.targetPath);
    formData.append('defaultStrategy', request.defaultStrategy);
    formData.append('resolutions', JSON.stringify(request.resolutions));
    for (const file of request.payload.files ?? []) formData.append('files', file);
    return apiClient.post<FileConflictBatchResult>(path, formData, options);
  }
  const body = request.operation === 'paste'
    ? {
        targetPath: request.targetPath,
        sources: request.sources,
        defaultStrategy: request.defaultStrategy,
        resolutions: request.resolutions,
      }
    : {
        archivePath: request.archivePath,
        targetPath: request.targetPath,
        defaultStrategy: request.defaultStrategy,
        resolutions: request.resolutions,
      };
  return apiClient.post<FileConflictBatchResult>(path, body, options);
}

export function buildKnowledgeBaseFileDownloadUrl(kbId: string, path: string): string {
  return apiClient.buildUrl(`/knowledge-bases/${kbId}/files/download?path=${encodeURIComponent(path)}`);
}

export async function listKnowledgeBaseShares(kbId: string) {
  const response = await apiClient.get<KnowledgeBaseShareListResponse>(`/knowledge-bases/${kbId}/shares`);
  return response.items ?? [];
}

export async function searchKnowledgeBaseShareCandidates(
  kbId: string,
  targetType: KnowledgeBaseShareTargetType,
  query: string,
  limit = 8,
): Promise<KnowledgeBaseShareCandidate[]> {
  const encodedQuery = encodeURIComponent(query);

  if (targetType === 'user_group') {
    const response = await apiClient.get<GroupShareCandidateResponse>(
      `/knowledge-bases/${kbId}/share-candidate-groups?query=${encodedQuery}&limit=${limit}`,
    );
    return (response.items ?? []).map((group) => ({
      id: group.id,
      label: group.name,
    }));
  }

  const response = await apiClient.get<UserShareCandidateResponse>(
    `/users?query=${encodedQuery}&limit=${limit}`,
  );
  return (response.items ?? []).map((user) => ({
    id: user.id,
    label: user.displayName || user.username || user.email || user.id,
    description: [user.email, user.username].filter(Boolean).join(' · '),
  }));
}

export async function createKnowledgeBaseShare(
  kbId: string,
  payload: KnowledgeBaseShareCreatePayload,
): Promise<KnowledgeBaseShareSummary> {
  return apiClient.post<KnowledgeBaseShareSummary>(`/knowledge-bases/${kbId}/shares`, payload);
}

export async function updateKnowledgeBaseShare(
  kbId: string,
  shareId: string,
  payload: KnowledgeBaseShareUpdatePayload,
): Promise<KnowledgeBaseShareSummary> {
  return apiClient.patch<KnowledgeBaseShareSummary>(`/knowledge-bases/${kbId}/shares/${shareId}`, payload);
}

export async function deleteKnowledgeBaseShare(kbId: string, shareId: string): Promise<void> {
  return apiClient.delete<void>(`/knowledge-bases/${kbId}/shares/${shareId}`);
}

export async function getKnowledgeBaseWorkspaceUsage(
  kbId: string,
): Promise<KnowledgeBaseWorkspaceUsageResponse> {
  return apiClient.get<KnowledgeBaseWorkspaceUsageResponse>(
    `/knowledge-bases/${kbId}/attachments`,
  );
}
