/**
 * useFileOperations Hook
 *
 * 提供所有檔案操作功能，包括：
 * - CRUD 操作（建立、讀取、更新、刪除）
 * - 批次操作（批次刪除）
 * - 檔案管理（重新命名、移動、複製）
 * - 檔案傳輸（上傳、下載）
 */

import { useCallback, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useFileOperations');
import { FileTreeApiAdapter } from '../services/fileTreeAdapter';
import type {
  FileTreeApiConfig,
  FileOperationRequest,
  FileOperationResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileUploadOptions,
  FileUploadResult,
  FileDownloadOptions,
} from '../types';
import { SUCCESS_MESSAGES } from '../constants';

export interface UseFileOperationsOptions {
  /** API 配置 */
  apiConfig: FileTreeApiConfig;
  /** 操作成功回調 */
  onSuccess?: (message: string) => void;
  /** 操作失敗回調 */
  onError?: (error: Error) => void;
  /** 操作完成回調（無論成功或失敗） */
  onComplete?: () => void;
}

export interface UseFileOperationsReturn {
  // 狀態
  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
  isUploading: boolean;
  isDownloading: boolean;
  isOperating: boolean;

  // CRUD 操作
  createFile: (path: string, content?: string) => Promise<FileOperationResponse>;
  createDirectory: (path: string) => Promise<FileOperationResponse>;
  readFile: (path: string) => Promise<string>;
  updateFile: (path: string, content: string) => Promise<FileOperationResponse>;
  deleteFile: (path: string, recursive?: boolean) => Promise<FileOperationResponse>;

  // 批次操作
  batchDelete: (paths: string[], recursive?: boolean) => Promise<BatchDeleteResponse>;

  // 檔案管理
  renameFile: (oldPath: string, newPath: string) => Promise<FileOperationResponse>;
  moveFile: (sourcePath: string, targetPath: string) => Promise<FileOperationResponse>;

  // 檔案傳輸
  uploadFiles: (options: FileUploadOptions) => Promise<FileUploadResult[]>;
  downloadFile: (options: FileDownloadOptions) => Promise<void>;

  // 通用操作
  executeOperation: (request: FileOperationRequest) => Promise<FileOperationResponse>;
}

export function useFileOperations(
  options: UseFileOperationsOptions
): UseFileOperationsReturn {
  const { apiConfig, onSuccess, onError, onComplete } = options;

  // 創建 API 適配器
  const adapter = new FileTreeApiAdapter(apiConfig);

  // 操作狀態
  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const isOperating = isCreating || isUpdating || isDeleting || isUploading || isDownloading;

  // 錯誤處理包裝器
  const withErrorHandling = useCallback(
    async <T,>(
      operation: () => Promise<T>,
      setLoading: (loading: boolean) => void,
      successMessage?: string
    ): Promise<T> => {
      logger.debug('withErrorHandling: 開始執行操作');
      setLoading(true);
      try {
        logger.debug('withErrorHandling: 執行 operation()');
        const result = await operation();
        logger.debug('withErrorHandling: 操作成功', { result });
        if (successMessage && onSuccess) {
          logger.debug('withErrorHandling: 呼叫 onSuccess', { successMessage });
          onSuccess(successMessage);
        }
        return result;
      } catch (error) {
        logger.error('withErrorHandling: 操作失敗', { error });
        if (onError) {
          logger.debug('withErrorHandling: 呼叫 onError');
          onError(error instanceof Error ? error : new Error('操作失敗'));
        }
        throw error;
      } finally {
        logger.debug('withErrorHandling: 設置 loading 為 false');
        setLoading(false);
        if (onComplete) {
          logger.debug('withErrorHandling: 呼叫 onComplete');
          onComplete();
        }
      }
    },
    [onSuccess, onError, onComplete]
  );

  // CRUD 操作
  const createFile = useCallback(
    async (path: string, content = ''): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => adapter.create({
          type: 'create',
          path,
          content,
          isDirectory: false,
        }),
        setIsCreating,
        SUCCESS_MESSAGES.FILE_CREATED
      );
    },
    [adapter, withErrorHandling]
  );

  const createDirectory = useCallback(
    async (path: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => adapter.create({
          type: 'create',
          path,
          isDirectory: true,
        }),
        setIsCreating,
        SUCCESS_MESSAGES.FILE_CREATED
      );
    },
    [adapter, withErrorHandling]
  );

  const readFile = useCallback(
    async (path: string): Promise<string> => {
      return withErrorHandling(
        () => adapter.getContent(path),
        setIsUpdating
      );
    },
    [adapter, withErrorHandling]
  );

  const updateFile = useCallback(
    async (path: string, content: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => adapter.update(path, content),
        setIsUpdating,
        SUCCESS_MESSAGES.FILE_UPDATED
      );
    },
    [adapter, withErrorHandling]
  );

  const deleteFile = useCallback(
    async (path: string, recursive = false): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => adapter.delete(path, recursive),
        setIsDeleting,
        SUCCESS_MESSAGES.FILE_DELETED
      );
    },
    [adapter, withErrorHandling]
  );

  // 批次操作
  const batchDelete = useCallback(
    async (paths: string[], recursive = false): Promise<BatchDeleteResponse> => {
      return withErrorHandling(
        () => adapter.batchDelete({ paths, recursive }),
        setIsDeleting,
        paths.length > 1 ? SUCCESS_MESSAGES.BATCH_DELETE_SUCCESS : SUCCESS_MESSAGES.FILE_DELETED
      );
    },
    [adapter, withErrorHandling]
  );

  // 檔案管理
  const renameFile = useCallback(
    async (oldPath: string, newPath: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => adapter.rename(oldPath, newPath),
        setIsUpdating,
        SUCCESS_MESSAGES.FILE_RENAMED
      );
    },
    [adapter, withErrorHandling]
  );

  const moveFile = useCallback(
    async (sourcePath: string, targetPath: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => adapter.move(sourcePath, targetPath),
        setIsUpdating,
        SUCCESS_MESSAGES.FILE_MOVED
      );
    },
    [adapter, withErrorHandling]
  );

  // 檔案傳輸
  const uploadFiles = useCallback(
    async (uploadOptions: FileUploadOptions): Promise<FileUploadResult[]> => {
      logger.debug('uploadFiles: 開始上傳', {
        targetPath: uploadOptions.targetPath,
        filesCount: uploadOptions.files.length,
        files: uploadOptions.files.map(f => ({ name: f.name, size: f.size }))
      });
      return withErrorHandling(
        () => {
          logger.debug('uploadFiles: 呼叫 adapter.upload()');
          return adapter.upload(uploadOptions);
        },
        setIsUploading,
        SUCCESS_MESSAGES.FILE_UPLOADED
      );
    },
    [adapter, withErrorHandling]
  );

  const downloadFile = useCallback(
    async (downloadOptions: FileDownloadOptions): Promise<void> => {
      return withErrorHandling(
        () => adapter.download(downloadOptions),
        setIsDownloading
      );
    },
    [adapter, withErrorHandling]
  );

  // 通用操作
  const executeOperation = useCallback(
    async (request: FileOperationRequest): Promise<FileOperationResponse> => {
      switch (request.type) {
        case 'create':
          return request.isDirectory
            ? createDirectory(request.path)
            : createFile(request.path, request.content);
        case 'read':
          const content = await readFile(request.path);
          return { success: true, data: { content } };
        case 'update':
          return updateFile(request.path, request.content || '');
        case 'delete':
          return deleteFile(request.path, request.recursive);
        case 'rename':
          return renameFile(request.path, request.targetPath!);
        case 'move':
          return moveFile(request.path, request.targetPath!);
        case 'upload':
          throw new Error('請使用 uploadFiles 方法進行上傳');
        case 'download':
          throw new Error('請使用 downloadFile 方法進行下載');
        default:
          throw new Error(`不支援的操作類型: ${request.type}`);
      }
    },
    [createFile, createDirectory, readFile, updateFile, deleteFile, renameFile, moveFile]
  );

  return {
    // 狀態
    isCreating,
    isUpdating,
    isDeleting,
    isUploading,
    isDownloading,
    isOperating,

    // CRUD 操作
    createFile,
    createDirectory,
    readFile,
    updateFile,
    deleteFile,

    // 批次操作
    batchDelete,

    // 檔案管理
    renameFile,
    moveFile,

    // 檔案傳輸
    uploadFiles,
    downloadFile,

    // 通用操作
    executeOperation,
  };
}

