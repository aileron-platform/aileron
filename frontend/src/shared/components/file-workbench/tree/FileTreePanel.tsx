/**
 *
 */

import React, { useRef, useCallback } from 'react';
import { TreeView } from '@/shared/components/file-workbench/primitives';
import { FileTreeSearchBar } from '@/shared/components/file-workbench/primitives/FileTreeSearchBar';
import { FileTreeNode } from './FileTreeNode';
import { FileTreeEmpty } from './FileTreeEmpty';
import { Plus, FolderPlus, Upload, RefreshCw, Trash2, X } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/shared/components/ui/popover';
import type { FileTreeNode as FileTreeNodeType, SelectionModifier } from '../types';
import type { UseFileTreeStateReturn } from '../hooks/useFileTreeState';
import { cn } from '@/shared/utils/cn';
import { createLogger } from '@/shared/services/logger';
import { useI18n } from '@/shared/hooks/useI18n';

const logger = createLogger('FileTreePanel');

export interface FileTreePanelProps {
  state: UseFileTreeStateReturn;

  onNodeClick?: (node: FileTreeNodeType, modifier: SelectionModifier) => void;

  onNodeDoubleClick?: (node: FileTreeNodeType) => void;

  onContextMenu?: (node: FileTreeNodeType, event: React.MouseEvent) => void;

  onDragStart?: (node: FileTreeNodeType, event: React.DragEvent) => void;

  onDragEnd?: (node: FileTreeNodeType, event: React.DragEvent) => void;

  onDragOver?: (node: FileTreeNodeType, event: React.DragEvent) => void;

  onDragLeave?: (node: FileTreeNodeType, event: React.DragEvent) => void;

  onDrop?: (node: FileTreeNodeType, event: React.DragEvent) => void;

  onCreateFile?: () => void;

  onCreateFolder?: () => void;

  onUpload?: () => void;

  onPaste?: (files: File[]) => void;

  onRefresh?: () => void;

  onBatchDelete?: (paths: string[]) => void;

  enableSearch?: boolean;

  enableToolbar?: boolean;

  enableMultiSelectBar?: boolean;

  enableBottomStatusBar?: boolean;

  bottomStatusText?: string;

  bottomStatusClearText?: string;

  enableDragDrop?: boolean;

  draggingPath?: string | null;

  dragOverPath?: string | null;

  className?: string;

  renderToolbar?: () => React.ReactNode;

  /**
   */
  onExpandDirectory?: (node: FileTreeNodeType) => void;

  loadingChildrenPaths?: Set<string>;
}

export const FileTreePanel: React.FC<FileTreePanelProps> = ({
  state,
  onNodeClick,
  onNodeDoubleClick,
  onContextMenu,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDragLeave,
  onDrop,
  onCreateFile,
  onCreateFolder,
  onUpload,
  onPaste,
  onRefresh,
  onBatchDelete,
  enableSearch = true,
  enableToolbar = true,
  enableMultiSelectBar = true,
  enableBottomStatusBar = false,
  bottomStatusText,
  bottomStatusClearText,
  enableDragDrop = true,
  draggingPath,
  dragOverPath,
  className,
  renderToolbar,
  onExpandDirectory,
  loadingChildrenPaths,
}) => {
  const { t } = useI18n();
  const { toggleNode } = state;
  const containerRef = useRef<HTMLDivElement>(null);
  const [isBottomStatusOpen, setIsBottomStatusOpen] = React.useState(false);

  React.useEffect(() => {
    logger.debug('state.nodes updated', { nodeCount: state.nodes.length });
  }, [state.nodes]);

  const handleContainerClick = useCallback((event: React.MouseEvent) => {
    if (event.target === event.currentTarget) {
      state.clearSelection();
    }
  }, [state]);

  const handlePaste = useCallback((event: ClipboardEvent) => {
    const files = event.clipboardData?.files;
    if (!files || files.length === 0) return;

    event.preventDefault();
    event.stopPropagation();

    if (onPaste) {
      onPaste(Array.from(files));
    }
  }, [onPaste]);

  React.useEffect(() => {
    const container = containerRef.current;
    if (!container || !onPaste) return;

    container.addEventListener('paste', handlePaste as EventListener);

    return () => {
      container.removeEventListener('paste', handlePaste as EventListener);
    };
  }, [handlePaste, onPaste]);

  const renderNode = useCallback(({ node, depth, state: nodeState }: {
    node: FileTreeNodeType;
    depth: number;
    state: { isSelected: boolean; isMultiSelected: boolean; isExpanded: boolean };
  }) => {
    const isDragging = draggingPath === node.path;
    const isDropTarget = dragOverPath === node.path;

    const isChildrenLoading = loadingChildrenPaths?.has(node.path) ?? false;

    return (
      <FileTreeNode
        key={node.path}
        node={node}
        depth={depth}
        isSelected={nodeState.isSelected}
        isMultiSelected={nodeState.isMultiSelected}
        isExpanded={nodeState.isExpanded}
        isDragging={isDragging}
        isDropTarget={isDropTarget}
        isLoading={isChildrenLoading}
        onClick={onNodeClick}
        onDoubleClick={onNodeDoubleClick}
        onExpandToggle={(n) => {
          if (onExpandDirectory) {
            onExpandDirectory(n);
          } else {
            toggleNode(n.path);
          }
        }}
        onContextMenu={onContextMenu}
        onDragStart={onDragStart}
        onDragEnd={onDragEnd}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        enableDragDrop={enableDragDrop}
        className="text-foreground hover:bg-muted/40"
      />
    );
  }, [onNodeClick, onNodeDoubleClick, onContextMenu, onDragStart, onDragEnd, onDragOver, onDragLeave, onDrop, toggleNode, onExpandDirectory, loadingChildrenPaths, enableDragDrop, draggingPath, dragOverPath]);

  const nodesToRender = React.useMemo(() => {
    const nodes = state.isSearching ? state.filteredNodes : state.nodes;
    logger.debug('nodesToRender recalculated', { nodeCount: nodes.length });
    return nodes;
  }, [state.isSearching, state.filteredNodes, state.nodes]);

  const isEmpty = nodesToRender.length === 0;
  const bottomStatusLabel = bottomStatusText || t('common.fileTree.multiSelect.selectedCount', { count: state.selectedIds.size });
  const resolvedBottomStatusClearText = bottomStatusClearText || t('common.fileTree.multiSelect.clearSelection');

  React.useEffect(() => {
    setIsBottomStatusOpen(false);
  }, [bottomStatusText]);

  return (
    <div className={cn('flex h-full min-h-0 flex-col', className)}>
      {enableSearch && (
        <div className="h-10 border-b">
          <FileTreeSearchBar
            value={state.searchQuery}
            onChange={state.setSearchQuery}
            onClear={state.clearSearch}
            placeholder={t('common.fileTree.search.placeholder')}
            containerClassName="border-none"
          />
        </div>
      )}

      {enableToolbar && (
        <div className="h-10 px-3 border-b bg-card flex items-center">
          {renderToolbar ? (
            renderToolbar()
          ) : (
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={onCreateFile}
                disabled={state.isLoading}
                title={t('common.fileTree.contextMenu.createFile')}
                aria-label={t('common.fileTree.contextMenu.createFile')}
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={onCreateFolder}
                disabled={state.isLoading}
                title={t('common.fileTree.contextMenu.createFolder')}
                aria-label={t('common.fileTree.contextMenu.createFolder')}
              >
                <FolderPlus className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={onUpload}
                disabled={state.isLoading}
                title={t('common.fileTree.contextMenu.upload')}
                aria-label={t('common.fileTree.contextMenu.upload')}
              >
                <Upload className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={onRefresh}
                disabled={state.isLoading}
                title={t('common.fileTree.contextMenu.refresh')}
                aria-label={t('common.fileTree.contextMenu.refresh')}
              >
                <RefreshCw className={cn('h-3.5 w-3.5', state.isLoading && 'animate-spin')} />
              </Button>
            </div>
          )}
        </div>
      )}

      {enableMultiSelectBar && state.selectedIds.size > 1 && (
        <div className="h-9 px-3 border-b bg-muted/50 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {t('common.fileTree.multiSelect.selectedCount', { count: state.selectedIds.size })}
          </span>
          <div className="flex items-center gap-1">
            <Button
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0"
              onClick={() => {
                if (onBatchDelete) {
                  onBatchDelete(Array.from(state.selectedIds));
                }
              }}
              title={t('common.fileTree.contextMenu.deleteSelected', { count: state.selectedIds.size })}
              aria-label={t('common.fileTree.contextMenu.deleteSelected', { count: state.selectedIds.size })}
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0"
              onClick={state.clearSelection}
              title={t('common.fileTree.multiSelect.clearSelection')}
              aria-label={t('common.fileTree.multiSelect.clearSelection')}
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}

      <div
        ref={containerRef}
        className="min-h-0 flex-1 overflow-y-auto p-2"
        onClick={handleContainerClick}
        tabIndex={0}
      >
        {state.isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        ) : state.error ? (
          <FileTreeEmpty
            type="error"
            title={t('common.fileTree.error.title')}
            description={state.error}
          />
        ) : isEmpty ? (
          <FileTreeEmpty
            type={state.isSearching ? 'search' : 'empty'}
          />
        ) : (
          <TreeView<FileTreeNodeType>
            nodes={nodesToRender}
            getNodeId={(node) => node.path}
            getNodeChildren={(node) => node.children ?? []}
            expandedIds={state.expandedIds}
            selectedId={state.selectedId}
            multiSelectedIds={state.selectedIds}
            expandAll={state.isSearching}
            renderNode={renderNode}
          />
        )}
      </div>

      {enableBottomStatusBar && (Boolean(bottomStatusText) || state.selectedIds.size > 0) && (
        <div className="h-8 px-3 border-t border-border bg-muted/30 flex items-center justify-between gap-2 text-xs text-muted-foreground">
          <Popover open={isBottomStatusOpen} onOpenChange={setIsBottomStatusOpen}>
            <PopoverTrigger asChild>
              <button
                type="button"
                className="min-w-0 flex-1 truncate text-left hover:text-foreground"
                title={bottomStatusLabel}
              >
                {bottomStatusLabel}
              </button>
            </PopoverTrigger>
            <PopoverContent
              align="start"
              side="top"
              className="max-w-[min(32rem,calc(100vw-4rem))] break-all p-3 font-mono text-xs"
            >
              {bottomStatusLabel}
            </PopoverContent>
          </Popover>
          {state.selectedIds.size > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={state.clearSelection}
            >
                {resolvedBottomStatusClearText}
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
