/**
 * useFileTreeContextMenu Hook
 * 
 * 統一的檔案樹右鍵選單項目生成邏輯
 * 提供標準化的選單結構和行為
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
import type { FileTreeContextMenuAction } from '@/shared/components/file-tree/FileTreeContextMenuItems';
import type { FileTreeNode } from '../types';

export interface FileTreeContextMenuConfig {
  /** 目標節點 */
  node: FileTreeNode | null;
  
  /** 是否為唯讀模式 */
  readOnly?: boolean;
  
  /** 是否支援多選 */
  enableMultiSelect?: boolean;
  
  /** 已選擇的節點數量 */
  selectedCount?: number;

  /** 已選擇的節點路徑 */
  selectedIds?: Set<string>;
  
  /** 剪貼簿是否有內容 */
  hasClipboard?: boolean;
  
  /** 是否為圖片檔案 */
  isImageFile?: boolean;
  
  /** 功能開關 */
  features?: {
    /** 開啟檔案 */
    open?: boolean;
    /** 查看（唯讀模式） */
    view?: boolean;
    /** 上傳檔案 */
    upload?: boolean;
    /** 新增檔案 */
    createFile?: boolean;
    /** 新增資料夾 */
    createFolder?: boolean;
    /** 複製 */
    copy?: boolean;
    /** 複製路徑 */
    copyPath?: boolean;
    /** 貼上 */
    paste?: boolean;
    /** 重新命名 */
    rename?: boolean;
    /** 刪除 */
    delete?: boolean;
    /** 重新整理 */
    refresh?: boolean;
    /** 查看圖片 */
    viewImage?: boolean;
    /** 解壓 ZIP */
    extractArchive?: boolean;
  };
  
  /** 回調函數 */
  callbacks: {
    /** 開啟檔案 */
    onOpen?: (node: FileTreeNode) => void;
    /** 查看（唯讀模式） */
    onView?: (node: FileTreeNode) => void;
    /** 上傳檔案 */
    onUpload?: () => void;
    /** 新增檔案 */
    onCreateFile?: () => void;
    /** 新增資料夾 */
    onCreateFolder?: () => void;
    /** 複製 */
    onCopy?: (node: FileTreeNode) => void;
    /** 複製路徑 */
    onCopyPath?: (path: string) => void;
    /** 貼上 */
    onPaste?: () => void;
    /** 重新命名 */
    onRename?: (node: FileTreeNode) => void;
    /** 刪除 */
    onDelete?: (node: FileTreeNode) => void;
    /** 批次刪除 */
    onBatchDelete?: (paths: string[]) => void;
    /** 重新整理 */
    onRefresh?: () => void;
    /** 查看圖片 */
    onViewImage?: (node: FileTreeNode) => void;
    /** 解壓 ZIP */
    onExtractArchive?: (node: FileTreeNode) => void;
    /** 關閉選單 */
    onClose: () => void;
  };
  
  /** 翻譯函數 */
  t: (key: string, options?: Record<string, any>) => string;
}

/**
 * 生成標準化的右鍵選單項目
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

    // 預設功能開關
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

    // 唯讀模式：只顯示查看
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
      return items;
    }

    // === 資料夾專屬選項 ===
    if (isDirectory) {
      // 上傳檔案
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

      // 新增資料夾
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

      // 新增檔案
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

    // === 通用操作 ===
    const shouldAddDividerBeforeCommon = items.length > 0;

    // 開啟檔案（僅檔案）
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

    // 查看圖片（僅圖片檔案）
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

    // 複製
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

    // 複製路徑
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

    // 貼上
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

    // === 檔案操作 ===
    // 重新命名
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

    // 刪除
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

    // === 其他操作 ===
    // 重新整理
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
