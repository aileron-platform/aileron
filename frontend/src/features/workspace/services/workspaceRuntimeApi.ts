/**
 * Workspace Runtime API service.
 */

import { ApiClient, apiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';
import { resolvePreferredWorkspaceUrl } from './workspacePublicUrl';

const logger = createLogger('workspaceRuntimeApi');
import type {
  WorkspaceListResponse,
  WorkspaceDetailResponse,
  RuntimeFileTreeResponse,
  RuntimeFileContentResponse,
  RuntimeDuplicateResponse,
  RuntimeSaveFileResponse,
  RuntimeBatchDeleteResponse,
  RuntimeDeleteResponse,
  RuntimeFileTreeNode,
} from '../providers/workspaceState.types';
import type { FileNode } from '../features/file-management/types';

export interface RuntimeUploadItem {
  path: string;
  size: number;
  lastModified: string;
  type?: 'file' | 'directory';
}

export interface RuntimeUploadResponse {
  uploaded: RuntimeUploadItem[];
  extracted: RuntimeUploadItem[];
  skipped: string[];
}

export interface RuntimeUploadOptions {
  archiveAction?: 'store' | 'extract';
  keepArchive?: boolean;
  conflictStrategy?: 'rename' | 'overwrite' | 'reject';
  contextId?: string | null;
}

export interface RuntimeUploadSummary extends RuntimeUploadResponse {
  uploadedPaths: string[];
  extractedPaths: string[];
  affectedPaths: string[];
}

export interface RuntimeExtractArchiveRequest {
  archivePath: string;
  targetPath?: string;
  conflictStrategy?: 'rename' | 'overwrite' | 'reject';
  contextId?: string | null;
}

export interface RuntimeExtractArchiveAcceptedResponse {
  operationId: string;
  status: 'pending' | 'running';
  message: string;
  startedAt: string;
}

export interface RuntimeExtractArchiveResult {
  extracted: RuntimeUploadItem[];
  extractedPaths: string[];
}

export interface RuntimeExtractArchiveStatusResponse {
  operationId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  startedAt: string;
  completedAt?: string | null;
  error?: string | null;
  result?: RuntimeExtractArchiveResult | null;
}

export interface RuntimeArchiveDownloadRequest {
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
 * Map Runtime nodes to FileNode.
 */
export const mapRuntimeNodeToFileNode = (node: RuntimeFileTreeNode, parentDepth: number = -1): FileNode => {
  const actualDepth = parentDepth + 1;
  return {
    id: node.path,
    name: node.name,
    path: node.path,
    type: node.type,
    size: node.size,
    lastModified: node.lastModified,
    depth: actualDepth,
    hasChildren: node.hasChildren ?? (node.children && node.children.length > 0),
    children: node.children?.map(child => mapRuntimeNodeToFileNode(child, actualDepth)) ?? [],
    isExpanded: false,
    isLoading: false,
  };
};

/**
 * Build a Runtime URL.
 */
export const buildRuntimeUrl = (base: string, path: string): string => {
  const normalizedBase = base.endsWith('/') ? base : `${base}/`;
  const normalizedPath = path.startsWith('/') ? path.slice(1) : path;
  const fullPath = `api/v1/${normalizedPath}`;
  return new URL(fullPath, normalizedBase).toString();
};

/**
 * Create a Runtime API client.
 */
const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

/**
 * Parse an error response.
 */
export const parseErrorResponse = async (
  response: Response
): Promise<{ message: string; errorCode?: string }> => {
  try {
    const payload = await response.json();
    if (payload?.detail) {
      if (typeof payload.detail === 'string') {
        return { message: payload.detail };
      }
      if (payload.detail?.message) {
        return { message: payload.detail.message, errorCode: payload.detail.errorCode };
      }
      if (payload.detail?.errorCode) {
        return { message: payload.detail.errorCode, errorCode: payload.detail.errorCode };
      }
    }
    if (payload?.message) {
      return { message: payload.message };
    }
  } catch (error) {
    logger.warn('Failed to parse error response', { error });
  }
  return { message: `${response.status} ${response.statusText}` };
};

/**
 * Normalize upload filenames consistently with Runtime.
 */
const sanitizeUploadPathSegment = (filename: string): string => {
  if (!filename) {
    return '';
  }
  const trimmed = filename.trim().replace(/^['"]+|['"]+$/g, '').trim();
  const normalized = trimmed.replace(/\\/g, '/').split('/').pop() ?? '';
  return normalized.replace(/\s+/g, '_');
};

const buildChildPath = (parentPath: string, name: string): string => {
  const normalizedParent = parentPath === '/' ? '' : parentPath.replace(/\/+$/, '');
  return `${normalizedParent}/${name}`.replace(/\/{2,}/g, '/');
};

const getBaseName = (path: string): string => {
  return path.split('/').filter(Boolean).pop() ?? path;
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
  const data = await apiClient.get<WorkspaceListResponse>('/workspaces/?page=1&pageSize=1');
  const firstWorkspace = data.items?.[0];
  if (!firstWorkspace?.id) {
    throw new Error('No workspace has been created');
  }
  return firstWorkspace.id;
};

export const fetchWorkspaceList = async (pageSize: number = 50): Promise<WorkspaceListResponse> => {
  return await apiClient.get<WorkspaceListResponse>(`/workspaces/?page=1&pageSize=${pageSize}`);
};

/**
 * Resolve the Runtime base URL.
 */
export const resolveRuntimeBaseUrl = async (
  workspaceId: string,
  cache: Map<string, string>
): Promise<string> => {
  if (!workspaceId) {
    throw new Error('workspaceId is required');
  }

  const cached = cache.get(workspaceId);
  if (cached) {
    return cached;
  }

  const detail = await apiClient.get<WorkspaceDetailResponse>(`/workspaces/${encodeURIComponent(workspaceId)}`);
  const runtimeUrl = resolvePreferredWorkspaceUrl(
    detail.runtimeStatus?.externalUrl,
    detail.runtimeStatus?.internalUrl
  );
  if (!runtimeUrl) {
    throw new Error('Workspace Runtime is not started or has no URL');
  }
  cache.set(workspaceId, runtimeUrl);
  return runtimeUrl;
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
  cache: Map<string, string>
): Promise<{ url: string; detail: WorkspaceDetailResponse | null }> => {
  if (!workspaceId) {
    throw new Error('workspaceId is required');
  }

  let detail: WorkspaceDetailResponse | null = null;
  let runtimeUrl: string | undefined;

  try {
    detail = await apiClient.get<WorkspaceDetailResponse>(`/workspaces/${encodeURIComponent(workspaceId)}`);
    runtimeUrl = resolvePreferredWorkspaceUrl(
      detail.runtimeStatus?.externalUrl,
      detail.runtimeStatus?.internalUrl
    );
  } catch (error) {
    const cached = cache.get(workspaceId);
    if (cached) {
      logger.error('Failed to fetch workspace detail, using cached URL and defaults', { error, workspaceId });
      return { url: cached, detail: null };
    }
    throw error;
  }

  if (!runtimeUrl) {
    throw new Error('Workspace Runtime is not started or has no URL');
  }

  cache.set(workspaceId, runtimeUrl);
  return { url: runtimeUrl, detail };
};

/**
 * Load the file tree. Runtime applies FILE_TREE_MAX_DEPTH when maxDepth is omitted.
 */
export const fetchFileTree = async (
  runtimeBaseUrl: string,
  path: string = '/',
  options?: { includeHidden?: boolean; contextId?: string | null }
): Promise<FileNode[]> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const params = new URLSearchParams();
  params.set('path', path);
  params.set('includeHidden', String(options?.includeHidden ?? false));
  appendContextId(params, options?.contextId);

  const data: RuntimeFileTreeResponse = await client.get(`/api/v1/files/tree?${params.toString()}`);
  return data.nodes?.map(node => mapRuntimeNodeToFileNode(node)) ?? [];
};

/**
 * Load child nodes. Runtime applies FILE_TREE_MAX_DEPTH when maxDepth is omitted.
 */
export const fetchNodeChildren = async (
  runtimeBaseUrl: string,
  nodePath: string,
  parentDepth: number,
  options?: { includeHidden?: boolean; contextId?: string | null }
): Promise<FileNode[]> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const params = new URLSearchParams();
  params.set('path', nodePath);
  params.set('includeHidden', String(options?.includeHidden ?? false));
  appendContextId(params, options?.contextId);

  const data: RuntimeFileTreeResponse = await client.get(`/api/v1/files/tree/children?${params.toString()}`);
  return data.nodes?.map(node => mapRuntimeNodeToFileNode(node, parentDepth)) ?? [];
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
  contextId?: string | null
): Promise<RuntimeSaveFileResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.put(withContextId('/api/v1/files/content', contextId), { path: filePath, content });
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
    overwrite: false,
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
 * Duplicate a file.
 */
export const duplicateFile = async (
  runtimeBaseUrl: string,
  sourcePath: string,
  targetDirectory: string,
  contextId?: string | null
): Promise<RuntimeDuplicateResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const destinationPath = buildChildPath(targetDirectory, getBaseName(sourcePath));
  await client.post(withContextId('/api/v1/files/copy', contextId), {
    sourcePath,
    destPath: destinationPath,
    overwrite: false,
  });
  return { destinationPath };
};

/**
 * Move a file or folder.
 */
export const moveFile = async (
  runtimeBaseUrl: string,
  oldPath: string,
  newPath: string,
  overwrite: boolean = false,
  contextId?: string | null
): Promise<void> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  await client.post(withContextId('/api/v1/files/move', contextId), {
    sourcePath: oldPath,
    destPath: newPath,
    overwrite,
  });
};

/**
 * Upload files.
 */
export const uploadFiles = async (
  runtimeBaseUrl: string,
  targetPath: string,
  files: File[] | FileList,
  useSystemTmp: boolean = false,
  options?: RuntimeUploadOptions
): Promise<RuntimeUploadSummary> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const formData = new FormData();
  formData.append('targetPath', targetPath);
  formData.append('useSystemTmp', String(useSystemTmp));
  formData.append('archiveAction', options?.archiveAction ?? 'store');
  formData.append('keepArchive', String(options?.keepArchive ?? false));
  formData.append('conflictStrategy', options?.conflictStrategy ?? 'rename');
  const fileArray = Array.isArray(files) ? files : Array.from(files);
  fileArray.forEach(file => {
    formData.append('files', file);
  });

  const result = await client.post<RuntimeUploadResponse>(
    withContextId('/api/v1/files/upload', options?.contextId),
    formData,
  );
  const uploaded = Array.isArray(result.uploaded) ? result.uploaded : [];
  const extracted = Array.isArray(result.extracted) ? result.extracted : [];

  if (uploaded.length > 0 || extracted.length > 0) {
    const uploadedPaths = uploaded.map(item => item.path);
    const extractedPaths = extracted.map(item => item.path);
    const affectedPaths = Array.from(new Set([...uploadedPaths, ...extractedPaths]));
    return {
      uploaded,
      extracted,
      skipped: Array.isArray(result.skipped) ? result.skipped : [],
      uploadedPaths,
      extractedPaths,
      affectedPaths,
    };
  }

  const fallbackPaths = fileArray.map(file => {
    const sanitized = sanitizeUploadPathSegment(file.name) || file.name;
    return `${targetPath}/${sanitized}`;
  });
  return {
    uploaded: fallbackPaths.map(path => ({
      path,
      size: 0,
      lastModified: new Date().toISOString(),
      type: 'file',
    })),
    extracted: [],
    skipped: [],
    uploadedPaths: fallbackPaths,
    extractedPaths: [],
    affectedPaths: fallbackPaths,
  };
};

export const startExtractArchive = async (
  runtimeBaseUrl: string,
  request: RuntimeExtractArchiveRequest
): Promise<RuntimeExtractArchiveAcceptedResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(withContextId('/api/v1/files/extract', request.contextId), {
    archivePath: request.archivePath,
    targetPath: request.targetPath,
    conflictStrategy: request.conflictStrategy ?? 'rename',
  });
};

export const fetchExtractArchiveStatus = async (
  runtimeBaseUrl: string,
  operationId: string
): Promise<RuntimeExtractArchiveStatusResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/files/extract/${encodeURIComponent(operationId)}`);
};

/**
 * Download a single file.
 */
export const downloadFile = async (
  runtimeBaseUrl: string,
  filePath: string,
  contextId?: string | null,
): Promise<string> => {
  const url = new URL(buildRuntimeUrl(runtimeBaseUrl, 'files/download'));
  url.searchParams.set('path', filePath);
  if (contextId) {
    url.searchParams.set('contextId', contextId);
  }

  return url.toString();
};

export const startArchiveDownload = async (
  runtimeBaseUrl: string,
  request: RuntimeArchiveDownloadRequest
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
export type CanvasOwnerType = 'skill' | 'user';

export interface CanvasOwner {
  type: CanvasOwnerType;
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

export interface CanvasManifestDeleteResponse {
  workspaceId: string;
  deleted: boolean;
  manifestStatus: CanvasManifestStatus;
  runtimeStatus?: CanvasRuntimeStatus | null;
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

export interface CanvasReviewNoteCreateRequest {
  sessionId?: string | null;
  routePath: string;
  canvasUrl: string;
  target: CanvasReviewTarget;
  instruction: string;
  status?: CanvasReviewStatus;
}

export const fetchCanvasDetect = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<CanvasDetectResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/workspaces/${workspaceId}/canvas/detect`);
};

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

export const resetCanvas = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<CanvasActionResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(`/api/v1/workspaces/${workspaceId}/canvas/reset`);
};

export const deactivateCanvas = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<CanvasManifestDeleteResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.delete(`/api/v1/canvases/${workspaceId}/manifest`);
};

export const fetchCanvasLogs = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<CanvasLogsResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/workspaces/${workspaceId}/canvas/logs`);
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
  request: CanvasReviewNoteCreateRequest
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

export const appendCanvasReviewNoteReply = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  noteId: string,
  role: 'user' | 'agent',
  content: string
): Promise<CanvasReviewNote> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(`/api/v1/workspaces/${workspaceId}/canvas/review-notes/${noteId}/replies`, {
    role,
    content,
  });
};

export const deleteCanvasReviewNote = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  noteId: string
): Promise<void> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  await client.delete(`/api/v1/workspaces/${workspaceId}/canvas/review-notes/${noteId}`);
};
