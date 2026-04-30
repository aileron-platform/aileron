import type { LucideIcon } from 'lucide-react';

export type AgentToolType = 'claude' | 'gemini' | 'opencode' | 'codex';
export type AgentScope = 'project' | 'user' | 'local' | 'plugin';
export type AgentHookScope = AgentScope;
export type AgentMdScope = 'project' | 'user' | 'plugin';
export type AgentFileCollection = 'skills' | 'scripts';
export type AgentDocumentFormat = 'markdown' | 'toml' | 'yaml';
export type AgentMcpTransport = 'stdio' | 'sse' | 'http';

export interface AgentDocument {
  id: string;
  workspaceId?: string;
  scope: AgentScope;
  title: string;
  description?: string;
  content: string;
  size?: string;
  metadata?: Record<string, unknown>;
  pluginName?: string;
  marketplaceName?: string;
}

export interface AgentMcpServer {
  id: string;
  name: string;
  scope: AgentScope;
  transport: AgentMcpTransport;
  command?: string;
  args?: string[];
  url?: string;
  env?: Record<string, string>;
  headers?: Record<string, string>;
  enabled?: boolean;
  pluginName?: string;
  marketplaceName?: string;
}

export interface AgentHookActionConfig {
  type: 'command' | 'webhook' | 'mcp_call';
  command?: string | null;
  timeout?: number | null;
}

export interface AgentHookRuleConfig {
  matcher: string;
  hooks: AgentHookActionConfig[];
}

export type AgentHookRuleMap = Record<string, AgentHookRuleConfig[]>;

export interface AgentHookScopeDocument {
  scope: AgentHookScope;
  hooks: AgentHookRuleMap;
}

export interface AgentHookScopesResponse {
  workspaceId: string;
  scopes: AgentHookScopeDocument[];
}

export interface AgentHookScopeResponse {
  workspaceId: string;
  scope: AgentHookScope;
  hooks: AgentHookRuleMap;
}

export interface AgentHookDeleteResponse {
  workspaceId: string;
  scope: AgentHookScope;
  deleted: boolean;
  deletedAt: string;
}

export type AgentHookImportMode = 'merge' | 'replace';

export interface AgentHookImportRequest {
  mode: AgentHookImportMode;
  scopes: AgentHookScopeDocument[];
}

export interface AgentHookImportResponse {
  workspaceId: string;
  mode: AgentHookImportMode;
  imported: number;
  updated: number;
  skipped: number;
}

export interface AgentHookMatcher {
  matcher: string;
  hooks: AgentHookActionConfig[];
}

export interface AgentHookWithEvent {
  id: string;
  scope: AgentHookScope;
  eventName: string;
  matchers: AgentHookMatcher[];
  pluginName?: string;
  marketplaceName?: string;
}

export interface AgentHookExportResponse {
  workspaceId: string;
  exportedAt: string;
  scopes: AgentHookScopeDocument[];
}

export interface AgentFileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: AgentFileNode[];
  size?: number;
  modified?: string;
  content?: string;
  scope?: AgentScope;
}

export interface AgentFileCollectionResponse {
  workspaceId?: string;
  scope?: AgentScope;
  nodes?: AgentFileNode[];
  tree?: AgentFileNode[];
}

export interface AgentFileResponse {
  data?: {
    content?: string;
    path?: string;
    scope?: AgentScope;
  };
  content?: string;
  path?: string;
  scope?: AgentScope;
}

export interface AgentFileCreateRequest {
  path: string;
  content?: string;
  type?: 'file' | 'directory';
  scope?: AgentScope;
}

export interface AgentFileUpdateRequest {
  content: string;
}

export interface AgentFileDeleteResponse {
  deleted: boolean;
  path?: string;
}

export interface AgentPluginSkillSummary {
  pluginName: string;
  marketplaceName: string;
  skillName: string;
}

export interface AgentPluginSkillsResponse {
  plugins: AgentPluginSkillSummary[];
}

export interface AgentSelectedFile {
  path: string;
  scope: Extract<AgentScope, 'project' | 'user' | 'plugin'>;
}

export interface AgentToolScopeOption {
  value: string;
  labelKey: string;
  icon: LucideIcon;
}

export interface AgentToolMd {
  fileName: string;
  subViewId: string;
  labelKey: string;
  scopes: AgentToolScopeOption[];
  endpoint?: string;
  apiEndpoint?: string;
}

export interface HookEventOption {
  value: string;
  labelKey: string;
  optionKey: string;
}

export interface AgentCapabilityBase {
  supported?: boolean;
}

export interface AgentInstructionCapability extends AgentCapabilityBase {
  fileName: string;
  subViewId: string;
  labelKey: string;
  scopes: AgentToolScopeOption[];
  endpoint: string;
}

export interface AgentMcpCapability extends AgentCapabilityBase {
  scopes: AgentScope[];
  supportsToggle: boolean;
}

export interface AgentHooksCapability extends AgentCapabilityBase {
  scopes: AgentHookScope[];
  events: HookEventOption[];
}

export interface AgentFileCollectionCapability extends AgentCapabilityBase {
  collection: AgentFileCollection;
  scopes: Extract<AgentScope, 'project' | 'user' | 'plugin'>[];
  supportsPlugin: boolean;
  readOnlyScopes?: AgentScope[];
  extensions?: string[];
}

export interface AgentCommandCapability extends AgentCapabilityBase {
  scopes: Extract<AgentScope, 'project' | 'user'>[];
  format: AgentDocumentFormat;
  supportsNamespace: boolean;
}

export interface AgentDefinitionCapability extends AgentCapabilityBase {
  endpoint: 'agents' | 'subagents';
  displayLabelKey: string;
  scopes: AgentScope[];
  format: AgentDocumentFormat;
}

export interface AgentToolCapabilities {
  instructions?: AgentInstructionCapability;
  mcp?: AgentMcpCapability;
  hooks?: AgentHooksCapability;
  skills?: AgentFileCollectionCapability;
  scripts?: AgentFileCollectionCapability;
  slashCommands?: AgentCommandCapability;
  agentDefinitions?: AgentDefinitionCapability;
}

export interface AgentToolConfig {
  id: AgentToolType;
  navigationId: string;
  navigationLabelKey: string;
  navigationIcon: LucideIcon;
  agentsMd: AgentToolMd;
  availableSubViews: string[];
  apiPathPrefix: 'claude-code' | 'gemini' | 'opencode' | 'codex';
  availableScopes: AgentScope[];
  supportsToggle?: boolean;
  slashCommandFormat?: Extract<AgentDocumentFormat, 'markdown' | 'toml'>;
  i18nNamespace: string;
  globalSettingsLabelKey: string;
  hookEvents?: HookEventOption[];
  capabilities: AgentToolCapabilities;
}
