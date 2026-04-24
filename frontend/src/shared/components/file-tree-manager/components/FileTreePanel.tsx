/**
 * FileTreePanel 組件
 *
 * 左側檔案樹面板，包含：
 * - 搜尋列
 * - 工具列
 * - 檔案樹
 * - 多選工具列
 */

import React, { useRef, useCallback } from 'react';
import { TreeView } from '@/shared/components/tree';
import { FileTreeSearchBar } from '@/shared/components/file-tree/FileTreeSearchBar';
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
  /** 狀態管理 */
  state: UseFileTreeStateReturn;

  /** 節點點擊回調 */
  onNodeClick?: (node: FileTreeNodeType, modifier: SelectionModifier) => void;

  /** 節點雙擊回調 */
  onNodeDoubleClick?: (node: FileTreeNodeType) => void;

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

  /** 新增檔案回調 */
  onCreateFile?: () => void;

  /** 新增資料夾回調 */
  onCreateFolder?: () => void;

  /** 上傳檔案回調 */
  onUpload?: () => void;

  /** 貼上檔案回調 */
  onPaste?: (files: File[]) => void;

  /** 重新整理回調 */
  onRefresh?: () => void;

  /** 批次刪除回調 */
  onBatchDelete?: (paths: string[]) => void;

  /** 是否啟用搜尋 */
  enableSearch?: boolean;

  /** 是否啟用工具列 */
  enableToolbar?: boolean;

  /** 是否啟用多選工具列（頂部） */
  enableMultiSelectBar?: boolean;

  /** 是否啟用底部狀態列 */
  enableBottomStatusBar?: boolean;

  /** 底部狀態列文字（自訂） */
  bottomStatusText?: string;

  /** 底部狀態列清除按鈕文字 */
  bottomStatusClearText?: string;

  /** 是否啟用拖放 */
  enableDragDrop?: boolean;

  /** 正在拖曳的節點路徑 */
  draggingPath?: string | null;

  /** 拖曳懸停的目標路徑 */
  dragOverPath?: string | null;

  /** 自訂 className */
  className?: string;

  /** 自訂工具列渲染 */
  renderToolbar?: () => React.ReactNode;

  /**
   * 目錄展開/收起回調（支援懶載入）。
   * 提供時取代 state.toggleNode；未提供時回退到 state.toggleNode。
   */
  onExpandDirectory?: (node: FileTreeNodeType) => void;

  /** 正在懶載入子項的目錄路徑集合（用於節點 loading spinner） */
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
  bottomStatusClearText = '清除選擇',
  enableDragDrop = true,
  draggingPath,
  dragOverPath,
  className,
  renderToolbar,
  onExpandDirectory,
  loadingChildrenPaths,
}) => {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement>(null);
  const [isBottomStatusOpen, setIsBottomStatusOpen] = React.useState(false);

  // 調試：監控 state.nodes 變化
  React.useEffect(() => {
    logger.debug('state.nodes 已更新', { nodeCount: state.nodes.length });
  }, [state.nodes]);

  // 空白區域點擊處理（清除選擇）
  const handleContainerClick = useCallback((event: React.MouseEvent) => {
    if (event.target === event.currentTarget) {
      state.clearSelection();
    }
  }, [state]);

  // 處理貼上事件
  const handlePaste = useCallback((event: ClipboardEvent) => {
    // 只處理檔案貼上，不處理文字貼上
    const files = event.clipboardData?.files;
    if (!files || files.length === 0) return;

    // 阻止預設行為
    event.preventDefault();
    event.stopPropagation();

    // 呼叫貼上回調
    if (onPaste) {
      onPaste(Array.from(files));
    }
  }, [onPaste]);

  // 註冊貼上事件監聽器
  React.useEffect(() => {
    const container = containerRef.current;
    if (!container || !onPaste) return;

    container.addEventListener('paste', handlePaste as EventListener);

    return () => {
      container.removeEventListener('paste', handlePaste as EventListener);
    };
  }, [handlePaste, onPaste]);

  // 渲染節點
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
            state.toggleNode(n.path);
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
  }, [onNodeClick, onNodeDoubleClick, onContextMenu, onDragStart, onDragEnd, onDragOver, onDragLeave, onDrop, state.toggleNode, onExpandDirectory, loadingChildrenPaths, enableDragDrop, draggingPath, dragOverPath]);

  // 決定要顯示的節點
  const nodesToRender = React.useMemo(() => {
    const nodes = state.isSearching ? state.filteredNodes : state.nodes;
    logger.debug('nodesToRender 重新計算', { nodeCount: nodes.length });
    return nodes;
  }, [state.isSearching, state.filteredNodes, state.nodes]);

  const isEmpty = nodesToRender.length === 0;
  const bottomStatusLabel = bottomStatusText || `已選擇 ${state.selectedIds.size} 個項目`;

  React.useEffect(() => {
    setIsBottomStatusOpen(false);
  }, [bottomStatusText]);

  return (
    <div className={cn('flex h-full min-h-0 flex-col', className)}>
      {/* 搜尋列 */}
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

      {/* 工具列 */}
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
                title="新增檔案"
              >
                <Plus className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={onCreateFolder}
                disabled={state.isLoading}
                title="新增資料夾"
              >
                <FolderPlus className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={onUpload}
                disabled={state.isLoading}
                title="上傳檔案"
              >
                <Upload className="h-3.5 w-3.5" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0"
                onClick={onRefresh}
                disabled={state.isLoading}
                title="重新整理"
              >
                <RefreshCw className={cn('h-3.5 w-3.5', state.isLoading && 'animate-spin')} />
              </Button>
            </div>
          )}
        </div>
      )}

      {/* 多選工具列 */}
      {enableMultiSelectBar && state.selectedIds.size > 1 && (
        <div className="h-9 px-3 border-b bg-muted/50 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            已選擇 {state.selectedIds.size} 個項目
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
              title="刪除選中項目"
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive" />
            </Button>
            <Button
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0"
              onClick={state.clearSelection}
              title="取消選擇"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* 檔案樹 */}
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
            title="載入失敗"
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

      {/* 底部狀態列 */}
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
              {bottomStatusClearText}
            </Button>
          )}
        </div>
      )}
    </div>
  );
};
