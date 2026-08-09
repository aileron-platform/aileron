import { apiClient } from '@/shared/api/apiClient';
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
  executeKnowledgeBaseFileConflictOperation,
  preflightKnowledgeBaseFileConflicts,
} from '../../api/knowledgeBaseApi';

interface KnowledgeBaseFileTreeDataAdapterOptions {
  knowledgeBaseId: string;
  includeHidden?: boolean;
}

const INITIAL_TREE_MAX_DEPTH = 5;
const CHILDREN_TREE_MAX_DEPTH = 1;

type FileContentResponse = {
  content: string;
  revision?: string | null;
  readable: boolean;
  unreadableReason?: 'binary' | null;
};

type FileOperationResponseWithRevision = FileOperationResponse & {
  revision?: string | null;
};

export const knowledgeBaseFileEndpoints = {
  getTree: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/tree`,
  getContent: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/content`,
  create: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
  update: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/content`,
  delete: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files`,
  move: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/move`,
  upload: (knowledgeBaseId: string) => `/knowledge-bases/${knowledgeBaseId}/files/upload`,
};

class KnowledgeBaseFileTreeDataAdapter implements FileTreeDataAdapter {
  constructor(private readonly options: KnowledgeBaseFileTreeDataAdapterOptions) {
    if (!options.knowledgeBaseId) {
      throw new Error('Missing Knowledge Base ID');
    }
  }

  async getTree(): Promise<FileTreeNode[]> {
    const { includeHidden } = this.options;
    const url = this.buildTreeUrl('/', INITIAL_TREE_MAX_DEPTH);
    const response = await apiClient.get<{ nodes?: FileTreeNode[] }>(url);
    return response.nodes ?? [];
  }

  async getChildren(path: string): Promise<FileTreeNode[]> {
    const url = this.buildTreeUrl(path, CHILDREN_TREE_MAX_DEPTH);
    const response = await apiClient.get<{ nodes?: FileTreeNode[] }>(url);
    return response.nodes ?? [];
  }

  async getContent(path: string): Promise<FileContentResult> {
    const { knowledgeBaseId } = this.options;
    const url = `${knowledgeBaseFileEndpoints.getContent(knowledgeBaseId)}?path=${encodeURIComponent(path)}`;
    const response = await apiClient.get<FileContentResponse>(url);
    return {
      content: response.content,
      revision: response.revision,
      readable: response.readable,
      unreadableReason: response.unreadableReason ?? undefined,
    };
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

  async update(path: string, content: string, options?: FileUpdateOptions): Promise<FileOperationResponse> {
    const body: { path: string; type: 'file'; content: string; revision?: string } = {
      path,
      type: 'file',
      content,
    };
    if (options?.revision != null) {
      body.revision = options.revision;
    }

    const response = await apiClient.put<FileOperationResponseWithRevision>(
      knowledgeBaseFileEndpoints.update(this.options.knowledgeBaseId),
      body,
    );
    return this.withReadableRevision(response);
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

  async upload(options: FileUploadOptions): Promise<FileConflictBatchResult> {
    const { knowledgeBaseId } = this.options;
    const controller = new AbortController();
    const request = {
      operation: 'upload' as const,
      targetPath: options.targetPath || '/',
      sources: options.files.map((file) => ({ sourcePath: file.name, entryType: 'file' as const })),
      archivePath: null,
    };
    const preflight = await preflightKnowledgeBaseFileConflicts(
      knowledgeBaseId,
      request,
      { signal: controller.signal },
    );
    if (preflight.conflicts.length > 0) throw new Error('FILE_CONFLICT_RESOLUTION_REQUIRED');
    return executeKnowledgeBaseFileConflictOperation(
      knowledgeBaseId,
      {
        ...request,
        defaultStrategy: 'cancel',
        resolutions: [],
        payload: { files: options.files },
      },
      { signal: controller.signal },
    );
  }

  async download(_options: FileDownloadOptions): Promise<void> {
    throw new Error('Knowledge Base does not support download');
  }

  private postMove(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    return apiClient.post(knowledgeBaseFileEndpoints.move(this.options.knowledgeBaseId), {
      sourcePath,
      destinationPath: targetPath,
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

export const createKnowledgeBaseFileTreeDataAdapter = (
  options: KnowledgeBaseFileTreeDataAdapterOptions,
): KnowledgeBaseFileTreeDataAdapter => new KnowledgeBaseFileTreeDataAdapter(options);
