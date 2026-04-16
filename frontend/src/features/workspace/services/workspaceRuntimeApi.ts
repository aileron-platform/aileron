/**
 * Workspace Runtime API 服務
 * 處理與 Workspace Runtime 相關的 API 操作
 */

import { ApiClient, apiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';
import { resolvePreferredWorkspaceUrl } from './workspacePublicUrl';

const logger = createLogger('workspaceRuntimeApi');
import type {
  RuntimeArchiveTicketResponse,
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

/**
 * 映射 Runtime 節點到 FileNode
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
 * 建構 Runtime URL
 */
export const buildRuntimeUrl = (base: string, path: string): string => {
  const normalizedBase = base.endsWith('/') ? base : `${base}/`;
  const normalizedPath = path.startsWith('/') ? path.slice(1) : path;
  const fullPath = `api/v1/${normalizedPath}`;
  return new URL(fullPath, normalizedBase).toString();
};

/**
 * 創建帶認證的 Runtime API Client
 */
const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

/**
 * 解析錯誤回應
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
    logger.warn('解析錯誤回應失敗', { error });
  }
  return { message: `${response.status} ${response.statusText}` };
};

/**
 * 與 Runtime 保持一致的檔名正規化
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
 * 獲取預設工作區 ID
 */
export const fetchDefaultWorkspaceId = async (): Promise<string> => {
  const data = await apiClient.get<WorkspaceListResponse>('/workspaces/?page=1&pageSize=1');
  const firstWorkspace = data.items?.[0];
  if (!firstWorkspace?.id) {
    throw new Error('尚未建立任何工作區');
  }
  return firstWorkspace.id;
};

/**
 * 解析 Runtime Base URL
 */
export const resolveRuntimeBaseUrl = async (
  workspaceId: string,
  cache: Map<string, string>
): Promise<string> => {
  if (!workspaceId) {
    throw new Error('workspaceId 缺失');
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
    throw new Error('Workspace Runtime 尚未啟動或尚未提供 URL');
  }
  cache.set(workspaceId, runtimeUrl);
  return runtimeUrl;
};

/**
 * 獲取工作區詳情（包含 cliType）
 */
export const fetchWorkspaceDetail = async (workspaceId: string): Promise<WorkspaceDetailResponse> => {
  return await apiClient.get<WorkspaceDetailResponse>(`/workspaces/${workspaceId}`);
};

/**
 * 載入檔案樹
 * 不指定 maxDepth，讓後端使用環境設定檔的 FILE_TREE_MAX_DEPTH
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
 * 載入節點子項
 * 不指定 maxDepth，讓後端使用環境設定檔的 FILE_TREE_MAX_DEPTH
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
 * 讀取檔案內容
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
 * 儲存檔案內容
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
 * 建立檔案或資料夾
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
 * 重新命名檔案
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
 * 刪除檔案
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
 * 批次刪除檔案
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
 * 複製檔案
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
 * 移動檔案或資料夾
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
 * 上傳檔案
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
 * 下載檔案
 * 返回下載 URL，前端可以使用 window.open 或 <a> 標籤觸發下載
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

  // 直接返回下載 URL，讓瀏覽器處理下載
  return url.toString();
};

/**
 * 批次下載檔案（打包成 ZIP）
 * 返回操作票據，可用於查詢打包狀態
 */
export const batchDownloadFiles = async (
  runtimeBaseUrl: string,
  paths: string[],
  archiveFormat: 'zip' | 'tar' = 'zip',
  contextId?: string | null
): Promise<RuntimeArchiveTicketResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(withContextId('/api/v1/files/batch-download', contextId), { paths, archiveFormat });
};

/**
 * Next.js 路由相關類型
 */
export interface NextJsRoute {
  path: string;
}

export interface NextJsRoutesResponse {
  workspaceId: string;
  routes: NextJsRoute[];
  total: number;
  scannedAt: string;
}

/**
 * 獲取 Next.js 路由列表
 */
export const fetchNextJsRoutes = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<NextJsRoutesResponse> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/workspaces/${workspaceId}/preview/nextjs/routes`);
};

/**
 * 同步 /workspace 到 /web-preview
 */
export const syncPreview = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  force: boolean = false
): Promise<any> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.post(`/api/v1/workspaces/${workspaceId}/preview/sync`, { force });
};

/**
 * 查詢預覽同步狀態
 */
export const fetchPreviewSyncStatus = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  operationId: string
): Promise<any> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/workspaces/${workspaceId}/preview/sync/${operationId}`);
};

/**
 * 檢查預覽服務健康狀態
 */
export const checkPreviewHealth = async (
  runtimeBaseUrl: string,
  workspaceId: string
): Promise<{
  status: 'healthy' | 'unhealthy' | 'standby' | 'starting' | 'checking';
  nextjs_running: boolean;
  port_available: boolean;
  message: string;
  source?: string | null;
  workspace_has_nextjs?: boolean;
}> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  return await client.get(`/api/v1/workspaces/${workspaceId}/preview/health`);
};
