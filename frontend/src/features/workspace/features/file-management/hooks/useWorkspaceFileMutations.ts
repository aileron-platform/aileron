import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { useWorkspaceVersionControlSession } from '../../../integrations/version-control/workspaceVersionControlSession';
import {
  batchDeleteFiles,
  buildArchiveDownloadUrl,
  createFileOrFolder,
  deleteFile as deleteRuntimeFile,
  downloadFile as downloadRuntimeFile,
  fetchArchiveDownloadStatus,
  fetchFileContent,
  moveFile as moveRuntimeFile,
  renameFile as renameRuntimeFile,
  saveFileContent as saveRuntimeFileContent,
  startArchiveDownload,
  executeRuntimeFileConflictOperation,
  preflightRuntimeFileConflicts,
} from '../../../api/workspaceRuntimeApi';
import type {
  CreateFilePayload,
  DeleteFilePayload,
  FileContent,
  FileOperationResult,
  PendingFileAction,
  RenameFilePayload,
  UploadFilePayload,
} from '../model/fileManagementTypes';

const logger = createLogger('useWorkspaceFileMutations');

interface UseWorkspaceFileMutationsOptions {
  workspaceId?: string;
  runtimeBaseUrl?: string | null;
  contextId?: string | null;
  ensureRuntimeReady: () => boolean;
  refreshFileTree: () => Promise<void>;
}

const mapOperationResponse = (
  response: { success: boolean; message?: string; data?: unknown; revision?: string },
  fallbackMessage: string,
): FileOperationResult => ({
  success: response.success,
  message: response.message ?? fallbackMessage,
  data: response.data,
  revision: response.revision,
});

export const useWorkspaceFileMutations = ({
  workspaceId,
  runtimeBaseUrl,
  contextId,
  ensureRuntimeReady,
  refreshFileTree,
}: UseWorkspaceFileMutationsOptions) => {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const versionControl = useWorkspaceVersionControlSession({
    workspaceId: workspaceId ?? '',
    runtimeBaseUrl: runtimeBaseUrl ?? '',
    contextId,
  });
  const [pendingAction, setPendingAction] = useState<PendingFileAction | null>(null);

  const refreshVersionControl = useCallback(async (
    options?: { includeBranches?: boolean; includeCommits?: boolean },
  ) => {
    if (!workspaceId) {
      return;
    }

    const groups = options?.includeBranches || options?.includeCommits
      ? ['changes', 'history'] as const
      : ['changes'] as const;
    await versionControl.refresh(queryClient, groups);
  }, [queryClient, versionControl, workspaceId]);

  const clearPendingAction = useCallback(() => {
    setPendingAction(null);
  }, []);

  const createFile = useCallback(async (
    request: CreateFilePayload,
  ): Promise<FileOperationResult> => {
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
      const message = error instanceof Error
        ? error.message
        : t('common.fileOperations.error.fileCreateFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const createFolder = useCallback(async (
    request: CreateFilePayload,
  ): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      await createFileOrFolder(
        runtimeBaseUrl!,
        request.name,
        request.path || '/',
        'directory',
        undefined,
        contextId,
      );
      await refreshFileTree();
      await refreshVersionControl();
      return { success: true, message: t('common.fileOperations.success.folderCreated') };
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : t('common.fileOperations.error.folderCreateFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const renameFile = useCallback(async (
    request: RenameFilePayload,
  ): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const response = await renameRuntimeFile(
        runtimeBaseUrl!,
        request.oldPath,
        request.newPath,
        contextId,
      );
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      return mapOperationResponse(
        { success: true, data: response },
        t('common.fileOperations.success.fileRenamed'),
      );
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : t('common.fileOperations.error.fileRenameFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const deleteFile = useCallback(async (
    request: DeleteFilePayload,
  ): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const response = await deleteRuntimeFile(
        runtimeBaseUrl!,
        request.path,
        request.recursive,
        contextId,
      );
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      return mapOperationResponse(
        { success: true, data: response },
        t('common.fileOperations.success.fileDeleted'),
      );
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : t('common.fileOperations.error.fileDeleteFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const deleteFiles = useCallback(async (
    paths: string[],
    options?: { recursive?: boolean },
  ): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    if (paths.length === 0) {
      return {
        success: true,
        message: t('common.fileOperations.success.noItemsToDelete'),
        data: { deleted: [], failed: [] },
      };
    }

    try {
      const response = await batchDeleteFiles(
        runtimeBaseUrl!,
        paths,
        options?.recursive,
        contextId,
      );
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      const hasFailures = response.failed.length > 0;
      return {
        success: !hasFailures,
        message: hasFailures
          ? t('common.fileOperations.error.batchDeleteFailed')
          : t('common.fileOperations.success.fileDeleted'),
        data: response,
      };
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : t('common.fileOperations.error.batchDeleteFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const moveNode = useCallback(async (
    sourcePath: string,
    targetPath: string,
  ): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const response = await moveRuntimeFile(
        runtimeBaseUrl!,
        sourcePath,
        targetPath,
        contextId,
      );
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      return mapOperationResponse(
        { success: true, data: response },
        t('common.fileOperations.success.fileMoved'),
      );
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : t('common.fileOperations.error.fileMoveFailed');
      return { success: false, message };
    }
  }, [contextId, ensureRuntimeReady, refreshFileTree, refreshVersionControl, runtimeBaseUrl, t]);

  const uploadFiles = useCallback(async (
    request: UploadFilePayload,
  ): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const controller = new AbortController();
      const preflightRequest = {
        operation: 'upload' as const,
        targetPath: request.targetPath,
        sources: request.files.map((file) => ({ sourcePath: file.name, entryType: 'file' as const })),
        archivePath: null,
      };
      const preflight = await preflightRuntimeFileConflicts(
        runtimeBaseUrl!,
        preflightRequest,
        { signal: controller.signal, contextId },
      );
      if (preflight.conflicts.length > 0) {
        return { success: false, message: t('common.fileOperations.error.fileUploadFailed') };
      }
      const uploadResult = await executeRuntimeFileConflictOperation(
        runtimeBaseUrl!,
        {
          ...preflightRequest,
          defaultStrategy: 'cancel',
          resolutions: [],
          payload: { files: request.files, contextId },
        },
        { signal: controller.signal },
      );
      await refreshFileTree();
      await refreshVersionControl({ includeBranches: true });
      const affectedPaths = uploadResult.items.flatMap((item) => item.finalPath ? [item.finalPath] : []);
      return {
        success: true,
        message: t('common.fileOperations.success.fileUploaded'),
        data: {
          items: uploadResult.items,
          affectedPaths,
        },
      };
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : t('common.fileOperations.error.fileUploadFailed');
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
      logger.error('Download file failed', { error });
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
      const accepted = await startArchiveDownload(runtimeBaseUrl!, {
        paths: filePaths,
        archiveFormat: 'zip',
        contextId,
      });
      for (let attempt = 0; attempt < 120; attempt += 1) {
        const status = await fetchArchiveDownloadStatus(runtimeBaseUrl!, accepted.operationId);
        if (status.status === 'completed' && status.result) {
          const downloadUrl = buildArchiveDownloadUrl(
            runtimeBaseUrl!,
            status.result.downloadUrl,
          );
          if (typeof window !== 'undefined') {
            window.open(downloadUrl, '_blank', 'noopener');
          }
          return;
        }
        if (status.status === 'failed' || status.status === 'expired') {
          throw new Error(status.error ?? status.message);
        }
        await new Promise(resolve => globalThis.setTimeout(resolve, 1000));
      }
      throw new Error(t('common.fileOperations.error.packageTaskFailed'));
    } catch (error) {
      logger.error('Batch download files failed', { error });
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
      revision: data.revision,
      language: data.language ?? null,
    };
  }, [contextId, ensureRuntimeReady, runtimeBaseUrl, t]);

  const saveFileContent = useCallback(async (
    filePath: string,
    content: string,
    revision?: string | null,
  ): Promise<FileOperationResult> => {
    if (!ensureRuntimeReady()) {
      return { success: false, message: t('common.messages.workspaceRuntimeNotStarted') };
    }

    try {
      const response = await saveRuntimeFileContent(
        runtimeBaseUrl!,
        filePath,
        content,
        contextId,
        revision,
      );
      await refreshVersionControl();
      return mapOperationResponse(
        { success: true, data: response, revision: response.revision },
        t('common.fileOperations.success.fileSaved'),
      );
    } catch (error) {
      const message = error instanceof Error
        ? error.message
        : t('common.fileOperations.error.fileSaveFailed');
      const errorCode = typeof error === 'object' && error !== null && 'errorCode' in error
        ? String((error as { errorCode?: unknown }).errorCode)
        : undefined;
      return { success: false, message, errorCode };
    }
  }, [contextId, ensureRuntimeReady, refreshVersionControl, runtimeBaseUrl, t]);

  return {
    pendingAction,
    clearPendingAction,
    createFile,
    createFolder,
    renameFile,
    deleteFile,
    deleteFiles,
    moveNode,
    uploadFiles,
    downloadFile,
    downloadFiles,
    readFileContent,
    saveFileContent,
  };
};
