import { workspaceFeatureSettingsReducer } from './state/workspaceFeatureSettingsReducer';
import { workspaceFileManagementReducer } from './state/workspaceFileManagementReducer';
import { workspaceLayoutReducer } from './state/workspaceLayoutReducer';
import { workspaceNavigationReducer } from './state/workspaceNavigationReducer';
import { workspaceVersionControlReducer } from './state/workspaceVersionControlReducer';
import type { WorkspaceAction, WorkspaceState } from './workspaceStateTypes';

type WorkspaceStateReducer = (
  state: WorkspaceState,
  action: WorkspaceAction,
) => WorkspaceState;

const workspaceReducerByActionType: Record<WorkspaceAction['type'], WorkspaceStateReducer> = {
  SET_CURRENT_FEATURE: workspaceNavigationReducer,
  TOGGLE_CHAT_EXPANDED: workspaceLayoutReducer,
  TOGGLE_FILE_MANAGEMENT_EDITOR_EXPANDED: workspaceLayoutReducer,
  SET_COMPANION_ACTIVE_TAB: workspaceLayoutReducer,
  SET_COMPANION_TERMINAL_PLACEMENT: workspaceLayoutReducer,
  SET_CHAT_EXPANDED: workspaceLayoutReducer,
  SET_FILE_MANAGEMENT_EDITOR_EXPANDED: workspaceLayoutReducer,
  TOGGLE_MAIN_CONTENT_EXPANDED: workspaceLayoutReducer,
  SET_MAIN_CONTENT_EXPANDED: workspaceLayoutReducer,
  TOGGLE_NAVIGATION_ITEM: workspaceNavigationReducer,
  ENSURE_NAVIGATION_ITEM_EXPANDED: workspaceNavigationReducer,
  SET_FILE_TREE_SHOW_HIDDEN_ENTRIES: workspaceLayoutReducer,
  SET_VERSION_CONTROL_SUB_VIEW: workspaceVersionControlReducer,
  SET_SELECTED_GIT_CONTEXT: workspaceVersionControlReducer,
  SET_WORKSPACE_SETTINGS_SUB_VIEW: workspaceFeatureSettingsReducer,
  SET_CONTAINER_MANAGEMENT_SUB_VIEW: workspaceFeatureSettingsReducer,
  SET_AGENT_TOOL_SUB_VIEW: workspaceFeatureSettingsReducer,
  OPEN_FILE_TAB: workspaceFileManagementReducer,
  CLOSE_FILE_TAB: workspaceFileManagementReducer,
  CLOSE_ALL_TABS: workspaceFileManagementReducer,
  CLEAR_WORKSPACE_FILE_STATE: workspaceFileManagementReducer,
  REORDER_FILE_TABS: workspaceFileManagementReducer,
  SET_ACTIVE_TAB: workspaceFileManagementReducer,
  UPDATE_TAB_CONTENT: workspaceFileManagementReducer,
  SET_TAB_MODIFIED: workspaceFileManagementReducer,
  SET_ORIGINAL_CONTENT: workspaceFileManagementReducer,
  SET_FILE_VERSION_ID: workspaceFileManagementReducer,
  REMAP_FILE_TABS: workspaceFileManagementReducer,
  TOGGLE_MERMAID_PREVIEW: workspaceFileManagementReducer,
  TOGGLE_MARKDOWN_PREVIEW: workspaceFileManagementReducer,
  SAVE_WORKSPACE_TABS: workspaceFileManagementReducer,
  RESTORE_WORKSPACE_TABS: workspaceFileManagementReducer,
  RESTORE_LAYOUT_PREFERENCES: workspaceLayoutReducer,
};

export const workspaceReducer = (
  state: WorkspaceState,
  action: WorkspaceAction,
): WorkspaceState => {
  const reducer = workspaceReducerByActionType[action.type];
  return reducer ? reducer(state, action) : state;
};
