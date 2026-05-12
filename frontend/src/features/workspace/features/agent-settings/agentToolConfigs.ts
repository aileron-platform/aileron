import { Bot, Building, Globe, Sparkles, User } from 'lucide-react';
import { HOOK_EVENTS } from '@/shared/hooks/providerHookSpec';
import type {
  AgentToolType,
  AgentToolConfig,
  AgentToolCapabilities,
  AgentToolScopeOption,
  HookEventOption,
} from './types';

const projectUserScopes: AgentToolScopeOption[] = [
  { value: 'project', labelKey: 'workspace.agentSettings.common.scope.project', icon: Building },
  { value: 'user', labelKey: 'workspace.agentSettings.common.scope.user', icon: User },
];

const buildNamedHookEvents = (providerKey: 'claude' | 'gemini', events: readonly string[]): HookEventOption[] => (
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
const geminiHookEvents: HookEventOption[] = buildNamedHookEvents('gemini', HOOK_EVENTS.gemini);
const codexHookEvents: HookEventOption[] = buildCodexHookEvents(HOOK_EVENTS.codex);

const buildAvailableSubViews = (instructionSubView: string, capabilities: AgentToolCapabilities, extra: string[] = []) => [
  instructionSubView,
  ...(capabilities.mcp?.supported === false || !capabilities.mcp ? [] : ['mcp']),
  ...(capabilities.skills?.supported === false || !capabilities.skills ? [] : ['skills']),
  ...(capabilities.slashCommands?.supported === false || !capabilities.slashCommands ? [] : ['slash-commands']),
  ...(capabilities.agentDefinitions?.supported === false || !capabilities.agentDefinitions ? [] : ['subagents']),
  ...(capabilities.hooks?.supported === false || !capabilities.hooks ? [] : ['hooks']),
  ...(capabilities.plugins?.supported === false || !capabilities.plugins ? [] : ['plugins']),
  ...extra,
];

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
  plugins: { supported: true },
  scripts: { supported: false, collection: 'scripts', scopes: [], supportsPlugin: false },
};

const geminiCapabilities: AgentToolCapabilities = {
  instructions: {
    supported: true,
    fileName: 'GEMINI.md',
    subViewId: 'gemini-md',
    labelKey: 'workspace.agentSettings.gemini.agentsMd',
    scopes: projectUserScopes,
    endpoint: 'agents-md',
  },
  mcp: { supported: true, scopes: ['project', 'user', 'extension'], supportsToggle: false },
  hooks: { supported: true, scopes: ['project', 'user', 'extension'], events: geminiHookEvents },
  slashCommands: { supported: true, scopes: ['project', 'user', 'extension'], format: 'toml', supportsNamespace: true },
  skills: { supported: true, collection: 'skills', scopes: ['project', 'user', 'extension'], supportsPlugin: true, readOnlyScopes: ['extension'] },
  scripts: { supported: false, collection: 'scripts', scopes: [], supportsPlugin: false },
  agentDefinitions: {
    supported: true,
    endpoint: 'subagents',
    displayLabelKey: 'workspace.agentSettings.common.subViews.subagents',
    scopes: ['project', 'user'],
    format: 'markdown',
  },
  memory: { supported: false },
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
  scripts: { supported: false, collection: 'scripts', scopes: [], supportsPlugin: false },
  agentDefinitions: { supported: false, endpoint: 'agents', displayLabelKey: 'workspace.agentSettings.common.subViews.agents', scopes: [], format: 'markdown' },
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
  slashCommands: { supported: true, scopes: ['project', 'user'], format: 'markdown', supportsNamespace: false },
  skills: { supported: true, collection: 'skills', scopes: ['project', 'user', 'plugin'], supportsPlugin: true, readOnlyScopes: ['plugin'] },
  scripts: { supported: false, collection: 'scripts', scopes: [], supportsPlugin: false },
  agentDefinitions: { supported: false, endpoint: 'agents', displayLabelKey: 'workspace.agentSettings.common.subViews.agents', scopes: [], format: 'markdown' },
};

const codexSettingsSubViews = [
  'agents-md',
  'mcp',
  'skills',
  'prompts',
  'subagents',
  'hooks',
  'rules',
  'plugins',
  'settings',
];

const claudeConfig: AgentToolConfig = {
  id: 'claude',
  navigationId: 'claude-code',
  navigationLabelKey: 'workspace.navigation.main.claudeCodeSettings',
  navigationIcon: Bot,
  agentsMd: claudeCapabilities.instructions!,
  availableSubViews: buildAvailableSubViews('claude-md', claudeCapabilities, ['memory', 'output-styles', 'settings']),
  apiPathPrefix: 'claude-code',
  availableScopes: ['project', 'user', 'local', 'plugin'],
  supportsToggle: true,
  slashCommandFormat: 'markdown',
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.claudeCode',
  hookEvents: claudeHookEvents,
  capabilities: claudeCapabilities,
};

const geminiConfig: AgentToolConfig = {
  id: 'gemini',
  navigationId: 'gemini',
  navigationLabelKey: 'workspace.navigation.main.geminiSettings',
  navigationIcon: Sparkles,
  agentsMd: geminiCapabilities.instructions!,
  availableSubViews: buildAvailableSubViews('gemini-md', geminiCapabilities, ['extensions', 'settings']),
  apiPathPrefix: 'gemini',
  availableScopes: ['project', 'user', 'extension'],
  supportsToggle: false,
  slashCommandFormat: 'toml',
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.gemini',
  hookEvents: geminiHookEvents,
  capabilities: geminiCapabilities,
};

const opencodeConfig: AgentToolConfig = {
  id: 'opencode',
  navigationId: 'opencode',
  navigationLabelKey: 'workspace.navigation.main.opencodeSettings',
  navigationIcon: Globe,
  agentsMd: opencodeCapabilities.instructions!,
  availableSubViews: buildAvailableSubViews('agents-md', opencodeCapabilities),
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
  availableSubViews: codexSettingsSubViews,
  apiPathPrefix: 'codex',
  availableScopes: ['project', 'user', 'plugin'],
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.codex',
  capabilities: codexCapabilities,
};

export const AGENT_TOOL_CONFIGS: Record<AgentToolType, AgentToolConfig> = {
  claude: claudeConfig,
  gemini: geminiConfig,
  opencode: opencodeConfig,
  codex: codexConfig,
};

export const AGENT_NAVIGATION_IDS = Object.values(AGENT_TOOL_CONFIGS).map((config) => config.navigationId);
