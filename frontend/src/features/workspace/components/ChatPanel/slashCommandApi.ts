import { ApiClient } from '@/shared/api/apiClient';
import type { SlashCommandItem, SlashCommandScope } from '@/shared/types/slashCommands';
import { buildSlashCommandCategory, buildSlashCommandDisplayName } from '@/shared/types/slashCommands';

/**
 * 創建帶認證的 Runtime API Client
 */
const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

interface SlashCommandSummaryResponse {
  fileName: string;
  namespace?: string | null;
  description?: string | null;
  scope: SlashCommandScope;
  size: string;
  pluginName?: string | null;
  marketplaceName?: string | null;
}

interface SlashCommandScopeGroupResponse {
  scope: SlashCommandScope;
  documents: SlashCommandSummaryResponse[];
}

interface SlashCommandCollectionResponse {
  workspaceId: string;
  scopes: SlashCommandScopeGroupResponse[];
}

const mapSummaryToItem = (
  scope: SlashCommandScope,
  summary: SlashCommandSummaryResponse,
): SlashCommandItem => {
  const namespace = summary.namespace?.trim() || undefined;
  const pluginName = summary.pluginName?.trim() || undefined;

  // 使用 buildSlashCommandDisplayName 組合顯示名稱
  // Plugin: {pluginName}:{fileName}
  // 非 Plugin: {namespace}/{fileName} 或 {fileName}
  const displayName = buildSlashCommandDisplayName(summary.fileName, namespace, pluginName);
  const category = buildSlashCommandCategory(scope, namespace);
  const id = namespace ? `${scope}:${namespace}:${summary.fileName}` : `${scope}:${summary.fileName}`;

  return {
    id,
    fileName: summary.fileName,
    namespace,
    displayName,
    category,
    scope,
    description: summary.description ?? '',
    tags: [],
  };
};

export const slashCommandApi = {
  async list(
    runtimeBaseUrl: string,
    workspaceId: string,
    apiPrefix: string = 'claude-code',
    signal?: AbortSignal,
  ): Promise<SlashCommandItem[]> {
    const client = createRuntimeClient(runtimeBaseUrl);
    const path = `/api/v1/workspaces/${workspaceId}/${apiPrefix}/slash-commands`;
    const response = await client.get<SlashCommandCollectionResponse>(path);
    const items = response.scopes.flatMap(({ scope, documents }) =>
      documents.map((document) => mapSummaryToItem(scope, document)),
    );
    return items.sort((a, b) => a.displayName.localeCompare(b.displayName));
  },
};

export type SlashCommandApi = typeof slashCommandApi;
