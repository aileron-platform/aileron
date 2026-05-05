/**
 * Navigation constants.
 * Based on the original navigation.ts items.
 */

import type { LucideIcon } from 'lucide-react';
import {
  Folder,
  GitBranch,
  BookOpen,
  Settings,
  Database,
  Building,
  Cpu,
  Monitor,
  Bot,
  Terminal,
  FileText,
  Network,
  Zap,
  Command,
  Sparkles,
  Shield,
  Clock,
  AlertTriangle,
  Wand2,
  Globe,
  Brain,
  CheckCircle2,
  Archive,
  Users,
  Wrench,
} from 'lucide-react';
import type { AgentToolType, AgentToolConfig } from '../features/agent-settings/types';
import { AGENT_TOOL_CONFIGS } from '../features/agent-settings/agentToolConfigs';

// Shared Claude Code icon configuration.
export const CLAUDE_CODE_ICONS = {
  'claude-md': FileText,
  'hooks': Zap,
  'mcp': Network,
  'subagents': Bot,
  'slash-commands': Command,
  'output-styles': Sparkles,
  'skills': Wand2,
  'memory': Brain,
  'rules': Shield,
} as const;

export interface NavigationConfig {
  id: string;
  icon: any;
  labelKey: string;
  mode: 'three-column' | 'four-column';
  hasSubMenu: boolean;
  subItems?: {
    id: string;
    labelKey: string;
    icon: any;
    parentId: string;
  }[];
}

export const MAIN_NAVIGATION_ITEMS: NavigationConfig[] = [
  {
    id: 'file-management',
    icon: Folder,
    labelKey: 'workspace.navigation.main.fileManagement',
    mode: 'four-column',
    hasSubMenu: false,
  },
  {
    id: 'version-control',
    icon: GitBranch,
    labelKey: 'workspace.navigation.main.versionControl',
    mode: 'four-column',
    hasSubMenu: true,
    subItems: [
      {
        id: 'changes',
        labelKey: 'shared.versionControl.mode.fileChanges',
        icon: FileText,
        parentId: 'version-control',
      },
      {
        id: 'history',
        labelKey: 'shared.versionControl.mode.commitHistory',
        icon: Clock,
        parentId: 'version-control',
      },
    ],
  },
  {
    id: 'openspec',
    icon: BookOpen,
    labelKey: 'workspace.navigation.main.openspec',
    mode: 'four-column',
    hasSubMenu: true,
    subItems: [
      {
        id: 'in-progress',
        labelKey: 'workspace.navigation.sub.openspec.inProgress',
        icon: Clock,
        parentId: 'openspec',
      },
      {
        id: 'complete',
        labelKey: 'workspace.navigation.sub.openspec.complete',
        icon: CheckCircle2,
        parentId: 'openspec',
      },
      {
        id: 'archived',
        labelKey: 'workspace.navigation.sub.openspec.archived',
        icon: Archive,
        parentId: 'openspec',
      },
      {
        id: 'customization',
        labelKey: 'workspace.navigation.sub.openspec.customization',
        icon: Wrench,
        parentId: 'openspec',
      },
    ],
  },
  {
    id: 'workspace-settings',
    icon: Settings,
    labelKey: 'workspace.navigation.main.workspaceSettings',
    mode: 'three-column',
    hasSubMenu: true,
    subItems: [
      {
        id: 'basic',
        labelKey: 'workspace.navigation.sub.workspaceSettings.basic',
        icon: Settings,
        parentId: 'workspace-settings',
      },
      {
        id: 'access',
        labelKey: 'workspace.navigation.sub.workspaceSettings.access',
        icon: Users,
        parentId: 'workspace-settings',
      },
      {
        id: 'knowledge-bases',
        labelKey: 'workspace.navigation.sub.workspaceSettings.knowledgeBases',
        icon: Database,
        parentId: 'workspace-settings',
      },
      {
        id: 'reset',
        labelKey: 'workspace.navigation.sub.workspaceSettings.reset',
        icon: AlertTriangle,
        parentId: 'workspace-settings',
      },
    ],
  },
  {
    id: 'container-management',
    icon: Building,
    labelKey: 'workspace.navigation.main.containerManagement',
    mode: 'three-column',
    hasSubMenu: true,
    subItems: [
      {
        id: 'runtime',
        labelKey: 'workspace.navigation.sub.containerManagement.runtime',
        icon: Monitor,
        parentId: 'container-management',
      },
      {
        id: 'firewall',
        labelKey: 'workspace.navigation.sub.containerManagement.firewall',
        icon: Shield,
        parentId: 'container-management',
      },
      {
        id: 'terminal',
        labelKey: 'workspace.navigation.sub.containerManagement.terminal',
        icon: Terminal,
        parentId: 'container-management',
      },
      {
        id: 'browser',
        labelKey: 'workspace.navigation.sub.containerManagement.browser',
        icon: Globe,
        parentId: 'container-management',
      },
    ],
  },
  {
    id: 'workspace-automation',
    icon: Cpu,
    labelKey: 'workspace.navigation.main.automation',
    mode: 'three-column',
    hasSubMenu: false,
  },
  {
    id: 'canvas',
    icon: Monitor,
    labelKey: 'workspace.navigation.main.canvas',
    mode: 'three-column',
    hasSubMenu: true,
    subItems: [
      {
        id: 'session-result',
        labelKey: 'workspace.navigation.sub.canvas.sessionResult',
        icon: FileText,
        parentId: 'canvas',
      },
      {
        id: 'web-canvas',
        labelKey: 'workspace.navigation.sub.canvas.webCanvas',
        icon: Monitor,
        parentId: 'canvas',
      },
    ],
  },
  {
    id: 'claude-code',
    icon: Bot,
    labelKey: 'workspace.navigation.main.claudeCodeSettings',
    mode: 'three-column',
    hasSubMenu: true,
    subItems: [
      {
        id: 'claude-md',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.claudeMd',
        icon: CLAUDE_CODE_ICONS['claude-md'],
        parentId: 'claude-code',
      },
      {
        id: 'mcp',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.mcp',
        icon: CLAUDE_CODE_ICONS['mcp'],
        parentId: 'claude-code',
      },
      {
        id: 'skills',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.skills',
        icon: CLAUDE_CODE_ICONS['skills'],
        parentId: 'claude-code',
      },
      {
        id: 'slash-commands',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.slashCommands',
        icon: CLAUDE_CODE_ICONS['slash-commands'],
        parentId: 'claude-code',
      },
      {
        id: 'subagents',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.subagents',
        icon: CLAUDE_CODE_ICONS['subagents'],
        parentId: 'claude-code',
      },
      {
        id: 'hooks',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.hooks',
        icon: CLAUDE_CODE_ICONS['hooks'],
        parentId: 'claude-code',
      },
      {
        id: 'output-styles',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.outputStyles',
        icon: CLAUDE_CODE_ICONS['output-styles'],
        parentId: 'claude-code',
      },
      {
        id: 'memory',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.memory',
        icon: CLAUDE_CODE_ICONS['memory'],
        parentId: 'claude-code',
      },
      {
        id: 'settings',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.settings',
        icon: Settings,
        parentId: 'claude-code',
      },
    ],
  },
];

// ============ Dynamic agent tool navigation ============

/** Shared icon configuration for agent settings. */
const AGENT_SETTINGS_ICONS: Record<string, LucideIcon> = {
  'mcp': Network,
  'hooks': Zap,
  'rules': Shield,
  'plugins': Wand2,
  'prompts': Command,
  'slash-commands': Command,
  'skills': Wand2,
  'claude-md': FileText,
  'gemini-md': FileText,
  'agents-md': FileText,
  'output-styles': Sparkles,
  'subagents': Bot,
  'settings': Settings,
  'memory': Brain,
};

/** Subview i18n key mapping. */
const SUB_VIEW_LABEL_KEYS: Record<string, string> = {
  'claude-md': 'workspace.navigation.sub.claudeCodeSettings.claudeMd',
  'gemini-md': 'workspace.agentSettings.common.subViews.geminiMd',
  'agents-md': 'workspace.agentSettings.common.subViews.agentsMd',
  'mcp': 'workspace.navigation.sub.claudeCodeSettings.mcp',
  'hooks': 'workspace.navigation.sub.claudeCodeSettings.hooks',
  'rules': 'workspace.agentSettings.common.subViews.rules',
  'plugins': 'workspace.agentSettings.common.subViews.plugins',
  'extensions': 'workspace.agentSettings.common.subViews.extensions',
  'prompts': 'workspace.agentSettings.common.subViews.prompts',
  'slash-commands': 'workspace.navigation.sub.claudeCodeSettings.slashCommands',
  'output-styles': 'workspace.navigation.sub.claudeCodeSettings.outputStyles',
  'subagents': 'workspace.agentSettings.common.subViews.subagents',
  'skills': 'workspace.navigation.sub.claudeCodeSettings.skills',
  'settings': 'workspace.navigation.sub.claudeCodeSettings.settings',
  'memory': 'workspace.agentSettings.common.subViews.memory',
};

/**
 * Build a navigation item from AgentToolConfig.
 */
export const buildAgentToolNavigationItem = (config: AgentToolConfig): NavigationConfig => ({
  id: config.navigationId,
  icon: config.navigationIcon,
  labelKey: config.navigationLabelKey,
  mode: 'three-column',
  hasSubMenu: true,
  subItems: config.availableSubViews.map((subViewId) => ({
    id: subViewId,
    labelKey: SUB_VIEW_LABEL_KEYS[subViewId] || `workspace.agentSettings.common.subViews.${subViewId}`,
    icon: AGENT_SETTINGS_ICONS[subViewId] || Settings,
    parentId: config.navigationId,
  })),
});

/** Static navigation items without agent tools. */
const STATIC_NAVIGATION_ITEMS: NavigationConfig[] = MAIN_NAVIGATION_ITEMS.filter(
  (item) => item.id !== 'claude-code',
);

/**
 * Get the complete navigation item list for the active agent type.
 * Replaces the agent tool settings section dynamically.
 */
export const getNavigationItems = (agentType: AgentToolType): NavigationConfig[] => {
  const config = AGENT_TOOL_CONFIGS[agentType];
  const agentNavItem = buildAgentToolNavigationItem(config);
  return [...STATIC_NAVIGATION_ITEMS, agentNavItem];
};
