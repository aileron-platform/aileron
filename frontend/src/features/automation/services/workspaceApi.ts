import type { SlashCommandItem } from '@/shared/types/slashCommands';
import { slashCommandApi } from '@/features/workspace/components/ChatPanel/slashCommandApi';
import { apiClient } from '@/shared/api/apiClient';
import { normalizeAgentType, getAgentToolConfig } from '@/features/workspace/features/agent-settings/utils';
import { resolvePreferredWorkspaceUrl } from '@/features/workspace/services/workspacePublicUrl';

interface WorkspaceListItem {
  id: string;
  name: string;
}

interface WorkspaceListResponse {
  items?: WorkspaceListItem[];
}

interface WorkspaceRuntimeStatus {
  internalUrl?: string | null;
  externalUrl?: string | null;
}

interface WorkspaceDetailResponse {
  id: string;
  name: string;
  cliType?: string;
  runtimeStatus?: WorkspaceRuntimeStatus;
}

export interface WorkspaceSummary {
  id: string;
  name: string;
}

const WORKSPACE_LIST_ENDPOINT = '/workspaces/?page=1&pageSize=50';

const buildWorkspaceDetailEndpoint = (workspaceId: string): string =>
  `/workspaces/${encodeURIComponent(workspaceId)}`;

async function parseJson<T>(response: Response): Promise<T> {
  try {
    return (await response.json()) as T;
  } catch (error) {
    throw new Error('無法解析 Workspace Manager 回應');
  }
}

const handleAbort = (signal?: AbortSignal) => {
  if (signal?.aborted) {
    throw new DOMException('Aborted', 'AbortError');
  }
};

export const workspaceApi = {
  async list(signal?: AbortSignal): Promise<WorkspaceSummary[]> {
    // Note: apiClient doesn't support AbortSignal yet, but we'll handle the signal check manually
    handleAbort(signal);

    const data = await apiClient.get<WorkspaceListResponse>(WORKSPACE_LIST_ENDPOINT);
    const items = Array.isArray(data.items) ? data.items : [];

    return items
      .map(item => ({ id: item.id, name: item.name }))
      .sort((a, b) => a.name.localeCompare(b.name));
  },

  async getDetail(workspaceId: string, signal?: AbortSignal): Promise<WorkspaceDetailResponse> {
    handleAbort(signal);

    return await apiClient.get<WorkspaceDetailResponse>(buildWorkspaceDetailEndpoint(workspaceId));
  },

  async listSlashCommands(workspaceId: string, signal?: AbortSignal): Promise<SlashCommandItem[]> {
    const detail = await this.getDetail(workspaceId, signal);

    handleAbort(signal);

    // 瀏覽器環境優先使用 externalUrl（可從瀏覽器訪問）
    const runtimeBaseUrl = resolvePreferredWorkspaceUrl(
      detail.runtimeStatus?.externalUrl,
      detail.runtimeStatus?.internalUrl
    );
    if (!runtimeBaseUrl) {
      throw new Error('無法取得工作區 Runtime URL');
    }

    const agentType = normalizeAgentType(detail.cliType);
    const apiPrefix = getAgentToolConfig(agentType).apiPathPrefix;

    return slashCommandApi.list(runtimeBaseUrl, workspaceId, apiPrefix, signal);
  },
};

// 向後相容別名
export const schedulerWorkspaceApi = workspaceApi;
export type WorkspaceSummary = WorkspaceSummary;
export type WorkspaceApi = typeof workspaceApi;
export type SchedulerWorkspaceApi = typeof workspaceApi;
