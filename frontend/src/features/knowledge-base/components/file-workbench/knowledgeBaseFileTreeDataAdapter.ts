import { apiClient } from '@/shared/api/apiClient';
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

export interface KnowledgeBaseFileTreeDataAdapterOptions {
  knowledgeBaseId: string;
  includeHidden?: boolean;
}

const INITIAL_TREE_MAX_DEPTH = 5;
const CHILDREN_TREE_MAX_DEPTH = 1;

export const knowledgeBaseFileEndpoints = {
  getTree: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/tree`,
  getContent: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/content`,
  create: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
  update: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/content`,
  delete: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
  move: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
  upload: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
  copy: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/copy`,
};

export class KnowledgeBaseFileTreeDataAdapter implements FileTreeDataAdapter {
  constructor(private readonly options: KnowledgeBaseFileTreeDataAdapterOptions) {
    if (!options.knowledgeBaseId) {
      throw new Error('Missing Knowledge Base ID');
    }
  }

  async getTree(): Promise<FileTreeNode[]> {
    const { knowledgeBaseId, includeHidden } = this.options;
    const url = this.buildTreeUrl('/', INITIAL_TREE_MAX_DEPTH);
    const response = await apiClient.get<{ nodes?: FileTreeNode[] }>(url);
    return response.nodes ?? [];
  }

  async getChildren(path: string): Promise<FileTreeNode[]> {
    const url = this.buildTreeUrl(path, CHILDREN_TREE_MAX_DEPTH);
    const response = await apiClient.get<{ nodes?: FileTreeNode[] }>(url);
    return response.nodes ?? [];
  }

  async getContent(path: string): Promise<string> {
    const { knowledgeBaseId } = this.options;
    const url = `${knowledgeBaseFileEndpoints.getContent(knowledgeBaseId)}?path=${encodeURIComponent(path)}`;
    const response = await apiClient.get<{ content?: string }>(url);
    return response.content ?? '';
  }

  async create(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { knowledgeBaseId } = this.options;
    const formData = new FormData();
    formData.append('path', request.path);
    formData.append('type', request.isDirectory ? 'directory' : 'file');
    if (!request.isDirectory) {
      formData.append('content', request.content ?? '');
    }

    return apiClient.post(knowledgeBaseFileEndpoints.create(knowledgeBaseId), formData);
  }

  async update(path: string, content: string): Promise<FileOperationResponse> {
    return apiClient.put(knowledgeBaseFileEndpoints.update(this.options.knowledgeBaseId), { path, content });
  }

  async delete(path: string, recursive = false): Promise<FileOperationResponse> {
    const { knowledgeBaseId } = this.options;
    const url = `${knowledgeBaseFileEndpoints.delete(knowledgeBaseId)}?path=${encodeURIComponent(path)}&recursive=${String(recursive)}`;
    return apiClient.delete(url);
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
        await this.delete(path, request.recursive ?? true);
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
    const { knowledgeBaseId } = this.options;
    const formData = new FormData();
    formData.append('path', options.targetPath || '/');
    formData.append('overwrite', options.conflictStrategy === 'overwrite' ? 'true' : 'false');
    options.files.forEach((file) => formData.append('files', file));

    const response = await apiClient.post<{
      results?: Array<{ filename: string; path: string; success: boolean; message?: string }>;
      uploaded?: Array<{ filename: string; path: string; success: boolean; error?: string }>;
    }>(knowledgeBaseFileEndpoints.upload(knowledgeBaseId), formData);

    const results = response.results ?? response.uploaded ?? [];
    return results.map((item) => ({
      fileName: item.filename,
      path: item.path,
      success: item.success,
      error: 'message' in item ? item.message : item.error,
    }));
  }

  async download(_options: FileDownloadOptions): Promise<void> {
    throw new Error('Knowledge Base does not support download');
  }

  private postMove(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    return apiClient.patch(knowledgeBaseFileEndpoints.move(this.options.knowledgeBaseId), {
      sourcePath,
      destinationPath: targetPath,
      overwrite: false,
    });
  }

  private buildTreeUrl(path: string, maxDepth: number): string {
    const { knowledgeBaseId, includeHidden } = this.options;
    const params = new URLSearchParams({
      path,
      includeHidden: String(includeHidden ?? false),
      maxDepth: String(maxDepth),
    });
    return `${knowledgeBaseFileEndpoints.getTree(knowledgeBaseId)}?${params.toString()}`;
  }
}

export const createKnowledgeBaseFileTreeDataAdapter = (
  options: KnowledgeBaseFileTreeDataAdapterOptions,
): KnowledgeBaseFileTreeDataAdapter => new KnowledgeBaseFileTreeDataAdapter(options);
