import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { slashCommandApi } from '@/shared/api/slashCommandApi';
import { apiClient } from '@/shared/api/apiClient';
import { normalizeAgenticTools } from '@/shared/types/agenticTool';
import type { WorkspaceCapabilities } from '@/features/ai-chat/public';
import type { WorkspaceDetailResponse, WorkspaceListResponse } from '@/features/workspace/public';
import type { AutomationWorkspaceSummary } from '../model/automationTypes';

const WORKSPACE_LIST_ENDPOINT = '/workspaces?page=1&pageSize=50';

const buildWorkspaceDetailEndpoint = (workspaceId: string): string =>
  `/workspaces/${encodeURIComponent(workspaceId)}`;

const handleAbort = (signal?: AbortSignal) => {
  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError');
  }
};

export const automationWorkspaceApi = {
  async list(signal?: AbortSignal): Promise<AutomationWorkspaceSummary[]> {
    // Note: apiClient doesn't support AbortSignal yet, but we'll handle the signal check manually
    handleAbort(signal);

    const data = await apiClient.get<WorkspaceListResponse>(WORKSPACE_LIST_ENDPOINT);
    const items = Array.isArray(data.items) ? data.items : [];

    return items
      .map(item => ({
        id: item.id,
        name: item.name,
        accessSource: item.accessSource === 'owned' ? 'owned' as const : 'shared' as const,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));
  },

  async getDetail(workspaceId: string, signal?: AbortSignal): Promise<WorkspaceDetailResponse> {
    handleAbort(signal);

    return await apiClient.get<WorkspaceDetailResponse>(buildWorkspaceDetailEndpoint(workspaceId));
  },

  async getCapabilities(workspaceId: string, signal?: AbortSignal): Promise<WorkspaceCapabilities> {
    handleAbort(signal);
    return apiClient.get<WorkspaceCapabilities>(
      `${buildWorkspaceDetailEndpoint(workspaceId)}/capabilities`,
    );
  },

  async listSlashCommands(workspaceId: string, signal?: AbortSignal): Promise<SlashCommandItem[]> {
    const detail = await this.getDetail(workspaceId, signal);

    handleAbort(signal);

    const runtimeBaseUrl = detail.runtimeStatus.runtimeUrl;

    const apiPrefix = normalizeAgenticTools(detail.agenticTools)[0];

    return slashCommandApi.list(runtimeBaseUrl, workspaceId, apiPrefix, signal);
  },
};
