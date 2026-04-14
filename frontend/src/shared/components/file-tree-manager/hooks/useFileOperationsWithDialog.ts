/**
 * 統一的檔案操作 Hook（帶 Dialog）
 *
 * 整合檔案操作邏輯、Dialog 狀態管理、Toast 通知、Loading 狀態
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

  // 關閉 Dialog
  const closeDialog = useCallback(() => {
    setDialogState({ type: null });
  }, []);

  // 開啟新增檔案 Dialog
  const openCreateFileDialog = useCallback((node?: FileTreeNode) => {
    setDialogState({
      type: 'create-file',
      data: { node }
    });
  }, []);

  // 開啟新增資料夾 Dialog
  const openCreateFolderDialog = useCallback((node?: FileTreeNode) => {
    setDialogState({
      type: 'create-folder',
      data: { node }
    });
  }, []);

  // 開啟重新命名 Dialog
  const openRenameDialog = useCallback((node: FileTreeNode) => {
    setDialogState({
      type: 'rename',
      data: { node, currentName: node.name },
    });
  }, []);

  // 開啟刪除 Dialog
  const openDeleteDialog = useCallback((node: FileTreeNode) => {
    setDialogState({
      type: 'delete',
      data: { node },
    });
  }, []);

  // 開啟批次刪除 Dialog
  const openBatchDeleteDialog = useCallback((nodes: FileTreeNode[]) => {
    setDialogState({
      type: 'batch-delete',
      data: { nodes },
    });
  }, []);

  // 處理新增檔案
  const handleCreateFile = useCallback(async (name: string) => {
    if (!options.onCreateFile) return;

    setIsLoading(true);
    try {
      // 獲取父路徑：如果選中的是資料夾，使用其路徑；否則使用根路徑
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
      logger.error('建立檔案失敗', { error });
      toast({
        title: t('common.fileTree.operations.createFile.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [options, toast, t, dialogState]);

  // 處理新增資料夾
  const handleCreateFolder = useCallback(async (name: string) => {
    if (!options.onCreateFolder) return;

    setIsLoading(true);
    try {
      // 獲取父路徑：如果選中的是資料夾，使用其路徑；否則使用根路徑
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
      logger.error('建立資料夾失敗', { error });
      toast({
        title: t('common.fileTree.operations.createFolder.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [options, toast, t, dialogState]);

  // 處理重新命名
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
      logger.error('重新命名失敗', { error });
      toast({
        title: t('common.fileTree.operations.rename.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [options, dialogState, toast, t]);

  // 處理刪除
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
      logger.error('刪除失敗', { error });
      toast({
        title: t('common.fileTree.operations.delete.error'),
        description: error instanceof Error ? error.message : t('common.fileEditor.unknownError'),
        variant: 'destructive',
      });
    } finally {
      setIsLoading(false);
    }
  }, [options, dialogState, toast, t]);

  // 處理批次刪除
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
      logger.error('批次刪除失敗', { error });
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
    // Dialog 狀態
    dialogState,
    isLoading,
    
    // Dialog 控制
    closeDialog,
    openCreateFileDialog,
    openCreateFolderDialog,
    openRenameDialog,
    openDeleteDialog,
    openBatchDeleteDialog,
    
    // 操作處理
    handleCreateFile,
    handleCreateFolder,
    handleRename,
    handleDelete,
    handleBatchDelete,
  };
}
