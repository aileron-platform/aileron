import type { LucideIcon } from 'lucide-react';
import type { AgentDocumentFormat, AgentFileCollection, AgentScope } from './documents';
import type { AgentHookScope, HookEventOption } from './agentHookTypes';

export type AgentSettingsToolId = 'claude' | 'opencode' | 'codex';

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
  scopes: Extract<AgentScope, 'project' | 'user' | 'plugin'>[];
  format: AgentDocumentFormat;
  supportsNamespace: boolean;
}

export interface AgentDefinitionCapability extends AgentCapabilityBase {
  endpoint: 'agents' | 'subagents';
  displayLabelKey: string;
  scopes: AgentScope[];
  format: AgentDocumentFormat;
}

export interface AgentPluginResourceCapability extends AgentCapabilityBase {
  scopes: Extract<AgentScope, 'project' | 'user' | 'plugin'>[];
  readOnlyScopes?: AgentScope[];
}

export interface AgentToolCapabilities {
  instructions?: AgentInstructionCapability;
  mcp?: AgentMcpCapability;
  hooks?: AgentHooksCapability;
  skills?: AgentFileCollectionCapability;
  slashCommands?: AgentCommandCapability;
  agentDefinitions?: AgentDefinitionCapability;
  outputStyles?: AgentPluginResourceCapability;
  memory?: AgentCapabilityBase;
  prompts?: AgentCapabilityBase;
  rules?: AgentCapabilityBase;
  plugins?: AgentCapabilityBase;
  settings?: AgentCapabilityBase;
}

export interface AgentToolConfig {
  id: AgentSettingsToolId;
  navigationId: string;
  navigationLabelKey: string;
  navigationIcon: LucideIcon;
  agentsMd: AgentToolMd;
  availableSubViews: string[];
  apiPathPrefix: 'claude-code' | 'opencode' | 'codex';
  availableScopes: AgentScope[];
  supportsToggle?: boolean;
  slashCommandFormat?: Extract<AgentDocumentFormat, 'markdown' | 'toml'>;
  i18nNamespace: string;
  globalSettingsLabelKey: string;
  hookEvents?: HookEventOption[];
  capabilities: AgentToolCapabilities;
}
