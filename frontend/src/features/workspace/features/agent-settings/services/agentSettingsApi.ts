import { ApiClient } from '@/shared/api/apiClient';
import { buildSlashCommandDisplayName } from '@/shared/types/slashCommands';
import type {
  AgentDocument,
  AgentMcpServer,
  AgentScope,
  AgentHookScope,
  AgentHookRuleMap,
  AgentHookScopesResponse,
  AgentHookScopeResponse,
  AgentHookDeleteResponse,
  AgentHookExportResponse,
  AgentHookImportRequest,
  AgentHookImportResponse,
  AgentFileCollectionResponse,
  AgentFileResponse,
  AgentFileCreateRequest,
  AgentFileUpdateRequest,
  AgentFileDeleteResponse,
  AgentPluginSkillsResponse,
  AgentHookScopeDocument,
  AgentHookWithEvent,
  AgentHookRuleConfig,
} from '../types';

export type {
  AgentHookRuleMap,
  AgentHookScopesResponse,
  AgentHookScopeResponse,
  AgentHookDeleteResponse,
  AgentHookExportResponse,
  AgentHookImportRequest,
  AgentHookImportResponse,
  AgentHookScopeDocument,
  AgentHookWithEvent,
  AgentHookMatcher,
  AgentHookActionConfig,
  AgentHookRuleConfig,
  AgentFileCollectionResponse,
  AgentFileResponse,
  AgentFileCreateRequest,
  AgentFileUpdateRequest,
  AgentFileDeleteResponse,
  AgentPluginSkillsResponse,
} from '../types';

const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

const apiRequest = async <T>(
  runtimeBaseUrl: string,
  path: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    body?: any;
    headers?: Record<string, string>;
  }
): Promise<T> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const fullPath = `/api/v1/${path.startsWith('/') ? path.slice(1) : path}`;

  const method = options?.method || 'GET';
  const headers = options?.headers;

  switch (method) {
    case 'GET':
      return await client.get<T>(fullPath, headers);
    case 'POST':
      return await client.post<T>(fullPath, options?.body, headers);
    case 'PUT':
      return await client.put<T>(fullPath, options?.body, headers);
    case 'PATCH':
      return await client.patch<T>(fullPath, options?.body, headers);
    case 'DELETE':
      return await client.delete<T>(fullPath, headers);
    default:
      throw new Error(`Unsupported HTTP method: ${method}`);
  }
};

type CliSlashCommandScope = 'project' | 'user';

interface CliSlashCommandSummary {
  fileName: string;
  namespace?: string | null;
  description?: string | null;
  scope: CliSlashCommandScope;
  size: string;
  format: 'markdown' | 'toml';
}

interface CliSlashCommandDetail extends CliSlashCommandSummary {
  content: string;
}

interface CliSlashCommandScopesResponse {
  workspaceId: string;
  scopes: Array<{ scope: CliSlashCommandScope; documents: CliSlashCommandSummary[] }>;
}

interface CliSlashCommandDocumentResponse {
  workspaceId: string;
  scope: CliSlashCommandScope;
  document: CliSlashCommandDetail;
}

const buildCliDocumentId = (scope: string, fileName: string) => `${scope}:${fileName}`;

const mapCliSlashCommandDocument = (
  scope: CliSlashCommandScope,
  detail: CliSlashCommandDetail,
): AgentDocument => {
  const namespace = detail.namespace ?? undefined;
  const title = buildSlashCommandDisplayName(detail.fileName, namespace);

  return {
    id: buildCliDocumentId(scope, detail.fileName),
    title,
    description: detail.description ?? '',
    content: detail.content,
    scope,
    size: detail.size,
    metadata: {
      fileName: detail.fileName,
      namespace,
      format: detail.format,
    },
  };
};

type AgentMcpScope = AgentScope;

interface McpServerConfigResponse {
  type: AgentMcpServer['transport'];
  command?: string | null;
  url?: string | null;
  args?: string[] | null;
  env?: Record<string, string> | null;
  headers?: Record<string, string> | null;
  enabled?: boolean;
  pluginName?: string;
  marketplaceName?: string;
}

interface McpScopeResponse {
  workspaceId: string;
  scope: AgentMcpScope;
  mcpServers: Record<string, McpServerConfigResponse>;
}

interface McpServerCollectionResponse {
  workspaceId: string;
  scopes: Array<{ scope: AgentMcpScope; mcpServers: Record<string, McpServerConfigResponse> }>;
}

interface McpImportResponse {
  workspaceId: string;
  scope: AgentMcpScope;
  created: string[];
  updated: string[];
  skipped: string[];
}

interface AgentsMdResponse {
  workspaceId: string;
  scope: string;
  content: string;
}

interface AgentsMdUpdateResponse {
  workspaceId: string;
  scope: string;
}

const cloneHookRuleMap = (hooks: AgentHookRuleMap | undefined): AgentHookRuleMap => {
  if (!hooks) return {};
  return Object.fromEntries(
    Object.entries(hooks).map(([event, rules]) => [
      event,
      rules.map((rule) => ({
        matcher: rule.matcher,
        hooks: rule.hooks.map((action) => ({ ...action })),
      })),
    ]),
  );
};

export const buildHookRulesFromAgentHook = (hook: AgentHookWithEvent): AgentHookRuleConfig[] =>
  hook.matchers
    .map((matcher) => ({
      matcher: matcher.matcher.trim() || '*',
      hooks: matcher.hooks
        .filter((action) => Boolean(action.command?.trim()))
        .map((action) => ({
          type: 'command' as const,
          command: action.command?.trim() ?? '',
          timeout: typeof action.timeout === 'number' ? action.timeout : null,
        })),
    }))
    .filter((rule) => rule.hooks.length > 0);

export const mapHookScopeDocumentToAgentHooks = (
  document: AgentHookScopeDocument,
): AgentHookWithEvent[] =>
  Object.entries(document.hooks ?? {})
    .map(([eventName, rules]) => ({
      id: `${document.scope}:${eventName}`,
      scope: document.scope,
      eventName,
      matchers: rules.map((rule) => ({
        matcher: rule.matcher,
        hooks: rule.hooks.map((action) => ({
          type: 'command' as const,
          command: action.command ?? '',
          timeout: typeof action.timeout === 'number' ? action.timeout : undefined,
        })),
      })),
    }))
    .sort((a, b) => a.eventName.localeCompare(b.eventName));

const mapMcpServer = (
  scope: AgentMcpScope,
  name: string,
  config: McpServerConfigResponse,
): AgentMcpServer => ({
  id: `${scope}:${name}`,
  name,
  scope,
  transport: config.type,
  command: config.command ?? undefined,
  args: config.args ?? undefined,
  url: config.url ?? undefined,
  env: config.env ?? undefined,
  headers: config.headers ?? undefined,
  enabled: config.enabled ?? true,
  pluginName: config.pluginName,
  marketplaceName: config.marketplaceName,
});

const normalizeMcpServers = (payload: McpServerCollectionResponse): AgentMcpServer[] =>
  payload.scopes.flatMap(({ scope, mcpServers }) =>
    Object.entries(mcpServers ?? {}).map(([name, config]) => mapMcpServer(scope, name, config)),
  ).sort((a, b) => a.name.localeCompare(b.name));

const buildMcpServerPayload = (server: AgentMcpServer): Record<string, McpServerConfigResponse> => {
  const config: McpServerConfigResponse = {
    type: server.transport,
    command: server.transport === 'stdio' ? server.command ?? '' : undefined,
    url: server.transport !== 'stdio' ? server.url ?? '' : undefined,
    args: server.args && server.args.length > 0 ? server.args : undefined,
    env: server.env && Object.keys(server.env).length > 0 ? server.env : undefined,
    headers:
      server.transport !== 'stdio' && server.headers && Object.keys(server.headers).length > 0
        ? server.headers
        : undefined,
  };
  if (config.command === '') delete config.command;
  if (config.url === '') delete config.url;
  return { [server.name]: config };
};

// ============ API factory ============

export const createAgentSettingsApi = (apiPrefix: string, agentsMdEndpoint: string = 'agents-md') => ({
  async getAgentsMd(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: string,
  ): Promise<AgentsMdResponse> {
    return apiRequest<AgentsMdResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/${agentsMdEndpoint}?scope=${scope}`,
    );
  },

  async updateAgentsMd(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: { scope: string; content: string; message?: string },
  ): Promise<AgentsMdUpdateResponse> {
    return apiRequest<AgentsMdUpdateResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/${agentsMdEndpoint}`,
      { method: 'PUT', body: payload },
    );
  },

  // ============ MCP Servers ============

  async listMcpServers(runtimeBaseUrl: string, workspaceId: string): Promise<AgentMcpServer[]> {
    const response = await apiRequest<McpServerCollectionResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers`,
    );
    return normalizeMcpServers(response);
  },

  async createMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: AgentMcpServer,
  ): Promise<AgentMcpServer> {
    const payload = { mcpServers: buildMcpServerPayload(server) };
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${server.scope}`,
      { method: 'POST', body: payload },
    );
    const config = response.mcpServers?.[server.name];
    if (!config) throw new Error(`Unable to create MCP server: ${server.name}`);
    return mapMcpServer(response.scope, server.name, config);
  },

  async updateMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: AgentMcpServer,
  ): Promise<AgentMcpServer> {
    const payload = { mcpServers: buildMcpServerPayload(server) };
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${server.scope}/${server.name}`,
      { method: 'PUT', body: payload, headers: { 'If-Match': '*' } },
    );
    const config = response.mcpServers?.[server.name];
    if (!config) throw new Error(`Unable to update MCP server: ${server.name}`);
    return mapMcpServer(response.scope, server.name, config);
  },

  async deleteMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: Pick<AgentMcpServer, 'name' | 'scope'>,
  ): Promise<void> {
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${server.scope}/${server.name}`,
      { method: 'DELETE' },
    );
  },

  async toggleMcpServerStatus(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: Pick<AgentMcpServer, 'name' | 'scope'>,
    enabled: boolean,
  ): Promise<AgentMcpServer> {
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${server.scope}/${server.name}/toggle?enabled=${enabled}`,
      { method: 'PATCH' },
    );
    const config = response.mcpServers[server.name];
    if (!config) throw new Error(`Unable to toggle MCP server status: ${server.name}`);
    return mapMcpServer(response.scope, server.name, config);
  },

  async importMcpServers(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: { scope: AgentMcpScope; file: File; overwrite?: boolean },
  ): Promise<McpImportResponse> {
    const formData = new FormData();
    formData.append('scope', payload.scope);
    formData.append('overwrite', payload.overwrite ? 'true' : 'false');
    formData.append('file', payload.file);
    return apiRequest<McpImportResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-import`,
      { method: 'POST', body: formData },
    );
  },

  // ============ Hooks ============

  async listHookScopes(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope?: AgentHookScope,
  ): Promise<AgentHookScopesResponse> {
    const path = scope
      ? `workspaces/${workspaceId}/${apiPrefix}/hooks?scope=${scope}`
      : `workspaces/${workspaceId}/${apiPrefix}/hooks`;
    const response = await apiRequest<AgentHookScopesResponse>(runtimeBaseUrl, path);
    return {
      ...response,
      scopes: response.scopes.map((document) => ({
        scope: document.scope,
        hooks: cloneHookRuleMap(document.hooks),
      })),
    };
  },

  async getHookScope(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: AgentHookScope,
  ): Promise<AgentHookScopeResponse> {
    const response = await apiRequest<AgentHookScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/hooks/${scope}`,
    );
    return {
      ...response,
      hooks: cloneHookRuleMap(response.hooks),
    };
  },

  async updateHookScope(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: AgentHookScope,
    hooks: AgentHookRuleMap,
  ): Promise<AgentHookScopeResponse> {
    const response = await apiRequest<AgentHookScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/hooks/${scope}`,
      { method: 'PUT', body: { hooks } },
    );
    return {
      ...response,
      hooks: cloneHookRuleMap(response.hooks),
    };
  },

  async deleteHookScope(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: AgentHookScope,
  ): Promise<AgentHookDeleteResponse> {
    return apiRequest<AgentHookDeleteResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/hooks/${scope}`,
      { method: 'DELETE' },
    );
  },

  async exportHooks(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope?: AgentHookScope,
  ): Promise<AgentHookExportResponse> {
    const path = scope
      ? `workspaces/${workspaceId}/${apiPrefix}/hooks/export?scope=${scope}`
      : `workspaces/${workspaceId}/${apiPrefix}/hooks/export`;
    const response = await apiRequest<AgentHookExportResponse>(runtimeBaseUrl, path);
    return {
      ...response,
      scopes: response.scopes.map((document) => ({
        scope: document.scope,
        hooks: cloneHookRuleMap(document.hooks),
      })),
    };
  },

  async importHooks(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: AgentHookImportRequest,
  ): Promise<AgentHookImportResponse> {
    return apiRequest<AgentHookImportResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/hooks/import`,
      { method: 'POST', body: payload },
    );
  },

  // ============ Skills ============

  async listSkills(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope?: 'project' | 'user' | 'plugin',
  ): Promise<AgentFileCollectionResponse> {
    const path = scope
      ? `workspaces/${workspaceId}/${apiPrefix}/skills/tree?scope=${scope}`
      : `workspaces/${workspaceId}/${apiPrefix}/skills/tree`;
    return apiRequest<AgentFileCollectionResponse>(runtimeBaseUrl, path);
  },

  async listPluginSkills(runtimeBaseUrl: string, workspaceId: string): Promise<AgentPluginSkillsResponse> {
    return apiRequest<AgentPluginSkillsResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/skills/plugins`,
    );
  },

  async getSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' | 'plugin' = 'project',
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/skills/content?path=${encodeURIComponent(filePath)}&scope=${scope}`,
    );
  },

  async createSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: AgentFileCreateRequest,
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/skills`,
      { method: 'POST', body: payload },
    );
  },

  async updateSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    payload: AgentFileUpdateRequest,
    scope?: 'project' | 'user',
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/skills/content?path=${encodeURIComponent(filePath)}&scope=${scope}&content=${encodeURIComponent(payload.content)}`,
      { method: 'PUT' },
    );
  },

  async deleteSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' = 'project',
    recursive: boolean = false,
  ): Promise<AgentFileDeleteResponse> {
    return apiRequest<AgentFileDeleteResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/skills/${filePath}?scope=${scope}&recursive=${recursive}`,
      { method: 'DELETE' },
    );
  },

  async moveSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    sourcePath: string,
    destPath: string,
    scope: 'project' | 'user' = 'project',
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/skills/move?scope=${scope}`,
      { method: 'POST', body: { sourcePath, destPath } },
    );
  },

  async copySkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    sourcePath: string,
    destPath: string,
    scope: 'project' | 'user' = 'project',
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/skills/copy?sourcePath=${encodeURIComponent(sourcePath)}&destPath=${encodeURIComponent(destPath)}&sourceScope=${scope}&destScope=${scope}&overwrite=false`,
      { method: 'POST' },
    );
  },

  async listScripts(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope?: 'project' | 'user' | 'plugin',
  ): Promise<AgentFileCollectionResponse> {
    const path = scope
      ? `workspaces/${workspaceId}/${apiPrefix}/scripts/tree?scope=${scope}`
      : `workspaces/${workspaceId}/${apiPrefix}/scripts/tree`;
    return apiRequest<AgentFileCollectionResponse>(runtimeBaseUrl, path);
  },

  async getScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' | 'plugin' = 'project',
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/scripts/content?path=${encodeURIComponent(filePath)}&scope=${scope}`,
    );
  },

  async createScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: AgentFileCreateRequest,
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/scripts`,
      { method: 'POST', body: payload },
    );
  },

  async updateScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    payload: AgentFileUpdateRequest,
    scope?: 'project' | 'user',
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/scripts/content?path=${encodeURIComponent(filePath)}&scope=${scope}&content=${encodeURIComponent(payload.content)}`,
      { method: 'PUT' },
    );
  },

  async deleteScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' = 'project',
    recursive: boolean = false,
  ): Promise<AgentFileDeleteResponse> {
    return apiRequest<AgentFileDeleteResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/scripts/${filePath}?scope=${scope}&recursive=${recursive}`,
      { method: 'DELETE' },
    );
  },

  async copyScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    sourcePath: string,
    destPath: string,
    scope: 'project' | 'user' = 'project',
  ): Promise<AgentFileResponse> {
    return apiRequest<AgentFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/scripts/copy?sourcePath=${encodeURIComponent(sourcePath)}&destPath=${encodeURIComponent(destPath)}&sourceScope=${scope}&destScope=${scope}&overwrite=false`,
      { method: 'POST' },
    );
  },

  // ============ Slash Commands ============

  async listSlashCommands(
    runtimeBaseUrl: string,
    workspaceId: string,
  ): Promise<AgentDocument[]> {
    const scopesRes = await apiRequest<CliSlashCommandScopesResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands`,
    );

    const documents: AgentDocument[] = [];
    for (const group of scopesRes.scopes) {
      for (const summary of group.documents) {
        // Fetch full document content.
        const detailRes = await apiRequest<CliSlashCommandDocumentResponse>(
          runtimeBaseUrl,
          `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${group.scope}/${encodeURIComponent(summary.fileName)}`,
        );
        documents.push(mapCliSlashCommandDocument(group.scope, detailRes.document));
      }
    }
    return documents.sort((a, b) => a.title.localeCompare(b.title));
  },

  async createSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliSlashCommandScope;
    const payload = {
      fileName: (document.metadata?.fileName as string) ?? document.title,
      content: document.content,
      namespace: (document.metadata?.namespace as string) ?? undefined,
    };
    const response = await apiRequest<CliSlashCommandDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${scope}`,
      { method: 'POST', body: payload },
    );
    return mapCliSlashCommandDocument(response.scope, response.document);
  },

  async updateSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliSlashCommandScope;
    const fileName = (document.metadata?.fileName as string) ?? document.title;
    const payload = {
      content: document.content,
      namespace: (document.metadata?.namespace as string) ?? undefined,
    };
    const response = await apiRequest<CliSlashCommandDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${scope}/${encodeURIComponent(fileName)}`,
      { method: 'PUT', body: payload },
    );
    return mapCliSlashCommandDocument(response.scope, response.document);
  },

  async deleteSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: Pick<AgentDocument, 'scope' | 'metadata' | 'title'>,
  ): Promise<void> {
    const scope = document.scope as CliSlashCommandScope;
    const fileName = (document.metadata?.fileName as string) ?? document.title;
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${scope}/${encodeURIComponent(fileName)}`,
      { method: 'DELETE' },
    );
  },
});

export type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;
