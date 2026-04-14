/**
 * Template API Service
 * 模板中心 API 服務
 */

import { apiClient } from '@/shared/api/apiClient';
import { createLogger } from './logger';
import type {
  TemplateHook,
  TemplateMcpServer,
  TemplateSlashCommand,
  TemplateSubAgent,
  TemplateOutputStyle,
  TemplateFileNode,
} from '@/shared/types/templates';

const logger = createLogger('Template API');

// ============ Types ============

export interface TemplateAuthorInfo {
  name: string;
  email?: string;
  url?: string;
}

export interface TemplateBasicInfo {
  templateId: string; // 模板代號
  name: string; // 模板名稱
  version: string;
  description?: string;
  author: TemplateAuthorInfo;
  keywords: string[];
  categoryId?: string;
  cli_type?: 'claude-code' | 'codex' | 'gemini';
  initCommands?: string;
}

export interface McpServer {
  description: string;
  type: 'stdio' | 'http' | 'sse';
  command?: string;
  args?: string[];
  env?: Record<string, string>;
  url?: string;
  headers?: Record<string, string>;
}

export interface McpServersConfig {
  mcpServers: Record<string, McpServer>;
}

export interface HookAction {
  type: 'command' | 'webhook' | 'mcp_call';
  command?: string;
  timeout?: number;
  url?: string;
  method?: string;
  headers?: Record<string, string>;
}

export interface HookRule {
  matcher: string;
  hooks: HookAction[];
}

export interface HooksConfig {
  hooks: Record<string, HookRule[]>;
}

export interface TemplateResponse {
  id: string;
  name: string;
  description?: string;
  version: string;
  author: TemplateAuthorInfo;
  keywords: string[];
  categoryId?: string;
  cli_type: string;
  status: 'draft' | 'released';
  created_at: string;
  updated_at: string;
  storagePath: string;
  documentation?: string;
  claudeMd?: string;
  initCommands?: string;
  mcpServers?: TemplateMcpServer[];
  slashCommands?: TemplateSlashCommand[];
  hooks?: TemplateHook[];
  subAgents?: TemplateSubAgent[];
  outputStyles?: TemplateOutputStyle[];
  scripts?: TemplateFileNode[];
  skills?: TemplateFileNode[];
}

export interface McpConfigResponse {
  templateId: string;
  mcpServers: Record<string, McpServer>;
}

export interface HooksConfigResponse {
  templateId: string;
  hooks: Record<string, HookRule[]>;
}

// ============ Feature Indexing Types ============

export interface TemplateFeatureInfo {
  templateId: string;
  features: string[];
  indexedAt?: string;
}

export interface FeatureStatItem {
  name: string;
  count: number;
  description?: string;
}

export interface FeatureStatsResponse {
  stats: Record<string, FeatureStatItem>;
}

// ============ Commands & Agents Types ============

export interface TemplateFile {
  file_name: string;
  size: number;
  last_modified: string;
}

export interface TemplateFileContent extends TemplateFile {
  content: string;
}

export interface TemplateFileCreateRequest {
  file_name: string;
  content: string;
}

export interface TemplateFileUpdateRequest {
  content: string;
}

export interface TemplateFileResponse {
  success: boolean;
  data?: TemplateFileContent;
  message?: string;
  error?: string;
}

export interface TemplateFileListResponse {
  success: boolean;
  data: TemplateFile[];
  message?: string;
  error?: string;
}

// ============ API Functions ============

/**
 * 取得模板列表
 */
export async function listTemplates(params?: {
  category?: string;
  cli_type?: string;
  keywords?: string[];
  search?: string;
  features?: string[];
  page?: number;
  limit?: number;
}): Promise<{ items: TemplateResponse[]; total: number; page: number; limit: number }> {
  const queryParams = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        if (Array.isArray(value)) {
          queryParams.append(key, value.join(','));
        } else {
          queryParams.append(key, String(value));
        }
      }
    });
  }

  const queryString = queryParams.toString();
  const url = queryString ? `/templates/?${queryString}` : '/templates/';

  const response = await apiClient.get(url);
  return response;
}

/**
 * 取得模板詳情
 */
export async function getTemplate(templateId: string): Promise<TemplateResponse> {
  const response = await apiClient.get(`/templates/${templateId}`);
  return response;
}

/**
 * 建立模板
 */
export async function createTemplate(data: TemplateBasicInfo): Promise<TemplateResponse> {
  const response = await apiClient.post('/templates/', data);
  return response;
}

/**
 * 更新模板基本資訊
 */
export async function updateTemplate(
  templateId: string,
  data: Partial<TemplateBasicInfo>
): Promise<TemplateResponse> {
  const response = await apiClient.put(`/templates/${templateId}`, data);
  return response;
}

/**
 * 刪除模板
 */
export async function deleteTemplate(templateId: string): Promise<void> {
  await apiClient.delete(`/templates/${templateId}`);
}

/**
 * 取得認證 Token
 */
function getAuthToken(): string | null {
  try {
    const stored = window.sessionStorage.getItem('oidc_tokens');
    if (!stored) {
      return null;
    }
    const parsed = JSON.parse(stored) as { access_token?: string };
    return parsed.access_token || null;
  } catch (error) {
    logger.warn('Failed to get auth token', { error });
    return null;
  }
}

/**
 * 匯出模板
 */
export async function exportTemplate(templateId: string): Promise<Blob> {
  // 使用 ApiClient.getBlob 來確保請求攜帶 Authorization header
  return apiClient.getBlob(`/templates/${templateId}/export`);
}

/**
 * 匯入模板
 */
export async function importTemplate(file: File): Promise<{ success: boolean; message: string }> {
  const formData = new FormData();
  formData.append('file', file);

  // 使用 ApiClient.post 來確保請求攜帶 Authorization header
  return apiClient.post<{ success: boolean; message: string }>('/templates/import', formData);
}

/**
 * 取得模板的 MCP 配置
 */
export async function getMcpConfig(templateId: string): Promise<McpConfigResponse> {
  const response = await apiClient.get(`/templates/${templateId}/mcp`);
  return response;
}

/**
 * 更新模板的 MCP 配置
 */
export async function updateMcpConfig(
  templateId: string,
  config: McpServersConfig
): Promise<McpConfigResponse> {
  const response = await apiClient.put(`/templates/${templateId}/mcp`, config);
  return response;
}

/**
 * 取得模板的 Hooks 配置
 */
export async function getHooksConfig(templateId: string): Promise<HooksConfigResponse> {
  const response = await apiClient.get(`/templates/${templateId}/hooks`);
  return response;
}

/**
 * 更新模板的 Hooks 配置
 */
export async function updateHooksConfig(
  templateId: string,
  config: HooksConfig
): Promise<HooksConfigResponse> {
  const response = await apiClient.put(`/templates/${templateId}/hooks`, config);
  return response;
}

// ============ SlashCommands API Functions ============

/**
 * 取得模板的 SlashCommands 檔案列表
 */
export async function getSlashCommandsFiles(templateId: string): Promise<TemplateFileListResponse> {
  const response = await apiClient.get(`/templates/${templateId}/slash-commands`);
  return response;
}

/**
 * 取得特定 SlashCommand 檔案內容
 */
export async function getSlashCommandFile(
  templateId: string,
  fileName: string
): Promise<TemplateFileResponse> {
  const response = await apiClient.get(`/templates/${templateId}/slash-commands/${fileName}`);
  return response;
}

/**
 * 新增 SlashCommand 檔案
 */
export async function createSlashCommandFile(
  templateId: string,
  data: TemplateFileCreateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.post(`/templates/${templateId}/slash-commands`, data);
  return response;
}

/**
 * 更新 SlashCommand 檔案
 */
export async function updateSlashCommandFile(
  templateId: string,
  fileName: string,
  data: TemplateFileUpdateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.put(`/templates/${templateId}/slash-commands/${fileName}`, data);
  return response;
}

/**
 * 刪除 SlashCommand 檔案
 */
export async function deleteSlashCommandFile(
  templateId: string,
  fileName: string
): Promise<void> {
  await apiClient.delete(`/templates/${templateId}/slash-commands/${fileName}`);
}

// ============ SubAgents API Functions ============

/**
 * 取得模板的 SubAgents 檔案列表
 */
export async function getSubAgentsFiles(templateId: string): Promise<TemplateFileListResponse> {
  const response = await apiClient.get(`/templates/${templateId}/subagents`);
  return response;
}

/**
 * 取得特定 SubAgent 檔案內容
 */
export async function getSubAgentFile(
  templateId: string,
  fileName: string
): Promise<TemplateFileResponse> {
  const response = await apiClient.get(`/templates/${templateId}/subagents/${fileName}`);
  return response;
}

/**
 * 新增 SubAgent 檔案
 */
export async function createSubAgentFile(
  templateId: string,
  data: TemplateFileCreateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.post(`/templates/${templateId}/subagents`, data);
  return response;
}

/**
 * 更新 SubAgent 檔案
 */
export async function updateSubAgentFile(
  templateId: string,
  fileName: string,
  data: TemplateFileUpdateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.put(`/templates/${templateId}/subagents/${fileName}`, data);
  return response;
}

/**
 * 刪除 SubAgent 檔案
 */
export async function deleteSubAgentFile(
  templateId: string,
  fileName: string
): Promise<void> {
  await apiClient.delete(`/templates/${templateId}/subagents/${fileName}`);
}

// ============ OutputStyles API Functions ============

/**
 * 取得模板的 OutputStyles 檔案列表
 */
export async function getOutputStylesFiles(templateId: string): Promise<TemplateFileListResponse> {
  const response = await apiClient.get(`/templates/${templateId}/output-styles`);
  return response;
}

/**
 * 取得特定 OutputStyle 檔案內容
 */
export async function getOutputStyleFile(
  templateId: string,
  fileName: string
): Promise<TemplateFileResponse> {
  const response = await apiClient.get(`/templates/${templateId}/output-styles/${fileName}`);
  return response;
}

/**
 * 新增 OutputStyle 檔案
 */
export async function createOutputStyleFile(
  templateId: string,
  data: TemplateFileCreateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.post(`/templates/${templateId}/output-styles`, data);
  return response;
}

/**
 * 更新 OutputStyle 檔案
 */
export async function updateOutputStyleFile(
  templateId: string,
  fileName: string,
  data: TemplateFileUpdateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.put(`/templates/${templateId}/output-styles/${fileName}`, data);
  return response;
}

/**
 * 刪除 OutputStyle 檔案
 */
export async function deleteOutputStyleFile(
  templateId: string,
  fileName: string
): Promise<void> {
  await apiClient.delete(`/templates/${templateId}/output-styles/${fileName}`);
}

// ============ Claude.md API Functions ============

export interface ClaudeMdResponse {
  success: boolean;
  data?: {
    content: string;
  };
  message?: string;
  error?: string;
}

export interface ClaudeMdUpdateRequest {
  content: string;
}

/**
 * 取得模板的 Claude.md 內容
 */
export async function getClaudeMd(templateId: string): Promise<ClaudeMdResponse> {
  const response = await apiClient.get(`/templates/${templateId}/claude-md`);
  return response;
}

/**
 * 更新模板的 Claude.md 內容
 */
export async function updateClaudeMd(
  templateId: string,
  data: ClaudeMdUpdateRequest
): Promise<ClaudeMdResponse> {
  const response = await apiClient.put(`/templates/${templateId}/claude-md`, data);
  return response;
}

// ============ 檔案管理 API Functions ============

export interface FileNodeInfo {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  content?: string;
  extension?: string;
  created_at?: string;
  modified_at?: string;
  children?: FileNodeInfo[];
}

export interface TemplateFilesResponse {
  success: boolean;
  data?: FileNodeInfo[];
  total_files: number;
  total_size: number;
  message?: string;
  error?: string;
}

export interface FileContentResponse {
  success: boolean;
  data?: FileNodeInfo;
  message?: string;
  error?: string;
}

export interface CreateFileRequest {
  path: string;
  type: 'file' | 'directory';
  content?: string;
}

export interface UpdateFileContentRequest {
  path: string;
  content: string;
}

export interface FileOperationResponse {
  success: boolean;
  data?: FileNodeInfo;
  message?: string;
  error?: string;
}

export interface UploadedFileInfo {
  filename: string;
  path: string;
  size: number;
  success: boolean;
  error?: string;
}

export interface FileUploadResponse {
  success: boolean;
  uploaded: UploadedFileInfo[];
  total: number;
  succeeded: number;
  failed: number;
  message?: string;
}

export interface RenameFileRequest {
  old_path: string;
  new_name: string;
}

export interface MoveFileRequest {
  source_path: string;
  target_path: string;
  overwrite?: boolean;
}

export interface CopyFileRequest {
  source_path: string;
  target_path: string;
  overwrite?: boolean;
}

export interface BatchDeleteRequest {
  paths: string[];
  recursive?: boolean;
}

export interface BatchOperationResult {
  path: string;
  success: boolean;
  error?: string;
}

export interface BatchOperationResponse {
  success: boolean;
  results: BatchOperationResult[];
  total: number;
  succeeded: number;
  failed: number;
  message?: string;
}

export interface FileSearchRequest {
  query: string;
  path?: string;
  scope?: string;
  fileTypes?: string[];
  searchContent?: boolean;
  caseSensitive?: boolean;
  maxResults?: number;
}

export interface FileSearchResult {
  path: string;
  name: string;
  type: 'file' | 'directory';
  size: number;
  updatedAt: string;
  matches?: string[];
}

export interface FileSearchResponse {
  query: string;
  path: string;
  scope?: string;
  results: FileSearchResult[];
  total: number;
}

/**
 * 取得模板檔案樹
 */
export async function getTemplateFiles(
  templateId: string,
  params?: {
    path?: string;
    include_hidden?: boolean;
    max_depth?: number;
    scope?: string;
  }
): Promise<TemplateFilesResponse> {
  const queryParams = new URLSearchParams();
  if (params?.path) queryParams.append('path', params.path);
  if (params?.include_hidden !== undefined) queryParams.append('include_hidden', String(params.include_hidden));
  if (params?.max_depth !== undefined) queryParams.append('max_depth', String(params.max_depth));
  if (params?.scope) queryParams.append('scope', params.scope);

  const queryString = queryParams.toString();
  const url = queryString ? `/templates/${templateId}/files/tree?${queryString}` : `/templates/${templateId}/files/tree`;

  const response = await apiClient.get(url);
  return response;
}

/**
 * 取得檔案內容
 */
export async function getFileContent(
  templateId: string,
  path: string,
  scope: string = 'scripts'
): Promise<FileContentResponse> {
  const response = await apiClient.get(`/templates/${templateId}/files/content?path=${encodeURIComponent(path)}&scope=${scope}`);
  return response;
}

/**
 * 建立檔案或目錄
 */
export async function createFileOrDirectory(
  templateId: string,
  data: CreateFileRequest,
  scope: string = 'scripts'
): Promise<FileOperationResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('path', data.path);
  queryParams.append('entry_type', data.type);  // 修正：使用 entry_type 而非 type
  queryParams.append('scope', scope);
  if (data.content) queryParams.append('content', data.content);

  const response = await apiClient.post(`/templates/${templateId}/files?${queryParams.toString()}`);
  return response;
}

/**
 * 更新檔案內容
 */
export async function updateFileContent(
  templateId: string,
  data: UpdateFileContentRequest,
  scope: string = 'scripts'
): Promise<FileOperationResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('path', data.path);
  queryParams.append('content', data.content);
  queryParams.append('scope', scope);

  const response = await apiClient.put(`/templates/${templateId}/files/content?${queryParams.toString()}`);
  return response;
}

/**
 * 上傳檔案
 */
export async function uploadFiles(
  templateId: string,
  files: File[],
  targetPath: string = '',
  overwrite: boolean = false,
  scope: string = 'scripts'
): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append('target_path', targetPath);
  formData.append('overwrite', String(overwrite));
  files.forEach(file => {
    formData.append('files', file);
  });

  const response = await apiClient.post(`/templates/${templateId}/files/upload?scope=${scope}`, formData);
  return response;
}

/**
 * 重命名檔案或目錄（已廢棄，使用 moveFile 代替）
 * @deprecated 請使用 moveFile
 */
export async function renameFile(
  templateId: string,
  data: RenameFileRequest,
  scope: string = 'scripts'
): Promise<FileOperationResponse> {
  // 重命名實際上是移動到同一目錄下的新名稱
  const oldPath = data.old_path;
  const newPath = oldPath.substring(0, oldPath.lastIndexOf('/') + 1) + data.new_name;
  return moveFile(templateId, { source_path: oldPath, dest_path: newPath }, scope);
}

/**
 * 移動檔案或目錄
 */
export async function moveFile(
  templateId: string,
  data: MoveFileRequest,
  scope: string = 'scripts'
): Promise<FileOperationResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('source_path', data.source_path);
  queryParams.append('dest_path', data.dest_path);
  queryParams.append('scope', scope);
  if (data.overwrite !== undefined) queryParams.append('overwrite', String(data.overwrite));

  const response = await apiClient.post(`/templates/${templateId}/files/move?${queryParams.toString()}`);
  return response;
}

/**
 * 複製檔案或目錄
 */
export async function copyFile(
  templateId: string,
  data: CopyFileRequest,
  scope: string = 'scripts'
): Promise<FileOperationResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('source_path', data.source_path);
  queryParams.append('dest_path', data.dest_path);
  queryParams.append('scope', scope);
  if (data.overwrite !== undefined) queryParams.append('overwrite', String(data.overwrite));

  const response = await apiClient.post(`/templates/${templateId}/files/copy?${queryParams.toString()}`);
  return response;
}

/**
 * 刪除檔案或目錄
 */
export async function deleteFile(
  templateId: string,
  path: string,
  recursive: boolean = false,
  scope: string = 'scripts'
): Promise<FileOperationResponse> {
  const response = await apiClient.delete(`/templates/${templateId}/files?path=${encodeURIComponent(path)}&recursive=${recursive}&scope=${scope}`);
  return response;
}

/**
 * 批次刪除檔案
 */
export async function batchDeleteFiles(
  templateId: string,
  data: BatchDeleteRequest,
  scope: string = 'scripts'
): Promise<BatchOperationResponse> {
  const queryParams = new URLSearchParams();
  data.paths.forEach(path => queryParams.append('paths', path));
  queryParams.append('scope', scope);

  const response = await apiClient.post(`/templates/${templateId}/files/batch-delete?${queryParams.toString()}`);
  return response;
}

/**
 * 搜尋檔案
 */
export async function searchFiles(
  templateId: string,
  data: FileSearchRequest,
  scope: string = 'scripts'
): Promise<FileSearchResponse> {
  const response = await apiClient.post(`/templates/${templateId}/files/search?scope=${scope}`, data);
  return response;
}

// ============ Template Installation ============

export interface TemplateInstallRequest {
  templateId: string;
  workspaceId: string;
}

export interface TemplateInstallItemResult {
  success: boolean;
  created: number;
  updated: number;
  failed: number;
}

export interface TemplateInstallResults {
  claudeMd?: TemplateInstallItemResult;
  slashCommands?: TemplateInstallItemResult;
  subagents?: TemplateInstallItemResult;
  mcp?: TemplateInstallItemResult;
  hooks?: TemplateInstallItemResult;
  scripts?: TemplateInstallItemResult;
}

export interface TemplateInstallResponse {
  success: boolean;
  message: string;
  templateId: string;
  templateName: string;
  workspaceId: string;
  results?: TemplateInstallResults;
  error?: string;
}

/**
 * 安裝模板到 Workspace
 */
export async function installTemplate(
  templateId: string,
  workspaceId: string
): Promise<TemplateInstallResponse> {
  const response = await apiClient.post<TemplateInstallResponse>('/templates/install', {
    templateId,
    workspaceId,
  });
  return response;
}

// ============ Feature Indexing API ============

/**
 * 查詢模板已索引的 Feature
 */
export async function getTemplateFeatures(templateId: string): Promise<TemplateFeatureInfo> {
  const response = await apiClient.get(`/templates/${templateId}/features`);
  return response;
}

/**
 * 取得 Feature 統計資訊
 */
export async function getFeatureStats(cliType?: string): Promise<FeatureStatsResponse> {
  const queryParams = new URLSearchParams();
  if (cliType) {
    queryParams.append('cli_type', cliType);
  }

  const queryString = queryParams.toString();
  const url = queryString ? `/templates/features/stats?${queryString}` : '/templates/features/stats';

  const response = await apiClient.get(url);
  return response;
}
