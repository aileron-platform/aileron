/**
 * Workspace Runtime API service.
 */

import { ApiClient, apiClient } from '@/shared/api/apiClient';
import { buildWorkspaceGatewayPath } from '@/shared/utils/workspaceGateway';
import { executionGrantBroker } from '@/features/auth/public';
import type {
  WorkspaceDetailResponse,
  RuntimeFileContentResponse,
  RuntimeSaveFileResponse,
  RuntimeBatchDeleteResponse,
  RuntimeDeleteResponse,
} from './workspaceApiTypes';
import type { WorkspaceListResponse } from '../model/workspaceTypes';
import type {
  FileConflictBatchResult,
  FileConflictExecutionRequest,
  FileConflictPreflightRequest,
  FileConflictPreflightResponse,
} from '@/shared/components/file-workbench';

export interface RuntimeFileConflictPayload {
  files?: File[];
  contextId?: string | null;
  sourcePath?: string;
  entryType?: 'file' | 'directory';
  content?: string;
}

export interface RuntimeArchiveDownloadPayload {
  paths: string[];
  archiveName?: string;
  archiveFormat?: 'zip';
  contextId?: string | null;
}

export interface RuntimeArchiveDownloadAcceptedResponse {
  operationId: string;
  status: 'pending' | 'running';
  message: string;
  startedAt: string;
}

export interface RuntimeArchiveDownloadResult {
  archiveName: string;
  size: number;
  downloadUrl: string;
  expiresAt: string;
}

export interface RuntimeArchiveDownloadStatusResponse {
  operationId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'expired';
  progress: number;
  message: string;
  startedAt: string;
  completedAt?: string | null;
  error?: string | null;
  result?: RuntimeArchiveDownloadResult | null;
}

/**
 * Build a Runtime URL.
 */
export const buildRuntimeUrl = (base: string, path: string): string => {
  const normalizedBase = base.endsWith('/') ? base : `${base}/`;
  const normalizedPath = path.startsWith('/') ? path.slice(1) : path;
  const fullPath = `api/v1/${normalizedPath}`;
  if (normalizedBase.startsWith('/')) {
    return `${normalizedBase}${fullPath}`;
  }
  return new URL(fullPath, normalizedBase).toString();
};

/**
 * Create a Runtime API client.
 */
const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({
    baseUrl: runtimeBaseUrl,
    unauthorizedBehavior: 'propagate',
    executionAudience: 'workspace-runtime',
  });
};

const buildChildPath = (parentPath: string, name: string): string => {
  const normalizedParent = parentPath === '/' ? '' : parentPath.replace(/\/+$/, '');
  return `${normalizedParent}/${name}`.replace(/\/{2,}/g, '/');
};

const appendContextId = (params: URLSearchParams, contextId?: string | null): void => {
  if (contextId) {
    params.set('contextId', contextId);
  }
};

const withContextId = (path: string, contextId?: string | null): string => {
  if (!contextId) {
    return path;
  }
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}contextId=${encodeURIComponent(contextId)}`;
};

/**
 * Fetch the default workspace ID.
 */
export const fetchDefaultWorkspaceId = async (): Promise<string> => {
  const data = await apiClient.get<WorkspaceListResponse>('/workspaces?page=1&pageSize=1');
  const firstWorkspace = data.items?.[0];
  if (!firstWorkspace?.id) {
    throw new Error('No workspace has been created');
  }
  return firstWorkspace.id;
};

/**
 * Fetch workspace detail.
 */
export const fetchWorkspaceDetail = async (workspaceId: string): Promise<WorkspaceDetailResponse> => {
  return await apiClient.get<WorkspaceDetailResponse>(`/workspaces/${workspaceId}`);
};

/**
 * Resolve Runtime base URL and workspace detail in one API call.
 */
export const resolveRuntimeBaseUrlWithDetail = async (
  workspaceId: string,
): Promise<{ url: string | null; detail: WorkspaceDetailResponse | null }> => {
  if (!workspaceId) {
    throw new Error('workspaceId is required');
  }

  const detail = await apiClient.get<WorkspaceDetailResponse>(
    `/workspaces/${encodeURIComponent(workspaceId)}`,
  );
  const status = detail.runtimeStatus.status;
  if (status !== 'running' && status !== 'ready') {
    return { url: null, detail };
  }

  const runtimeUrl = detail.runtimeStatus.runtimeUrl;
  executionGrantBroker.registerTarget(runtimeUrl, workspaceId);
  executionGrantBroker.registerTarget(
    buildWorkspaceGatewayPath(workspaceId, 'runtime', '/ws/terminal'),
    workspaceId,
  );
  return { url: runtimeUrl, detail };
};

/**
 * Read file content.
 */
export const fetchFileContent = async (
  runtimeBaseUrl: string,
  filePath: string,
  contextId?: string | null
): Promise<RuntimeFileContentResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const params = new URLSearchParams();
  params.set('path', filePath);
  appendContextId(params, contextId);

  return await client.get(`/api/v1/files/content?${params.toString()}`);
};

/**
 * Save file content.
 */
export const saveFileContent = async (
  runtimeBaseUrl: string,
  filePath: string,
  content: string,
  contextId?: string | null,
  revision?: string | null,
): Promise<RuntimeSaveFileResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const body: { path: string; content: string; revision?: string } = { path: filePath, content };
  if (revision != null) {
    body.revision = revision;
  }
  return await client.put(withContextId('/api/v1/files/content', contextId), body);
};

/**
 * Create a file or folder.
 */
export const createFileOrFolder = async (
  runtimeBaseUrl: string,
  name: string,
  parentPath: string,
  type: 'file' | 'directory',
  content?: string,
  contextId?: string | null
): Promise<void> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  await client.post(withContextId('/api/v1/files', contextId), {
    path: buildChildPath(parentPath, name),
    type,
    content: type === 'directory' ? undefined : content ?? '',
  });
};

/**
 * Rename a file.
 */
export const renameFile = async (
  runtimeBaseUrl: string,
  oldPath: string,
  newPath: string,
  contextId?: string | null
): Promise<void> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  await client.post(withContextId('/api/v1/files/move', contextId), {
    sourcePath: oldPath,
    destPath: newPath,
  });
};

/**
 * Delete a file.
 */
export const deleteFile = async (
  runtimeBaseUrl: string,
  path: string,
  recursive?: boolean,
  contextId?: string | null
): Promise<RuntimeDeleteResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const params = new URLSearchParams();
  params.set('path', path);
  if (recursive) {
    params.set('recursive', 'true');
  }
  appendContextId(params, contextId);

  return await client.delete(`/api/v1/files?${params.toString()}`);
};

/**
 * Delete files in a batch.
 */
export const batchDeleteFiles = async (
  runtimeBaseUrl: string,
  paths: string[],
  recursive?: boolean,
  contextId?: string | null
): Promise<RuntimeBatchDeleteResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(withContextId('/api/v1/files/batch-delete', contextId), { paths, recursive: recursive ?? true });
};

/**
 * Move a file or folder.
 */
export const moveFile = async (
  runtimeBaseUrl: string,
  oldPath: string,
  newPath: string,
  contextId?: string | null
): Promise<void> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  await client.post(withContextId('/api/v1/files/move', contextId), {
    sourcePath: oldPath,
    destPath: newPath,
  });
};

export const preflightRuntimeFileConflicts = async (
  runtimeBaseUrl: string,
  request: FileConflictPreflightRequest,
  options: { signal: AbortSignal; contextId?: string | null },
): Promise<FileConflictPreflightResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return client.post<FileConflictPreflightResponse>(
    withContextId('/api/v1/files/conflicts/preflight', options.contextId),
    request,
    { signal: options.signal },
  );
};

export const executeRuntimeFileConflictOperation = async (
  runtimeBaseUrl: string,
  request: FileConflictExecutionRequest<RuntimeFileConflictPayload>,
  options: { signal: AbortSignal },
): Promise<FileConflictBatchResult> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const path = withContextId(`/api/v1/files/${request.operation}`, request.payload.contextId);
  if (request.operation === 'upload') {
    const formData = new FormData();
    formData.append('targetPath', request.targetPath);
    formData.append('defaultStrategy', request.defaultStrategy);
    formData.append('resolutions', JSON.stringify(request.resolutions));
    for (const file of request.payload.files ?? []) formData.append('files', file);
    return client.post<FileConflictBatchResult>(path, formData, { signal: options.signal });
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
  return client.post<FileConflictBatchResult>(path, body, { signal: options.signal });
};

/**
 * Download a single file.
 */
export const downloadFile = async (
  runtimeBaseUrl: string,
  filePath: string,
  contextId?: string | null,
): Promise<string> => {
  const params = new URLSearchParams();
  params.set('path', filePath);
  if (contextId) {
    params.set('contextId', contextId);
  }

  return `${buildRuntimeUrl(runtimeBaseUrl, 'files/download')}?${params.toString()}`;
};

export const startArchiveDownload = async (
  runtimeBaseUrl: string,
  request: RuntimeArchiveDownloadPayload
): Promise<RuntimeArchiveDownloadAcceptedResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(withContextId('/api/v1/files/archive', request.contextId), {
    paths: request.paths,
    archiveName: request.archiveName,
    archiveFormat: request.archiveFormat ?? 'zip',
  });
};

export const fetchArchiveDownloadStatus = async (
  runtimeBaseUrl: string,
  operationId: string
): Promise<RuntimeArchiveDownloadStatusResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/files/archive/${encodeURIComponent(operationId)}`);
};

export const buildArchiveDownloadUrl = (
  runtimeBaseUrl: string,
  downloadUrl: string
): string => {
  if (downloadUrl.startsWith('http')) {
    return downloadUrl;
  }
  return buildRuntimeUrl(runtimeBaseUrl, downloadUrl.replace(/^\/api\/v1\//, ''));
};

const normalizeArchiveDownloadPath = (downloadUrl: string): string => {
  if (!downloadUrl) {
    return '/api/v1/files/archive';
  }
  if (downloadUrl.startsWith('http')) {
    const parsed = new URL(downloadUrl);
    return `${parsed.pathname}${parsed.search}`;
  }
  return downloadUrl.startsWith('/') ? downloadUrl : `/${downloadUrl}`;
};

export const downloadArchiveBlob = async (
  runtimeBaseUrl: string,
  downloadUrl: string
): Promise<Blob> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.getBlob(normalizeArchiveDownloadPath(downloadUrl));
};

export type CanvasType = 'active' | 'default';
export type CanvasKind = 'static' | 'nextjs';
export type CanvasManifestStatus = 'missing' | 'valid' | 'invalid';
export type CanvasRuntimeStatus = 'healthy' | 'starting' | 'unhealthy';
export interface CanvasOwner {
  skillName?: string | null;
}

export interface CanvasRoute {
  path: string;
  label?: string | null;
}

export interface CanvasRoutesResponse {
  workspaceId: string;
  type: CanvasType;
  kind?: CanvasKind | null;
  title?: string | null;
  owner?: CanvasOwner | null;
  manifestStatus: CanvasManifestStatus;
  runtimeStatus?: CanvasRuntimeStatus | null;
  defaultPath: string;
  routes: CanvasRoute[];
  total: number;
  scannedAt: string;
}

export interface CanvasDetectResponse {
  workspaceId: string;
  type: CanvasType;
  kind?: CanvasKind | null;
  title?: string | null;
  owner?: CanvasOwner | null;
  manifestStatus: CanvasManifestStatus;
  runtimeStatus?: CanvasRuntimeStatus | null;
  defaultPath: string;
  routes: CanvasRoute[];
  error?: string | null;
  detectedAt: string;
}

export interface CanvasHealthResponse {
  workspaceId: string;
  status: 'healthy' | 'unhealthy' | 'standby' | 'starting' | 'checking' | string;
  type?: CanvasType | null;
  kind?: CanvasKind | null;
  manifestStatus?: CanvasManifestStatus | null;
  runtimeStatus?: CanvasRuntimeStatus | null;
  rendererRunning: boolean;
  portAvailable: boolean;
  message: string;
  source?: string | null;
}

export interface CanvasActionResponse {
  workspaceId: string;
  status: string;
  type?: CanvasType | null;
  kind?: CanvasKind | null;
  manifestStatus?: CanvasManifestStatus | null;
  runtimeStatus?: CanvasRuntimeStatus | null;
  message: string;
  syncedAt?: string | null;
  resetAt?: string | null;
  rendererAction?: 'reused' | 'restarted' | string | null;
  rendererActionReason?: string | null;
}

export interface CanvasLogsResponse {
  workspaceId: string;
  logs: string[];
  rendererLogs: string[];
  total: number;
}

export type CanvasReviewStatus = 'open' | 'seen' | 'applied' | 'dismissed';
export type CanvasReviewCoordinateSpace = 'viewport' | 'document';
export type CanvasReviewSelectorKind = 'data-canvas-id' | 'id' | 'css' | 'xpath';

export interface CanvasReviewRect {
  x: number;
  y: number;
  width: number;
  height: number;
  coordinateSpace: CanvasReviewCoordinateSpace;
}

export interface CanvasReviewElementTarget {
  type: 'element';
  selector: string;
  selectorKind: CanvasReviewSelectorKind;
  tagName: string;
  textPreview: string;
  htmlPreview: string;
  parentHtmlPreview: string;
  rect: CanvasReviewRect;
  documentRect?: CanvasReviewRect | null;
}

export interface CanvasReviewMultiElementTarget {
  type: 'multi-element';
  elements: CanvasReviewElementTarget[];
  rect: CanvasReviewRect;
  documentRect?: CanvasReviewRect | null;
}

export interface CanvasReviewAreaTarget {
  type: 'area';
  rect: CanvasReviewRect;
  documentRect?: CanvasReviewRect | null;
}

export type CanvasReviewTarget =
  | CanvasReviewElementTarget
  | CanvasReviewMultiElementTarget
  | CanvasReviewAreaTarget;

export interface CanvasReviewReply {
  id: string;
  role: 'user' | 'agent';
  content: string;
  createdAt: string;
}

export interface CanvasReviewNote {
  id: string;
  workspaceId: string;
  sessionId?: string | null;
  routePath: string;
  canvasUrl: string;
  target: CanvasReviewTarget;
  instruction: string;
  status: CanvasReviewStatus;
  replies: CanvasReviewReply[];
  createdAt: string;
  updatedAt: string;
  resolvedAt?: string | null;
}

export interface CanvasReviewNotesResponse {
  workspaceId: string;
  notes: CanvasReviewNote[];
  total: number;
}

export interface CanvasReviewNoteCreatePayload {
  sessionId?: string | null;
  routePath: string;
  canvasUrl: string;
  target: CanvasReviewTarget;
  instruction: string;
  status?: CanvasReviewStatus;
}

export const fetchCanvasRoutes = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<CanvasRoutesResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/workspaces/${workspaceId}/canvas/routes`);
};

export const syncCanvas = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<CanvasActionResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(`/api/v1/workspaces/${workspaceId}/canvas/sync`);
};

export const checkCanvasHealth = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<CanvasHealthResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/workspaces/${workspaceId}/canvas/health`);
};

export const fetchCanvasReviewNotes = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  filters?: { status?: CanvasReviewStatus; routePath?: string }
): Promise<CanvasReviewNotesResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const params = new URLSearchParams();
  if (filters?.status) params.set('status', filters.status);
  if (filters?.routePath) params.set('routePath', filters.routePath);
  const suffix = params.toString() ? `?${params.toString()}` : '';
  return await client.get(`/api/v1/workspaces/${workspaceId}/canvas/review-notes${suffix}`);
};

export const createCanvasReviewNote = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  request: CanvasReviewNoteCreatePayload
): Promise<CanvasReviewNote> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(`/api/v1/workspaces/${workspaceId}/canvas/review-notes`, request);
};

export const updateCanvasReviewNoteStatus = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  noteId: string,
  status: CanvasReviewStatus
): Promise<CanvasReviewNote> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.patch(`/api/v1/workspaces/${workspaceId}/canvas/review-notes/${noteId}/status`, { status });
};

export const deleteCanvasReviewNote = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  noteId: string
): Promise<void> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  await client.delete(`/api/v1/workspaces/${workspaceId}/canvas/review-notes/${noteId}`);
};
