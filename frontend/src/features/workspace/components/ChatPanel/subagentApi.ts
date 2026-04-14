import { ApiClient } from '@/shared/api/apiClient';
import type { SubagentItem, SubagentScope } from '@/shared/types/subagents';
import { buildSubagentCategory, buildSubagentDisplayName } from '@/shared/types/subagents';

/**
 * 創建帶認證的 Runtime API Client
 */
const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

interface SubagentSummaryResponse {
  fileName: string;
  name?: string | null;
  description?: string | null;
  scope: SubagentScope;
  size: string;
  pluginName?: string | null;
  marketplaceName?: string | null;
}

interface SubagentScopeGroupResponse {
  scope: SubagentScope;
  documents: SubagentSummaryResponse[];
}

interface SubagentCollectionResponse {
  workspaceId: string;
  scopes: SubagentScopeGroupResponse[];
}

const mapSummaryToItem = (
  scope: SubagentScope,
  summary: SubagentSummaryResponse,
): SubagentItem => {
  const name = summary.name?.trim() || undefined;
  const pluginName = summary.pluginName?.trim() || undefined;

  // 使用 buildSubagentDisplayName 組合顯示名稱
  // Plugin: {pluginName}:{fileName}
  // 非 Plugin: {name} 或 {fileName}
  const displayName = buildSubagentDisplayName(summary.fileName, name, pluginName);
  const category = buildSubagentCategory(scope, name);
  const id = name ? `${scope}:${name}:${summary.fileName}` : `${scope}:${summary.fileName}`;

  return {
    id,
    fileName: summary.fileName,
    name,
    displayName,
    category,
    scope,
    description: summary.description ?? '',
    tags: [],
    pluginName,
    marketplaceName: summary.marketplaceName ?? undefined,
  };
};

export const subagentApi = {
  async list(
    runtimeBaseUrl: string,
    workspaceId: string,
    signal?: AbortSignal,
  ): Promise<SubagentItem[]> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const path = `/api/v1/workspaces/${workspaceId}/claude-code/subagents`;
    const response = await client.get<SubagentCollectionResponse>(path);
    const items = response.scopes.flatMap(({ scope, documents }) =>
      documents.map((document) => mapSummaryToItem(scope, document)),
    );
    return items.sort((a, b) => a.displayName.localeCompare(b.displayName));
  },
};

export type SubagentApi = typeof subagentApi;

