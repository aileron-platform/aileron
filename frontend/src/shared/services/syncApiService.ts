/**
 * 同步 API 服務
 * 負責將設定同步到 workspace-runtime
 */

import { apiClient } from '@/shared/api/apiClient';

export interface SyncWorkspaceResult {
  workspace_id: string;
  workspace_name: string;
  success: boolean;
  details?: {
    ssh: { success: boolean; message: string };
    claude_code: { success: boolean; message: string };
    git: { success: boolean; message: string };
  };
  error?: string;
}

export interface SyncResponse {
  success: boolean;
  message: string;
  workspaces: SyncWorkspaceResult[];
}

export class SyncApiService {
  /**
   * 同步設定到所有運行中的 workspace
   */
  static async syncSettingsToWorkspaces(userId: string): Promise<SyncResponse> {
    const response = await apiClient.post<SyncResponse>(
      `/users/${userId}/settings/sync`,
      {}
    );
    return response;
  }

  /**
   * 同步設定到指定的 workspace
   */
  static async syncSettingsToWorkspace(userId: string, workspaceId: string): Promise<SyncWorkspaceResult> {
    const response = await apiClient.post<SyncWorkspaceResult>(
      `/users/${userId}/settings/sync/${workspaceId}`,
      {}
    );
    return response;
  }
}

export default SyncApiService;

