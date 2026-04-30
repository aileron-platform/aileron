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

export interface TemplateFileTreeDataAdapterOptions {
  templateId: string;
  scope: string;
}

const templateFileEndpoints = {
  getTree: (templateId: string, scope: string) =>
    `/templates/${templateId}/files/tree?scope=${scope}&include_hidden=true`,
  getContent: (templateId: string, scope: string) =>
    `/templates/${templateId}/files/content?scope=${scope}`,
  create: (templateId: string, scope: string) =>
    `/templates/${templateId}/files?scope=${scope}`,
  update: (templateId: string, scope: string) =>
    `/templates/${templateId}/files/content?scope=${scope}`,
  delete: (templateId: string, scope: string) =>
    `/templates/${templateId}/files?scope=${scope}`,
  batchDelete: (templateId: string, scope: string) =>
    `/templates/${templateId}/files/batch-delete?scope=${scope}`,
  move: (templateId: string, scope: string) =>
    `/templates/${templateId}/files/move?scope=${scope}`,
  upload: (templateId: string, scope: string) =>
    `/templates/${templateId}/files/upload?scope=${scope}`,
};

export class TemplateFileTreeDataAdapter implements FileTreeDataAdapter {
  constructor(private readonly options: TemplateFileTreeDataAdapterOptions) {
    if (!options.templateId) {
      throw new Error('Missing Template ID');
    }
    if (!options.scope) {
      throw new Error('Missing scope parameter');
    }
  }

  async getTree(): Promise<FileTreeNode[]> {
    const { templateId, scope } = this.options;
    const response = await apiClient.get<{ nodes?: FileTreeNode[] }>(
      templateFileEndpoints.getTree(templateId, scope),
    );
    return response.nodes ?? [];
  }

  async getChildren(): Promise<FileTreeNode[]> {
    return [];
  }

  async getContent(path: string): Promise<string> {
    const { templateId, scope } = this.options;
    const url = `${templateFileEndpoints.getContent(templateId, scope)}&path=${encodeURIComponent(path)}`;
    const response = await apiClient.get<{ content?: string }>(url);
    return response.content ?? '';
  }

  async create(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { templateId, scope } = this.options;
    const queryParams = new URLSearchParams();
    queryParams.append('path', request.path);
    queryParams.append('entry_type', request.isDirectory ? 'directory' : 'file');
    if (request.content) {
      queryParams.append('content', request.content);
    }

    return apiClient.post(`${templateFileEndpoints.create(templateId, scope)}&${queryParams.toString()}`);
  }

  async update(path: string, content: string): Promise<FileOperationResponse> {
    const { templateId, scope } = this.options;
    const queryParams = new URLSearchParams();
    queryParams.append('path', path);
    queryParams.append('content', content);

    return apiClient.put(`${templateFileEndpoints.update(templateId, scope)}&${queryParams.toString()}`);
  }

  async delete(path: string, recursive = false): Promise<FileOperationResponse> {
    const { templateId, scope } = this.options;
    const url = `${templateFileEndpoints.delete(templateId, scope)}&path=${encodeURIComponent(path)}&recursive=${recursive}`;
    return apiClient.delete(url);
  }

  async batchDelete(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    const { templateId, scope } = this.options;
    return apiClient.post(templateFileEndpoints.batchDelete(templateId, scope), request);
  }

  async move(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    return this.postMove(sourcePath, targetPath);
  }

  async upload(options: FileUploadOptions): Promise<FileUploadResult[]> {
    const { templateId, scope } = this.options;
    const formData = new FormData();
    formData.append('target_path', options.targetPath);
    formData.append('overwrite', 'false');
    options.files.forEach((file) => formData.append('files', file));

    const response = await apiClient.post<{
      uploaded?: Array<{ filename: string; path: string; size: number; success: boolean; error?: string }>;
    }>(templateFileEndpoints.upload(templateId, scope), formData);

    return response.uploaded?.map((item) => ({
      fileName: item.filename,
      path: item.path,
      size: item.size,
      success: item.success,
      error: item.error,
    })) ?? [];
  }

  async download(_options: FileDownloadOptions): Promise<void> {
    throw new Error('Template does not support download');
  }

  private postMove(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    const { templateId, scope } = this.options;
    const queryParams = new URLSearchParams();
    queryParams.append('source_path', sourcePath);
    queryParams.append('dest_path', targetPath);

    return apiClient.post(`${templateFileEndpoints.move(templateId, scope)}&${queryParams.toString()}`);
  }
}

export const createTemplateFileTreeDataAdapter = (
  options: TemplateFileTreeDataAdapterOptions,
): TemplateFileTreeDataAdapter => new TemplateFileTreeDataAdapter(options);
