import { ApiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';
import type {
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileDownloadOptions,
  FileOperationRequest,
  FileOperationResponse,
  FileTreeDataAdapter,
  FileTreeNode,
  FileUploadOptions,
  FileUploadResult,
} from '@/shared/components/file-workbench';

const logger = createLogger('WorkspaceFileTreeDataAdapter');

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

    this.client = new ApiClient({ baseUrl: `${options.runtimeBaseUrl ?? ''}/api/v1` });
  }

  async getTree(): Promise<FileTreeNode[]> {
    const path = '/';
    const maxDepth = 2;
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
      .then((data) => data.nodes ?? [])
      .finally(() => {
        WorkspaceFileTreeDataAdapter.rootTreeRequests.delete(requestKey);
      });

    WorkspaceFileTreeDataAdapter.rootTreeRequests.set(requestKey, request);
    return request;
  }

  async getChildren(path: string): Promise<FileTreeNode[]> {
    const url = this.appendContext(
      `/files/tree/children?path=${encodeURIComponent(path)}&includeHidden=${String(this.options.includeHidden ?? false)}&maxDepth=1`,
    );
    const data = await this.client.get<{ nodes?: FileTreeNode[] }>(url);
    return data.nodes ?? [];
  }

  async getContent(path: string): Promise<string> {
    const data = await this.client.get<{ content?: string }>(
      this.appendContext(`/files/content?path=${encodeURIComponent(path)}`),
    );
    return data.content ?? '';
  }

  async create(request: FileOperationRequest): Promise<FileOperationResponse> {
    return this.client.post(this.appendContext('/files'), {
      path: request.path,
      type: request.isDirectory ? 'directory' : 'file',
      content: request.isDirectory ? undefined : (request.content ?? ''),
    });
  }

  async update(path: string, content: string): Promise<FileOperationResponse> {
    return this.client.put(this.appendContext('/files/content'), { path, content });
  }

  async delete(path: string, recursive = false): Promise<FileOperationResponse> {
    const url = this.appendContext(`/files?path=${encodeURIComponent(path)}&recursive=${recursive}`);
    return this.client.delete(url);
  }

  async batchDelete(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    return this.client.post(this.appendContext('/files/batch-delete'), {
      paths: request.paths,
      recursive: request.recursive ?? true,
    });
  }

  async move(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    return this.postMove(sourcePath, targetPath);
  }

  async upload(options: FileUploadOptions): Promise<FileUploadResult[]> {
    const formData = new FormData();
    formData.append('targetPath', options.targetPath);
    formData.append('archiveAction', options.archiveAction ?? 'store');
    formData.append('keepArchive', String(options.keepArchive ?? false));
    formData.append('conflictStrategy', options.conflictStrategy ?? 'rename');

    for (const file of options.files) {
      formData.append('files', file);
    }

    const result = await this.client.post<{
      uploaded?: Array<{ path: string }>;
      extracted?: Array<{ path: string }>;
      skipped?: string[];
    }>(this.appendContext('/files/upload'), formData);

    const uploaded = [
      ...(result.uploaded ?? []),
      ...(result.extracted ?? []),
    ].map((item) => ({
      fileName: item.path.split('/').pop() ?? '',
      path: item.path,
      success: true,
    }));

    const skipped = (result.skipped ?? []).map((path) => ({
      fileName: path.split('/').pop() ?? '',
      path,
      success: false,
      error: 'File already exists or was skipped',
    }));

    return [...uploaded, ...skipped];
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
}

export const createWorkspaceFileTreeDataAdapter = (
  options: WorkspaceFileTreeDataAdapterOptions,
): WorkspaceFileTreeDataAdapter => new WorkspaceFileTreeDataAdapter(options);
