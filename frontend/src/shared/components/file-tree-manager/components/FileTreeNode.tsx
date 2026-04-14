/**
 * FileTreeNode 組件
 * 
 * 統一的檔案樹節點組件，支援：
 * - 檔案/資料夾顯示
 * - 選擇狀態（單選、多選）
 * - 展開/收合
 * - 拖放操作
 * - 右鍵選單
 */

import React from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { TreeNodeRow } from '@/shared/components/tree';
import type { FileTreeNode as FileTreeNodeType, SelectionModifier } from '../types';
import { getFileExtension } from '../utils/fileTreeUtils';

// 檔案圖示映射（使用 lucide-react 圖示）
import {
  File,
  FileText,
  FileCode,
  FileJson,
  FileImage,
  Folder,
  FolderOpen,
  FolderCode,
  FolderGit,
} from 'lucide-react';

/**
 * 根據檔案名稱和類型取得圖示
 */
function getFileIcon(name: string, isDirectory: boolean, isExpanded: boolean): React.ReactNode {
  if (isDirectory) {
    // 特殊資料夾
    if (name === '.git') return <FolderGit className="h-4 w-4 text-orange-500" />;
    if (name === 'src' || name === 'lib') return <FolderCode className="h-4 w-4 text-blue-500" />;
    
    // 一般資料夾
    return isExpanded 
      ? <FolderOpen className="h-4 w-4 text-yellow-500" />
      : <Folder className="h-4 w-4 text-yellow-500" />;
  }

  // 檔案圖示
  const extension = getFileExtension(name);
  
  // 程式碼檔案
  if (['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'go', 'rs', 'rb', 'php'].includes(extension)) {
    return <FileCode className="h-4 w-4 text-blue-400" />;
  }
  
  // JSON/YAML 配置檔
  if (['json', 'yaml', 'yml', 'toml', 'xml'].includes(extension)) {
    return <FileJson className="h-4 w-4 text-yellow-400" />;
  }
  
  // 圖片檔案
  if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico'].includes(extension)) {
    return <FileImage className="h-4 w-4 text-green-400" />;
  }
  
  // Markdown 檔案
  if (['md', 'markdown'].includes(extension)) {
    return <FileText className="h-4 w-4 text-purple-400" />;
  }
  
  // 預設檔案圖示
  return <File className="h-4 w-4 text-muted-foreground" />;
}

/**
 * 取得選擇修飾鍵
 */
function getSelectionModifierFromEvent(event: React.MouseEvent): SelectionModifier {
  const isMac = navigator.userAgent.toUpperCase().indexOf('MAC') >= 0;
  const isCtrlOrCmd = isMac ? event.metaKey : event.ctrlKey;

  if (event.shiftKey) return 'shift';
  if (isCtrlOrCmd) return 'ctrl';
  return 'none';
}

export interface FileTreeNodeProps {
  /** 節點資料 */
  node: FileTreeNodeType;
  
  /** 節點深度 */
  depth?: number;
  
  /** 是否選中（單選） */
  isSelected?: boolean;
  
  /** 是否多選中 */
  isMultiSelected?: boolean;
  
  /** 是否展開 */
  isExpanded?: boolean;
  
  /** 是否正在拖曳 */
  isDragging?: boolean;
  
  /** 是否為拖放目標 */
  isDropTarget?: boolean;
  
  /** 是否載入中 */
  isLoading?: boolean;
  
  /** 點擊回調 */
  onClick?: (node: FileTreeNodeType, modifier: SelectionModifier) => void;
  
  /** 雙擊回調 */
  onDoubleClick?: (node: FileTreeNodeType) => void;
  
  /** 展開切換回調 */
  onExpandToggle?: (node: FileTreeNodeType) => void;
  
  /** 右鍵選單回調 */
  onContextMenu?: (node: FileTreeNodeType, event: React.MouseEvent) => void;
  
  /** 拖曳開始回調 */
  onDragStart?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  /** 拖曳結束回調 */
  onDragEnd?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  /** 拖曳經過回調 */
  onDragOver?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  /** 拖曳離開回調 */
  onDragLeave?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  /** 放置回調 */
  onDrop?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  /** 是否啟用拖放 */
  enableDragDrop?: boolean;
  
  /** 自訂 className */
  className?: string;
}

export const FileTreeNode: React.FC<FileTreeNodeProps> = ({
  node,
  depth = 0,
  isSelected = false,
  isMultiSelected = false,
  isExpanded = false,
  isDragging = false,
  isDropTarget = false,
  isLoading = false,
  onClick,
  onDoubleClick,
  onExpandToggle,
  onContextMenu,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDragLeave,
  onDrop,
  enableDragDrop = true,
  className,
}) => {
  // 事件處理
  const handleClick = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();

    const modifier = getSelectionModifierFromEvent(event);
    
    if (onClick) {
      onClick(node, modifier);
    }

    // 如果是資料夾且無修飾鍵，切換展開狀態
    if (node.type === 'directory' && modifier === 'none' && onExpandToggle) {
      onExpandToggle(node);
    }
  };

  const handleDoubleClick = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    
    if (onDoubleClick) {
      onDoubleClick(node);
    }
  };

  const handleContextMenu = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
    
    if (onContextMenu) {
      onContextMenu(node, event);
    }
  };

  const handleDragStart = (event: React.DragEvent) => {
    if (!enableDragDrop) return;
    
    event.stopPropagation();
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', node.path);
    
    if (onDragStart) {
      onDragStart(node, event);
    }
  };

  const handleDragEnd = (event: React.DragEvent) => {
    if (!enableDragDrop) return;
    
    event.stopPropagation();
    
    if (onDragEnd) {
      onDragEnd(node, event);
    }
  };

  const handleDragOver = (event: React.DragEvent) => {
    if (!enableDragDrop) return;
    
    // 只有資料夾可以作為放置目標
    if (node.type === 'directory') {
      event.preventDefault();
      event.stopPropagation();
      event.dataTransfer.dropEffect = 'move';
      
      if (onDragOver) {
        onDragOver(node, event);
      }
    }
  };

  const handleDragLeave = (event: React.DragEvent) => {
    if (!enableDragDrop) return;
    
    event.stopPropagation();
    
    if (onDragLeave) {
      onDragLeave(node, event);
    }
  };

  const handleDrop = (event: React.DragEvent) => {
    if (!enableDragDrop) return;
    
    if (node.type === 'directory') {
      event.preventDefault();
      event.stopPropagation();
      
      if (onDrop) {
        onDrop(node, event);
      }
    }
  };

  const handleExpandToggle = (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    
    if (onExpandToggle) {
      onExpandToggle(node);
    }
  };

  return (
    <TreeNodeRow
      depth={depth}
      label={<span className="truncate">{node.name}</span>}
      icon={getFileIcon(node.name, node.type === 'directory', isExpanded)}
      isSelected={isSelected}
      isMultiSelected={isMultiSelected}
      isExpanded={isExpanded}
      isDragging={isDragging}
      isDropTarget={isDropTarget}
      showExpandIcon={node.type === 'directory'}
      expandIcon={<ChevronRight className="h-4 w-4 text-muted-foreground" />}
      collapseIcon={<ChevronDown className="h-4 w-4 text-muted-foreground" />}
      trailingContent={
        isLoading ? (
          <div className="w-4 h-4 ml-2">
            <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-primary" />
          </div>
        ) : null
      }
      className={className}
      draggable={enableDragDrop}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleContextMenu}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onExpandToggle={handleExpandToggle}
      title={node.path}
    />
  );
};

