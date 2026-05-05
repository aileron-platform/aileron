import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('FileManagementView');
import { Eye, EyeOff, Folder, Loader2, RefreshCw, FilePlus, FolderPlus, Upload } from 'lucide-react';
import {
  FileTreePanel,
  StandardFileTreeLayout,
  FileTreeContextMenu,
  useFileTreeContextMenu,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import {
  FileCreateDialog,
  FileRenameDialog,
  FileDeleteDialog,
  BatchDeleteDialog,
} from '@/shared/components/file-workbench';
import { useFileTreeManager } from '@/shared/components/file-workbench';
import { useFileOperationsWithDialog } from '@/shared/components/file-workbench';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { Button } from '@/shared/components/ui/button';
import { isImageFile } from '@/shared/utils/fileTypeUtils';
import {
  buildArchiveDownloadUrl,
  duplicateFile,
  fetchArchiveDownloadStatus,
  fetchExtractArchiveStatus,
  startArchiveDownload,
  startExtractArchive,
} from '../../../services/workspaceRuntimeApi';
import { refreshVersionControlQueries } from '../../version-control/lib/queryClient';
import { createWorkspaceFileTreeDataAdapter } from '../adapters/workspaceFileTreeDataAdapter';
interface ClipboardEntry {
  path: string;
  type: 'file' | 'directory';
}

interface ExtractProgressState {
  operationId: string;
  archivePath: string;
  archiveName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  message: string;
  errorMessage?: string | null;
}

interface ArchiveProgressState {
  operationId: string;
  archiveName: string;
  paths: string[];
  status: 'pending' | 'running' | 'completed' | 'failed' | 'expired';
  progress: number;
  message: string;
  downloadUrl?: string | null;
  errorMessage?: string | null;
}

interface PersistedArchiveOperation {
  operationId: string;
  archiveName: string;
  paths: string[];
  workspaceId: string;
  contextId: string | null;
  runtimeBaseUrl: string;
  startedAt: string;
  downloadTriggeredAt?: string | null;
}

const ARCHIVE_OPERATIONS_STORAGE_KEY = 'workspace.fileManagement.archiveOperations.v1';

const ensureLeadingSlash = (path: string) => {
  if (!path.startsWith('/')) {
    return `/${path}`;
  }
  return path;
};

const getParentPath = (path: string): string => {
  if (!path || path === '/') {
    return '/';
  }
  const segments = path.split('/').filter(Boolean);
  segments.pop();
  if (segments.length === 0) {
    return '/';
  }
  return `/${segments.join('/')}`;
};

const loadPersistedArchiveOperations = (): PersistedArchiveOperation[] => {
  if (typeof window === 'undefined') {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(ARCHIVE_OPERATIONS_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
};

const savePersistedArchiveOperations = (operations: PersistedArchiveOperation[]) => {
  if (typeof window === 'undefined') {
    return;
  }
  window.localStorage.setItem(ARCHIVE_OPERATIONS_STORAGE_KEY, JSON.stringify(operations));
};

const upsertPersistedArchiveOperation = (operation: PersistedArchiveOperation) => {
  const existing = loadPersistedArchiveOperations().filter(
    (item) => item.operationId !== operation.operationId,
  );
  savePersistedArchiveOperations([...existing, operation]);
};

const removePersistedArchiveOperation = (operationId: string) => {
  savePersistedArchiveOperations(
    loadPersistedArchiveOperations().filter((item) => item.operationId !== operationId),
  );
};

const markPersistedArchiveDownloadTriggered = (operationId: string) => {
  savePersistedArchiveOperations(
    loadPersistedArchiveOperations().map((item) => (
      item.operationId === operationId
        ? { ...item, downloadTriggeredAt: new Date().toISOString() }
        : item
    )),
  );
};

export const FileManagementView: React.FC = () => {
  const {
    workspace,
    state: workspaceState,
    dispatch,
    workspaceRuntime,
    layout,
    toggleSecondColumn,
    openFileInTab,
    closeTab,
  } = useWorkspace();
  const { t } = useI18n();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const fileInputRef = useRef<HTMLInputElement>(null);
  const [clipboardItem, setClipboardItem] = useState<ClipboardEntry | null>(null);
  const [uploadTargetPath, setUploadTargetPath] = useState<string>('/');
  const [draggingPath, setDraggingPath] = useState<string | null>(null);
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);
  const [extractProgress, setExtractProgress] = useState<ExtractProgressState | null>(null);
  const [archiveProgress, setArchiveProgress] = useState<ArchiveProgressState | null>(null);
  const selectedGitContextId = workspaceState.versionControl.selectedGitContextId;
  const showHiddenEntries = workspaceState.fileTreeShowHiddenEntries;

  const fileTreeAdapter = useMemo(
    () => createWorkspaceFileTreeDataAdapter({
      workspaceId: workspaceRuntime.workspaceId ?? 'pending-workspace',
      contextId: selectedGitContextId,
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl || undefined,
      includeHidden: showHiddenEntries,
    }),
    [selectedGitContextId, showHiddenEntries, workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl]
  );
  const fileTreeAdapterKey = useMemo(
    () =>
      JSON.stringify({
        workspaceId: workspaceRuntime.workspaceId ?? 'pending-workspace',
        contextId: selectedGitContextId ?? null,
        runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? null,
        includeHidden: showHiddenEntries,
      }),
    [selectedGitContextId, showHiddenEntries, workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl],
  );

  const manager = useFileTreeManager({
    adapter: fileTreeAdapter,
    adapterKey: fileTreeAdapterKey,
    stateOptions: { enableMultiSelect: true },
    autoLoad: false,
    onError: (error) => {
      toast({
        title: t('workspace.fileManagement.error.loadFailed'),
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
  const isCollapsed = layout.secondColumnCollapsed;

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedGitContextId, showHiddenEntries, workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId]);

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

  const resolveTargetDirectory = useCallback(
    (basePath?: string | null) => {
      if (!basePath || basePath === '/' || basePath === '') {
        return '/';
      }
      const node = managerState.flatNodes.find((item) => item.path === basePath);
      if (node?.type === 'directory') {
        return node.path;
      }
      return getParentPath(basePath);
    },
    [managerState.flatNodes]
  );

  const resolveUploadOptions = useCallback(() => {
    return {
      archiveAction: 'store' as const,
      keepArchive: false,
      conflictStrategy: 'rename' as const,
    };
  }, []);

  const refreshVersionControl = useCallback(async (options?: { includeBranches?: boolean; includeCommits?: boolean }) => {
    if (!workspaceRuntime.workspaceId) {
      return;
    }

    await refreshVersionControlQueries(queryClient, workspaceRuntime.workspaceId, {
      ...options,
      contextId: selectedGitContextId,
    });
  }, [queryClient, selectedGitContextId, workspaceRuntime.workspaceId]);

  const waitForExtractCompletion = useCallback(async (operationId: string) => {
    const baseUrl = requireRuntimeBaseUrl();

    for (let attempt = 0; attempt < 120; attempt += 1) {
      const status = await fetchExtractArchiveStatus(baseUrl, operationId);
      setExtractProgress(current => current ? {
        ...current,
        status: status.status,
        progress: status.progress,
        message: status.message,
        errorMessage: status.error ?? null,
      } : current);

      if (status.status === 'completed') {
        await loadTree();
        toast({
          title: t('workspace.fileManagement.tree.notifications.extractSuccess'),
          description: status.message,
        });
        if (typeof window !== 'undefined') {
          window.setTimeout(() => setExtractProgress(null), 600);
        } else {
          setExtractProgress(null);
        }
        return;
      }

      if (status.status === 'failed') {
        toast({
          title: t('workspace.fileManagement.tree.notifications.extractFailed'),
          description: status.error ?? status.message,
          variant: 'destructive',
        });
        if (typeof window !== 'undefined') {
          window.setTimeout(() => setExtractProgress(null), 1500);
        } else {
          setExtractProgress(null);
        }
        return;
      }

      await new Promise(resolve => globalThis.setTimeout(resolve, 1000));
    }

    setExtractProgress(current => current ? {
      ...current,
      status: 'failed',
      errorMessage: t('common.messages.cannotGetSyncStatus'),
      message: t('common.messages.cannotGetSyncStatus'),
    } : current);
    toast({
      title: t('workspace.fileManagement.tree.notifications.extractFailed'),
      description: t('common.messages.cannotGetSyncStatus'),
      variant: 'destructive',
    });
  }, [loadTree, requireRuntimeBaseUrl, t, toast]);

  const triggerArchiveBrowserDownload = useCallback((downloadUrl: string, operationId: string) => {
    const fullUrl = buildArchiveDownloadUrl(requireRuntimeBaseUrl(), downloadUrl);
    if (typeof window !== 'undefined') {
      window.open(fullUrl, '_blank', 'noopener');
      markPersistedArchiveDownloadTriggered(operationId);
    }
  }, [requireRuntimeBaseUrl]);

  const waitForArchiveCompletion = useCallback(async (
    operationId: string,
    options?: { restored?: boolean },
  ) => {
    const baseUrl = requireRuntimeBaseUrl();

    for (let attempt = 0; attempt < 120; attempt += 1) {
      const status = await fetchArchiveDownloadStatus(baseUrl, operationId);
      setArchiveProgress(current => current ? {
        ...current,
        status: status.status,
        progress: status.progress,
        message: status.message,
        downloadUrl: status.result?.downloadUrl ?? current.downloadUrl ?? null,
        errorMessage: status.error ?? null,
      } : current);

      if (status.status === 'completed' && status.result) {
        setArchiveProgress(current => current ? {
          ...current,
          status: 'completed',
          progress: 1,
          message: status.message,
          archiveName: status.result?.archiveName ?? current.archiveName,
          downloadUrl: status.result?.downloadUrl ?? null,
        } : current);
        toast({
          title: t('workspace.fileManagement.tree.notifications.archiveReady'),
          description: t('workspace.fileManagement.tree.notifications.archiveReadyDescription', {
            name: status.result.archiveName,
          }),
        });
        const persisted = loadPersistedArchiveOperations().find((item) => item.operationId === operationId);
        if (!persisted?.downloadTriggeredAt) {
          triggerArchiveBrowserDownload(status.result.downloadUrl, operationId);
        }
        if (!options?.restored && typeof window !== 'undefined') {
          window.setTimeout(() => {
            removePersistedArchiveOperation(operationId);
            setArchiveProgress(null);
          }, 3000);
        }
        return;
      }

      if (status.status === 'failed' || status.status === 'expired') {
        removePersistedArchiveOperation(operationId);
        setArchiveProgress(current => current ? {
          ...current,
          status: status.status,
          errorMessage: status.error ?? status.message,
          message: status.error ?? status.message,
        } : current);
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

    toast({
      title: t('workspace.fileManagement.tree.notifications.archiveFailed'),
      description: t('common.messages.cannotGetSyncStatus'),
      variant: 'destructive',
    });
  }, [requireRuntimeBaseUrl, t, toast, triggerArchiveBrowserDownload]);

  const handleArchiveOperationNotFound = useCallback((operationId: string) => {
    removePersistedArchiveOperation(operationId);
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

    const persisted = loadPersistedArchiveOperations()
      .filter((item) => (
        item.workspaceId === workspaceRuntime.workspaceId
        && item.contextId === (selectedGitContextId ?? null)
        && item.runtimeBaseUrl === workspaceRuntime.runtimeBaseUrl
      ))
      .sort((a, b) => b.startedAt.localeCompare(a.startedAt))[0];

    if (!persisted || archiveProgress) {
      return;
    }

    let cancelled = false;
    const restore = async () => {
      try {
        const status = await fetchArchiveDownloadStatus(
          workspaceRuntime.runtimeBaseUrl!,
          persisted.operationId,
        );
        if (cancelled) {
          return;
        }
        setArchiveProgress({
          operationId: persisted.operationId,
          archiveName: status.result?.archiveName ?? persisted.archiveName,
          paths: persisted.paths,
          status: status.status,
          progress: status.progress,
          message: status.message,
          downloadUrl: status.result?.downloadUrl ?? null,
          errorMessage: status.error ?? null,
        });
        if (status.status === 'completed' && status.result) {
          toast({
            title: t('workspace.fileManagement.tree.notifications.archiveReady'),
            description: t('workspace.fileManagement.tree.notifications.archiveReadyDescription', {
              name: status.result.archiveName,
            }),
          });
          if (!persisted.downloadTriggeredAt) {
            triggerArchiveBrowserDownload(status.result.downloadUrl, persisted.operationId);
          }
          return;
        }
        if (status.status === 'failed' || status.status === 'expired') {
          removePersistedArchiveOperation(persisted.operationId);
          toast({
            title: status.status === 'expired'
              ? t('workspace.fileManagement.tree.notifications.archiveExpired')
              : t('workspace.fileManagement.tree.notifications.archiveFailed'),
            description: status.error ?? status.message,
            variant: 'destructive',
          });
          return;
        }
        void waitForArchiveCompletion(persisted.operationId, { restored: true });
      } catch {
        if (!cancelled) {
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
    selectedGitContextId,
    t,
    toast,
    triggerArchiveBrowserDownload,
    waitForArchiveCompletion,
    workspaceRuntime.runtimeBaseUrl,
    workspaceRuntime.workspaceId,
  ]);

  const handleExtractArchive = useCallback(async (node: FileTreeNode) => {
    if (!ensureRuntimeReady()) {
      return;
    }

    if (extractProgress && (extractProgress.status === 'pending' || extractProgress.status === 'running')) {
      toast({
        title: t('workspace.fileManagement.tree.notifications.operationBlocked'),
        description: extractProgress.archiveName,
        variant: 'destructive',
      });
      return;
    }

    const baseUrl = requireRuntimeBaseUrl();

    try {
      const accepted = await startExtractArchive(baseUrl, {
        archivePath: node.path,
        targetPath: getParentPath(node.path),
        conflictStrategy: 'rename',
        contextId: selectedGitContextId,
      });

      setExtractProgress({
        operationId: accepted.operationId,
        archivePath: node.path,
        archiveName: node.name,
        status: accepted.status,
        progress: 0,
        message: accepted.message,
        errorMessage: null,
      });

      await waitForExtractCompletion(accepted.operationId);
    } catch (error) {
      toast({
        title: t('workspace.fileManagement.tree.notifications.extractFailed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
      setExtractProgress(null);
    }
  }, [ensureRuntimeReady, extractProgress, requireRuntimeBaseUrl, selectedGitContextId, t, toast, waitForExtractCompletion]);

  const handleDownloadEntries = useCallback(async (node: FileTreeNode, paths: string[]) => {
    if (!ensureRuntimeReady()) {
      return;
    }

    const selectedPaths = Array.from(new Set(paths.length > 0 ? paths : [node.path]));
    const shouldArchive = node.type === 'directory' || selectedPaths.length > 1;

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
      const resolvedArchiveName = archiveName ?? 'workspace-selection.zip';

      upsertPersistedArchiveOperation({
        operationId: accepted.operationId,
        archiveName: resolvedArchiveName,
        paths: selectedPaths,
        workspaceId: workspaceRuntime.workspaceId ?? 'pending-workspace',
        contextId: selectedGitContextId ?? null,
        runtimeBaseUrl: requireRuntimeBaseUrl(),
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

  const createPlaceholderNode = useCallback((path: string, type: 'file' | 'directory' = 'file'): FileTreeNode => ({
    id: path,
    name: path.split('/').filter(Boolean).pop() ?? path,
    path,
    type,
  }), []);

  const fileOps = useFileOperationsWithDialog({
    onCreateFile: async (name, parentPath = '/') => {
      requireRuntimeBaseUrl();
      const fullPath = parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;
      await operations.createFile(fullPath, '');
      await refreshVersionControl();
      openFileInTab(fullPath);
    },
    onCreateFolder: async (name, parentPath = '/') => {
      requireRuntimeBaseUrl();
      const fullPath = parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;
      await operations.createDirectory(fullPath);
      await refreshVersionControl();
    },
    onRename: async (oldPath, newName) => {
      requireRuntimeBaseUrl();
      const parentPath = getParentPath(oldPath);
      const newPath = parentPath === '/' ? `/${newName}` : `${parentPath}/${newName}`;
      const normalizedOldPath = ensureLeadingSlash(oldPath);
      const isOpen = workspace.openTabs.some(
        (tab) => ensureLeadingSlash(tab.path) === normalizedOldPath
      );

      await operations.renameFile(oldPath, newPath);
      await refreshVersionControl({ includeBranches: true });

      if (isOpen) {
        closeTabsForPaths([normalizedOldPath]);
        openFileInTab(newPath);
      }
    },
    onDelete: async (path, node) => {
      requireRuntimeBaseUrl();
      const targetPath = ensureLeadingSlash(path);
      const relatedPaths = new Set<string>([targetPath]);

      if (node?.type === 'directory') {
        managerState.flatNodes.forEach((flatNode) => {
          if (flatNode.path.startsWith(`${targetPath}/`)) {
            relatedPaths.add(flatNode.path);
          }
        });
      }

      await operations.deleteFile(path, node?.type === 'directory');
      await refreshVersionControl({ includeBranches: true });
      closeTabsForPaths(Array.from(relatedPaths));
    },
    onBatchDelete: async (paths) => {
      requireRuntimeBaseUrl();
      if (!paths.length) {
        return;
      }

      const pathsToClose = new Set<string>();
      paths.forEach((item) => {
        const normalized = ensureLeadingSlash(item);
        pathsToClose.add(normalized);
        managerState.flatNodes.forEach((flatNode) => {
          if (flatNode.path.startsWith(`${normalized}/`)) {
            pathsToClose.add(flatNode.path);
          }
        });
      });

      await operations.batchDelete(paths, true);
      await refreshVersionControl({ includeBranches: true });
      closeTabsForPaths(Array.from(pathsToClose));
      managerState.clearSelection();
    },
  });

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
      const targetNode = getDirectoryNodeForPath(parentPath);
      if (targetNode) {
        fileOps.openCreateFileDialog(targetNode);
      } else {
        fileOps.openCreateFileDialog();
      }
    },
    [fileOps, getDirectoryNodeForPath]
  );

  const triggerCreateFolder = useCallback(
    (parentPath: string) => {
      const targetNode = getDirectoryNodeForPath(parentPath);
      if (targetNode) {
        fileOps.openCreateFolderDialog(targetNode);
      } else {
        fileOps.openCreateFolderDialog();
      }
    },
    [fileOps, getDirectoryNodeForPath]
  );

  const handleToolbarCreateFile = useCallback(() => {
    const parent = resolveTargetDirectory(managerState.selectedId ?? '/');
    triggerCreateFile(parent);
  }, [managerState.selectedId, resolveTargetDirectory, triggerCreateFile]);

  const handleToolbarCreateFolder = useCallback(() => {
    const parent = resolveTargetDirectory(managerState.selectedId ?? '/');
    triggerCreateFolder(parent);
  }, [managerState.selectedId, resolveTargetDirectory, triggerCreateFolder]);

  const handleUpload = useCallback(
    (targetPath?: string) => {
      const parent = resolveTargetDirectory(targetPath ?? managerState.selectedId ?? '/');
      if (!ensureRuntimeReady()) {
        return;
      }
      setUploadTargetPath(parent);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
        fileInputRef.current.click();
      }
    },
    [ensureRuntimeReady, managerState.selectedId, resolveTargetDirectory]
  );

  const handleRefresh = useCallback(() => {
    logger.debug('handleRefresh: refreshing file tree');
    void loadTree();
  }, [loadTree]);

  const handleBatchDelete = useCallback(
    (paths: string[]) => {
      if (paths.length === 0) {
        return;
      }
      const nodes = paths.map((path) => {
        const node = managerState.flatNodes.find((item) => item.path === path);
        return node ?? createPlaceholderNode(path);
      });
      fileOps.openBatchDeleteDialog(nodes);
    },
    [createPlaceholderNode, fileOps, managerState.flatNodes]
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
      try {
        await duplicateFile(
          workspaceRuntime.runtimeBaseUrl!,
          clipboardItem.path,
          targetDirectory,
          selectedGitContextId,
        );
        toast({
          title: t('workspace.fileManagement.tree.notifications.pasteSuccess'),
          description: clipboardItem.path,
        });
        await loadTree();
        await refreshVersionControl();
      } catch (error) {
        toast({
          title: t('workspace.fileManagement.tree.notifications.pasteFailed'),
          description: error instanceof Error ? error.message : String(error),
          variant: 'destructive',
        });
      }
    },
    [clipboardItem, ensureRuntimeReady, toast, t, workspaceRuntime.runtimeBaseUrl, loadTree, refreshVersionControl, selectedGitContextId]
  );


  const handleFileInputChange = useCallback(
    async (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = event.target.files;

      if (!files || files.length === 0) {
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
        const result = await operations.uploadFiles({
          targetPath: uploadTargetPath,
          files: selectedFiles,
          ...resolveUploadOptions(),
        });
        if (!result.success) {
          throw new Error(result.message);
        }
        toast({
          title: t('workspace.fileManagement.tree.notifications.uploadSuccess'),
          description: result.message,
        });
        await refreshVersionControl({ includeBranches: true });
      } catch (error) {
        toast({
          title: t('workspace.fileManagement.tree.notifications.uploadFailed'),
          description: error instanceof Error ? error.message : String(error),
          variant: 'destructive',
        });
      } finally {
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    },
    [ensureRuntimeReady, operations, refreshVersionControl, resolveUploadOptions, uploadTargetPath, t, toast]
  );

  const handleToggleHiddenEntries = useCallback(() => {
    dispatch({ type: 'SET_FILE_TREE_SHOW_HIDDEN_ENTRIES', payload: !showHiddenEntries });
  }, [dispatch, showHiddenEntries]);

  const handlePasteFiles = useCallback(
    async (files: File[]) => {
      if (!files.length) {
        return;
      }
      if (!ensureRuntimeReady()) {
        return;
      }
      const targetDirectory = resolveTargetDirectory(managerState.selectedId ?? '/');
      try {
        const result = await operations.uploadFiles({
          targetPath: targetDirectory,
          files,
          ...resolveUploadOptions(),
        });
        if (!result.success) {
          throw new Error(result.message);
        }
        toast({
          title: t('workspace.fileManagement.tree.notifications.uploadSuccess'),
          description: result.message,
        });
        await refreshVersionControl({ includeBranches: true });
      } catch (error) {
        toast({
          title: t('workspace.fileManagement.tree.notifications.uploadFailed'),
          description: error instanceof Error ? error.message : String(error),
          variant: 'destructive',
        });
      }
    },
    [ensureRuntimeReady, managerState.selectedId, operations, refreshVersionControl, resolveTargetDirectory, resolveUploadOptions, t, toast]
  );

  const handleDragStart = useCallback((node: FileTreeNode, event: React.DragEvent) => {
    logger.debug('handleDragStart: drag started', { path: node.path });
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', node.path);
    setDraggingPath(node.path);
  }, []);

  const handleDragEnd = useCallback((node: FileTreeNode, event: React.DragEvent) => {
    logger.debug('handleDragEnd: drag ended', { path: node.path });
    setDraggingPath(null);
    setDragOverPath(null);
  }, []);

  const handleDragOver = useCallback((node: FileTreeNode, event: React.DragEvent) => {
    if (node.type === 'directory') {
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      if (dragOverPath !== node.path) {
        setDragOverPath(node.path);
      }
    }
  }, [dragOverPath]);

  const handleDragLeave = useCallback((node: FileTreeNode, event: React.DragEvent) => {
    if (dragOverPath === node.path) {
      setDragOverPath(null);
    }
  }, [dragOverPath]);

  const handleDrop = useCallback(async (targetNode: FileTreeNode, event: React.DragEvent) => {
    event.preventDefault();
    logger.debug('handleDrop: dropping file', { targetPath: targetNode.path });

    if (!draggingPath || !targetNode || targetNode.type !== 'directory') {
      logger.debug('handleDrop: invalid drag operation');
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }

    const sourcePath = draggingPath;
    const targetPath = targetNode.path;

    logger.debug('handleDrop: moving file', { from: sourcePath, to: targetPath });
    if (sourcePath === targetPath) {
      logger.debug('handleDrop: skipped moving file onto itself');
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }
    if (targetPath.startsWith(sourcePath + '/')) {
      logger.debug('handleDrop: skipped moving folder into its descendant');
      toast({
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: t('workspace.fileManagement.tree.notifications.moveToSubfolderError'),
        variant: 'destructive',
      });
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }
    const fileName = sourcePath.split('/').filter(Boolean).pop() || '';
    const newPath = targetPath === '/' ? `/${fileName}` : `${targetPath}/${fileName}`;

    logger.debug('handleDrop: computed destination path', { newPath });
    const targetExists = managerState.flatNodes.some(node => node.path === newPath);
    if (targetExists) {
      logger.debug('handleDrop: destination already contains an entry with the same name');
      toast({
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: t('workspace.fileManagement.tree.notifications.fileExistsError', { name: fileName }),
        variant: 'destructive',
      });
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }
    if (!ensureRuntimeReady()) {
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }

    try {
      logger.debug('handleDrop: calling operations.moveFile');
      await operations.moveFile(sourcePath, newPath);

      toast({
        title: t('workspace.fileManagement.tree.notifications.moveSuccess'),
        description: t('workspace.fileManagement.tree.notifications.moveSuccessDescription', {
          source: fileName,
          target: targetNode.name,
        }),
      });
      await refreshVersionControl({ includeBranches: true });
      const normalizedSourcePath = ensureLeadingSlash(sourcePath);
      const isOpen = workspace.openTabs.some(
        (tab) => ensureLeadingSlash(tab.path) === normalizedSourcePath
      );

      if (isOpen) {
        closeTabsForPaths([normalizedSourcePath]);
        openFileInTab(newPath);
      }
    } catch (error) {
      logger.error('handleDrop: move file failed', { error });
      toast({
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      });
    } finally {
      setDraggingPath(null);
      setDragOverPath(null);
    }
  }, [draggingPath, managerState.flatNodes, ensureRuntimeReady, operations, toast, t, workspace.openTabs, closeTabsForPaths, openFileInTab, refreshVersionControl]);
  const contextMenuItems = useFileTreeContextMenu({
    node: managerState.contextMenu?.node || null,
    enableMultiSelect: true,
    selectedCount: managerState.selectedIds.size,
    selectedIds: managerState.selectedIds,
    hasClipboard: !!clipboardItem,
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
        const targetDirectory = node?.type === 'directory' ? node.path : getParentPath(node?.path || '/');
        handleUpload(targetDirectory);
      },
      onCreateFile: () => {
        const node = managerState.contextMenu?.node;
        const targetDirectory = node?.type === 'directory' ? node.path : getParentPath(node?.path || '/');
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
        const targetDirectory = node?.type === 'directory' ? node.path : getParentPath(node?.path || '/');
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
        const targetDirectory = node?.type === 'directory' ? node.path : getParentPath(node?.path || '/');
        handleClipboardPaste(targetDirectory);
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

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col border-r border-sidebar-border">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="sr-only"
        onChange={handleFileInputChange}
      />

      <StandardFileTreeLayout
        className="flex-1 min-h-0"
        title={t('workspace.fileManagement.view.treeTitle')}
        icon={<Folder className="h-4 w-4 text-sidebar-primary" />}
        isCollapsed={isCollapsed}
        onToggleCollapse={toggleSecondColumn}
        searchValue={managerState.searchQuery}
        onSearchChange={managerState.setSearchQuery}
        onSearchClear={managerState.clearSearch}
        searchPlaceholder={t('workspace.fileManagement.tree.search.placeholder')}
        showSearch={!isCollapsed}
        headerActions={(
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0"
            onClick={() => handleRefresh()}
            disabled={managerState.isLoading}
            aria-label={t('common.fileTree.contextMenu.refresh')}
            title={t('common.fileTree.contextMenu.refresh')}
          >
            <RefreshCw className={`h-3.5 w-3.5 ${managerState.isLoading ? 'animate-spin' : ''}`} />
          </Button>
        )}
        showToolbar={false}
      >
        {isCollapsed ? (
          <CollapsedSidebarPlaceholder
            icon={Folder}
            className="text-primary"
            iconClassName="text-primary"
          />
        ) : workspaceRuntime.isLoading ? (
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
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              draggingPath={draggingPath}
              dragOverPath={dragOverPath}
              onCreateFile={handleToolbarCreateFile}
              onCreateFolder={handleToolbarCreateFolder}
              onUpload={() => handleUpload()}
              onPaste={handlePasteFiles}
              onRefresh={handleRefresh}
              onBatchDelete={handleBatchDelete}
              enableSearch={false}
              enableToolbar={true}
              enableMultiSelectBar={true}
              enableBottomStatusBar={true}
              enableDragDrop={true}
              onExpandDirectory={(node) => void toggleDirectory(node)}
              loadingChildrenPaths={loadingChildrenPaths}
              renderToolbar={() => (
                <div className="flex w-full items-center justify-between gap-2">
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0"
                      onClick={handleToolbarCreateFile}
                      disabled={managerState.isLoading}
                      title={t('workspace.fileManagement.tree.actions.create.file')}
                    >
                      <FilePlus className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0"
                      onClick={handleToolbarCreateFolder}
                      disabled={managerState.isLoading}
                      title={t('workspace.fileManagement.tree.actions.create.folder')}
                    >
                      <FolderPlus className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0"
                      onClick={() => handleUpload()}
                      disabled={managerState.isLoading}
                      title={t('workspace.fileManagement.tree.actions.create.upload')}
                    >
                      <Upload className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0"
                      onClick={handleToggleHiddenEntries}
                      disabled={managerState.isLoading}
                      title={t(
                        showHiddenEntries
                          ? 'workspace.fileManagement.tree.actions.hidden.hideTooltip'
                          : 'workspace.fileManagement.tree.actions.hidden.showTooltip'
                      )}
                    >
                      {showHiddenEntries ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </Button>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 w-7 p-0"
                    onClick={handleRefresh}
                    disabled={managerState.isLoading}
                    title={t('workspace.fileManagement.tree.actions.refresh.tooltip')}
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${managerState.isLoading ? 'animate-spin' : ''}`} />
                  </Button>
                </div>
              )}
              bottomStatusText={currentPath}
              bottomStatusClearText={t('workspace.fileManagement.tree.status.clearSelection')}
            />

            {extractProgress && (extractProgress.status === 'pending' || extractProgress.status === 'running') && (
              <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-background/80 text-sm text-muted-foreground backdrop-blur-sm">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                <span>
                  {t('workspace.fileManagement.tree.pending.extract', {
                    name: extractProgress.archiveName,
                  })}
                </span>
                <span className="text-xs">
                  {t('workspace.fileManagement.tree.pending.progress', {
                    value: Math.round(Math.min(1, Math.max(0, extractProgress.progress)) * 100),
                  })}
                </span>
                <span className="max-w-[320px] text-center text-xs text-muted-foreground">
                  {extractProgress.message}
                </span>
              </div>
            )}

            {archiveProgress && (
              <div className="absolute bottom-3 left-3 right-3 z-10 rounded-md border border-border bg-background/95 p-3 text-sm shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 font-medium text-foreground">
                      {(archiveProgress.status === 'pending' || archiveProgress.status === 'running') && (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                      )}
                      <span className="truncate">
                        {archiveProgress.status === 'completed'
                          ? t('workspace.fileManagement.tree.notifications.archiveReady')
                          : t('workspace.fileManagement.tree.pending.archive', { name: archiveProgress.archiveName })}
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {t('workspace.fileManagement.tree.pending.progress', {
                        value: Math.round(Math.min(1, Math.max(0, archiveProgress.progress)) * 100),
                      })}
                    </div>
                    <div className="mt-1 truncate text-xs text-muted-foreground">
                      {archiveProgress.errorMessage ?? archiveProgress.message}
                    </div>
                  </div>
                  {archiveProgress.status === 'completed' && archiveProgress.downloadUrl && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => triggerArchiveBrowserDownload(archiveProgress.downloadUrl!, archiveProgress.operationId)}
                    >
                      {t('common.fileTree.contextMenu.download')}
                    </Button>
                  )}
                </div>
              </div>
            )}

            <FileTreeContextMenu
              contextMenu={managerState.contextMenu}
              items={contextMenuItems}
              onClose={closeContextMenu}
            />
          </div>
        )}
      </StandardFileTreeLayout>

      <FileCreateDialog
        open={fileOps.dialogState.type === 'create-file'}
        type="file"
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleCreateFile}
      />
      <FileCreateDialog
        open={fileOps.dialogState.type === 'create-folder'}
        type="folder"
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleCreateFolder}
      />
      <FileRenameDialog
        open={fileOps.dialogState.type === 'rename'}
        onClose={fileOps.closeDialog}
        currentName={fileOps.dialogState.data?.currentName ?? fileOps.dialogState.data?.node?.name ?? ''}
        onConfirm={fileOps.handleRename}
      />
      <FileDeleteDialog
        open={fileOps.dialogState.type === 'delete'}
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleDelete}
        fileName={fileOps.dialogState.data?.node?.name ?? ''}
        fileType={fileOps.dialogState.data?.node?.type ?? 'file'}
      />
      <BatchDeleteDialog
        open={fileOps.dialogState.type === 'batch-delete'}
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleBatchDelete}
        files={(fileOps.dialogState.data?.nodes ?? []).map((node) => ({
          name: node.name,
          path: node.path,
          type: node.type,
        }))}
      />
    </div>
  );
};

export default FileManagementView;
