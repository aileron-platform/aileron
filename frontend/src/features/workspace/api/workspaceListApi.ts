import { apiClient } from '@/shared/api/apiClient';
import { normalizeResourceAuthorization } from '@/shared/authorization/resourceAuthorization';
import { type WorkspaceListResponse } from '../model/workspaceTypes';

export const fetchWorkspaceList = async (pageSize: number = 50): Promise<WorkspaceListResponse> => {
  const response = await apiClient.get<WorkspaceListResponse>(
    `/workspaces?page=1&pageSize=${pageSize}`,
  );
  const items = Array.isArray(response.items)
    ? response.items.flatMap((item) => {
      const authorization = normalizeResourceAuthorization(item);
      return authorization
        ? [{ ...item, ...authorization }]
        : [];
    })
    : [];

  return { ...response, items };
};
