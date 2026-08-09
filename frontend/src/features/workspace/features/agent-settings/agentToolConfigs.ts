import { Bot, Building, Globe, User } from 'lucide-react';
import { HOOK_EVENTS } from '@/shared/components/hook-workflow';
import type {
  AgentSettingsToolId,
  AgentToolConfig,
  AgentToolCapabilities,
  AgentToolScopeOption,
} from './model/capabilities';
import type {
  HookEventOption,
} from './model/agentHookTypes';
import { buildAgentSettingsSubViews } from './agentToolConfigModel';

const projectUserScopes: AgentToolScopeOption[] = [
  { value: 'project', labelKey: 'workspace.agentSettings.common.scope.project', icon: Building },
  { value: 'user', labelKey: 'workspace.agentSettings.common.scope.user', icon: User },
];

const buildNamedHookEvents = (providerKey: 'claude', events: readonly string[]): HookEventOption[] => (
  events.map(value => ({
    value,
    labelKey: `workspace.agentSettings.${providerKey}.hooks.events.${value}.name`,
    optionKey: `workspace.agentSettings.${providerKey}.hooks.events.${value}.option`,
  }))
);

const buildCodexHookEvents = (events: readonly string[]): HookEventOption[] => (
  events.map(value => ({
    value,
    labelKey: `workspace.agentSettings.codex.hooks.events.${value}`,
    optionKey: `workspace.agentSettings.codex.hooks.events.${value}`,
  }))
);

const claudeHookEvents: HookEventOption[] = buildNamedHookEvents('claude', HOOK_EVENTS['claude-code']);
const codexHookEvents: HookEventOption[] = buildCodexHookEvents(HOOK_EVENTS.codex);

const claudeCapabilities: AgentToolCapabilities = {
  instructions: {
    supported: true,
    fileName: 'CLAUDE.md',
    subViewId: 'claude-md',
    labelKey: 'workspace.agentSettings.claude.agentsMd',
    scopes: projectUserScopes,
    endpoint: 'claude-md',
  },
  mcp: { supported: true, scopes: ['project', 'user', 'local', 'plugin'], supportsToggle: true },
  hooks: { supported: true, scopes: ['project', 'user', 'local', 'plugin'], events: claudeHookEvents },
  slashCommands: { supported: true, scopes: ['project', 'user', 'plugin'], format: 'markdown', supportsNamespace: true },
  agentDefinitions: {
    supported: true,
    endpoint: 'subagents',
    displayLabelKey: 'workspace.navigation.sub.claudeCodeSettings.subagents',
    scopes: ['project', 'user', 'plugin'],
    format: 'markdown',
  },
  skills: { supported: true, collection: 'skills', scopes: ['project', 'user', 'plugin'], supportsPlugin: true, readOnlyScopes: ['plugin'] },
  outputStyles: { supported: true, scopes: ['project', 'user', 'plugin'], readOnlyScopes: ['plugin'] },
  memory: { supported: true },
  plugins: { supported: true },
  settings: { supported: true },
};

const opencodeCapabilities: AgentToolCapabilities = {
  instructions: {
    supported: true,
    fileName: 'AGENTS.md',
    subViewId: 'agents-md',
    labelKey: 'workspace.agentSettings.opencode.agentsMd',
    scopes: [
      { value: 'project', labelKey: 'workspace.agentSettings.common.scope.project', icon: Building },
      { value: 'user', labelKey: 'workspace.agentSettings.common.scope.global', icon: User },
    ],
    endpoint: 'agents-md',
  },
  mcp: { supported: true, scopes: ['project', 'user'], supportsToggle: true },
  hooks: { supported: false, scopes: [], events: [] },
  slashCommands: { supported: true, scopes: ['project', 'user'], format: 'markdown', supportsNamespace: true },
  skills: { supported: true, collection: 'skills', scopes: ['project', 'user'], supportsPlugin: false },
  agentDefinitions: {
    supported: true,
    endpoint: 'subagents',
    displayLabelKey: 'workspace.agentSettings.common.subViews.subagents',
    scopes: ['project', 'user'],
    format: 'markdown',
  },
  outputStyles: { supported: false, scopes: [] },
  memory: { supported: false },
  prompts: { supported: false },
  rules: { supported: false },
  plugins: { supported: false },
  settings: { supported: false },
};

const codexCapabilities: AgentToolCapabilities = {
  instructions: {
    supported: true,
    fileName: 'AGENTS.md',
    subViewId: 'agents-md',
    labelKey: 'workspace.agentSettings.codex.agentsMd.title',
    scopes: projectUserScopes,
    endpoint: 'agents-md',
  },
  mcp: { supported: true, scopes: ['project', 'user', 'plugin'], supportsToggle: true },
  hooks: { supported: true, scopes: ['project', 'user', 'plugin'], events: codexHookEvents },
  slashCommands: { supported: false, scopes: ['project', 'user'], format: 'markdown', supportsNamespace: false },
  skills: { supported: true, collection: 'skills', scopes: ['project', 'user', 'plugin'], supportsPlugin: true, readOnlyScopes: ['plugin'] },
  agentDefinitions: {
    supported: true,
    endpoint: 'subagents',
    displayLabelKey: 'workspace.agentSettings.common.subViews.subagents',
    scopes: ['project', 'user'],
    format: 'toml',
  },
  outputStyles: { supported: false, scopes: [] },
  memory: { supported: false },
  prompts: { supported: true },
  rules: { supported: true },
  plugins: { supported: true },
  settings: { supported: true },
};

const claudeConfig: AgentToolConfig = {
  id: 'claude',
  navigationId: 'claude-code',
  navigationLabelKey: 'workspace.navigation.main.claudeCodeSettings',
  navigationIcon: Bot,
  agentsMd: claudeCapabilities.instructions!,
  availableSubViews: buildAgentSettingsSubViews('claude-md', claudeCapabilities),
  apiPathPrefix: 'claude-code',
  availableScopes: ['project', 'user', 'local', 'plugin'],
  supportsToggle: true,
  slashCommandFormat: 'markdown',
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.claudeCode',
  hookEvents: claudeHookEvents,
  capabilities: claudeCapabilities,
};

const opencodeConfig: AgentToolConfig = {
  id: 'opencode',
  navigationId: 'opencode',
  navigationLabelKey: 'workspace.navigation.main.opencodeSettings',
  navigationIcon: Globe,
  agentsMd: opencodeCapabilities.instructions!,
  availableSubViews: buildAgentSettingsSubViews('agents-md', opencodeCapabilities),
  apiPathPrefix: 'opencode',
  availableScopes: ['project', 'user'],
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.opencode',
  capabilities: opencodeCapabilities,
};

const codexConfig: AgentToolConfig = {
  id: 'codex',
  navigationId: 'codex',
  navigationLabelKey: 'workspace.navigation.main.codexSettings',
  navigationIcon: Bot,
  agentsMd: codexCapabilities.instructions!,
  availableSubViews: buildAgentSettingsSubViews('agents-md', codexCapabilities),
  apiPathPrefix: 'codex',
  availableScopes: ['project', 'user', 'plugin'],
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.codex',
  capabilities: codexCapabilities,
};

export const AGENT_TOOL_CONFIGS: Record<AgentSettingsToolId, AgentToolConfig> = {
  claude: claudeConfig,
  opencode: opencodeConfig,
  codex: codexConfig,
};

export const AGENT_NAVIGATION_IDS = Object.values(AGENT_TOOL_CONFIGS).map((config) => config.navigationId);
