import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FileText } from 'lucide-react';
import { isImageFile, toFileWorkbenchTab } from '@/shared/components/file-workbench';
import {
  FileViewerWorkbenchSplitView,
  type FileWorkbenchPane,
  type FileViewerWorkbenchTab,
  type FileViewerTextSelection,
} from '@/shared/components/file-workbench/viewer-entry';
import { createWorkspaceFileWorkbenchAdapter } from '../adapters/workspaceFileWorkbenchAdapter';
import { fileWorkbenchSplitStorage } from '../utils/fileWorkbenchSplitStorage';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { EmptyState } from '@/shared/components/ui/empty-state';
import { useWorkspaceAiChatSelection } from '../../../integrations/ai-chat/WorkspaceAiChatSelectionContext';

const logger = createLogger('FileEditor');

const getWorkspaceSaveErrorTitle = (error: unknown, t: (key: string) => string): string => {
  const isContentConflict = (
    typeof error === 'object' &&
    error !== null &&
    'errorCode' in error &&
    (error as { errorCode?: unknown }).errorCode === 'CONTENT_CONFLICT'
  );

  return t(isContentConflict
    ? 'workspace.fileManagement.tree.notifications.saveConflict'
    : 'workspace.fileManagement.tree.notifications.saveFailed');
};

export const FileEditor: React.FC = () => {
  const {
    workspace,
    workspaceRuntime,
    permissions,
    layout,
    closeTab,
    switchToTab,
    closeAllTabs,
    openFileInTab,
    fileTreeActions: actions,
    fileEditor,
    toggleFileManagementEditorExpanded,
  } = useWorkspace();
  const { t } = useI18n();
  const { toast } = useToast();
  const {
    canSelectCodeReference,
    selectCodeReference,
  } = useWorkspaceAiChatSelection();
  const [loadingFiles, setLoadingFiles] = useState<string[]>([]);
  const workspaceId = workspaceRuntime.workspaceId;
  const [panes, setPanes] = useState<FileWorkbenchPane[] | undefined>(undefined);
  const [sizes, setSizes] = useState<number[] | undefined>(undefined);

  useEffect(() => {
    if (!workspaceId) {
      return;
    }

    const saved = fileWorkbenchSplitStorage.load(workspaceId);
    setPanes(saved?.panes.map((pane, index) => ({ id: `restored-pane-${index}`, ...pane })));
    setSizes(saved?.sizes);
  }, [workspaceId]);

  useEffect(() => {
    // SplitPaneGroup reconciles sizes when pane membership changes, so only persist matching live ratios.
    if (!workspaceId || !panes || !sizes) {
      return;
    }

    const timeoutId = setTimeout(() => {
      fileWorkbenchSplitStorage.save(workspaceId, {
        direction: 'horizontal',
        panes: panes.map(({ tabIds, activeTabId }) => ({ tabIds, activeTabId })),
        sizes,
      });
    }, 500);

    return () => clearTimeout(timeoutId);
  }, [workspaceId, panes, sizes]);

  const activeTab = workspace.openTabs.find(tab => tab.id === workspace.activeTabId) ?? null;
  const isFocusMode = layout.fileManagementFocusMode ?? layout.fileManagementEditorExpanded;

  const workbenchTabs = useMemo(
    () => workspace.openTabs.map((tab): FileViewerWorkbenchTab => toFileWorkbenchTab({
      id: tab.id,
      path: tab.path,
      name: tab.name,
      content: tab.content ?? '',
      originalContent: fileEditor.originalContents[tab.id] ?? tab.content ?? '',
      isModified: fileEditor.modifiedTabs.includes(tab.id),
      isLoading: loadingFiles.includes(tab.id),
    })),
    [fileEditor.modifiedTabs, fileEditor.originalContents, loadingFiles, workspace.openTabs],
  );

  const saveWorkspaceFile = useCallback(async (path: string, content: string) => {
    if (!permissions.canWrite) {
      throw new Error(t('common.authorization.readOnlyDescription'));
    }
    const result = await actions.saveFileContent(path, content, fileEditor.revisions[path]);
    if (!result.success) {
      const error = new Error(result.message || t('workspace.fileManagement.tree.notifications.saveFailed')) as Error & {
        errorCode?: string;
      };
      error.errorCode = result.errorCode;
      throw error;
    }
    fileEditor.updateTabContent(path, content);
    fileEditor.setOriginalContent(path, content);
    fileEditor.setFileRevision(path, result.revision);
    fileEditor.setTabModified(path, false);
  }, [actions, fileEditor, permissions.canWrite, t]);

  const workbenchAdapter = useMemo(() => createWorkspaceFileWorkbenchAdapter({
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    readFile: async (path) => {
      const result = await actions.readFileContent(path);
      fileEditor.setFileRevision(path, result.revision);
      return result.content;
    },
    saveFile: saveWorkspaceFile,
    saveDrawio: async (path, content) => {
      fileEditor.updateTabContent(path, content);
      fileEditor.setOriginalContent(path, content);
      fileEditor.setTabModified(path, false);
    },
    copyPath: async (path) => {
      await navigator.clipboard.writeText(path);
      toast({
        title: t('workspace.fileManagement.editor.toolbar.pathCopied'),
      });
    },
    revealInTree: (path) => {
      actions.selectFile(path);
    },
  }), [actions, fileEditor, saveWorkspaceFile, t, toast, workspaceRuntime.runtimeBaseUrl]);

  const loadFileContent = useCallback(async (filePath: string) => {
    const tab = workspace.openTabs.find(item => item.id === filePath);
    if (!tab || isImageFile(tab.name) || fileEditor.originalContents[filePath] !== undefined) {
      return;
    }

    if (loadingFiles.includes(filePath)) {
      return;
    }

    setLoadingFiles(prev => prev.includes(filePath) ? prev : [...prev, filePath]);

    try {
      const content = await workbenchAdapter.readFile(filePath);
      fileEditor.updateTabContent(filePath, content);
      fileEditor.setOriginalContent(filePath, content);
      fileEditor.setTabModified(filePath, false);
    } catch (error) {
      logger.error('Failed to load file content', { error });
      const errorContent = t('workspace.fileManagement.editor.loadErrorPlaceholder');
      fileEditor.updateTabContent(filePath, errorContent);
      fileEditor.setOriginalContent(filePath, errorContent);
      fileEditor.setTabModified(filePath, false);
    } finally {
      setLoadingFiles(prev => prev.filter(id => id !== filePath));
    }
  }, [fileEditor, loadingFiles, t, workbenchAdapter, workspace.openTabs]);

  useEffect(() => {
    if (activeTab) {
      void loadFileContent(activeTab.id);
    }
  }, [activeTab, loadFileContent]);

  useEffect(() => {
    const handleKeyDown = async (event: KeyboardEvent) => {
      if (!permissions.canWrite) {
        return;
      }
      const isMod = event.ctrlKey || event.metaKey;

      if (isMod && event.shiftKey && event.key === 's') {
        event.preventDefault();
        const modifiedTabs = workspace.openTabs.filter(tab => fileEditor.modifiedTabs.includes(tab.id));
        try {
          await Promise.all(modifiedTabs.map(tab => saveWorkspaceFile(tab.id, tab.content ?? '')));
        } catch (error) {
          toast({
            title: getWorkspaceSaveErrorTitle(error, t),
            description: error instanceof Error ? error.message : undefined,
            variant: 'destructive',
          });
        }
        return;
      }

      if (isMod && event.key === 's') {
        event.preventDefault();
        if (activeTab && fileEditor.modifiedTabs.includes(activeTab.id)) {
          try {
            await saveWorkspaceFile(activeTab.id, activeTab.content ?? '');
          } catch (error) {
            toast({
              title: getWorkspaceSaveErrorTitle(error, t),
              description: error instanceof Error ? error.message : undefined,
              variant: 'destructive',
            });
          }
        }
        return;
      }

      if (isMod && event.altKey && event.key === 'z') {
        event.preventDefault();
        if (activeTab && fileEditor.modifiedTabs.includes(activeTab.id)) {
          const result = fileEditor.revertFile(activeTab.id);
          if (!result.success) {
            toast({
              title: t('workspace.fileManagement.editor.toolbar.revertFailed'),
              description: result.error ? t(result.error) : undefined,
              variant: 'destructive',
            });
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [
    activeTab,
    fileEditor,
    permissions.canWrite,
    saveWorkspaceFile,
    t,
    toast,
    workspace.openTabs,
  ]);

  const handleTabsChange = useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    const nextById = new Map(nextTabs.map(tab => [tab.id, tab]));
    const currentIds = workspace.openTabs.map(tab => tab.id);
    const nextIds = nextTabs.map(tab => tab.id);
    const hasSameTabs = currentIds.length === nextIds.length
      && currentIds.every(id => nextById.has(id));
    const hasOrderChanged = hasSameTabs
      && currentIds.some((id, index) => id !== nextIds[index]);

    if (hasOrderChanged) {
      fileEditor.reorderTabs(nextIds);
    }

    workspace.openTabs.forEach(tab => {
      if (!nextById.has(tab.id)) {
        closeTab(tab.id);
        setLoadingFiles(prev => prev.filter(id => id !== tab.id));
      }
    });

    if (permissions.canWrite) {
      nextTabs.forEach(nextTab => {
      const previous = workspace.openTabs.find(tab => tab.id === nextTab.id);
      if (!previous) return;

      if (previous.content !== nextTab.content) {
        fileEditor.updateTabContent(nextTab.id, nextTab.content);
      }

      if (fileEditor.originalContents[nextTab.id] !== nextTab.originalContent) {
        fileEditor.setOriginalContent(nextTab.id, nextTab.originalContent);
      }

      if (fileEditor.modifiedTabs.includes(nextTab.id) !== nextTab.isModified) {
        fileEditor.setTabModified(nextTab.id, nextTab.isModified);
      }
      });
    }

    if (nextTabs.length === 0 && workspace.openTabs.length > 0) {
      closeAllTabs();
      setLoadingFiles([]);
    }
  }, [closeAllTabs, closeTab, fileEditor, permissions.canWrite, workspace.openTabs]);

  const handleActiveTabChange = useCallback((tabId: string | null) => {
    if (!tabId) return;
    switchToTab(tabId);
    actions.selectFile(tabId);
  }, [actions, switchToTab]);

  const handleTextSelectionChange = useCallback((selection: FileViewerTextSelection) => {
    if (!canSelectCodeReference) {
      return;
    }
    selectCodeReference(selection);
  }, [canSelectCodeReference, selectCodeReference]);

  useEffect(() => {
    if (workspace.openTabs.length === 0 && isFocusMode) {
      toggleFileManagementEditorExpanded();
    }
  }, [isFocusMode, toggleFileManagementEditorExpanded, workspace.openTabs.length]);

  if (workspace.openTabs.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title={t('workspace.fileManagement.editor.emptyState.title')}
      />
    );
  }

  return (
    <FileViewerWorkbenchSplitView
      tabs={workbenchTabs}
      activeTabId={workspace.activeTabId}
      adapter={workbenchAdapter}
      capabilities={{
        canEdit: permissions.canWrite,
        canSave: permissions.canWrite,
        canReadBlob: true,
        canPreviewDrawio: true,
        canCopyPath: true,
        canRevealInTree: true,
        canCloseTabs: true,
      }}
      isExpanded={isFocusMode}
      onExpandedChange={toggleFileManagementEditorExpanded}
      onTabsChange={handleTabsChange}
      onActiveTabChange={handleActiveTabChange}
      onOpenPath={openFileInTab}
      onTextSelectionChange={canSelectCodeReference
        ? handleTextSelectionChange
        : undefined}
      panes={panes}
      onPanesChange={setPanes}
      sizes={sizes}
      onSizesChange={setSizes}
    />
  );
};
