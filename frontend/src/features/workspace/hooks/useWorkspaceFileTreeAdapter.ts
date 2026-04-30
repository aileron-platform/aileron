/**
 * useWorkspaceFileTreeAdapter
 *
 * 使用 file-tree-manager 作為核心，轉接為 WorkspaceProvider 既有的
 * fileTreeState / fileTreeActions 介面，方便過渡階段維持相容性。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useWorkspaceFileTreeAdapter');
import { useFileTreeManager } from '@/shared/components/file-workbench';
import type {
  FileTreeNode as ManagerFileTreeNode,
  FileTreeApiConfig,
} from '@/shared/components/file-workbench';
import { findNodeByPath as findManagerNode } from '@/shared/components/file-workbench';
import type {
  FileTreeState,
  FileTreeActions,
  FileNode,
  FileOperationResult,
  CreateFileRequest,
  RenameFileRequest,
  DeleteFileRequest,
  UploadFileRequest,
  FileContent,
  PendingFileAction,
  SelectionModifier,
} from '../features/file-management/types';
import {
  buildRuntimeUrl,
  createFileOrFolder,
  renameFile as renameRuntimeFile,
  deleteFile as deleteRuntimeFile,
  batchDeleteFiles,
  duplicateFile,
  moveFile as moveRuntimeFile,
  uploadFiles as uploadRuntimeFiles,
  downloadFile as downloadRuntimeFile,
  batchDownloadFiles,
  fetchFileContent,
  saveFileContent,
} from '../services/workspaceRuntimeApi';
import { useI18n } from '@/shared/hooks/useI18n';
import { refreshVersionControlQueries } from '../features/version-control/lib/queryClient';

interface UseWorkspaceFileTreeAdapterOptions {
  workspaceId?: string;
  runtimeBaseUrl?: string | null;
  contextId?: string | null;
  showHiddenEntries: boolean;
  onShowHiddenEntriesChange?: (showHiddenEntries: boolean) => void;
}

interface WorkspaceFileTreeAdapterResult {
  state: FileTreeState;
  actions: FileTreeActions;
}

const ensureLeadingSlash = (path: string): string => {
  if (!path.startsWith('/')) {
    return `/${path}`;
  }
  return path;
};

const mapManagerNodeToFileNode = (
  node: ManagerFileTreeNode,
  expandedIds: Set<string>,
  depth: number
): FileNode => {
  const children = node.children?.map(child => mapManagerNodeToFileNode(child, expandedIds, depth + 1)) ?? [];
  const normalizedPath = ensureLeadingSlash(node.path);
  // hasChildren 優先使用後端回傳的欄位（懶載入截斷時 children=[] 但 hasChildren=true）
  const hasChildren =
    node.type === 'directory' && (
      node.hasChildren === true ||
      (node.hasChildren === undefined && (node.children ? node.children.length > 0 : true))
    );

  return {
    id: node.id ?? normalizedPath,
    name: node.name,
    path: normalizedPath,
    type: node.type,
    size: node.size,
    lastModified: node.modifiedAt,
    children,
    hasChildren,
    isExpanded: expandedIds.has(normalizedPath),
    isLoading: false,
    depth,
  };
};

const mapManagerNodes = (
  nodes: ManagerFileTreeNode[],
  expandedIds: Set<string>
): FileNode[] => {
  return nodes.map(node => mapManagerNodeToFileNode(node, expandedIds, 0));
};

const mapOperationResponse = (
  response: { success: boolean; message?: string; data?: any },
  fallbackMessage: string
): FileOperationResult => {
  return {
    success: response.success,
    message: response.message ?? fallbackMessage,
    data: response.data,
  };
};

export function useWorkspaceFileTreeAdapter(
  options: UseWorkspaceFileTreeAdapterOptions
): WorkspaceFileTreeAdapterResult {
  const { t } = useI18n();
  const { workspaceId, runtimeBaseUrl, contextId, showHiddenEntries, onShowHiddenEntriesChange } = options;
  const queryClient = useQueryClient();

  const apiConfig: FileTreeApiConfig = useMemo(
    () => ({
      type: 'workspace',
      workspaceId: workspaceId ?? 'pending-workspace',
      contextId,
      baseUrl: runtimeBaseUrl ?? undefined,
      includeHidden: showHiddenEntries,
    }),
    [contextId, runtimeBaseUrl, showHiddenEntries, workspaceId]
  );

  const manager = useFileTreeManager({
    apiConfig,
    stateOptions: { enableMultiSelect: true },
    autoLoad: false,
  });

  const [pendingAction, setPendingAction] = useState<PendingFileAction | null>(null);
  const [draggedNode, setDraggedNode] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);
  const workspaceIdentity = useMemo(
    () =>
      `${workspaceId ?? 'pending-workspace'}::${runtimeBaseUrl ?? ''}::${contextId ?? 'primary'}::${
        showHiddenEntries ? 'show-hidden' : 'hide-hidden'
      }`,
    [contextId, runtimeBaseUrl, showHiddenEntries, workspaceId]
  );
  const previousWorkspaceIdentityRef = useRef<string | null>(null);
  const previousHiddenVisibilityRef = useRef(showHiddenEntries);

  const runtimeReady = Boolean(runtimeBaseUrl && runtimeBaseUrl.length > 0);

  const ensureRuntimeReady = useCallback(() => {
    if (!runtimeReady) {
      manager.state.setError('Workspace Runtime 尚未就緒');
      return false;
    }
    manager.state.setError(null);
    return true;
  }, [manager.state, runtimeReady]);

  const loadFileTree = useCallback(async () => {
    if (!ensureRuntimeReady()) {
      return;
    }
    await manager.loadTree();
  }, [ensureRuntimeReady, manager]);

  const refreshFileTree = useCallback(async () => {
    await loadFileTree();
  }, [loadFileTree]);

  const setShowHiddenEntries = useCallback(async (nextShowHiddenEntries: boolean) => {
    onShowHiddenEntriesChange?.(nextShowHiddenEntries);
  }, [onShowHiddenEntriesChange]);

  const toggleShowHiddenEntries = useCallback(async () => {
    onShowHiddenEntriesChange?.(!showHiddenEntries);
  }, [onShowHiddenEntriesChange, showHiddenEntries]);

  const refreshVersionControl = useCallback(async (options?: { includeBranches?: boolean; includeCommits?: boolean }) => {
    if (!workspaceId) {
      return;
    }

    await refreshVersionControlQueries(queryClient, workspaceId, { ...options, contextId });
  }, [contextId, queryClient, workspaceId]);

  const resetWorkspaceTreeState = useCallback(() => {
    manager.state.resetState();
    setPendingAction(null);
    setDraggedNode(null);
    setDropTarget(null);
  }, [manager.state]);

  useEffect(() => {
    const previousWorkspaceIdentity = previousWorkspaceIdentityRef.current;
    previousWorkspaceIdentityRef.current = workspaceIdentity;

    if (previousWorkspaceIdentity === null || previousWorkspaceIdentity === workspaceIdentity) {
      return;
    }

    resetWorkspaceTreeState();
  }, [resetWorkspaceTreeState, workspaceIdentity]);

  useEffect(() => {
    if (previousHiddenVisibilityRef.current === showHiddenEntries) {
      return;
    }

    previousHiddenVisibilityRef.current = showHiddenEntries;

    if (!runtimeReady) {
      return;
    }

    void manager.loadTree();
  }, [manager, runtimeReady, showHiddenEntries]);

  const selectFile = useCallback((filePath: string) => {
    manager.state.selectNode(ensureLeadingSlash(filePath));
  }, [manager.state]);

  const selectFileWithModifier = useCallback((filePath: string, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(ensureLeadingSlash(filePath), modifier);
  }, [manager.state]);

  const selectRange = useCallback((fromPath: string, toPath: string) => {
    const normalizedFrom = ensureLeadingSlash(fromPath);
    const normalizedTo = ensureLeadingSlash(toPath);
    manager.state.selectNode(normalizedFrom);
    manager.state.selectNodeWithModifier(normalizedTo, 'shift');
  }, [manager.state]);

  const toggleMultiSelect = useCallback((filePath: string) => {
    manager.state.selectNodeWithModifier(ensureLeadingSlash(filePath), 'ctrl');
  }, [manager.state]);

  const clearSelection = useCallback(() => {
    manager.state.clearSelection();
  }, [manager.state]);

  const selectAllFiles = useCallback((filePaths: string[]) => {
    const normalized = filePaths.map(ensureLeadingSlash);
    if (normalized.length === 0) {
      manager.state.clearSelection();
      return;
    }

    const [first, ...rest] = normalized;
    manager.state.selectNode(first);
    rest.forEach(path => manager.state.selectNodeWithModifier(path, 'ctrl'));
  }, [manager.state]);

  const expandNode = useCallback(async (nodePath: string) => {
    const normalized = ensureLeadingSlash(nodePath);
    const node = findManagerNode(manager.state.nodes, normalized);
    if (!node) return;
    // 使用 toggleDirectory 走懶載入路徑，避免全樹重載
    await manager.toggleDirectory(node);
  }, [manager]);

  const collapseNode = useCallback((nodePath: string) => {
    manager.state.collapseNode(ensureLeadingSlash(nodePath));
  }, [manager.state]);

  const createFile = useCallback(async (request: CreateFileRequest): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      await createFileOrFolder(
        runtimeBaseUrl!,
        request.name,
        request.path || '/',
        'file',
        request.content ?? '',
        contextId,
      );
      await refreshFileTree();
      await refreshVersionControl();
      return { success: true, message: t('common.fileOperations.success.fileCreated') };
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.fileCreateFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const createFolder = useCallback(async (request: CreateFileRequest): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      await createFileOrFolder(runtimeBaseUrl!, request.name, request.path || '/', 'directory', undefined, contextId);
      await refreshFileTree();
      await refreshVersionControl();
      return { success: true, message: t('common.fileOperations.success.folderCreated') };
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.folderCreateFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const renameFile = useCallback(async (request: RenameFileRequest): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const response = await renameRuntimeFile(runtimeBaseUrl!, request.oldPath, request.newPath, contextId);
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      return mapOperationResponse({ success: true, data: response }, t('common.fileOperations.success.fileRenamed'));
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.fileRenameFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const deleteFile = useCallback(async (request: DeleteFileRequest): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const response = await deleteRuntimeFile(runtimeBaseUrl!, request.path, request.recursive, contextId);
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      return mapOperationResponse({ success: true, data: response }, t('common.fileOperations.success.fileDeleted'));
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.fileDeleteFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const deleteFiles = useCallback(async (paths: string[], options?: { recursive?: boolean }): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    if (paths.length === 0) {
      return { success: true, message: t('common.fileOperations.success.noItemsToDelete'), data: { deleted: [], failed: [] } };
    }

    try {
      const response = await batchDeleteFiles(runtimeBaseUrl!, paths, options?.recursive, contextId);
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      const hasFailures = response.failed.length > 0;
      return {
        success: !hasFailures,
        message: hasFailures ? t('common.fileOperations.error.batchDeleteFailed') : t('common.fileOperations.success.fileDeleted'),
        data: response,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.batchDeleteFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const copyNode = useCallback(async (sourcePath: string, targetDirectory: string): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    const actionId = `copy-${Date.now()}`;
    const clearPending = (delay: number) => {
      if (typeof window !== 'undefined') {
        window.setTimeout(() => setPendingAction(null), delay);
      } else {
        setPendingAction(null);
      }
    };

    setPendingAction({
      id: actionId,
      type: 'copy',
      sourcePath,
      targetDirectory,
      status: 'running',
      progress: 0,
      errorMessage: null,
    });

    try {
      const data = await duplicateFile(runtimeBaseUrl!, sourcePath, targetDirectory, contextId);
      await refreshFileTree();
      await refreshVersionControl();
      setPendingAction({
        id: actionId,
        type: 'copy',
        sourcePath,
        targetDirectory,
        targetPath: data.destinationPath,
        status: 'succeeded',
        progress: 1,
        errorMessage: null,
      });
      clearPending(600);
      return { success: true, message: t('common.fileOperations.success.fileCopied'), data: { destinationPath: data.destinationPath } };
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.fileCopyFailed');
      setPendingAction({
        id: actionId,
        type: 'copy',
        sourcePath,
        targetDirectory,
        status: 'failed',
        progress: null,
        errorMessage: message,
      });
      clearPending(1500);
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const moveNode = useCallback(async (sourcePath: string, targetPath: string): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const response = await moveRuntimeFile(runtimeBaseUrl!, sourcePath, targetPath, false, contextId);
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      return mapOperationResponse({ success: true, data: response }, t('common.fileOperations.success.fileMoved'));
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.fileMoveFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const uploadFiles = useCallback(async (request: UploadFileRequest): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const uploadResult = await uploadRuntimeFiles(
        runtimeBaseUrl!,
        request.targetPath,
        request.files,
        request.useSystemTmp ?? false,
        {
          archiveAction: request.archiveAction,
          keepArchive: request.keepArchive,
          conflictStrategy: request.conflictStrategy,
          contextId,
        }
      );
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      const extractedCount = uploadResult.extractedPaths.length;
      return {
        success: true,
        message: extractedCount > 0 ? `已解壓 ${extractedCount} 個項目` : t('common.fileOperations.success.fileUploaded'),
        data: {
          uploadedPaths: uploadResult.uploadedPaths,
          extractedPaths: uploadResult.extractedPaths,
          affectedPaths: uploadResult.affectedPaths,
        },
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.fileUploadFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const downloadFile = useCallback(async (filePath: string): Promise<void> => {
    if (!ensureRuntimeReady()) {
      throw new Error(t('common.messages.workspaceRuntimeNotStarted'));
    }
    try {
      const downloadUrl = await downloadRuntimeFile(runtimeBaseUrl!, filePath, contextId);
      if (downloadUrl && typeof window !== 'undefined') {
        window.open(downloadUrl, '_blank', 'noopener');
      }
    } catch (error) {
      logger.error('下載檔案失敗', { error });
      throw error;
    }
  }, [contextId, ensureRuntimeReady, runtimeBaseUrl, t]);

  const downloadFiles = useCallback(async (filePaths: string[]): Promise<void> => {
    if (!ensureRuntimeReady()) {
      throw new Error(t('common.messages.workspaceRuntimeNotStarted'));
    }

    if (filePaths.length === 0) {
      return;
    }

    if (filePaths.length === 1) {
      await downloadFile(filePaths[0]);
      return;
    }

    try {
      const ticket = await batchDownloadFiles(runtimeBaseUrl!, filePaths, 'zip', contextId);
      if (ticket.status === 'succeeded') {
        const downloadUrl = ticket.statusUrl.startsWith('http')
          ? ticket.statusUrl
          : buildRuntimeUrl(runtimeBaseUrl!, ticket.statusUrl.replace(/^\/api\/v1\//, ''));
        if (typeof window !== 'undefined') {
          window.open(downloadUrl, '_blank', 'noopener');
        }
      } else {
        throw new Error(t('common.fileOperations.error.packageTaskFailed'));
      }
    } catch (error) {
      logger.error('批次下載檔案失敗', { error });
      throw error;
    }
  }, [contextId, downloadFile, ensureRuntimeReady, runtimeBaseUrl, t]);

  const readFileContent = useCallback(async (filePath: string): Promise<FileContent> => {
    if (!ensureRuntimeReady()) {
      throw new Error(t('common.messages.workspaceRuntimeNotStarted'));
    }

    const data = await fetchFileContent(runtimeBaseUrl!, filePath, contextId);
    return {
      content: data.content,
      encoding: data.encoding,
      size: data.size,
      lastModified: data.lastModified,
      versionId: data.versionId,
      contentHash: data.contentHash,
      language: data.language ?? null,
    };
  }, [contextId, ensureRuntimeReady, runtimeBaseUrl, t]);

  const saveFile = useCallback(async (filePath: string, content: string): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const response = await saveFileContent(runtimeBaseUrl!, filePath, content, contextId);
      await refreshVersionControl();
      return mapOperationResponse({ success: true, data: response }, t('common.fileOperations.success.fileSaved'));
    } catch (error) {
      const message = error instanceof Error ? error.message : t('common.fileOperations.error.fileSaveFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshVersionControl, runtimeBaseUrl, t]);

  const state = useMemo<FileTreeState>(() => {
    const expandedIds = manager.state.expandedIds;
    return {
      nodes: mapManagerNodes(manager.state.nodes, expandedIds),
      selectedFile: manager.state.selectedId ? ensureLeadingSlash(manager.state.selectedId) : null,
      selectedFiles: new Set(Array.from(manager.state.selectedIds).map(ensureLeadingSlash)),
      lastSelectedFile: manager.state.lastSelectedId ? ensureLeadingSlash(manager.state.lastSelectedId) : null,
      isLoading: manager.state.isLoading,
      error: manager.state.error,
      expandedNodes: new Set(Array.from(expandedIds).map(ensureLeadingSlash)),
      pendingAction,
      draggedNode,
      dropTarget,
      showHiddenEntries,
    };
  }, [draggedNode, dropTarget, manager.state.error, manager.state.expandedIds, manager.state.isLoading, manager.state.lastSelectedId, manager.state.nodes, manager.state.selectedId, manager.state.selectedIds, pendingAction, showHiddenEntries]);

  const actions = useMemo<FileTreeActions>(() => ({
    loadFileTree,
    refreshFileTree,
    setShowHiddenEntries,
    toggleShowHiddenEntries,
    selectFile,
    selectFileWithModifier,
    selectRange,
    toggleMultiSelect,
    clearSelection,
    selectAllFiles,
    expandNode,
    collapseNode,
    createFile,
    createFolder,
    renameFile,
    deleteFile,
    deleteFiles,
    copyNode,
    moveNode,
    uploadFiles,
    downloadFile,
    downloadFiles,
    readFileContent,
    saveFileContent: saveFile,
    setDraggedNode: setDraggedNode,
    setDropTarget: setDropTarget,
  }), [
    loadFileTree,
    refreshFileTree,
    setShowHiddenEntries,
    toggleShowHiddenEntries,
    selectFile,
    selectFileWithModifier,
    selectRange,
    toggleMultiSelect,
    clearSelection,
    selectAllFiles,
    expandNode,
    collapseNode,
    createFile,
    createFolder,
    renameFile,
    deleteFile,
    deleteFiles,
    copyNode,
    moveNode,
    uploadFiles,
    downloadFile,
    downloadFiles,
    readFileContent,
    saveFile,
  ]);

  return { state, actions };
}

export type { WorkspaceFileTreeAdapterResult };
