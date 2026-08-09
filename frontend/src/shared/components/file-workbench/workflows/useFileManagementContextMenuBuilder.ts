import { useFileTreeContextMenu, type FileTreeContextMenuConfig } from '../hooks/useFileTreeContextMenu';
import type { FileTreeNode } from '../types';

export interface UseFileManagementContextMenuBuilderOptions {
  node: FileTreeNode | null;
  selectedIds?: Set<string>;
  clipboardItem?: unknown;
  readOnly?: boolean;
  isImageFile?: boolean;
  isPathWritable?: FileTreeContextMenuConfig['isPathWritable'];
  features?: FileTreeContextMenuConfig['features'];
  callbacks: FileTreeContextMenuConfig['callbacks'];
  t: FileTreeContextMenuConfig['t'];
}

export const useFileManagementContextMenuBuilder = ({
  node,
  selectedIds,
  clipboardItem,
  readOnly,
  isImageFile,
  isPathWritable,
  features,
  callbacks,
  t,
}: UseFileManagementContextMenuBuilderOptions) => useFileTreeContextMenu({
  node,
  readOnly,
  enableMultiSelect: true,
  selectedCount: selectedIds?.size ?? 0,
  selectedIds,
  hasClipboard: Boolean(clipboardItem),
  isImageFile,
  isPathWritable,
  features,
  callbacks,
  t,
});
