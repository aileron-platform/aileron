import { ApiClient, apiClient } from '@/shared/api/apiClient';
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
import type { AgentFileCollection, AgentSelectedFile } from '../types';

export interface AgentFileTreeDataAdapterOptions {
  workspaceId: string;
  apiPrefix: 'claude-code' | 'gemini' | 'codex' | 'opencode';
  scope: AgentSelectedFile['scope'];
  collection: AgentFileCollection;
  runtimeBaseUrl?: string | null;
}

const agentFileEndpoints = {
  getTree: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/tree?scope=${scope}&includeHidden=true`,
  getContent: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, path: string, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/content?path=${encodeURIComponent(path)}&scope=${scope}`,
  create: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}?scope=${scope}`,
  update: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, path: string, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/content?path=${encodeURIComponent(path)}&scope=${scope}`,
  delete: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, path: string, scope: string, recursive: boolean) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}?path=${encodeURIComponent(path)}&scope=${scope}&recursive=${recursive}`,
  move: (workspaceId: string, apiPrefix: string, collection: AgentFileCollection, scope: string) =>
    `/workspaces/${workspaceId}/${apiPrefix}/${collection}/move?scope=${scope}`,
};

export class AgentFileTreeDataAdapter implements FileTreeDataAdapter {
  private readonly client: ApiClient;

  constructor(private readonly options: AgentFileTreeDataAdapterOptions) {
    if (!options.workspaceId) {
      throw new Error('Missing Workspace ID');
    }

    this.client = options.runtimeBaseUrl
      ? new ApiClient({ baseUrl: `${options.runtimeBaseUrl}/api/v1` })
      : apiClient;
  }

  async getTree(): Promise<FileTreeNode[]> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    const response = await this.client.get<{ nodes?: FileTreeNode[] }>(
      agentFileEndpoints.getTree(workspaceId, apiPrefix, collection, scope),
    );
    return response.nodes ?? [];
  }

  async getChildren(): Promise<FileTreeNode[]> {
    return [];
  }

  async getContent(path: string): Promise<string> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    const response = await this.client.get<{ data?: { content?: string } }>(
      agentFileEndpoints.getContent(workspaceId, apiPrefix, collection, path, scope),
    );
    return response.data?.content ?? '';
  }

  async create(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    const baseUrl = agentFileEndpoints.create(workspaceId, apiPrefix, collection, scope);
    const url = `${baseUrl}&path=${encodeURIComponent(request.path)}&type=file${
      request.content ? `&content=${encodeURIComponent(request.content)}` : ''
    }`;
    return this.client.post(url);
  }

  async update(path: string, content: string): Promise<FileOperationResponse> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    const baseUrl = agentFileEndpoints.update(workspaceId, apiPrefix, collection, path, scope);
    return this.client.put(`${baseUrl}&content=${encodeURIComponent(content)}`);
  }

  async delete(path: string, recursive = false): Promise<FileOperationResponse> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    return this.client.delete(agentFileEndpoints.delete(workspaceId, apiPrefix, collection, path, scope, recursive));
  }

  async batchDelete(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    const results: BatchDeleteResponse = {
      success: true,
      deleted: [],
      failed: [],
      total: request.paths.length,
      successCount: 0,
      failedCount: 0,
    };

    for (const path of request.paths) {
      try {
        await this.delete(path, true);
        results.deleted.push(path);
        results.successCount += 1;
      } catch (error) {
        results.failed.push({
          path,
          error: error instanceof Error ? error.message : 'Delete failed',
        });
        results.failedCount += 1;
      }
    }

    results.success = results.failedCount === 0;
    return results;
  }

  async move(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    return this.postMove(sourcePath, targetPath);
  }

  async upload(options: FileUploadOptions): Promise<FileUploadResult[]> {
    const results: FileUploadResult[] = [];

    for (const file of options.files) {
      try {
        const content = await file.text();
        const fileName = `${options.targetPath}/${file.name}`.replace(/^\/+/, '');

        await this.create({
          type: 'create',
          path: fileName,
          content,
          isDirectory: false,
        });

        results.push({
          fileName: file.name,
          success: true,
          path: fileName,
        });
      } catch (error) {
        results.push({
          fileName: file.name,
          success: false,
          error: error instanceof Error ? error.message : 'Upload failed',
        });
      }
    }

    return results;
  }

  async download(_options: FileDownloadOptions): Promise<void> {
    throw new Error('Agent file collections do not support download');
  }

  private postMove(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    const { workspaceId, apiPrefix, collection, scope } = this.options;
    const baseUrl = agentFileEndpoints.move(workspaceId, apiPrefix, collection, scope);
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set('sourcePath', sourcePath);
    url.searchParams.set('destPath', targetPath);
    url.searchParams.set('sourceScope', scope);
    url.searchParams.set('destScope', scope);
    url.searchParams.set('overwrite', 'false');
    return this.client.post(url.pathname + url.search);
  }
}

export const createAgentFileTreeDataAdapter = (
  options: AgentFileTreeDataAdapterOptions,
): AgentFileTreeDataAdapter => new AgentFileTreeDataAdapter(options);
