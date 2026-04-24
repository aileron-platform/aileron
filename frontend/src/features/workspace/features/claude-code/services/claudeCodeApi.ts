import { ApiClient } from '@/shared/api/apiClient';
import type { ClaudeDocument, ClaudeScope, ClaudeHookScope, ClaudeMcpServer } from '../data';
import { buildSlashCommandDisplayName } from '@/shared/types/slashCommands';

/**
 * 創建帶認證的 Runtime API Client
 */
const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({ baseUrl: runtimeBaseUrl });
};

/**
 * 輔助函數：使用 ApiClient 發送請求
 */
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

const buildDocumentId = (scope: ClaudeScope, fileName: string) => `${scope}:${fileName}`;

type ClaudeMcpScope = ClaudeScope;
type ClaudeMcpTransport = ClaudeMcpServer['transport'];

export interface ClaudeHookActionConfig {
  type: 'command' | 'webhook' | 'mcp_call';
  command?: string | null;
  timeout?: number | null;
}

export interface ClaudeHookRuleConfig {
  matcher: string;
  hooks: ClaudeHookActionConfig[];
}

export type ClaudeHookRuleMap = Record<string, ClaudeHookRuleConfig[]>;

export interface ClaudeHookScopeDocument {
  scope: ClaudeHookScope;
  hooks: ClaudeHookRuleMap;
}

export interface ClaudeHookScopesResponse {
  workspaceId: string;
  scopes: ClaudeHookScopeDocument[];
}

export interface ClaudeHookScopeResponse {
  workspaceId: string;
  scope: ClaudeHookScope;
  hooks: ClaudeHookRuleMap;
}

export interface ClaudeHookDeleteResponse {
  workspaceId: string;
  scope: ClaudeHookScope;
  deleted: boolean;
  deletedAt: string;
}

export type ClaudeHookImportMode = 'merge' | 'replace';

export interface ClaudeHookImportRequest {
  mode: ClaudeHookImportMode;
  scopes: ClaudeHookScopeDocument[];
}

export interface ClaudeHookImportResponse {
  workspaceId: string;
  mode: ClaudeHookImportMode;
  imported: number;
  updated: number;
  skipped: number;
}

// 擴展的 Hook 類型，用於 UI 顯示（包含 eventName 和 matchers）
export interface ClaudeHookMatcher {
  matcher: string;
  hooks: ClaudeHookActionConfig[];
}

export interface ClaudeHookWithEvent {
  id: string;
  scope: ClaudeHookScope;
  eventName: string;
  matchers: ClaudeHookMatcher[];
  pluginName?: string;
  marketplaceName?: string;
}

export interface ClaudeHookExportResponse {
  workspaceId: string;
  exportedAt: string;
  scopes: ClaudeHookScopeDocument[];
}

// Settings 保留 local scope 支援
export type ClaudeCodeSettingsScope = ClaudeHookScope;

export interface ClaudeCodePermissionRules {
  allow: string[];
  deny: string[];
  ask?: string[];
  additionalDirectories?: string[];
}

export interface ClaudeMcpServerPolicy {
  serverName: string;
  [key: string]: unknown;
}

export interface ClaudeCodeSettings {
  mode: string;
  defaultMode?: string | null;
  outputStyle?: string | null;
  model?: string | null;
  permissions: ClaudeCodePermissionRules;
  env: Record<string, string>;
  enabledPlugins?: Record<string, boolean>;
  apiKeyHelper?: string | null;
  cleanupPeriodDays?: number | null;
  includeCoAuthoredBy?: boolean;
  disableAllHooks?: boolean;
  enableAllProjectMcpServers?: boolean;
  enabledMcpjsonServers?: string[];
  disabledMcpjsonServers?: string[];
  allowedMcpServers?: ClaudeMcpServerPolicy[];
  deniedMcpServers?: ClaudeMcpServerPolicy[];
}

export interface ClaudeCodeSettingsUpdateRequest {
  mode?: string | null;
  defaultMode?: string | null;
  outputStyle?: string | null;
  model?: string | null;
  permissions?: ClaudeCodePermissionRules | null;
  env?: Record<string, string> | null;
  enabledPlugins?: Record<string, boolean> | null;
  apiKeyHelper?: string | null;
  cleanupPeriodDays?: number | null;
  includeCoAuthoredBy?: boolean;
  disableAllHooks?: boolean;
  enableAllProjectMcpServers?: boolean;
  enabledMcpjsonServers?: string[];
  disabledMcpjsonServers?: string[];
  allowedMcpServers?: ClaudeMcpServerPolicy[];
  deniedMcpServers?: ClaudeMcpServerPolicy[];
}

// Marketplace & Plugin Types
export interface PluginMetadata {
  name: string;
  description: string;
  version: string;
  author?: { name: string };
  license?: string;
  keywords?: string[];
  source?: string;
  strict?: boolean;
  commands?: string[];
  agents?: string[];
  mcpServers?: string[];
}

export interface MarketplaceOwner {
  name: string;
  email?: string;
  url?: string;
}

export interface MarketplaceMetadata {
  description: string;
  version: string;
}

export interface Marketplace {
  name: string;
  owner: MarketplaceOwner;
  metadata: MarketplaceMetadata;
  plugins: PluginMetadata[];
}

export interface MarketplaceListResponse {
  marketplaces: Marketplace[];
}

const cloneHookRuleMap = (hooks: ClaudeHookRuleMap | undefined): ClaudeHookRuleMap => {
  if (!hooks) {
    return {};
  }
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

export const buildHookRulesFromClaudeHook = (hook: ClaudeHookWithEvent): ClaudeHookRuleConfig[] =>
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

export const mapHookScopeDocumentToClaudeHooks = (
  document: ClaudeHookScopeDocument,
): ClaudeHookWithEvent[] =>
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

interface SlashCommandSummary {
  fileName: string;
  namespace?: string | null;
  description?: string | null;
  scope: ClaudeScope;
  size: string;
  pluginName?: string;
  marketplaceName?: string;
}

interface SlashCommandDocumentResponse {
  workspaceId: string;
  scope: ClaudeScope;
  document: SlashCommandSummary & { content: string };
}

interface OutputStyleSummary {
  fileName: string;
  name?: string | null;
  description?: string | null;
  scope: ClaudeScope;
  size: string;
}

interface OutputStyleDocumentResponse {
  workspaceId: string;
  scope: ClaudeScope;
  document: OutputStyleSummary & { content: string };
}

interface SubagentSummary {
  fileName: string;
  name?: string | null;
  description?: string | null;
  scope: ClaudeScope;
  size: string;
  pluginName?: string;
  marketplaceName?: string;
}

interface SubagentDocumentResponse {
  workspaceId: string;
  scope: ClaudeScope;
  document: SubagentSummary & { content: string };
}

interface MemorySummary {
  fileName: string;
  name?: string | null;
  description?: string | null;
  size: string;
}

interface MemoryCollectionResponse {
  workspaceId: string;
  documents: MemorySummary[];
}

interface MemoryDocumentResponse {
  workspaceId: string;
  document: MemorySummary & { content: string };
}

interface McpServerConfigResponse {
  type: ClaudeMcpTransport;
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
  scope: ClaudeMcpScope;
  mcpServers: Record<string, McpServerConfigResponse>;
}

interface McpServerCollectionResponse {
  workspaceId: string;
  scopes: Array<{ scope: ClaudeMcpScope; mcpServers: Record<string, McpServerConfigResponse> }>;
}

interface McpImportResponse {
  workspaceId: string;
  scope: ClaudeMcpScope;
  created: string[];
  updated: string[];
  skipped: string[];
}

const mapSlashCommandDocument = (
  scope: ClaudeScope,
  detail: SlashCommandSummary & { content: string },
): ClaudeDocument => {
  const namespace = detail.namespace ?? undefined;
  const pluginName = detail.pluginName ?? undefined;

  // 使用 buildSlashCommandDisplayName 組合顯示名稱
  // Plugin: {pluginName}:{fileName}
  // 非 Plugin: {namespace}/{fileName} 或 {fileName}
  const title = buildSlashCommandDisplayName(detail.fileName, namespace, pluginName);

  return {
    id: buildDocumentId(scope, detail.fileName),
    title,
    description: detail.description ?? '',
    content: detail.content,
    scope,
    size: detail.size,
    metadata: {
      fileName: detail.fileName,
      namespace,
    },
    pluginName: detail.pluginName,
    marketplaceName: detail.marketplaceName,
  };
};

const mapOutputStyleDocument = (
  scope: ClaudeScope,
  detail: OutputStyleSummary & { content: string },
): ClaudeDocument => ({
  id: buildDocumentId(scope, detail.fileName),
  title: detail.name ?? detail.fileName,
  description: detail.description ?? '',
  content: detail.content,
  scope,
  size: detail.size,
  metadata: {
    fileName: detail.fileName,
  },
});

const mapSubagentDocument = (
  scope: ClaudeScope,
  detail: SubagentSummary & { content: string },
): ClaudeDocument => {
  const pluginName = detail.pluginName ?? undefined;

  // Plugin subagents: 使用 {pluginName}:{fileName} 格式
  // 非 Plugin subagents: 使用 name 或 fileName
  const title = pluginName
    ? `${pluginName}:${detail.fileName}`
    : (detail.name ?? detail.fileName);

  return {
    id: buildDocumentId(scope, detail.fileName),
    title,
    description: detail.description ?? '',
    content: detail.content,
    scope,
    size: detail.size,
    metadata: {
      fileName: detail.fileName,
    },
    pluginName: detail.pluginName,
    marketplaceName: detail.marketplaceName,
  };
};

const mapMemoryDocument = (
  detail: MemorySummary & { content: string },
): ClaudeDocument => ({
  id: buildDocumentId('user', detail.fileName),
  title: detail.name ?? detail.fileName,
  description: detail.description ?? '',
  content: detail.content,
  scope: 'user',
  size: detail.size,
  metadata: {
    fileName: detail.fileName,
  },
});

const collectDocuments = async <TSummary extends { scope: ClaudeScope; fileName: string } & Record<string, any>,
  TResponse extends { workspaceId: string; scope: ClaudeScope; document: TSummary & { content: string } }>(
  runtimeBaseUrl: string,
  workspaceId: string,
  resource: string,
  collectionPath: string,
  responseMapper: (scope: ClaudeScope, detail: TSummary & { content: string }) => ClaudeDocument,
): Promise<ClaudeDocument[]> => {
  const collection = await apiRequest<{ workspaceId: string; scopes: Array<{ scope: ClaudeScope; documents: TSummary[] }> }>(
    runtimeBaseUrl,
    collectionPath,
  );

  const documentPromises = collection.scopes.flatMap(({ scope, documents }) =>
    documents.map(async (summary) => {
      const detail = await apiRequest<TResponse>(
        runtimeBaseUrl,
        `workspaces/${workspaceId}/claude-code/${resource}/${scope}/${summary.fileName}`,
      );
      return responseMapper(scope, detail.document);
    }),
  );

  const documents = await Promise.all(documentPromises);
  return documents.sort((a, b) => a.title.localeCompare(b.title));
};

const mapMcpServer = (
  scope: ClaudeMcpScope,
  name: string,
  config: McpServerConfigResponse,
): ClaudeMcpServer => ({
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

const normalizeMcpServers = (payload: McpServerCollectionResponse): ClaudeMcpServer[] =>
  payload.scopes.flatMap(({ scope, mcpServers }) =>
    Object.entries(mcpServers ?? {}).map(([name, config]) => mapMcpServer(scope, name, config)),
  ).sort((a, b) => a.name.localeCompare(b.name));

const buildMcpServerPayload = (server: ClaudeMcpServer): Record<string, McpServerConfigResponse> => {
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
  if (config.command === '') {
    delete config.command;
  }
  if (config.url === '') {
    delete config.url;
  }
  return { [server.name]: config };
};

export const claudeCodeApi = {
  async listHookScopes(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope?: ClaudeHookScope,
  ): Promise<ClaudeHookScopesResponse> {
    const path = scope
      ? `workspaces/${workspaceId}/claude-code/hooks?scope=${scope}`
      : `workspaces/${workspaceId}/claude-code/hooks`;
    const response = await apiRequest<ClaudeHookScopesResponse>(runtimeBaseUrl, path);
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
    scope: ClaudeHookScope,
  ): Promise<ClaudeHookScopeResponse> {
    const response = await apiRequest<ClaudeHookScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/hooks/${scope}`,
    );
    return {
      ...response,
      hooks: cloneHookRuleMap(response.hooks),
    };
  },

  async updateHookScope(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: ClaudeHookScope,
    hooks: ClaudeHookRuleMap,
  ): Promise<ClaudeHookScopeResponse> {
    const response = await apiRequest<ClaudeHookScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/hooks/${scope}`,
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
    scope: ClaudeHookScope,
  ): Promise<ClaudeHookDeleteResponse> {
    return apiRequest<ClaudeHookDeleteResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/hooks/${scope}`,
      { method: 'DELETE' },
    );
  },

  async exportHooks(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope?: ClaudeHookScope,
  ): Promise<ClaudeHookExportResponse> {
    const path = scope
      ? `workspaces/${workspaceId}/claude-code/hooks/export?scope=${scope}`
      : `workspaces/${workspaceId}/claude-code/hooks/export`;
    const response = await apiRequest<ClaudeHookExportResponse>(runtimeBaseUrl, path);
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
    payload: ClaudeHookImportRequest,
  ): Promise<ClaudeHookImportResponse> {
    return apiRequest<ClaudeHookImportResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/hooks/import`,
      { method: 'POST', body: payload },
    );
  },

  async getSettings(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope?: ClaudeCodeSettingsScope,
  ): Promise<ClaudeCodeSettings> {
    const path = scope
      ? `workspaces/${workspaceId}/claude-code/settings?scope=${scope}`
      : `workspaces/${workspaceId}/claude-code/settings`;
    return apiRequest<ClaudeCodeSettings>(runtimeBaseUrl, path);
  },

  async updateSettings(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: ClaudeCodeSettingsUpdateRequest,
    scope: ClaudeCodeSettingsScope = 'project',
  ): Promise<ClaudeCodeSettings> {
    const path = scope
      ? `workspaces/${workspaceId}/claude-code/settings?scope=${scope}`
      : `workspaces/${workspaceId}/claude-code/settings`;
    return apiRequest<ClaudeCodeSettings>(runtimeBaseUrl, path, {
      method: 'PUT',
      body: payload,
    });
  },

  async listSlashCommands(runtimeBaseUrl: string, workspaceId: string): Promise<ClaudeDocument[]> {
    return collectDocuments<SlashCommandSummary, SlashCommandDocumentResponse>(
      runtimeBaseUrl,
      workspaceId,
      'slash-commands',
      `workspaces/${workspaceId}/claude-code/slash-commands`,
      mapSlashCommandDocument,
    );
  },

  async createSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<ClaudeDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    const payload = {
      fileName,
      content: document.content,
      namespace: document.metadata?.namespace ?? undefined,
    };
    const response = await apiRequest<SlashCommandDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/slash-commands/${document.scope}`,
      { method: 'POST', body: payload },
    );
    return mapSlashCommandDocument(response.scope, response.document);
  },

  async updateSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<ClaudeDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    const payload = {
      content: document.content,
      namespace: document.metadata?.namespace ?? undefined,
    };
    const response = await apiRequest<SlashCommandDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/slash-commands/${document.scope}/${fileName}`,
      { method: 'PUT', body: payload },
    );
    return mapSlashCommandDocument(response.scope, response.document);
  },

  async deleteSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<void> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/slash-commands/${document.scope}/${fileName}`,
      { method: 'DELETE' },
    );
  },

  async listOutputStyles(runtimeBaseUrl: string, workspaceId: string, scope?: ClaudeScope): Promise<ClaudeDocument[]> {
    const path = scope
      ? `workspaces/${workspaceId}/claude-code/output-styles?scope=${scope}`
      : `workspaces/${workspaceId}/claude-code/output-styles`;

    const collection = await apiRequest<{ workspaceId: string; scopes: Array<{ scope: ClaudeScope; documents: OutputStyleSummary[] }> }>(
      runtimeBaseUrl,
      path,
    );

    const documentPromises = collection.scopes.flatMap(({ scope: docScope, documents }) =>
      documents.map(async (summary) => {
        const detail = await apiRequest<OutputStyleDocumentResponse>(
          runtimeBaseUrl,
          `workspaces/${workspaceId}/claude-code/output-styles/${docScope}/${summary.fileName}`,
        );
        return mapOutputStyleDocument(docScope, detail.document);
      }),
    );

    const documents = await Promise.all(documentPromises);
    return documents.sort((a, b) => a.title.localeCompare(b.title));
  },

  async createOutputStyle(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<ClaudeDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    const payload = {
      fileName,
      content: document.content,
      name: document.title,
      description: document.description,
    };
    const response = await apiRequest<OutputStyleDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/output-styles/${document.scope}`,
      { method: 'POST', body: payload },
    );
    return mapOutputStyleDocument(response.scope, response.document);
  },

  async updateOutputStyle(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<ClaudeDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    const payload = {
      content: document.content,
      name: document.title,
      description: document.description,
    };
    const response = await apiRequest<OutputStyleDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/output-styles/${document.scope}/${fileName}`,
      { method: 'PUT', body: payload },
    );
    return mapOutputStyleDocument(response.scope, response.document);
  },

  async deleteOutputStyle(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<void> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/output-styles/${document.scope}/${fileName}`,
      { method: 'DELETE' },
    );
  },

  async listSubagents(runtimeBaseUrl: string, workspaceId: string): Promise<ClaudeDocument[]> {
    return collectDocuments<SubagentSummary, SubagentDocumentResponse>(
      runtimeBaseUrl,
      workspaceId,
      'subagents',
      `workspaces/${workspaceId}/claude-code/subagents`,
      mapSubagentDocument,
    );
  },

  async createSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<ClaudeDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    const payload = {
      fileName,
      content: document.content,
      name: document.title,
      description: document.description,
    };
    const response = await apiRequest<SubagentDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/subagents/${document.scope}`,
      { method: 'POST', body: payload },
    );
    return mapSubagentDocument(response.scope, response.document);
  },

  async updateSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<ClaudeDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    const payload = {
      content: document.content,
      name: document.title,
      description: document.description,
    };
    const response = await apiRequest<SubagentDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/subagents/${document.scope}/${fileName}`,
      { method: 'PUT', body: payload },
    );
    return mapSubagentDocument(response.scope, response.document);
  },

  async deleteSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<void> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/subagents/${document.scope}/${fileName}`,
      { method: 'DELETE' },
    );
  },

  async listMemoryDocuments(runtimeBaseUrl: string, workspaceId: string): Promise<ClaudeDocument[]> {
    const collection = await apiRequest<MemoryCollectionResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/memory`,
    );

    const documents = await Promise.all(
      collection.documents.map(async (summary) => {
        const detail = await apiRequest<MemoryDocumentResponse>(
          runtimeBaseUrl,
          `workspaces/${workspaceId}/claude-code/memory/${summary.fileName}`,
        );
        return mapMemoryDocument(detail.document);
      }),
    );

    return documents.sort((a, b) => a.title.localeCompare(b.title));
  },

  async createMemoryDocument(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<ClaudeDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    const response = await apiRequest<MemoryDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/memory`,
      { method: 'POST', body: { fileName, content: document.content } },
    );
    return mapMemoryDocument(response.document);
  },

  async updateMemoryDocument(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<ClaudeDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    const response = await apiRequest<MemoryDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/memory/${fileName}`,
      { method: 'PUT', body: { content: document.content } },
    );
    return mapMemoryDocument(response.document);
  },

  async deleteMemoryDocument(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: ClaudeDocument,
  ): Promise<void> {
    const fileName = (document.metadata?.fileName as string) ?? document.id.split(':').at(-1) ?? document.id;
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/memory/${fileName}`,
      { method: 'DELETE' },
    );
  },

  async listMcpServers(runtimeBaseUrl: string, workspaceId: string): Promise<ClaudeMcpServer[]> {
    const response = await apiRequest<McpServerCollectionResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/mcp-servers`,
    );
    return normalizeMcpServers(response);
  },

  async createMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: ClaudeMcpServer,
  ): Promise<ClaudeMcpServer> {
    const payload = { mcpServers: buildMcpServerPayload(server) };
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/mcp-servers/${server.scope}`,
      { method: 'POST', body: payload },
    );
    const config = response.mcpServers?.[server.name];
    if (!config) {
      throw new Error(`無法建立 MCP 伺服器：${server.name}`);
    }
    return mapMcpServer(response.scope, server.name, config);
  },

  async updateMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: ClaudeMcpServer,
  ): Promise<ClaudeMcpServer> {
    const payload = { mcpServers: buildMcpServerPayload(server) };
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/mcp-servers/${server.scope}/${server.name}`,
      { method: 'PUT', body: payload, headers: { 'If-Match': '*' } },
    );
    const config = response.mcpServers?.[server.name];
    if (!config) {
      throw new Error(`無法更新 MCP 伺服器：${server.name}`);
    }
    return mapMcpServer(response.scope, server.name, config);
  },

  async deleteMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: Pick<ClaudeMcpServer, 'name' | 'scope'>,
  ): Promise<void> {
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/mcp-servers/${server.scope}/${server.name}`,
      { method: 'DELETE' },
    );
  },

  async toggleMcpServerStatus(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: Pick<ClaudeMcpServer, 'name' | 'scope'>,
    enabled: boolean,
  ): Promise<ClaudeMcpServer> {
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/mcp-servers/${server.scope}/${server.name}/toggle?enabled=${enabled}`,
      { method: 'PATCH' },
    );
    const config = response.mcpServers[server.name];
    if (!config) {
      throw new Error(`無法切換 MCP 伺服器狀態：${server.name}`);
    }
    return mapMcpServer(response.scope, server.name, config);
  },

  async importMcpServers(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: { scope: ClaudeMcpScope; file: File; overwrite?: boolean },
  ): Promise<McpImportResponse> {
    const formData = new FormData();
    formData.append('scope', payload.scope);
    formData.append('overwrite', payload.overwrite ? 'true' : 'false');
    formData.append('file', payload.file);
    return apiRequest<McpImportResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/mcp-import`,
      { method: 'POST', body: formData },
    );
  },

  // ============ Skills API ============
  async listSkills(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope?: 'project' | 'user' | 'plugin'
  ): Promise<FileCollectionResponse> {
    const path = scope
      ? `workspaces/${workspaceId}/claude-code/skills/tree?scope=${scope}`
      : `workspaces/${workspaceId}/claude-code/skills/tree`;
    return apiRequest<FileCollectionResponse>(runtimeBaseUrl, path);
  },

  async listPluginSkills(runtimeBaseUrl: string, workspaceId: string): Promise<PluginSkillsResponse> {
    return apiRequest<PluginSkillsResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/skills/plugins`,
    );
  },

  async getSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' | 'plugin' = 'project',
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/skills/content?path=${encodeURIComponent(filePath)}&scope=${scope}`,
    );
  },

  async createSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: FileCreateRequest,
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/skills`,
      { method: 'POST', body: payload },
    );
  },

  async updateSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    payload: FileUpdateRequest,
    scope?: 'project' | 'user',
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/skills/content?path=${encodeURIComponent(filePath)}&scope=${scope}&content=${encodeURIComponent(payload.content)}`,
      { method: 'PUT' },
    );
  },

  async deleteSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' = 'project',
    recursive: boolean = false,
  ): Promise<FileDeleteResponse> {
    return apiRequest<FileDeleteResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/skills/${filePath}?scope=${scope}&recursive=${recursive}`,
      { method: 'DELETE' },
    );
  },

  async moveSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    sourcePath: string,
    destPath: string,
    scope: 'project' | 'user' = 'project',
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/skills/move?scope=${scope}`,
      { method: 'POST', body: { sourcePath, destPath } },
    );
  },

  async copySkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    sourcePath: string,
    destPath: string,
    scope: 'project' | 'user' = 'project',
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/skills/copy?sourcePath=${encodeURIComponent(sourcePath)}&destPath=${encodeURIComponent(destPath)}&sourceScope=${scope}&destScope=${scope}&overwrite=false`,
      { method: 'POST' },
    );
  },

  // ============ Scripts API ============
  async listScripts(runtimeBaseUrl: string, workspaceId: string, scope?: 'project' | 'user' | 'plugin'): Promise<FileCollectionResponse> {
    const path = scope
      ? `workspaces/${workspaceId}/claude-code/scripts/tree?scope=${scope}`
      : `workspaces/${workspaceId}/claude-code/scripts/tree`;
    return apiRequest<FileCollectionResponse>(runtimeBaseUrl, path);
  },

  async getScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' = 'project',
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/scripts/content?path=${encodeURIComponent(filePath)}&scope=${scope}`,
    );
  },

  async createScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: FileCreateRequest,
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/scripts`,
      { method: 'POST', body: payload },
    );
  },

  async updateScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    payload: FileUpdateRequest,
    scope?: 'project' | 'user',
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/scripts/content?path=${encodeURIComponent(filePath)}&scope=${scope}&content=${encodeURIComponent(payload.content)}`,
      { method: 'PUT' },
    );
  },

  async deleteScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' = 'project',
    recursive: boolean = false,
  ): Promise<FileDeleteResponse> {
    return apiRequest<FileDeleteResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/scripts/${filePath}?scope=${scope}&recursive=${recursive}`,
      { method: 'DELETE' },
    );
  },

  async moveScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    sourcePath: string,
    destPath: string,
    scope: 'project' | 'user' = 'project',
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/scripts/move?scope=${scope}`,
      { method: 'POST', body: { sourcePath, destPath } },
    );
  },

  async copyScript(
    runtimeBaseUrl: string,
    workspaceId: string,
    sourcePath: string,
    destPath: string,
    scope: 'project' | 'user' = 'project',
  ): Promise<FileResponse> {
    return apiRequest<FileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/scripts/copy?sourcePath=${encodeURIComponent(sourcePath)}&destPath=${encodeURIComponent(destPath)}&sourceScope=${scope}&destScope=${scope}&overwrite=false`,
      { method: 'POST' },
    );
  },

  // ============ Marketplaces ============
  async getMarketplaces(runtimeBaseUrl: string, workspaceId: string): Promise<MarketplaceListResponse> {
    return apiRequest<MarketplaceListResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/settings/marketplaces`,
    );
  },
};

export type ClaudeCodeApi = typeof claudeCodeApi;

// ============ Skills & Scripts Types ============
export type FileCollectionType = 'skills' | 'scripts';

export type FileType = 'markdown' | 'typescript' | 'javascript' | 'yaml' | 'json' | 'python' | 'shell' | 'unknown';

export interface FileSummary {
  fileName: string;
  filePath: string;
  fileType: FileType;
  scope: 'project' | 'user' | 'plugin';
  sizeBytes: number;
  sizeLabel: string;
  updatedAt: string;
  name: string | null;
  description: string | null;
  metadata: Record<string, unknown>;
}

export interface FileDetail extends FileSummary {
  content: string;
}

export interface FileTreeNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  fileType?: FileType;
  scope?: 'project' | 'user' | 'plugin';
  children?: FileTreeNode[] | null;
  sizeBytes?: number;
  updatedAt?: string;
  skillName?: string;
  skillDescription?: string;
}

export interface FileCollectionResponse {
  workspaceId: string;
  collectionType: FileCollectionType;
  files: FileSummary[];
  tree: FileTreeNode[];
}

// 新的統一 API 回應格式
export interface FileResponse {
  path: string;
  scope?: string;
  content: string;
  size: number;
  updatedAt: string;
  versionId?: string;
  contentHash?: string;
}

export interface FileCreateRequest {
  fileName: string;
  content: string;
  namespace?: string | null;
  scope?: 'project' | 'user';
}

export interface FileUpdateRequest {
  content: string;
}

export interface FileDeleteResponse {
  workspaceId: string;
  collectionType: FileCollectionType;
  filePath: string;
  deleted: boolean;
}

export interface PluginSkillInfo {
  pluginId: string;
  pluginName: string;
  marketplaceName: string;
  skillName: string;
  skillPath: string;
}

export interface PluginSkillsResponse {
  workspaceId: string;
  plugins: PluginSkillInfo[];
}
