import { useCallback, useMemo, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useFileOperations');
import type {
  FileTreeDataAdapter,
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
  adapter: FileTreeDataAdapter;
  onSuccess?: (message: string) => void;
  onError?: (error: Error) => void;
  onComplete?: () => void;
}

export interface UseFileOperationsReturn {

  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
  isUploading: boolean;
  isDownloading: boolean;
  isOperating: boolean;


  createFile: (path: string, content?: string) => Promise<FileOperationResponse>;
  createDirectory: (path: string) => Promise<FileOperationResponse>;
  readFile: (path: string) => Promise<string>;
  updateFile: (path: string, content: string) => Promise<FileOperationResponse>;
  deleteFile: (path: string, recursive?: boolean) => Promise<FileOperationResponse>;


  batchDelete: (paths: string[], recursive?: boolean) => Promise<BatchDeleteResponse>;


  renameFile: (oldPath: string, newPath: string) => Promise<FileOperationResponse>;
  moveFile: (sourcePath: string, targetPath: string) => Promise<FileOperationResponse>;


  uploadFiles: (options: FileUploadOptions) => Promise<FileUploadResult[]>;
  downloadFile: (options: FileDownloadOptions) => Promise<void>;


  executeOperation: (request: FileOperationRequest) => Promise<FileOperationResponse>;
}

export function useFileOperations(
  options: UseFileOperationsOptions
): UseFileOperationsReturn {
  const { adapter, onSuccess, onError, onComplete } = options;
  const stableAdapter = useMemo(() => adapter, [adapter]);


  const [isCreating, setIsCreating] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isDownloading, setIsDownloading] = useState(false);

  const isOperating = isCreating || isUpdating || isDeleting || isUploading || isDownloading;


  const withErrorHandling = useCallback(
    async <T,>(
      operation: () => Promise<T>,
      setLoading: (loading: boolean) => void,
      successMessage?: string
    ): Promise<T> => {
      logger.debug('withErrorHandling: starting operation');
      setLoading(true);
      try {
        logger.debug('withErrorHandling: executing operation()');
        const result = await operation();
        logger.debug('withErrorHandling: operation succeeded', { result });
        if (successMessage && onSuccess) {
          logger.debug('withErrorHandling: calling onSuccess', { successMessage });
          onSuccess(successMessage);
        }
        return result;
      } catch (error) {
        logger.error('withErrorHandling: operation failed', { error });
        if (onError) {
          logger.debug('withErrorHandling: calling onError');
          onError(error instanceof Error ? error : new Error('Operation failed'));
        }
        throw error;
      } finally {
        logger.debug('withErrorHandling: setting loading to false');
        setLoading(false);
        if (onComplete) {
          logger.debug('withErrorHandling: calling onComplete');
          onComplete();
        }
      }
    },
    [onSuccess, onError, onComplete]
  );


  const createFile = useCallback(
    async (path: string, content = ''): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.create({
          type: 'create',
          path,
          content,
          isDirectory: false,
        }),
        setIsCreating,
        SUCCESS_MESSAGES.FILE_CREATED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const createDirectory = useCallback(
    async (path: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.create({
          type: 'create',
          path,
          isDirectory: true,
        }),
        setIsCreating,
        SUCCESS_MESSAGES.FILE_CREATED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const readFile = useCallback(
    async (path: string): Promise<string> => {
      return withErrorHandling(
        () => stableAdapter.getContent(path),
        setIsUpdating
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const updateFile = useCallback(
    async (path: string, content: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.update(path, content),
        setIsUpdating,
        SUCCESS_MESSAGES.FILE_UPDATED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const deleteFile = useCallback(
    async (path: string, recursive = false): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.delete(path, recursive),
        setIsDeleting,
        SUCCESS_MESSAGES.FILE_DELETED
      );
    },
    [stableAdapter, withErrorHandling]
  );


  const batchDelete = useCallback(
    async (paths: string[], recursive = false): Promise<BatchDeleteResponse> => {
      return withErrorHandling(
        () => stableAdapter.batchDelete({ paths, recursive }),
        setIsDeleting,
        paths.length > 1 ? SUCCESS_MESSAGES.BATCH_DELETE_SUCCESS : SUCCESS_MESSAGES.FILE_DELETED
      );
    },
    [stableAdapter, withErrorHandling]
  );


  const renameFile = useCallback(
    async (oldPath: string, newPath: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.move(oldPath, newPath),
        setIsUpdating,
        SUCCESS_MESSAGES.FILE_RENAMED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const moveFile = useCallback(
    async (sourcePath: string, targetPath: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.move(sourcePath, targetPath),
        setIsUpdating,
        SUCCESS_MESSAGES.FILE_MOVED
      );
    },
    [stableAdapter, withErrorHandling]
  );


  const uploadFiles = useCallback(
    async (uploadOptions: FileUploadOptions): Promise<FileUploadResult[]> => {
      logger.debug('uploadFiles: starting upload', {
        targetPath: uploadOptions.targetPath,
        filesCount: uploadOptions.files.length,
        files: uploadOptions.files.map(f => ({ name: f.name, size: f.size }))
      });
      return withErrorHandling(
        () => {
          logger.debug('uploadFiles: calling adapter.upload()');
          return stableAdapter.upload(uploadOptions);
        },
        setIsUploading,
        SUCCESS_MESSAGES.FILE_UPLOADED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const downloadFile = useCallback(
    async (downloadOptions: FileDownloadOptions): Promise<void> => {
      return withErrorHandling(
        () => stableAdapter.download(downloadOptions),
        setIsDownloading
      );
    },
    [stableAdapter, withErrorHandling]
  );


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
          return moveFile(request.path, request.targetPath!);
        case 'move':
          return moveFile(request.path, request.targetPath!);
        case 'upload':
          throw new Error('Use uploadFiles for upload operations');
        case 'download':
          throw new Error('Use downloadFile for download operations');
        default:
          throw new Error(`Unsupported operation type: ${request.type}`);
      }
    },
    [createFile, createDirectory, readFile, updateFile, deleteFile, renameFile, moveFile]
  );

  return {

    isCreating,
    isUpdating,
    isDeleting,
    isUploading,
    isDownloading,
    isOperating,


    createFile,
    createDirectory,
    readFile,
    updateFile,
    deleteFile,


    batchDelete,


    renameFile,
    moveFile,


    uploadFiles,
    downloadFile,


    executeOperation,
  };
}
