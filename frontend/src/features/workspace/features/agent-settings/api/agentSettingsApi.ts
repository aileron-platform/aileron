import { ApiClient } from '@/shared/api/apiClient';
import {
  parseResourceError,
  parseResourceResult,
  type AvailableScope,
  type ResourceError,
  type ResourceListResult,
} from '@/shared/components/document-resource';
import type {
  AgentDocument,
  AgentScope,
  AgentFileCollectionResponse,
  AgentFileResponse,
  AgentFileCreatePayload,
  AgentFileUpdatePayload,
  AgentFileDeleteResponse,
  AgentPluginSkillsResponse,
} from '../model/documents';
import type {
  AgentMcpServer,
  CodexPluginMcpPolicy,
} from '../model/mcp';
import type {
  AgentHookScope,
  AgentHookRuleMap,
  AgentHookScopesResponse,
  AgentHookScopeResponse,
  AgentHookDeleteResponse,
  AgentHookExportResponse,
  AgentHookImportPayload,
  AgentHookImportResponse,
  AgentHookScopeDocument,
  AgentHookWithEvent,
  AgentHookActionConfig,
  AgentHookRuleConfig,
} from '../model/agentHookTypes';

export type {
  AgentHookRuleMap,
  AgentHookScopesResponse,
  AgentHookScopeResponse,
  AgentHookDeleteResponse,
  AgentHookExportResponse,
  AgentHookImportPayload,
  AgentHookImportResponse,
  AgentHookScopeDocument,
  AgentHookWithEvent,
  AgentHookMatcher,
  AgentHookActionConfig,
  AgentHookRuleConfig,
} from '../model/agentHookTypes';
export type {
  AgentFileCollectionResponse,
  AgentFileResponse,
  AgentFileCreatePayload,
  AgentFileUpdatePayload,
  AgentFileDeleteResponse,
  AgentPluginSkillsResponse,
} from '../model/documents';

const createRuntimeClient = (runtimeBaseUrl: string): ApiClient => {
  return new ApiClient({
    baseUrl: runtimeBaseUrl,
    unauthorizedBehavior: 'propagate',
    executionAudience: 'workspace-runtime',
  });
};

const encodePathLocator = (locator: string): string => (
  locator.split('/').map(segment => encodeURIComponent(segment)).join('/')
);

const apiRequest = async <T>(
  runtimeBaseUrl: string,
  path: string,
  options?: {
    method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
    body?: unknown;
    headers?: Record<string, string>;
    signal?: AbortSignal;
  }
): Promise<T> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const fullPath = `/api/v1/${path.startsWith('/') ? path.slice(1) : path}`;

  const method = options?.method || 'GET';
  const headers = options?.headers;

  try {
    switch (method) {
      case 'GET':
        return options?.signal
          ? await client.get<T>(fullPath, { headers, signal: options.signal })
          : await client.get<T>(fullPath, headers);
      case 'POST':
        return options?.signal
          ? await client.post<T>(
            fullPath,
            options?.body,
            { headers, signal: options.signal },
          )
          : await client.post<T>(fullPath, options?.body, headers);
      case 'PUT':
        return await client.put<T>(fullPath, options?.body, headers);
      case 'PATCH':
        return await client.patch<T>(fullPath, options?.body, headers);
      case 'DELETE':
        return await client.delete<T>(fullPath, headers, options?.body);
      default:
        throw new Error(`Unsupported HTTP method: ${method}`);
    }
  } catch (err) {
    const parsed = parseResourceError(err);
    const error = new Error(parsed.message) as Error & ResourceError;
    if (parsed.errorCode) error.errorCode = parsed.errorCode;
    if (parsed.validationResults) error.validationResults = parsed.validationResults;
    throw error;
  }
};

const apiBlobRequest = async (
  runtimeBaseUrl: string,
  path: string,
): Promise<Blob> => {
  const client = createRuntimeClient(runtimeBaseUrl);
  const fullPath = `/api/v1/${path.startsWith('/') ? path.slice(1) : path}`;

  try {
    return await client.getBlob(fullPath);
  } catch (err) {
    const parsed = parseResourceError(err);
    const error = new Error(parsed.message) as Error & ResourceError;
    if (parsed.errorCode) error.errorCode = parsed.errorCode;
    if (parsed.validationResults) error.validationResults = parsed.validationResults;
    throw error;
  }
};

type CliSlashCommandScope = 'project' | 'user' | 'plugin';

interface CliSlashCommandSummary {
  path: string;
  description?: string | null;
  scope: CliSlashCommandScope;
  size: string;
  format?: 'markdown' | 'toml';
  pluginName?: string | null;
  marketplaceName?: string | null;
}

interface CliSlashCommandDetail extends CliSlashCommandSummary {
  content: string;
}

interface CliSlashCommandScopesResponse {
  workspaceId: string;
  items: CliSlashCommandSummary[];
  availableScopes: AvailableScope[];
}

interface CliSlashCommandScopeResponse {
  workspaceId: string;
  scope: CliSlashCommandScope;
  revision?: string;
  documents: CliSlashCommandSummary[];
}

interface CliSlashCommandDocumentResponse {
  workspaceId: string;
  scope: CliSlashCommandScope;
  revision?: string;
  document: CliSlashCommandDetail;
}

const buildCliDocumentId = (
  scope: string,
  fileName: string,
  namespace?: string,
) => [scope, namespace, fileName].filter(Boolean).join(':');

type CliSubagentScope = 'project' | 'user' | 'plugin';

interface CliSubagentSummary {
  path: string;
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
  items: CliSubagentSummary[];
  availableScopes: AvailableScope[];
}

interface CliSubagentScopeResponse {
  workspaceId: string;
  scope: CliSubagentScope;
  revision?: string;
  documents: CliSubagentSummary[];
}

interface CliSubagentDocumentResponse {
  workspaceId: string;
  scope: CliSubagentScope;
  revision?: string;
  document: CliSubagentDetail;
}

type CliOutputStyleScope = 'project' | 'user' | 'plugin';

interface CliOutputStyleSummary {
  fileName: string;
  name?: string | null;
  description?: string | null;
  scope: CliOutputStyleScope;
  size: string;
  pluginId?: string | null;
  pluginName?: string | null;
  marketplaceId?: string | null;
  enabled?: boolean;
  readOnly?: boolean;
  editable?: boolean;
  relativeSourcePath?: string | null;
  generation?: number;
  provenance?: Record<string, unknown> | null;
}

interface CliOutputStyleDetail extends CliOutputStyleSummary {
  content: string;
}

interface CliOutputStyleScopesResponse {
  workspaceId: string;
  providerResourceGeneration?: number;
  scopes: Array<{
    scope: CliOutputStyleScope;
    revision?: string;
    documents: CliOutputStyleSummary[];
  }>;
}

interface CliOutputStyleScopeResponse {
  workspaceId: string;
  providerResourceGeneration?: number;
  scope: CliOutputStyleScope;
  revision?: string;
  documents: CliOutputStyleSummary[];
}

interface CliOutputStyleDocumentResponse {
  workspaceId: string;
  providerResourceGeneration?: number;
  scope: CliOutputStyleScope;
  revision?: string;
  document: CliOutputStyleDetail;
}

interface CliMemorySummary {
  path: string;
  scope: AgentScope;
  name?: string | null;
  description?: string | null;
  size: string;
}

interface CliMemoryCollectionResponse {
  workspaceId: string;
  revision?: string;
  items: CliMemorySummary[];
  availableScopes: AvailableScope[];
}

type CliMemoryDocumentResponse = {
  revision?: string;
  resource?: CliMemorySummary & { content: string };
  document?: CliMemorySummary & { content: string };
};

const mapCliSlashCommandDocument = (
  scope: CliSlashCommandScope,
  detail: CliSlashCommandDetail,
  revision?: string,
): AgentDocument => {
  const pluginName = detail.pluginName ?? undefined;
  const marketplaceName = detail.marketplaceName ?? undefined;
  const commandName = detail.path.replace(/\.(md|toml)$/i, '');
  const title = pluginName ? `${pluginName}:${commandName}` : commandName;

  return {
    id: buildCliDocumentId(scope, detail.path),
    title,
    description: detail.description ?? '',
    content: detail.content,
    scope,
    size: detail.size,
    pluginName,
    marketplaceName,
    metadata: {
      fileName: detail.path,
      relativePath: detail.path,
      source: scope,
      format: detail.format ?? 'markdown',
      pluginName,
      marketplaceName,
      revision,
    },
  };
};

const mapCliSubagentDocument = (
  scope: CliSubagentScope,
  detail: CliSubagentDetail,
  revision?: string,
): AgentDocument => ({
  id: buildCliDocumentId(scope, detail.path),
  title: detail.name ?? detail.path,
  description: detail.description ?? '',
  content: detail.content,
  scope,
  size: detail.size,
  pluginName: detail.pluginName ?? undefined,
  marketplaceName: detail.marketplaceName ?? undefined,
  metadata: {
    fileName: detail.path,
    relativePath: detail.path,
    source: scope,
    revision,
  },
});

const mapCliOutputStyleDocument = (
  scope: CliOutputStyleScope,
  detail: CliOutputStyleDetail,
  revision?: string,
): AgentDocument => ({
  id: buildCliDocumentId(
    scope,
    detail.fileName,
    scope === 'plugin' ? detail.pluginId ?? undefined : undefined,
  ),
  title: detail.name ?? detail.fileName,
  description: detail.description ?? '',
  content: detail.content,
  scope,
  size: detail.size,
  pluginName: detail.pluginName ?? undefined,
  marketplaceName: detail.marketplaceId ?? undefined,
  metadata: {
    fileName: detail.fileName,
    source: scope,
    revision,
    pluginId: detail.pluginId ?? undefined,
    marketplaceId: detail.marketplaceId ?? undefined,
    enabled: detail.enabled,
    readOnly: detail.readOnly ?? scope === 'plugin',
    editable: detail.editable ?? scope !== 'plugin',
    relativeSourcePath: detail.relativeSourcePath ?? undefined,
    generation: detail.generation,
    provenance: detail.provenance ?? undefined,
  },
});

const mapCliMemoryDocument = (
  detail: CliMemorySummary & { content: string },
  revision?: string,
): AgentDocument => ({
  id: buildCliDocumentId(detail.scope, detail.path),
  title: detail.name ?? detail.path,
  description: detail.description ?? '',
  content: detail.content,
  scope: detail.scope,
  size: detail.size,
  metadata: {
    fileName: detail.path,
    relativePath: detail.path,
    source: detail.scope,
    revision,
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
  serverId?: string;
  pluginId?: string;
  relativeSourcePath?: string;
  generation?: number;
  readOnly?: boolean;
  editable?: boolean;
  effective?: boolean;
  policy?: CodexPluginMcpPolicy;
  policyRevision?: string;
}

interface McpScopeResponse {
  workspaceId: string;
  scope: AgentMcpScope;
  revision?: string;
  mcpServers: Record<string, McpServerConfigResponse>;
}

interface McpServerCollectionResponse {
  workspaceId: string;
  scopes: Array<{
    scope: AgentMcpScope;
    revision?: string;
    mcpServers: Record<string, McpServerConfigResponse>;
  }>;
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
  revision?: string;
}

interface AgentsMdUpdateResponse {
  workspaceId: string;
  scope: string;
  revision?: string;
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
  revision?: string;
}

export interface CodexRulesValidationResponse {
  valid: boolean;
  exitCode: number;
  stdout: string;
  stderr: string;
}

export type CodexHookScope = 'user' | 'project' | 'plugin' | 'session';
export type CodexHookSource = 'hooks_json' | 'inline_config' | 'plugin' | 'session';
export type CodexHookEventScope = 'start' | 'turn' | 'end';
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
  async?: boolean | null;
  commandWindows?: string | null;
  additionalContextLimit?: number | null;
  raw?: Record<string, unknown>;
}

export type CodexHookAction = CodexHookCommandAction | Record<string, unknown>;

export interface CodexHookEntry {
  id: string;
  event: string;
  index: number;
  matcher?: string | null;
  actions: CodexHookAction[];
  action?: CodexHookAction;
  source: CodexHookSource;
  layer?: 'user' | 'project' | null;
  hookScope?: CodexHookScope | null;
  readOnly: boolean;
  editable?: boolean;
  scope?: CodexHookScope | null;
  sourcePath?: string | null;
  pluginId?: string | null;
  pluginName?: string | null;
  marketplaceName?: string | null;
  trustState?: 'trusted' | 'untrusted' | 'modified' | 'mixed';
  trusted?: boolean;
  effective?: boolean;
  trustRevision?: string;
  generation?: number;
  raw?: Record<string, unknown>;
}

export interface CodexPluginMcpPolicyUpdateResponse {
  workspaceId: string;
  scope: 'user';
  pluginId: string;
  serverId: string;
  policy: CodexPluginMcpPolicy;
  effective: boolean;
  revision: string;
  providerResourceGeneration: number;
  newThreadRequired: true;
}

export interface CodexPluginHookTrustUpdateResponse {
  workspaceId: string;
  scope: 'user';
  pluginId: string;
  trusted: boolean;
  trustState: 'trusted' | 'untrusted' | 'modified' | 'mixed';
  revision: string;
  providerResourceGeneration: number;
  newThreadRequired: true;
}

export interface CodexHooksDocumentResponse {
  workspaceId: string;
  scope: CodexHookScope;
  path: string;
  content: string;
  exists: boolean;
  revision: string;
  featureEnabled: boolean;
  effectiveFeatureEnabled?: boolean;
  readOnly?: boolean;
  editable?: boolean;
  source?: CodexHookSource;
  inlineHooks: Array<Record<string, unknown>>;
  entries: CodexHookEntry[];
  eventMetadata: CodexHookEventMetadata[];
  providerResourceGeneration?: number;
}

export interface CodexHooksScopesResponse {
  workspaceId: string;
  scopes: CodexHooksDocumentResponse[];
}

export interface CodexPluginSummary {
  id: string;
  name: string;
  displayName: string;
  shortDescription?: string | null;
  version?: string | null;
  authorName?: string | null;
  category?: string | null;
  capabilities: string[];
  brandColor?: string | null;
  homepage?: string | null;
  marketplace?: string | null;
  listed: boolean;
  installed: boolean;
  effectiveEnabled: boolean;
  scopes: CodexPluginScopeState[];
  resourceCounts: Record<string, number>;
}

export type CodexPluginScope = 'user' | 'project';

export interface CodexPluginScopeState {
  scope: CodexPluginScope;
  configured: boolean;
  enabled?: boolean | null;
}

export interface CodexPluginDetail extends CodexPluginSummary {
  longDescription?: string | null;
  keywords: string[];
  license?: string | null;
  repository?: string | null;
  websiteURL?: string | null;
  privacyPolicyURL?: string | null;
  termsOfServiceURL?: string | null;
  defaultPrompts: string[];
  readme?: string | null;
  skills: Array<{ name: string; description?: string | null; path: string }>;
  mcpServers: Array<{ name: string; command?: string | null; url?: string | null; config: Record<string, unknown> }>;
  apps: Array<{ name: string; config: Record<string, unknown> }>;
  hooks: Array<{ name: string; path?: string | null; config: Record<string, unknown> }>;
}

export interface CodexPluginsResponse {
  workspaceId: string;
  plugins: CodexPluginSummary[];
  installReserved: boolean;
  providerResourceGeneration?: number;
}

export interface CodexPluginDetailResponse {
  workspaceId: string;
  plugin: CodexPluginDetail;
  providerResourceGeneration?: number;
}

export type ClaudePluginScope = 'user' | 'project' | 'local';

export interface ClaudePluginInstallation {
  scope: ClaudePluginScope;
  enabled: boolean;
  version?: string | null;
  installedAt?: string | null;
  lastUpdated?: string | null;
}

export interface ClaudePluginResourceCounts {
  commands: number;
  agents: number;
  hooks: number;
  mcpServers: number;
  skills: number;
  outputStyles: number;
}

export interface ClaudePluginMarketplaceSummary {
  name: string;
  owner?: string | null;
  pluginCount: number;
  source?: string | null;
}

export interface ClaudePluginSummary {
  id: string;
  name: string;
  marketplace?: string | null;
  version?: string | null;
  description?: string | null;
  author?: string | null;
  category?: string | null;
  homepage?: string | null;
  enabled: boolean;
  installations: ClaudePluginInstallation[];
  errors: string[];
  resourceCounts: ClaudePluginResourceCounts;
}

export interface ClaudePluginsResponse {
  workspaceId: string;
  plugins: ClaudePluginSummary[];
  marketplaces: ClaudePluginMarketplaceSummary[];
  providerResourceGeneration?: number;
}

export interface ClaudePluginDetail extends ClaudePluginSummary {
  repository?: string | null;
  license?: string | null;
  readme?: string | null;
  dependencies: Array<{ name: string; version?: string | null; marketplace?: string | null }>;
  resources: Record<string, Array<Record<string, unknown>>>;
  manifest: Record<string, unknown>;
}

export interface ClaudePluginDetailResponse {
  workspaceId: string;
  plugin: ClaudePluginDetail;
  providerResourceGeneration?: number;
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
  scope: 'user' | 'project';
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
        .filter((action) => {
          if (action.type === 'http') return Boolean(action.url.trim());
          if (action.type === 'mcp_tool') return Boolean(action.server.trim() && action.tool.trim());
          if (action.type === 'prompt' || action.type === 'agent') return Boolean(action.prompt.trim());
          return Boolean(action.command.trim());
        })
        .map((action) => {
          const nextAction: AgentHookActionConfig = { ...action, timeout: typeof action.timeout === 'number' ? action.timeout : undefined } as AgentHookActionConfig;
          if (nextAction.type === 'command') nextAction.command = nextAction.command.trim();
          if (nextAction.type === 'http') nextAction.url = nextAction.url.trim();
          if (nextAction.type === 'mcp_tool') {
            nextAction.server = nextAction.server.trim();
            nextAction.tool = nextAction.tool.trim();
          }
          if (nextAction.type === 'prompt' || nextAction.type === 'agent') nextAction.prompt = nextAction.prompt.trim();
          if (action.name?.trim()) {
            nextAction.name = action.name.trim();
          } else {
            delete nextAction.name;
          }
          if (action.description?.trim()) {
            nextAction.description = action.description.trim();
          } else {
            delete nextAction.description;
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
    .map(([eventName, rules]) => {
      return {
        id: `${document.scope}:${eventName}`,
        scope: document.scope,
        eventName,
        matchers: rules.map((rule) => ({
          matcher: rule.matcher,
          hooks: rule.hooks.map((action) => ({
            ...action,
            timeout: typeof action.timeout === 'number' ? action.timeout : undefined,
          })),
        })),
        pluginName: rules.find((rule) => rule.pluginName)?.pluginName ?? undefined,
        marketplaceName: rules.find((rule) => rule.marketplaceName)?.marketplaceName ?? undefined,
      };
    })
    .sort((a, b) => a.eventName.localeCompare(b.eventName));

const mapMcpServer = (
  scope: AgentMcpScope,
  name: string,
  config: McpServerConfigResponse,
  revision?: string,
): AgentMcpServer => {
  const pluginIdentity = scope === 'plugin' && config.pluginId && config.serverId
    ? `${config.pluginId}:${config.serverId}`
    : null;
  return {
    id: `${scope}:${pluginIdentity ?? name}`,
    name: scope === 'plugin' && config.serverId ? config.serverId : name,
    scope,
    transport: config.type,
    command: config.command ?? undefined,
    args: config.args ?? undefined,
    url: config.url ?? undefined,
    env: config.env ?? undefined,
    headers: config.headers ?? undefined,
    enabled: config.enabled ?? true,
    revision,
    pluginName: config.pluginName,
    marketplaceName: config.marketplaceName,
    serverId: config.serverId,
    pluginId: config.pluginId,
    relativeSourcePath: config.relativeSourcePath,
    generation: config.generation,
    readOnly: config.readOnly,
    editable: config.editable,
    effective: config.effective,
    policy: config.policy,
    policyRevision: config.policyRevision,
  };
};

const normalizeMcpServers = (payload: McpServerCollectionResponse): AgentMcpServer[] =>
  payload.scopes.flatMap(({ scope, revision, mcpServers }) =>
    Object.entries(mcpServers ?? {}).map(([name, config]) => mapMcpServer(scope, name, config, revision)),
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

const loadMcpScopeRevision = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  apiPrefix: string,
  scope: AgentMcpScope,
): Promise<string> => {
  const response = await apiRequest<McpScopeResponse>(
    runtimeBaseUrl,
    `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${scope}`,
  );
  return response.revision ?? '';
};

const loadOutputStyleScopeRevision = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  apiPrefix: string,
  scope: CliOutputStyleScope,
): Promise<string> => {
  const response = await apiRequest<CliOutputStyleScopeResponse>(
    runtimeBaseUrl,
    `workspaces/${workspaceId}/${apiPrefix}/output-styles/${scope}`,
  );
  return response.revision ?? '';
};

const loadOutputStyleDocumentRevision = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  apiPrefix: string,
  scope: CliOutputStyleScope,
  fileName: string,
): Promise<string> => {
  const response = await apiRequest<CliOutputStyleDocumentResponse>(
    runtimeBaseUrl,
    `workspaces/${workspaceId}/${apiPrefix}/output-styles/${scope}/${encodePathLocator(fileName)}`,
  );
  return response.revision ?? '';
};

const loadSubagentScopeRevision = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  apiPrefix: string,
  scope: CliSubagentScope,
): Promise<string> => {
  const response = await apiRequest<CliSubagentScopeResponse>(
    runtimeBaseUrl,
    `workspaces/${workspaceId}/${apiPrefix}/subagents/${scope}`,
  );
  return response.revision ?? '';
};

const loadSlashCommandScopeRevision = async (
  runtimeBaseUrl: string,
  workspaceId: string,
  apiPrefix: string,
  scope: CliSlashCommandScope,
): Promise<string> => {
  const response = await apiRequest<CliSlashCommandScopeResponse>(
    runtimeBaseUrl,
    `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${scope}`,
  );
  return response.revision ?? '';
};

// ============ API factory ============

export const createAgentSettingsApi = (apiPrefix: string, agentsMdEndpoint: string = 'agents-md') => ({
  async refreshCache(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: {
      provider: 'claude-code' | 'codex';
      capability?: string;
      scope?: string;
    },
    signal?: AbortSignal,
  ): Promise<{ refreshed: true }> {
    return apiRequest<{ refreshed: true }>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/agent-settings/cache/refresh`,
      { method: 'POST', body: payload, signal },
    );
  },
  async getCodexAgentsMd(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: string,
  ): Promise<CodexAgentsMdResponse> {
    return apiRequest<CodexAgentsMdResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/agents-md?scope=${encodeURIComponent(scope)}`,
    );
  },

  async updateCodexAgentsMd(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: { scope: string; content: string; revision?: string },
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
    scope: 'user' | 'project',
  ): Promise<CodexRulesListResponse> {
    return apiRequest<CodexRulesListResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules?scope=${scope}`,
    );
  },

  async getCodexRulesFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: 'user' | 'project',
    path: string,
  ): Promise<CodexTextFileResponse> {
    return apiRequest<CodexTextFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules/file?scope=${scope}&path=${encodeURIComponent(path)}`,
    );
  },

  async updateCodexRulesFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: 'user' | 'project',
    path: string,
    content: string,
  ): Promise<CodexTextFileResponse> {
    return apiRequest<CodexTextFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules/file?scope=${scope}&path=${encodeURIComponent(path)}`,
      { method: 'PUT', body: { path, content } },
    );
  },

  async deleteCodexRulesFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: 'user' | 'project',
    path: string,
  ): Promise<void> {
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/rules/file?scope=${scope}&path=${encodeURIComponent(path)}`,
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
      `workspaces/${workspaceId}/codex/hooks/${layer}`,
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
    revision?: string,
  ): Promise<CodexHooksDocumentResponse> {
    const payloadRevision = revision
      ?? (await apiRequest<CodexHooksDocumentResponse>(
        runtimeBaseUrl,
        `workspaces/${workspaceId}/codex/hooks/${layer}`,
      )).revision
      ?? '';
    return apiRequest<CodexHooksDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks/${layer}`,
      { method: 'PUT', body: { content, revision: payloadRevision } },
    );
  },

  async upsertCodexHookEntry(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    entry: CodexHookEntry,
    revision?: string,
    previous?: CodexHookEntry | null,
  ): Promise<CodexHooksDocumentResponse> {
    const payloadRevision = revision
      ?? (await apiRequest<CodexHooksDocumentResponse>(
        runtimeBaseUrl,
        `workspaces/${workspaceId}/codex/hooks/${layer}`,
      )).revision
      ?? '';
    return apiRequest<CodexHooksDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks/${layer}/entry`,
      { method: 'PUT', body: { entry, previous: previous ?? null, revision: payloadRevision } },
    );
  },

  async deleteCodexHookEntry(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
    entry: CodexHookEntry,
    revision?: string,
  ): Promise<CodexHooksDocumentResponse> {
    const payloadRevision = revision
      ?? (await apiRequest<CodexHooksDocumentResponse>(
        runtimeBaseUrl,
        `workspaces/${workspaceId}/codex/hooks/${layer}`,
      )).revision
      ?? '';
    return apiRequest<CodexHooksDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks/${layer}/entry`,
      { method: 'DELETE', body: { entry, revision: payloadRevision } },
    );
  },

  async enableCodexHooks(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
  ): Promise<{ workspaceId: string; featureEnabled: boolean }> {
    return apiRequest<{ workspaceId: string; featureEnabled: boolean }>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks/${layer}/enable`,
      { method: 'POST' },
    );
  },

  async disableCodexHooks(
    runtimeBaseUrl: string,
    workspaceId: string,
    layer: 'user' | 'project',
  ): Promise<{ workspaceId: string; featureEnabled: boolean }> {
    return apiRequest<{ workspaceId: string; featureEnabled: boolean }>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/hooks/${layer}/disable`,
      { method: 'POST' },
    );
  },

  async listCodexPlugins(runtimeBaseUrl: string, workspaceId: string): Promise<CodexPluginsResponse> {
    return apiRequest<CodexPluginsResponse>(runtimeBaseUrl, `workspaces/${workspaceId}/codex/plugins`);
  },

  async getCodexPlugin(runtimeBaseUrl: string, workspaceId: string, pluginId: string): Promise<CodexPluginDetailResponse> {
    return apiRequest<CodexPluginDetailResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/plugins/${encodeURIComponent(pluginId)}`,
    );
  },

  async setCodexPluginEnabled(
    runtimeBaseUrl: string,
    workspaceId: string,
    pluginId: string,
    scope: 'user' | 'project',
    enabled: boolean,
  ): Promise<{ workspaceId: string; scope: 'user' | 'project'; pluginId: string; enabled: boolean; newThreadRequired: boolean }> {
    return apiRequest<{ workspaceId: string; scope: 'user' | 'project'; pluginId: string; enabled: boolean; newThreadRequired: boolean }>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/plugins/${encodeURIComponent(pluginId)}`,
      { method: 'PATCH', body: { scope, enabled } },
    );
  },

  async updateCodexPluginMcpPolicy(
    runtimeBaseUrl: string,
    workspaceId: string,
    pluginId: string,
    serverId: string,
    policy: CodexPluginMcpPolicy,
    revision: string,
  ): Promise<CodexPluginMcpPolicyUpdateResponse> {
    return apiRequest<CodexPluginMcpPolicyUpdateResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/plugins/${encodePathLocator(pluginId)}/mcp-servers/${encodePathLocator(serverId)}/policy`,
      {
        method: 'PATCH',
        body: {
          scope: 'user',
          policy,
          revision,
        },
      },
    );
  },

  async updateCodexPluginHookTrust(
    runtimeBaseUrl: string,
    workspaceId: string,
    pluginId: string,
    trusted: boolean,
    revision: string,
  ): Promise<CodexPluginHookTrustUpdateResponse> {
    return apiRequest<CodexPluginHookTrustUpdateResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/plugins/${encodePathLocator(pluginId)}/hook-trust`,
      {
        method: 'PATCH',
        body: {
          scope: 'user',
          trusted,
          revision,
        },
      },
    );
  },

  async listClaudePlugins(runtimeBaseUrl: string, workspaceId: string): Promise<ClaudePluginsResponse> {
    return apiRequest<ClaudePluginsResponse>(runtimeBaseUrl, `workspaces/${workspaceId}/claude-code/plugins`);
  },

  async getClaudePlugin(runtimeBaseUrl: string, workspaceId: string, pluginId: string): Promise<ClaudePluginDetailResponse> {
    return apiRequest<ClaudePluginDetailResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/plugins/${encodeURIComponent(pluginId)}`,
    );
  },

  async setClaudePluginEnabled(
    runtimeBaseUrl: string,
    workspaceId: string,
    pluginId: string,
    scope: ClaudePluginScope,
    enabled: boolean,
  ): Promise<{ workspaceId: string; pluginId: string; scope: ClaudePluginScope; enabled: boolean }> {
    return apiRequest<{ workspaceId: string; pluginId: string; scope: ClaudePluginScope; enabled: boolean }>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/claude-code/plugins/${encodeURIComponent(pluginId)}`,
      { method: 'PATCH', body: { scope, enabled } },
    );
  },

  async listCodexFiles(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    scope: 'user' | 'project' | 'plugin' | 'all',
  ): Promise<CodexFileListResponse> {
    return apiRequest<CodexFileListResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/files?scope=${scope}`,
    );
  },

  async getCodexFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    scope: 'user' | 'project' | 'plugin',
    path: string,
    pluginId?: string,
  ): Promise<CodexTextFileResponse> {
    const query = new URLSearchParams({ scope, path });
    if (pluginId) {
      query.set('pluginId', pluginId);
    }
    return apiRequest<CodexTextFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/file?${query.toString()}`,
    );
  },

  async getCodexFileBlob(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    scope: 'user' | 'project' | 'plugin',
    path: string,
    pluginId?: string,
  ): Promise<Blob> {
    const query = new URLSearchParams({ scope, path, raw: 'true' });
    if (pluginId) {
      query.set('pluginId', pluginId);
    }
    return apiBlobRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/file?${query.toString()}`,
    );
  },

  async updateCodexFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    scope: 'user' | 'project',
    path: string,
    content: string,
  ): Promise<CodexTextFileResponse> {
    let body: { path: string; content: string; revision?: string } = { path, content };
    if (resource === 'skills') {
      const query = new URLSearchParams({ scope, path });
      const current = await apiRequest<CodexTextFileResponse>(
        runtimeBaseUrl,
        `workspaces/${workspaceId}/codex/${resource}/file?${query.toString()}`,
      );
      if (!current.revision) {
        throw new Error('Codex Skills file revision is required before updating');
      }
      body = { ...body, revision: current.revision };
    }
    return apiRequest<CodexTextFileResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/file?scope=${scope}`,
      { method: 'PUT', body },
    );
  },

  async deleteCodexFile(
    runtimeBaseUrl: string,
    workspaceId: string,
    resource: string,
    scope: 'user' | 'project',
    path: string,
  ): Promise<void> {
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/${resource}/file?scope=${scope}&path=${encodeURIComponent(path)}`,
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
      scope: 'user' | 'project';
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
    scope: 'user' | 'project',
    path: string,
  ): Promise<void> {
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/codex/subagents?scope=${scope}&path=${encodeURIComponent(path)}`,
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
    payload: { scope: string; content: string; revision?: string; message?: string },
  ): Promise<AgentsMdUpdateResponse> {
    return apiRequest<AgentsMdUpdateResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/${agentsMdEndpoint}`,
      { method: 'PUT', body: payload },
    );
  },

  // ============ MCP Servers ============

  async listMcpServers(
    runtimeBaseUrl: string,
    workspaceId: string,
    signal?: AbortSignal,
  ): Promise<AgentMcpServer[]> {
    const response = await apiRequest<McpServerCollectionResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers`,
      signal ? { signal } : undefined,
    );
    return normalizeMcpServers(response);
  },

  async createMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: AgentMcpServer,
  ): Promise<AgentMcpServer> {
    const revision = server.revision
      ?? await loadMcpScopeRevision(runtimeBaseUrl, workspaceId, apiPrefix, server.scope);
    const payload = {
      revision,
      mcpServers: buildMcpServerPayload(server),
    };
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${server.scope}`,
      { method: 'POST', body: payload },
    );
    const config = response.mcpServers?.[server.name];
    if (!config) throw new Error(`Unable to create MCP server: ${server.name}`);
    return mapMcpServer(response.scope, server.name, config, response.revision);
  },

  async updateMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: AgentMcpServer,
  ): Promise<AgentMcpServer> {
    const revision = server.revision
      ?? await loadMcpScopeRevision(runtimeBaseUrl, workspaceId, apiPrefix, server.scope);
    const payload = {
      revision,
      mcpServers: buildMcpServerPayload(server),
    };
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${server.scope}/${server.name}`,
      { method: 'PUT', body: payload },
    );
    const config = response.mcpServers?.[server.name];
    if (!config) throw new Error(`Unable to update MCP server: ${server.name}`);
    return mapMcpServer(response.scope, server.name, config, response.revision);
  },

  async deleteMcpServer(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: Pick<AgentMcpServer, 'name' | 'scope' | 'revision'>,
  ): Promise<void> {
    const revision = server.revision
      ?? await loadMcpScopeRevision(runtimeBaseUrl, workspaceId, apiPrefix, server.scope);
    const query = new URLSearchParams({ revision });
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${server.scope}/${server.name}?${query.toString()}`,
      { method: 'DELETE' },
    );
  },

  async toggleMcpServerStatus(
    runtimeBaseUrl: string,
    workspaceId: string,
    server: Pick<AgentMcpServer, 'name' | 'scope' | 'revision'>,
    enabled: boolean,
  ): Promise<AgentMcpServer> {
    const revision = server.revision
      ?? await loadMcpScopeRevision(runtimeBaseUrl, workspaceId, apiPrefix, server.scope);
    const query = new URLSearchParams({
      enabled: String(enabled),
      revision,
    });
    const response = await apiRequest<McpScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/mcp-servers/${server.scope}/${server.name}/toggle?${query.toString()}`,
      { method: 'PATCH' },
    );
    const config = response.mcpServers[server.name];
    if (!config) throw new Error(`Unable to toggle MCP server status: ${server.name}`);
    return mapMcpServer(response.scope, server.name, config, response.revision);
  },

  async importMcpServers(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: { scope: AgentMcpScope; file: File; overwrite?: boolean; revision?: string },
  ): Promise<McpImportResponse> {
    const revision = payload.revision
      ?? await loadMcpScopeRevision(runtimeBaseUrl, workspaceId, apiPrefix, payload.scope);
    const formData = new FormData();
    formData.append('scope', payload.scope);
    formData.append('overwrite', payload.overwrite ? 'true' : 'false');
    formData.append('revision', revision);
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
        revision: document.revision,
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
      revision: response.revision,
    };
  },

  async updateHookScope(
    runtimeBaseUrl: string,
    workspaceId: string,
    scope: AgentHookScope,
    hooks: AgentHookRuleMap,
    revision?: string,
  ): Promise<AgentHookScopeResponse> {
    const payloadRevision = revision
      ?? (await apiRequest<AgentHookScopeResponse>(
        runtimeBaseUrl,
        `workspaces/${workspaceId}/${apiPrefix}/hooks/${scope}`,
      )).revision
      ?? '';
    const response = await apiRequest<AgentHookScopeResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/hooks/${scope}`,
      { method: 'PUT', body: { hooks, revision: payloadRevision } },
    );
    return {
      ...response,
      hooks: cloneHookRuleMap(response.hooks),
      revision: response.revision,
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
    payload: AgentHookImportPayload,
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

  async getSkillBlob(
    runtimeBaseUrl: string,
    workspaceId: string,
    filePath: string,
    scope: 'project' | 'user' | 'plugin' = 'project',
  ): Promise<Blob> {
    const query = new URLSearchParams({ path: filePath, scope, raw: 'true' });
    return apiBlobRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/skills/content?${query.toString()}`,
    );
  },

  async createSkill(
    runtimeBaseUrl: string,
    workspaceId: string,
    payload: AgentFileCreatePayload,
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
    payload: AgentFileUpdatePayload,
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

  // ============ Slash Commands ============

  async listSlashCommands(
    runtimeBaseUrl: string,
    workspaceId: string,
  ): Promise<ResourceListResult> {
    const scopesRes = await apiRequest<CliSlashCommandScopesResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands`,
    );

    const documents = scopesRes.items.map((summary) =>
      mapCliSlashCommandDocument(
        summary.scope,
        { ...summary, content: '' },
      ));
    return {
      items: documents.sort((a, b) => a.title.localeCompare(b.title)),
      availableScopes: scopesRes.availableScopes,
    };
  },

  async loadSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const query = new URLSearchParams({ path });
    const response = await apiRequest<CliSlashCommandDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${document.scope}/content?${query.toString()}`,
    );
    return mapCliSlashCommandDocument(
      response.scope,
      response.document,
      response.revision,
    );
  },

  async createSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliSlashCommandScope;
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const revision = (document.metadata?.revision as string | undefined)
      ?? await loadSlashCommandScopeRevision(runtimeBaseUrl, workspaceId, apiPrefix, scope);
    const payload = {
      path,
      content: document.content,
      revision,
    };
    const response = await apiRequest<CliSlashCommandDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${scope}`,
      { method: 'POST', body: payload },
    );
    return mapCliSlashCommandDocument(response.scope, response.document, response.revision);
  },

  async updateSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliSlashCommandScope;
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const payload = {
      path,
      content: document.content,
      revision: (document.metadata?.revision as string | undefined) ?? '',
    };
    const response = await apiRequest<CliSlashCommandDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${scope}/content`,
      { method: 'PUT', body: payload },
    );
    return mapCliSlashCommandDocument(response.scope, response.document, response.revision);
  },

  async deleteSlashCommand(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: Pick<AgentDocument, 'scope' | 'metadata' | 'title'>,
  ): Promise<void> {
    const scope = document.scope as CliSlashCommandScope;
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const query = new URLSearchParams({ path });
    const revision = document.metadata?.revision as string | undefined;
    if (revision) {
      query.set('revision', revision);
    }
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/slash-commands/${scope}/content?${query.toString()}`,
      { method: 'DELETE' },
    );
  },

  // ============ Output Styles ============

  async listOutputStyles(
    runtimeBaseUrl: string,
    workspaceId: string,
    filter?: { scope?: CliOutputStyleScope; pluginId?: string | null },
  ): Promise<ResourceListResult> {
    const listQuery = new URLSearchParams();
    if (filter?.scope) {
      listQuery.set('scope', filter.scope);
    }
    if (filter?.pluginId) {
      listQuery.set('pluginId', filter.pluginId);
    }
    const scopesRes = await apiRequest<CliOutputStyleScopesResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/output-styles${listQuery.size ? `?${listQuery.toString()}` : ''}`,
    );

    const documents = scopesRes.scopes.flatMap((group) =>
      group.documents.map((summary) => mapCliOutputStyleDocument(
        group.scope,
        { ...summary, content: '' },
        group.revision,
      )));
    return {
      items: documents.sort((a, b) => a.title.localeCompare(b.title)),
      availableScopes: scopesRes.scopes.map((group) => ({
        scope: group.scope,
        readOnly: group.scope === 'plugin',
      })),
      providerResourceGeneration: scopesRes.providerResourceGeneration,
    };
  },

  async loadOutputStyle(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const fileName = (document.metadata?.fileName as string) ?? document.title;
    const query = new URLSearchParams();
    const pluginId = document.metadata?.pluginId;
    if (document.scope === 'plugin' && typeof pluginId === 'string') {
      query.set('pluginId', pluginId);
    }
    const response = await apiRequest<CliOutputStyleDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/output-styles/${document.scope}/${encodePathLocator(fileName)}${query.size ? `?${query.toString()}` : ''}`,
    );
    return mapCliOutputStyleDocument(
      response.scope,
      response.document,
      response.revision,
    );
  },

  async createOutputStyle(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliOutputStyleScope;
    const fileName = (document.metadata?.fileName as string) ?? document.title;
    const revision = (document.metadata?.revision as string | undefined)
      ?? await loadOutputStyleScopeRevision(runtimeBaseUrl, workspaceId, apiPrefix, scope);
    const payload = {
      fileName,
      content: document.content,
      name: document.title,
      description: document.description,
      revision,
    };
    const response = await apiRequest<CliOutputStyleDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/output-styles/${scope}`,
      { method: 'POST', body: payload },
    );
    return mapCliOutputStyleDocument(response.scope, response.document, response.revision);
  },

  async updateOutputStyle(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliOutputStyleScope;
    const fileName = (document.metadata?.fileName as string) ?? document.title;
    const revision = (document.metadata?.revision as string | undefined)
      ?? await loadOutputStyleDocumentRevision(runtimeBaseUrl, workspaceId, apiPrefix, scope, fileName);
    const payload = {
      content: document.content,
      name: document.title,
      description: document.description,
      revision,
    };
    const response = await apiRequest<CliOutputStyleDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/output-styles/${scope}/${encodePathLocator(fileName)}`,
      { method: 'PUT', body: payload },
    );
    return mapCliOutputStyleDocument(response.scope, response.document, response.revision);
  },

  async deleteOutputStyle(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: Pick<AgentDocument, 'scope' | 'metadata' | 'title'>,
  ): Promise<void> {
    const scope = document.scope as CliOutputStyleScope;
    const fileName = (document.metadata?.fileName as string) ?? document.title;
    const revision = (document.metadata?.revision as string | undefined)
      ?? await loadOutputStyleDocumentRevision(runtimeBaseUrl, workspaceId, apiPrefix, scope, fileName);
    const query = new URLSearchParams({ revision });
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/output-styles/${scope}/${encodePathLocator(fileName)}?${query.toString()}`,
      { method: 'DELETE' },
    );
  },

  // ============ Memory ============

  async listMemoryDocuments(
    runtimeBaseUrl: string,
    workspaceId: string,
  ): Promise<ResourceListResult> {
    const collection = await apiRequest<CliMemoryCollectionResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/memory`,
    );

    const documents = collection.items.map((summary) =>
      mapCliMemoryDocument(
        { ...summary, content: '' },
        collection.revision,
      ));

    return {
      items: documents.sort((a, b) => a.title.localeCompare(b.title)),
      availableScopes: collection.availableScopes ?? [],
    };
  },

  async loadMemoryDocument(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const query = new URLSearchParams({ path });
    const response = await apiRequest<CliMemoryDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/memory/${document.scope}/content?${query.toString()}`,
    );
    const parsed =
      parseResourceResult<CliMemorySummary & { content: string }>(response);
    if (!parsed.resource) {
      throw new Error('Memory document response missing resource');
    }
    return mapCliMemoryDocument(parsed.resource, parsed.revision);
  },

  async updateMemoryDocument(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const revision = (document.metadata?.revision as string | undefined) ?? '';
    const response = await apiRequest<CliMemoryDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/memory/${document.scope}/content`,
      {
        method: 'PUT',
        body: { path, content: document.content, revision },
      },
    );
    const parsed = parseResourceResult<CliMemorySummary & { content: string }>(response);
    if (!parsed.resource) {
      throw new Error('Memory document response missing resource');
    }
    return mapCliMemoryDocument(parsed.resource, parsed.revision);
  },

  async deleteMemoryDocument(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: Pick<AgentDocument, 'metadata' | 'title'>,
  ): Promise<void> {
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const revision = (document.metadata?.revision as string | undefined) ?? '';
    const query = new URLSearchParams({ path, revision });
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/memory/${document.metadata?.source ?? 'user'}/content?${query.toString()}`,
      { method: 'DELETE' },
    );
  },

  // ============ Subagents ============

  async listSubagents(
    runtimeBaseUrl: string,
    workspaceId: string,
  ): Promise<ResourceListResult> {
    const scopesRes = await apiRequest<CliSubagentScopesResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents`,
    );

    const documents = scopesRes.items.map((summary) =>
      mapCliSubagentDocument(
        summary.scope,
        { ...summary, content: '' },
      ));
    return {
      items: documents.sort((a, b) => a.title.localeCompare(b.title)),
      availableScopes: scopesRes.availableScopes,
    };
  },

  async loadSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const query = new URLSearchParams({ path });
    const response = await apiRequest<CliSubagentDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents/${document.scope}/content?${query.toString()}`,
    );
    return mapCliSubagentDocument(
      response.scope,
      response.document,
      response.revision,
    );
  },

  async createSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliSubagentScope;
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const revision = (document.metadata?.revision as string | undefined)
      ?? await loadSubagentScopeRevision(runtimeBaseUrl, workspaceId, apiPrefix, scope);
    const payload = {
      path,
      content: document.content,
      revision,
    };
    const response = await apiRequest<CliSubagentDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents/${scope}`,
      { method: 'POST', body: payload },
    );
    return mapCliSubagentDocument(response.scope, response.document, response.revision);
  },

  async updateSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: AgentDocument,
    _previousFileName?: string,
  ): Promise<AgentDocument> {
    const scope = document.scope as CliSubagentScope;
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const response = await apiRequest<CliSubagentDocumentResponse>(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents/${scope}/content`,
      {
        method: 'PUT',
        body: {
          path,
          content: document.content,
          revision: (document.metadata?.revision as string | undefined) ?? '',
        },
      },
    );
    return mapCliSubagentDocument(response.scope, response.document, response.revision);
  },

  async deleteSubagent(
    runtimeBaseUrl: string,
    workspaceId: string,
    document: Pick<AgentDocument, 'scope' | 'metadata' | 'title'>,
  ): Promise<void> {
    const scope = document.scope as CliSubagentScope;
    const path = (document.metadata?.relativePath as string)
      ?? (document.metadata?.fileName as string)
      ?? document.title;
    const query = new URLSearchParams({ path });
    const revision = document.metadata?.revision as string | undefined;
    if (revision) {
      query.set('revision', revision);
    }
    await apiRequest(
      runtimeBaseUrl,
      `workspaces/${workspaceId}/${apiPrefix}/subagents/${scope}/content?${query.toString()}`,
      { method: 'DELETE' },
    );
  },
});
