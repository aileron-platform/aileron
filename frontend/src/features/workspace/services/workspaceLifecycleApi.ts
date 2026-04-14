/**
 * Workspace 生命週期 API 服務
 * 處理 workspace 的刪除和重啟操作
 */

import { apiClient } from '@/shared/api/apiClient';

/**
 * 刪除 workspace 回應
 */
export interface DeleteWorkspaceResponse {
  message: string;
  workspaceId: string;
  status: string;
}

/**
 * 重啟 workspace 回應
 */
export interface RebuildWorkspaceResponse {
  message: string;
  workspaceId: string;
  status: string;
}

/**
 * 重啟 Browser 容器回應
 */
export interface RestartBrowserResponse {
  message: string;
  workspaceId: string;
  status: string;
}

/**
 * 重啟 Runtime 回應
 */
export interface RestartRuntimeResponse {
  message: string;
  workspaceId: string;
  status: string;
}

/**
 * 重啟 Next.js 容器回應
 */
export interface RestartNextjsResponse {
  message: string;
  workspaceId: string;
  status: string;
}

/**
 * Workspace 生命週期 API
 */
export const workspaceLifecycleApi = {
  /**
   * 刪除工作區
   * 
   * 此操作會在背景執行以下步驟：
   * 1. 停止並刪除 Docker container
   * 2. 刪除掛載的資料目錄
   * 3. 刪除資料庫中的 workspace 記錄
   * 
   * @param workspaceId - Workspace ID
   * @returns 刪除操作回應
   */
  async deleteWorkspace(workspaceId: string): Promise<DeleteWorkspaceResponse> {
    return await apiClient.delete<DeleteWorkspaceResponse>(`/workspaces/${workspaceId}`);
  },

  /**
   * 重啟工作區 Container
   *
   * 此操作會在背景執行以下步驟：
   * 1. 重啟 Docker container
   * 2. 更新 workspace 狀態
   *
   * @param workspaceId - Workspace ID
   * @returns 重啟操作回應
   */
  async rebuildWorkspace(workspaceId: string): Promise<RebuildWorkspaceResponse> {
    return await apiClient.post<RebuildWorkspaceResponse>(`/workspaces/${workspaceId}/rebuild`);
  },

  /**
   * 重啟工作區 Runtime
   *
   * 目前與整體 workspace restart 共用後端 rebuild endpoint。
   */
  async restartRuntime(workspaceId: string): Promise<RestartRuntimeResponse> {
    return await apiClient.post<RestartRuntimeResponse>(`/workspaces/${workspaceId}/rebuild`);
  },

  /**
   * 重啟整體工作區
   *
   * 目前與 rebuild 共用後端 endpoint。
   */
  async restartWorkspace(workspaceId: string): Promise<RebuildWorkspaceResponse> {
    return await apiClient.post<RebuildWorkspaceResponse>(`/workspaces/${workspaceId}/rebuild`);
  },

  /**
   * 重啟工作區的 Browser 容器
   *
   * 此操作會在背景執行以下步驟：
   * 1. 重啟 Browser Docker container
   * 2. 更新 browser_status 狀態
   *
   * @param workspaceId - Workspace ID
   * @returns 重啟操作回應
   */
  async restartBrowserContainer(workspaceId: string): Promise<RestartBrowserResponse> {
    return await apiClient.post<RestartBrowserResponse>(`/workspaces/${workspaceId}/restart-browser`);
  },

  /**
   * 重啟工作區的 Next.js 容器
   *
   * @param workspaceId - Workspace ID
   * @returns 重啟操作回應
   */
  async restartNextjsContainer(workspaceId: string): Promise<RestartNextjsResponse> {
    return await apiClient.post<RestartNextjsResponse>(`/workspaces/${workspaceId}/restart-nextjs`);
  },
};

export default workspaceLifecycleApi;
