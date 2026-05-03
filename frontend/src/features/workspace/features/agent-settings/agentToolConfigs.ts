import { Bot, Building, Globe, Sparkles, User } from 'lucide-react';
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

const claudeHookEvents: HookEventOption[] = [
  { value: 'PreToolUse', labelKey: 'workspace.agentSettings.claude.hooks.events.PreToolUse.name', optionKey: 'workspace.agentSettings.claude.hooks.events.PreToolUse.option' },
  { value: 'PostToolUse', labelKey: 'workspace.agentSettings.claude.hooks.events.PostToolUse.name', optionKey: 'workspace.agentSettings.claude.hooks.events.PostToolUse.option' },
  { value: 'UserPromptSubmit', labelKey: 'workspace.agentSettings.claude.hooks.events.UserPromptSubmit.name', optionKey: 'workspace.agentSettings.claude.hooks.events.UserPromptSubmit.option' },
  { value: 'Notification', labelKey: 'workspace.agentSettings.claude.hooks.events.Notification.name', optionKey: 'workspace.agentSettings.claude.hooks.events.Notification.option' },
  { value: 'Stop', labelKey: 'workspace.agentSettings.claude.hooks.events.Stop.name', optionKey: 'workspace.agentSettings.claude.hooks.events.Stop.option' },
  { value: 'SubagentStop', labelKey: 'workspace.agentSettings.claude.hooks.events.SubagentStop.name', optionKey: 'workspace.agentSettings.claude.hooks.events.SubagentStop.option' },
  { value: 'PreCompact', labelKey: 'workspace.agentSettings.claude.hooks.events.PreCompact.name', optionKey: 'workspace.agentSettings.claude.hooks.events.PreCompact.option' },
  { value: 'SessionStart', labelKey: 'workspace.agentSettings.claude.hooks.events.SessionStart.name', optionKey: 'workspace.agentSettings.claude.hooks.events.SessionStart.option' },
  { value: 'SessionEnd', labelKey: 'workspace.agentSettings.claude.hooks.events.SessionEnd.name', optionKey: 'workspace.agentSettings.claude.hooks.events.SessionEnd.option' },
];

const geminiHookEvents: HookEventOption[] = [
  { value: 'BeforeTool', labelKey: 'workspace.agentSettings.gemini.hooks.events.BeforeTool.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.BeforeTool.option' },
  { value: 'AfterTool', labelKey: 'workspace.agentSettings.gemini.hooks.events.AfterTool.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.AfterTool.option' },
  { value: 'BeforeAgent', labelKey: 'workspace.agentSettings.gemini.hooks.events.BeforeAgent.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.BeforeAgent.option' },
  { value: 'AfterAgent', labelKey: 'workspace.agentSettings.gemini.hooks.events.AfterAgent.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.AfterAgent.option' },
  { value: 'BeforeModel', labelKey: 'workspace.agentSettings.gemini.hooks.events.BeforeModel.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.BeforeModel.option' },
  { value: 'AfterModel', labelKey: 'workspace.agentSettings.gemini.hooks.events.AfterModel.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.AfterModel.option' },
  { value: 'BeforeToolSelection', labelKey: 'workspace.agentSettings.gemini.hooks.events.BeforeToolSelection.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.BeforeToolSelection.option' },
  { value: 'SessionStart', labelKey: 'workspace.agentSettings.gemini.hooks.events.SessionStart.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.SessionStart.option' },
  { value: 'SessionEnd', labelKey: 'workspace.agentSettings.gemini.hooks.events.SessionEnd.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.SessionEnd.option' },
  { value: 'PreCompress', labelKey: 'workspace.agentSettings.gemini.hooks.events.PreCompress.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.PreCompress.option' },
  { value: 'Notification', labelKey: 'workspace.agentSettings.gemini.hooks.events.Notification.name', optionKey: 'workspace.agentSettings.gemini.hooks.events.Notification.option' },
];

const codexHookEvents: HookEventOption[] = [
  { value: 'SessionStart', labelKey: 'workspace.agentSettings.codex.hooks.events.SessionStart', optionKey: 'workspace.agentSettings.codex.hooks.events.SessionStart' },
  { value: 'PreToolUse', labelKey: 'workspace.agentSettings.codex.hooks.events.PreToolUse', optionKey: 'workspace.agentSettings.codex.hooks.events.PreToolUse' },
  { value: 'PostToolUse', labelKey: 'workspace.agentSettings.codex.hooks.events.PostToolUse', optionKey: 'workspace.agentSettings.codex.hooks.events.PostToolUse' },
  { value: 'PermissionRequest', labelKey: 'workspace.agentSettings.codex.hooks.events.PermissionRequest', optionKey: 'workspace.agentSettings.codex.hooks.events.PermissionRequest' },
  { value: 'UserPromptSubmit', labelKey: 'workspace.agentSettings.codex.hooks.events.UserPromptSubmit', optionKey: 'workspace.agentSettings.codex.hooks.events.UserPromptSubmit' },
  { value: 'Stop', labelKey: 'workspace.agentSettings.codex.hooks.events.Stop', optionKey: 'workspace.agentSettings.codex.hooks.events.Stop' },
];

const buildAvailableSubViews = (instructionSubView: string, capabilities: AgentToolCapabilities, extra: string[] = []) => [
  instructionSubView,
  ...(capabilities.mcp?.supported === false || !capabilities.mcp ? [] : ['mcp']),
  ...(capabilities.skills?.supported === false || !capabilities.skills ? [] : ['skills']),
  ...(capabilities.slashCommands?.supported === false || !capabilities.slashCommands ? [] : ['slash-commands']),
  ...(capabilities.agentDefinitions?.supported === false || !capabilities.agentDefinitions ? [] : ['subagents']),
  ...(capabilities.hooks?.supported === false || !capabilities.hooks ? [] : ['hooks']),
  ...(capabilities.scripts?.supported === false || !capabilities.scripts ? [] : ['scripts']),
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
  slashCommands: { supported: true, scopes: ['project', 'user'], format: 'markdown', supportsNamespace: true },
  agentDefinitions: {
    supported: true,
    endpoint: 'subagents',
    displayLabelKey: 'workspace.navigation.sub.claudeCodeSettings.subagents',
    scopes: ['project', 'user', 'plugin'],
    format: 'markdown',
  },
  skills: { supported: true, collection: 'skills', scopes: ['project', 'user', 'plugin'], supportsPlugin: true, readOnlyScopes: ['plugin'] },
  scripts: { supported: true, collection: 'scripts', scopes: ['project', 'user'], supportsPlugin: false },
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
  mcp: { supported: true, scopes: ['project', 'user'], supportsToggle: false },
  hooks: { supported: true, scopes: ['project', 'user'], events: geminiHookEvents, supportsActionMetadata: true },
  slashCommands: { supported: true, scopes: ['project', 'user'], format: 'toml', supportsNamespace: true },
  skills: { supported: true, collection: 'skills', scopes: ['project', 'user', 'plugin'], supportsPlugin: true, readOnlyScopes: ['plugin'] },
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
  availableSubViews: buildAvailableSubViews('gemini-md', geminiCapabilities, ['memory']),
  apiPathPrefix: 'gemini',
  availableScopes: ['project', 'user'],
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
