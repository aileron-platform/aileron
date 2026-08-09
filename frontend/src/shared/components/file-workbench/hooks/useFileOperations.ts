import { useCallback, useMemo, useRef, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useFileOperations');
import type {
  FileTreeDataAdapter,
  FileOperationRequest,
  FileOperationResponse,
  FileContentPayload,
  FileContentResult,
  FileUpdateOptions,
  BatchDeleteRequest,
  BatchDeleteResponse,
  FileUploadOptions,
  FileDownloadOptions,
} from '../types';
import type { FileConflictBatchResult } from '../conflicts/types';
import { SUCCESS_MESSAGES } from '../constants';

const normalizeFileContent = (payload: FileContentPayload): FileContentResult => (
  typeof payload === 'string' ? { content: payload } : payload
);

export interface UseFileOperationsOptions {
  adapter: FileTreeDataAdapter;
  resourceGeneration: number;
  onSuccess?: (message: string) => void;
  onError?: (error: Error) => void;
  onComplete?: (settlement: FileOperationSettlement) => void;
}

export interface FileOperationSettlement {
  error: Error | null;
}

type FileOperationActivity =
  | 'create'
  | 'update'
  | 'delete'
  | 'upload'
  | 'download';

type FileOperationActivityCounts = Record<FileOperationActivity, number>;

interface FileOperationActivityState {
  resourceGeneration: number;
  counts: FileOperationActivityCounts;
}

const createEmptyActivityCounts = (): FileOperationActivityCounts => ({
  create: 0,
  update: 0,
  delete: 0,
  upload: 0,
  download: 0,
});

export interface UseFileOperationsReturn {

  isCreating: boolean;
  isUpdating: boolean;
  isDeleting: boolean;
  isUploading: boolean;
  isDownloading: boolean;
  isOperating: boolean;


  createFile: (path: string, content?: string) => Promise<FileOperationResponse>;
  createDirectory: (path: string) => Promise<FileOperationResponse>;
  readFile: (path: string) => Promise<FileContentResult>;
  updateFile: (path: string, content: string, options?: FileUpdateOptions) => Promise<FileOperationResponse>;
  deleteFile: (path: string, recursive?: boolean) => Promise<FileOperationResponse>;


  batchDelete: (paths: string[], recursive?: boolean) => Promise<BatchDeleteResponse>;


  renameFile: (oldPath: string, newPath: string) => Promise<FileOperationResponse>;
  moveFile: (sourcePath: string, targetPath: string) => Promise<FileOperationResponse>;


  uploadFiles: (options: FileUploadOptions) => Promise<FileConflictBatchResult>;
  downloadFile: (options: FileDownloadOptions) => Promise<void>;


  executeOperation: (request: FileOperationRequest) => Promise<FileOperationResponse>;
}

export function useFileOperations(
  options: UseFileOperationsOptions
): UseFileOperationsReturn {
  const {
    adapter,
    resourceGeneration,
    onSuccess,
    onError,
    onComplete,
  } = options;
  const stableAdapter = useMemo(() => adapter, [adapter]);
  const currentResourceGenerationRef = useRef(resourceGeneration);
  currentResourceGenerationRef.current = resourceGeneration;
  const [activityState, setActivityState] = useState<FileOperationActivityState>({
    resourceGeneration,
    counts: createEmptyActivityCounts(),
  });
  const adjustActivity = useCallback((
    activity: FileOperationActivity,
    delta: 1 | -1,
    requestGeneration: number,
  ) => {
    if (currentResourceGenerationRef.current !== requestGeneration) return;
    setActivityState(current => {
      const counts = current.resourceGeneration === requestGeneration
        ? current.counts
        : createEmptyActivityCounts();
      return {
        resourceGeneration: requestGeneration,
        counts: {
          ...counts,
          [activity]: Math.max(0, counts[activity] + delta),
        },
      };
    });
  }, []);
  const currentCounts = activityState.resourceGeneration === resourceGeneration
    ? activityState.counts
    : createEmptyActivityCounts();
  const isCreating = currentCounts.create > 0;
  const isUpdating = currentCounts.update > 0;
  const isDeleting = currentCounts.delete > 0;
  const isUploading = currentCounts.upload > 0;
  const isDownloading = currentCounts.download > 0;
  const isOperating = isCreating || isUpdating || isDeleting || isUploading || isDownloading;


  const withErrorHandling = useCallback(
    async <T,>(
      operation: () => Promise<T>,
      activity: FileOperationActivity,
      successMessage?: string
    ): Promise<T> => {
      logger.debug('withErrorHandling: starting operation');
      const requestGeneration = resourceGeneration;
      adjustActivity(activity, 1, requestGeneration);
      let operationError: Error | undefined;
      try {
        logger.debug('withErrorHandling: executing operation()');
        const result = await operation();
        logger.debug('withErrorHandling: operation succeeded');
        if (successMessage && onSuccess) {
          logger.debug('withErrorHandling: calling onSuccess', { successMessage });
          onSuccess(successMessage);
        }
        return result;
      } catch (error) {
        operationError = error instanceof Error ? error : new Error('Operation failed');
        logger.error('withErrorHandling: operation failed', { error });
        if (onError) {
          logger.debug('withErrorHandling: calling onError');
          onError(operationError);
        }
        throw error;
      } finally {
        logger.debug('withErrorHandling: settling operation activity');
        adjustActivity(activity, -1, requestGeneration);
        if (onComplete) {
          logger.debug('withErrorHandling: calling onComplete');
          onComplete({ error: operationError ?? null });
        }
      }
    },
    [adjustActivity, onSuccess, onError, onComplete, resourceGeneration]
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
        'create',
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
        'create',
        SUCCESS_MESSAGES.FILE_CREATED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const readFile = useCallback(
    async (path: string): Promise<FileContentResult> => {
      const payload = await withErrorHandling(
        () => stableAdapter.getContent(path),
        'update'
      );
      return normalizeFileContent(payload);
    },
    [stableAdapter, withErrorHandling]
  );

  const updateFile = useCallback(
    async (path: string, content: string, updateOptions?: FileUpdateOptions): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.update(path, content, updateOptions),
        'update',
        SUCCESS_MESSAGES.FILE_UPDATED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const deleteFile = useCallback(
    async (path: string, recursive = false): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.delete(path, recursive),
        'delete',
        SUCCESS_MESSAGES.FILE_DELETED
      );
    },
    [stableAdapter, withErrorHandling]
  );


  const batchDelete = useCallback(
    async (paths: string[], recursive = false): Promise<BatchDeleteResponse> => {
      return withErrorHandling(
        () => stableAdapter.batchDelete({ paths, recursive }),
        'delete',
        paths.length > 1 ? SUCCESS_MESSAGES.BATCH_DELETE_SUCCESS : SUCCESS_MESSAGES.FILE_DELETED
      );
    },
    [stableAdapter, withErrorHandling]
  );


  const renameFile = useCallback(
    async (oldPath: string, newPath: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.move(oldPath, newPath),
        'update',
        SUCCESS_MESSAGES.FILE_RENAMED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const moveFile = useCallback(
    async (sourcePath: string, targetPath: string): Promise<FileOperationResponse> => {
      return withErrorHandling(
        () => stableAdapter.move(sourcePath, targetPath),
        'update',
        SUCCESS_MESSAGES.FILE_MOVED
      );
    },
    [stableAdapter, withErrorHandling]
  );


  const uploadFiles = useCallback(
    async (uploadOptions: FileUploadOptions): Promise<FileConflictBatchResult> => {
      logger.debug('uploadFiles: starting upload', {
        targetPath: uploadOptions.targetPath,
        filesCount: uploadOptions.files.length,
      });
      return withErrorHandling(
        () => {
          logger.debug('uploadFiles: calling adapter.upload()');
          return stableAdapter.upload(uploadOptions);
        },
        'upload',
        SUCCESS_MESSAGES.FILE_UPLOADED
      );
    },
    [stableAdapter, withErrorHandling]
  );

  const downloadFile = useCallback(
    async (downloadOptions: FileDownloadOptions): Promise<void> => {
      return withErrorHandling(
        () => stableAdapter.download(downloadOptions),
        'download'
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
          return { success: true, data: content };
        case 'update':
          return updateFile(request.path, request.content || '', {
            revision: request.revision,
          });
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
    [createFile, createDirectory, readFile, updateFile, deleteFile, moveFile]
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
