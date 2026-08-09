import type { AgentSettingsToolId } from '../features/agent-settings/model/capabilities';
import {
  getAgentTypeFromFeatureId,
  normalizeAgentType,
} from '../features/agent-settings/model/agentSettingsModel';
import type { WorkspacePermissions } from '../model/workspacePermissions';
import type {
  WorkspaceCompanionActiveTab,
  WorkspaceCompanionTerminalPlacement,
  WorkspaceContextType,
  WorkspaceState,
} from '../providers/workspaceStateTypes';

const AGENT_TOOL_FEATURES = ['claude-code', 'opencode', 'codex'] as const;
const CLAUDE_DOCUMENT_SUBVIEWS = [
  'slash-commands',
  'output-styles',
  'subagents',
  'memory',
] as const;
const CODEX_DOCUMENT_SUBVIEWS = ['subagents', 'prompts', 'rules'] as const;
const OPENCODE_DOCUMENT_SUBVIEWS = ['slash-commands', 'subagents'] as const;

type WorkspaceRuntimeSurface = Pick<
  WorkspaceContextType['workspaceRuntime'],
  'workspaceId' | 'agenticTools'
>;

type WorkspacePermissionSurface = Pick<
  WorkspacePermissions,
  'canRead' | 'canUseChat' | 'canUseTerminal'
>;

export interface WorkspaceShellSurfaceModel {
  activeAgentToolId: AgentSettingsToolId;
  hasWorkspaceRuntime: boolean;
  isAgentToolFeatureActive: boolean;
  isAgentToolSkillsView: boolean;
  isMainContentExpanded: boolean;
  isContainerTerminalPage: boolean;
  shouldRenderNavigator: boolean;
  companionActiveTab: WorkspaceCompanionActiveTab | null;
  shouldRenderCompanion: boolean;
  companionPlacement: WorkspaceCompanionTerminalPlacement;
  isCompanionFullscreen: boolean;
}

export const isAgentToolFeature = (
  feature: WorkspaceState['currentFeature'],
): boolean => AGENT_TOOL_FEATURES.includes(
  feature as (typeof AGENT_TOOL_FEATURES)[number],
);

export const resolveWorkspaceCompanionTab = (
  activeTab: WorkspaceCompanionActiveTab,
  canUseAgentChat: boolean,
  canUseTerminal: boolean,
): WorkspaceCompanionActiveTab | null => {
  const allowedTabs = [
    ...(canUseAgentChat ? ['ai-chat' as const] : []),
    ...(canUseTerminal ? ['terminal' as const] : []),
  ];
  return allowedTabs.includes(activeTab) ? activeTab : allowedTabs[0] ?? null;
};

export const hasWorkspaceNavigator = ({
  feature,
  subView,
  canRead,
}: {
  feature: WorkspaceState['currentFeature'];
  subView: string;
  canRead: boolean;
}): boolean => {
  if (feature === 'file-management' || feature === 'version-control') {
    return canRead;
  }
  if (!isAgentToolFeature(feature) || !canRead) {
    return false;
  }
  if (subView === 'skills') {
    return true;
  }
  if (feature === 'claude-code') {
    return CLAUDE_DOCUMENT_SUBVIEWS.includes(
      subView as (typeof CLAUDE_DOCUMENT_SUBVIEWS)[number],
    );
  }
  if (feature === 'opencode') {
    return OPENCODE_DOCUMENT_SUBVIEWS.includes(
      subView as (typeof OPENCODE_DOCUMENT_SUBVIEWS)[number],
    );
  }
  return CODEX_DOCUMENT_SUBVIEWS.includes(
    subView as (typeof CODEX_DOCUMENT_SUBVIEWS)[number],
  );
};

export const resolveWorkspaceShellSurface = ({
  state,
  permissions,
  workspaceRuntime,
}: {
  state: WorkspaceState;
  permissions: WorkspacePermissionSurface;
  workspaceRuntime: WorkspaceRuntimeSurface;
}): WorkspaceShellSurfaceModel => {
  const activeAgentToolId = getAgentTypeFromFeatureId(state.currentFeature)
    ?? normalizeAgentType(workspaceRuntime.agenticTools[0]);
  const hasWorkspaceRuntime = Boolean(workspaceRuntime.workspaceId);
  const isAgentToolFeatureActive = isAgentToolFeature(state.currentFeature);
  const isAgentToolSkillsView = isAgentToolFeatureActive
    && state.agentToolSettings.subView === 'skills';
  const isMainContentExpanded = (
    state.currentFeature === 'file-management' && state.fileManagementEditorExpanded
  ) || state.mainContentExpanded;
  const isContainerTerminalPage = state.currentFeature === 'container-management'
    && state.containerManagement.subView === 'terminal';
  const showNavigator = state.currentFeature !== 'ai-chat-home'
    && !isContainerTerminalPage
    && !isMainContentExpanded;
  const shouldRenderNavigator = showNavigator && hasWorkspaceNavigator({
    feature: state.currentFeature,
    subView: state.agentToolSettings.subView,
    canRead: permissions.canRead,
  });
  const hasCompanionAccess = permissions.canUseChat || permissions.canUseTerminal;
  const companionActiveTab = resolveWorkspaceCompanionTab(
    state.companionActiveTab,
    permissions.canUseChat,
    permissions.canUseTerminal,
  );
  const shouldRenderCompanion = hasWorkspaceRuntime
    && hasCompanionAccess
    && companionActiveTab !== null
    && state.currentFeature !== 'ai-chat-home'
    && !isContainerTerminalPage
    && !isMainContentExpanded;
  const companionPlacement: WorkspaceCompanionTerminalPlacement = companionActiveTab === 'terminal'
    ? state.companionTerminalPlacement
    : 'side';

  return {
    activeAgentToolId,
    hasWorkspaceRuntime,
    isAgentToolFeatureActive,
    isAgentToolSkillsView,
    isMainContentExpanded,
    isContainerTerminalPage,
    shouldRenderNavigator,
    companionActiveTab,
    shouldRenderCompanion,
    companionPlacement,
    isCompanionFullscreen: shouldRenderCompanion && state.chatExpanded,
  };
};
