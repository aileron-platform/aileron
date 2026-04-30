/**
 * useFileTreeContextMenu Hook
 * 
 */

import { useMemo } from 'react';
import {
  Archive,
  Eye,
  FilePlus,
  FolderPlus,
  Edit,
  Copy,
  ClipboardPaste,
  Trash2,
  RefreshCw,
  Upload,
  FileEdit,
} from 'lucide-react';
import type { FileTreeContextMenuAction } from '@/shared/components/file-workbench/primitives/FileTreeContextMenuItems';
import type { FileTreeNode } from '../types';

export interface FileTreeContextMenuConfig {
  node: FileTreeNode | null;
  
  readOnly?: boolean;
  
  enableMultiSelect?: boolean;
  
  selectedCount?: number;

  selectedIds?: Set<string>;
  
  hasClipboard?: boolean;
  
  isImageFile?: boolean;
  
  features?: {
    open?: boolean;
    view?: boolean;
    upload?: boolean;
    createFile?: boolean;
    createFolder?: boolean;
    copy?: boolean;
    copyPath?: boolean;
    paste?: boolean;
    rename?: boolean;
    delete?: boolean;
    refresh?: boolean;
    viewImage?: boolean;
    extractArchive?: boolean;
  };
  
  callbacks: {
    onOpen?: (node: FileTreeNode) => void;
    onView?: (node: FileTreeNode) => void;
    onUpload?: () => void;
    onCreateFile?: () => void;
    onCreateFolder?: () => void;
    onCopy?: (node: FileTreeNode) => void;
    onCopyPath?: (path: string) => void;
    onPaste?: () => void;
    onRename?: (node: FileTreeNode) => void;
    onDelete?: (node: FileTreeNode) => void;
    onBatchDelete?: (paths: string[]) => void;
    onRefresh?: () => void;
    onViewImage?: (node: FileTreeNode) => void;
    onExtractArchive?: (node: FileTreeNode) => void;
    onClose: () => void;
  };
  
  t: (key: string, options?: Record<string, any>) => string;
}

/**
 */
export function useFileTreeContextMenu(config: FileTreeContextMenuConfig): FileTreeContextMenuAction[] {
  const {
    node,
    readOnly = false,
    enableMultiSelect = false,
    selectedCount = 0,
    selectedIds,
    hasClipboard = false,
    isImageFile = false,
    features = {},
    callbacks,
    t,
  } = config;

  return useMemo<FileTreeContextMenuAction[]>(() => {
    if (!node) {
      return [];
    }

    const items: FileTreeContextMenuAction[] = [];
    const isDirectory = node.type === 'directory';
    const multipleSelected = enableMultiSelect && selectedCount > 1;
    const isZipFile = !isDirectory && node.name.toLowerCase().endsWith('.zip');


    const defaultFeatures = {
      open: true,
      view: false,
      upload: true,
      createFile: true,
      createFolder: true,
      copy: true,
      copyPath: false,
      paste: true,
      rename: true,
      delete: true,
      refresh: false,
      viewImage: false,
      extractArchive: false,
      ...features,
    };


    if (readOnly) {
      if (defaultFeatures.view && callbacks.onView) {
        items.push({
          key: 'view',
          label: t('common.fileTree.contextMenu.view'),
          icon: Edit,
          onSelect: () => {
            callbacks.onClose();
            callbacks.onView(node);
          },
        });
      }

      if (defaultFeatures.copyPath && callbacks.onCopyPath) {
        items.push({
          key: 'copy-path',
          label: t('common.fileTree.contextMenu.copyPath'),
          icon: Copy,
          onSelect: () => {
            callbacks.onClose();
            callbacks.onCopyPath(node.path);
          },
        });
      }

      if (defaultFeatures.refresh && callbacks.onRefresh) {
        items.push({
          key: 'refresh',
          label: t('common.fileTree.contextMenu.refresh'),
          icon: RefreshCw,
          onSelect: () => {
            callbacks.onClose();
            callbacks.onRefresh();
          },
          showDividerBefore: items.length > 0,
        });
      }

      return items;
    }


    if (isDirectory) {

      if (defaultFeatures.upload && callbacks.onUpload) {
        items.push({
          key: 'upload',
          label: t('common.fileTree.contextMenu.upload'),
          icon: Upload,
          onSelect: () => {
            callbacks.onClose();
            callbacks.onUpload();
          },
        });
      }


      if (defaultFeatures.createFolder && callbacks.onCreateFolder) {
        items.push({
          key: 'create-folder',
          label: t('common.fileTree.contextMenu.createFolder'),
          icon: FolderPlus,
          onSelect: () => {
            callbacks.onClose();
            callbacks.onCreateFolder();
          },
        });
      }


      if (defaultFeatures.createFile && callbacks.onCreateFile) {
        items.push({
          key: 'create-file',
          label: t('common.fileTree.contextMenu.createFile'),
          icon: FilePlus,
          onSelect: () => {
            callbacks.onClose();
            callbacks.onCreateFile();
          },
        });
      }
    }


    const shouldAddDividerBeforeCommon = items.length > 0;


    if (!isDirectory && defaultFeatures.open && callbacks.onOpen) {
      items.push({
        key: 'open',
        label: t('common.fileTree.contextMenu.open'),
        icon: Eye,
        onSelect: () => {
          callbacks.onClose();
          callbacks.onOpen(node);
        },
        showDividerBefore: shouldAddDividerBeforeCommon,
      });
    }


    if (!isDirectory && isImageFile && defaultFeatures.viewImage && callbacks.onViewImage) {
      items.push({
        key: 'view-image',
        label: t('common.fileTree.contextMenu.viewImage'),
        icon: Eye,
        onSelect: () => {
          callbacks.onClose();
          callbacks.onViewImage(node);
        },
      });
    }

    if (isZipFile && defaultFeatures.extractArchive && callbacks.onExtractArchive) {
      items.push({
        key: 'extract-archive',
        label: t('common.fileTree.contextMenu.extractArchive'),
        icon: Archive,
        onSelect: () => {
          callbacks.onClose();
          callbacks.onExtractArchive(node);
        },
      });
    }


    if (defaultFeatures.copy && callbacks.onCopy) {
      items.push({
        key: 'copy',
        label: t('common.fileTree.contextMenu.copy'),
        icon: Copy,
        onSelect: () => {
          callbacks.onClose();
          callbacks.onCopy(node);
        },
        showDividerBefore: !shouldAddDividerBeforeCommon && items.length > 0,
      });
    }


    if (defaultFeatures.copyPath && callbacks.onCopyPath) {
      items.push({
        key: 'copy-path',
        label: t('common.fileTree.contextMenu.copyPath'),
        icon: Copy,
        onSelect: () => {
          callbacks.onClose();
          callbacks.onCopyPath(node.path);
        },
      });
    }


    if (defaultFeatures.paste && callbacks.onPaste) {
      items.push({
        key: 'paste',
        label: t('common.fileTree.contextMenu.paste'),
        icon: ClipboardPaste,
        disabled: !hasClipboard,
        onSelect: () => {
          callbacks.onClose();
          callbacks.onPaste();
        },
      });
    }



    if (defaultFeatures.rename && callbacks.onRename) {
      items.push({
        key: 'rename',
        label: t('common.fileTree.contextMenu.rename'),
        icon: FileEdit,
        onSelect: () => {
          callbacks.onClose();
          callbacks.onRename(node);
        },
        showDividerBefore: true,
      });
    }


    if (defaultFeatures.delete && (callbacks.onDelete || callbacks.onBatchDelete)) {
      items.push({
        key: 'delete',
        label: multipleSelected
          ? t('common.fileTree.contextMenu.deleteSelected', { count: selectedCount })
          : t('common.fileTree.contextMenu.delete'),
        icon: Trash2,
        variant: 'destructive' as const,
        onSelect: () => {
          callbacks.onClose();
          if (multipleSelected && callbacks.onBatchDelete && selectedIds) {
            callbacks.onBatchDelete(Array.from(selectedIds));
          } else if (callbacks.onDelete) {
            callbacks.onDelete(node);
          }
        },
      });
    }



    if (defaultFeatures.refresh && callbacks.onRefresh) {
      items.push({
        key: 'refresh',
        label: t('common.fileTree.contextMenu.refresh'),
        icon: RefreshCw,
        onSelect: () => {
          callbacks.onClose();
          callbacks.onRefresh();
        },
        showDividerBefore: true,
      });
    }

    return items;
  }, [node, readOnly, enableMultiSelect, selectedCount, hasClipboard, isImageFile, features, callbacks, t]);
}
