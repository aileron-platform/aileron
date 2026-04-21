/**
 * 導航相關常數配置
 * 基於原始 navigation.ts 的導航項目
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
  FileCode,
  Globe,
  Brain,
  CheckCircle2,
  Archive,
  Users,
  Wrench,
} from 'lucide-react';
import type { AgentToolType, AgentToolConfig } from '../features/agent-settings/types';
import { AGENT_TOOL_CONFIGS } from '../features/agent-settings/agentToolConfigs';

// Claude Code 功能統一 Icon 配置
export const CLAUDE_CODE_ICONS = {
  'claude-md': FileText,
  'hooks': Zap,
  'mcp': Network,
  'subagents': Bot,
  'slash-commands': Command,
  'output-styles': Sparkles,
  'skills': Wand2,
  'scripts': FileCode,
  'memory': Brain,
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
        labelKey: 'workspace.navigation.sub.versionControl.changes',
        icon: FileText,
        parentId: 'version-control',
      },
      {
        id: 'history',
        labelKey: 'workspace.navigation.sub.versionControl.history',
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
    id: 'preview',
    icon: Monitor,
    labelKey: 'workspace.navigation.main.preview',
    mode: 'three-column',
    hasSubMenu: true,
    subItems: [
      {
        id: 'session-result',
        labelKey: 'workspace.navigation.sub.preview.sessionResult',
        icon: FileText,
        parentId: 'preview',
      },
      {
        id: 'web-preview',
        labelKey: 'workspace.navigation.sub.preview.webPreview',
        icon: Monitor,
        parentId: 'preview',
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
        id: 'hooks',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.hooks',
        icon: CLAUDE_CODE_ICONS['hooks'],
        parentId: 'claude-code',
      },
      {
        id: 'slash-commands',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.slashCommands',
        icon: CLAUDE_CODE_ICONS['slash-commands'],
        parentId: 'claude-code',
      },
      {
        id: 'output-styles',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.outputStyles',
        icon: CLAUDE_CODE_ICONS['output-styles'],
        parentId: 'claude-code',
      },
      {
        id: 'skills',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.skills',
        icon: CLAUDE_CODE_ICONS['skills'],
        parentId: 'claude-code',
      },
      {
        id: 'scripts',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.scripts',
        icon: CLAUDE_CODE_ICONS['scripts'],
        parentId: 'claude-code',
      },
      {
        id: 'memory',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.memory',
        icon: CLAUDE_CODE_ICONS['memory'],
        parentId: 'claude-code',
      },
      {
        id: 'subagents',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.subagents',
        icon: CLAUDE_CODE_ICONS['subagents'],
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

// ============ 動態 Agent 工具導航 ============

/** Agent 設定通用 Icon 配置 */
const AGENT_SETTINGS_ICONS: Record<string, LucideIcon> = {
  'mcp': Network,
  'hooks': Zap,
  'slash-commands': Command,
  'skills': Wand2,
  'claude-md': FileText,
  'gemini-md': FileText,
  'agents-md': FileText,
  'output-styles': Sparkles,
  'subagents': Bot,
  'scripts': FileCode,
  'settings': Settings,
  'memory': Brain,
};

/** 子視圖的 i18n key 對照表 */
const SUB_VIEW_LABEL_KEYS: Record<string, string> = {
  'claude-md': 'workspace.navigation.sub.claudeCodeSettings.claudeMd',
  'gemini-md': 'workspace.agentSettings.common.subViews.geminiMd',
  'agents-md': 'workspace.agentSettings.common.subViews.agentsMd',
  'mcp': 'workspace.navigation.sub.claudeCodeSettings.mcp',
  'hooks': 'workspace.navigation.sub.claudeCodeSettings.hooks',
  'slash-commands': 'workspace.navigation.sub.claudeCodeSettings.slashCommands',
  'output-styles': 'workspace.navigation.sub.claudeCodeSettings.outputStyles',
  'subagents': 'workspace.navigation.sub.claudeCodeSettings.subagents',
  'skills': 'workspace.navigation.sub.claudeCodeSettings.skills',
  'scripts': 'workspace.navigation.sub.claudeCodeSettings.scripts',
  'settings': 'workspace.navigation.sub.claudeCodeSettings.settings',
  'memory': 'workspace.navigation.sub.claudeCodeSettings.memory',
};

/**
 * 根據 AgentToolConfig 建立導航項目
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

/** 不包含 Agent 工具的靜態導航項目 */
const STATIC_NAVIGATION_ITEMS: NavigationConfig[] = MAIN_NAVIGATION_ITEMS.filter(
  (item) => item.id !== 'claude-code',
);

/**
 * 根據 agentType 取得完整的導航項目列表
 * 動態替換 Agent 工具設定區段
 */
export const getNavigationItems = (agentType: AgentToolType): NavigationConfig[] => {
  const config = AGENT_TOOL_CONFIGS[agentType];
  const agentNavItem = buildAgentToolNavigationItem(config);
  return [...STATIC_NAVIGATION_ITEMS, agentNavItem];
};
