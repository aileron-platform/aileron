import type { WorkspaceAction, WorkspaceState } from '../workspaceStateTypes';

export const workspaceFeatureSettingsReducer = (
  state: WorkspaceState,
  action: WorkspaceAction,
): WorkspaceState => {
  switch (action.type) {
    case 'SET_WORKSPACE_SETTINGS_SUB_VIEW':
      return {
        ...state,
        workspaceSettings: {
          ...state.workspaceSettings,
          subView: action.payload,
        },
      };

    case 'SET_CONTAINER_MANAGEMENT_SUB_VIEW':
      return {
        ...state,
        containerManagement: {
          ...state.containerManagement,
          subView: action.payload,
        },
      };

    case 'SET_AGENT_TOOL_SUB_VIEW':
      return {
        ...state,
        agentToolSettings: {
          ...state.agentToolSettings,
          subView: action.payload,
        },
      };

    default:
      return state;
  }
};
