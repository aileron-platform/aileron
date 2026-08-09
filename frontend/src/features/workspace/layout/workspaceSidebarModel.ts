import type { WorkspaceState } from '../providers/workspaceStateTypes';
import { AGENT_NAVIGATION_IDS } from '../features/agent-settings/agentToolConfigs';
import type { NavigationConfig, NavigationSubItem } from './workspaceNavigationModel';
import { ROUTES } from '@/shared/constants/routes';

/**
 * Per-feature active sub-view selectors. Driving the lookup from a map keeps the
 * resolution data-driven instead of a per-feature if-ladder with special cases.
 */
const SUB_VIEW_SELECTORS: Record<string, (state: WorkspaceState) => string> = {
  'version-control': (state) => state.versionControl.subView,
  'workspace-settings': (state) => state.workspaceSettings.subView,
  'container-management': (state) => state.containerManagement.subView,
};

const getNavigationTarget = (
  itemId: string,
  subItem?: string | NavigationSubItem,
) => {
  const subItemId = typeof subItem === 'object' ? subItem.id : subItem;
  const targetFeature = typeof subItem === 'object'
    ? subItem.targetFeature ?? itemId
    : itemId;
  const targetSubView = typeof subItem === 'object'
    ? subItem.targetSubView ?? subItemId
    : subItemId;

  return { targetFeature, targetSubView };
};

export const isWorkspaceSubItemActive = (
  state: WorkspaceState,
  itemId: string,
  subItem: string | NavigationSubItem,
): boolean => {
  const { targetFeature, targetSubView } = getNavigationTarget(itemId, subItem);

  if (state.currentFeature !== targetFeature) {
    return false;
  }

  const selector = SUB_VIEW_SELECTORS[targetFeature]
    ?? (AGENT_NAVIGATION_IDS.includes(targetFeature) ? (state: WorkspaceState) => state.agentToolSettings.subView : undefined);

  return selector ? selector(state) === targetSubView : targetSubView === '';
};

export const isWorkspaceNavigationItemActive = (
  state: WorkspaceState,
  item: NavigationConfig,
): boolean => {
  if (state.currentFeature === item.id) {
    if (!item.hasSubMenu || !item.subItems?.length) {
      return true;
    }

    const selector = SUB_VIEW_SELECTORS[item.id]
      ?? (AGENT_NAVIGATION_IDS.includes(item.id) ? (state: WorkspaceState) => state.agentToolSettings.subView : undefined);

    if (!selector) {
      return true;
    }

    const activeSubView = selector(state);
    return item.subItems.some((subItem) => {
      const { targetFeature, targetSubView } = getNavigationTarget(item.id, subItem);
      return targetFeature === item.id && targetSubView === activeSubView;
    });
  }
  return item.subItems?.some((subItem) => isWorkspaceSubItemActive(state, item.id, subItem)) === true;
};

export const buildWorkspaceNavigationPath = (
  itemId: string,
  subItem: string | NavigationSubItem | undefined,
  workspaceId: string,
): string => {
  const { targetFeature, targetSubView } = getNavigationTarget(itemId, subItem);

  if (targetFeature === 'ai-chat-home') {
    return ROUTES.workspace.home(workspaceId);
  }

  if (targetFeature === 'file-management') {
    return ROUTES.workspace.files(workspaceId);
  }

  if (targetFeature === 'version-control') {
    return ROUTES.workspace.versionControl(workspaceId, targetSubView);
  }

  if (targetFeature === 'workspace-settings') {
    return ROUTES.workspace.settings(workspaceId, targetSubView);
  }

  if (targetFeature === 'container-management') {
    return ROUTES.workspace.containers(workspaceId, targetSubView);
  }

  if (targetFeature === 'workspace-automation') {
    return ROUTES.workspace.automation(workspaceId);
  }

  if (targetFeature === 'canvas') {
    return ROUTES.workspace.canvas(workspaceId);
  }

  if (targetFeature === 'browser') {
    return ROUTES.workspace.browser(workspaceId);
  }

  return ROUTES.workspace.agentTool(workspaceId, targetFeature, targetSubView);
};
