import type { LucideIcon } from 'lucide-react';
import {
  Bot,
  Brain,
  Cable,
  Command,
  FileText,
  Network,
  Settings,
  Shield,
  Sparkles,
  Wand2,
  Zap,
} from 'lucide-react';
import { getAgentSubViewLabelKey } from '../features/agent-settings/agentSubViewLabelModel';

export const AGENT_TOOL_ICONS = {
  'claude-md': FileText,
  hooks: Zap,
  mcp: Network,
  subagents: Bot,
  'slash-commands': Command,
  'output-styles': Sparkles,
  skills: Wand2,
  memory: Brain,
  rules: Shield,
} as const satisfies Record<string, LucideIcon>;

const AGENT_SETTINGS_ICONS: Record<string, LucideIcon> = {
  mcp: AGENT_TOOL_ICONS.mcp,
  hooks: AGENT_TOOL_ICONS.hooks,
  rules: AGENT_TOOL_ICONS.rules,
  plugins: Wand2,
  prompts: Command,
  'slash-commands': AGENT_TOOL_ICONS['slash-commands'],
  skills: AGENT_TOOL_ICONS.skills,
  'claude-md': AGENT_TOOL_ICONS['claude-md'],
  'agents-md': FileText,
  'output-styles': AGENT_TOOL_ICONS['output-styles'],
  apps: Cable,
  subagents: AGENT_TOOL_ICONS.subagents,
  settings: Settings,
  memory: AGENT_TOOL_ICONS.memory,
};

const NAVIGATION_SUB_VIEW_LABEL_KEY_OVERRIDES: Record<string, string> = {
  'claude-md': 'workspace.navigation.sub.claudeCodeSettings.claudeMd',
  mcp: 'workspace.navigation.sub.claudeCodeSettings.mcp',
  hooks: 'workspace.navigation.sub.claudeCodeSettings.hooks',
  'slash-commands': 'workspace.navigation.sub.claudeCodeSettings.slashCommands',
  'output-styles': 'workspace.navigation.sub.claudeCodeSettings.outputStyles',
  skills: 'workspace.navigation.sub.claudeCodeSettings.skills',
};

export interface AgentToolSubViewNavigationMeta {
  labelKey: string;
  icon: LucideIcon;
}

export const getAgentToolSubViewNavigationMeta = (
  subViewId: string,
): AgentToolSubViewNavigationMeta => ({
  labelKey: NAVIGATION_SUB_VIEW_LABEL_KEY_OVERRIDES[subViewId] ?? getAgentSubViewLabelKey(subViewId),
  icon: AGENT_SETTINGS_ICONS[subViewId] || Settings,
});
