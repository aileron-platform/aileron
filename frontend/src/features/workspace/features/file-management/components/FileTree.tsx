/**
 * 檔案樹主組件
 * 基於原始設計重構，保持完全相同的 UI 設計
 */

import React, { useEffect, useRef, useMemo } from 'react';
import { FilePlus, FolderPlus, Loader2, Plus, Upload, RefreshCw } from 'lucide-react';
import { Button } from '../../../../../shared/components/ui/button';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { FileTreeNode } from './FileTreeNode';
import { getAllFileNodes } from '../utils/fileOperationUtils';
import { isMacOS } from '../utils/selectionUtils';
import type { FileTreeProps, FileNode } from '../types';
import { useI18n } from '@/shared/hooks/useI18n';
import { useToast } from '@/shared/components/ui/use-toast';
import { TreeView } from '@/shared/components/tree';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('FileTree');
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { FileTreeToolbar, FileTreeMultiSelectBar } from '@/shared/components/file-tree';

export const FileTree: React.FC<FileTreeProps> = ({
  className = '',
  showHeader = true,
  showActions = true,
  onFileSelect,
  onFileDoubleClick,
  onContextMenu,
  searchTerm = '',
  onCreateAction,
}) => {
  const {
    openFileInTab,
    fileTreeState: state,
    fileTreeActions: actions
  } = useWorkspace();
  const { t } = useI18n();
  const { toast } = useToast();
  const containerRef = useRef<HTMLDivElement>(null);

  const normalizedSearchTerm = searchTerm.trim().toLowerCase();
  const isSearching = normalizedSearchTerm.length > 0;
  const pendingAction = state.pendingAction;
  const isActionBlocking =
    pendingAction !== null && (pendingAction.status === 'pending' || pendingAction.status === 'running');

  // 計算選中的檔案數量（只計算檔案，不包含資料夾）
  const selectedFileCount = useMemo(() => {
    if (!state.selectedFiles || state.selectedFiles.size === 0) {
      return 0;
    }

    // 獲取所有檔案節點
    const allFileNodes = getAllFileNodes(state.nodes);

    // 計算有多少選中的路徑是檔案
    let count = 0;
    for (const selectedPath of state.selectedFiles) {
      // 檢查這個路徑是否在檔案節點列表中
      if (allFileNodes.some(node => node.path === selectedPath)) {
        count++;
      }
    }

    return count;
  }, [state.selectedFiles, state.nodes]);
  const pendingActionLabel = React.useMemo(() => {
    if (!pendingAction) {
      return '';
    }

    const fallbackName = t('workspace.fileManagement.tree.pending.itemFallback');
    const sourceName =
      pendingAction.sourcePath && pendingAction.sourcePath !== '/'
        ? pendingAction.sourcePath.split('/').pop() ?? pendingAction.sourcePath
        : fallbackName;

    switch (pendingAction.type) {
      case 'copy':
        return t('workspace.fileManagement.tree.pending.copy', {
          name: sourceName,
        });
      case 'extract':
        return t('workspace.fileManagement.tree.pending.extract', {
          name: sourceName,
        });
      default:
        return t('workspace.fileManagement.tree.pending.generic');
    }
  }, [pendingAction, t]);
  const progressLabel = React.useMemo(() => {
    if (!pendingAction || typeof pendingAction.progress !== 'number') {
      return null;
    }
    const percentage = Math.min(100, Math.max(0, Math.round(pendingAction.progress * 100)));
    return t('workspace.fileManagement.tree.pending.progress', { value: percentage });
  }, [pendingAction, t]);

  const filterNodesBySearchTerm = React.useCallback((nodes: FileNode[]): FileNode[] => {
    if (!isSearching) {
      return nodes;
    }

    const filterRecursive = (nodeList: FileNode[]): FileNode[] => {
      const filtered: FileNode[] = [];

      nodeList.forEach(node => {
        const matches = node.name.toLowerCase().includes(normalizedSearchTerm);
        const filteredChildren = node.children ? filterRecursive(node.children) : undefined;

        if (matches || (filteredChildren && filteredChildren.length > 0)) {
          filtered.push({
            ...node,
            children: filteredChildren,
          });
        }
      });

      return filtered;
    };

    return filterRecursive(nodes);
  }, [isSearching, normalizedSearchTerm]);

  const nodesToRender = React.useMemo(() => filterNodesBySearchTerm(state.nodes), [filterNodesBySearchTerm, state.nodes]);

  // 鍵盤事件處理：Ctrl/Cmd + A 全選，Escape 取消選擇
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isMac = isMacOS();
      const isCtrlOrCmd = isMac ? event.metaKey : event.ctrlKey;

      // Ctrl/Cmd + A: 全選
      if (isCtrlOrCmd && event.key === 'a') {
        event.preventDefault();
        const allFileNodes = getAllFileNodes(state.nodes);
        const allFilePaths = allFileNodes.map(node => node.path);
        actions.selectAllFiles(allFilePaths);
      }

      // Escape: 取消選擇
      if (event.key === 'Escape') {
        event.preventDefault();
        actions.clearSelection();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [state.nodes, actions]);

  // 處理空白區域點擊：清除選擇
  const handleContainerClick = React.useCallback((event: React.MouseEvent) => {
    // 只有點擊容器本身（非子元素）時才清除選擇
    if (event.target === event.currentTarget) {
      actions.clearSelection();
    }
  }, [actions]);

  // 處理拖曳開始
  const handleDragStart = React.useCallback((nodePath: string) => {
    actions.setDraggedNode(nodePath);
  }, [actions]);

  // 處理拖曳結束
  const handleDragEnd = React.useCallback(() => {
    actions.setDraggedNode(null);
    actions.setDropTarget(null);
  }, [actions]);

  // 處理拖曳經過
  const handleDragOver = React.useCallback((nodePath: string) => {
    // 只有當目標改變時才更新
    if (state.dropTarget !== nodePath) {
      actions.setDropTarget(nodePath);
    }
  }, [actions, state.dropTarget]);

  // 處理拖曳離開
  const handleDragLeave = React.useCallback((nodePath: string) => {
    // 只有當離開的是當前的 dropTarget 時才清除
    if (state.dropTarget === nodePath) {
      actions.setDropTarget(null);
    }
  }, [actions, state.dropTarget]);

  // 處理放置
  const handleDrop = React.useCallback(async (targetPath: string, event: React.DragEvent) => {
    event.preventDefault();
    const sourcePath = state.draggedNode;

    if (!sourcePath || sourcePath === targetPath) {
      actions.setDraggedNode(null);
      actions.setDropTarget(null);
      return;
    }

    // 檢查是否試圖將資料夾移動到自己的子資料夾中
    if (targetPath !== '/' && targetPath.startsWith(sourcePath + '/')) {
      actions.setDraggedNode(null);
      actions.setDropTarget(null);
      return;
    }

    // 計算新路徑
    const fileName = sourcePath.split('/').pop() || '';
    const newPath = targetPath === '/' ? `/${fileName}` : `${targetPath}/${fileName}`;

    // 檢查目標位置是否已存在同名檔案
    const findNodeByPath = (nodes: typeof state.nodes, path: string): boolean => {
      for (const node of nodes) {
        if (node.path === path) {
          return true;
        }
        if (node.children) {
          if (findNodeByPath(node.children, path)) {
            return true;
          }
        }
      }
      return false;
    };

    if (findNodeByPath(state.nodes, newPath)) {
      // 顯示錯誤提示
      toast({
        variant: 'destructive',
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: t('workspace.fileManagement.tree.notifications.fileExistsError', { name: fileName }),
      });
      actions.setDraggedNode(null);
      actions.setDropTarget(null);
      return;
    }

    try {
      const result = await actions.moveNode(sourcePath, newPath);
      if (!result.success) {
        // 改善錯誤訊息的友好度
        let errorMessage = result.message;
        if (errorMessage === 'FILE_ALREADY_EXISTS' || errorMessage.includes('FILE_ALREADY_EXISTS')) {
          errorMessage = t('workspace.fileManagement.tree.notifications.fileExistsError', { name: fileName });
        }

        toast({
          variant: 'destructive',
          title: t('workspace.fileManagement.tree.notifications.moveFailed'),
          description: errorMessage,
        });
      }
    } catch (error) {
      logger.error('移動檔案失敗', { error });
      let message = error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.moveFailed');

      // 改善錯誤訊息的友好度
      if (message === 'FILE_ALREADY_EXISTS' || message.includes('FILE_ALREADY_EXISTS')) {
        message = t('workspace.fileManagement.tree.notifications.fileExistsError', { name: fileName });
      }

      toast({
        variant: 'destructive',
        title: t('workspace.fileManagement.tree.notifications.moveFailed'),
        description: message,
      });
    } finally {
      actions.setDraggedNode(null);
      actions.setDropTarget(null);
    }
  }, [state.draggedNode, state.nodes, actions, toast]);

  // 處理根目錄的拖放事件
  const handleRootDragOver = React.useCallback((event: React.DragEvent) => {
    if (state.draggedNode) {
      event.preventDefault();
      event.stopPropagation();
      event.dataTransfer.dropEffect = 'move';

      // 只有當拖曳的檔案不在根目錄時才設置 dropTarget
      const draggedPath = state.draggedNode;
      const isInRoot = draggedPath.split('/').filter(Boolean).length === 1;

      if (!isInRoot && state.dropTarget !== '/') {
        actions.setDropTarget('/');
      }
    }
  }, [state.draggedNode, state.dropTarget, actions]);

  const handleRootDragLeave = React.useCallback((event: React.DragEvent) => {
    // 檢查是否真的離開了根區域
    const relatedTarget = event.relatedTarget as HTMLElement;
    const currentTarget = event.currentTarget as HTMLElement;

    if (relatedTarget && currentTarget.contains(relatedTarget)) {
      return;
    }

    if (state.dropTarget === '/') {
      actions.setDropTarget(null);
    }
  }, [state.dropTarget, actions]);

  const handleRootDrop = React.useCallback(async (event: React.DragEvent) => {
    await handleDrop('/', event);
  }, [handleDrop]);

  const handleRefresh = () => {
    actions.refreshFileTree();
  };

  return (
    <div className={`h-full flex flex-col ${className}`}>
      {/* Header */}
      {showHeader && (
        <FileTreeToolbar
          title={t('workspace.fileManagement.tree.header.title')}
          variant="sidebar"
          actions={
            showActions ? (
              <>
                {onCreateAction && (
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs gap-1"
                        disabled={isActionBlocking}
                      >
                        <Plus className="h-3 w-3" />
                        {t('workspace.fileManagement.tree.actions.create.trigger')}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuItem
                        onSelect={event => {
                          event.preventDefault();
                          if (!isActionBlocking) {
                            onCreateAction('upload');
                          }
                        }}
                        className="gap-2 text-xs"
                        disabled={isActionBlocking}
                      >
                        <Upload className="h-4 w-4" />
                        {t('workspace.fileManagement.tree.actions.create.upload')}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={event => {
                          event.preventDefault();
                          if (!isActionBlocking) {
                            onCreateAction('folder');
                          }
                        }}
                        className="gap-2 text-xs"
                        disabled={isActionBlocking}
                      >
                        <FolderPlus className="h-4 w-4" />
                        {t('workspace.fileManagement.tree.actions.create.folder')}
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onSelect={event => {
                          event.preventDefault();
                          if (!isActionBlocking) {
                            onCreateAction('file');
                          }
                        }}
                        className="gap-2 text-xs"
                        disabled={isActionBlocking}
                      >
                        <FilePlus className="h-4 w-4" />
                        {t('workspace.fileManagement.tree.actions.create.file')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                )}
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 px-2 text-xs gap-1"
                  onClick={handleRefresh}
                  disabled={state.isLoading}
                  title={t('workspace.fileManagement.tree.actions.refresh.tooltip')}
                >
                  <RefreshCw className={`h-3 w-3 ${state.isLoading ? 'animate-spin' : ''}`} />
                  {t('workspace.fileManagement.tree.actions.refresh.label')}
                </Button>
              </>
            ) : null
          }
          actionsClassName="gap-1"
          multiSelectBar={
            selectedFileCount > 0 ? (
              <FileTreeMultiSelectBar
                selectedCount={selectedFileCount}
                totalCount={(() => {
                  const allFileNodes = getAllFileNodes(state.nodes);
                  return allFileNodes.length;
                })()}
                isAllSelected={(() => {
                  const allFileNodes = getAllFileNodes(state.nodes);
                  return selectedFileCount === allFileNodes.length;
                })()}
                onToggleSelectAll={() => {
                  const allFileNodes = getAllFileNodes(state.nodes);
                  if (selectedFileCount === allFileNodes.length) {
                    actions.clearSelection();
                  } else {
                    const allFilePaths = allFileNodes.map(node => node.path);
                    actions.selectAllFiles(allFilePaths);
                  }
                }}
                primaryAction={{
                  label: t('workspace.fileManagement.tree.multiSelect.download', { count: state.selectedFiles?.size ?? 0 }),
                  onClick: async () => {
                    if ((state.selectedFiles?.size ?? 0) === 0) return;

                    const selectedPaths = Array.from(state.selectedFiles ?? []);
                    try {
                      await actions.downloadFiles(selectedPaths);
                      toast({
                        title: t('workspace.fileManagement.tree.notifications.downloadSuccess'),
                        description: t('workspace.fileManagement.tree.notifications.downloadSuccessDescription', {
                          count: selectedPaths.length,
                        }),
                      });
                    } catch (error) {
                      toast({
                        title: t('workspace.fileManagement.tree.notifications.downloadFailed'),
                        description: error instanceof Error ? error.message : t('workspace.fileManagement.tree.notifications.downloadError'),
                        variant: 'destructive',
                      });
                    }
                  },
                  disabled: (state.selectedFiles?.size ?? 0) === 0,
                }}
                variant="sidebar"
              />
            ) : undefined
          }
          multiSelectBarClassName="h-10"
        />
      )}

      {/* 內容區域 */}
      <div
        ref={containerRef}
        className={`flex-1 overflow-y-auto p-2 relative outline-none ${
          state.dropTarget === '/' ? 'bg-primary/10 ring-2 ring-primary ring-inset' : ''
        }`}
        onClick={handleContainerClick}
        onContextMenu={event => {
          if (isActionBlocking) {
            event.preventDefault();
            return;
          }

          if (onContextMenu) {
            onContextMenu('/', event);
          }
        }}
        onDragOver={handleRootDragOver}
        onDragLeave={handleRootDragLeave}
        onDrop={handleRootDrop}
      >
        {state.error && (
          <div className="p-3 mb-2 text-sm text-destructive bg-destructive/10 rounded border border-destructive/20">
            {state.error}
          </div>
        )}

        {state.isLoading && state.nodes.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm">{t('workspace.fileManagement.tree.loading')}</span>
            </div>
          </div>
        ) : state.nodes.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <div className="text-center text-muted-foreground">
              <div className="text-sm">{t('workspace.fileManagement.tree.empty.title')}</div>
              <div className="text-xs mt-1">{t('workspace.fileManagement.tree.empty.description')}</div>
            </div>
          </div>
        ) : nodesToRender.length === 0 && isSearching ? (
          <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
            {t('workspace.fileManagement.tree.search.noResults')}
          </div>
        ) : (
          <TreeView<FileNode>
            nodes={nodesToRender}
            getNodeId={node => node.path}
            getNodeChildren={node => node.children ?? []}
            expandedIds={state.expandedNodes}
            selectedId={state.selectedFile}
            multiSelectedIds={state.selectedFiles}
            expandAll={isSearching}
            renderNode={({ node, state: nodeState }) => (
              <FileTreeNode
                key={node.id}
                node={node}
                isSelected={nodeState.isSelected}
                isMultiSelected={nodeState.isMultiSelected}
                isExpanded={nodeState.isExpanded}
                isDragging={state.draggedNode === node.path}
                isDropTarget={state.dropTarget === node.path}
                onSelect={() => {
                  actions.selectFile(node.path);

                  if (node.type === 'file') {
                    openFileInTab(node.path);
                  }

                  if (onFileSelect) {
                    onFileSelect(node.path);
                  }
                }}
                onSelectWithModifier={actions.selectFileWithModifier}
                onDoubleClick={(filePath) => {
                  if (onFileDoubleClick) {
                    onFileDoubleClick(filePath);
                  }
                }}
                onToggleExpand={(nodePath) => {
                  if (state.expandedNodes.has(nodePath)) {
                    actions.collapseNode(nodePath);
                  } else {
                    actions.expandNode(nodePath);
                  }
                }}
                onContextMenu={onContextMenu}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
              />
            )}
          />
        )}

        {isActionBlocking && (
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin text-primary" />
            <span>{pendingActionLabel}</span>
            {progressLabel && <span className="text-xs">{progressLabel}</span>}
          </div>
        )}
      </div>

      {/* 底部狀態列 */}
      {selectedFileCount > 0 && (
        <div className="h-8 px-4 border-t border-border bg-muted/30 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {t('workspace.fileManagement.tree.status.selected', { count: selectedFileCount })}
          </span>
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => {
              // 清除選擇
              actions.clearSelection();
            }}
          >
            {t('workspace.fileManagement.tree.status.clearSelection')}
          </Button>
        </div>
      )}
    </div>
  );
};
