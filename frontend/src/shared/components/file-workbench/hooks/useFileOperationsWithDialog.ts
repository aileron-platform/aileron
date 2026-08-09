/**
 *
 */

import { useState, useCallback } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useFileOperationsWithDialog');
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import type { FileTreeNode } from '../types';

export interface DialogState {
  type: 'create-file' | 'create-folder' | 'rename' | 'delete' | 'batch-delete' | null;
  data?: {
    node?: FileTreeNode;
    nodes?: FileTreeNode[];
    currentName?: string;
    parentPath?: string;
    parentPathWasOverridden?: boolean;
  };
}

export interface FileOperationDialogResult {
  suppressSuccessToast?: boolean;
}

type FileOperationDialogHandler<TArgs extends unknown[]> = (
  ...args: TArgs
) => Promise<void | FileOperationDialogResult>;

export interface UseFileOperationsWithDialogOptions {
  onCreateFile?: FileOperationDialogHandler<[string, (string | undefined)?]>;
  onCreateFolder?: FileOperationDialogHandler<[string, (string | undefined)?]>;
  onRename?: FileOperationDialogHandler<[string, string]>;
  onDelete?: FileOperationDialogHandler<[string, FileTreeNode?]>;
  onBatchDelete?: FileOperationDialogHandler<[string[]]>;
  isPathWritable?: (path: string) => boolean;
  defaultWritableParent?: string;
  onUnwriteableContextHint?: () => void;
}

export function useFileOperationsWithDialog(options: UseFileOperationsWithDialogOptions) {
  const { toast } = useToast();
  const { t } = useI18n();
  const [dialogState, setDialogState] = useState<DialogState>({ type: null });
  const [isLoading, setIsLoading] = useState(false);

  const getNodeParentPath = useCallback((node?: FileTreeNode) => {
    if (!node) return '/';
    if (node.type === 'directory') return node.path;
    const lastSlashIndex = node.path.lastIndexOf('/');
    return lastSlashIndex > 0 ? node.path.substring(0, lastSlashIndex) : '/';
  }, []);

  const resolveCreateParentPath = useCallback((node?: FileTreeNode) => {
    const parentPath = getNodeParentPath(node);
    const nodeWritable = node?.writable ?? options.isPathWritable?.(parentPath) ?? true;
    if (!nodeWritable && options.defaultWritableParent) {
      options.onUnwriteableContextHint?.();
      return { parentPath: options.defaultWritableParent, parentPathWasOverridden: true };
    }
    return { parentPath, parentPathWasOverridden: false };
  }, [getNodeParentPath, options]);

  const closeDialog = useCallback(() => {
    setDialogState({ type: null });
  }, []);


  const openCreateFileDialog = useCallback((node?: FileTreeNode) => {
    const { parentPath, parentPathWasOverridden } = resolveCreateParentPath(node);
    setDialogState({
      type: 'create-file',
      data: { node, parentPath, parentPathWasOverridden }
    });
  }, [resolveCreateParentPath]);


  const openCreateFolderDialog = useCallback((node?: FileTreeNode) => {
    const { parentPath, parentPathWasOverridden } = resolveCreateParentPath(node);
    setDialogState({
      type: 'create-folder',
      data: { node, parentPath, parentPathWasOverridden }
    });
  }, [resolveCreateParentPath]);


  const openRenameDialog = useCallback((node: FileTreeNode) => {
    setDialogState({
      type: 'rename',
      data: { node, currentName: node.name },
    });
  }, []);


  const openDeleteDialog = useCallback((node: FileTreeNode) => {
    setDialogState({
      type: 'delete',
      data: { node },
    });
  }, []);


  const openBatchDeleteDialog = useCallback((nodes: FileTreeNode[]) => {
    setDialogState({
      type: 'batch-delete',
      data: { nodes },
    });
  }, []);


  const handleCreateFile = useCallback(async (name: string) => {
    if (!options.onCreateFile) return;

    setIsLoading(true);
    try {

      const parentPath = dialogState.data?.parentPath ?? getNodeParentPath(dialogState.data?.node);

      const result = await options.onCreateFile(name, parentPath);
      if (!result?.suppressSuccessToast) {
        toast({
          title: t('common.fileTree.operations.createFile.success'),
          description: t('common.fileTree.operations.createFile.successDesc', {
            name
          }),
        });
      }
      return result;
    } catch (error) {
      logger.error('failed to create file', { error });
      toast({
        title: t('common.fileTree.operations.createFile.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [options, toast, t, dialogState, getNodeParentPath]);


  const handleCreateFolder = useCallback(async (name: string) => {
    if (!options.onCreateFolder) return;

    setIsLoading(true);
    try {

      const parentPath = dialogState.data?.parentPath ?? getNodeParentPath(dialogState.data?.node);

      const result = await options.onCreateFolder(name, parentPath);
      if (!result?.suppressSuccessToast) {
        toast({
          title: t('common.fileTree.operations.createFolder.success'),
          description: t('common.fileTree.operations.createFolder.successDesc', {
            name
          }),
        });
      }
      return result;
    } catch (error) {
      logger.error('failed to create folder', { error });
      toast({
        title: t('common.fileTree.operations.createFolder.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [options, toast, t, dialogState, getNodeParentPath]);


  const handleRename = useCallback(async (newName: string) => {
    if (!options.onRename || !dialogState.data?.node) return;

    const node = dialogState.data.node;
    setIsLoading(true);
    try {
      const result = await options.onRename(node.path, newName);
      if (!result?.suppressSuccessToast) {
        toast({
          title: t('common.fileTree.operations.rename.success'),
          description: t('common.fileTree.operations.rename.successDesc', {
            name: newName
          }),
        });
      }
      return result;
    } catch (error) {
      logger.error('failed to rename item', { error });
      toast({
        title: t('common.fileTree.operations.rename.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [options, dialogState, toast, t]);


  const handleDelete = useCallback(async () => {
    if (!options.onDelete || !dialogState.data?.node) return;

      const node = dialogState.data.node;
      setIsLoading(true);
      try {
        const result = await options.onDelete(node.path, node);
      if (!result?.suppressSuccessToast) {
        toast({
          title: t('common.fileTree.operations.delete.success'),
          description: t('common.fileTree.operations.delete.successDesc', {
            name: node.name
          }),
        });
      }
      return result;
    } catch (error) {
      logger.error('failed to delete item', { error });
      toast({
        title: t('common.fileTree.operations.delete.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [options, dialogState, toast, t]);


  const handleBatchDelete = useCallback(async () => {
    if (!options.onBatchDelete || !dialogState.data?.nodes) return;

    const nodes = dialogState.data.nodes;
    const paths = nodes.map(n => n.path);

    setIsLoading(true);
    try {
      const result = await options.onBatchDelete(paths);
      if (!result?.suppressSuccessToast) {
        toast({
          title: t('common.fileTree.operations.batchDelete.success'),
          description: t('common.fileTree.operations.batchDelete.successDesc', {
            count: nodes.length
          }),
        });
      }
      return result;
    } catch (error) {
      logger.error('failed to delete items', { error });
      toast({
        title: t('common.fileTree.operations.batchDelete.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [options, dialogState, toast, t]);

  return {

    dialogState,
    isLoading,
    

    closeDialog,
    openCreateFileDialog,
    openCreateFolderDialog,
    openRenameDialog,
    openDeleteDialog,
    openBatchDeleteDialog,
    

    handleCreateFile,
    handleCreateFolder,
    handleRename,
    handleDelete,
    handleBatchDelete,
  };
}
