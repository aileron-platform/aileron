import React from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Database, Eye, EyeOff, Folder, RefreshCw } from 'lucide-react';
import {
  ArchiveProgressOverlays,
  FileConflictDialog,
  FileTreeContextMenu,
  FileTreePanel,
  FileManagementDialogs,
  FileManagementSidebarWorkflow,
  buildArchiveProgressFromStatus,
  createFileTreeResourceIdentity,
  composeFileConflictTransports,
  createLocalFileConflictTransport,
  findLatestPersistedArchiveOperation,
  getFileOperationResponseRevision,
  loadPersistedArchiveOperations,
  markPersistedArchiveDownloadTriggered,
  removePersistedArchiveOperation,
  removePersistedArchiveOperationsForContext,
  toFileWorkbenchTab,
  toFileManagementDialogState,
  upsertPersistedArchiveOperation,
  useFileManagementContextMenuBuilder,
  useFileConflictController,
  useFileOperationsWithDialog,
  useFileTreeManager,
  type ArchiveProgressState,
  type FileManagementSidebarInteractionState,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { createKnowledgeBaseFileWorkbenchAdapter } from '../adapters/file-workbench/knowledgeBaseFileWorkbenchAdapter';
import { createKnowledgeBaseFileConflictTransport } from '../adapters/file-workbench/knowledgeBaseFileConflictTransport';
import {
  createKnowledgeBaseFileTreeDataAdapter,
} from '../adapters/file-workbench/knowledgeBaseFileTreeDataAdapter';
import {
  FileViewerWorkbench,
  type FileViewerWorkbenchTab,
} from '@/shared/components/file-workbench/viewer-entry';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import {
  buildKnowledgeBaseFileDownloadUrl,
  downloadKnowledgeBaseArchiveBlob,
  fetchKnowledgeBaseArchiveDownloadStatus,
  startKnowledgeBaseArchiveDownload,
} from '../api/knowledgeBaseApi';
import type { KnowledgeBaseFileConflictPayload } from '../api/knowledgeBaseApi';
import { useKnowledgeBaseVersionControlSession } from '@/shared/version-control';
import {
  KNOWLEDGE_BASE_FILE_ROOT_PATH,
  getKnowledgeBaseFileName,
  getKnowledgeBaseFileParentPath,
  getKnowledgeBaseFileTargetPath,
  isKnowledgeBaseFileContentConflictError,
  joinKnowledgeBaseFilePath,
} from '../model/knowledgeBaseFileModel';
import { KNOWLEDGE_BASE_ARCHIVE_OPERATIONS_STORAGE_KEY } from '../model/knowledgeBaseArchivePersistence';

interface KnowledgeBaseFilesTabProps {
  knowledgeBaseId: string;
  canWrite: boolean;
  renderRegions?: (regions: KnowledgeBaseFilesTabRegions) => React.ReactNode;
}

export interface KnowledgeBaseFilesTabRegions {
  navigator: React.ReactNode;
  navigatorActions: React.ReactNode;
  main: React.ReactNode;
}

const ARCHIVE_STORAGE_KEY = KNOWLEDGE_BASE_ARCHIVE_OPERATIONS_STORAGE_KEY;

interface KnowledgeBaseArchiveContext {
  knowledgeBaseId: string;
}

export const KnowledgeBaseFilesTab: React.FC<KnowledgeBaseFilesTabProps> = ({
  knowledgeBaseId,
  canWrite,
  renderRegions,
}) => {
  const { toast } = useToast();
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [isExternalDragActive, setIsExternalDragActive] = React.useState(false);
  const [showHiddenEntries, setShowHiddenEntries] = React.useState(false);
  const [isWorkbenchExpanded, setIsWorkbenchExpanded] = React.useState(false);
  const [clipboardItem, setClipboardItem] = React.useState<{ path: string; type: 'file' | 'directory' } | null>(null);
  const [archiveProgress, setArchiveProgress] = React.useState<ArchiveProgressState | null>(null);
  const dragDepthRef = React.useRef(0);
  const completedFileConflictOperationRef = React.useRef<'upload' | 'paste' | 'extract' | 'create' | 'move' | null>(null);
  const destinationConflictRef = React.useRef<{ operation: 'create' | 'move'; sourcePath?: string } | null>(null);
  const canWriteRef = React.useRef(canWrite);
  const writeOperationGenerationRef = React.useRef(0);
  const mountedRef = React.useRef(true);
  React.useLayoutEffect(() => {
    if (canWriteRef.current !== canWrite) {
      canWriteRef.current = canWrite;
      writeOperationGenerationRef.current += 1;
    }
  }, [canWrite]);
  const isWriteOperationActive = React.useCallback((generation: number) => (
    mountedRef.current
    && canWriteRef.current
    && writeOperationGenerationRef.current === generation
  ), []);

  React.useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      writeOperationGenerationRef.current += 1;
    };
  }, []);

  const fileTreeAdapter = React.useMemo(
    () => createKnowledgeBaseFileTreeDataAdapter({
      knowledgeBaseId,
      includeHidden: showHiddenEntries,
    }),
    [knowledgeBaseId, showHiddenEntries],
  );
  const resourceIdentity = React.useMemo(
    () => createFileTreeResourceIdentity('knowledge-base', {
      knowledgeBaseId,
      includeHidden: showHiddenEntries,
    }),
    [knowledgeBaseId, showHiddenEntries],
  );

  const manager = useFileTreeManager({
    adapter: fileTreeAdapter,
    resourceIdentity,
    autoLoad: false,
  });
  const versionControl = useKnowledgeBaseVersionControlSession({ knowledgeBaseId, isGitRepo: true });
  const localFileConflictTransport = React.useMemo(() => createLocalFileConflictTransport<KnowledgeBaseFileConflictPayload>({
    findEntry: (path) => manager.state.flatNodes.find((node) => node.path === path) ?? null,
    refreshTree: manager.loadTree,
    createEntry: (path, entryType, content) => entryType === 'directory'
      ? manager.operations.createDirectory(path)
      : manager.operations.createFile(path, content),
    moveEntry: manager.operations.moveFile,
    deleteEntry: manager.operations.deleteFile,
    getPayload: (payload) => payload,
  }), [manager.loadTree, manager.operations, manager.state.flatNodes]);
  const fileConflictTransport = React.useMemo(() => composeFileConflictTransports(
    createKnowledgeBaseFileConflictTransport(knowledgeBaseId),
    localFileConflictTransport,
  ), [knowledgeBaseId, localFileConflictTransport]);

  const showErrorToast = React.useCallback((error: unknown, fallback: string) => {
    const message = error instanceof Error ? error.message : fallback;
    toast({
      title: fallback,
      description: message,
      variant: 'destructive',
    });
  }, [toast]);

  const fileConflictController = useFileConflictController({
    transport: fileConflictTransport,
    onCompleted: (result) => {
      const operation = completedFileConflictOperationRef.current;
      completedFileConflictOperationRef.current = null;
      const destinationOperation = destinationConflictRef.current;
      destinationConflictRef.current = null;
      const successfulItems = result.items.filter((item) => (
        item.finalPath !== null
        && ['created', 'kept-both', 'replaced', 'merged'].includes(item.status)
      ));
      const finalItem = successfulItems[0];
      const replacedPaths = successfulItems
        .filter((item) => item.status === 'replaced' && item.finalPath)
        .map((item) => item.finalPath!);

      void (async () => {
        const destinationItem = successfulItems[0];
        if (
          destinationOperation?.operation === 'move'
          && destinationOperation.sourcePath
          && destinationItem?.finalPath
          && result.failed === 0
        ) {
          manager.editor.remapPath(destinationOperation.sourcePath, destinationItem.finalPath);
        }
        await Promise.allSettled([
          manager.loadTree(),
          versionControl.refresh(queryClient, ['changes', 'history']),
        ]);
        await Promise.all(replacedPaths.map((path) => manager.reloadFileTab(path)));

        result.items
          .filter((item) => item.status === 'failed')
          .forEach((item) => {
            toast({
              title: t('common.fileOperations.error.fileOperationFailed'),
              description: item.error ?? item.sourcePath,
              variant: 'destructive',
            });
          });

        if (finalItem?.finalPath && result.failed === 0 && destinationOperation?.operation !== 'move') {
          manager.state.selectNode(finalItem.finalPath);
          if (finalItem.type === 'file') void manager.handleFileSelect({
            id: finalItem.finalPath,
            name: getKnowledgeBaseFileName(finalItem.finalPath),
            path: finalItem.finalPath,
            type: 'file',
          });
        }
        if (result.failed === 0 && operation === 'paste') setClipboardItem(null);
      })();
    },
    onError: (error, stage) => {
      completedFileConflictOperationRef.current = null;
      destinationConflictRef.current = null;
      if (stage === 'execute') return;
      showErrorToast(error, t('knowledgeBase.files.operationFailedTitle'));
    },
    onCancelled: () => {
      completedFileConflictOperationRef.current = null;
      destinationConflictRef.current = null;
    },
  });

  const triggerArchiveBrowserDownload = React.useCallback(async (
    downloadUrl: string,
    operationId: string,
    archiveName?: string,
  ): Promise<boolean> => {
    const generation = writeOperationGenerationRef.current;
    if (!isWriteOperationActive(generation)) {
      return false;
    }
    try {
      const blob = await downloadKnowledgeBaseArchiveBlob(knowledgeBaseId, downloadUrl);
      if (!isWriteOperationActive(generation)) {
        return false;
      }
      const objectUrl = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = archiveName ?? 'archive.zip';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(objectUrl);
      markPersistedArchiveDownloadTriggered(ARCHIVE_STORAGE_KEY, operationId);
      return true;
    } catch (error) {
      if (!isWriteOperationActive(generation)) {
        return false;
      }
      toast({
        title: t('workspace.fileManagement.tree.notifications.downloadFailed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
      return false;
    }
  }, [isWriteOperationActive, knowledgeBaseId, t, toast]);

  const waitForArchiveCompletion = React.useCallback(async (
    operationId: string,
    options?: { restored?: boolean },
  ) => {
    const generation = writeOperationGenerationRef.current;
    if (!isWriteOperationActive(generation)) {
      return;
    }
    for (let attempt = 0; attempt < 120; attempt += 1) {
      if (!isWriteOperationActive(generation)) {
        return;
      }
      const status = await fetchKnowledgeBaseArchiveDownloadStatus(knowledgeBaseId, operationId);
      if (!isWriteOperationActive(generation)) {
        return;
      }
      setArchiveProgress(current => current
        ? buildArchiveProgressFromStatus({ current, status })
        : current);

      if (status.status === 'completed' && status.result) {
        toast({
          title: t('shared.fileWorkbench.archive.ready'),
          description: t('shared.fileWorkbench.archive.readyDescription', {
            name: status.result.archiveName,
          }),
        });
        const persisted = loadPersistedArchiveOperations(ARCHIVE_STORAGE_KEY)
          .find((item) => item.operationId === operationId);
        const downloadTriggered = persisted?.downloadTriggeredAt
          ? true
          : await triggerArchiveBrowserDownload(
            status.result.downloadUrl,
            operationId,
            status.result.archiveName,
          );
        if (downloadTriggered && !options?.restored) {
          window.setTimeout(() => {
            if (isWriteOperationActive(generation)) {
              removePersistedArchiveOperation(ARCHIVE_STORAGE_KEY, operationId);
              setArchiveProgress(null);
            }
          }, 3000);
        }
        return;
      }

      if (status.status === 'failed' || status.status === 'expired') {
        removePersistedArchiveOperation(ARCHIVE_STORAGE_KEY, operationId);
        toast({
          title: status.status === 'expired'
            ? t('workspace.fileManagement.tree.notifications.archiveExpired')
            : t('workspace.fileManagement.tree.notifications.archiveFailed'),
          description: status.error ?? status.message,
          variant: 'destructive',
        });
        return;
      }

      await new Promise(resolve => globalThis.setTimeout(resolve, 1000));
    }

    if (!isWriteOperationActive(generation)) {
      return;
    }
    toast({
      title: t('workspace.fileManagement.tree.notifications.archiveFailed'),
      description: t('common.messages.cannotGetSyncStatus'),
      variant: 'destructive',
    });
  }, [isWriteOperationActive, knowledgeBaseId, t, toast, triggerArchiveBrowserDownload]);

  React.useEffect(() => {
    const archiveContext = { knowledgeBaseId } satisfies KnowledgeBaseArchiveContext;
    if (!canWrite) {
      removePersistedArchiveOperationsForContext({
        storageKey: ARCHIVE_STORAGE_KEY,
        context: archiveContext,
      });
      setArchiveProgress(null);
      return;
    }

    const persisted = findLatestPersistedArchiveOperation({
      storageKey: ARCHIVE_STORAGE_KEY,
      context: archiveContext,
    });
    if (!persisted || archiveProgress) {
      return;
    }

    let cancelled = false;
    const restore = async () => {
      try {
        const status = await fetchKnowledgeBaseArchiveDownloadStatus(knowledgeBaseId, persisted.operationId);
        if (cancelled || !canWriteRef.current) {
          return;
        }
        setArchiveProgress(buildArchiveProgressFromStatus({
          current: {
            operationId: persisted.operationId,
            archiveName: persisted.archiveName,
            paths: persisted.paths,
            status: 'pending',
            progress: 0,
            message: '',
            downloadUrl: null,
            errorMessage: null,
          },
          status,
        }));
        if (status.status === 'completed' && status.result) {
          if (!persisted.downloadTriggeredAt) {
            await triggerArchiveBrowserDownload(
              status.result.downloadUrl,
              persisted.operationId,
              status.result.archiveName,
            );
          }
          return;
        }
        if (status.status === 'failed' || status.status === 'expired') {
          removePersistedArchiveOperation(ARCHIVE_STORAGE_KEY, persisted.operationId);
          return;
        }
        void waitForArchiveCompletion(persisted.operationId, { restored: true });
      } catch {
        if (!cancelled && canWriteRef.current) {
          removePersistedArchiveOperation(ARCHIVE_STORAGE_KEY, persisted.operationId);
          setArchiveProgress(null);
        }
      }
    };

    void restore();
    return () => {
      cancelled = true;
    };
  }, [
    archiveProgress,
    canWrite,
    knowledgeBaseId,
    triggerArchiveBrowserDownload,
    waitForArchiveCompletion,
  ]);

  const uploadFilesToPath = React.useCallback(async (files: File[], targetPath: string) => {
    const generation = writeOperationGenerationRef.current;
    if (!isWriteOperationActive(generation) || files.length === 0) {
      return;
    }

    completedFileConflictOperationRef.current = 'upload';
    await fileConflictController.start({
      operation: 'upload',
      targetPath,
      sources: files.map((file) => ({ sourcePath: file.name, entryType: 'file' })),
      archivePath: null,
    }, { files });
  }, [fileConflictController, isWriteOperationActive]);

  const handleUpload = React.useCallback((targetPath = KNOWLEDGE_BASE_FILE_ROOT_PATH) => {
    if (!canWrite) {
      return;
    }
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = async (event) => {
      const files = (event.target as HTMLInputElement).files;
      if (!files || files.length === 0) {
        return;
      }

      await uploadFilesToPath(Array.from(files), targetPath);
    };
    input.click();
  }, [canWrite, uploadFilesToPath]);

  const handleSave = React.useCallback(async (path: string, content: string) => {
    if (!canWrite) {
      return;
    }
    try {
      const tab = manager.editor.getTab(path);
      const response = await manager.operations.updateFile(path, content, {
        revision: tab?.revision,
      });
      manager.editor.saveTab(path, content, getFileOperationResponseRevision(response));
      toast({
        title: t('knowledgeBase.files.saveSuccessTitle'),
        description: path,
      });
    } catch (error) {
      showErrorToast(error, t(isKnowledgeBaseFileContentConflictError(error)
        ? 'knowledgeBase.files.saveConflict'
        : 'knowledgeBase.files.saveFailed'));
      throw error;
    }
  }, [canWrite, manager, showErrorToast, t, toast]);

  React.useEffect(() => {
    if (!canWrite) {
      return;
    }
    const handleKeyDown = async (event: KeyboardEvent) => {
      const isMod = event.ctrlKey || event.metaKey;
      if (!isMod) {
        return;
      }

      if (event.shiftKey && event.key === 's') {
        event.preventDefault();
        const modifiedTabs = manager.editor.tabs.filter((tab) => tab.isModified);
        for (const tab of modifiedTabs) {
          await handleSave(tab.path, tab.content);
        }
        return;
      }

      if (event.key === 's') {
        event.preventDefault();
        const activeTab = manager.editor.activeTab;
        if (activeTab?.isModified) {
          await handleSave(activeTab.path, activeTab.content);
        }
        return;
      }

      if (event.altKey && event.key === 'z') {
        event.preventDefault();
        const activeTab = manager.editor.activeTab;
        if (activeTab?.isModified) {
          manager.editor.revertTab(activeTab.path);
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [canWrite, handleSave, manager.editor]);

  const fileOps = useFileOperationsWithDialog({
    onCreateFile: async (name, parentPath = KNOWLEDGE_BASE_FILE_ROOT_PATH) => {
      if (!canWrite) {
        return;
      }
      const fullPath = joinKnowledgeBaseFilePath(parentPath, name);
      destinationConflictRef.current = { operation: 'create' };
      completedFileConflictOperationRef.current = 'create';
      const result = await fileConflictController.start({
        operation: 'create',
        targetPath: fullPath,
        sources: [{ sourcePath: fullPath, entryType: 'file' }],
        archivePath: null,
      }, { files: [], sourcePath: fullPath, entryType: 'file', content: '' });
      if (!result) return { suppressSuccessToast: true };
    },
    onCreateFolder: async (name, parentPath = KNOWLEDGE_BASE_FILE_ROOT_PATH) => {
      if (!canWrite) {
        return;
      }
      const fullPath = joinKnowledgeBaseFilePath(parentPath, name);
      destinationConflictRef.current = { operation: 'create' };
      completedFileConflictOperationRef.current = 'create';
      const result = await fileConflictController.start({
        operation: 'create',
        targetPath: fullPath,
        sources: [{ sourcePath: fullPath, entryType: 'directory' }],
        archivePath: null,
      }, { files: [], sourcePath: fullPath, entryType: 'directory', content: '' });
      if (!result) return { suppressSuccessToast: true };
    },
    onRename: async (oldPath, newName) => {
      if (!canWrite) {
        return;
      }
      const parentPath = oldPath.split('/').slice(0, -1).join('/') || KNOWLEDGE_BASE_FILE_ROOT_PATH;
      const newPath = joinKnowledgeBaseFilePath(parentPath, newName);
      const sourceNode = manager.state.flatNodes.find((node) => node.path === oldPath);
      if (!sourceNode) return;
      destinationConflictRef.current = { operation: 'move', sourcePath: oldPath };
      completedFileConflictOperationRef.current = 'move';
      const result = await fileConflictController.start({
        operation: 'move',
        targetPath: newPath,
        sources: [{ sourcePath: oldPath, entryType: sourceNode.type }],
        archivePath: null,
      }, { files: [], sourcePath: oldPath, entryType: sourceNode.type });
      if (!result) return { suppressSuccessToast: true };
    },
    onDelete: async (path, node) => {
      if (!canWrite) {
        return;
      }
      const response = await manager.deleteFileAndCloseTab(path, node?.type === 'directory');
      if (!response.success) {
        throw new Error(response.error || response.message || t('common.fileOperations.error.fileOperationFailed'));
      }
      manager.state.clearSelection();
    },
    onBatchDelete: async (paths) => {
      if (!canWrite) {
        return;
      }
      const response = await manager.batchDeleteAndCloseTabs(paths, true);
      response.failed.forEach((failure) => {
        toast({
          title: t('common.fileOperations.error.fileOperationFailed'),
          description: `${failure.path}: ${failure.error}`,
          variant: 'destructive',
        });
      });
      if (response.failedCount === 0) manager.state.clearSelection();
      if (response.failedCount > 0) return { suppressSuccessToast: true };
    },
  });
  const { closeDialog: closeFileDialog } = fileOps;

  React.useEffect(() => {
    if (!canWrite) {
      closeFileDialog();
      setClipboardItem(null);
    }
  }, [canWrite, closeFileDialog]);

  const sharedDialogState = toFileManagementDialogState(fileOps.dialogState);

  const getAffectedUnsavedTabsCount = React.useCallback((paths: string[]) => (
    manager.editor.tabs.filter((tab) => tab.isModified && paths.some((path) => (
      tab.path === path || tab.path.startsWith(`${path.replace(/\/$/, '')}/`)
    ))).length
  ), [manager.editor.tabs]);

  const handleNodeClick = React.useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);

    if (node.type === 'file' && modifier === 'none') {
      void manager.handleFileSelect(node);
    }
  }, [manager]);

  const handleNodeDoubleClick = React.useCallback((node: FileTreeNode) => {
    void manager.handleFileDoubleClick(node);
  }, [manager]);

  const handleContextMenu = React.useCallback((node: FileTreeNode, event: React.MouseEvent) => {
    manager.state.openContextMenu(event.clientX, event.clientY, node);
  }, [manager.state]);

  const handleMove = React.useCallback(async (sourcePath: string, destinationDirectory: string) => {
    if (!canWrite) {
      return;
    }
    const targetPath = joinKnowledgeBaseFilePath(destinationDirectory, sourcePath.split('/').pop() || sourcePath);
    if (sourcePath === targetPath || destinationDirectory.startsWith(`${sourcePath}/`)) {
      return;
    }

    try {
      const sourceNode = manager.state.flatNodes.find((node) => node.path === sourcePath);
      if (!sourceNode) return;
      destinationConflictRef.current = { operation: 'move', sourcePath };
      completedFileConflictOperationRef.current = 'move';
      await fileConflictController.start({
        operation: 'move',
        targetPath,
        sources: [{ sourcePath, entryType: sourceNode.type }],
        archivePath: null,
      }, { files: [], sourcePath, entryType: sourceNode.type });
    } catch (error) {
      showErrorToast(error, t('knowledgeBase.files.moveFailed'));
    }
  }, [canWrite, fileConflictController, manager.state.flatNodes, showErrorToast, t]);

  const handleCopy = React.useCallback((node: FileTreeNode) => {
    if (!canWrite) {
      return;
    }
    setClipboardItem({ path: node.path, type: node.type });
    toast({
      title: t('knowledgeBase.files.copySuccessTitle'),
      description: t('knowledgeBase.files.copySuccessDescription', { path: node.path }),
    });
  }, [canWrite, t, toast]);

  const handleCopyPath = React.useCallback(async (path: string) => {
    try {
      await navigator.clipboard.writeText(path);
      toast({
        title: t('knowledgeBase.files.copyPathSuccessTitle'),
        description: path,
      });
    } catch (error) {
      showErrorToast(error, t('knowledgeBase.files.copyPathFailed'));
    }
  }, [showErrorToast, t, toast]);

  const workbenchTabs = React.useMemo(
    () => manager.editor.tabs.map((tab): FileViewerWorkbenchTab => toFileWorkbenchTab(tab)),
    [manager.editor.tabs],
  );

  const workbenchAdapter = React.useMemo(() => createKnowledgeBaseFileWorkbenchAdapter({
    knowledgeBaseId,
    readFile: async (path) => (await manager.operations.readFile(path)).content,
    saveFile: handleSave,
    copyPath: handleCopyPath,
    revealInTree: (path) => {
      manager.state.selectNode(path);
    },
  }), [handleCopyPath, handleSave, knowledgeBaseId, manager.operations, manager.state]);

  const handleWorkbenchTabsChange = React.useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    const nextPaths = new Set(nextTabs.map((tab) => tab.path));

    manager.editor.tabs.forEach((tab) => {
      if (!nextPaths.has(tab.path)) {
        manager.editor.closeTab(tab.path);
      }
    });

    nextTabs.forEach((nextTab) => {
      const currentTab = manager.editor.getTab(nextTab.path);
      if (!currentTab) {
        return;
      }

      if (canWrite && currentTab.content !== nextTab.content) {
        manager.editor.updateContent(nextTab.path, nextTab.content);
      }

      if (canWrite && !nextTab.isModified && currentTab.isModified) {
        manager.editor.saveTab(nextTab.path, nextTab.content);
      }
    });
  }, [canWrite, manager.editor]);

  const handleWorkbenchActiveTabChange = React.useCallback((tabId: string | null) => {
    if (tabId) {
      manager.editor.setActiveTab(tabId);
    }
  }, [manager.editor]);

  const handlePaste = React.useCallback(async () => {
    if (!canWrite) {
      return;
    }
    const targetNode = manager.state.contextMenu?.node;
    if (!clipboardItem || !targetNode) {
      return;
    }

    const targetDirectory = targetNode.type === 'directory'
      ? targetNode.path
      : getKnowledgeBaseFileParentPath(targetNode.path);
    completedFileConflictOperationRef.current = 'paste';
    await fileConflictController.start({
      operation: 'paste',
      targetPath: targetDirectory,
      sources: [{ sourcePath: clipboardItem.path, entryType: clipboardItem.type }],
      archivePath: null,
    }, {});
  }, [canWrite, clipboardItem, fileConflictController, manager.state.contextMenu]);

  const handleExtractArchive = React.useCallback(async (node: FileTreeNode) => {
    if (!isWriteOperationActive(writeOperationGenerationRef.current)) {
      return;
    }
    completedFileConflictOperationRef.current = 'extract';
    await fileConflictController.start({
      operation: 'extract',
      targetPath: getKnowledgeBaseFileParentPath(node.path),
      sources: null,
      archivePath: node.path,
    }, {});
  }, [
    fileConflictController,
    isWriteOperationActive,
  ]);

  const handleDownloadEntries = React.useCallback(async (node: FileTreeNode, paths: string[]) => {
    const selectedPaths = Array.from(new Set(paths.length > 0 ? paths : [node.path]));
    const shouldArchive = node.type === 'directory' || selectedPaths.length > 1;
    const generation = writeOperationGenerationRef.current;
    if (shouldArchive && !isWriteOperationActive(generation)) {
      return;
    }

    try {
      if (!shouldArchive) {
        window.open(buildKnowledgeBaseFileDownloadUrl(knowledgeBaseId, node.path), '_blank', 'noopener,noreferrer');
        toast({
          title: t('workspace.fileManagement.tree.notifications.downloadSuccess'),
          description: t('workspace.fileManagement.tree.notifications.downloadSuccessDescription', { count: 1 }),
        });
        return;
      }

      const archiveName = selectedPaths.length === 1
        ? `${node.name.replace(/\.zip$/i, '')}.zip`
        : undefined;
      const accepted = await startKnowledgeBaseArchiveDownload(knowledgeBaseId, {
        paths: selectedPaths,
        archiveName,
      });
      if (!isWriteOperationActive(generation)) {
        return;
      }
      const resolvedArchiveName = archiveName ?? 'knowledge-base-selection.zip';

      upsertPersistedArchiveOperation(ARCHIVE_STORAGE_KEY, {
        operationId: accepted.operationId,
        archiveName: resolvedArchiveName,
        paths: selectedPaths,
        context: { knowledgeBaseId } satisfies KnowledgeBaseArchiveContext,
        startedAt: accepted.startedAt,
      });
      setArchiveProgress({
        operationId: accepted.operationId,
        archiveName: resolvedArchiveName,
        paths: selectedPaths,
        status: accepted.status,
        progress: 0,
        message: accepted.message,
        downloadUrl: null,
        errorMessage: null,
      });
      toast({
        title: t('workspace.fileManagement.tree.notifications.archiveStarted'),
        description: resolvedArchiveName,
      });
      await waitForArchiveCompletion(accepted.operationId);
    } catch (error) {
      if (shouldArchive && !isWriteOperationActive(generation)) {
        return;
      }
      toast({
        title: shouldArchive
          ? t('workspace.fileManagement.tree.notifications.archiveFailed')
          : t('workspace.fileManagement.tree.notifications.downloadFailed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
    }
  }, [
    isWriteOperationActive,
    knowledgeBaseId,
    t,
    toast,
    waitForArchiveCompletion,
  ]);

  const handleDragStart = React.useCallback((
    node: FileTreeNode,
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    interactionState.setDraggingPath(node.path);
  }, []);

  const handleDragEnd = React.useCallback((
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    interactionState.setDraggingPath(null);
    interactionState.setDragOverPath(null);
  }, []);

  const handleDragOverNode = React.useCallback((
    node: FileTreeNode,
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    interactionState.setDragOverPath(node.path);
  }, []);

  const handleDragLeaveNode = React.useCallback((
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    interactionState.setDragOverPath(null);
  }, []);

  const handleDropOnNode = React.useCallback(async (
    node: FileTreeNode,
    event: React.DragEvent,
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    if (!canWrite) {
      return;
    }
    interactionState.setDragOverPath(null);
    interactionState.setDraggingPath(null);

    const externalFiles = Array.from(event.dataTransfer.files ?? []);
    if (externalFiles.length > 0) {
      await uploadFilesToPath(externalFiles, getKnowledgeBaseFileTargetPath(node));
      return;
    }

    const sourcePath = event.dataTransfer.getData('text/plain');
    if (!sourcePath || node.type !== 'directory' || sourcePath === node.path) {
      return;
    }

    await handleMove(sourcePath, node.path);
  }, [canWrite, handleMove, uploadFilesToPath]);

  const handleExternalDragEnter = React.useCallback((event: React.DragEvent<HTMLDivElement>) => {
    if (!canWrite) {
      return;
    }
    if (!Array.from(event.dataTransfer.types).includes('Files')) {
      return;
    }

    dragDepthRef.current += 1;
    setIsExternalDragActive(true);
    event.preventDefault();
  }, [canWrite]);

  const handleExternalDragOver = React.useCallback((event: React.DragEvent<HTMLDivElement>) => {
    if (!canWrite) {
      return;
    }
    if (!Array.from(event.dataTransfer.types).includes('Files')) {
      return;
    }

    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  }, [canWrite]);

  const handleExternalDragLeave = React.useCallback(() => {
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsExternalDragActive(false);
    }
  }, []);

  const handleExternalDrop = React.useCallback(async (event: React.DragEvent<HTMLDivElement>) => {
    if (!canWrite) {
      return;
    }
    event.preventDefault();
    dragDepthRef.current = 0;
    setIsExternalDragActive(false);

    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length > 0) {
      await uploadFilesToPath(files, KNOWLEDGE_BASE_FILE_ROOT_PATH);
    }
  }, [canWrite, uploadFilesToPath]);

  const selectedNodes = React.useMemo(() => (
    Array.from(manager.state.selectedIds)
      .map((path) => manager.state.flatNodes.find((node) => node.path === path))
      .filter((node): node is FileTreeNode => Boolean(node))
  ), [manager.state.flatNodes, manager.state.selectedIds]);

  const getDirectoryNodeForPath = React.useCallback((path: string): FileTreeNode | undefined => (
    manager.state.flatNodes.find((node) => node.path === path && node.type === 'directory')
  ), [manager.state.flatNodes]);

  const getPrimaryTargetDirectoryNode = React.useCallback((): FileTreeNode | undefined => {
    if (selectedNodes.length !== 1) {
      return undefined;
    }

    const [selectedNode] = selectedNodes;
    if (selectedNode.type === 'directory') {
      return selectedNode;
    }

    return getDirectoryNodeForPath(getKnowledgeBaseFileParentPath(selectedNode.path));
  }, [getDirectoryNodeForPath, selectedNodes]);

  const handleToolbarCreateFile = React.useCallback(() => {
    if (!canWrite) {
      return;
    }
    fileOps.openCreateFileDialog(getPrimaryTargetDirectoryNode());
  }, [canWrite, fileOps, getPrimaryTargetDirectoryNode]);

  const handleToolbarCreateFolder = React.useCallback(() => {
    if (!canWrite) {
      return;
    }
    fileOps.openCreateFolderDialog(getPrimaryTargetDirectoryNode());
  }, [canWrite, fileOps, getPrimaryTargetDirectoryNode]);

  const handleToolbarUpload = React.useCallback(() => {
    if (!canWrite) {
      return;
    }
    handleUpload(getPrimaryTargetDirectoryNode()?.path ?? KNOWLEDGE_BASE_FILE_ROOT_PATH);
  }, [canWrite, getPrimaryTargetDirectoryNode, handleUpload]);

  const handleToggleHiddenEntries = React.useCallback(() => {
    setShowHiddenEntries((current) => !current);
  }, []);

  const contextMenuItems = useFileManagementContextMenuBuilder({
    node: manager.state.contextMenu?.node ?? null,
    selectedIds: manager.state.selectedIds,
    clipboardItem,
    readOnly: !canWrite,
    features: {
      open: true,
      upload: true,
      createFile: true,
      createFolder: true,
      copy: true,
      copyPath: true,
      download: true,
      paste: true,
      rename: true,
      delete: true,
      refresh: true,
      extractArchive: true,
    },
    callbacks: {
      onOpen: (node) => {
        void manager.handleFileSelect(node);
      },
      onUpload: () => handleUpload(getKnowledgeBaseFileTargetPath(manager.state.contextMenu?.node)),
      onCreateFile: () => fileOps.openCreateFileDialog(manager.state.contextMenu?.node ?? undefined),
      onCreateFolder: () => fileOps.openCreateFolderDialog(manager.state.contextMenu?.node ?? undefined),
      onCopy: handleCopy,
      onCopyPath: (path) => {
        void handleCopyPath(path);
      },
      onDownload: (node, paths) => {
        void handleDownloadEntries(node, paths);
      },
      onPaste: () => {
        void handlePaste();
      },
      onRename: (node) => fileOps.openRenameDialog(node),
      onDelete: (node) => fileOps.openDeleteDialog(node),
      onBatchDelete: () => fileOps.openBatchDeleteDialog(selectedNodes),
      onRefresh: () => {
        void manager.loadTree();
      },
      onExtractArchive: (node) => {
        void handleExtractArchive(node);
      },
      onClose: manager.state.closeContextMenu,
    },
    t,
  });

  const navigatorActions = (
    <Button
      type="button"
      size="sm"
      variant="ghost"
      className="h-7 w-7 p-0"
      onClick={() => { void manager.loadTree(); }}
      disabled={manager.state.isLoading}
      title={t('knowledgeBase.files.actions.refresh')}
      aria-label={t('knowledgeBase.files.actions.refresh')}
    >
      <RefreshCw className={cn('h-3.5 w-3.5', manager.state.isLoading && 'animate-spin')} />
    </Button>
  );

  const navigatorContent = (
    <div
      data-testid="kb-files-tree"
      className="flex h-full min-h-0 flex-col"
      onDragEnter={canWrite ? handleExternalDragEnter : undefined}
      onDragOver={canWrite ? handleExternalDragOver : undefined}
      onDragLeave={canWrite ? handleExternalDragLeave : undefined}
      onDrop={canWrite ? handleExternalDrop : undefined}
    >
            <FileManagementSidebarWorkflow
              manager={manager}
              title={t('knowledgeBase.files.toolbarTitle')}
              searchPlaceholder={t('knowledgeBase.files.toolbarTitle')}
              headerIcon={Database}
              showHeader={false}
              capabilities={{
                canCreateFile: canWrite,
                canCreateFolder: canWrite,
                canUpload: canWrite,
              }}
              toolbarRightContent={(
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  onClick={handleToggleHiddenEntries}
                  disabled={manager.state.isLoading}
                  title={t(
                    showHiddenEntries
                      ? 'knowledgeBase.files.actions.hidden.hideTooltip'
                      : 'knowledgeBase.files.actions.hidden.showTooltip'
                  )}
                  aria-label={t(
                    showHiddenEntries
                      ? 'knowledgeBase.files.actions.hidden.hideLabel'
                      : 'knowledgeBase.files.actions.hidden.showLabel'
                  )}
                >
                  {showHiddenEntries ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </Button>
              )}
              isCollapsed={false}
              onToggleCollapse={() => undefined}
              loadEnabled={true}
              onCreateFile={handleToolbarCreateFile}
              onCreateFolder={handleToolbarCreateFolder}
              onUpload={handleToolbarUpload}
              renderBody={({ interactionState }) => (
                <>
                  <FileTreePanel
                    state={manager.state}
                    onNodeClick={handleNodeClick}
                    onNodeDoubleClick={handleNodeDoubleClick}
                    onContextMenu={handleContextMenu}
                    onDragStart={canWrite
                      ? (node) => handleDragStart(node, interactionState)
                      : undefined}
                    onDragEnd={canWrite
                      ? () => handleDragEnd(interactionState)
                      : undefined}
                    onDragOver={canWrite
                      ? (node) => handleDragOverNode(node, interactionState)
                      : undefined}
                    onDragLeave={canWrite
                      ? () => handleDragLeaveNode(interactionState)
                      : undefined}
                    onDrop={canWrite
                      ? (node, event) => handleDropOnNode(node, event, interactionState)
                      : undefined}
                    onPaste={canWrite
                      ? (files) => {
                        void uploadFilesToPath(files, KNOWLEDGE_BASE_FILE_ROOT_PATH);
                      }
                      : undefined}
                    onRefresh={() => { void manager.loadTree(); }}
                    onBatchDelete={canWrite
                      ? () => fileOps.openBatchDeleteDialog(selectedNodes)
                      : undefined}
                    enableSearch={false}
                    enableToolbar={false}
                    enableMultiSelectBar={canWrite}
                    enableDragDrop={canWrite}
                    draggingPath={interactionState.draggingPath}
                    dragOverPath={interactionState.dragOverPath}
                    className="flex-1"
                  />
                  <FileTreeContextMenu
                    contextMenu={manager.state.contextMenu}
                    items={contextMenuItems}
                    onClose={manager.state.closeContextMenu}
                  />
                  {canWrite ? (
                    <ArchiveProgressOverlays
                      extractProgress={null}
                      archiveProgress={archiveProgress}
                      onArchiveDownload={({ downloadUrl, operationId, archiveName }) => {
                        void triggerArchiveBrowserDownload(downloadUrl, operationId, archiveName);
                      }}
                    />
                  ) : null}
                </>
              )}
            />
    </div>
  );

  const main = (
    <div
      className="relative flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-background"
      onDragEnter={canWrite ? handleExternalDragEnter : undefined}
      onDragOver={canWrite ? handleExternalDragOver : undefined}
      onDragLeave={canWrite ? handleExternalDragLeave : undefined}
      onDrop={canWrite ? handleExternalDrop : undefined}
    >
            <FeatureHeader title={t('knowledgeBase.navigation.files')} icon={Folder} />
            {manager.state.error && (
              <Alert variant="destructive" className="m-4 mb-0">
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>{t('knowledgeBase.files.operationFailedTitle')}</AlertTitle>
                <AlertDescription>{manager.state.error}</AlertDescription>
              </Alert>
            )}

            <div className="min-h-0 flex-1">
              <FileViewerWorkbench
                tabs={workbenchTabs}
                activeTabId={manager.editor.activeTabPath}
                adapter={workbenchAdapter}
                capabilities={{
                  canEdit: canWrite,
                  canSave: canWrite,
                  canReadBlob: true,
                  canCopyPath: true,
                  canRevealInTree: true,
                  canCloseTabs: true,
                }}
                readOnly={!canWrite}
                isExpanded={isWorkbenchExpanded}
                onExpandedChange={setIsWorkbenchExpanded}
                onTabsChange={handleWorkbenchTabsChange}
                onActiveTabChange={handleWorkbenchActiveTabChange}
              />
            </div>
      {canWrite && isExternalDragActive ? (
          <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-sky-500/10">
            <div className="rounded-xl border border-sky-300 bg-background/95 px-6 py-4 text-sm font-medium text-sky-700 shadow-lg">
              {t('knowledgeBase.files.dropOverlay')}
            </div>
          </div>
      ) : null}
    </div>
  );

  const dialogs = canWrite ? (

        <>
          <FileManagementDialogs
            dialogState={sharedDialogState}
            onClose={fileOps.closeDialog}
            onCreateFile={fileOps.handleCreateFile}
            onCreateFolder={fileOps.handleCreateFolder}
            onRename={fileOps.handleRename}
            onDelete={fileOps.handleDelete}
            onBatchDelete={fileOps.handleBatchDelete}
            getAffectedUnsavedTabsCount={getAffectedUnsavedTabsCount}
          />
          <FileConflictDialog
            open={fileConflictController.open}
            operation={fileConflictController.operation}
            conflicts={fileConflictController.conflicts}
            defaultStrategy={fileConflictController.defaultStrategy}
            itemStrategies={fileConflictController.itemStrategies}
            pending={fileConflictController.pending}
            error={fileConflictController.error}
            getAffectedUnsavedTabsCount={getAffectedUnsavedTabsCount}
            onDefaultStrategyChange={fileConflictController.setDefaultStrategy}
            onItemStrategyChange={fileConflictController.setItemStrategy}
            onCancel={fileConflictController.cancel}
            onConfirm={fileConflictController.confirm}
          />
        </>
  ) : null;

  if (renderRegions) {
    return (
      <>
        {renderRegions({ navigator: navigatorContent, navigatorActions, main })}
        {dialogs}
      </>
    );
  }

  return (
    <div className="relative flex h-full min-h-0 w-full overflow-hidden bg-background">
      <div className="flex min-h-0 shrink-0">{navigatorContent}</div>
      <div className="flex min-w-0 flex-1">{main}</div>
      {dialogs}
    </div>
  );
};
