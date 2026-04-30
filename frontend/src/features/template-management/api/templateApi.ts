/**
 * Template API Service
 */

import { apiClient } from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';
import type {
  CliType,
  TemplateFileNode,
  TemplateHook,
  TemplateMcpServer,
  TemplateOutputStyle,
  TemplateCommand,
  TemplateAgent,
} from '@/shared/types/templates';

const logger = createLogger('Template API');

// ============ Types ============

export interface TemplateAuthorInfo {
  name: string;
  email?: string;
  url?: string;
}

export interface TemplateBasicInfo {
  templateId: string;
  name: string;
  version: string;
  description?: string;
  author: TemplateAuthorInfo;
  keywords: string[];
  categoryId?: string;
  cli_type?: 'claude-code' | 'codex' | 'gemini' | 'opencode';
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
  agentsMd?: string;
  initCommands?: string;
  mcpServers?: TemplateMcpServer[];
  commands?: TemplateCommand[];
  hooks?: TemplateHook[];
  agents?: TemplateAgent[];
  outputStyle?: TemplateOutputStyle[];
  scripts?: TemplateFileNode[];
  skills?: TemplateFileNode[];
}

export interface CanonicalTemplateUpdatePayload {
  name: string;
  description?: string;
  version: string;
  author: TemplateAuthorInfo;
  keywords: string[];
  categoryId?: string;
  documentation?: string;
  agentsMd?: string;
  initCommands?: string;
  mcpServers: TemplateMcpServer[];
  commands: TemplateCommand[];
  hooks: TemplateHook[];
  agents: TemplateAgent[];
  outputStyle: TemplateOutputStyle[];
  skills: TemplateFileNode[];
  scripts: TemplateFileNode[];
  isActive?: boolean;
  cliType?: CliType;
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

export interface TemplateCompileIssue {
  feature: string;
  target: CliType;
  message: string;
}

export interface TemplateCompiledFile {
  path: string;
  source: string;
  content: string;
}

export interface TemplateCompilePreview {
  target: CliType;
  files: TemplateCompiledFile[];
  warnings: TemplateCompileIssue[];
  unsupported: TemplateCompileIssue[];
  degradationNotes: TemplateCompileIssue[];
  installHints: Record<string, unknown>;
  sourceHash?: string;
  cacheKey?: string;
}

// ============ API Functions ============

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

export async function getTemplate(templateId: string): Promise<TemplateResponse> {
  const response = await apiClient.get(`/templates/${templateId}`);
  return response;
}

export async function getTemplateCompilePreview(
  templateId: string,
  target: CliType,
): Promise<TemplateCompilePreview> {
  const response = await apiClient.get(
    `/templates/${templateId}/compile-preview?target=${encodeURIComponent(target)}`,
  );
  return response;
}

export async function createTemplate(data: TemplateBasicInfo): Promise<TemplateResponse> {
  const response = await apiClient.post('/templates/', data);
  return response;
}

export async function updateTemplate(
  templateId: string,
  data: Partial<TemplateBasicInfo>
): Promise<TemplateResponse> {
  const response = await apiClient.put(`/templates/${templateId}`, data);
  return response;
}

export async function updateCanonicalTemplate(
  templateId: string,
  data: CanonicalTemplateUpdatePayload,
): Promise<TemplateResponse> {
  const response = await apiClient.put(`/templates/${templateId}/canonical`, data);
  return response;
}

export async function deleteTemplate(templateId: string): Promise<void> {
  await apiClient.delete(`/templates/${templateId}`);
}

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

export async function exportTemplate(templateId: string, target?: CliType): Promise<Blob> {

  const suffix = target ? `?target=${encodeURIComponent(target)}` : '';
  return apiClient.getBlob(`/templates/${templateId}/export${suffix}`);
}

export async function importTemplate(file: File): Promise<{ success: boolean; message: string }> {
  const formData = new FormData();
  formData.append('file', file);


  return apiClient.post<{ success: boolean; message: string }>('/templates/import', formData);
}

export async function getMcpConfig(templateId: string): Promise<McpConfigResponse> {
  const response = await apiClient.get(`/templates/${templateId}/mcp`);
  return response;
}

export async function updateMcpConfig(
  templateId: string,
  config: McpServersConfig
): Promise<McpConfigResponse> {
  const response = await apiClient.put(`/templates/${templateId}/mcp`, config);
  return response;
}

export async function getHooksConfig(templateId: string): Promise<HooksConfigResponse> {
  const response = await apiClient.get(`/templates/${templateId}/hooks`);
  return response;
}

export async function updateHooksConfig(
  templateId: string,
  config: HooksConfig
): Promise<HooksConfigResponse> {
  const response = await apiClient.put(`/templates/${templateId}/hooks`, config);
  return response;
}

// ============ Commands API Functions ============

export async function getCommandsFiles(templateId: string): Promise<TemplateFileListResponse> {
  const response = await apiClient.get(`/templates/${templateId}/commands`);
  return response;
}

export async function getCommandFile(
  templateId: string,
  fileName: string
): Promise<TemplateFileResponse> {
  const response = await apiClient.get(`/templates/${templateId}/commands/${fileName}`);
  return response;
}

export async function createCommandFile(
  templateId: string,
  data: TemplateFileCreateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.post(`/templates/${templateId}/commands`, data);
  return response;
}

export async function updateCommandFile(
  templateId: string,
  fileName: string,
  data: TemplateFileUpdateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.put(`/templates/${templateId}/commands/${fileName}`, data);
  return response;
}

export async function deleteCommandFile(
  templateId: string,
  fileName: string
): Promise<void> {
  await apiClient.delete(`/templates/${templateId}/commands/${fileName}`);
}

// ============ Agents API Functions ============

export async function getAgentsFiles(templateId: string): Promise<TemplateFileListResponse> {
  const response = await apiClient.get(`/templates/${templateId}/agents`);
  return response;
}

export async function getAgentFile(
  templateId: string,
  fileName: string
): Promise<TemplateFileResponse> {
  const response = await apiClient.get(`/templates/${templateId}/agents/${fileName}`);
  return response;
}

export async function createAgentFile(
  templateId: string,
  data: TemplateFileCreateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.post(`/templates/${templateId}/agents`, data);
  return response;
}

export async function updateAgentFile(
  templateId: string,
  fileName: string,
  data: TemplateFileUpdateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.put(`/templates/${templateId}/agents/${fileName}`, data);
  return response;
}

export async function deleteAgentFile(
  templateId: string,
  fileName: string
): Promise<void> {
  await apiClient.delete(`/templates/${templateId}/agents/${fileName}`);
}

// ============ Output Style API Functions ============

export async function getOutputStyleFiles(templateId: string): Promise<TemplateFileListResponse> {
  const response = await apiClient.get(`/templates/${templateId}/output-style`);
  return response;
}

export async function getOutputStyleFile(
  templateId: string,
  fileName: string
): Promise<TemplateFileResponse> {
  const response = await apiClient.get(`/templates/${templateId}/output-style/${fileName}`);
  return response;
}

export async function createOutputStyleFile(
  templateId: string,
  data: TemplateFileCreateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.post(`/templates/${templateId}/output-style`, data);
  return response;
}

export async function updateOutputStyleFile(
  templateId: string,
  fileName: string,
  data: TemplateFileUpdateRequest
): Promise<TemplateFileResponse> {
  const response = await apiClient.put(`/templates/${templateId}/output-style/${fileName}`, data);
  return response;
}

export async function deleteOutputStyleFile(
  templateId: string,
  fileName: string
): Promise<void> {
  await apiClient.delete(`/templates/${templateId}/output-style/${fileName}`);
}

// ============ AGENTS.md API Functions ============

export interface AgentsMdResponse {
  success: boolean;
  data?: {
    content: string;
  };
  message?: string;
  error?: string;
}

export interface AgentsMdUpdateRequest {
  content: string;
}

export async function getAgentsMd(templateId: string): Promise<AgentsMdResponse> {
  const response = await apiClient.get(`/templates/${templateId}/agents-md`);
  return response;
}

export async function updateAgentsMd(
  templateId: string,
  data: AgentsMdUpdateRequest
): Promise<AgentsMdResponse> {
  const response = await apiClient.put(`/templates/${templateId}/agents-md`, data);
  return response;
}



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

export async function getFileContent(
  templateId: string,
  path: string,
  scope: string = 'scripts'
): Promise<FileContentResponse> {
  const response = await apiClient.get(`/templates/${templateId}/files/content?path=${encodeURIComponent(path)}&scope=${scope}`);
  return response;
}

export async function createFileOrDirectory(
  templateId: string,
  data: CreateFileRequest,
  scope: string = 'scripts'
): Promise<FileOperationResponse> {
  const queryParams = new URLSearchParams();
  queryParams.append('path', data.path);
  queryParams.append('entry_type', data.type);
  queryParams.append('scope', scope);
  if (data.content) queryParams.append('content', data.content);

  const response = await apiClient.post(`/templates/${templateId}/files?${queryParams.toString()}`);
  return response;
}

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

export async function deleteFile(
  templateId: string,
  path: string,
  recursive: boolean = false,
  scope: string = 'scripts'
): Promise<FileOperationResponse> {
  const response = await apiClient.delete(`/templates/${templateId}/files?path=${encodeURIComponent(path)}&recursive=${recursive}&scope=${scope}`);
  return response;
}

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
  agentsMd?: TemplateInstallItemResult;
  commands?: TemplateInstallItemResult;
  agents?: TemplateInstallItemResult;
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

export async function getTemplateFeatures(templateId: string): Promise<TemplateFeatureInfo> {
  const response = await apiClient.get(`/templates/${templateId}/features`);
  return response;
}

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
