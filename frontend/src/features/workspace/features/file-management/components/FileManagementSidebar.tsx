import React, {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('FileManagementSidebar');
import { Eye, EyeOff, Folder, FilePlus, FolderPlus, Upload } from 'lucide-react';
import {
  ArchiveProgressOverlays,
  FileConflictDialog,
  FileManagementDialogs,
  FileManagementSidebarWorkflow,
  FileTreePanel,
  FileTreeContextMenu,
  buildArchiveProgressFromStatus,
  findLatestPersistedArchiveOperation,
  loadPersistedArchiveOperations,
  markPersistedArchiveDownloadTriggered,
  removePersistedArchiveOperation,
  removePersistedArchiveOperationsForContext,
  toFileManagementDialogState,
  upsertPersistedArchiveOperation,
  createFileTreeResourceIdentity,
  composeFileConflictTransports,
  createLocalFileConflictTransport,
  useFileManagementContextMenuBuilder,
  useFileConflictController,
  useFileOperationsWithDialog,
  useFileTreeManager,
  isImageFile,
  type ArchiveProgressState,
  type FileManagementSidebarInteractionState,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { Button } from '@/shared/components/ui/button';
import { useWorkspaceVersionControlSession } from '../../../integrations/version-control/workspaceVersionControlSession';
import {
  downloadArchiveBlob,
  fetchArchiveDownloadStatus,
  startArchiveDownload,
} from '../../../api/workspaceRuntimeApi';
import type { RuntimeFileConflictPayload } from '../../../api/workspaceRuntimeApi';
import { createWorkspaceFileTreeDataAdapter } from '../adapters/workspaceFileTreeDataAdapter';
import { createWorkspaceFileConflictTransport } from '../adapters/workspaceFileConflictTransport';
import {
  createPlaceholderNode,
  getContextMenuTargetDirectory,
  getParentPath,
  getRelatedPathsForDelete,
  resolveTargetDirectory,
} from '../model/fileManagementSidebarModel';
import { ensureLeadingSlash } from '../model/filePathModel';
import { WORKSPACE_ARCHIVE_OPERATIONS_STORAGE_KEY } from '../model/workspaceArchivePersistence';
interface WorkspaceArchiveContext {
  workspaceId: string;
  contextId: string | null;
  runtimeBaseUrl: string;
}

const ARCHIVE_STORAGE_KEY = WORKSPACE_ARCHIVE_OPERATIONS_STORAGE_KEY;

interface ClipboardEntry {
  path: string;
  type: 'file' | 'directory';
}

export interface FileManagementSidebarProps {
  collapsed?: boolean;
  showHeader?: boolean;
  refreshSignal?: number;
  onRefreshingChange?: (isRefreshing: boolean) => void;
}

export const FileManagementSidebar: React.FC<FileManagementSidebarProps> = ({
  collapsed = false,
  showHeader = true,
  refreshSignal,
  onRefreshingChange,
}) => {
  const {
    workspace,
    state: workspaceState,
    dispatch,
    workspaceRuntime,
    permissions,
    fileEditor,
    openFileInTab,
    closeTab,
  } = useWorkspace();
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [clipboardItem, setClipboardItem] = useState<ClipboardEntry | null>(null);
  const [uploadTargetPath, setUploadTargetPath] = useState<string>('/');
  const [archiveProgress, setArchiveProgress] = useState<ArchiveProgressState | null>(null);
  const completedFileConflictOperationRef = useRef<'upload' | 'paste' | 'extract' | 'create' | 'move' | null>(null);
  const destinationConflictRef = useRef<{ operation: 'create' | 'move'; sourcePath?: string } | null>(null);
  const canWriteRef = useRef(permissions.canWrite);
  const writeOperationGenerationRef = useRef(0);
  const mountedRef = useRef(true);
  useLayoutEffect(() => {
    if (canWriteRef.current !== permissions.canWrite) {
      canWriteRef.current = permissions.canWrite;
      writeOperationGenerationRef.current += 1;
    }
  }, [permissions.canWrite]);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      writeOperationGenerationRef.current += 1;
    };
  }, []);
  const isWriteOperationActive = useCallback((generation: number) => (
    mountedRef.current
    && canWriteRef.current
    && writeOperationGenerationRef.current === generation
  ), []);
  const selectedGitContextId = workspaceState.versionControl.selectedGitContextId;
  const showHiddenEntries = workspaceState.fileTreeShowHiddenEntries;
  const versionControl = useWorkspaceVersionControlSession({
    workspaceId: workspaceRuntime.workspaceId ?? '',
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? '',
    contextId: selectedGitContextId,
  });

  const fileTreeAdapter = useMemo(
    () => createWorkspaceFileTreeDataAdapter({
      workspaceId: workspaceRuntime.workspaceId ?? 'pending-workspace',
      contextId: selectedGitContextId,
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl || undefined,
      includeHidden: showHiddenEntries,
    }),
    [selectedGitContextId, showHiddenEntries, workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl]
  );
  const resourceIdentity = useMemo(
    () => createFileTreeResourceIdentity('workspace', {
      workspaceId: workspaceRuntime.workspaceId ?? 'pending-workspace',
      contextId: selectedGitContextId ?? null,
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? null,
      includeHidden: showHiddenEntries,
    }),
    [selectedGitContextId, showHiddenEntries, workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl],
  );

  const manager = useFileTreeManager({
    adapter: fileTreeAdapter,
    resourceIdentity,
    stateOptions: { enableMultiSelect: true },
    autoLoad: false,
    onError: (error) => {
      const isContentConflict = (
        typeof error === 'object' &&
        error !== null &&
        (
          ('status' in error && (error as { status?: unknown }).status === 409) ||
          ('errorCode' in error && (error as { errorCode?: unknown }).errorCode === 'CONTENT_CONFLICT')
        )
      );

      toast({
        title: t(isContentConflict
          ? 'workspace.fileManagement.tree.notifications.saveConflict'
          : 'workspace.fileManagement.error.loadFailed'),
        description: error.message,
        variant: 'destructive',
      });
    },
  });

  const { state: managerState, loadTree, operations, toggleDirectory, loadingChildrenPaths } = manager;
  const currentPath = managerState.selectedId ?? workspace.activeTabId ?? '/';
  const closeContextMenu = useCallback(() => {
    managerState.closeContextMenu();
  }, [managerState]);
  const isCollapsed = collapsed;

  const requireRuntimeBaseUrl = useCallback(() => {
    const baseUrl = workspaceRuntime.runtimeBaseUrl;
    if (!baseUrl) {
      throw new Error(
        t('workspace.fileManagement.runtime.unavailableDescription')
      );
    }
    return baseUrl;
  }, [t, workspaceRuntime.runtimeBaseUrl]);

  const ensureRuntimeReady = useCallback(() => {
    if (!workspaceRuntime.runtimeBaseUrl) {
      toast({
        title: t('workspace.fileManagement.runtime.unavailableTitle'),
        description: t('workspace.fileManagement.runtime.unavailableDescription'),
        variant: 'destructive',
      });
      return false;
    }
    return true;
  }, [toast, t, workspaceRuntime.runtimeBaseUrl]);

  useEffect(() => {
    if (workspaceRuntime.runtimeBaseUrl) {
      void loadTree();
    }
  }, [loadTree, selectedGitContextId, showHiddenEntries, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

  const previousRefreshSignalRef = useRef(refreshSignal);
  useEffect(() => {
    if (refreshSignal === undefined || refreshSignal === previousRefreshSignalRef.current) {
      return;
    }
    previousRefreshSignalRef.current = refreshSignal;
    if (!workspaceRuntime.runtimeBaseUrl) {
      return;
    }
    let cancelled = false;
    onRefreshingChange?.(true);
    void loadTree().finally(() => {
      if (!cancelled) {
        onRefreshingChange?.(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [refreshSignal, loadTree, onRefreshingChange, workspaceRuntime.runtimeBaseUrl]);

  const closeTabsForPaths = useCallback(
    (paths: string[]) => {
      if (!paths.length) return;
      const normalized = paths
        .map((path) => (path.endsWith('/') && path.length > 1 ? path.slice(0, -1) : path))
        .map(ensureLeadingSlash);
      const unique = Array.from(new Set(normalized));
      const tabsToClose = new Set<string>();

      workspace.openTabs.forEach((tab) => {
        const tabPath = ensureLeadingSlash(tab.path);
        unique.forEach((path) => {
          if (tabPath === path || tabPath.startsWith(`${path}/`)) {
            tabsToClose.add(tab.id);
          }
        });
      });

      tabsToClose.forEach((tabId) => closeTab(tabId));
    },
    [workspace.openTabs, closeTab]
  );

  const reloadOpenTabsForPaths = useCallback(async (paths: string[]) => {
    const normalizedPaths = paths.map((path) => ensureLeadingSlash(path).replace(/\/$/, ''));
    const affectedTabs = workspace.openTabs.filter((tab) => {
      const tabPath = ensureLeadingSlash(tab.path);
      return normalizedPaths.some((path) => tabPath === path || tabPath.startsWith(`${path}/`));
    });

    await Promise.all(affectedTabs.map(async (tab) => {
      try {
        const fileContent = await operations.readFile(tab.path);
        dispatch({
          type: 'UPDATE_TAB_CONTENT',
          payload: { tabId: tab.id, content: fileContent.content },
        });
        dispatch({
          type: 'SET_ORIGINAL_CONTENT',
          payload: { tabId: tab.id, content: fileContent.content },
        });
        dispatch({
          type: 'SET_FILE_VERSION_ID',
          payload: { tabId: tab.id, revision: fileContent.revision },
        });
        dispatch({ type: 'SET_TAB_MODIFIED', payload: { tabId: tab.id, isModified: false } });
      } catch (error) {
        closeTab(tab.id);
        toast({
          title: t('common.fileOperations.error.fileOperationFailed'),
          description: error instanceof Error ? error.message : String(error),
          variant: 'destructive',
        });
      }
    }));
  }, [closeTab, dispatch, operations, t, toast, workspace.openTabs]);

  const getAffectedUnsavedTabsCount = useCallback((paths: string[]) => {
    const normalizedPaths = paths.map((path) => ensureLeadingSlash(path).replace(/\/$/, ''));
    return workspace.openTabs.filter((tab) => {
      if (!fileEditor.modifiedTabs.includes(tab.id)) return false;
      const tabPath = ensureLeadingSlash(tab.path);
      return normalizedPaths.some((path) => tabPath === path || tabPath.startsWith(`${path}/`));
    }).length;
  }, [fileEditor.modifiedTabs, workspace.openTabs]);

  const resolveCurrentTargetDirectory = useCallback(
    (basePath?: string | null) => resolveTargetDirectory({
      basePath,
      flatNodes: managerState.flatNodes,
    }),
    [managerState.flatNodes],
  );

  const refreshVersionControl = useCallback(async (options?: { includeBranches?: boolean; includeCommits?: boolean }) => {
    if (!workspaceRuntime.workspaceId) {
      return;
    }

    const groups = options?.includeBranches || options?.includeCommits
      ? ['changes', 'history'] as const
      : ['changes'] as const;
    await versionControl.refresh(queryClient, groups);
  }, [queryClient, versionControl, workspaceRuntime.workspaceId]);

  const settleFileTreeMutation = useCallback(async (options?: { includeBranches?: boolean; includeCommits?: boolean }) => {
    await Promise.allSettled([
      loadTree(),
      refreshVersionControl(options),
    ]);
  }, [loadTree, refreshVersionControl]);

  const localFileConflictTransport = useMemo(() => createLocalFileConflictTransport<RuntimeFileConflictPayload>({
    findEntry: (path) => managerState.flatNodes.find((node) => (
      ensureLeadingSlash(node.path) === ensureLeadingSlash(path)
    )) ?? null,
    refreshTree: loadTree,
    createEntry: (path, entryType, content) => entryType === 'directory'
      ? operations.createDirectory(path)
      : operations.createFile(path, content),
    moveEntry: operations.moveFile,
    deleteEntry: operations.deleteFile,
    getPayload: (payload) => payload,
  }), [loadTree, managerState.flatNodes, operations]);
  const fileConflictTransport = useMemo(() => composeFileConflictTransports(
    createWorkspaceFileConflictTransport({
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? '',
      contextId: selectedGitContextId,
    }),
    localFileConflictTransport,
  ), [localFileConflictTransport, selectedGitContextId, workspaceRuntime.runtimeBaseUrl]);

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
      const finalPath = successfulItems[0]?.finalPath;
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
          dispatch({
            type: 'REMAP_FILE_TABS',
            payload: {
              sourcePath: ensureLeadingSlash(destinationOperation.sourcePath),
              targetPath: ensureLeadingSlash(destinationItem.finalPath),
            },
          });
        }
        await settleFileTreeMutation({ includeBranches: true });
        await reloadOpenTabsForPaths(replacedPaths);

        result.items
          .filter((item) => item.status === 'failed')
          .forEach((item) => {
            toast({
              title: t('common.fileOperations.error.fileOperationFailed'),
              description: item.error ?? item.sourcePath,
              variant: 'destructive',
            });
          });

        if (finalPath && result.failed === 0) {
          managerState.selectNode(finalPath);
          const item = successfulItems.find((candidate) => candidate.finalPath === finalPath);
          if (item?.type === 'file' && destinationOperation?.operation !== 'move') openFileInTab(finalPath);
        }
        if (result.failed === 0 && operation === 'paste') setClipboardItem(null);
      })();
    },
    onError: (error, stage) => {
      completedFileConflictOperationRef.current = null;
      destinationConflictRef.current = null;
      if (stage === 'execute') return;
      toast({
        title: t('common.fileOperations.error.fileUploadFailed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
    },
    onCancelled: () => {
      completedFileConflictOperationRef.current = null;
      destinationConflictRef.current = null;
    },
  });

  const triggerArchiveBrowserDownload = useCallback(async (
    downloadUrl: string,
    operationId: string,
    archiveName?: string,
  ): Promise<boolean> => {
    const generation = writeOperationGenerationRef.current;
    if (typeof window === 'undefined' || !isWriteOperationActive(generation)) {
      return false;
    }
    try {
      const baseUrl = requireRuntimeBaseUrl();
      const blob = await downloadArchiveBlob(baseUrl, downloadUrl);
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
  }, [isWriteOperationActive, requireRuntimeBaseUrl, t, toast]);

  const waitForArchiveCompletion = useCallback(async (
    operationId: string,
    options?: { restored?: boolean },
  ) => {
    const generation = writeOperationGenerationRef.current;
    if (!isWriteOperationActive(generation)) {
      return;
    }
    const baseUrl = requireRuntimeBaseUrl();

    for (let attempt = 0; attempt < 120; attempt += 1) {
      if (!isWriteOperationActive(generation)) {
        return;
      }
      const status = await fetchArchiveDownloadStatus(baseUrl, operationId);
      if (!isWriteOperationActive(generation)) {
        return;
      }
      setArchiveProgress(current => current
        ? buildArchiveProgressFromStatus({ current, status })
        : current);

      if (status.status === 'completed' && status.result) {
        setArchiveProgress(current => current
          ? buildArchiveProgressFromStatus({ current, status })
          : current);
        toast({
          title: t('shared.fileWorkbench.archive.ready'),
          description: t('shared.fileWorkbench.archive.readyDescription', {
            name: status.result.archiveName,
          }),
        });
        const persisted = loadPersistedArchiveOperations(ARCHIVE_STORAGE_KEY).find((item) => item.operationId === operationId);
        let downloadTriggered = Boolean(persisted?.downloadTriggeredAt);
        if (!persisted?.downloadTriggeredAt) {
          downloadTriggered = await triggerArchiveBrowserDownload(
            status.result.downloadUrl,
            operationId,
            status.result.archiveName,
          );
        }
        if (downloadTriggered && !options?.restored && typeof window !== 'undefined') {
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
        setArchiveProgress(current => current
          ? buildArchiveProgressFromStatus({ current, status })
          : current);
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
  }, [isWriteOperationActive, requireRuntimeBaseUrl, t, toast, triggerArchiveBrowserDownload]);

  const handleArchiveOperationNotFound = useCallback((operationId: string) => {
    removePersistedArchiveOperation(ARCHIVE_STORAGE_KEY, operationId);
    setArchiveProgress(null);
    toast({
      title: t('workspace.fileManagement.tree.notifications.archiveExpired'),
      description: t('workspace.fileManagement.tree.notifications.archiveExpiredDescription'),
      variant: 'destructive',
    });
  }, [t, toast]);

  useEffect(() => {
    if (!workspaceRuntime.runtimeBaseUrl || !workspaceRuntime.workspaceId) {
      return;
    }

    const archiveContext = {
      workspaceId: workspaceRuntime.workspaceId,
      contextId: selectedGitContextId ?? null,
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    } satisfies WorkspaceArchiveContext;
    if (!permissions.canWrite) {
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
    const generation = writeOperationGenerationRef.current;
    const restore = async () => {
      try {
        const status = await fetchArchiveDownloadStatus(
          workspaceRuntime.runtimeBaseUrl!,
          persisted.operationId,
        );
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
          toast({
            title: t('shared.fileWorkbench.archive.ready'),
            description: t('shared.fileWorkbench.archive.readyDescription', {
              name: status.result.archiveName,
            }),
          });
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
          toast({
            title: status.status === 'expired'
              ? t('workspace.fileManagement.tree.notifications.archiveExpired')
              : t('workspace.fileManagement.tree.notifications.archiveFailed'),
            description: status.error ?? status.message,
            variant: 'destructive',
          });
          return;
        }
        void waitForArchiveCompletion(persisted.operationId, { restored: true }).catch(() => {
          if (isWriteOperationActive(generation)) {
            handleArchiveOperationNotFound(persisted.operationId);
          }
        });
      } catch {
        if (!cancelled && canWriteRef.current) {
          handleArchiveOperationNotFound(persisted.operationId);
        }
      }
    };

    void restore();
    return () => {
      cancelled = true;
    };
  }, [
    archiveProgress,
    handleArchiveOperationNotFound,
    isWriteOperationActive,
    permissions.canWrite,
    selectedGitContextId,
    t,
    toast,
    triggerArchiveBrowserDownload,
    waitForArchiveCompletion,
    workspaceRuntime.runtimeBaseUrl,
    workspaceRuntime.workspaceId,
  ]);

  const handleExtractArchive = useCallback(async (node: FileTreeNode) => {
    if (!permissions.canWrite || !ensureRuntimeReady()) {
      return;
    }
    completedFileConflictOperationRef.current = 'extract';
    await fileConflictController.start({
      operation: 'extract',
      targetPath: getParentPath(node.path),
      sources: null,
      archivePath: node.path,
    }, {});
  }, [ensureRuntimeReady, fileConflictController, permissions.canWrite]);

  const handleDownloadEntries = useCallback(async (node: FileTreeNode, paths: string[]) => {
    const selectedPaths = Array.from(new Set(paths.length > 0 ? paths : [node.path]));
    const shouldArchive = node.type === 'directory' || selectedPaths.length > 1;
    if ((shouldArchive && !permissions.canWrite) || !ensureRuntimeReady()) {
      return;
    }
    const generation = writeOperationGenerationRef.current;

    try {
      if (!shouldArchive) {
        await fileTreeAdapter.download({ path: node.path, fileName: node.name });
        toast({
          title: t('workspace.fileManagement.tree.notifications.downloadSuccess'),
          description: t('workspace.fileManagement.tree.notifications.downloadSuccessDescription', { count: 1 }),
        });
        return;
      }

      const archiveName = selectedPaths.length === 1
        ? `${node.name.replace(/\.zip$/i, '')}.zip`
        : undefined;
      const accepted = await startArchiveDownload(requireRuntimeBaseUrl(), {
        paths: selectedPaths,
        archiveName,
        archiveFormat: 'zip',
        contextId: selectedGitContextId,
      });
      if (!isWriteOperationActive(generation)) {
        return;
      }
      const resolvedArchiveName = archiveName ?? 'workspace-selection.zip';

      upsertPersistedArchiveOperation(ARCHIVE_STORAGE_KEY, {
        operationId: accepted.operationId,
        archiveName: resolvedArchiveName,
        paths: selectedPaths,
        context: {
          workspaceId: workspaceRuntime.workspaceId ?? 'pending-workspace',
          contextId: selectedGitContextId ?? null,
          runtimeBaseUrl: requireRuntimeBaseUrl(),
        } satisfies WorkspaceArchiveContext,
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
    ensureRuntimeReady,
    fileTreeAdapter,
    isWriteOperationActive,
    permissions.canWrite,
    requireRuntimeBaseUrl,
    selectedGitContextId,
    t,
    toast,
    waitForArchiveCompletion,
    workspaceRuntime.workspaceId,
  ]);

  const getDirectoryNodeForPath = useCallback(
    (path?: string | null): FileTreeNode | undefined => {
      if (!path || path === '/' || path === '') {
        return undefined;
      }
      const existing = managerState.flatNodes.find(
        (item) => item.path === path && item.type === 'directory'
      );
      if (existing) {
        return existing;
      }
      const name = path.split('/').filter(Boolean).pop() ?? '/';
      return {
        id: path,
        name,
        path,
        type: 'directory',
      };
    },
    [managerState.flatNodes]
  );

  const fileOps = useFileOperationsWithDialog({
    onCreateFile: async (name, parentPath = '/') => {
      if (!permissions.canWrite) {
        return;
      }
      requireRuntimeBaseUrl();
      const fullPath = parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;
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
    onCreateFolder: async (name, parentPath = '/') => {
      if (!permissions.canWrite) {
        return;
      }
      requireRuntimeBaseUrl();
      const fullPath = parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;
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
      if (!permissions.canWrite) {
        return;
      }
      requireRuntimeBaseUrl();
      const parentPath = getParentPath(oldPath);
      const newPath = parentPath === '/' ? `/${newName}` : `${parentPath}/${newName}`;
      const normalizedOldPath = ensureLeadingSlash(oldPath);
      const sourceNode = managerState.flatNodes.find((node) => (
        ensureLeadingSlash(node.path) === normalizedOldPath
      ));
      if (!sourceNode) return;
      destinationConflictRef.current = { operation: 'move', sourcePath: normalizedOldPath };
      completedFileConflictOperationRef.current = 'move';
      const result = await fileConflictController.start({
        operation: 'move',
        targetPath: ensureLeadingSlash(newPath),
        sources: [{ sourcePath: normalizedOldPath, entryType: sourceNode.type }],
        archivePath: null,
      }, { files: [], sourcePath: normalizedOldPath, entryType: sourceNode.type });
      if (!result) return { suppressSuccessToast: true };
    },
    onDelete: async (path, node) => {
      if (!permissions.canWrite) {
        return;
      }
      requireRuntimeBaseUrl();
      const targetPath = ensureLeadingSlash(path);
      const relatedPaths = getRelatedPathsForDelete({
        paths: [targetPath],
        flatNodes: node?.type === 'directory' ? managerState.flatNodes : [],
      });

      const response = await operations.deleteFile(path, node?.type === 'directory');
      if (!response.success) {
        throw new Error(response.error || response.message || t('common.fileOperations.error.fileOperationFailed'));
      }
      closeTabsForPaths(relatedPaths);
      await settleFileTreeMutation({ includeBranches: true });
    },
    onBatchDelete: async (paths) => {
      if (!permissions.canWrite) {
        return;
      }
      requireRuntimeBaseUrl();
      if (!paths.length) {
        return;
      }

      const response = await operations.batchDelete(paths, true);
      if (response.successCount > 0) {
        const successfulPathsToClose = getRelatedPathsForDelete({
          paths: response.deleted,
          flatNodes: managerState.flatNodes,
        });
        closeTabsForPaths(successfulPathsToClose);
        await settleFileTreeMutation({ includeBranches: true });
      }
      response.failed.forEach((failure) => {
        toast({
          title: t('common.fileOperations.error.fileOperationFailed'),
          description: `${failure.path}: ${failure.error}`,
          variant: 'destructive',
        });
      });
      if (response.failedCount === 0) managerState.clearSelection();
      if (response.failedCount > 0) return { suppressSuccessToast: true };
    },
  });
  const closeFileOperationDialog = fileOps.closeDialog;

  useEffect(() => {
    if (!permissions.canWrite) {
      closeFileOperationDialog();
      setClipboardItem(null);
    }
  }, [closeFileOperationDialog, permissions.canWrite]);

  const handleNodeClick = useCallback(
    (node: FileTreeNode, modifier: SelectionModifier) => {
      managerState.selectNodeWithModifier(node.path, modifier);
      if (node.type === 'file' && modifier === 'none') {
        openFileInTab(node.path);
      }
    },
    [managerState, openFileInTab]
  );

  const handleNodeDoubleClick = useCallback(
    (node: FileTreeNode) => {
      if (node.type === 'directory') {
        void toggleDirectory(node);
        return;
      }
      openFileInTab(node.path);
    },
    [toggleDirectory, openFileInTab]
  );

  const handleContextMenu = useCallback(
    (node: FileTreeNode, event: React.MouseEvent) => {
      event.preventDefault();
      managerState.openContextMenu(event.clientX, event.clientY, node);
    },
    [managerState]
  );

  const triggerCreateFile = useCallback(
    (parentPath: string) => {
      if (!permissions.canWrite) {
        return;
      }
      const targetNode = getDirectoryNodeForPath(parentPath);
      if (targetNode) {
        fileOps.openCreateFileDialog(targetNode);
      } else {
        fileOps.openCreateFileDialog();
      }
    },
    [fileOps, getDirectoryNodeForPath, permissions.canWrite]
  );

  const triggerCreateFolder = useCallback(
    (parentPath: string) => {
      if (!permissions.canWrite) {
        return;
      }
      const targetNode = getDirectoryNodeForPath(parentPath);
      if (targetNode) {
        fileOps.openCreateFolderDialog(targetNode);
      } else {
        fileOps.openCreateFolderDialog();
      }
    },
    [fileOps, getDirectoryNodeForPath, permissions.canWrite]
  );

  const handleToolbarCreateFile = useCallback(() => {
    const parent = resolveCurrentTargetDirectory(managerState.selectedId ?? '/');
    triggerCreateFile(parent);
  }, [managerState.selectedId, resolveCurrentTargetDirectory, triggerCreateFile]);

  const handleToolbarCreateFolder = useCallback(() => {
    const parent = resolveCurrentTargetDirectory(managerState.selectedId ?? '/');
    triggerCreateFolder(parent);
  }, [managerState.selectedId, resolveCurrentTargetDirectory, triggerCreateFolder]);

  const handleUpload = useCallback(
    (targetPath?: string) => {
      if (!permissions.canWrite) {
        return;
      }
      const parent = resolveCurrentTargetDirectory(targetPath ?? managerState.selectedId ?? '/');
      if (!ensureRuntimeReady()) {
        return;
      }
      setUploadTargetPath(parent);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
        fileInputRef.current.click();
      }
    },
    [
      ensureRuntimeReady,
      managerState.selectedId,
      permissions.canWrite,
      resolveCurrentTargetDirectory,
    ]
  );

  const handleToolbarUpload = useCallback(() => {
    handleUpload();
  }, [handleUpload]);

  const handleRefresh = useCallback(() => {
    logger.debug('handleRefresh: refreshing file tree');
    void loadTree();
  }, [loadTree]);

  const handleBatchDelete = useCallback(
    (paths: string[]) => {
      if (!permissions.canWrite || paths.length === 0) {
        return;
      }
      const nodes = paths.map((path) => {
        const node = managerState.flatNodes.find((item) => item.path === path);
        return node ?? createPlaceholderNode(path);
      });
      fileOps.openBatchDeleteDialog(nodes);
    },
    [fileOps, managerState.flatNodes, permissions.canWrite]
  );

  const handleClipboardCopy = useCallback(
    (node: FileTreeNode) => {
      setClipboardItem({ path: node.path, type: node.type });
      toast({
        title: t('workspace.fileManagement.tree.notifications.copySuccess'),
        description: node.name,
      });
    },
    [toast, t]
  );

  const handleCopyPath = useCallback(
    async (path: string) => {
      try {
        await navigator.clipboard.writeText(path);
        toast({
          title: t('workspace.fileManagement.tree.notifications.pathCopied'),
          description: path,
        });
      } catch (error) {
        toast({
          title: t('workspace.fileManagement.tree.notifications.copyFailed'),
          description: error instanceof Error ? error.message : String(error),
          variant: 'destructive',
        });
      }
    },
    [toast, t]
  );

  const handleClipboardPaste = useCallback(
    async (targetDirectory: string) => {
      if (!permissions.canWrite) {
        return;
      }
      if (!clipboardItem) {
        toast({
          title: t('workspace.fileManagement.tree.notifications.pasteUnavailable'),
          variant: 'destructive',
        });
        return;
      }
      if (!ensureRuntimeReady()) {
        return;
      }
      completedFileConflictOperationRef.current = 'paste';
      await fileConflictController.start({
        operation: 'paste',
        targetPath: targetDirectory,
        sources: [{ sourcePath: clipboardItem.path, entryType: clipboardItem.type }],
        archivePath: null,
      }, {});
    },
    [
      clipboardItem,
      ensureRuntimeReady,
      fileConflictController,
      permissions.canWrite,
      t,
      toast,
    ]
  );


  const handleFileInputChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;

      if (!permissions.canWrite || !files || files.length === 0) {
        return;
      }

      if (!ensureRuntimeReady()) {
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }

      try {
        const selectedFiles = Array.from(files);
        completedFileConflictOperationRef.current = 'upload';
        await fileConflictController.start({
          operation: 'upload',
          targetPath: uploadTargetPath,
          sources: selectedFiles.map((file) => ({ sourcePath: file.name, entryType: 'file' })),
          archivePath: null,
        }, { files: selectedFiles });
      } finally {
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }

    },
    [
      ensureRuntimeReady,
      fileConflictController,
      permissions.canWrite,
      uploadTargetPath,
    ]
  );

  const handleToggleHiddenEntries = useCallback(() => {
    dispatch({ type: 'SET_FILE_TREE_SHOW_HIDDEN_ENTRIES', payload: !showHiddenEntries });
  }, [dispatch, showHiddenEntries]);

  const handlePasteFiles = useCallback(
    async (files: File[]) => {
      if (!permissions.canWrite || !files.length) {
        return;
      }
      if (!ensureRuntimeReady()) {
        return;
      }
      const targetDirectory = resolveCurrentTargetDirectory(managerState.selectedId ?? '/');
      completedFileConflictOperationRef.current = 'upload';
      await fileConflictController.start({
        operation: 'upload',
        targetPath: targetDirectory,
        sources: files.map((file) => ({ sourcePath: file.name, entryType: 'file' })),
        archivePath: null,
      }, { files });
    },
    [
      ensureRuntimeReady,
      fileConflictController,
      managerState.selectedId,
      permissions.canWrite,
      resolveCurrentTargetDirectory,
    ]
  );

  const handleDragStart = useCallback((
    node: FileTreeNode,
    event: React.DragEvent,
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    logger.debug('handleDragStart: drag started', { path: node.path });
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', node.path);
    interactionState.setDraggingPath(node.path);
  }, []);

  const handleDragEnd = useCallback((
    node: FileTreeNode,
    event: React.DragEvent,
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    logger.debug('handleDragEnd: drag ended', { path: node.path });
    interactionState.setDraggingPath(null);
    interactionState.setDragOverPath(null);
  }, []);

  const handleDragOver = useCallback((
    node: FileTreeNode,
    event: React.DragEvent,
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    if (node.type === 'directory') {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      if (interactionState.dragOverPath !== node.path) {
        interactionState.setDragOverPath(node.path);
      }
    }
  }, []);

  const handleDragLeave = useCallback((
    node: FileTreeNode,
    event: React.DragEvent,
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    if (interactionState.dragOverPath === node.path) {
      interactionState.setDragOverPath(null);
    }
  }, []);

  const handleDrop = useCallback(async (
    targetNode: FileTreeNode,
    event: React.DragEvent,
    interactionState: FileManagementSidebarInteractionState,
  ) => {
    event.preventDefault();
    logger.debug('handleDrop: dropping file', { targetPath: targetNode.path });

    if (
      !permissions.canWrite
      || !interactionState.draggingPath
      || !targetNode
      || targetNode.type !== 'directory'
    ) {
      logger.debug('handleDrop: invalid drag operation');
      interactionState.setDraggingPath(null);
      interactionState.setDragOverPath(null);
      return;
    }

    const sourcePath = interactionState.draggingPath;
    const targetPath = targetNode.path;

    logger.debug('handleDrop: moving file', { from: sourcePath, to: targetPath });
    if (sourcePath === targetPath) {
      logger.debug('handleDrop: skipped moving file onto itself');
      interactionState.setDraggingPath(null);
      interactionState.setDragOverPath(null);
      return;
    }
    if (targetPath.startsWith(sourcePath + '/')) {
      logger.debug('handleDrop: skipped moving folder into its descendant');
      toast({
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: t('workspace.fileManagement.tree.notifications.moveToSubfolderError'),
        variant: 'destructive',
      });
      interactionState.setDraggingPath(null);
      interactionState.setDragOverPath(null);
      return;
    }
    const fileName = sourcePath.split('/').filter(Boolean).pop() || '';
    const newPath = targetPath === '/' ? `/${fileName}` : `${targetPath}/${fileName}`;

    logger.debug('handleDrop: computed destination path', { newPath });
    if (!ensureRuntimeReady()) {
      interactionState.setDraggingPath(null);
      interactionState.setDragOverPath(null);
      return;
    }

    try {
      const sourceNode = managerState.flatNodes.find((node) => (
        ensureLeadingSlash(node.path) === ensureLeadingSlash(sourcePath)
      ));
      if (!sourceNode) return;
      destinationConflictRef.current = {
        operation: 'move',
        sourcePath: ensureLeadingSlash(sourcePath),
      };
      completedFileConflictOperationRef.current = 'move';
      logger.debug('handleDrop: starting shared move conflict workflow');
      const response = await fileConflictController.start({
        operation: 'move',
        targetPath: ensureLeadingSlash(newPath),
        sources: [{ sourcePath: ensureLeadingSlash(sourcePath), entryType: sourceNode.type }],
        archivePath: null,
      }, {
        files: [],
        sourcePath: ensureLeadingSlash(sourcePath),
        entryType: sourceNode.type,
      });
      if (response) {
        toast({
          title: t('workspace.fileManagement.tree.notifications.moveSuccess'),
          description: t('workspace.fileManagement.tree.notifications.moveSuccessDescription', {
            source: fileName,
            target: targetNode.name,
          }),
        });
      }
    } catch (error) {
      logger.error('handleDrop: move file failed', { error });
      toast({
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
    } finally {
      interactionState.setDraggingPath(null);
      interactionState.setDragOverPath(null);
    }
  }, [
    ensureRuntimeReady,
    fileConflictController,
    managerState.flatNodes,
    permissions.canWrite,
    settleFileTreeMutation,
    t,
    toast,
  ]);
  const contextMenuItems = useFileManagementContextMenuBuilder({
    node: managerState.contextMenu?.node || null,
    selectedIds: managerState.selectedIds,
    clipboardItem,
    readOnly: !permissions.canWrite,
    isImageFile: managerState.contextMenu?.node
      ? isImageFile(managerState.contextMenu.node.name)
      : false,
    features: {
      open: true,
      upload: true,
      createFile: true,
      createFolder: true,
      extractArchive: true,
      copy: true,
      copyPath: true,
      download: true,
      paste: true,
      rename: true,
      delete: true,
      refresh: true,
      viewImage: false,
    },
    callbacks: {
      onOpen: (node) => openFileInTab(node.path),
      onUpload: () => {
        const node = managerState.contextMenu?.node;
        handleUpload(getContextMenuTargetDirectory(node));
      },
      onCreateFile: () => {
        const node = managerState.contextMenu?.node;
        const targetDirectory = getContextMenuTargetDirectory(node);
        if (node?.type === 'directory') {
          fileOps.openCreateFileDialog(node);
        } else {
          const parentNode = getDirectoryNodeForPath(targetDirectory);
          if (parentNode) {
            fileOps.openCreateFileDialog(parentNode);
          } else {
            fileOps.openCreateFileDialog();
          }
        }
      },
      onCreateFolder: () => {
        const node = managerState.contextMenu?.node;
        const targetDirectory = getContextMenuTargetDirectory(node);
        if (node?.type === 'directory') {
          fileOps.openCreateFolderDialog(node);
        } else {
          const parentNode = getDirectoryNodeForPath(targetDirectory);
          if (parentNode) {
            fileOps.openCreateFolderDialog(parentNode);
          } else {
            fileOps.openCreateFolderDialog();
          }
        }
      },
      onCopy: (node) => handleClipboardCopy(node),
      onCopyPath: (path) => {
        void handleCopyPath(path);
      },
      onDownload: (node, paths) => {
        void handleDownloadEntries(node, paths);
      },
      onPaste: () => {
        const node = managerState.contextMenu?.node;
        handleClipboardPaste(getContextMenuTargetDirectory(node));
      },
      onRename: (node) => fileOps.openRenameDialog(node),
      onDelete: (node) => fileOps.openDeleteDialog(node),
      onBatchDelete: (paths) => handleBatchDelete(paths),
      onRefresh: () => handleRefresh(),
      onExtractArchive: (node) => {
        void handleExtractArchive(node);
      },
      onClose: closeContextMenu,
    },
    t,
  });
  const sharedDialogState = toFileManagementDialogState(fileOps.dialogState);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col border-r border-sidebar-border">
      {permissions.canWrite ? (
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="sr-only"
        onChange={handleFileInputChange}
      />
      ) : null}

      <FileManagementSidebarWorkflow
        manager={manager}
        title={t('workspace.fileManagement.view.treeTitle')}
        searchPlaceholder={t('workspace.fileManagement.tree.search.placeholder')}
        headerIcon={Folder}
        showHeader={showHeader}
        capabilities={{
          canCreateFile: permissions.canWrite,
          canCreateFolder: permissions.canWrite,
          canUpload: permissions.canWrite,
        }}
        toolbarRightContent={(
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            disabled={managerState.isLoading}
            onClick={handleToggleHiddenEntries}
            title={t(
              showHiddenEntries
                ? 'workspace.fileManagement.tree.actions.hidden.hideTooltip'
                : 'workspace.fileManagement.tree.actions.hidden.showTooltip'
            )}
            aria-label={t(
              showHiddenEntries
                ? 'workspace.fileManagement.tree.actions.hidden.hideLabel'
                : 'workspace.fileManagement.tree.actions.hidden.showLabel'
            )}
          >
            {showHiddenEntries ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </Button>
        )}
        isCollapsed={showHeader ? isCollapsed : false}
        onToggleCollapse={() => undefined}
        loadEnabled={false}
        onCreateFile={handleToolbarCreateFile}
        onCreateFolder={handleToolbarCreateFolder}
        onUpload={handleToolbarUpload}
        renderBody={({ interactionState }) => (
          workspaceRuntime.isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
              <p className="text-sm text-muted-foreground">
                {t('workspace.fileManagement.runtime.initializing')}
              </p>
            </div>
          </div>
        ) : workspaceRuntime.error ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-sm text-destructive mb-2">
                {t('workspace.fileManagement.runtime.unavailableTitle')}
              </p>
              <p className="text-xs text-muted-foreground">
                {workspaceRuntime.error}
              </p>
            </div>
          </div>
          ) : (
          <div className="relative flex h-full min-h-0 flex-1 flex-col">
            <FileTreePanel
              state={managerState}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={handleNodeDoubleClick}
              onContextMenu={handleContextMenu}
              onDragStart={permissions.canWrite
                ? (node, event) => handleDragStart(node, event, interactionState)
                : undefined}
              onDragEnd={permissions.canWrite
                ? (node, event) => handleDragEnd(node, event, interactionState)
                : undefined}
              onDragOver={permissions.canWrite
                ? (node, event) => handleDragOver(node, event, interactionState)
                : undefined}
              onDragLeave={permissions.canWrite
                ? (node, event) => handleDragLeave(node, event, interactionState)
                : undefined}
              onDrop={permissions.canWrite
                ? (node, event) => handleDrop(node, event, interactionState)
                : undefined}
              draggingPath={interactionState.draggingPath}
              dragOverPath={interactionState.dragOverPath}
              onPaste={permissions.canWrite ? handlePasteFiles : undefined}
              onRefresh={handleRefresh}
              onBatchDelete={permissions.canWrite ? handleBatchDelete : undefined}
              enableSearch={false}
              enableToolbar={false}
              enableMultiSelectBar={true}
              enableBottomStatusBar={true}
              enableDragDrop={permissions.canWrite}
              onExpandDirectory={(node) => void toggleDirectory(node)}
              loadingChildrenPaths={loadingChildrenPaths}
              bottomStatusText={currentPath}
              bottomStatusClearText={t('workspace.fileManagement.tree.status.clearSelection')}
            />

            {permissions.canWrite ? (
              <ArchiveProgressOverlays
                extractProgress={null}
                archiveProgress={archiveProgress}
                onArchiveDownload={({ downloadUrl, operationId, archiveName }) => {
                  void triggerArchiveBrowserDownload(downloadUrl, operationId, archiveName);
                }}
              />
            ) : null}

            <FileTreeContextMenu
              contextMenu={managerState.contextMenu}
              items={contextMenuItems}
              onClose={closeContextMenu}
            />
          </div>
          )
        )}
      />

      {permissions.canWrite ? (
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
      ) : null}
    </div>
  );
};

export default FileManagementSidebar;
