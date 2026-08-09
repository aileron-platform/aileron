import type { WorkspaceAction, WorkspaceState } from '../workspaceStateTypes';

export const workspaceVersionControlReducer = (
  state: WorkspaceState,
  action: WorkspaceAction,
): WorkspaceState => {
  switch (action.type) {
    case 'SET_VERSION_CONTROL_SUB_VIEW':
      return {
        ...state,
        versionControl: {
          ...state.versionControl,
          subView: action.payload,
        },
      };

    case 'SET_SELECTED_GIT_CONTEXT':
      return {
        ...state,
        versionControl: {
          ...state.versionControl,
          selectedGitContextId: action.payload,
        },
      };

    default:
      return state;
  }
};
