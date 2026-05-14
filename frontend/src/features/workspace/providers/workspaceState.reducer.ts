/**
 * WorkspaceProvider Reducer
 */

import type { WorkspaceState, WorkspaceAction, WorkspaceTabScope, WorkspaceTabState } from './workspaceState.types';
import type { FileNode } from '../features/file-management/types';
import { getLayoutModeForFeature } from './workspaceState.constants';

const getTabStateForScope = (state: WorkspaceState, scope: WorkspaceTabScope): WorkspaceTabState => {
  if (scope === 'openspec') {
    return {
      openTabs: state.openspec.openTabs,
      activeTabId: state.openspec.activeTabId,
      modifiedTabs: state.openspec.modifiedTabs,
      originalContents: state.openspec.originalContents,
    };
  }

  return {
    openTabs: state.fileManagement.openTabs,
    activeTabId: state.fileManagement.activeTabId,
    modifiedTabs: state.fileManagement.modifiedTabs,
    originalContents: state.fileManagement.originalContents,
  };
};

const getWorkspaceTabsCacheScopeKey = (
  scope: WorkspaceTabScope,
  contextId?: string | null,
): string => {
  if (scope !== 'file-management') {
    return scope;
  }

  return `${scope}:${contextId ?? 'primary'}`;
};

const updateTabStateForScope = (
  state: WorkspaceState,
  scope: WorkspaceTabScope,
  updater: (tabState: WorkspaceTabState) => WorkspaceTabState,
): WorkspaceState => {
  const nextTabState = updater(getTabStateForScope(state, scope));

  if (scope === 'openspec') {
    return {
      ...state,
      openspec: {
        ...state.openspec,
        ...nextTabState,
      },
    };
  }

  return {
    ...state,
    fileManagement: {
      ...state.fileManagement,
      ...nextTabState,
    },
  };
};

// Reducer 函數
export const workspaceReducer = (state: WorkspaceState, action: WorkspaceAction): WorkspaceState => {
  switch (action.type) {
    case 'SET_CURRENT_FEATURE':
      return {
        ...state,
        currentFeature: action.payload,
        layoutMode: getLayoutModeForFeature(action.payload),
        fileManagementEditorExpanded: action.payload === 'file-management'
          ? state.fileManagementEditorExpanded
          : false,
      };

    case 'SET_LAYOUT_MODE':
      return {
        ...state,
        layoutMode: action.payload,
      };

    case 'TOGGLE_SIDEBAR':
      return {
        ...state,
        sidebarCollapsed: !state.sidebarCollapsed,
      };

    case 'TOGGLE_SECOND_COLUMN':
      return {
        ...state,
        secondColumnCollapsed: !state.secondColumnCollapsed,
      };

    case 'TOGGLE_RIGHT_CHAT':
      return {
        ...state,
        rightChatCollapsed: !state.rightChatCollapsed,
      };

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

    case 'SET_SIDEBAR_COLLAPSED':
      return {
        ...state,
        sidebarCollapsed: action.payload,
      };

    case 'SET_SECOND_COLUMN_COLLAPSED':
      return {
        ...state,
        secondColumnCollapsed: action.payload,
      };

    case 'SET_RIGHT_CHAT_COLLAPSED':
      return {
        ...state,
        rightChatCollapsed: action.payload,
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

    case 'TOGGLE_NAVIGATION_ITEM':
      const itemId = action.payload;
      const currentExpanded = state.expandedNavigationItems;
      const isExpanded = currentExpanded.includes(itemId);

      return {
        ...state,
        expandedNavigationItems: isExpanded
          ? currentExpanded.filter(id => id !== itemId)
          : [...currentExpanded, itemId],
      };

    case 'ENSURE_NAVIGATION_ITEM_EXPANDED':
      const targetItemId = action.payload;
      const currentExpandedItems = state.expandedNavigationItems;
      const isAlreadyExpanded = currentExpandedItems.includes(targetItemId);

      // 如果已經展開，不做任何改變
      if (isAlreadyExpanded) {
        return state;
      }

      // 如果未展開，添加到展開列表
      return {
        ...state,
        expandedNavigationItems: [...currentExpandedItems, targetItemId],
      };

    case 'SET_SIDEBAR_WIDTH':
      return {
        ...state,
        sidebarWidth: Math.max(200, Math.min(500, action.payload)),
      };

    case 'SET_SECOND_COLUMN_WIDTH':
      return {
        ...state,
        secondColumnWidth: Math.max(250, Math.min(600, action.payload)),
      };

    case 'SET_RIGHT_CHAT_WIDTH':
      return {
        ...state,
        rightChatWidth: Math.max(360, Math.min(800, action.payload)),
      };

    case 'SET_FILE_TREE_SHOW_HIDDEN_ENTRIES':
      return {
        ...state,
        fileTreeShowHiddenEntries: action.payload,
      };

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

    case 'SET_OPENSPEC_SUB_VIEW':
      return {
        ...state,
        openspec: {
          ...state.openspec,
          subView: action.payload,
        },
      };

    case 'SET_OPENSPEC_SELECTED_PATH':
      if (state.openspec.selectedPath === action.payload) {
        return state;
      }
      return {
        ...state,
        openspec: {
          ...state.openspec,
          selectedPath: action.payload,
        },
      };

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

    case 'SET_CLAUDE_CODE_SUB_VIEW':
      return {
        ...state,
        claudeCodeSettings: {
          ...state.claudeCodeSettings,
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

    case 'SET_CANVAS_SUB_VIEW':
      return {
        ...state,
        canvas: {
          ...state.canvas,
          subView: action.payload,
        },
      };

    case 'SET_CANVAS_SESSION_RESULT':
      return {
        ...state,
        canvas: {
          ...state.canvas,
          markdownContent: action.payload.markdownContent,
          rawContent: action.payload.rawContent,
        },
      };

    case 'SET_CANVAS_MARKDOWN':
      return {
        ...state,
        canvas: {
          ...state.canvas,
          markdownContent: action.payload,
        },
      };

    case 'SET_CANVAS_RAW_CONTENT':
      return {
        ...state,
        canvas: {
          ...state.canvas,
          rawContent: action.payload,
        },
      };

    case 'OPEN_FILE_TAB': {
      const scope = action.payload.scope ?? 'file-management';
      return updateTabStateForScope(state, scope, (tabState) => {
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

        const { scope: _scope, ...nextTab } = action.payload;
        return {
          ...tabState,
          openTabs: [...tabState.openTabs, nextTab],
          activeTabId: action.payload.id,
        };
      });
    }

    case 'CLOSE_FILE_TAB': {
      const scope = action.payload.scope ?? 'file-management';
      return updateTabStateForScope(state, scope, (tabState) => {
        const updatedTabs = tabState.openTabs.filter(tab => tab.id !== action.payload.tabId);
        const newActiveTabId = tabState.activeTabId === action.payload.tabId
          ? (updatedTabs.length > 0 ? updatedTabs[updatedTabs.length - 1].id : null)
          : tabState.activeTabId;
        const { [action.payload.tabId]: _, ...remainingOriginalContents } = tabState.originalContents;

        return {
          ...tabState,
          openTabs: updatedTabs,
          activeTabId: newActiveTabId,
          modifiedTabs: tabState.modifiedTabs.filter(id => id !== action.payload.tabId),
          originalContents: remainingOriginalContents,
        };
      });
    }

    case 'SET_ACTIVE_TAB': {
      const scope = action.payload.scope ?? 'file-management';
      return updateTabStateForScope(state, scope, (tabState) => ({
        ...tabState,
        activeTabId: action.payload.tabId,
      }));
    }

    case 'CLOSE_ALL_TABS': {
      const scope = action.payload?.scope ?? 'file-management';
      return updateTabStateForScope(state, scope, () => ({
        openTabs: [],
        activeTabId: null,
        modifiedTabs: [],
        originalContents: {},
      }));
    }

    case 'REORDER_FILE_TABS': {
      const scope = action.payload.scope ?? 'file-management';
      return updateTabStateForScope(state, scope, (tabState) => {
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
    }

    case 'UPDATE_TAB_CONTENT': {
      const scope = action.payload.scope ?? 'file-management';
      return updateTabStateForScope(state, scope, (tabState) => ({
        ...tabState,
        openTabs: tabState.openTabs.map(tab =>
          tab.id === action.payload.tabId
            ? { ...tab, content: action.payload.content }
            : tab
        ),
      }));
    }

    case 'SET_TAB_MODIFIED': {
      const scope = action.payload.scope ?? 'file-management';
      const { tabId, isModified } = action.payload;
      return updateTabStateForScope(state, scope, (tabState) => ({
        ...tabState,
        modifiedTabs: isModified
          ? tabState.modifiedTabs.includes(tabId)
            ? tabState.modifiedTabs
            : [...tabState.modifiedTabs, tabId]
          : tabState.modifiedTabs.filter(id => id !== tabId),
      }));
    }

    case 'SET_ORIGINAL_CONTENT': {
      const scope = action.payload.scope ?? 'file-management';
      return updateTabStateForScope(state, scope, (tabState) => ({
        ...tabState,
        originalContents: {
          ...tabState.originalContents,
          [action.payload.tabId]: action.payload.content,
        },
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

    // 檔案樹相關處理
    case 'SET_FILE_TREE_NODES':
      // 保留現有的展開節點，並合併新節點中標記為展開的節點
      const mergeExpandedNodes = (nodes: FileNode[], existingExpanded: Set<string>): Set<string> => {
        const expandedNodes = new Set<string>(existingExpanded);

        // 收集所有存在的目錄路徑
        const existingDirs = new Set<string>();
        const traverse = (nodeList: FileNode[]) => {
          nodeList.forEach(node => {
            if (node.type === 'directory') {
              existingDirs.add(node.path);
              // 如果節點本身標記為展開，也加入
              if (node.isExpanded) {
                expandedNodes.add(node.path);
              }
            }
            if (node.children) {
              traverse(node.children);
            }
          });
        };
        traverse(nodes);

        // 移除不再存在的目錄
        const validExpandedNodes = new Set<string>();
        expandedNodes.forEach(path => {
          if (existingDirs.has(path)) {
            validExpandedNodes.add(path);
          }
        });

        return validExpandedNodes;
      };

      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          nodes: action.payload,
          expandedNodes: mergeExpandedNodes(action.payload, state.fileTreeState.expandedNodes),
        },
      };

    case 'SET_FILE_TREE_LOADING':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          isLoading: action.payload,
        },
      };

    case 'SET_FILE_TREE_ERROR':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          error: action.payload,
        },
      };

    case 'SET_PENDING_FILE_ACTION':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          pendingAction: action.payload,
        },
      };

    case 'SELECT_FILE':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          selectedFile: action.payload,
        },
      };

    case 'SELECT_FILE_WITH_MODIFIER': {
      const { filePath, modifier } = action.payload;

      switch (modifier) {
        case 'none':
          // 清除其他選擇，只選擇當前檔案
          return {
            ...state,
            fileTreeState: {
              ...state.fileTreeState,
              selectedFile: filePath,
              selectedFiles: new Set([filePath]),
              lastSelectedFile: filePath,
            },
          };

        case 'ctrl':
          // 切換選擇狀態
          const ctrlSelectedFiles = new Set(state.fileTreeState.selectedFiles);
          if (ctrlSelectedFiles.has(filePath)) {
            ctrlSelectedFiles.delete(filePath);
          } else {
            ctrlSelectedFiles.add(filePath);
          }
          return {
            ...state,
            fileTreeState: {
              ...state.fileTreeState,
              selectedFile: filePath,
              selectedFiles: ctrlSelectedFiles,
              lastSelectedFile: filePath,
            },
          };

        case 'shift':
          // Shift 範圍選擇會在 WorkspaceProvider 中處理
          // 這裡只是更新 selectedFile
          return {
            ...state,
            fileTreeState: {
              ...state.fileTreeState,
              selectedFile: filePath,
            },
          };

        default:
          return state;
      }
    }

    case 'SELECT_RANGE': {
      const { fromPath, toPath } = action.payload;
      // 範圍選擇的檔案列表會在 WorkspaceProvider 中計算
      // 這裡只是佔位，實際邏輯在 provider 中
      return state;
    }

    case 'SET_LAST_SELECTED_FILE':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          lastSelectedFile: action.payload,
        },
      };

    case 'TOGGLE_MULTI_SELECT':
      const toggledSelectedFiles = new Set(state.fileTreeState.selectedFiles);
      if (toggledSelectedFiles.has(action.payload)) {
        toggledSelectedFiles.delete(action.payload);
      } else {
        toggledSelectedFiles.add(action.payload);
      }
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          selectedFiles: toggledSelectedFiles,
        },
      };

    case 'CLEAR_SELECTION':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          selectedFiles: new Set<string>(),
          lastSelectedFile: null,
        },
      };

    case 'SELECT_ALL_FILES':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          selectedFiles: new Set(action.payload),
        },
      };

    case 'EXPAND_NODE':
      const newExpandedNodes = new Set(state.fileTreeState.expandedNodes);
      newExpandedNodes.add(action.payload);
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          expandedNodes: newExpandedNodes,
        },
      };

    case 'COLLAPSE_NODE':
      const updatedExpandedNodes = new Set(state.fileTreeState.expandedNodes);
      updatedExpandedNodes.delete(action.payload);
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          expandedNodes: updatedExpandedNodes,
        },
      };

    case 'SET_NODE_LOADING': {
      const updateNodeLoading = (nodes: FileNode[]): FileNode[] => {
        return nodes.map(node => {
          if (node.path === action.payload.path) {
            return { ...node, isLoading: action.payload.isLoading };
          }
          if (node.children) {
            return { ...node, children: updateNodeLoading(node.children) };
          }
          return node;
        });
      };

      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          nodes: updateNodeLoading(state.fileTreeState.nodes),
        },
      };
    }

    case 'SET_NODE_CHILDREN': {
      const updateNodeChildren = (nodes: FileNode[]): FileNode[] => {
        return nodes.map(node => {
          if (node.path === action.payload.path) {
            return {
              ...node,
              children: action.payload.children,
              isLoading: false,
              isExpanded: true,
            };
          }
          if (node.children) {
            return { ...node, children: updateNodeChildren(node.children) };
          }
          return node;
        });
      };

      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          nodes: updateNodeChildren(state.fileTreeState.nodes),
        },
      };
    }

    case 'SET_DRAGGED_NODE':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          draggedNode: action.payload,
        },
      };

    case 'SET_DROP_TARGET':
      return {
        ...state,
        fileTreeState: {
          ...state.fileTreeState,
          dropTarget: action.payload,
        },
      };

    case 'SAVE_WORKSPACE_TABS': {
      const { workspaceId, scope, contextId } = action.payload;
      const tabState = getTabStateForScope(state, scope);
      const scopeKey = getWorkspaceTabsCacheScopeKey(scope, contextId);
      return {
        ...state,
        workspaceTabsCache: {
          ...state.workspaceTabsCache,
          [workspaceId]: {
            ...state.workspaceTabsCache[workspaceId],
            [scopeKey]: tabState,
          },
        },
      };
    }

    case 'RESTORE_WORKSPACE_TABS': {
      const { workspaceId, tabsState, scope, contextId } = action.payload;
      const scopeKey = getWorkspaceTabsCacheScopeKey(scope, contextId);

      // 優先使用傳入的 tabsState，否則從 cache 中取
      const tabsToRestore = tabsState || state.workspaceTabsCache[workspaceId]?.[scopeKey];

      if (!tabsToRestore) {
        return updateTabStateForScope(state, scope, () => ({
          openTabs: [],
          activeTabId: null,
          modifiedTabs: [],
          originalContents: {},
        }));
      }

      // 如果有 tabsState，同時更新到 cache
      const newCache = tabsState
        ? {
            ...state.workspaceTabsCache,
            [workspaceId]: {
              ...state.workspaceTabsCache[workspaceId],
              [scopeKey]: tabsState,
            },
        }
        : state.workspaceTabsCache;

      const nextState = {
        ...state,
        workspaceTabsCache: newCache,
      };

      return updateTabStateForScope(nextState, scope, () => tabsToRestore);
    }

    case 'CLEAR_WORKSPACE_TABS_CACHE': {
      const { workspaceId, scope, contextId } = action.payload;
      if (!scope) {
        const { [workspaceId]: _, ...remainingCache } = state.workspaceTabsCache;
        return {
          ...state,
          workspaceTabsCache: remainingCache,
        };
      }

      const workspaceCache = state.workspaceTabsCache[workspaceId];
      if (!workspaceCache) {
        return state;
      }
      const scopeKey = getWorkspaceTabsCacheScopeKey(scope, contextId);
      const { [scopeKey]: _, ...remainingScopedCache } = workspaceCache;
      return {
        ...state,
        workspaceTabsCache: {
          ...state.workspaceTabsCache,
          [workspaceId]: remainingScopedCache,
        },
      };
    }

    case 'RESTORE_LAYOUT_PREFERENCES':
      return {
        ...state,
        sidebarCollapsed: action.payload.sidebarCollapsed,
        sidebarWidth: action.payload.sidebarWidth,
        secondColumnCollapsed: action.payload.secondColumnCollapsed,
        secondColumnWidth: action.payload.secondColumnWidth,
        rightChatCollapsed: action.payload.rightChatCollapsed,
        rightChatWidth: action.payload.rightChatWidth,
        expandedNavigationItems: action.payload.expandedNavigationItems,
        fileTreeShowHiddenEntries: action.payload.fileTreeShowHiddenEntries,
      };

    default:
      return state;
  }
};
