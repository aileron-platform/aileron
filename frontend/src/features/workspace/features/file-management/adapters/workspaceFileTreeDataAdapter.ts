import { ApiClient } from '@/shared/api/apiClient';
import { parseFileContent, parseFileTree } from '@/shared/components/file-workbench';
import { createLogger } from '@/shared/services/logger';
import type {
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileContentResult,
  FileDownloadOptions,
  FileOperationRequest,
  FileOperationResponse,
  FileTreeDataAdapter,
  FileTreeNode,
  FileUpdateOptions,
  FileUploadOptions,
  FileConflictBatchResult,
} from '@/shared/components/file-workbench';
import {
  executeRuntimeFileConflictOperation,
  preflightRuntimeFileConflicts,
} from '../../../api/workspaceRuntimeApi';

const logger = createLogger('WorkspaceFileTreeDataAdapter');
const ROOT_TREE_PATH = '/';
const ROOT_TREE_MAX_DEPTH = 2;

type FileOperationResponseWithRevision = FileOperationResponse & {
  revision?: string | null;
};

export interface WorkspaceFileTreeDataAdapterOptions {
  workspaceId: string;
  runtimeBaseUrl?: string;
  contextId?: string | null;
  includeHidden?: boolean;
}

export class WorkspaceFileTreeDataAdapter implements FileTreeDataAdapter {
  private static readonly rootTreeRequests = new Map<string, Promise<FileTreeNode[]>>();
  private readonly client: ApiClient;

  constructor(private readonly options: WorkspaceFileTreeDataAdapterOptions) {
    if (!options.workspaceId) {
      throw new Error('Missing Workspace ID');
    }

    this.client = new ApiClient({
      baseUrl: `${options.runtimeBaseUrl ?? ''}/api/v1`,
      unauthorizedBehavior: 'propagate',
      executionAudience: 'workspace-runtime',
    });
  }

  async getTree(): Promise<FileTreeNode[]> {
    const path = ROOT_TREE_PATH;
    const maxDepth = ROOT_TREE_MAX_DEPTH;
    const url = this.appendContext(
      `/files/tree?path=${encodeURIComponent(path)}&includeHidden=${String(this.options.includeHidden ?? false)}&maxDepth=${maxDepth}`,
    );
    const requestKey = this.buildTreeRequestKey(path, maxDepth);

    const inflightRequest = WorkspaceFileTreeDataAdapter.rootTreeRequests.get(requestKey);
    if (inflightRequest) {
      logger.debug('Reusing in-flight workspace root tree request', { requestKey });
      return inflightRequest;
    }

    const request = this.client.get<{ nodes?: FileTreeNode[] }>(url)
      .then((data) => parseFileTree(data))
      .finally(() => {
        if (WorkspaceFileTreeDataAdapter.rootTreeRequests.get(requestKey) === request) {
          WorkspaceFileTreeDataAdapter.rootTreeRequests.delete(requestKey);
        }
      });

    WorkspaceFileTreeDataAdapter.rootTreeRequests.set(requestKey, request);
    return request;
  }

  async getChildren(path: string): Promise<FileTreeNode[]> {
    const url = this.appendContext(
      `/files/tree/children?path=${encodeURIComponent(path)}&includeHidden=${String(this.options.includeHidden ?? false)}&maxDepth=1`,
    );
    const data = await this.client.get<unknown>(url);
    return parseFileTree(data);
  }

  async getContent(path: string): Promise<FileContentResult> {
    const data = await this.client.get<unknown>(
      this.appendContext(`/files/content?path=${encodeURIComponent(path)}`),
    );
    const content = parseFileContent(data);
    return {
      content: content.content,
      revision: content.revision,
    };
  }

  async create(request: FileOperationRequest): Promise<FileOperationResponse> {
    const response = await this.client.post<FileOperationResponse>(this.appendContext('/files'), {
      path: request.path,
      type: request.isDirectory ? 'directory' : 'file',
      content: request.isDirectory ? undefined : (request.content ?? ''),
    });
    this.invalidateRootTreeRequest();
    return response;
  }

  async update(path: string, content: string, options?: FileUpdateOptions): Promise<FileOperationResponse> {
    const body: { path: string; content: string; revision?: string } = { path, content };
    if (options?.revision != null) {
      body.revision = options.revision;
    }

    const response = await this.client.put<FileOperationResponseWithRevision>(
      this.appendContext('/files/content'),
      body,
    );
    this.invalidateRootTreeRequest();
    return this.withReadableRevision(response);
  }

  async delete(path: string, recursive = false): Promise<FileOperationResponse> {
    const url = this.appendContext(`/files?path=${encodeURIComponent(path)}&recursive=${recursive}`);
    const response = await this.client.delete<FileOperationResponse>(url);
    this.invalidateRootTreeRequest();
    return response;
  }

  async batchDelete(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    const response = await this.client.post<BatchDeleteResponse>(
      this.appendContext('/files/batch-delete'),
      {
        paths: request.paths,
        recursive: request.recursive ?? true,
      },
    );
    this.invalidateRootTreeRequest();
    return response;
  }

  async move(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    const response = await this.postMove(sourcePath, targetPath);
    this.invalidateRootTreeRequest();
    return response;
  }

  async upload(options: FileUploadOptions): Promise<FileConflictBatchResult> {
    const controller = new AbortController();
    const request = {
      operation: 'upload' as const,
      targetPath: options.targetPath || '/',
      sources: options.files.map((file) => ({ sourcePath: file.name, entryType: 'file' as const })),
      archivePath: null,
    };
    const preflight = await preflightRuntimeFileConflicts(
      this.requireRuntimeBaseUrl(),
      request,
      { signal: controller.signal, contextId: this.options.contextId },
    );
    if (preflight.conflicts.length > 0) throw new Error('FILE_CONFLICT_RESOLUTION_REQUIRED');
    const result = await executeRuntimeFileConflictOperation(
      this.requireRuntimeBaseUrl(),
      {
        ...request,
        defaultStrategy: 'cancel',
        resolutions: [],
        payload: { files: options.files, contextId: this.options.contextId },
      },
      { signal: controller.signal },
    );
    this.invalidateRootTreeRequest();
    return result;
  }

  async download(options: FileDownloadOptions): Promise<void> {
    const blob = await this.client.getBlob(
      this.appendContext(`/files/download?path=${encodeURIComponent(options.path)}`),
    );

    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = options.fileName || options.path.split('/').pop() || 'download';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  }

  private postMove(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    return this.client.post(this.appendContext('/files/move'), { sourcePath, destPath: targetPath });
  }

  private requireRuntimeBaseUrl(): string {
    const baseUrl = this.options.runtimeBaseUrl;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }
    return baseUrl;
  }

  private appendContext(url: string): string {
    const contextId = this.options.contextId;
    if (!contextId) {
      return url;
    }

    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}contextId=${encodeURIComponent(contextId)}`;
  }

  private buildTreeRequestKey(path: string, maxDepth: number): string {
    return JSON.stringify({
      workspaceId: this.options.workspaceId,
      runtimeBaseUrl: this.options.runtimeBaseUrl ?? null,
      contextId: this.options.contextId ?? null,
      includeHidden: this.options.includeHidden ?? false,
      path,
      maxDepth,
    });
  }

  private invalidateRootTreeRequest(): void {
    WorkspaceFileTreeDataAdapter.rootTreeRequests.delete(
      this.buildTreeRequestKey(ROOT_TREE_PATH, ROOT_TREE_MAX_DEPTH),
    );
  }

  private withReadableRevision(response: FileOperationResponseWithRevision): FileOperationResponse {
    if (response.revision == null || this.hasReadableRevision(response.data)) {
      return response;
    }

    const data = response.data && typeof response.data === 'object' && !Array.isArray(response.data)
      ? { ...response.data, revision: response.revision }
      : { revision: response.revision };

    return { ...response, data };
  }

  private hasReadableRevision(data: unknown): data is { revision?: string | null } {
    return data !== null
      && typeof data === 'object'
      && 'revision' in data
      && (typeof data.revision === 'string' || data.revision === null || data.revision === undefined);
  }
}

export const createWorkspaceFileTreeDataAdapter = (
  options: WorkspaceFileTreeDataAdapterOptions,
): WorkspaceFileTreeDataAdapter => new WorkspaceFileTreeDataAdapter(options);
