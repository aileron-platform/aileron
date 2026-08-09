/**
 * Navigation constants.
 * Based on the original navigation.ts items.
 */

import {
  Folder,
  GitBranch,
  Settings,
  Database,
  Building,
  Cpu,
  Monitor,
  Bot,
  SquareTerminal,
  FileText,
  Network,
  Zap,
  Shield,
  Clock,
  AlertTriangle,
  Globe,
  Users,
  MessageSquare,
  type LucideIcon,
} from 'lucide-react';
import type { AgentSettingsToolId, AgentToolConfig } from '../features/agent-settings/model/capabilities';
import { AGENT_TOOL_CONFIGS } from '../features/agent-settings/agentToolConfigs';
import { AGENT_TOOL_ICONS, getAgentToolSubViewNavigationMeta } from './agentToolNavigationModel';
import { OPERATION_IDS } from '@/shared/authorization/operationIds';
import type { AgenticTool } from '@/shared/types/agenticTool';
import type { WorkspaceOperationId } from '../model/workspacePermissions';

export interface NavigationSubItem {
  id: string;
  labelKey: string;
  icon: LucideIcon;
  parentId: string;
  targetFeature?: string;
  targetSubView?: string;
  requiredWorkspaceOperation?: WorkspaceOperationId;
}

export interface NavigationConfig {
  id: string;
  icon: LucideIcon;
  iconSrc?: string;
  labelKey: string;
  hasSubMenu: boolean;
  subItems?: NavigationSubItem[];
  requiredWorkspaceOperation?: WorkspaceOperationId;
}

const AGENTIC_TOOL_NAVIGATION_ICON_SRC: Record<AgenticTool, string> = {
  'claude-code': '/marketplace/providers/claude-code.png',
  codex: '/marketplace/providers/codex.png',
  opencode: '/marketplace/providers/opencode.png',
};

export const MAIN_NAVIGATION_ITEMS: NavigationConfig[] = [
  {
    id: 'ai-agent',
    icon: Bot,
    labelKey: 'workspace.navigation.main.aiAgent',
    hasSubMenu: true,
    subItems: [
      {
        id: 'ai-chat-home',
        labelKey: 'workspace.navigation.sub.aiAgent.aiChat',
        icon: MessageSquare,
        parentId: 'ai-agent',
        targetFeature: 'ai-chat-home',
        requiredWorkspaceOperation: OPERATION_IDS.workspaceAgentChatUse,
      },
      {
        id: 'terminal',
        labelKey: 'workspace.navigation.sub.aiAgent.terminal',
        icon: SquareTerminal,
        parentId: 'ai-agent',
        targetFeature: 'container-management',
        targetSubView: 'terminal',
        requiredWorkspaceOperation: OPERATION_IDS.workspaceTerminalUse,
      },
    ],
  },
  {
    id: 'file-management',
    icon: Folder,
    labelKey: 'workspace.navigation.main.fileManagement',
    hasSubMenu: false,
    requiredWorkspaceOperation: OPERATION_IDS.workspaceDetailRead,
  },
  {
    id: 'version-control',
    icon: GitBranch,
    labelKey: 'workspace.navigation.main.versionControl',
    hasSubMenu: true,
    requiredWorkspaceOperation: OPERATION_IDS.workspaceDetailRead,
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
    id: 'workspace-settings',
    icon: Settings,
    labelKey: 'workspace.navigation.main.workspaceSettings',
    hasSubMenu: true,
    subItems: [
      {
        id: 'basic',
        labelKey: 'workspace.navigation.sub.workspaceSettings.basic',
        icon: Settings,
        parentId: 'workspace-settings',
        requiredWorkspaceOperation: OPERATION_IDS.workspaceDetailRead,
      },
      {
        id: 'access',
        labelKey: 'workspace.navigation.sub.workspaceSettings.access',
        icon: Users,
        parentId: 'workspace-settings',
        requiredWorkspaceOperation: OPERATION_IDS.workspaceDetailRead,
      },
      {
        id: 'knowledge-bases',
        labelKey: 'workspace.navigation.sub.workspaceSettings.knowledgeBases',
        icon: Database,
        parentId: 'workspace-settings',
        requiredWorkspaceOperation: OPERATION_IDS.workspaceDetailRead,
      },
      {
        id: 'reset',
        labelKey: 'workspace.navigation.sub.workspaceSettings.reset',
        icon: AlertTriangle,
        parentId: 'workspace-settings',
        requiredWorkspaceOperation: OPERATION_IDS.workspaceLifecycleExecute,
      },
    ],
  },
  {
    id: 'container-management',
    icon: Building,
    labelKey: 'workspace.navigation.main.containerManagement',
    hasSubMenu: true,
    subItems: [
      {
        id: 'runtime',
        labelKey: 'workspace.navigation.sub.containerManagement.runtime',
        icon: Monitor,
        parentId: 'container-management',
        requiredWorkspaceOperation: OPERATION_IDS.workspaceSensitiveSettingsManage,
      },
      {
        id: 'firewall',
        labelKey: 'workspace.navigation.sub.containerManagement.firewall',
        icon: Shield,
        parentId: 'container-management',
        requiredWorkspaceOperation: OPERATION_IDS.workspaceFirewallRead,
      },
    ],
  },
  {
    id: 'workspace-automation',
    icon: Cpu,
    labelKey: 'workspace.navigation.main.automation',
    hasSubMenu: false,
    requiredWorkspaceOperation: OPERATION_IDS.workspaceAutomationExecute,
  },
  {
    id: 'canvas',
    icon: Monitor,
    labelKey: 'workspace.navigation.main.canvas',
    hasSubMenu: false,
    requiredWorkspaceOperation: OPERATION_IDS.workspaceDetailRead,
  },
  {
    id: 'browser',
    icon: Globe,
    labelKey: 'workspace.navigation.main.browser',
    hasSubMenu: false,
    requiredWorkspaceOperation: OPERATION_IDS.workspaceBrowserAutomationUse,
  },
  {
    id: 'claude-code',
    icon: Bot,
    labelKey: 'workspace.navigation.main.claudeCodeSettings',
    hasSubMenu: true,
    subItems: [
      {
        id: 'claude-md',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.claudeMd',
        icon: AGENT_TOOL_ICONS['claude-md'],
        parentId: 'claude-code',
      },
      {
        id: 'mcp',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.mcp',
        icon: AGENT_TOOL_ICONS.mcp,
        parentId: 'claude-code',
      },
      {
        id: 'skills',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.skills',
        icon: AGENT_TOOL_ICONS.skills,
        parentId: 'claude-code',
      },
      {
        id: 'slash-commands',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.slashCommands',
        icon: AGENT_TOOL_ICONS['slash-commands'],
        parentId: 'claude-code',
      },
      {
        id: 'subagents',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.subagents',
        icon: AGENT_TOOL_ICONS.subagents,
        parentId: 'claude-code',
      },
      {
        id: 'hooks',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.hooks',
        icon: AGENT_TOOL_ICONS.hooks,
        parentId: 'claude-code',
      },
      {
        id: 'output-styles',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.outputStyles',
        icon: AGENT_TOOL_ICONS['output-styles'],
        parentId: 'claude-code',
      },
      {
        id: 'memory',
        labelKey: 'workspace.navigation.sub.claudeCodeSettings.memory',
        icon: AGENT_TOOL_ICONS.memory,
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

/**
 * Build a navigation item from AgentToolConfig.
 */
export const buildAgentToolNavigationItem = (config: AgentToolConfig): NavigationConfig => ({
  id: config.navigationId,
  icon: config.navigationIcon,
  iconSrc: AGENTIC_TOOL_NAVIGATION_ICON_SRC[config.id === 'claude' ? 'claude-code' : config.id],
  labelKey: config.navigationLabelKey,
  hasSubMenu: true,
  requiredWorkspaceOperation: OPERATION_IDS.workspaceDetailRead,
  subItems: config.availableSubViews.map((subViewId) => {
    const meta = getAgentToolSubViewNavigationMeta(subViewId);
    return {
      id: subViewId,
      labelKey: meta.labelKey,
      icon: meta.icon,
      parentId: config.navigationId,
      ...(
        subViewId === 'mcp' || subViewId === 'settings'
          ? {
            requiredWorkspaceOperation:
              OPERATION_IDS.workspaceSensitiveSettingsManage,
          }
          : {
            requiredWorkspaceOperation: OPERATION_IDS.workspaceDetailRead,
          }
      ),
    };
  }),
});

/** Static navigation items without agent tools. */
const STATIC_NAVIGATION_ITEMS: NavigationConfig[] = MAIN_NAVIGATION_ITEMS.filter(
  (item) => item.id !== 'claude-code',
);

interface GetNavigationItemsOptions {
  agenticTools: AgenticTool[];
  hasWorkspaceOperation: (operation: WorkspaceOperationId) => boolean;
}

const toAgentSettingsToolId = (toolId: AgenticTool): AgentSettingsToolId => (
  toolId === 'claude-code' ? 'claude' : toolId
);

/**
 * Get the complete navigation item list for enabled agent tools.
 */
export const getNavigationItems = ({
  agenticTools,
  hasWorkspaceOperation,
}: GetNavigationItemsOptions): NavigationConfig[] => {
  const agentNavItems = agenticTools.map((toolId) => {
    const config = AGENT_TOOL_CONFIGS[toAgentSettingsToolId(toolId)];
    return buildAgentToolNavigationItem(config);
  });
  return [...STATIC_NAVIGATION_ITEMS, ...agentNavItems].flatMap((item) => {
    if (
      item.requiredWorkspaceOperation
      && !hasWorkspaceOperation(item.requiredWorkspaceOperation)
    ) {
      return [];
    }

    const subItems = item.subItems?.filter((subItem) => (
      !subItem.requiredWorkspaceOperation
      || hasWorkspaceOperation(subItem.requiredWorkspaceOperation)
    ));
    if (item.hasSubMenu && subItems?.length === 0) {
      return [];
    }

    return [{
      ...item,
      ...(subItems ? { subItems } : {}),
    }];
  });
};
