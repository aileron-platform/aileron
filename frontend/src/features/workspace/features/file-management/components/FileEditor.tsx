import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FileText } from 'lucide-react';
import {
  FileViewerWorkbench,
  FileFocusToolbar,
  toFileWorkbenchTab,
  type FileViewerWorkbenchTab,
} from '@/shared/components/file-workbench/viewer-entry';
import { createWorkspaceFileWorkbenchAdapter } from '../adapters/workspaceFileWorkbenchAdapter';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { getFileIcon } from '@/shared/utils/fileIconUtils';
import { isImageFile } from '@/shared/utils/fileTypeUtils';
import { createLogger } from '@/shared/services/logger';
import { useWorkspace } from '../../../providers/WorkspaceProvider';

const logger = createLogger('FileEditor');

export const FileEditor: React.FC = () => {
  const {
    workspace,
    workspaceRuntime,
    layout,
    closeTab,
    switchToTab,
    closeAllTabs,
    fileTreeActions: actions,
    fileEditor,
    toggleFileManagementEditorExpanded,
  } = useWorkspace();
  const { t } = useI18n();
  const { toast } = useToast();
  const [loadingFiles, setLoadingFiles] = useState<string[]>([]);

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
    const result = await actions.saveFileContent(path, content);
    if (!result.success) {
      throw new Error(result.message || t('workspace.fileManagement.tree.notifications.saveFailed'));
    }
    fileEditor.updateTabContent(path, content);
    fileEditor.setOriginalContent(path, content);
    fileEditor.setTabModified(path, false);
  }, [actions, fileEditor, t]);

  const workbenchAdapter = useMemo(() => createWorkspaceFileWorkbenchAdapter({
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    readFile: async (path) => {
      const result = await actions.readFileContent(path);
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
        duration: 2000,
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
      const isMod = event.ctrlKey || event.metaKey;

      if (isMod && event.shiftKey && event.key === 's') {
        event.preventDefault();
        const modifiedTabs = workspace.openTabs.filter(tab => fileEditor.modifiedTabs.includes(tab.id));
        try {
          await Promise.all(modifiedTabs.map(tab => saveWorkspaceFile(tab.id, tab.content ?? '')));
        } catch (error) {
          toast({
            title: t('workspace.fileManagement.tree.notifications.saveFailed'),
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
              title: t('workspace.fileManagement.tree.notifications.saveFailed'),
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
              description: result.error,
              variant: 'destructive',
            });
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [activeTab, fileEditor, saveWorkspaceFile, t, toast, workspace.openTabs]);

  const handleTabsChange = useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    const nextById = new Map(nextTabs.map(tab => [tab.id, tab]));
    workspace.openTabs.forEach(tab => {
      if (!nextById.has(tab.id)) {
        closeTab(tab.id);
        setLoadingFiles(prev => prev.filter(id => id !== tab.id));
      }
    });

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

    if (nextTabs.length === 0 && workspace.openTabs.length > 0) {
      closeAllTabs();
      setLoadingFiles([]);
    }
  }, [closeAllTabs, closeTab, fileEditor, workspace.openTabs]);

  const handleActiveTabChange = useCallback((tabId: string | null) => {
    if (!tabId) return;
    switchToTab(tabId);
    actions.selectFile(tabId);
  }, [actions, switchToTab]);

  if (workspace.openTabs.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <div className="text-center">
          <FileText className="mx-auto mb-4 h-12 w-12 opacity-50" />
          <div className="text-sm">{t('workspace.fileManagement.editor.emptyState.title')}</div>
        </div>
      </div>
    );
  }

  return (
    <FileViewerWorkbench
      tabs={workbenchTabs}
      activeTabId={workspace.activeTabId}
      adapter={workbenchAdapter}
      capabilities={{
        canEdit: true,
        canSave: true,
        canReadBlob: true,
        canPreviewDrawio: true,
        canCopyPath: true,
        canRevealInTree: true,
        canCloseTabs: true,
      }}
      isExpanded={isFocusMode}
      onExpandedChange={toggleFileManagementEditorExpanded}
      useViewportExpansion={false}
      hideChromeWhenExpanded
      renderFocusToolbar={({ actions: focusActions, icon, metadata, subtitle, title }) => (
        <FileFocusToolbar
          icon={icon ?? getFileIcon(activeTab?.name ?? '')}
          title={title}
          subtitle={subtitle}
          metadata={metadata}
          actions={focusActions}
          exitLabel={t('workspace.fileManagement.focus.exit')}
          onExit={toggleFileManagementEditorExpanded}
        />
      )}
      onTabsChange={handleTabsChange}
      onActiveTabChange={handleActiveTabChange}
    />
  );
};
