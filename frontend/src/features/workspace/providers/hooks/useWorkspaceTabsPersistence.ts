import { useCallback, useEffect, useRef, useState, type Dispatch } from 'react';
import type { WorkspaceAction, WorkspaceContextType, WorkspaceState } from '../workspaceStateTypes';
import { loadWorkspaceTabs, saveWorkspaceTabs } from '../../storage/workspaceTabsStorage';

interface UseWorkspaceTabsPersistenceOptions {
  workspaceId: string | null;
  contextId: string | null | undefined;
  fileManagement: WorkspaceState['fileManagement'];
  dispatch: Dispatch<WorkspaceAction>;
}

export const useWorkspaceTabsPersistence = ({
  workspaceId,
  contextId,
  fileManagement,
  dispatch,
}: UseWorkspaceTabsPersistenceOptions): WorkspaceContextType['fileManagementTabsRestoreStatus'] => {
  const previousWorkspaceIdRef = useRef<string | null>(null);
  const previousContextIdRef = useRef<string | null | undefined>(undefined);
  const hasLoadedInitialTabsRef = useRef(false);
  const [restoreStatus, setRestoreStatus] = useState<WorkspaceContextType['fileManagementTabsRestoreStatus']>({
    ready: false,
    workspaceId: null,
    contextId: null,
  });

  const restoreTabs = useCallback((currentWorkspaceId: string, currentContextId: string | null | undefined) => {
    setRestoreStatus({
      ready: false,
      workspaceId: currentWorkspaceId,
      contextId: currentContextId,
    });
    const resolvedTabs = loadWorkspaceTabs(currentWorkspaceId, currentContextId);
    dispatch({
      type: 'RESTORE_WORKSPACE_TABS',
      payload: {
        workspaceId: currentWorkspaceId,
        contextId: currentContextId,
        tabsState: resolvedTabs || undefined,
      },
    });
    setRestoreStatus({
      ready: true,
      workspaceId: currentWorkspaceId,
      contextId: currentContextId,
    });
  }, [dispatch]);

  useEffect(() => {
    if (workspaceId && !hasLoadedInitialTabsRef.current) {
      hasLoadedInitialTabsRef.current = true;
      restoreTabs(workspaceId, contextId);
      previousWorkspaceIdRef.current = workspaceId;
      previousContextIdRef.current = contextId;
    }
  }, [contextId, restoreTabs, workspaceId]);

  useEffect(() => {
    const previousWorkspaceId = previousWorkspaceIdRef.current;

    if (workspaceId && previousWorkspaceId && workspaceId !== previousWorkspaceId) {
      dispatch({
        type: 'SAVE_WORKSPACE_TABS',
        payload: {
          workspaceId: previousWorkspaceId,
          contextId: previousContextIdRef.current,
        },
      });
      restoreTabs(workspaceId, contextId);
    }

    if (workspaceId && workspaceId !== previousWorkspaceId) {
      previousWorkspaceIdRef.current = workspaceId;
      previousContextIdRef.current = contextId;
    }
  }, [contextId, dispatch, restoreTabs, workspaceId]);

  useEffect(() => {
    if (!workspaceId) return;

    const previousContextId = previousContextIdRef.current;
    if (previousContextId === undefined) {
      previousContextIdRef.current = contextId;
      return;
    }

    if (previousContextId === contextId) return;

    dispatch({
      type: 'SAVE_WORKSPACE_TABS',
      payload: {
        workspaceId,
        contextId: previousContextId,
      },
    });
    restoreTabs(workspaceId, contextId);
    previousContextIdRef.current = contextId;
  }, [contextId, dispatch, restoreTabs, workspaceId]);

  useEffect(() => {
    if (!workspaceId) return;

    const timeoutId = setTimeout(() => {
      saveWorkspaceTabs(workspaceId, {
        openTabs: fileManagement.openTabs,
        activeTabId: fileManagement.activeTabId,
        modifiedTabs: fileManagement.modifiedTabs,
        originalContents: fileManagement.originalContents,
        revisions: fileManagement.revisions ?? {},
      }, contextId);
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [
    contextId,
    fileManagement.activeTabId,
    fileManagement.modifiedTabs,
    fileManagement.openTabs,
    fileManagement.originalContents,
    fileManagement.revisions,
    workspaceId,
  ]);

  return restoreStatus;
};
