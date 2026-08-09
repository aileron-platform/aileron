import { apiClient } from './apiClient';

interface RecentWorkspaceResponse {
  workspace_id: string | null;
}

export const getRecentWorkspace = async (): Promise<string | null> => {
  const response = await apiClient.get<RecentWorkspaceResponse>('/users/me/recent-workspace');
  return response.workspace_id;
};

export const updateRecentWorkspace = async (workspaceId: string): Promise<void> => {
  await apiClient.put<RecentWorkspaceResponse>('/users/me/recent-workspace', {
    workspace_id: workspaceId,
  });
};
