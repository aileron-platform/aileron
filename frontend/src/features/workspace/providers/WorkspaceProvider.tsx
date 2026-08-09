/**
 *
 */

import React, {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  type ReactNode,
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { WorkspaceContextType } from './workspaceStateTypes';
import type { BrowserContainerStatus, WorkspaceRuntimeStatus } from '../api/workspaceApiTypes';
import { WorkspaceContext } from './WorkspaceContext';
import { workspaceReducer } from './workspaceStateReducer';
import { initialState, getFeatureFromPath } from './workspaceStateConstants';
import {
  useWorkspaceRuntime,
  type UseWorkspaceRuntimeReturn,
} from '../hooks/useWorkspaceRuntime';
import { useWorkspaceRouteSync } from '../hooks/useWorkspaceRouteSync';
import {
  clearWorkspaceLayoutPreferences,
  loadWorkspaceLayoutPreferences,
} from '../storage/workspaceLayoutStorage';
import { clearWorkspaceTabs } from '../storage/workspaceTabsStorage';
import { useWorkspaceFileTreeAdapter } from '../features/file-management/hooks/useWorkspaceFileTreeAdapter';
import { useWorkspaceFileEditorActions } from './hooks/useWorkspaceFileEditorActions';
import { useWorkspaceLayoutPersistence } from './hooks/useWorkspaceLayoutPersistence';
import { useWorkspaceTabsPersistence } from './hooks/useWorkspaceTabsPersistence';
import { useThreadEvents } from '@/features/ai-chat/public';
import { createLogger } from '@/shared/services/logger';
import { updateRecentWorkspace } from '@/shared/api/recentWorkspaceApi';
import { WorkspaceAiChatIntegration } from '../integrations/ai-chat/WorkspaceAiChatIntegration';
import { WorkspaceAiChatSelectionProvider } from '../integrations/ai-chat/WorkspaceAiChatSelectionContext';
import { resolveWorkspacePermissions } from '../model/workspacePermissions';
import { subscribeApiError } from '@/shared/api/apiClient';
import { isWorkspaceAuthorizationDenialCode } from '@/shared/authorization/authorizationErrorCodes';
import { clearWorkspaceArchiveOperations } from '../features/file-management/model/workspaceArchivePersistence';
import { fileWorkbenchSplitStorage } from '../features/file-management/utils/fileWorkbenchSplitStorage';
import { clearRevokedWorkspaceAvailabilitySession } from '../availability/workspaceAvailabilitySession';
import { clearSelectedWorkspaceIdIfMatches } from '../selection/workspaceSelectionStorage';
import { workspaceShellLayoutStorage } from '../storage/workspaceShellLayoutStorage';
import { useOptionalWorkspaceSelection } from '../selection/WorkspaceSelectionContext';

const logger = createLogger('WorkspaceProvider');
const unavailableAiChatSelection = {
  canSelectCodeReference: false,
  selectCodeReference: () => undefined,
  companionRevealRequestId: 0,
};

export { useWorkspace } from './WorkspaceContext';

interface WorkspaceProviderProps {
  children: ReactNode;
  workspaceId?: string | null;
  runtimeSnapshot?: UseWorkspaceRuntimeReturn;
}

const BROWSER_CONTAINER_STATUSES: readonly BrowserContainerStatus[] = [
  'stopped',
  'starting',
  'running',
  'error',
  'restarting',
];

const normalizeBrowserContainerStatus = (status: string): BrowserContainerStatus | undefined => {
  return BROWSER_CONTAINER_STATUSES.includes(status as BrowserContainerStatus)
    ? status as BrowserContainerStatus
    : undefined;
};

const normalizeWorkspaceRuntimeStatus = (
  runtimeStatus: WorkspaceRuntimeStatus | null
): WorkspaceRuntimeStatus | null => {
  if (!runtimeStatus) {
    return null;
  }

  return {
    ...runtimeStatus,
    browserStatus: normalizeBrowserContainerStatus(runtimeStatus.browserStatus),
  };
};

export const WorkspaceProvider: React.FC<WorkspaceProviderProps> = ({
  children,
  workspaceId,
  runtimeSnapshot,
}) => {
  const queryClient = useQueryClient();
  const workspaceSelection = useOptionalWorkspaceSelection();
  const computedInitialState = useMemo(() => {
    const currentFeature = getFeatureFromPath(window.location.pathname);
    const persistedLayoutPreferences = workspaceId
      ? loadWorkspaceLayoutPreferences(workspaceId)
      : null;

    return {
      ...initialState,
      currentFeature,
      fileTreeShowHiddenEntries:
        persistedLayoutPreferences?.fileTreeShowHiddenEntries ?? initialState.fileTreeShowHiddenEntries,
    };
  }, [workspaceId]);

  const [state, dispatch] = useReducer(workspaceReducer, computedInitialState);

  const ownedWorkspaceRuntime = useWorkspaceRuntime(runtimeSnapshot ? null : workspaceId);
  const workspaceRuntime = runtimeSnapshot ?? ownedWorkspaceRuntime;
  const permissions = useMemo(
    () => resolveWorkspacePermissions(
      workspaceRuntime.accessRole,
      workspaceRuntime.allowedOperations,
    ),
    [workspaceRuntime.accessRole, workspaceRuntime.allowedOperations],
  );
  const clearedWorkspaceIdRef = useRef<string | null>(null);
  const workspaceAuthorizationRefreshRef = useRef<Promise<void> | null>(null);
  const activeRuntimeWorkspaceId = workspaceRuntime.workspaceId;
  const reloadWorkspaceRuntime = workspaceRuntime.reload;
  const refreshWorkspaceAuthorization = useCallback((): Promise<void> => {
    const activeWorkspaceId = activeRuntimeWorkspaceId ?? workspaceId ?? null;
    if (!activeWorkspaceId) {
      return Promise.resolve();
    }
    if (workspaceAuthorizationRefreshRef.current) {
      return workspaceAuthorizationRefreshRef.current;
    }

    const refreshRequest = reloadWorkspaceRuntime()
      .catch((error: unknown) => {
        logger.warn('Failed to refresh workspace authorization', {
          error,
          workspaceId: activeWorkspaceId,
        });
      })
      .finally(() => {
        workspaceAuthorizationRefreshRef.current = null;
      });
    workspaceAuthorizationRefreshRef.current = refreshRequest;
    return refreshRequest;
  }, [activeRuntimeWorkspaceId, reloadWorkspaceRuntime, workspaceId]);

  useThreadEvents(
    workspaceRuntime.workspaceId ?? workspaceId ?? '',
    workspaceRuntime.runtimeBaseUrl ?? '',
    permissions.canUseChat,
  );

  useEffect(() => {
    const activeWorkspaceId = workspaceRuntime.workspaceId;
    if (!activeWorkspaceId || !permissions.canRead) return;
    void updateRecentWorkspace(activeWorkspaceId).catch((error) => {
      logger.warn('Failed to update recent workspace', { error, workspaceId: activeWorkspaceId });
    });
  }, [permissions.canRead, workspaceRuntime.workspaceId]);

  useEffect(() => {
    const activeWorkspaceId = workspaceRuntime.workspaceId ?? workspaceId ?? null;
    if (permissions.canRead) {
      clearedWorkspaceIdRef.current = null;
      return;
    }
    const accessRevocationConfirmed = (
      workspaceRuntime.isAuthorizationResolved
      && !workspaceRuntime.isLoading
      && (
        !workspaceRuntime.error
        || workspaceRuntime.errorCode === 'WORKSPACE_ACCESS_DENIED'
      )
    );

    if (
      !activeWorkspaceId
      || !accessRevocationConfirmed
      || clearedWorkspaceIdRef.current === activeWorkspaceId
    ) {
      return;
    }

    clearedWorkspaceIdRef.current = activeWorkspaceId;
    dispatch({
      type: 'CLEAR_WORKSPACE_FILE_STATE',
      payload: { workspaceId: activeWorkspaceId },
    });
    clearWorkspaceTabs(activeWorkspaceId);
    fileWorkbenchSplitStorage.clear(activeWorkspaceId);
    clearWorkspaceArchiveOperations(activeWorkspaceId);
    clearWorkspaceLayoutPreferences(activeWorkspaceId);
    workspaceShellLayoutStorage.clear(activeWorkspaceId);
    if (workspaceSelection?.selectedWorkspaceId === activeWorkspaceId) {
      workspaceSelection.setSelectedWorkspaceId(null);
    }
    clearSelectedWorkspaceIdIfMatches(activeWorkspaceId);
    void clearRevokedWorkspaceAvailabilitySession(queryClient, activeWorkspaceId).catch((error) => {
      logger.warn('Failed to clear revoked workspace queries', {
        error,
        workspaceId: activeWorkspaceId,
      });
    });
  }, [
    permissions.canRead,
    queryClient,
    workspaceSelection,
    workspaceId,
    workspaceRuntime.errorCode,
    workspaceRuntime.error,
    workspaceRuntime.isAuthorizationResolved,
    workspaceRuntime.isLoading,
    workspaceRuntime.workspaceId,
  ]);

  useEffect(() => {
    const refresh = () => {
      void refreshWorkspaceAuthorization();
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refresh();
      }
    };
    const unsubscribeApiError = subscribeApiError((event) => {
      if (isWorkspaceAuthorizationDenialCode(event.errorCode)) {
        refresh();
      }
    });

    window.addEventListener('focus', refresh);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      unsubscribeApiError();
      window.removeEventListener('focus', refresh);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [refreshWorkspaceAuthorization]);

  const selectedGitContextId = state.versionControl.selectedGitContextId;
  const fileManagementContextId = selectedGitContextId;

  useWorkspaceRouteSync(state, dispatch);

  const fileTreeAdapter = useWorkspaceFileTreeAdapter({
    workspaceId: permissions.canRead
      ? workspaceRuntime.workspaceId ?? workspaceId
      : undefined,
    runtimeBaseUrl: permissions.canRead
      ? workspaceRuntime.runtimeBaseUrl
      : null,
    contextId: fileManagementContextId,
    showHiddenEntries: state.fileTreeShowHiddenEntries,
    onShowHiddenEntriesChange: (showHiddenEntries) => {
      dispatch({ type: 'SET_FILE_TREE_SHOW_HIDDEN_ENTRIES', payload: showHiddenEntries });
    },
  });

  const fileTreeActions = fileTreeAdapter.actions;
  const fileManagementTabsRestoreStatus = useWorkspaceTabsPersistence({
    workspaceId: permissions.canRead
      ? workspaceRuntime.workspaceId
      : null,
    contextId: fileManagementContextId,
    fileManagement: state.fileManagement,
    dispatch,
  });

  useWorkspaceLayoutPersistence({
    workspaceId: permissions.canRead ? workspaceRuntime.workspaceId : null,
    state,
    dispatch,
  });

  const {
    tabState,
    openFileInTab,
    closeTab,
    closeAllTabs,
    switchToTab,
    updateTabContent,
    reorderTabs,
    setTabModified,
    setOriginalContent,
    setFileRevision,
    saveFile,
    saveAllFiles,
    reloadCurrentFile,
    revertFile,
    revertAllFiles,
  } = useWorkspaceFileEditorActions({
    fileManagement: state.fileManagement,
    fileTreeActions,
    dispatch,
  });

  const isMermaidCanvasMode = useCallback((tabId: string) => {
    return state.fileManagement.mermaidCanvasMode[tabId] ?? false;
  }, [state.fileManagement.mermaidCanvasMode]);

  const toggleMermaidCanvas = useCallback((tabId: string) => {
    dispatch({ type: 'TOGGLE_MERMAID_PREVIEW', payload: tabId });
  }, []);

  const isMarkdownCanvasMode = useCallback((tabId: string) => {
    return state.fileManagement.markdownCanvasMode[tabId] ?? false;
  }, [state.fileManagement.markdownCanvasMode]);

  const toggleMarkdownCanvas = useCallback((tabId: string) => {
    dispatch({ type: 'TOGGLE_MARKDOWN_PREVIEW', payload: tabId });
  }, []);

  const toggleFileManagementEditorExpanded = useCallback(() => {
    dispatch({ type: 'TOGGLE_FILE_MANAGEMENT_EDITOR_EXPANDED' });
  }, []);


  const normalizedRuntimeStatus = useMemo(
    () => normalizeWorkspaceRuntimeStatus(workspaceRuntime.runtimeStatus),
    [workspaceRuntime.runtimeStatus]
  );

  const contextValue = useMemo<WorkspaceContextType>(
    () => ({
      state,
      dispatch,
      permissions,
      fileManagementTabsRestoreStatus,
      workspace: {
        openTabs: tabState.openTabs,
        activeTabId: tabState.activeTabId,
        versionControl: state.versionControl,
        workspaceSettings: state.workspaceSettings,
        containerManagement: state.containerManagement,
      },
      workspaceRuntime: {
        workspaceId: workspaceRuntime.workspaceId,
        runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
        agenticTools: workspaceRuntime.agenticTools,
        accessRole: workspaceRuntime.accessRole,
        allowedOperations: workspaceRuntime.allowedOperations,
        runtimeStatus: normalizedRuntimeStatus,
        browserConnectivity: workspaceRuntime.browserConnectivity,
        isLoading: workspaceRuntime.isLoading,
        isAuthorizationResolved: workspaceRuntime.isAuthorizationResolved,
        error: workspaceRuntime.error,
        errorCode: workspaceRuntime.errorCode,
        reload: workspaceRuntime.reload,
        changeWorkspace: workspaceRuntime.changeWorkspace,
      },
      layout: {
        fileManagementEditorExpanded: state.fileManagementEditorExpanded,
        fileManagementFocusMode: state.fileManagementEditorExpanded,
      },
      fileTreeState: fileTreeAdapter.state,
      fileTreeActions,
      openFileInTab,
      closeTab,
      closeAllTabs,
      switchToTab,
      fileEditor: {
        modifiedTabs: tabState.modifiedTabs,
        originalContents: tabState.originalContents,
        revisions: tabState.revisions,
        updateTabContent,
        reorderTabs,
        setTabModified,
        setOriginalContent,
        setFileRevision,
        saveFile,
        saveAllFiles,
        reloadCurrentFile,
        revertFile,
        revertAllFiles,
      },
      mermaidCanvas: {
        isCanvasMode: isMermaidCanvasMode,
        toggleCanvas: toggleMermaidCanvas,
      },
      markdownCanvas: {
        isCanvasMode: isMarkdownCanvasMode,
        toggleCanvas: toggleMarkdownCanvas,
      },
      toggleFileManagementEditorExpanded,
      toggleFileManagementFocusMode: toggleFileManagementEditorExpanded,
    }),
    [
      state,
      permissions,
      fileManagementTabsRestoreStatus,
      workspaceRuntime,
      normalizedRuntimeStatus,
      tabState,
      fileTreeAdapter.state,
      fileTreeActions,
      openFileInTab,
      closeTab,
      closeAllTabs,
      switchToTab,
      updateTabContent,
      reorderTabs,
      setTabModified,
      setOriginalContent,
      setFileRevision,
      saveFile,
      saveAllFiles,
      reloadCurrentFile,
      revertFile,
      revertAllFiles,
      isMermaidCanvasMode,
      toggleMermaidCanvas,
      isMarkdownCanvasMode,
      toggleMarkdownCanvas,
      toggleFileManagementEditorExpanded,
    ]
  );

  return (
    <WorkspaceContext.Provider value={contextValue}>
      {permissions.canUseChat ? (
        <WorkspaceAiChatIntegration>{children}</WorkspaceAiChatIntegration>
      ) : (
        <WorkspaceAiChatSelectionProvider value={unavailableAiChatSelection}>
          {children}
        </WorkspaceAiChatSelectionProvider>
      )}
    </WorkspaceContext.Provider>
  );
};
