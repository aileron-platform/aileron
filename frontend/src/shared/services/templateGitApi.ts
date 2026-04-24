/**
 * 模板 Git 版本控制 API
 */

import { apiClient } from '@/shared/api/apiClient';
import type {
  VersionControlBranch,
  VersionControlChangesResponse,
  VersionControlCommitFilesResponse,
  VersionControlCommitListResponse,
  VersionControlStatus,
  VersionControlDiffResponse,
} from '@/shared/types/versionControl';

// ============ 型別定義 ============

export interface GitCommitRequest {
  message: string;
  paths?: string[];
}

export interface GitOperationResponse {
  success: boolean;
  message: string;
  data?: any;
  error?: string;
}

export interface GitUserConfig {
  userName: string | null;
  userEmail: string | null;
}

export interface GitUserConfigResponse {
  success: boolean;
  data?: GitUserConfig;
  error?: string;
}

export interface GitUserConfigRequest {
  userName: string;
  userEmail: string;
}

export interface GitRemoteUrlRequest {
  remoteUrl: string;
}

export interface GitCloneRequest {
  url: string;
  branch?: string;
}

// ============ API 方法 ============

/**
 * 取得 Git 全域使用者設定
 */
export async function getGitUserConfig(): Promise<GitUserConfigResponse> {
  return apiClient.get<GitUserConfigResponse>('/templates/git/user-config');
}

/**
 * 更新 Git 全域使用者設定
 */
export async function updateGitUserConfig(request: GitUserConfigRequest): Promise<GitOperationResponse> {
  return apiClient.post<GitOperationResponse>('/templates/git/user-config', request);
}

/**
 * 設定 Git 遠端倉庫 URL
 */
export async function setGitRemoteUrl(request: GitRemoteUrlRequest): Promise<GitOperationResponse> {
  return apiClient.post<GitOperationResponse>('/templates/git/remote-url', request);
}

/**
 * Clone Git 遠端倉庫（後台任務）
 */
export async function cloneRepository(request: GitCloneRequest): Promise<{
  success: boolean;
  task_id?: string;
  message?: string;
  error?: string;
}> {
  return apiClient.post<{
    success: boolean;
    task_id?: string;
    message?: string;
    error?: string;
  }>('/templates/git/clone', request);
}

/**
 * 查詢 Clone 任務進度
 */
export interface TaskProgress {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  message: string;
  error: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result: {
    message?: string;
    synced_count?: number;
  } | null;
}

export async function getCloneProgress(taskId: string): Promise<{
  success: boolean;
  data?: TaskProgress;
  error?: string;
}> {
  return apiClient.get<{
    success: boolean;
    data?: TaskProgress;
    error?: string;
  }>(`/templates/git/clone/progress/${taskId}`);
}

/**
 * 檢查倉庫是否已 Clone
 */
export interface CloneStatus {
  is_cloned: boolean;
  remote_url?: string;
  current_branch?: string;
}

export async function checkCloneStatus(): Promise<{
  success: boolean;
  data?: CloneStatus;
  error?: string;
}> {
  return apiClient.get<{
    success: boolean;
    data?: CloneStatus;
    error?: string;
  }>('/templates/git/clone/status');
}

/**
 * 重建資料庫模板資料（後台任務）
 */
export async function rebuildTemplates(): Promise<{
  success: boolean;
  task_id?: string;
  message?: string;
  error?: string;
}> {
  return apiClient.post<{
    success: boolean;
    task_id?: string;
    message?: string;
    error?: string;
  }>('/templates/rebuild', {});
}

/**
 * 查詢重建任務進度
 */
export async function getRebuildProgress(taskId: string): Promise<{
  success: boolean;
  data?: TaskProgress;
  error?: string;
}> {
  return apiClient.get<{
    success: boolean;
    data?: TaskProgress;
    error?: string;
  }>(`/templates/rebuild/progress/${taskId}`);
}

export interface TemplateCheckoutRequest {
  create?: boolean;
  startPoint?: string;
  stashChanges?: boolean;
}

export interface TemplateRemoteRequest {
  remote?: string;
  branch?: string;
  rebase?: boolean;
  autostash?: boolean;
  force?: boolean;
}

const templateVersionControlBase = '/templates/git/version-control';

export const templateVersionControlApi = {
  getStatus: () => apiClient.get<VersionControlStatus>(`${templateVersionControlBase}/status`),
  getChanges: (page = 1, pageSize = 100) =>
    apiClient.get<VersionControlChangesResponse>(`${templateVersionControlBase}/changes?page=${page}&pageSize=${pageSize}`),
  getBranches: async () => {
    const response = await apiClient.get<{ branches: VersionControlBranch[] }>(`${templateVersionControlBase}/branches`);
    return response.branches ?? [];
  },
  checkoutBranch: (branch: string, payload: TemplateCheckoutRequest) =>
    apiClient.post<{ branch: string; created: boolean; stashedChanges?: string | null }>(
      `${templateVersionControlBase}/branches/${encodeURIComponent(branch)}/checkout`,
      payload,
    ),
  stage: (paths: string[]) =>
    apiClient.post<{ staged: string[]; unstaged: string[] }>(`${templateVersionControlBase}/stage`, {
      paths,
      includeUntracked: true,
    }),
  unstage: (paths: string[]) =>
    apiClient.post<{ unstaged: string[]; remainingStaged: number }>(`${templateVersionControlBase}/unstage`, { paths }),
  discard: (paths: string[]) =>
    apiClient.post<{ discarded: string[]; warnings: string[] }>(`${templateVersionControlBase}/discard`, { paths }),
  commit: (message: string, paths?: string[]) =>
    apiClient.post<{ commit: unknown }>(`${templateVersionControlBase}/commit`, { message, paths }),
  getCommits: (page = 1, pageSize = 20, branch?: string) => {
    const params = new URLSearchParams();
    params.set('page', String(page));
    params.set('pageSize', String(pageSize));
    if (branch) params.set('branch', branch);
    return apiClient.get<VersionControlCommitListResponse>(`${templateVersionControlBase}/commits?${params}`);
  },
  getCommitFiles: (commitId: string) =>
    apiClient.get<VersionControlCommitFilesResponse>(`${templateVersionControlBase}/commits/${encodeURIComponent(commitId)}/files`),
  getDiff: (path: string, head: 'INDEX' | 'WORKTREE' = 'WORKTREE') =>
    apiClient.get<VersionControlDiffResponse>(
      `${templateVersionControlBase}/diff?path=${encodeURIComponent(path)}&head=${encodeURIComponent(head)}`,
    ),
  fetch: (payload: TemplateRemoteRequest = {}) =>
    apiClient.post<{ remote: string; branch?: string | null; message: string }>(`${templateVersionControlBase}/fetch`, payload),
  pull: (payload: TemplateRemoteRequest = {}) =>
    apiClient.post<{ remote: string; branch?: string | null; message: string }>(`${templateVersionControlBase}/pull`, payload),
  push: (payload: TemplateRemoteRequest = {}) =>
    apiClient.post<{ remote: string; branch?: string | null; message: string }>(`${templateVersionControlBase}/push`, payload),
};
