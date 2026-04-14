/**
 * 檔案樹節點組件
 * 完全按照原始設計重構，保持 UI 一致性
 */

import React from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { TreeNodeRow } from '@/shared/components/tree';
import { getFileIcon } from '../utils/fileIconUtils';
import { formatFileSize, formatDateTime } from '../utils/fileTypeUtils';
import { getSelectionModifierFromEvent } from '../utils/selectionUtils';
import type { FileNode, SelectionModifier } from '../types';

interface FileTreeNodeProps {
  node: FileNode;
  isSelected: boolean;
  isMultiSelected: boolean;
  isExpanded: boolean;
  isDragging?: boolean;
  isDropTarget?: boolean;
  onSelect: (filePath: string) => void;
  onSelectWithModifier: (filePath: string, modifier: SelectionModifier) => void;
  onDoubleClick: (filePath: string) => void;
  onToggleExpand: (nodePath: string) => void;
  onContextMenu?: (filePath: string, event: React.MouseEvent) => void;
  onDragStart?: (nodePath: string) => void;
  onDragEnd?: () => void;
  onDragOver?: (nodePath: string, event: React.DragEvent) => void;
  onDragLeave?: (nodePath: string) => void;
  onDrop?: (targetPath: string, event: React.DragEvent) => void;
}

export const FileTreeNode: React.FC<FileTreeNodeProps> = ({
  node,
  isSelected,
  isMultiSelected,
  isExpanded,
  isDragging = false,
  isDropTarget = false,
  onSelect,
  onSelectWithModifier,
  onDoubleClick,
  onToggleExpand,
  onContextMenu,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDragLeave,
  onDrop,
}) => {
  const handleClick = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();

    // 檢測修飾鍵
    const modifier = getSelectionModifierFromEvent(event);

    // 呼叫新的選擇處理函數
    onSelectWithModifier(node.path, modifier);

    // 如果是資料夾且無修飾鍵，切換展開狀態
    if (node.type === 'directory' && modifier === 'none') {
      onToggleExpand(node.path);
    }

    // 如果是檔案且無修飾鍵，開啟檔案
    if (node.type === 'file' && modifier === 'none') {
      onSelect(node.path);
    }
  };

  const handleDoubleClick = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    onDoubleClick(node.path);
  };

  const handleDragStart = (event: React.DragEvent) => {
    event.stopPropagation();
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', node.path);
    if (onDragStart) {
      onDragStart(node.path);
    }
  };

  const handleDragEnd = (event: React.DragEvent) => {
    event.stopPropagation();
    if (onDragEnd) {
      onDragEnd();
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    // 只有資料夾可以作為放置目標
    if (node.type === 'directory') {
      event.preventDefault();
      event.stopPropagation();
      event.dataTransfer.dropEffect = 'move';
      if (onDragOver) {
        onDragOver(node.path, event);
      }
    }
  };

  const handleDragLeave = (event: React.DragEvent) => {
    // 只有當離開當前元素（而非子元素）時才清除高亮
    const target = event.currentTarget as HTMLElement;
    const relatedTarget = event.relatedTarget as HTMLElement;

    // 檢查 relatedTarget 是否是當前元素的子元素
    if (relatedTarget && target.contains(relatedTarget)) {
      return; // 不清除高亮，因為只是移動到子元素
    }

    event.stopPropagation();
    if (onDragLeave) {
      onDragLeave(node.path);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    if (node.type === 'directory') {
      event.preventDefault();
      event.stopPropagation();
      if (onDrop) {
        onDrop(node.path, event);
      }
    }
  };

  const handleContextMenu = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    if (onContextMenu) {
      onContextMenu(node.path, event);
    }
  };

  return (
    <TreeNodeRow
      depth={node.depth ?? 0}
      label={<span className="text-sm">{node.name}</span>}
      icon={
        node.type === 'directory'
          ? getFileIcon(node.name, true, isExpanded)
          : getFileIcon(node.name, false, false)
      }
      isSelected={isSelected}
      isMultiSelected={isMultiSelected}
      isExpanded={isExpanded}
      isDragging={isDragging}
      isDropTarget={isDropTarget}
      showExpandIcon={node.type === 'directory'}
      expandIcon={<ChevronRight className="h-4 w-4 text-muted-foreground" />}
      collapseIcon={<ChevronDown className="h-4 w-4 text-muted-foreground" />}
      trailingContent={
        node.isLoading ? (
          <div className="w-4 h-4 ml-2">
            <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-primary" />
          </div>
        ) : null
      }
      className="text-sidebar-foreground hover:bg-sidebar-accent"
      data-file-tree-node="true"
      data-node-path={node.path}
      data-node-type={node.type}
      draggable={true}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleContextMenu}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      title={`${node.name}${node.size ? ` (${formatFileSize(node.size)})` : ''}${
        node.lastModified ? ` - ${formatDateTime(node.lastModified)}` : ''
      }`}
      onExpandToggle={() => onToggleExpand(node.path)}
    />
  );
};
