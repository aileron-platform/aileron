import type { WorkspaceAction, WorkspaceState } from '../workspaceStateTypes';

export const workspaceNavigationReducer = (
  state: WorkspaceState,
  action: WorkspaceAction,
): WorkspaceState => {
  switch (action.type) {
    case 'SET_CURRENT_FEATURE':
      return {
        ...state,
        currentFeature: action.payload,
        fileManagementEditorExpanded: action.payload === 'file-management'
          ? state.fileManagementEditorExpanded
          : false,
        // Leaving a feature exits the full-screen main-content mode.
        mainContentExpanded: false,
      };

    case 'TOGGLE_NAVIGATION_ITEM': {
      const itemId = action.payload;
      const currentExpanded = state.expandedNavigationItems;
      const isExpanded = currentExpanded.includes(itemId);

      return {
        ...state,
        expandedNavigationItems: isExpanded
          ? currentExpanded.filter(id => id !== itemId)
          : [...currentExpanded, itemId],
      };
    }

    case 'ENSURE_NAVIGATION_ITEM_EXPANDED': {
      const targetItemId = action.payload;
      const currentExpandedItems = state.expandedNavigationItems;

      if (currentExpandedItems.includes(targetItemId)) {
        return state;
      }

      return {
        ...state,
        expandedNavigationItems: [...currentExpandedItems, targetItemId],
      };
    }

    default:
      return state;
  }
};
