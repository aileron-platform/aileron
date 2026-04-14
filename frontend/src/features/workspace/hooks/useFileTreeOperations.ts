/**
 * useFileTreeOperations Hook
 * 處理檔案樹的所有操作邏輯
 */

import { useCallback } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useFileTreeOperations');
import { useI18n } from '@/shared/hooks/useI18n';
import type { WorkspaceAction } from '../providers/workspaceState.types';
import type {
  FileNode,
  FileTreeActions,
  FileOperationResult,
  CreateFileRequest,
  RenameFileRequest,
  DeleteFileRequest,
  UploadFileRequest,
  FileContent,
} from '../features/file-management/types';
import {
  buildRuntimeUrl,
  fetchFileTree,
  fetchNodeChildren,
  fetchFileContent,
  saveFileContent,
  createFileOrFolder,
  renameFile as renameFileApi,
  deleteFile as deleteFileApi,
  batchDeleteFiles,
  duplicateFile,
  uploadFiles as uploadFilesApi,
  downloadFile as downloadFileApi,
  batchDownloadFiles as batchDownloadFilesApi,
  moveFile as moveFileApi,
} from '../services/workspaceRuntimeApi';

export interface UseFileTreeOperationsProps {
  runtimeBaseUrl: string | null;
  workspaceRuntimeError: string | null;
  dispatch: React.Dispatch<WorkspaceAction>;
  customRefreshFileTree?: () => Promise<void>;
}

export const useFileTreeOperations = ({
  runtimeBaseUrl,
  workspaceRuntimeError,
  dispatch,
  customRefreshFileTree,
}: UseFileTreeOperationsProps) => {
  const { t } = useI18n();

  // 載入檔案樹
  const loadFileTree = useCallback(async () => {
    if (!runtimeBaseUrl) {
      if (workspaceRuntimeError) {
        dispatch({ type: 'SET_FILE_TREE_ERROR', payload: workspaceRuntimeError });
      }
      return;
    }

    dispatch({ type: 'SET_FILE_TREE_LOADING', payload: true });
    try {
      const nodes = await fetchFileTree(runtimeBaseUrl);
      dispatch({ type: 'SET_FILE_TREE_NODES', payload: nodes });
      dispatch({ type: 'SET_FILE_TREE_ERROR', payload: null });
    } catch (error) {
      const message = error instanceof Error ? error.message : t('workspace.fileManagement.error.loadFailed');
      dispatch({ type: 'SET_FILE_TREE_ERROR', payload: message });
    } finally {
      dispatch({ type: 'SET_FILE_TREE_LOADING', payload: false });
    }
  }, [runtimeBaseUrl, workspaceRuntimeError, dispatch, t]);

  const refreshFileTree = useCallback(async () => {
    if (customRefreshFileTree) {
      await customRefreshFileTree();
    } else {
      await loadFileTree();
    }
  }, [customRefreshFileTree, loadFileTree]);

  // 載入節點子項
  const loadNodeChildren = useCallback(
    async (nodePath: string, parentDepth: number): Promise<void> => {
      if (!runtimeBaseUrl) {
        return;
      }

      dispatch({ type: 'SET_NODE_LOADING', payload: { path: nodePath, isLoading: true } });

      try {
        const children = await fetchNodeChildren(runtimeBaseUrl, nodePath, parentDepth);
        dispatch({ type: 'SET_NODE_CHILDREN', payload: { path: nodePath, children } });
        dispatch({ type: 'EXPAND_NODE', payload: nodePath });
      } catch (error) {
        logger.error('載入子節點失敗', { error });
        dispatch({ type: 'SET_NODE_LOADING', payload: { path: nodePath, isLoading: false } });
      }
    },
    [runtimeBaseUrl, dispatch]
  );

  // 建立檔案
  const createFile = useCallback(
    async (request: CreateFileRequest): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      try {
        await createFileOrFolder(runtimeBaseUrl, request.name, request.path, 'file', request.content);
        await refreshFileTree();
        return { success: true, message: t('workspace.fileManagement.tree.notifications.createFileSuccess') };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.createFileFailed');
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, refreshFileTree, t]
  );

  // 建立資料夾
  const createFolder = useCallback(
    async (request: CreateFileRequest): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      try {
        await createFileOrFolder(runtimeBaseUrl, request.name, request.path, 'directory');
        await refreshFileTree();
        return { success: true, message: t('workspace.fileManagement.tree.notifications.createFolderSuccess') };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.createFolderFailed');
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, refreshFileTree, t]
  );

  // 重新命名檔案
  const renameFile = useCallback(
    async (request: RenameFileRequest): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      try {
        await renameFileApi(runtimeBaseUrl, request.oldPath, request.newPath);
        await refreshFileTree();
        return { success: true, message: t('workspace.fileManagement.tree.notifications.renameSuccess') };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.renameFailed');
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, refreshFileTree, t]
  );

  // 刪除檔案
  const deleteFile = useCallback(
    async (request: DeleteFileRequest): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      try {
        const data = await deleteFileApi(runtimeBaseUrl, request.path, request.recursive);
        await refreshFileTree();
        return { success: true, message: t('workspace.fileManagement.tree.notifications.deleteSuccess'), data };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.deleteFailed');
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, refreshFileTree, t]
  );

  // 批次刪除檔案
  const deleteFiles = useCallback(
    async (paths: string[], options?: { recursive?: boolean }): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      if (paths.length === 0) {
        return {
          success: true,
          message: t('workspace.fileManagement.tree.notifications.batchDeleteSuccess'),
          data: { deleted: [], failed: [] },
        };
      }

      try {
        const data = await batchDeleteFiles(runtimeBaseUrl, paths, options?.recursive);
        await refreshFileTree();
        const hasFailures = data.failed.length > 0;
        return {
          success: !hasFailures,
          message: hasFailures ? t('workspace.fileManagement.tree.notifications.batchDeletePartial') : t('workspace.fileManagement.tree.notifications.batchDeleteSuccess'),
          data,
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.batchDeleteFailed');
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, refreshFileTree, t]
  );

  // 複製節點
  const copyNode = useCallback(
    async (sourcePath: string, targetDirectory: string): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      const actionId = `copy-${Date.now()}`;
      dispatch({
        type: 'SET_PENDING_FILE_ACTION',
        payload: {
          id: actionId,
          type: 'copy',
          sourcePath,
          targetDirectory,
          status: 'running',
          progress: 0,
          errorMessage: null,
        },
      });

      const clearPending = (delay: number) => {
        if (typeof window !== 'undefined') {
          window.setTimeout(() => {
            dispatch({ type: 'SET_PENDING_FILE_ACTION', payload: null });
          }, delay);
        } else {
          dispatch({ type: 'SET_PENDING_FILE_ACTION', payload: null });
        }
      };

      try {
        const data = await duplicateFile(runtimeBaseUrl, sourcePath, targetDirectory);
        await refreshFileTree();
        dispatch({
          type: 'SET_PENDING_FILE_ACTION',
          payload: {
            id: actionId,
            type: 'copy',
            sourcePath,
            targetDirectory,
            targetPath: data.destinationPath,
            status: 'succeeded',
            progress: 1,
            errorMessage: null,
          },
        });
        clearPending(600);
        return { success: true, message: t('workspace.fileManagement.tree.notifications.copySuccess'), data: { destinationPath: data.destinationPath } };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.copyFailed');
        dispatch({
          type: 'SET_PENDING_FILE_ACTION',
          payload: {
            id: actionId,
            type: 'copy',
            sourcePath,
            targetDirectory,
            status: 'failed',
            progress: null,
            errorMessage: message,
          },
        });
        clearPending(1500);
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, refreshFileTree, dispatch, t]
  );

  // 上傳檔案
  const uploadFiles = useCallback(
    async (request: UploadFileRequest): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      try {
        const uploadResult = await uploadFilesApi(
          runtimeBaseUrl,
          request.targetPath,
          request.files,
          request.useSystemTmp ?? false,
          {
            archiveAction: request.archiveAction,
            keepArchive: request.keepArchive,
            conflictStrategy: request.conflictStrategy,
          }
        );
        await refreshFileTree();
        const extractedCount = uploadResult.extractedPaths.length;
        const message = extractedCount > 0
          ? `已解壓 ${extractedCount} 個項目`
          : t('workspace.fileManagement.tree.notifications.uploadSuccess');
        return {
          success: true,
          message,
          data: {
            uploadedPaths: uploadResult.uploadedPaths,
            extractedPaths: uploadResult.extractedPaths,
            affectedPaths: uploadResult.affectedPaths,
          },
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.uploadFailed');
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, refreshFileTree, t]
  );

  // 下載檔案
  const downloadFile = useCallback(
    async (filePath: string): Promise<void> => {
      if (!runtimeBaseUrl) {
        throw new Error(workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'));
      }

      try {
        const downloadUrl = await downloadFileApi(runtimeBaseUrl, filePath);
        if (downloadUrl && typeof window !== 'undefined') {
          window.open(downloadUrl, '_blank', 'noopener');
        }
      } catch (error) {
        logger.error('下載檔案失敗', { error });
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, t]
  );

  // 批次下載檔案
  const downloadFiles = useCallback(
    async (filePaths: string[]): Promise<void> => {
      if (!runtimeBaseUrl) {
        throw new Error(workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'));
      }

      if (filePaths.length === 0) {
        return;
      }

      // 如果只有一個檔案，直接下載
      if (filePaths.length === 1) {
        return downloadFile(filePaths[0]);
      }

      // 多個檔案，使用批次下載（打包成 ZIP）
      try {
        // 1. 建立打包任務
        const ticket = await batchDownloadFilesApi(runtimeBaseUrl, filePaths, 'zip');

        // 2. 檢查任務狀態
        if (ticket.status === 'succeeded') {
          const downloadUrl = ticket.statusUrl.startsWith('http')
            ? ticket.statusUrl
            : buildRuntimeUrl(runtimeBaseUrl, ticket.statusUrl.replace(/^\/api\/v1\//, ''));
          if (typeof window !== 'undefined') {
            window.open(downloadUrl, '_blank', 'noopener');
          }
        } else {
          throw new Error(t('workspace.fileManagement.tree.notifications.downloadFailed'));
        }
      } catch (error) {
        logger.error('批次下載檔案失敗', { error });
        throw error;
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, downloadFile, t]
  );

  // 讀取檔案內容
  const readFileContent = useCallback(
    async (filePath: string): Promise<FileContent> => {
      if (!runtimeBaseUrl) {
        throw new Error(workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'));
      }

      const data = await fetchFileContent(runtimeBaseUrl, filePath);
      return {
        content: data.content,
        encoding: data.encoding,
        size: data.size,
        lastModified: data.lastModified,
        versionId: data.versionId,
        contentHash: data.contentHash,
        language: data.language ?? null,
      };
    },
    [runtimeBaseUrl, workspaceRuntimeError, t]
  );

  // 儲存檔案內容
  const saveFileContentHandler = useCallback(
    async (filePath: string, content: string): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      try {
        const data = await saveFileContent(runtimeBaseUrl, filePath, content);
        return {
          success: true,
          message: t('workspace.fileManagement.tree.notifications.saveSuccess'),
          data: { versionId: data.versionId },
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.saveFailed');
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, t]
  );

  // 移動檔案或資料夾
  const moveNode = useCallback(
    async (sourcePath: string, targetPath: string): Promise<FileOperationResult> => {
      if (!runtimeBaseUrl) {
        return {
          success: false,
          message: workspaceRuntimeError ?? t('workspace.fileManagement.runtime.unavailableDescription'),
        };
      }

      try {
        await moveFileApi(runtimeBaseUrl, sourcePath, targetPath, false);
        await refreshFileTree();
        return { success: true, message: t('workspace.fileManagement.tree.notifications.moveSuccess') };
      } catch (error) {
        const message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.moveFailed');
        return { success: false, message };
      }
    },
    [runtimeBaseUrl, workspaceRuntimeError, refreshFileTree, t]
  );

  // 設定拖曳節點
  const setDraggedNode = useCallback(
    (nodePath: string | null) => {
      dispatch({ type: 'SET_DRAGGED_NODE', payload: nodePath });
    },
    [dispatch]
  );

  // 設定放置目標
  const setDropTarget = useCallback(
    (nodePath: string | null) => {
      dispatch({ type: 'SET_DROP_TARGET', payload: nodePath });
    },
    [dispatch]
  );

  return {
    loadFileTree,
    refreshFileTree,
    loadNodeChildren,
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
    saveFileContent: saveFileContentHandler,
    setDraggedNode,
    setDropTarget,
  };
};
