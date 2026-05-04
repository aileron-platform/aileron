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

type CliSlashCommandScope = 'project' | 'user' | 'extension';

interface CliSlashCommandSummary {
  fileName: string;
  namespace?: string | null;
  description?: string | null;
  scope: CliSlashCommandScope;
  size: string;
  format: 'markdown' | 'toml';
  extensionName?: string | null;
  extensionVersion?: string | null;
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

type CliSubagentScope = 'project' | 'user' | 'plugin';

interface CliSubagentSummary {
  fileName: string;
  name?: string | null;
  description?: string | null;
  scope: CliSubagentScope;
  size: string;
  pluginName?: string | null;
  marketplaceName?: string | null;
}

interface CliSubagentDetail extends CliSubagentSummary {
  content: string;
}

interface CliSubagentScopesResponse {
  workspaceId: string;
  scopes: Array<{ scope: CliSubagentScope; documents: CliSubagentSummary[] }>;
}

interface CliSubagentDocumentResponse {
  workspaceId: string;
  scope: CliSubagentScope;
  document: CliSubagentDetail;
}

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
    extensionName: detail.extensionName ?? undefined,
    extensionVersion: detail.extensionVersion ?? undefined,
    metadata: {
      fileName: detail.fileName,
      namespace,
      format: detail.format,
      extensionName: detail.extensionName ?? undefined,
      extensionVersion: detail.extensionVersion ?? undefined,
    },
  };
};

const mapCliSubagentDocument = (
  scope: CliSubagentScope,
  detail: CliSubagentDetail,
): AgentDocument => ({
  id: buildCliDocumentId(scope, detail.fileName),
  title: detail.name ?? detail.fileName,
  description: detail.description ?? '',
  content: detail.content,
  scope,
  size: detail.size,
  pluginName: detail.pluginName ?? undefined,
  marketplaceName: detail.marketplaceName ?? undefined,
  metadata: {
    fileName: detail.fileName,
    source: scope,
  },
});

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
  extensionName?: string;
  extensionVersion?: string;
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

export interface GeminiExtensionSummary {
  name: string;
  version?: string | null;
  installSource?: string | null;
  installType?: string | null;
  releaseTag?: string | null;
  enabledHere: boolean;
  overrides: string[];
  resourceCounts: Record<'mcp' | 'commands' | 'skills' | 'hooks' | 'policies', number>;
  excludeToolsCount: number;
}

export interface GeminiExtensionDetail {
  name: string;
  version?: string | null;
  installInfo?: {
    source?: string | null;
    type?: string | null;
    releaseTag?: string | null;
  } | null;
  enabledHere: boolean;
  overrides: string[];
  contextFile?: { path: string; content: string } | null;
  policies: Array<{ path: string; content: string }>;
  excludeTools: string[];
  mcpServers: Array<{ name: string; config: Record<string, unknown> }>;
  slashCommands: Array<Record<string, unknown>>;
  skills: Array<Record<string, unknown>>;
  hooks: Array<Record<string, unknown>>;
}

export interface GeminiExtensionListResponse {
  workspaceId: string;
  extensions: GeminiExtensionSummary[];
}

export interface GeminiExtensionDetailResponse {
  workspaceId: string;
  extension: GeminiExtensionDetail;
}

export interface CodexAgentsMdCaveat {
  type: 'override' | 'fallback' | 'size_limit';
  path?: string | null;
  messageKey: string;
  metadata?: Record<string, unknown>;
}

export interface CodexAgentsMdResponse extends AgentsMdResponse {
  path: string;
  exists: boolean;
  activePath?: string | null;
  maxBytes: number;
  sizeBytes: number;
  caveats: CodexAgentsMdCaveat[];
}

export interface CodexRulesFileSummary {
  name: string;
  path: string;
  sizeBytes: number;
}

export interface CodexRulesListResponse {
  workspaceId: string;
  layer: 'user' | 'project';
  directory: string;
  files: CodexRulesFileSummary[];
}

export interface CodexTextFileResponse {
  workspaceId: string;
  layer: 'user' | 'project' | 'plugin';
  path: string;
  content: string;
  exists: boolean;
}

export interface CodexRulesValidationResponse {
  valid: boolean;
  exitCode: number;
  stdout: string;
  stderr: string;
}

export type CodexHookSource = 'hooks_json' | 'inline_config' | 'plugin' | 'built_in' | 'project' | 'user';
export type CodexHookEventScope = 'session_start' | 'turn';
export type CodexHookMatcherTarget = 'source' | 'tool_name' | 'none';

export interface CodexHookEventMetadata {
  event: string;
  scope: CodexHookEventScope;
  matcherSupported: boolean;
  matcherTarget: CodexHookMatcherTarget;
  matcherExamples: string[];
}

export interface CodexHookCommandAction {
  type: 'command';
  command: string;
  timeout?: number | null;
  statusMessage?: string | null;
  raw?: Record<string, unknown>;
}

export interface CodexHookEntry {
  id: string;
  event: string;
  index: number;
  matcher?: string | null;
  actions: CodexHookCommandAction[];
  action?: CodexHookCommandAction | Record<string, unknown>;
  source: CodexHookSource;
  layer?: 'user' | 'project' | null;
  readOnly: boolean;
  sourcePath?: string | null;
  pluginId?: string | null;
  pluginName?: string | null;
  marketplaceName?: string | null;
  raw?: Record<string, unknown>;
}

export interface CodexHooksDocumentResponse extends CodexTextFileResponse {
  featureEnabled: boolean;
  inlineHooks: Array<Record<string, unknown>>;
  entries: CodexHookEntry[];
  eventMetadata: CodexHookEventMetadata[];
}

export interface CodexHooksScopesResponse {
  workspaceId: string;
  scopes: CodexHooksDocumentResponse[];
}

export interface CodexPluginSummary {
  id: string;
  name: string;
  marketplace?: string | null;
  listed: boolean;
  installed: boolean;
  enabled: boolean;
  path?: string | null;
  sourcePath?: string | null;
  bundled: Record<string, unknown>;
}

export interface CodexPluginsResponse {
  workspaceId: string;
  plugins: CodexPluginSummary[];
  installReserved: boolean;
}

export interface CodexFileSummary {
  name: string;
  path: string;
  sizeBytes: number;
  source: 'user' | 'project' | 'plugin' | 'built_in';
  readOnly: boolean;
  metadata: Record<string, unknown>;
}

export interface CodexFileListResponse {
  workspaceId: string;
  layer: 'user' | 'project' | 'plugin';
  resource: string;
  directory: string;
  files: CodexFileSummary[];
  config: Record<string, unknown>;
}

export type CodexSubagentSource = 'built_in' | 'user' | 'project' | 'plugin';

export interface CodexSubagentDefinition {
  name: string;
  description: string;
  developer_instructions: string;
  nickname_candidates?: string[] | null;
  model?: string | null;
  model_reasoning_effort?: string | null;
  sandbox_mode?: string | null;
  mcp_servers?: Record<string, unknown> | null;
  skills?: Record<string, unknown> | null;
}

export interface CodexSubagentItem {
  id: string;
  name: string;
  source: CodexSubagentSource;
  editable: boolean;
  readOnly: boolean;
  layer?: 'user' | 'project' | null;
  path?: string | null;
  relativePath?: string | null;
  sourcePath?: string | null;
  content: string;
  definition?: CodexSubagentDefinition | null;
  effective: boolean;
  overridden: boolean;
  pluginId?: string | null;
  pluginName?: string | null;
  marketplaceName?: string | null;
  metadata: Record<string, unknown>;
}

export interface CodexSubagentRegistrySource {
  layer: 'user' | 'project';
  path: string;
  settings: {
    max_threads?: number | null;
    max_depth?: number | null;
    job_max_runtime_seconds?: number | null;
  };
}

export interface CodexSubagentsResponse {
  workspaceId: string;
  items: CodexSubagentItem[];
  registry: CodexSubagentRegistrySource[];
}

const cloneHookRuleMap = (hooks: AgentHookRuleMap | undefined): AgentHookRuleMap => {
  if (!hooks) return {};
  return Object.fromEntries(
    Object.entries(hooks).map(([event, rules]) => [
      event,
      rules.map((rule) => ({
        matcher: rule.matcher,
        pluginName: rule.pluginName,
        marketplaceName: rule.marketplaceName,
        extensionName: rule.extensionName,
        extensionVersion: rule.extensionVersion,
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
        .map((action) => {
          const nextAction: AgentHookActionConfig = {
            type: 'command',
            command: action.command?.trim() ?? '',
            timeout: typeof action.timeout === 'number' ? action.timeout : null,
          };
          if (action.name?.trim()) {
            nextAction.name = action.name.trim();
          }
          if (action.description?.trim()) {
            nextAction.description = action.description.trim();
          }
          if (action.statusMessage?.trim()) {
            nextAction.statusMessage = action.statusMessage.trim();
          }
          return nextAction;
        }),
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
          name: action.name ?? undefined,
          command: action.command ?? '',
          timeout: typeof action.timeout === 'number' ? action.timeout : undefined,
          description: action.description ?? undefined,
          statusMessage: action.statusMessage ?? undefined,
        })),
      })),
      pluginName: rules.find((rule) => rule.pluginName)?.pluginName ?? undefined,
      marketplaceName: rules.find((rule) => rule.marketplaceName)?.marketplaceName ?? undefined,
      extensionName: rules.find((rule) => rule.extensionName)?.extensionName ?? undefined,
      extensionVersion: rules.find((rule) => rule.extensionVersion)?.extensionVersion ?? undefined,
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
  extensionName: config.extensionName,
  extensionVersion: config.extensionVersion,
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
  async getCodexAgentsMd(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: string,
  ): Promise<CodexAgentsMdResponse> {
    return apiRequest<CodexAgentsMdResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/agents-md?scope=${scope}`,
    );
  },

  async updateCodexAgentsMd(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: { scope: string; content: string },
  ): Promise<AgentsMdUpdateResponse> {
    return apiRequest<AgentsMdUpdateResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/agents-md`,
      { method: 'PUT', body: payload },
    );
  },

  async listCodexRules(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
  ): Promise<CodexRulesListResponse> {
    return apiRequest<CodexRulesListResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules?layer=${layer}`,
    );
  },

  async getCodexRulesFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    path: string,
  ): Promise<CodexTextFileResponse> {
    return apiRequest<CodexTextFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules/file?layer=${layer}&path=${encodeURIComponent(path)}`,
    );
  },

  async updateCodexRulesFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    path: string,
    content: string,
  ): Promise<CodexTextFileResponse> {
    return apiRequest<CodexTextFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules/file?layer=${layer}&path=${encodeURIComponent(path)}`,
      { method: 'PUT', body: { path, content } },
    );
  },

  async deleteCodexRulesFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    path: string,
  ): Promise<void> {
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules/file?layer=${layer}&path=${encodeURIComponent(path)}`,
      { method: 'DELETE' },
    );
  },

  async validateCodexRulesFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    path: string,
    command: string[],
  ): Promise<CodexRulesValidationResponse> {
    return apiRequest<CodexRulesValidationResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules/validate`,
      { method: 'POST', body: { layer, path, command } },
    );
  },

  async getCodexHooks(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
  ): Promise<CodexHooksDocumentResponse> {
    return apiRequest<CodexHooksDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks?layer=${layer}`,
    );
  },

  async listCodexHooksScopes(
    runtimeBaseUrl: string,
    workspaceId: string,
  ): Promise<CodexHooksScopesResponse> {
    return apiRequest<CodexHooksScopesResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks-scopes`,
    );
  },

  async updateCodexHooks(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    content: string,
  ): Promise<CodexHooksDocumentResponse> {
    return apiRequest<CodexHooksDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks?layer=${layer}`,
      { method: 'PUT', body: { content } },
    );
  },

  async enableCodexHooks(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
  ): Promise<{ workspaceId: string; featureEnabled: boolean }> {
    return apiRequest<{ workspaceId: string; featureEnabled: boolean }>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks/enable?layer=${layer}`,
      { method: 'POST' },
    );
  },

  async listCodexPlugins(runtimeBaseUrl: string, workspaceId: string): Promise<CodexPluginsResponse> {
    return apiRequest<CodexPluginsResponse>(runtimeBaseUrl, `workspaces/${workspaceId}/codex/plugins`);
  },

  async setCodexPluginEnabled(
    runtimeBaseUrl: string,
    workspaceId: string,
    pluginId: string,
    layer: 'user' | 'project',
    enabled: boolean,
  ): Promise<{ workspaceId: string; layer: 'user' | 'project'; pluginId: string; enabled: boolean; newThreadRequired: boolean }> {
    return apiRequest<{ workspaceId: string; layer: 'user' | 'project'; pluginId: string; enabled: boolean; newThreadRequired: boolean }>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/plugins/${encodeURIComponent(pluginId)}`,
      { method: 'PATCH', body: { layer, enabled } },
    );
  },

  async listGeminiExtensions(runtimeBaseUrl: string, workspaceId: string): Promise<GeminiExtensionListResponse> {
    return apiRequest<GeminiExtensionListResponse>(runtimeBaseUrl, `workspaces/${workspaceId}/gemini/extensions`);
  },

  async getGeminiExtension(runtimeBaseUrl: string, workspaceId: string, name: string): Promise<GeminiExtensionDetailResponse> {
    return apiRequest<GeminiExtensionDetailResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/gemini/extensions/${encodeURIComponent(name)}`,
    );
  },

  async enableGeminiExtension(
    runtimeBaseUrl: string,
    workspaceId: string,
    name: string,
    scope: 'workspace' | 'user',
  ): Promise<{ workspaceId: string; name: string; enabledHere: boolean; overrides: string[] }> {
    return apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/gemini/extensions/${encodeURIComponent(name)}/enable?scope=${scope}`,
      { method: 'POST' },
    );
  },

  async disableGeminiExtension(
    runtimeBaseUrl: string,
    workspaceId: string,
    name: string,
    scope: 'workspace' | 'user',
  ): Promise<{ workspaceId: string; name: string; enabledHere: boolean; overrides: string[] }> {
    return apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/gemini/extensions/${encodeURIComponent(name)}/disable?scope=${scope}`,
      { method: 'POST' },
    );
  },

  async listCodexFiles(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    layer: 'user' | 'project' | 'plugin',
  ): Promise<CodexFileListResponse> {
    return apiRequest<CodexFileListResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/files?layer=${layer}`,
    );
  },

  async getCodexFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    layer: 'user' | 'project' | 'plugin',
    path: string,
    pluginId?: string,
  ): Promise<CodexTextFileResponse> {
    const query = new URLSearchParams({ layer, path });
    if (pluginId) {
      query.set('pluginId', pluginId);
    }
    return apiRequest<CodexTextFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/file?${query.toString()}`,
    );
  },

  async updateCodexFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    layer: 'user' | 'project',
    path: string,
    content: string,
  ): Promise<CodexTextFileResponse> {
    return apiRequest<CodexTextFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/file?layer=${layer}`,
      { method: 'PUT', body: { path, content } },
    );
  },

  async deleteCodexFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    layer: 'user' | 'project',
    path: string,
  ): Promise<void> {
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/file?layer=${layer}&path=${encodeURIComponent(path)}`,
      { method: 'DELETE' },
    );
  },

  async listCodexSubagents(runtimeBaseUrl: string, workspaceId: string): Promise<CodexSubagentsResponse> {
    return apiRequest<CodexSubagentsResponse>(runtimeBaseUrl, `workspaces/${workspaceId}/codex/subagents`);
  },

  async getCodexSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    source: CodexSubagentSource,
    path: string,
    pluginId?: string,
  ): Promise<CodexSubagentItem> {
    const query = new URLSearchParams({ source, path });
    if (pluginId) {
      query.set('pluginId', pluginId);
    }
    return apiRequest<CodexSubagentItem>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/subagents/detail?${query.toString()}`,
    );
  },

  async saveCodexSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: {
      layer: 'user' | 'project';
      path?: string | null;
      previousPath?: string | null;
      content?: string | null;
      definition?: CodexSubagentDefinition | null;
      overwrite?: boolean;
    },
  ): Promise<CodexSubagentItem> {
    return apiRequest<CodexSubagentItem>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/subagents`,
      { method: 'PUT', body: payload },
    );
  },

  async deleteCodexSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    path: string,
  ): Promise<void> {
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/subagents?layer=${layer}&path=${encodeURIComponent(path)}`,
      { method: 'DELETE' },
    );
  },

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
    scope?: 'project' | 'user' | 'plugin' | 'extension',
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
    scope: 'project' | 'user' | 'plugin' | 'extension' = 'project',
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

  // ============ Subagents ============

  async listSubagents(
    runtimeBaseUrl: string,
    workspaceId: string,
  ): Promise<AgentDocument[]> {
    const scopesRes = await apiRequest<CliSubagentScopesResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents`,
    );

    const documents: AgentDocument[] = [];
    for (const group of scopesRes.scopes) {
      for (const summary of group.documents) {
        const detailRes = await apiRequest<CliSubagentDocumentResponse>(
          runtimeBaseUrl,
          `workspaces/${workspaceId}/${apiPrefix}/subagents/${group.scope}/${encodeURIComponent(summary.fileName)}`,
        );
        documents.push(mapCliSubagentDocument(group.scope, detailRes.document));
      }
    }
    return documents.sort((a, b) => a.title.localeCompare(b.title));
  },

  async createSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliSubagentScope;
    const payload = {
      fileName: (document.metadata?.fileName as string) ?? document.title,
      content: document.content,
    };
    const response = await apiRequest<CliSubagentDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents/${scope}`,
      { method: 'POST', body: payload },
    );
    return mapCliSubagentDocument(response.scope, response.document);
  },

  async updateSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliSubagentScope;
    const fileName = (document.metadata?.fileName as string) ?? document.title;
    const response = await apiRequest<CliSubagentDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents/${scope}/${encodeURIComponent(fileName)}`,
      {
        method: 'PUT',
        body: {
          fileName: (document.metadata?.fileName as string | undefined) ?? document.title,
          content: document.content,
        },
      },
    );
    return mapCliSubagentDocument(response.scope, response.document);
  },

  async deleteSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: Pick<AgentDocument, 'scope' | 'metadata' | 'title'>,
  ): Promise<void> {
    const scope = document.scope as CliSubagentScope;
    const fileName = (document.metadata?.fileName as string) ?? document.title;
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents/${scope}/${encodeURIComponent(fileName)}`,
      { method: 'DELETE' },
    );
  },
});

export type AgentSettingsApi = ReturnType<typeof createAgentSettingsApi>;
