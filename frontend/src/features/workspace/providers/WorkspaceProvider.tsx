/**
 * WorkspaceProvider - 工作區模組狀態管理（重構版）
 *
 * 提供工作區模組專用的狀態管理，包含檔案樹功能
 * 採用分層架構：Context → Hooks → Services
 */

import React, { useCallback, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react';
import type { WorkspaceContextType } from './workspaceState.types';
import { WorkspaceContext } from './WorkspaceContext';
import { workspaceReducer } from './workspaceState.reducer';
import { initialState, getFeatureFromPath, getLayoutModeForFeature, getTabScopeForFeature } from './workspaceState.constants';
import { useWorkspaceRuntime } from '../hooks/useWorkspaceRuntime';
import { useWorkspaceRouteSync } from '../hooks/useWorkspaceRouteSync';
import { MarkdownRenderer } from '../components/MarkdownRenderer';
import { loadWorkspaceTabs, saveWorkspaceTabs } from '../utils/workspaceTabsStorage';
import { loadWorkspaceLayoutPreferences, saveWorkspaceLayoutPreferences } from '../utils/workspaceLayoutStorage';
import { useWorkspaceFileTreeAdapter } from '../hooks/useWorkspaceFileTreeAdapter';
import { useAuth } from '@/features/auth/hooks/useAuth';

// 重新導出型別供外部使用
export type { WorkspaceFeature, LayoutMode, WorkspaceState, WorkspaceAction } from './workspaceState.types';

// 重新導出 useWorkspace Hook 供外部使用
export { useWorkspace, useWorkspaceOptional } from './WorkspaceContext';

// Provider 組件
interface WorkspaceProviderProps {
  children: ReactNode;
  workspaceId?: string;
}

export const WorkspaceProvider: React.FC<WorkspaceProviderProps> = ({ children, workspaceId }) => {
  // 初始化 state 與 reducer
  const computedInitialState = useMemo(() => {
    const currentFeature = getFeatureFromPath(window.location.pathname);

    return {
      ...initialState,
      currentFeature,
      layoutMode: getLayoutModeForFeature(currentFeature),
    };
  }, []);

  const [state, dispatch] = useReducer(workspaceReducer, computedInitialState);
  const stateRef = useRef(state);
  stateRef.current = state;

  const { isAuthenticated, isLoading: isAuthLoading, getAccessToken } = useAuth();

  // 使用 Workspace Runtime Hook
  const workspaceRuntime = useWorkspaceRuntime(workspaceId);

  // 使用路由同步 Hook
  useWorkspaceRouteSync(state, dispatch);

  // 使用檔案樹管理適配器，維持既有介面
  const fileTreeAdapter = useWorkspaceFileTreeAdapter({
    workspaceId: workspaceRuntime.workspaceId ?? workspaceId,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
  });

  const fileTreeActions = fileTreeAdapter.actions;

  const lastLoadedTreeIdentityRef = useRef<string | null>(null);
  const previousWorkspaceIdRef = useRef<string | null>(null);
  const hasLoadedInitialTabsRef = useRef(false);
  // 記錄最近一次已完成 layout restore 的 workspaceId。
  // 1) 作為防抖寫入的 gate：只有與當前 workspaceId 相同時才允許寫入，避免切換瞬間用舊 state 污染新 workspace key
  // 2) 作為 workspace 切換時的 "前一個 workspace" 指標，用來 flush 最後狀態
  // 這裡刻意不使用 boolean + useEffect cleanup 的寫法：React 18 StrictMode 會在掛載後立即模擬 cleanup，
  // 會在 stateRef 還是 initialState 的情況下誤覆蓋 localStorage 的已保存偏好
  const previousRestoredWorkspaceIdRef = useRef<string | null>(null);
  const { loadFileTree } = fileTreeActions;
  const accessToken = getAccessToken();
  const currentTabScope = getTabScopeForFeature(state.currentFeature);
  const getScopedTabState = useCallback((scope = currentTabScope) => {
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
  }, [
    currentTabScope,
    state.fileManagement.activeTabId,
    state.fileManagement.modifiedTabs,
    state.fileManagement.openTabs,
    state.fileManagement.originalContents,
    state.openspec.activeTabId,
    state.openspec.modifiedTabs,
    state.openspec.openTabs,
    state.openspec.originalContents,
  ]);

  // 初始化時載入當前 workspace 的 tabs
  useEffect(() => {
    const currentWorkspaceId = workspaceRuntime.workspaceId;

    if (currentWorkspaceId && !hasLoadedInitialTabsRef.current) {
      hasLoadedInitialTabsRef.current = true;

      (['file-management', 'openspec'] as const).forEach((scope) => {
        const savedTabs = loadWorkspaceTabs(currentWorkspaceId, scope);
        dispatch({
          type: 'RESTORE_WORKSPACE_TABS',
          payload: {
            workspaceId: currentWorkspaceId,
            scope,
            tabsState: savedTabs || undefined,
          }
        });
      });

      previousWorkspaceIdRef.current = currentWorkspaceId;
    }
  }, [workspaceRuntime.workspaceId]);

  // 當 workspace 切換時，儲存舊的 tabs 並載入新的 tabs
  useEffect(() => {
    const currentWorkspaceId = workspaceRuntime.workspaceId;
    const previousWorkspaceId = previousWorkspaceIdRef.current;

    // 如果 workspace 改變（且不是初始化）
    if (currentWorkspaceId && previousWorkspaceId && currentWorkspaceId !== previousWorkspaceId) {
      (['file-management', 'openspec'] as const).forEach((scope) => {
        dispatch({ type: 'SAVE_WORKSPACE_TABS', payload: { workspaceId: previousWorkspaceId, scope } });

        const savedTabs = loadWorkspaceTabs(currentWorkspaceId, scope);
        dispatch({
          type: 'RESTORE_WORKSPACE_TABS',
          payload: {
            workspaceId: currentWorkspaceId,
            scope,
            tabsState: savedTabs || undefined,
          }
        });
      });
    }

    // 更新 ref
    if (currentWorkspaceId) {
      previousWorkspaceIdRef.current = currentWorkspaceId;
    }
  }, [workspaceRuntime.workspaceId]);

  // 載入 workspace 層級的 layout 偏好；workspace 切換時同時 flush 上一個 workspace 的最後狀態
  useEffect(() => {
    const currentWorkspaceId = workspaceRuntime.workspaceId;
    if (!currentWorkspaceId) return;

    // 若從另一個 workspace 切過來，在讀取新 workspace 前先把舊 workspace 的最後 state 寫入 storage
    // 這段不會被 StrictMode 的模擬 re-mount 誤觸發：第二次執行時 previousId 已等於 currentWorkspaceId
    const previousId = previousRestoredWorkspaceIdRef.current;
    if (previousId && previousId !== currentWorkspaceId) {
      const s = stateRef.current;
      saveWorkspaceLayoutPreferences(previousId, {
        sidebarCollapsed: s.sidebarCollapsed,
        sidebarWidth: s.sidebarWidth,
        secondColumnCollapsed: s.secondColumnCollapsed,
        secondColumnWidth: s.secondColumnWidth,
        rightChatCollapsed: s.rightChatCollapsed,
        rightChatWidth: s.rightChatWidth,
        expandedNavigationItems: [...s.expandedNavigationItems],
      });
    }

    // 載入並套用當前 workspace 的 saved preference
    const saved = loadWorkspaceLayoutPreferences(currentWorkspaceId);
    if (saved) {
      dispatch({ type: 'RESTORE_LAYOUT_PREFERENCES', payload: saved });
    }
    previousRestoredWorkspaceIdRef.current = currentWorkspaceId;

    // 刻意不在 cleanup 中 save：React 18 StrictMode 會在 mount 後立即執行一次 cleanup，
    // 那時 stateRef 仍是 initialState（dispatch RESTORE 尚未套用），會誤覆蓋 localStorage。
    // 所有寫入都交給下方的防抖 effect 處理。
  }, [workspaceRuntime.workspaceId]);

  // 在 layout state 變更時以防抖方式寫回 localStorage，
  // 支援 F5 重新整理 / 關閉分頁等不會觸發 React unmount 的情境
  useEffect(() => {
    const currentWorkspaceId = workspaceRuntime.workspaceId;
    // 只對「已完成 restore 的 workspaceId」寫入，避免 workspace 切換瞬間用舊 state 污染新 key
    if (!currentWorkspaceId || previousRestoredWorkspaceIdRef.current !== currentWorkspaceId) return;

    const timeoutId = setTimeout(() => {
      saveWorkspaceLayoutPreferences(currentWorkspaceId, {
        sidebarCollapsed: state.sidebarCollapsed,
        sidebarWidth: state.sidebarWidth,
        secondColumnCollapsed: state.secondColumnCollapsed,
        secondColumnWidth: state.secondColumnWidth,
        rightChatCollapsed: state.rightChatCollapsed,
        rightChatWidth: state.rightChatWidth,
        expandedNavigationItems: [...state.expandedNavigationItems],
      });
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [
    workspaceRuntime.workspaceId,
    state.sidebarCollapsed,
    state.sidebarWidth,
    state.secondColumnCollapsed,
    state.secondColumnWidth,
    state.rightChatCollapsed,
    state.rightChatWidth,
    state.expandedNavigationItems,
  ]);

  // 當 runtimeBaseUrl 與 access token 都可用時自動載入檔案樹。
  // 這可避免 OIDC callback 導頁後，runtime request 早於 auth context 完整就緒而送出未帶 Authorization 的請求。
  useEffect(() => {
    const baseUrl = workspaceRuntime.runtimeBaseUrl;
    const currentWorkspaceId = workspaceRuntime.workspaceId;
    const isAuthReady = !isAuthLoading && isAuthenticated && Boolean(accessToken);
    const treeIdentity =
      currentWorkspaceId && baseUrl && isAuthReady
        ? `${currentWorkspaceId}::${baseUrl}`
        : null;

    if (!treeIdentity) {
      lastLoadedTreeIdentityRef.current = null;
      return;
    }

    if (lastLoadedTreeIdentityRef.current !== treeIdentity) {
      lastLoadedTreeIdentityRef.current = treeIdentity;
      void loadFileTree();
    }
  }, [
    workspaceRuntime.workspaceId,
    workspaceRuntime.runtimeBaseUrl,
    loadFileTree,
    isAuthLoading,
    isAuthenticated,
    accessToken,
  ]);

  // 定期儲存當前 workspace 的 tabs 到 localStorage (防抖處理)
  useEffect(() => {
    const currentWorkspaceId = workspaceRuntime.workspaceId;
    if (!currentWorkspaceId) return;

    const timeoutId = setTimeout(() => {
      saveWorkspaceTabs(currentWorkspaceId, 'file-management', {
        openTabs: state.fileManagement.openTabs,
        activeTabId: state.fileManagement.activeTabId,
        modifiedTabs: state.fileManagement.modifiedTabs,
        originalContents: state.fileManagement.originalContents,
      });
      saveWorkspaceTabs(currentWorkspaceId, 'openspec', {
        openTabs: state.openspec.openTabs,
        activeTabId: state.openspec.activeTabId,
        modifiedTabs: state.openspec.modifiedTabs,
        originalContents: state.openspec.originalContents,
      });
    }, 500); // 500ms 防抖

    return () => clearTimeout(timeoutId);
  }, [
    workspaceRuntime.workspaceId,
    state.fileManagement.openTabs,
    state.fileManagement.activeTabId,
    state.fileManagement.modifiedTabs,
    state.fileManagement.originalContents,
    state.openspec.openTabs,
    state.openspec.activeTabId,
    state.openspec.modifiedTabs,
    state.openspec.originalContents,
  ]);

  // 檔案標籤頁操作
  const openFileInTab = useCallback(
    (filePath: string, content?: string, scope = currentTabScope) => {
      const fileName = filePath.split('/').pop() || filePath;
      const existingTab = getScopedTabState(scope).openTabs.find(tab => tab.id === filePath);

      if (existingTab) {
        dispatch({ type: 'SET_ACTIVE_TAB', payload: { tabId: filePath, scope } });

        if (content !== undefined) {
          dispatch({ type: 'UPDATE_TAB_CONTENT', payload: { tabId: filePath, content, scope } });
        }
        return;
      }

      const initialContent = content ?? '';
      dispatch({
        type: 'OPEN_FILE_TAB',
        payload: {
          scope,
          id: filePath,
          name: fileName,
          path: filePath,
          content: initialContent,
        },
      });

      if (content !== undefined) {
        dispatch({
          type: 'SET_ORIGINAL_CONTENT',
          payload: { tabId: filePath, content: initialContent, scope },
        });
      }
    },
    [currentTabScope, dispatch, getScopedTabState]
  );

  const closeTab = useCallback((tabId: string, scope = currentTabScope) => {
    dispatch({ type: 'CLOSE_FILE_TAB', payload: { tabId, scope } });
  }, [currentTabScope]);

  const closeAllTabs = useCallback((scope = currentTabScope) => {
    dispatch({ type: 'CLOSE_ALL_TABS', payload: { scope } });
  }, [currentTabScope]);

  const switchToTab = useCallback((tabId: string, scope = currentTabScope) => {
    dispatch({ type: 'SET_ACTIVE_TAB', payload: { tabId, scope } });
  }, [currentTabScope]);

  // 檔案編輯器操作
  const updateTabContent = useCallback((tabId: string, content: string, scope = currentTabScope) => {
    dispatch({ type: 'UPDATE_TAB_CONTENT', payload: { tabId, content, scope } });
  }, [currentTabScope]);

  const setTabModified = useCallback((tabId: string, isModified: boolean, scope = currentTabScope) => {
    dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId, isModified, scope } });
  }, [currentTabScope]);

  const setOriginalContent = useCallback((tabId: string, content: string, scope = currentTabScope) => {
    dispatch({ type: 'SET_ORIGINAL_CONTENT', payload: { tabId, content, scope } });
  }, [currentTabScope]);

  const saveFile = useCallback(async (
    tabId: string,
    scope = currentTabScope,
  ): Promise<{ success: boolean; error?: string }> => {
    const tab = getScopedTabState(scope).openTabs.find(t => t.id === tabId);
    if (!tab) {
      return { success: false, error: '找不到要儲存的檔案' };
    }

    const result = await fileTreeActions.saveFileContent(tab.path, tab.content);
    if (result.success) {
      dispatch({ type: 'SET_ORIGINAL_CONTENT', payload: { tabId, content: tab.content, scope } });
      dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId, isModified: false, scope } });
      return { success: true };
    }
    return { success: false, error: result.message || '儲存檔案失敗' };
  }, [currentTabScope, fileTreeActions, getScopedTabState]);

  const saveAllFiles = useCallback(async (scope = currentTabScope): Promise<{ success: boolean; failed: string[] }> => {
    const scopedTabState = getScopedTabState(scope);
    const modifiedTabs = scopedTabState.openTabs.filter(tab =>
      scopedTabState.modifiedTabs.includes(tab.id)
    );

    const failed: string[] = [];
    for (const tab of modifiedTabs) {
      const result = await saveFile(tab.id, scope);
      if (!result.success) {
        failed.push(tab.id);
      }
    }
    return { success: failed.length === 0, failed };
  }, [currentTabScope, getScopedTabState, saveFile]);

  // 重新載入當前活動檔案
  const reloadCurrentFile = useCallback(async (scope = currentTabScope) => {
    const scopedTabState = getScopedTabState(scope);
    const activeTab = scopedTabState.openTabs.find(t => t.id === scopedTabState.activeTabId);
    if (!activeTab) return { success: false, error: '沒有開啟的檔案' };

    try {
      const result = await fileTreeActions.readFileContent(activeTab.path);
      dispatch({ type: 'UPDATE_TAB_CONTENT', payload: { tabId: activeTab.id, content: result.content, scope } });
      dispatch({ type: 'SET_ORIGINAL_CONTENT', payload: { tabId: activeTab.id, content: result.content, scope } });
      dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId: activeTab.id, isModified: false, scope } });
      return { success: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : '重新載入檔案失敗';
      return { success: false, error: message };
    }
  }, [currentTabScope, fileTreeActions, getScopedTabState]);

  // 還原單個檔案到原始內容
  const revertFile = useCallback((tabId: string, scope = currentTabScope): { success: boolean; error?: string } => {
    const originalContent = getScopedTabState(scope).originalContents[tabId];
    if (originalContent === undefined) {
      return { success: false, error: '找不到原始內容，請嘗試重新載入檔案' };
    }
    dispatch({ type: 'UPDATE_TAB_CONTENT', payload: { tabId, content: originalContent, scope } });
    dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId, isModified: false, scope } });
    return { success: true };
  }, [currentTabScope, getScopedTabState]);

  // 還原所有已修改的檔案
  const revertAllFiles = useCallback((scope = currentTabScope): { success: boolean; failed: string[] } => {
    const scopedTabState = getScopedTabState(scope);
    const failed: string[] = [];
    scopedTabState.modifiedTabs.forEach(tabId => {
      const result = revertFile(tabId, scope);
      if (!result.success) {
        failed.push(tabId);
      }
    });
    return { success: failed.length === 0, failed };
  }, [currentTabScope, getScopedTabState, revertFile]);

  // Mermaid 預覽操作
  const isMermaidPreviewMode = useCallback((tabId: string) => {
    return state.fileManagement.mermaidPreviewMode[tabId] ?? false;
  }, [state.fileManagement.mermaidPreviewMode]);

  const toggleMermaidPreview = useCallback((tabId: string) => {
    dispatch({ type: 'TOGGLE_MERMAID_PREVIEW', payload: tabId });
  }, []);

  // Markdown 預覽操作
  const isMarkdownPreviewMode = useCallback((tabId: string) => {
    return state.fileManagement.markdownPreviewMode[tabId] ?? false;
  }, [state.fileManagement.markdownPreviewMode]);

  const toggleMarkdownPreview = useCallback((tabId: string) => {
    dispatch({ type: 'TOGGLE_MARKDOWN_PREVIEW', payload: tabId });
  }, []);

  // 佈局操作
  const toggleSecondColumn = useCallback(() => {
    dispatch({ type: 'TOGGLE_SECOND_COLUMN' });
  }, []);

  // 檔案樹 Actions

  // Preview 操作
  const renderMarkdown = useCallback((content?: string) => {
    const markdownContent = content ?? state.preview.markdownContent;
    return <MarkdownRenderer content={markdownContent} />;
  }, [state.preview.markdownContent]);

  // 組裝 Context Value
  const contextValue = useMemo<WorkspaceContextType>(
    () => ({
      state,
      dispatch,
      workspace: {
        tabScope: currentTabScope,
        openTabs: getScopedTabState().openTabs,
        activeTabId: getScopedTabState().activeTabId,
        versionControl: state.versionControl,
        workspaceSettings: state.workspaceSettings,
        containerManagement: state.containerManagement,
      },
      workspaceRuntime: {
        workspaceId: workspaceRuntime.workspaceId,
        runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
        terminalExternalUrl: workspaceRuntime.terminalExternalUrl,
        cliType: workspaceRuntime.cliType,
        runtimeStatus: workspaceRuntime.runtimeStatus,
        isLoading: workspaceRuntime.isLoading,
        error: workspaceRuntime.error,
        reload: workspaceRuntime.reload,
        changeWorkspace: workspaceRuntime.changeWorkspace,
      },
      layout: {
        secondColumnCollapsed: state.secondColumnCollapsed,
      },
      fileTreeState: fileTreeAdapter.state,
      fileTreeActions,
      preview: {
        subView: state.preview.subView,
        markdownContent: state.preview.markdownContent,
        rawContent: state.preview.rawContent,
        renderMarkdown,
      },
      openFileInTab,
      closeTab,
      closeAllTabs,
      switchToTab,
      fileEditor: {
        scope: currentTabScope,
        modifiedTabs: getScopedTabState().modifiedTabs,
        originalContents: getScopedTabState().originalContents,
        updateTabContent,
        setTabModified,
        setOriginalContent,
        saveFile,
        saveAllFiles,
        reloadCurrentFile,
        revertFile,
        revertAllFiles,
      },
      mermaidPreview: {
        isPreviewMode: isMermaidPreviewMode,
        togglePreview: toggleMermaidPreview,
      },
      markdownPreview: {
        isPreviewMode: isMarkdownPreviewMode,
        togglePreview: toggleMarkdownPreview,
      },
      toggleSecondColumn,
    }),
    [
      state,
      currentTabScope,
      workspaceRuntime,
      getScopedTabState,
      fileTreeAdapter.state,
      fileTreeActions,
      renderMarkdown,
      openFileInTab,
      closeTab,
      closeAllTabs,
      switchToTab,
      updateTabContent,
      setTabModified,
      setOriginalContent,
      saveFile,
      saveAllFiles,
      reloadCurrentFile,
      revertFile,
      revertAllFiles,
      isMermaidPreviewMode,
      toggleMermaidPreview,
      isMarkdownPreviewMode,
      toggleMarkdownPreview,
      toggleSecondColumn,
    ]
  );

  return <WorkspaceContext.Provider value={contextValue}>{children}</WorkspaceContext.Provider>;
};

export default WorkspaceProvider;
