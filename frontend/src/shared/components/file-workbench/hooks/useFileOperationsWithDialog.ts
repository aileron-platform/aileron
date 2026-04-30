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
  };
}

export interface UseFileOperationsWithDialogOptions {
  onCreateFile?: (name: string, parentPath?: string) => Promise<void>;
  onCreateFolder?: (name: string, parentPath?: string) => Promise<void>;
  onRename?: (oldPath: string, newName: string) => Promise<void>;
  onDelete?: (path: string, node?: FileTreeNode) => Promise<void>;
  onBatchDelete?: (paths: string[]) => Promise<void>;
}

export function useFileOperationsWithDialog(options: UseFileOperationsWithDialogOptions) {
  const { toast } = useToast();
  const { t } = useI18n();
  const [dialogState, setDialogState] = useState<DialogState>({ type: null });
  const [isLoading, setIsLoading] = useState(false);


  const closeDialog = useCallback(() => {
    setDialogState({ type: null });
  }, []);


  const openCreateFileDialog = useCallback((node?: FileTreeNode) => {
    setDialogState({
      type: 'create-file',
      data: { node }
    });
  }, []);


  const openCreateFolderDialog = useCallback((node?: FileTreeNode) => {
    setDialogState({
      type: 'create-folder',
      data: { node }
    });
  }, []);


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

      const parentPath = dialogState.data?.node
        ? (dialogState.data.node.type === 'directory'
          ? dialogState.data.node.path
          : dialogState.data.node.path.substring(0, dialogState.data.node.path.lastIndexOf('/')))
        : '/';

      await options.onCreateFile(name, parentPath);
      toast({
        title: t('common.fileTree.operations.createFile.success'),
        description: t('common.fileTree.operations.createFile.successDesc', {
          name
        }),
      });
    } catch (error) {
      logger.error('failed to create file', { error });
      toast({
        title: t('common.fileTree.operations.createFile.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [options, toast, t, dialogState]);


  const handleCreateFolder = useCallback(async (name: string) => {
    if (!options.onCreateFolder) return;

    setIsLoading(true);
    try {

      const parentPath = dialogState.data?.node
        ? (dialogState.data.node.type === 'directory'
          ? dialogState.data.node.path
          : dialogState.data.node.path.substring(0, dialogState.data.node.path.lastIndexOf('/')))
        : '/';

      await options.onCreateFolder(name, parentPath);
      toast({
        title: t('common.fileTree.operations.createFolder.success'),
        description: t('common.fileTree.operations.createFolder.successDesc', {
          name
        }),
      });
    } catch (error) {
      logger.error('failed to create folder', { error });
      toast({
        title: t('common.fileTree.operations.createFolder.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [options, toast, t, dialogState]);


  const handleRename = useCallback(async (newName: string) => {
    if (!options.onRename || !dialogState.data?.node) return;

    const node = dialogState.data.node;
    setIsLoading(true);
    try {
      await options.onRename(node.path, newName);
      toast({
        title: t('common.fileTree.operations.rename.success'),
        description: t('common.fileTree.operations.rename.successDesc', {
          name: newName
        }),
      });
    } catch (error) {
      logger.error('failed to rename item', { error });
      toast({
        title: t('common.fileTree.operations.rename.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [options, dialogState, toast, t]);


  const handleDelete = useCallback(async () => {
    if (!options.onDelete || !dialogState.data?.node) return;

    const node = dialogState.data.node;
    setIsLoading(true);
    try {
      await options.onDelete(node.path, node);
      toast({
        title: t('common.fileTree.operations.delete.success'),
        description: t('common.fileTree.operations.delete.successDesc', {
          name: node.name
        }),
      });
    } catch (error) {
      logger.error('failed to delete item', { error });
      toast({
        title: t('common.fileTree.operations.delete.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
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
      await options.onBatchDelete(paths);
      toast({
        title: t('common.fileTree.operations.batchDelete.success'),
        description: t('common.fileTree.operations.batchDelete.successDesc', {
          count: nodes.length
        }),
      });
    } catch (error) {
      logger.error('failed to delete items', { error });
      toast({
        title: t('common.fileTree.operations.batchDelete.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
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
