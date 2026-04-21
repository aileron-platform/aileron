/**
 * 統一檔案樹管理組件 - API 適配器
 *
 * 統一不同端點的 API 調用，提供一致的介面
 */

import { createLogger } from '@/shared/services/logger';
import { apiClient, ApiClient } from '@/shared/api/apiClient';

const logger = createLogger('FileTreeAdapter');
import type {
  FileTreeNode,
  FileTreeApiConfig,
  FileOperationRequest,
  FileOperationResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileUploadOptions,
  FileUploadResult,
  FileDownloadOptions,
} from '../types';
import { API_ENDPOINTS, ERROR_MESSAGES } from '../constants';

/**
 * 檔案樹 API 適配器
 */
export class FileTreeApiAdapter {
  private client: ApiClient;

  constructor(private config: FileTreeApiConfig) {
    this.validateConfig();
    // 如果提供了自定義 baseUrl，創建新的 API client 實例
    if (config.baseUrl) {
      this.client = new ApiClient({ baseUrl: config.baseUrl + '/api/v1' });
    } else {
      this.client = apiClient;
    }
  }

  private appendWorkspaceContext(url: string): string {
    const contextId = this.config.contextId;
    if (!contextId) {
      return url;
    }

    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}contextId=${encodeURIComponent(contextId)}`;
  }

  /**
   * 驗證配置
   */
  private validateConfig(): void {
    const { type, workspaceId, templateId, knowledgeBaseId, scope } = this.config;

    if (type === 'workspace' || type === 'claude-code') {
      if (!workspaceId) {
        throw new Error(ERROR_MESSAGES.MISSING_WORKSPACE_ID);
      }
    }

    if (type === 'template') {
      if (!templateId) {
        throw new Error(ERROR_MESSAGES.MISSING_TEMPLATE_ID);
      }
      if (!scope) {
        throw new Error(ERROR_MESSAGES.MISSING_SCOPE);
      }
    }

    if (type === 'knowledge-base' && !knowledgeBaseId) {
      throw new Error(ERROR_MESSAGES.MISSING_KNOWLEDGE_BASE_ID);
    }
  }

  /**
   * 取得檔案樹
   */
  async getTree(): Promise<FileTreeNode[]> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.getWorkspaceTree();
      case 'template':
        return this.getTemplateTree();
      case 'knowledge-base':
        return this.getKnowledgeBaseTree();
      case 'claude-code':
        return this.getClaudeCodeTree();
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 取得檔案內容
   */
  async getContent(path: string): Promise<string> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.getWorkspaceContent(path);
      case 'template':
        return this.getTemplateContent(path);
      case 'knowledge-base':
        return this.getKnowledgeBaseContent(path);
      case 'claude-code':
        return this.getClaudeCodeContent(path);
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 建立檔案或資料夾
   */
  async create(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.createWorkspaceFile(request);
      case 'template':
        return this.createTemplateFile(request);
      case 'knowledge-base':
        return this.createKnowledgeBaseFile(request);
      case 'claude-code':
        return this.createClaudeCodeFile(request);
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 更新檔案內容
   */
  async update(path: string, content: string): Promise<FileOperationResponse> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.updateWorkspaceFile(path, content);
      case 'template':
        return this.updateTemplateFile(path, content);
      case 'knowledge-base':
        return this.updateKnowledgeBaseFile(path, content);
      case 'claude-code':
        return this.updateClaudeCodeFile(path, content);
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 刪除檔案或資料夾
   */
  async delete(path: string, recursive = false): Promise<FileOperationResponse> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.deleteWorkspaceFile(path, recursive);
      case 'template':
        return this.deleteTemplateFile(path, recursive);
      case 'knowledge-base':
        return this.deleteKnowledgeBaseFile(path, recursive);
      case 'claude-code':
        return this.deleteClaudeCodeFile(path, recursive);
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 批次刪除
   */
  async batchDelete(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.batchDeleteWorkspace(request);
      case 'template':
        return this.batchDeleteTemplate(request);
      case 'knowledge-base':
        return this.batchDeleteKnowledgeBase(request);
      case 'claude-code':
        // Claude Code 不支援批次刪除，逐一刪除
        return this.batchDeleteClaudeCode(request);
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 重新命名
   */
  async rename(oldPath: string, newPath: string): Promise<FileOperationResponse> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.renameWorkspaceFile(oldPath, newPath);
      case 'template':
        return this.renameTemplateFile(oldPath, newPath);
      case 'knowledge-base':
        return this.renameKnowledgeBaseFile(oldPath, newPath);
      case 'claude-code':
        return this.renameClaudeCodeFile(oldPath, newPath);
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 移動檔案
   */
  async move(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.moveWorkspaceFile(sourcePath, targetPath);
      case 'template':
        return this.moveTemplateFile(sourcePath, targetPath);
      case 'knowledge-base':
        return this.moveKnowledgeBaseFile(sourcePath, targetPath);
      case 'claude-code':
        return this.moveClaudeCodeFile(sourcePath, targetPath);
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 上傳檔案
   */
  async upload(options: FileUploadOptions): Promise<FileUploadResult[]> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.uploadWorkspaceFiles(options);
      case 'template':
        return this.uploadTemplateFiles(options);
      case 'knowledge-base':
        return this.uploadKnowledgeBaseFiles(options);
      case 'claude-code':
        return this.uploadClaudeCodeFiles(options);
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  /**
   * 下載檔案
   */
  async download(options: FileDownloadOptions): Promise<void> {
    const { type } = this.config;

    switch (type) {
      case 'workspace':
        return this.downloadWorkspaceFile(options);
      case 'template':
        throw new Error('Template does not support download');
      case 'knowledge-base':
        throw new Error('Knowledge Base does not support download');
      case 'claude-code':
        throw new Error('Claude Code does not support download');
      default:
        throw new Error(ERROR_MESSAGES.INVALID_CONFIG);
    }
  }

  // ==================== Workspace 實作 ====================
  // Workspace 直接調用 runtime API，不經過 workspace-manager

  private async getWorkspaceTree(): Promise<FileTreeNode[]> {
    logger.debug('getWorkspaceTree: 開始獲取檔案樹');
    const { baseUrl, includeHidden } = this.config;
    if (!baseUrl) {
      logger.error('getWorkspaceTree: baseUrl 未設置');
      throw new Error('Workspace runtime baseUrl is required');
    }

    // 不指定 maxDepth，讓後端使用環境設定檔的 FILE_TREE_MAX_DEPTH
    const url = this.appendWorkspaceContext(
      `/files/tree?path=/&includeHidden=${String(includeHidden ?? false)}`
    );
    logger.debug('getWorkspaceTree: 請求 URL', { url });

    const data = await this.client.get(url);
    logger.debug('getWorkspaceTree: 獲取到的數據', { data, nodeCount: data.nodes?.length || 0 });
    return data.nodes || [];
  }

  private async getWorkspaceContent(path: string): Promise<string> {
    const { baseUrl } = this.config;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }

    const url = this.appendWorkspaceContext(`/files/content?path=${encodeURIComponent(path)}`);
    const data = await this.client.get(url);
    return data.content || '';
  }

  private async createWorkspaceFile(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { baseUrl } = this.config;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }

    const data = await this.client.post(this.appendWorkspaceContext('/files'), {
      path: request.path,
      type: request.isDirectory ? 'directory' : 'file',
      content: request.isDirectory ? undefined : (request.content ?? ''),
    });

    return data;
  }

  private async updateWorkspaceFile(path: string, content: string): Promise<FileOperationResponse> {
    const { baseUrl } = this.config;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }

    const data = await this.client.put(this.appendWorkspaceContext('/files/content'), { path, content });

    return data;
  }

  private async deleteWorkspaceFile(path: string, recursive: boolean): Promise<FileOperationResponse> {
    const { baseUrl } = this.config;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }

    const url = this.appendWorkspaceContext(`/files?path=${encodeURIComponent(path)}&recursive=${recursive}`);
    const data = await this.client.delete(url);

    return data;
  }

  private async batchDeleteWorkspace(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    const { baseUrl } = this.config;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }

    const data = await this.client.post(this.appendWorkspaceContext('/files/batch-delete'), {
      paths: request.paths,
      recursive: request.recursive ?? true,
    });

    return data;
  }

  private async renameWorkspaceFile(oldPath: string, newPath: string): Promise<FileOperationResponse> {
    const { baseUrl } = this.config;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }

    const data = await this.client.post(this.appendWorkspaceContext('/files/move'), { sourcePath: oldPath, destPath: newPath });

    return data;
  }

  private async moveWorkspaceFile(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    const { baseUrl } = this.config;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }

    const data = await this.client.post(this.appendWorkspaceContext('/files/move'), { sourcePath, destPath: targetPath });

    return data;
  }

  private async uploadWorkspaceFiles(options: FileUploadOptions): Promise<FileUploadResult[]> {
    logger.debug('uploadWorkspaceFiles: 開始準備上傳', { options });
    const { baseUrl } = this.config;
    if (!baseUrl) {
      logger.error('uploadWorkspaceFiles: baseUrl 未設置');
      throw new Error('Workspace runtime baseUrl is required');
    }

    // 使用 FormData multipart/form-data 上傳，自動處理所有類型的文件
    const formData = new FormData();
    formData.append('targetPath', options.targetPath);
    formData.append('archiveAction', options.archiveAction ?? 'store');
    formData.append('keepArchive', String(options.keepArchive ?? false));
    formData.append('conflictStrategy', options.conflictStrategy ?? 'rename');

    // 添加所有文件到 FormData
    for (const file of options.files) {
      formData.append('files', file);
      logger.debug('uploadWorkspaceFiles: 添加檔案到 FormData', { fileName: file.name, size: file.size });
    }

    // 使用 POST /files/upload 端點（multipart 上傳）
    logger.debug('uploadWorkspaceFiles: 請求 URL: /files/upload');

    const result: any = await this.client.post(this.appendWorkspaceContext('/files/upload'), formData);
    logger.debug('uploadWorkspaceFiles: 上傳成功', { result });

    // 將 multipart 上傳的結果轉換為 FileUploadResult 格式
    const results: FileUploadResult[] = [];

    if (result.uploaded && Array.isArray(result.uploaded)) {
      for (const item of result.uploaded) {
        results.push({
          fileName: item.path.split('/').pop() || '',
          path: item.path,
          success: true,
        });
      }
    }

    if (result.extracted && Array.isArray(result.extracted)) {
      for (const item of result.extracted) {
        results.push({
          fileName: item.path.split('/').pop() || '',
          path: item.path,
          success: true,
        });
      }
    }

    if (result.skipped && Array.isArray(result.skipped)) {
      for (const path of result.skipped) {
        results.push({
          fileName: path.split('/').pop() || '',
          path: path,
          success: false,
          error: '檔案已存在或被跳過',
        });
      }
    }

    logger.debug('uploadWorkspaceFiles: 所有檔案處理完成', { results });
    return results;
  }

  private async downloadWorkspaceFile(options: FileDownloadOptions): Promise<void> {
    const { baseUrl } = this.config;
    if (!baseUrl) {
      throw new Error('Workspace runtime baseUrl is required');
    }

    // 使用 ApiClient.getBlob 來確保請求攜帶 Authorization header
    const path = this.appendWorkspaceContext(`/files/download?path=${encodeURIComponent(options.path)}`);
    const blob = await this.client.getBlob(path);

    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = options.fileName || options.path.split('/').pop() || 'download';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
  }

  // ==================== Template 實作 ====================

  private async getTemplateTree(): Promise<FileTreeNode[]> {
    const { templateId, scope } = this.config;
    const url = API_ENDPOINTS.template.getTree(templateId!, scope!);
    const response = await this.client.get<{ path: string; scope: string; nodes: FileTreeNode[]; total: number }>(url);
    return response.nodes || [];
  }

  private async getTemplateContent(path: string): Promise<string> {
    const { templateId, scope } = this.config;
    const url = `${API_ENDPOINTS.template.getContent(templateId!, scope!)}&path=${encodeURIComponent(path)}`;
    const response = await this.client.get<{ content: string }>(url);
    return response.content || '';
  }

  private async createTemplateFile(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { templateId, scope } = this.config;
    const baseUrl = API_ENDPOINTS.template.create(templateId!, scope!);
    // 後端期望使用 query 參數：path, entry_type, content
    const queryParams = new URLSearchParams();
    queryParams.append('path', request.path);
    queryParams.append('entry_type', request.isDirectory ? 'directory' : 'file');
    if (request.content) {
      queryParams.append('content', request.content);
    }
    const url = `${baseUrl}&${queryParams.toString()}`;
    return this.client.post(url);
  }

  private async updateTemplateFile(path: string, content: string): Promise<FileOperationResponse> {
    const { templateId, scope } = this.config;
    const baseUrl = API_ENDPOINTS.template.update(templateId!, scope!);
    // 後端期望使用 query 參數：path, content
    const queryParams = new URLSearchParams();
    queryParams.append('path', path);
    queryParams.append('content', content);
    const url = `${baseUrl}&${queryParams.toString()}`;
    return this.client.put(url);
  }

  private async deleteTemplateFile(path: string, recursive: boolean): Promise<FileOperationResponse> {
    const { templateId, scope } = this.config;
    const url = `${API_ENDPOINTS.template.delete(templateId!, scope!)}&path=${encodeURIComponent(path)}&recursive=${recursive}`;
    return this.client.delete(url);
  }

  private async batchDeleteTemplate(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    const { templateId, scope } = this.config;
    const url = API_ENDPOINTS.template.batchDelete(templateId!, scope!);
    return this.client.post(url, request);
  }

  private async renameTemplateFile(oldPath: string, newPath: string): Promise<FileOperationResponse> {
    // 重命名實際上是移動到同一目錄下的新名稱，使用 move API
    return this.moveTemplateFile(oldPath, newPath);
  }

  private async moveTemplateFile(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    const { templateId, scope } = this.config;
    const baseUrl = API_ENDPOINTS.template.move(templateId!, scope!);
    // 後端期望使用 query 參數：source_path, dest_path
    const queryParams = new URLSearchParams();
    queryParams.append('source_path', sourcePath);
    queryParams.append('dest_path', targetPath);
    const url = `${baseUrl}&${queryParams.toString()}`;
    return this.client.post(url);
  }

  private async uploadTemplateFiles(options: FileUploadOptions): Promise<FileUploadResult[]> {
    const { templateId, scope } = this.config;
    const url = API_ENDPOINTS.template.upload(templateId!, scope!);

    const formData = new FormData();
    formData.append('target_path', options.targetPath);
    formData.append('overwrite', 'false');
    options.files.forEach(file => formData.append('files', file));

    const response = await this.client.post<{
      success: boolean;
      uploaded: Array<{ filename: string; path: string; size: number; success: boolean; error?: string }>;
      total: number;
      succeeded: number;
      failed: number;
      message?: string;
    }>(url, formData);

    // 轉換後端返回的格式到前端期望的格式
    return response.uploaded?.map(item => ({
      fileName: item.filename,
      path: item.path,
      size: item.size,
      success: item.success,
      error: item.error,
    })) || [];
  }

  // ==================== Knowledge Base 實作 ====================

  private async getKnowledgeBaseTree(): Promise<FileTreeNode[]> {
    const { knowledgeBaseId, includeHidden } = this.config;
    const url = `${API_ENDPOINTS.knowledgeBase.getTree(knowledgeBaseId!)}?path=${encodeURIComponent('/')}&includeHidden=${String(includeHidden ?? false)}`;
    const response = await this.client.get<{ path: string; scope: string; nodes: FileTreeNode[]; total: number }>(url);
    return response.nodes || [];
  }

  private async getKnowledgeBaseContent(path: string): Promise<string> {
    const { knowledgeBaseId } = this.config;
    const url = `${API_ENDPOINTS.knowledgeBase.getContent(knowledgeBaseId!)}?path=${encodeURIComponent(path)}`;
    const response = await this.client.get<{ content: string }>(url);
    return response.content || '';
  }

  private async createKnowledgeBaseFile(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { knowledgeBaseId } = this.config;
    const formData = new FormData();
    formData.append('path', request.path);
    formData.append('type', request.isDirectory ? 'directory' : 'file');
    if (!request.isDirectory) {
      formData.append('content', request.content ?? '');
    }

    return this.client.post(API_ENDPOINTS.knowledgeBase.create(knowledgeBaseId!), formData);
  }

  private async updateKnowledgeBaseFile(path: string, content: string): Promise<FileOperationResponse> {
    const { knowledgeBaseId } = this.config;
    return this.client.put(API_ENDPOINTS.knowledgeBase.update(knowledgeBaseId!), { path, content });
  }

  private async deleteKnowledgeBaseFile(path: string, recursive: boolean): Promise<FileOperationResponse> {
    const { knowledgeBaseId } = this.config;
    const url = `${API_ENDPOINTS.knowledgeBase.delete(knowledgeBaseId!)}?path=${encodeURIComponent(path)}&recursive=${String(recursive)}`;
    return this.client.delete(url);
  }

  private async batchDeleteKnowledgeBase(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
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
        await this.deleteKnowledgeBaseFile(path, request.recursive ?? true);
        results.deleted.push(path);
        results.successCount += 1;
      } catch (error) {
        results.failed.push({
          path,
          error: error instanceof Error ? error.message : '刪除失敗',
        });
        results.failedCount += 1;
      }
    }

    results.success = results.failedCount === 0;
    return results;
  }

  private async renameKnowledgeBaseFile(oldPath: string, newPath: string): Promise<FileOperationResponse> {
    return this.moveKnowledgeBaseFile(oldPath, newPath);
  }

  private async moveKnowledgeBaseFile(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    const { knowledgeBaseId } = this.config;
    return this.client.patch(API_ENDPOINTS.knowledgeBase.move(knowledgeBaseId!), {
      sourcePath,
      destinationPath: targetPath,
      overwrite: false,
    });
  }

  private async uploadKnowledgeBaseFiles(options: FileUploadOptions): Promise<FileUploadResult[]> {
    const { knowledgeBaseId } = this.config;
    const formData = new FormData();
    formData.append('path', options.targetPath || '/');
    formData.append('overwrite', options.conflictStrategy === 'overwrite' ? 'true' : 'false');
    options.files.forEach((file) => formData.append('files', file));

    const response = await this.client.post<{
      total: number;
      succeeded: number;
      failed: number;
      results?: Array<{ filename: string; path: string; size: number; success: boolean; message?: string }>;
      uploaded?: Array<{ filename: string; path: string; size: number; success: boolean; error?: string }>;
    }>(API_ENDPOINTS.knowledgeBase.upload(knowledgeBaseId!), formData);

    const results = response.results ?? response.uploaded ?? [];
    return results.map((item) => ({
      fileName: item.filename,
      path: item.path,
      success: item.success,
      error: 'message' in item ? item.message : item.error,
    }));
  }

  // ==================== Claude Code 實作 ====================

  private getClaudeCodeCollection(): 'skills' | 'scripts' {
    // 從配置中取得 collection 類型
    const { collection } = this.config;
    if (!collection) {
      throw new Error('Claude Code collection type is required');
    }
    return collection;
  }

  private async getClaudeCodeTree(): Promise<FileTreeNode[]> {
    const { workspaceId, scope = 'project' } = this.config;
    const collection = this.getClaudeCodeCollection();
    const url = API_ENDPOINTS.claudeCode.getTree(workspaceId!, collection, scope);
    const response = await this.client.get<{
      path: string;
      scope: string;
      nodes: FileTreeNode[];
      total: number;
    }>(url);
    return response.nodes || [];
  }

  private async getClaudeCodeContent(path: string): Promise<string> {
    const { workspaceId, scope = 'project' } = this.config;
    const collection = this.getClaudeCodeCollection();
    const url = API_ENDPOINTS.claudeCode.getContent(workspaceId!, collection, path, scope);
    const response = await this.client.get<{ success: boolean; data: { content: string } }>(url);
    return response.data?.content || '';
  }

  private async createClaudeCodeFile(request: FileOperationRequest): Promise<FileOperationResponse> {
    const { workspaceId, scope = 'project' } = this.config;
    const collection = this.getClaudeCodeCollection();
    const baseUrl = API_ENDPOINTS.claudeCode.create(workspaceId!, collection, scope);
    // 使用 query 參數
    const url = `${baseUrl}&path=${encodeURIComponent(request.path)}&type=file${request.content ? `&content=${encodeURIComponent(request.content)}` : ''}`;
    return this.client.post(url);
  }

  private async updateClaudeCodeFile(path: string, content: string): Promise<FileOperationResponse> {
    const { workspaceId, scope = 'project' } = this.config;
    const collection = this.getClaudeCodeCollection();
    const baseUrl = API_ENDPOINTS.claudeCode.update(workspaceId!, collection, path, scope);
    // 使用 query 參數
    const url = `${baseUrl}&content=${encodeURIComponent(content)}`;
    return this.client.put(url);
  }

  private async deleteClaudeCodeFile(path: string, recursive = false): Promise<FileOperationResponse> {
    const { workspaceId, scope = 'project' } = this.config;
    const collection = this.getClaudeCodeCollection();
    const url = API_ENDPOINTS.claudeCode.delete(workspaceId!, collection, path, scope, recursive);
    return this.client.delete(url);
  }

  private async batchDeleteClaudeCode(request: BatchDeleteRequest): Promise<BatchDeleteResponse> {
    // Claude Code 不支援批次刪除，逐一刪除
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
        // 批次刪除時，預設使用 recursive=true 以刪除資料夾
        await this.deleteClaudeCodeFile(path, true);
        results.deleted.push(path);
        results.successCount++;
      } catch (error) {
        results.failed.push({
          path,
          error: error instanceof Error ? error.message : '刪除失敗',
        });
        results.failedCount++;
      }
    }

    results.success = results.failedCount === 0;
    return results;
  }

  private async moveClaudeCodeFileInternal(sourcePath: string, destPath: string): Promise<FileOperationResponse> {
    const { workspaceId, scope = 'project' } = this.config;
    const collection = this.getClaudeCodeCollection();
    // 使用新的統一 API：POST /move?sourcePath=...&destPath=...&sourceScope=...&destScope=...&overwrite=false
    const baseUrl = API_ENDPOINTS.claudeCode.move(workspaceId!, collection, scope);
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set('sourcePath', sourcePath);
    url.searchParams.set('destPath', destPath);
    url.searchParams.set('sourceScope', scope);
    url.searchParams.set('destScope', scope);
    url.searchParams.set('overwrite', 'false');
    return this.client.post(url.pathname + url.search);
  }

  private async renameClaudeCodeFile(oldPath: string, newPath: string): Promise<FileOperationResponse> {
    return this.moveClaudeCodeFileInternal(oldPath, newPath);
  }

  private async moveClaudeCodeFile(sourcePath: string, targetPath: string): Promise<FileOperationResponse> {
    return this.moveClaudeCodeFileInternal(sourcePath, targetPath);
  }

  private async copyClaudeCodeFile(sourcePath: string, destPath: string): Promise<FileOperationResponse> {
    const { workspaceId, scope = 'project' } = this.config;
    const collection = this.getClaudeCodeCollection();
    // 使用新的統一 API：POST /copy?sourcePath=...&destPath=...&sourceScope=...&destScope=...&overwrite=false
    const baseUrl = API_ENDPOINTS.claudeCode.copy(workspaceId!, collection, scope);
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set('sourcePath', sourcePath);
    url.searchParams.set('destPath', destPath);
    url.searchParams.set('sourceScope', scope);
    url.searchParams.set('destScope', scope);
    url.searchParams.set('overwrite', 'false');
    return this.client.post(url.pathname + url.search);
  }

  private async uploadClaudeCodeFiles(options: FileUploadOptions): Promise<FileUploadResult[]> {
    // Claude Code 上傳需要逐一建立檔案
    const results: FileUploadResult[] = [];

    for (const file of options.files) {
      try {
        const content = await file.text();
        const fileName = `${options.targetPath}/${file.name}`.replace(/^\/+/, '');

        await this.createClaudeCodeFile({
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
          error: error instanceof Error ? error.message : '上傳失敗',
        });
      }
    }

    return results;
  }
}
