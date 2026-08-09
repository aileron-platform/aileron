/**
 * useWorkspaceRouteSync Hook
 */

import { useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import type { WorkspaceState, WorkspaceAction } from '../providers/workspaceStateTypes';
import {
  getFeatureFromPath,
  getVersionControlSubView,
  getWorkspaceSettingsSubView,
  getContainerManagementSubView,
  getAgentToolSubView,
  initialState,
} from '../providers/workspaceStateConstants';
import { AGENT_NAVIGATION_IDS } from '../features/agent-settings/agentToolConfigs';

/** Navigation ids of all agent tool features (Claude Code, OpenCode, Codex). */
const AGENT_TOOL_FEATURES = AGENT_NAVIGATION_IDS;

export const useWorkspaceRouteSync = (
  state: WorkspaceState,
  dispatch: React.Dispatch<WorkspaceAction>
) => {
  const location = useLocation();

  const getInitialState = useCallback((): WorkspaceState => {
    const currentFeature = getFeatureFromPath(location.pathname);

    return {
      ...initialState,
      currentFeature,
      versionControl: {
        ...initialState.versionControl,
        subView: getVersionControlSubView(location.pathname),
      },
      workspaceSettings: {
        ...initialState.workspaceSettings,
        subView: getWorkspaceSettingsSubView(location.pathname),
      },
      containerManagement: {
        ...initialState.containerManagement,
        subView: getContainerManagementSubView(location.pathname),
      },
      agentToolSettings: {
        ...initialState.agentToolSettings,
        subView: (AGENT_TOOL_FEATURES as readonly string[]).includes(currentFeature)
          ? getAgentToolSubView(location.pathname)
          : '',
      },
    };
  }, [location.pathname]);

  useEffect(() => {
    const currentFeature = getFeatureFromPath(location.pathname);
    if (currentFeature !== state.currentFeature) {
      dispatch({ type: 'SET_CURRENT_FEATURE', payload: currentFeature });
    }

    if (currentFeature === 'version-control') {
      const subView = getVersionControlSubView(location.pathname);
      if (subView !== state.versionControl.subView) {
        dispatch({ type: 'SET_VERSION_CONTROL_SUB_VIEW', payload: subView });
      }
    } else if (currentFeature === 'workspace-settings') {
      const subView = getWorkspaceSettingsSubView(location.pathname);
      if (subView !== state.workspaceSettings.subView) {
        dispatch({ type: 'SET_WORKSPACE_SETTINGS_SUB_VIEW', payload: subView });
      }
    } else if (currentFeature === 'container-management') {
      const subView = getContainerManagementSubView(location.pathname);
      if (subView !== state.containerManagement.subView) {
        dispatch({ type: 'SET_CONTAINER_MANAGEMENT_SUB_VIEW', payload: subView });
      }
    } else if ((AGENT_TOOL_FEATURES as readonly string[]).includes(currentFeature)) {
      const subView = getAgentToolSubView(location.pathname);
      if (subView !== state.agentToolSettings.subView) {
        dispatch({ type: 'SET_AGENT_TOOL_SUB_VIEW', payload: subView });
      }
    }
  }, [location.pathname, state, dispatch]);

  return { getInitialState };
};
