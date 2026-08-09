import { useCallback, useMemo, type Dispatch } from 'react';
import type { FileTreeActions } from '../../features/file-management/model/fileManagementTypes';
import type { WorkspaceAction, WorkspaceState } from '../workspaceStateTypes';
import { FILE_EDITOR_ERROR_KEYS } from '../workspaceProviderModel';

interface UseWorkspaceFileEditorActionsOptions {
  fileManagement: WorkspaceState['fileManagement'];
  fileTreeActions: FileTreeActions;
  dispatch: Dispatch<WorkspaceAction>;
}

export const useWorkspaceFileEditorActions = ({
  fileManagement,
  fileTreeActions,
  dispatch,
}: UseWorkspaceFileEditorActionsOptions) => {
  const tabState = useMemo(() => ({
    openTabs: fileManagement.openTabs,
    activeTabId: fileManagement.activeTabId,
    modifiedTabs: fileManagement.modifiedTabs,
    originalContents: fileManagement.originalContents,
    revisions: fileManagement.revisions ?? {},
  }), [
    fileManagement.activeTabId,
    fileManagement.modifiedTabs,
    fileManagement.openTabs,
    fileManagement.originalContents,
    fileManagement.revisions,
  ]);

  const openFileInTab = useCallback((
    filePath: string,
    content?: string,
  ) => {
    const fileName = filePath.split('/').pop() || filePath;
    const existingTab = tabState.openTabs.find(tab => tab.id === filePath);

    if (existingTab) {
      dispatch({ type: 'SET_ACTIVE_TAB', payload: { tabId: filePath } });
      if (content !== undefined) {
        dispatch({ type: 'UPDATE_TAB_CONTENT', payload: { tabId: filePath, content } });
      }
      return;
    }

    const initialContent = content ?? '';
    dispatch({
      type: 'OPEN_FILE_TAB',
      payload: {
        id: filePath,
        name: fileName,
        path: filePath,
        content: initialContent,
      },
    });

    if (content !== undefined) {
      dispatch({
        type: 'SET_ORIGINAL_CONTENT',
        payload: { tabId: filePath, content: initialContent },
      });
    }
  }, [dispatch, tabState.openTabs]);

  const closeTab = useCallback((tabId: string) => {
    dispatch({ type: 'CLOSE_FILE_TAB', payload: { tabId } });
  }, [dispatch]);

  const closeAllTabs = useCallback(() => {
    dispatch({ type: 'CLOSE_ALL_TABS' });
  }, [dispatch]);

  const switchToTab = useCallback((tabId: string) => {
    dispatch({ type: 'SET_ACTIVE_TAB', payload: { tabId } });
  }, [dispatch]);

  const updateTabContent = useCallback((tabId: string, content: string) => {
    dispatch({ type: 'UPDATE_TAB_CONTENT', payload: { tabId, content } });
  }, [dispatch]);

  const reorderTabs = useCallback((tabIds: string[]) => {
    dispatch({ type: 'REORDER_FILE_TABS', payload: { tabIds } });
  }, [dispatch]);

  const setTabModified = useCallback((tabId: string, isModified: boolean) => {
    dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId, isModified } });
  }, [dispatch]);

  const setOriginalContent = useCallback((tabId: string, content: string) => {
    dispatch({ type: 'SET_ORIGINAL_CONTENT', payload: { tabId, content } });
  }, [dispatch]);

  const setFileRevision = useCallback((
    tabId: string,
    revision?: string | null,
  ) => {
    dispatch({ type: 'SET_FILE_VERSION_ID', payload: { tabId, revision } });
  }, [dispatch]);

  const saveFile = useCallback(async (
    tabId: string,
  ): Promise<{ success: boolean; error?: string }> => {
    const tab = tabState.openTabs.find(item => item.id === tabId);
    if (!tab) {
      return { success: false, error: FILE_EDITOR_ERROR_KEYS.saveFileMissing };
    }

    const revision = tabState.revisions[tab.id];
    const result = await fileTreeActions.saveFileContent(tab.path, tab.content, revision);
    if (result.success) {
      dispatch({ type: 'SET_ORIGINAL_CONTENT', payload: { tabId, content: tab.content } });
      dispatch({ type: 'SET_FILE_VERSION_ID', payload: { tabId, revision: result.revision } });
      dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId, isModified: false } });
      return { success: true };
    }
    return { success: false, error: result.message || FILE_EDITOR_ERROR_KEYS.saveFailed };
  }, [dispatch, fileTreeActions, tabState.openTabs, tabState.revisions]);

  const saveAllFiles = useCallback(async (): Promise<{ success: boolean; failed: string[] }> => {
    const modifiedTabs = tabState.openTabs.filter(tab => (
      tabState.modifiedTabs.includes(tab.id)
    ));
    const failed: string[] = [];

    for (const tab of modifiedTabs) {
      const result = await saveFile(tab.id);
      if (!result.success) failed.push(tab.id);
    }
    return { success: failed.length === 0, failed };
  }, [saveFile, tabState.modifiedTabs, tabState.openTabs]);

  const reloadCurrentFile = useCallback(async () => {
    const activeTab = tabState.openTabs.find(tab => tab.id === tabState.activeTabId);
    if (!activeTab) {
      return { success: false, error: FILE_EDITOR_ERROR_KEYS.reloadFileMissing };
    }

    try {
      const result = await fileTreeActions.readFileContent(activeTab.path);
      dispatch({ type: 'UPDATE_TAB_CONTENT', payload: { tabId: activeTab.id, content: result.content } });
      dispatch({ type: 'SET_ORIGINAL_CONTENT', payload: { tabId: activeTab.id, content: result.content } });
      dispatch({ type: 'SET_FILE_VERSION_ID', payload: { tabId: activeTab.id, revision: result.revision } });
      dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId: activeTab.id, isModified: false } });
      return { success: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : FILE_EDITOR_ERROR_KEYS.reloadFailed;
      return { success: false, error: message };
    }
  }, [dispatch, fileTreeActions, tabState.activeTabId, tabState.openTabs]);

  const revertFile = useCallback((
    tabId: string,
  ): { success: boolean; error?: string } => {
    const originalContent = tabState.originalContents[tabId];
    if (originalContent === undefined) {
      return { success: false, error: FILE_EDITOR_ERROR_KEYS.originalContentMissing };
    }
    dispatch({ type: 'UPDATE_TAB_CONTENT', payload: { tabId, content: originalContent } });
    dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId, isModified: false } });
    return { success: true };
  }, [dispatch, tabState.originalContents]);

  const revertAllFiles = useCallback((): { success: boolean; failed: string[] } => {
    const failed: string[] = [];
    tabState.modifiedTabs.forEach(tabId => {
      const result = revertFile(tabId);
      if (!result.success) failed.push(tabId);
    });
    return { success: failed.length === 0, failed };
  }, [revertFile, tabState.modifiedTabs]);

  return {
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
  };
};
