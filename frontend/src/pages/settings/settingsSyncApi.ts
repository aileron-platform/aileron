import { apiClient } from '@/shared/api/apiClient';

export interface SyncWorkspaceResult {
  workspace_id: string;
  workspace_name: string;
  success: boolean;
  details?: {
    ssh: { success: boolean; message: string };
    claude_code: { success: boolean; message: string };
    codex?: { success: boolean; message: string };
    git: { success: boolean; message: string };
  };
  error?: string;
}

export interface SyncResponse {
  success: boolean;
  message: string;
  workspaces: SyncWorkspaceResult[];
}

export const syncSettingsToWorkspaces = async (
  userId: string,
): Promise<SyncResponse> => (
  apiClient.post<SyncResponse>(
    `/users/${userId}/settings/sync`,
    {},
  )
);
