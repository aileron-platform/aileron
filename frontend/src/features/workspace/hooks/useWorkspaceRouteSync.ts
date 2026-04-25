/**
 * useWorkspaceRouteSync Hook
 * 處理路由與狀態的同步
 */

import { useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import type { WorkspaceState, WorkspaceAction } from '../providers/workspaceState.types';
import {
  getFeatureFromPath,
  getVersionControlSubView,
  getOpenSpecSubView,
  getWorkspaceSettingsSubView,
  getContainerManagementSubView,
  getClaudeCodeSubView,
  getAgentToolSubView,
  getCanvasSubView,
  getLayoutModeForFeature,
  initialState,
} from '../providers/workspaceState.constants';

/** gemini / opencode / codex 共用的 Agent 工具 feature */
const AGENT_TOOL_FEATURES = ['gemini', 'opencode', 'codex'] as const;

export const useWorkspaceRouteSync = (
  state: WorkspaceState,
  dispatch: React.Dispatch<WorkspaceAction>
) => {
  const location = useLocation();

  // 根據當前路由初始化狀態
  const getInitialState = useCallback((): WorkspaceState => {
    const currentFeature = getFeatureFromPath(location.pathname);

    return {
      ...initialState,
      currentFeature,
      layoutMode: getLayoutModeForFeature(currentFeature),
      versionControl: {
        ...initialState.versionControl,
        subView: getVersionControlSubView(location.pathname),
      },
      openspec: {
        ...initialState.openspec,
        subView: getOpenSpecSubView(location.pathname),
      },
      workspaceSettings: {
        ...initialState.workspaceSettings,
        subView: getWorkspaceSettingsSubView(location.pathname),
      },
      containerManagement: {
        ...initialState.containerManagement,
        subView: getContainerManagementSubView(location.pathname),
      },
      claudeCodeSettings: {
        ...initialState.claudeCodeSettings,
        subView: getClaudeCodeSubView(location.pathname),
      },
      agentToolSettings: {
        ...initialState.agentToolSettings,
        subView: (AGENT_TOOL_FEATURES as readonly string[]).includes(currentFeature)
          ? getAgentToolSubView(location.pathname)
          : '',
      },
      canvas: {
        ...initialState.canvas,
        subView: getCanvasSubView(location.pathname),
      },
    };
  }, [location.pathname]);

  // 監聽路由變化並同步狀態
  useEffect(() => {
    const currentFeature = getFeatureFromPath(location.pathname);
    if (currentFeature !== state.currentFeature) {
      dispatch({ type: 'SET_CURRENT_FEATURE', payload: currentFeature });
    }

    // 同步子視圖狀態
    if (currentFeature === 'version-control') {
      const subView = getVersionControlSubView(location.pathname);
      if (subView !== state.versionControl.subView) {
        dispatch({ type: 'SET_VERSION_CONTROL_SUB_VIEW', payload: subView });
      }
    } else if (currentFeature === 'openspec') {
      const subView = getOpenSpecSubView(location.pathname);
      if (subView !== state.openspec.subView) {
        dispatch({ type: 'SET_OPENSPEC_SUB_VIEW', payload: subView });
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
    } else if (currentFeature === 'claude-code') {
      const subView = getClaudeCodeSubView(location.pathname);
      if (subView !== state.claudeCodeSettings.subView) {
        dispatch({ type: 'SET_CLAUDE_CODE_SUB_VIEW', payload: subView });
      }
    } else if ((AGENT_TOOL_FEATURES as readonly string[]).includes(currentFeature)) {
      const subView = getAgentToolSubView(location.pathname);
      if (subView !== state.agentToolSettings.subView) {
        dispatch({ type: 'SET_AGENT_TOOL_SUB_VIEW', payload: subView });
      }
    } else if (currentFeature === 'canvas') {
      const subView = getCanvasSubView(location.pathname);
      if (subView !== state.canvas.subView) {
        dispatch({ type: 'SET_CANVAS_SUB_VIEW', payload: subView });
      }
    }
  }, [location.pathname, state, dispatch]);

  return { getInitialState };
};
