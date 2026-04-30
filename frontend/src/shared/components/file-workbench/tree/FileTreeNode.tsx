/**
 * 
 */

import React from 'react';
import { ChevronRight, ChevronDown } from 'lucide-react';
import { TreeNodeRow } from '@/shared/components/file-workbench/primitives';
import type { FileTreeNode as FileTreeNodeType, SelectionModifier } from '../types';
import { getFileExtension } from '../utils/fileTreeUtils';


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
 */
function getFileIcon(name: string, isDirectory: boolean, isExpanded: boolean): React.ReactNode {
  if (isDirectory) {

    if (name === '.git') return <FolderGit className="h-4 w-4 text-orange-500" />;
    if (name === 'src' || name === 'lib') return <FolderCode className="h-4 w-4 text-blue-500" />;
    

    return isExpanded 
      ? <FolderOpen className="h-4 w-4 text-yellow-500" />
      : <Folder className="h-4 w-4 text-yellow-500" />;
  }


  const extension = getFileExtension(name);
  

  if (['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'c', 'cpp', 'go', 'rs', 'rb', 'php'].includes(extension)) {
    return <FileCode className="h-4 w-4 text-blue-400" />;
  }
  

  if (['json', 'yaml', 'yml', 'toml', 'xml'].includes(extension)) {
    return <FileJson className="h-4 w-4 text-yellow-400" />;
  }
  

  if (['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico'].includes(extension)) {
    return <FileImage className="h-4 w-4 text-green-400" />;
  }
  

  if (['md', 'markdown'].includes(extension)) {
    return <FileText className="h-4 w-4 text-purple-400" />;
  }
  

  return <File className="h-4 w-4 text-muted-foreground" />;
}

/**
 */
function getSelectionModifierFromEvent(event: React.MouseEvent): SelectionModifier {
  const isMac = navigator.userAgent.toUpperCase().indexOf('MAC') >= 0;
  const isCtrlOrCmd = isMac ? event.metaKey : event.ctrlKey;

  if (event.shiftKey) return 'shift';
  if (isCtrlOrCmd) return 'ctrl';
  return 'none';
}

export interface FileTreeNodeProps {
  node: FileTreeNodeType;
  
  depth?: number;
  
  isSelected?: boolean;
  
  isMultiSelected?: boolean;
  
  isExpanded?: boolean;
  
  isDragging?: boolean;
  
  isDropTarget?: boolean;
  
  isLoading?: boolean;
  
  onClick?: (node: FileTreeNodeType, modifier: SelectionModifier) => void;
  
  onDoubleClick?: (node: FileTreeNodeType) => void;
  
  onExpandToggle?: (node: FileTreeNodeType) => void;
  
  onContextMenu?: (node: FileTreeNodeType, event: React.MouseEvent) => void;
  
  onDragStart?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  onDragEnd?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  onDragOver?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  onDragLeave?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  onDrop?: (node: FileTreeNodeType, event: React.DragEvent) => void;
  
  enableDragDrop?: boolean;
  
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

  const handleClick = (event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();

    const modifier = getSelectionModifierFromEvent(event);
    
    if (onClick) {
      onClick(node, modifier);
    }


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

