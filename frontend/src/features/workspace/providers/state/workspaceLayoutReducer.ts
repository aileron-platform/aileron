import type { WorkspaceAction, WorkspaceState } from '../workspaceStateTypes';

export const workspaceLayoutReducer = (
  state: WorkspaceState,
  action: WorkspaceAction,
): WorkspaceState => {
  switch (action.type) {
    case 'TOGGLE_CHAT_EXPANDED':
      return {
        ...state,
        chatExpanded: !state.chatExpanded,
      };

    case 'TOGGLE_FILE_MANAGEMENT_EDITOR_EXPANDED':
      return {
        ...state,
        fileManagementEditorExpanded: !state.fileManagementEditorExpanded,
      };

    case 'TOGGLE_MAIN_CONTENT_EXPANDED':
      return {
        ...state,
        mainContentExpanded: !state.mainContentExpanded,
      };

    case 'SET_MAIN_CONTENT_EXPANDED':
      return {
        ...state,
        mainContentExpanded: action.payload,
      };

    case 'SET_COMPANION_ACTIVE_TAB':
      return {
        ...state,
        companionActiveTab: action.payload,
      };

    case 'SET_COMPANION_TERMINAL_PLACEMENT':
      return {
        ...state,
        companionTerminalPlacement: action.payload,
      };

    case 'SET_CHAT_EXPANDED':
      return {
        ...state,
        chatExpanded: action.payload,
      };

    case 'SET_FILE_MANAGEMENT_EDITOR_EXPANDED':
      return {
        ...state,
        fileManagementEditorExpanded: action.payload,
      };

    case 'SET_FILE_TREE_SHOW_HIDDEN_ENTRIES':
      return {
        ...state,
        fileTreeShowHiddenEntries: action.payload,
      };

    case 'RESTORE_LAYOUT_PREFERENCES':
      return {
        ...state,
        companionActiveTab: action.payload.companionActiveTab,
        companionTerminalPlacement: action.payload.companionTerminalPlacement,
        expandedNavigationItems: [...action.payload.expandedNavigationItems],
        fileTreeShowHiddenEntries: action.payload.fileTreeShowHiddenEntries,
      };

    default:
      return state;
  }
};
