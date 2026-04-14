/**
 * Agent Tool Configs - 四種 AI Agent 工具的設定常數物件
 */

import { Bot, Building, Globe, Sparkles, User } from 'lucide-react';
import type { AgentToolType, AgentToolConfig, HookEventOption } from './types';

/** Claude Code hook 事件 */
const claudeHookEvents: HookEventOption[] = [
  { value: 'PreToolUse', labelKey: 'workspace.claudeCode.hooks.events.PreToolUse.name', optionKey: 'workspace.claudeCode.hooks.events.PreToolUse.option' },
  { value: 'PostToolUse', labelKey: 'workspace.claudeCode.hooks.events.PostToolUse.name', optionKey: 'workspace.claudeCode.hooks.events.PostToolUse.option' },
  { value: 'UserPromptSubmit', labelKey: 'workspace.claudeCode.hooks.events.UserPromptSubmit.name', optionKey: 'workspace.claudeCode.hooks.events.UserPromptSubmit.option' },
  { value: 'Notification', labelKey: 'workspace.claudeCode.hooks.events.Notification.name', optionKey: 'workspace.claudeCode.hooks.events.Notification.option' },
  { value: 'Stop', labelKey: 'workspace.claudeCode.hooks.events.Stop.name', optionKey: 'workspace.claudeCode.hooks.events.Stop.option' },
  { value: 'SubagentStop', labelKey: 'workspace.claudeCode.hooks.events.SubagentStop.name', optionKey: 'workspace.claudeCode.hooks.events.SubagentStop.option' },
  { value: 'PreCompact', labelKey: 'workspace.claudeCode.hooks.events.PreCompact.name', optionKey: 'workspace.claudeCode.hooks.events.PreCompact.option' },
  { value: 'SessionStart', labelKey: 'workspace.claudeCode.hooks.events.SessionStart.name', optionKey: 'workspace.claudeCode.hooks.events.SessionStart.option' },
  { value: 'SessionEnd', labelKey: 'workspace.claudeCode.hooks.events.SessionEnd.name', optionKey: 'workspace.claudeCode.hooks.events.SessionEnd.option' },
];

/** Gemini CLI hook 事件 */
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

/** Claude Code 設定 */
const claudeConfig: AgentToolConfig = {
  id: 'claude',
  navigationId: 'claude-code',
  navigationLabelKey: 'workspace.navigation.main.claudeCodeSettings',
  navigationIcon: Bot,
  agentsMd: {
    fileName: 'CLAUDE.md',
    subViewId: 'claude-md',
    labelKey: 'workspace.agentSettings.claude.agentsMd',
    scopes: [
      { value: 'project', labelKey: 'workspace.agentSettings.common.scope.project', icon: Building },
      { value: 'user', labelKey: 'workspace.agentSettings.common.scope.user', icon: User },
    ],
  },
  availableSubViews: ['claude-md', 'memory', 'mcp', 'hooks', 'slash-commands', 'output-styles', 'subagents', 'skills', 'scripts', 'settings'],
  apiPathPrefix: 'claude-code',
  availableScopes: ['project', 'user', 'local', 'plugin'],
  i18nNamespace: 'workspace.claudeCode',
  globalSettingsLabelKey: 'pages.settings.tabs.claudeCode',
  hookEvents: claudeHookEvents,
};

/** Gemini 設定 */
const geminiConfig: AgentToolConfig = {
  id: 'gemini',
  navigationId: 'gemini',
  navigationLabelKey: 'workspace.navigation.main.geminiSettings',
  navigationIcon: Sparkles,
  agentsMd: {
    fileName: 'GEMINI.md',
    subViewId: 'gemini-md',
    labelKey: 'workspace.agentSettings.gemini.agentsMd',
    scopes: [
      { value: 'project', labelKey: 'workspace.agentSettings.common.scope.project', icon: Building },
      { value: 'user', labelKey: 'workspace.agentSettings.common.scope.user', icon: User },
    ],
  },
  availableSubViews: ['gemini-md', 'mcp', 'hooks', 'slash-commands', 'skills'],
  apiPathPrefix: 'gemini',
  availableScopes: ['project', 'user'],
  supportsToggle: false,
  slashCommandFormat: 'toml',
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.gemini',
  hookEvents: geminiHookEvents,
};

/** OpenCode 設定 */
const opencodeConfig: AgentToolConfig = {
  id: 'opencode',
  navigationId: 'opencode',
  navigationLabelKey: 'workspace.navigation.main.opencodeSettings',
  navigationIcon: Globe,
  agentsMd: {
    fileName: 'AGENTS.md',
    subViewId: 'agents-md',
    labelKey: 'workspace.agentSettings.opencode.agentsMd',
    scopes: [
      { value: 'project', labelKey: 'workspace.agentSettings.common.scope.project', icon: Building },
      { value: 'user', labelKey: 'workspace.agentSettings.common.scope.global', icon: User },
    ],
  },
  availableSubViews: ['agents-md', 'mcp', 'hooks', 'slash-commands', 'skills'],
  apiPathPrefix: 'opencode',
  availableScopes: ['project', 'user'],
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.opencode',
};

/** Codex 設定 */
const codexConfig: AgentToolConfig = {
  id: 'codex',
  navigationId: 'codex',
  navigationLabelKey: 'workspace.navigation.main.codexSettings',
  navigationIcon: Bot,
  agentsMd: {
    fileName: 'AGENTS.md',
    subViewId: 'agents-md',
    labelKey: 'workspace.agentSettings.codex.agentsMd',
    scopes: [
      { value: 'project', labelKey: 'workspace.agentSettings.common.scope.project', icon: Building },
      { value: 'user', labelKey: 'workspace.agentSettings.common.scope.user', icon: User },
    ],
  },
  availableSubViews: ['agents-md', 'mcp', 'hooks', 'slash-commands', 'skills'],
  apiPathPrefix: 'codex',
  availableScopes: ['project', 'user'],
  i18nNamespace: 'workspace.agentSettings.common',
  globalSettingsLabelKey: 'pages.settings.tabs.codex',
};

/** 所有 Agent 工具設定 */
export const AGENT_TOOL_CONFIGS: Record<AgentToolType, AgentToolConfig> = {
  claude: claudeConfig,
  gemini: geminiConfig,
  opencode: opencodeConfig,
  codex: codexConfig,
};



/** 所有 Agent 工具的 navigationId 清單 */
export const AGENT_NAVIGATION_IDS = Object.values(AGENT_TOOL_CONFIGS).map(c => c.navigationId);
