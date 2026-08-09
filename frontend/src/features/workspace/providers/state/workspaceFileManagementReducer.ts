import type {
  WorkspaceAction,
  WorkspaceState,
  WorkspaceTabState,
} from '../workspaceStateTypes';

const getTabState = (state: WorkspaceState): WorkspaceTabState => ({
  openTabs: state.fileManagement.openTabs,
  activeTabId: state.fileManagement.activeTabId,
  modifiedTabs: state.fileManagement.modifiedTabs,
  originalContents: state.fileManagement.originalContents,
  revisions: state.fileManagement.revisions ?? {},
});

const getWorkspaceTabsCacheKey = (contextId?: string | null): string =>
  contextId ?? 'primary';

const updateTabState = (
  state: WorkspaceState,
  updater: (tabState: WorkspaceTabState) => WorkspaceTabState,
): WorkspaceState => {
  const nextTabState = updater(getTabState(state));

  return {
    ...state,
    fileManagement: {
      ...state.fileManagement,
      ...nextTabState,
    },
  };
};

export const workspaceFileManagementReducer = (
  state: WorkspaceState,
  action: WorkspaceAction,
): WorkspaceState => {
  switch (action.type) {
    case 'OPEN_FILE_TAB':
      return updateTabState(state, (tabState) => {
        const existingTab = tabState.openTabs.find(tab => tab.id === action.payload.id);
        if (existingTab) {
          return {
            ...tabState,
            activeTabId: action.payload.id,
            openTabs: action.payload.content !== existingTab.content
              ? tabState.openTabs.map(tab =>
                  tab.id === action.payload.id ? { ...tab, content: action.payload.content } : tab)
              : tabState.openTabs,
          };
        }

        return {
          ...tabState,
          openTabs: [...tabState.openTabs, action.payload],
          activeTabId: action.payload.id,
        };
      });

    case 'CLOSE_FILE_TAB':
      return updateTabState(state, (tabState) => {
        const updatedTabs = tabState.openTabs.filter(tab => tab.id !== action.payload.tabId);
        const newActiveTabId = tabState.activeTabId === action.payload.tabId
          ? (updatedTabs.length > 0 ? updatedTabs[updatedTabs.length - 1].id : null)
          : tabState.activeTabId;
        const { [action.payload.tabId]: _, ...remainingOriginalContents } = tabState.originalContents;
        const { [action.payload.tabId]: _revision, ...remainingVersionIds } = tabState.revisions;

        return {
          ...tabState,
          openTabs: updatedTabs,
          activeTabId: newActiveTabId,
          modifiedTabs: tabState.modifiedTabs.filter(id => id !== action.payload.tabId),
          originalContents: remainingOriginalContents,
          revisions: remainingVersionIds,
        };
      });

    case 'SET_ACTIVE_TAB':
      return updateTabState(state, (tabState) => ({
        ...tabState,
        activeTabId: action.payload.tabId,
      }));

    case 'CLOSE_ALL_TABS':
      return updateTabState(state, () => ({
        openTabs: [],
        activeTabId: null,
        modifiedTabs: [],
        originalContents: {},
        revisions: {},
      }));

    case 'CLEAR_WORKSPACE_FILE_STATE': {
      const { [action.payload.workspaceId]: _, ...remainingWorkspaceTabsCache } =
        state.workspaceTabsCache;
      return {
        ...state,
        fileManagement: {
          ...state.fileManagement,
          selectedFile: null,
          openTabs: [],
          activeTabId: null,
          modifiedTabs: [],
          originalContents: {},
          revisions: {},
          mermaidCanvasMode: {},
          markdownCanvasMode: {},
        },
        workspaceTabsCache: remainingWorkspaceTabsCache,
      };
    }

    case 'REORDER_FILE_TABS':
      return updateTabState(state, (tabState) => {
        const tabsById = new Map(tabState.openTabs.map(tab => [tab.id, tab]));
        const nextTabIds = new Set(action.payload.tabIds);
        const reorderedTabs = action.payload.tabIds
          .map(tabId => tabsById.get(tabId))
          .filter((tab): tab is typeof tabState.openTabs[number] => Boolean(tab));
        const remainingTabs = tabState.openTabs.filter(tab => !nextTabIds.has(tab.id));

        return {
          ...tabState,
          openTabs: [...reorderedTabs, ...remainingTabs],
        };
      });

    case 'UPDATE_TAB_CONTENT':
      return updateTabState(state, (tabState) => ({
        ...tabState,
        openTabs: tabState.openTabs.map(tab =>
          tab.id === action.payload.tabId
            ? { ...tab, content: action.payload.content }
            : tab
        ),
      }));

    case 'SET_TAB_MODIFIED': {
      const { tabId, isModified } = action.payload;
      return updateTabState(state, (tabState) => ({
        ...tabState,
        modifiedTabs: isModified
          ? tabState.modifiedTabs.includes(tabId)
            ? tabState.modifiedTabs
            : [...tabState.modifiedTabs, tabId]
          : tabState.modifiedTabs.filter(id => id !== tabId),
      }));
    }

    case 'SET_ORIGINAL_CONTENT':
      return updateTabState(state, (tabState) => ({
        ...tabState,
        originalContents: {
          ...tabState.originalContents,
          [action.payload.tabId]: action.payload.content,
        },
      }));

    case 'SET_FILE_VERSION_ID':
      return updateTabState(state, (tabState) => ({
        ...tabState,
        revisions: {
          ...tabState.revisions,
          [action.payload.tabId]: action.payload.revision,
        },
      }));

    case 'REMAP_FILE_TABS': {
      const { sourcePath, targetPath } = action.payload;
      const isAffected = (path: string) => (
        path === sourcePath || path.startsWith(`${sourcePath}/`)
      );
      const remapPath = (path: string) => (
        path === sourcePath
          ? targetPath
          : `${targetPath}${path.slice(sourcePath.length)}`
      );
      const remapKeyedValues = <T,>(values: Record<string, T>): Record<string, T> => (
        Object.entries(values).reduce<Record<string, T>>((next, [path, value]) => {
          next[isAffected(path) ? remapPath(path) : path] = value;
          return next;
        }, {})
      );

      return updateTabState(state, (tabState) => ({
        ...tabState,
        openTabs: tabState.openTabs.map((tab) => {
          if (!isAffected(tab.path)) return tab;
          const nextPath = remapPath(tab.path);
          return {
            ...tab,
            id: nextPath,
            path: nextPath,
            name: nextPath.split('/').pop() || nextPath,
          };
        }),
        activeTabId: tabState.activeTabId && isAffected(tabState.activeTabId)
          ? remapPath(tabState.activeTabId)
          : tabState.activeTabId,
        modifiedTabs: tabState.modifiedTabs.map((path) => (
          isAffected(path) ? remapPath(path) : path
        )),
        originalContents: remapKeyedValues(tabState.originalContents),
        revisions: remapKeyedValues(tabState.revisions),
      }));
    }

    case 'TOGGLE_MERMAID_PREVIEW':
      return {
        ...state,
        fileManagement: {
          ...state.fileManagement,
          mermaidCanvasMode: {
            ...state.fileManagement.mermaidCanvasMode,
            [action.payload]: !state.fileManagement.mermaidCanvasMode[action.payload],
          },
        },
      };

    case 'TOGGLE_MARKDOWN_PREVIEW':
      return {
        ...state,
        fileManagement: {
          ...state.fileManagement,
          markdownCanvasMode: {
            ...state.fileManagement.markdownCanvasMode,
            [action.payload]: !state.fileManagement.markdownCanvasMode[action.payload],
          },
        },
      };

    case 'SAVE_WORKSPACE_TABS': {
      const { workspaceId, contextId } = action.payload;
      const cacheKey = getWorkspaceTabsCacheKey(contextId);
      return {
        ...state,
        workspaceTabsCache: {
          ...state.workspaceTabsCache,
          [workspaceId]: {
            ...state.workspaceTabsCache[workspaceId],
            [cacheKey]: getTabState(state),
          },
        },
      };
    }

    case 'RESTORE_WORKSPACE_TABS': {
      const { workspaceId, tabsState, contextId } = action.payload;
      const cacheKey = getWorkspaceTabsCacheKey(contextId);
      const tabsToRestore = tabsState || state.workspaceTabsCache[workspaceId]?.[cacheKey];

      if (!tabsToRestore) {
        return updateTabState(state, () => ({
          openTabs: [],
          activeTabId: null,
          modifiedTabs: [],
          originalContents: {},
          revisions: {},
        }));
      }

      const newCache = tabsState
        ? {
            ...state.workspaceTabsCache,
            [workspaceId]: {
              ...state.workspaceTabsCache[workspaceId],
              [cacheKey]: tabsState,
            },
          }
        : state.workspaceTabsCache;

      return updateTabState({
        ...state,
        workspaceTabsCache: newCache,
      }, () => ({
        openTabs: tabsToRestore.openTabs,
        activeTabId: tabsToRestore.activeTabId,
        modifiedTabs: tabsToRestore.modifiedTabs,
        originalContents: tabsToRestore.originalContents,
        revisions: tabsToRestore.revisions ?? {},
      }));
    }

    default:
      return state;
  }
};
