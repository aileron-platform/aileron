/**
 * 模板 Git 版本控制 API
 */

import { apiClient } from '@/shared/api/apiClient';

// ============ 型別定義 ============

export interface GitStatus {
  current_branch: string;
  has_changes: boolean;
  ahead_count: number;
  behind_count: number;
  remote_url: string | null;
  is_git_repo: boolean;
}

export interface TemplateChange {
  template_id: string;
  template_name: string;
  status: 'modified' | 'added' | 'deleted' | 'untracked';
  changed_files: string[];
  changed_dirs: string[];
}

export interface GitChangeLog {
  templates: TemplateChange[];
  total_changes: number;
  has_staged: boolean;
  has_unstaged: boolean;
}

export interface GitBranch {
  name: string;
  is_current: boolean;
  is_remote: boolean;
}

export interface GitBranchList {
  branches: GitBranch[];
  current_branch: string;
}

export interface GitCommitRequest {
  message: string;
  branch?: string;
  push?: boolean;
}

export interface GitPullRequest {
  branch?: string;
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

export interface GitStatusResponse {
  success: boolean;
  data?: GitStatus;
  error?: string;
}

export interface GitChangeLogResponse {
  success: boolean;
  data?: GitChangeLog;
  error?: string;
}

export interface GitBranchListResponse {
  success: boolean;
  data?: GitBranchList;
  error?: string;
}

// ============ API 方法 ============

/**
 * 取得 Git 倉庫狀態
 */
export async function getGitStatus(): Promise<GitStatusResponse> {
  return apiClient.get<GitStatusResponse>('/templates/git/status');
}

/**
 * 取得變更記錄
 */
export async function getGitChanges(): Promise<GitChangeLogResponse> {
  return apiClient.get<GitChangeLogResponse>('/templates/git/changes');
}

/**
 * 取得分支列表
 */
export async function getGitBranches(): Promise<GitBranchListResponse> {
  return apiClient.get<GitBranchListResponse>('/templates/git/branches');
}

/**
 * 提交並推送變更（本地同步遠端）
 */
export async function commitAndPush(request: GitCommitRequest): Promise<GitOperationResponse> {
  return apiClient.post<GitOperationResponse>('/templates/git/commit', request);
}

/**
 * 從遠端拉取變更（遠端同步本地）
 */
export async function pullFromRemote(request: GitPullRequest): Promise<GitOperationResponse> {
  return apiClient.post<GitOperationResponse>('/templates/git/pull', request);
}

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
