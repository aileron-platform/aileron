/**
 * 檔案管理主視圖（重構版 - 階段 3）
 *
 * 1. 使用 file-tree-manager 的 useFileTreeManager 作為核心狀態管理
 * 2. 採用 StandardFileTreeLayout + FileTreePanel 統一 UI 架構
 * 3. 與 WorkspaceProvider 維持原有 tab 操作與佈局整合
 */

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
  type FileTreeApiConfig,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-tree-manager';
import {
  FileCreateDialog,
  FileRenameDialog,
  FileDeleteDialog,
  BatchDeleteDialog,
} from '@/shared/components/file-tree-manager/components';
import { useFileTreeManager } from '@/shared/components/file-tree-manager/hooks/useFileTreeManager';
import { useFileOperationsWithDialog } from '@/shared/components/file-tree-manager/hooks/useFileOperationsWithDialog';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { Button } from '@/shared/components/ui/button';
import { isImageFile } from '../utils/fileTypeUtils';
import {
  duplicateFile,
  fetchExtractArchiveStatus,
  startExtractArchive,
} from '../../../services/workspaceRuntimeApi';
import { refreshVersionControlQueries } from '../../version-control/lib/queryClient';
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
  const selectedGitContextId = workspaceState.versionControl.selectedGitContextId;
  const showHiddenEntries = workspaceState.fileTreeShowHiddenEntries;

  // 只有當 runtime 準備好時才創建 apiConfig
  const apiConfig: FileTreeApiConfig = useMemo(
    () => ({
      type: 'workspace',
      workspaceId: workspaceRuntime.workspaceId ?? 'pending-workspace',
      contextId: selectedGitContextId,
      baseUrl: workspaceRuntime.runtimeBaseUrl || undefined,
      includeHidden: showHiddenEntries,
    }),
    [selectedGitContextId, showHiddenEntries, workspaceRuntime.workspaceId, workspaceRuntime.runtimeBaseUrl]
  );

  const manager = useFileTreeManager({
    apiConfig,
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

  const { state: managerState, loadTree, operations } = manager;
  const currentPath = managerState.selectedId ?? workspace.activeTabId ?? '/';
  const closeContextMenu = useCallback(() => {
    managerState.closeContextMenu();
  }, [managerState]);
  const isCollapsed = layout.secondColumnCollapsed;

  const requireRuntimeBaseUrl = useCallback(() => {
    const baseUrl = workspaceRuntime.runtimeBaseUrl;
    if (!baseUrl) {
      throw new Error(
        t('workspace.fileManagement.runtime.unavailableDescription', {
          defaultValue: 'Workspace Runtime 尚未就緒，請稍候或重新整理後再試一次。',
        })
      );
    }
    return baseUrl;
  }, [t, workspaceRuntime.runtimeBaseUrl]);

  const ensureRuntimeReady = useCallback(() => {
    if (!workspaceRuntime.runtimeBaseUrl) {
      toast({
        title: t('workspace.fileManagement.runtime.unavailableTitle', {
          defaultValue: 'Workspace Runtime 尚未就緒',
        }),
        description: t('workspace.fileManagement.runtime.unavailableDescription', {
          defaultValue: '請稍候或重新整理後再試一次',
        }),
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
      // operations 的 onComplete 會自動重新載入，不需要手動調用
      await refreshVersionControl();
      openFileInTab(fullPath);
    },
    onCreateFolder: async (name, parentPath = '/') => {
      requireRuntimeBaseUrl();
      const fullPath = parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;
      await operations.createDirectory(fullPath);
      // operations 的 onComplete 會自動重新載入，不需要手動調用
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
      // operations 的 onComplete 會自動重新載入，不需要手動調用
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
      // operations 的 onComplete 會自動重新載入，不需要手動調用
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
      // operations 的 onComplete 會自動重新載入，不需要手動調用
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
        managerState.toggleNode(node.path);
        return;
      }
      openFileInTab(node.path);
    },
    [managerState, openFileInTab]
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
    logger.debug('handleRefresh: 觸發重新整理');
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
        // operations 的 onComplete 會自動重新載入，不需要手動調用
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
        // operations 的 onComplete 會自動重新載入，不需要手動調用
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



  // ==================== 拖曳處理 ====================

  const handleDragStart = useCallback((node: FileTreeNode, event: React.DragEvent) => {
    logger.debug('handleDragStart: 開始拖曳', { path: node.path });
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', node.path);
    setDraggingPath(node.path);
  }, []);

  const handleDragEnd = useCallback((node: FileTreeNode, event: React.DragEvent) => {
    logger.debug('handleDragEnd: 拖曳結束', { path: node.path });
    setDraggingPath(null);
    setDragOverPath(null);
  }, []);

  const handleDragOver = useCallback((node: FileTreeNode, event: React.DragEvent) => {
    // 只有資料夾可以作為放置目標
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
    logger.debug('handleDrop: 放置檔案到', { targetPath: targetNode.path });

    if (!draggingPath || !targetNode || targetNode.type !== 'directory') {
      logger.debug('handleDrop: 無效的拖曳操作');
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }

    const sourcePath = draggingPath;
    const targetPath = targetNode.path;

    logger.debug('handleDrop: 移動檔案', { from: sourcePath, to: targetPath });

    // 檢查是否試圖移動到自己
    if (sourcePath === targetPath) {
      logger.debug('handleDrop: 試圖移動到自己，取消操作');
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }

    // 檢查是否試圖將資料夾移動到自己的子資料夾中
    if (targetPath.startsWith(sourcePath + '/')) {
      logger.debug('handleDrop: 試圖將資料夾移動到自己的子資料夾中，取消操作');
      toast({
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: t('workspace.fileManagement.tree.notifications.moveToSubfolderError'),
        variant: 'destructive',
      });
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }

    // 計算新路徑
    const fileName = sourcePath.split('/').filter(Boolean).pop() || '';
    const newPath = targetPath === '/' ? `/${fileName}` : `${targetPath}/${fileName}`;

    logger.debug('handleDrop: 新路徑', { newPath });

    // 檢查目標位置是否已存在同名檔案
    const targetExists = managerState.flatNodes.some(node => node.path === newPath);
    if (targetExists) {
      logger.debug('handleDrop: 目標位置已存在同名檔案');
      toast({
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: t('workspace.fileManagement.tree.notifications.fileExistsError', { name: fileName }),
        variant: 'destructive',
      });
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }

    // 檢查 runtime 是否就緒
    if (!ensureRuntimeReady()) {
      setDraggingPath(null);
      setDragOverPath(null);
      return;
    }

    try {
      logger.debug('handleDrop: 呼叫 operations.moveFile');
      await operations.moveFile(sourcePath, newPath);

      toast({
        title: t('workspace.fileManagement.tree.notifications.moveSuccess'),
        description: t('workspace.fileManagement.tree.notifications.moveSuccessDescription', {
          source: fileName,
          target: targetNode.name,
        }),
      });
      await refreshVersionControl({ includeBranches: true });

      // 如果移動的檔案有開啟的 tab，關閉並重新開啟
      const normalizedSourcePath = ensureLeadingSlash(sourcePath);
      const isOpen = workspace.openTabs.some(
        (tab) => ensureLeadingSlash(tab.path) === normalizedSourcePath
      );

      if (isOpen) {
        closeTabsForPaths([normalizedSourcePath]);
        openFileInTab(newPath);
      }

      // operations 的 onComplete 會自動重新載入
    } catch (error) {
      logger.error('handleDrop: 移動檔案失敗', { error });
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

  // 使用統一的右鍵選單 Hook
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
                {t('workspace.fileManagement.runtime.initializing', {
                  defaultValue: 'Workspace Runtime 初始化中...',
                })}
              </p>
            </div>
          </div>
        ) : workspaceRuntime.error ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-sm text-destructive mb-2">
                {t('workspace.fileManagement.runtime.unavailableTitle', {
                  defaultValue: 'Workspace Runtime 尚未就緒',
                })}
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
