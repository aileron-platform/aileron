import React from 'react';
import {
  BatchDeleteDialog,
  FileCreateDialog,
  FileDeleteDialog,
  FileRenameDialog,
} from '../tree/FileOperationDialogs';
import type {
  DialogState,
  FileOperationDialogResult,
} from '../hooks/useFileOperationsWithDialog';
import type { FileTreeNode } from '../types';

export type FileManagementDialogState =
  | { type: 'create-file'; parentPath: string }
  | { type: 'create-folder'; parentPath: string }
  | { type: 'rename'; node: FileTreeNode }
  | { type: 'delete'; node: FileTreeNode }
  | { type: 'batch-delete'; nodes: FileTreeNode[] }
  | null;

export interface FileManagementDialogsProps {
  dialogState: FileManagementDialogState;
  onClose: () => void;
  onCreateFile: (name: string) => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
  onCreateFolder: (name: string) => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
  onRename: (name: string) => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
  onDelete: () => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
  onBatchDelete?: () => void | FileOperationDialogResult | Promise<void | FileOperationDialogResult>;
  getAffectedUnsavedTabsCount?: (paths: string[]) => number;
}

export const toFileManagementDialogState = (
  dialogState: DialogState,
): FileManagementDialogState => {
  if (dialogState.type === 'create-file') {
    return {
      type: 'create-file',
      parentPath: dialogState.data?.parentPath ?? '/',
    };
  }

  if (dialogState.type === 'create-folder') {
    return {
      type: 'create-folder',
      parentPath: dialogState.data?.parentPath ?? '/',
    };
  }

  if (dialogState.type === 'rename' && dialogState.data?.node) {
    return {
      type: 'rename',
      node: dialogState.data.node,
    };
  }

  if (dialogState.type === 'delete' && dialogState.data?.node) {
    return {
      type: 'delete',
      node: dialogState.data.node,
    };
  }

  if (dialogState.type === 'batch-delete' && dialogState.data?.nodes) {
    return {
      type: 'batch-delete',
      nodes: dialogState.data.nodes,
    };
  }

  return null;
};

export const FileManagementDialogs = ({
  dialogState,
  onClose,
  onCreateFile,
  onCreateFolder,
  onRename,
  onDelete,
  onBatchDelete,
  getAffectedUnsavedTabsCount,
}: FileManagementDialogsProps) => (
  <>
    <FileCreateDialog
      open={dialogState?.type === 'create-file'}
      type="file"
      onClose={onClose}
      onConfirm={onCreateFile}
    />
    <FileCreateDialog
      open={dialogState?.type === 'create-folder'}
      type="folder"
      onClose={onClose}
      onConfirm={onCreateFolder}
    />
    <FileRenameDialog
      open={dialogState?.type === 'rename'}
      onClose={onClose}
      onConfirm={onRename}
      currentName={dialogState?.type === 'rename' ? dialogState.node.name : ''}
    />
    <FileDeleteDialog
      open={dialogState?.type === 'delete'}
      onClose={onClose}
      onConfirm={onDelete}
      fileName={dialogState?.type === 'delete' ? dialogState.node.name : ''}
      filePath={dialogState?.type === 'delete' ? dialogState.node.path : undefined}
      fileType={dialogState?.type === 'delete' ? dialogState.node.type : 'file'}
      affectedUnsavedTabsCount={dialogState?.type === 'delete'
        ? getAffectedUnsavedTabsCount?.([dialogState.node.path]) ?? 0
        : 0}
    />
    <BatchDeleteDialog
      open={dialogState?.type === 'batch-delete'}
      onClose={onClose}
      onConfirm={onBatchDelete ?? (() => undefined)}
      files={(dialogState?.type === 'batch-delete' ? dialogState.nodes : []).map((node) => ({
        name: node.name,
        path: node.path,
        type: node.type,
      }))}
      affectedUnsavedTabsCount={dialogState?.type === 'batch-delete'
        ? getAffectedUnsavedTabsCount?.(dialogState.nodes.map((node) => node.path)) ?? 0
        : 0}
    />
  </>
);
