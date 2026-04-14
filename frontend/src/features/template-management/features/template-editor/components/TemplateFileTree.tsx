import React, { useMemo, useState, useRef, useCallback } from 'react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Folder, File, Plus, Trash2, Upload, Edit, Copy, FolderPlus, FilePlus, RefreshCw, Search, ClipboardPaste, Eye } from 'lucide-react';
import type { FileNode } from '../hooks/useTemplateFileManagement';
import { TreeView, TreeNodeRow } from '@/shared/components/tree';
import { FileTreeToolbar, FileTreeSearchBar, FileTreeContextMenuItems, type FileTreeContextMenuAction } from '@/shared/components/file-tree';
import { isImageFile } from '@/features/workspace/features/file-management/utils/fileTypeUtils';
import { useFileTreeSelection, getSelectionModifierFromEvent } from '@/shared/hooks/useFileTreeSelection';
import { useI18n } from '@/shared/hooks/useI18n';

interface TemplateFileTreeProps {
  files: FileNode[];
  loading?: boolean;
  selectedFile: FileNode | null;
  expandedFolders: Set<string>;
  searchTerm: string;
  searchResults: any[];
  searching: boolean;
  isSearchMode: boolean;
  onFileSelect: (file: FileNode) => void;
  onToggleFolder: (folderId: string) => void;
  onSearchChange: (term: string) => void;
  onSearch: () => void;
  onClearSearch: () => void;
  onRefresh: () => void;
  onCreateNew?: () => void;
  onUpload?: () => void;
  onBatchDelete?: () => void;
  onRename?: (file: FileNode) => void;
  onMove?: (file: FileNode) => void;
  onCopy?: (file: FileNode) => void;
  onDelete?: (file: FileNode) => void;
  title?: string;
}

export const TemplateFileTree: React.FC<TemplateFileTreeProps> = ({
  files,
  loading = false,
  selectedFile,
  expandedFolders,
  searchTerm,
  searchResults,
  searching,
  isSearchMode,
  onFileSelect,
  onToggleFolder,
  onSearchChange,
  onSearch,
  onClearSearch,
  onRefresh,
  onCreateNew,
  onUpload,
  onBatchDelete,
  onRename,
  onMove,
  onCopy,
  onDelete,
  title,
}) => {
  const { t } = useI18n();
  const containerRef = useRef<HTMLDivElement>(null);
  const [contextMenuState, setContextMenuState] = useState({
    visible: false,
    x: 0,
    y: 0,
    targetNode: null as FileNode | null,
  });
  const contextMenuRef = useRef<HTMLDivElement>(null);

  // 使用 useFileTreeSelection Hook
  const {
    selectedFiles,
    selectFileWithModifier,
    clearSelection,
  } = useFileTreeSelection({
    nodes: files,
    expandedNodes: expandedFolders,
  });

  const hideContextMenu = useCallback(() => {
    setContextMenuState(prev => ({ ...prev, visible: false, targetNode: null }));
  }, []);

  // 監聽全局點擊，關閉右鍵選單
  React.useEffect(() => {
    if (!contextMenuState.visible) {
      return;
    }

    const handleGlobalClick = (event: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(event.target as Node)) {
        hideContextMenu();
      }
    };

    document.addEventListener('mousedown', handleGlobalClick);
    document.addEventListener('contextmenu', handleGlobalClick);
    return () => {
      document.removeEventListener('mousedown', handleGlobalClick);
      document.removeEventListener('contextmenu', handleGlobalClick);
    };
  }, [contextMenuState.visible, hideContextMenu]);

  const nodePathById = useMemo(() => {
    const map = new Map<string, string>();

    const traverse = (nodes: FileNode[]) => {
      nodes.forEach(node => {
        map.set(node.id, node.path);
        if (node.children) {
          traverse(node.children);
        }
      });
    };

    traverse(files);
    return map;
  }, [files]);

  const expandedFolderIds = useMemo(() => Array.from(expandedFolders), [expandedFolders]);

  const expandedPathSet = useMemo(() => {
    const set = new Set<string>();
    expandedFolderIds.forEach(folderId => {
      const path = nodePathById.get(folderId);
      if (path) {
        set.add(path);
      }
    });
    return set;
  }, [expandedFolderIds, nodePathById]);

  const handleNodeClick = (node: FileNode, event: React.MouseEvent) => {
    const modifier = getSelectionModifierFromEvent(event);

    if (modifier !== 'none') {
      // 有修飾鍵：使用多選邏輯
      selectFileWithModifier(node.path, modifier);
    } else {
      // 無修飾鍵：正常行為
      if (node.type === 'directory') {
        onToggleFolder(node.id);
      } else {
        onFileSelect(node);
      }
    }
  };

  // 空白區域點擊處理
  const handleContainerClick = useCallback((event: React.MouseEvent) => {
    if (event.target === event.currentTarget) {
      clearSelection();
    }
  }, [clearSelection]);

  // 右鍵選單處理
  const handleContextMenu = (node: FileNode, event: React.MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();

    setContextMenuState({
      visible: true,
      x: event.clientX,
      y: event.clientY,
      targetNode: node,
    });
  };

  // 右鍵選單項目
  const contextMenuItems = useMemo<FileTreeContextMenuAction[]>(() => {
    if (!contextMenuState.targetNode) {
      return [];
    }

    const node = contextMenuState.targetNode;
    const items: FileTreeContextMenuAction[] = [];
    const isDirectory = node.type === 'directory';

    // 目錄專屬選單項目
    if (isDirectory) {
      if (onUpload) {
        items.push({
          key: 'upload',
          label: t('template.editor.fileManagement.contextMenu.upload'),
          icon: Upload,
          onSelect: () => {
            hideContextMenu();
            onUpload();
          },
        });
      }

      if (onCreateNew) {
        items.push(
          {
            key: 'create-folder',
            label: t('template.editor.fileManagement.contextMenu.createFolder'),
            icon: FolderPlus,
            onSelect: () => {
              hideContextMenu();
              onCreateNew();
            },
          },
          {
            key: 'create-file',
            label: t('template.editor.fileManagement.contextMenu.createFile'),
            icon: FilePlus,
            onSelect: () => {
              hideContextMenu();
              onCreateNew();
            },
          }
        );
      }
    }

    // 檔案專屬選單項目 - 圖片預覽
    if (!isDirectory && isImageFile(node.path)) {
      items.push({
        key: 'view-image',
        label: t('common.fileTree.context.viewImage'),
        icon: Eye,
        onSelect: () => {
          hideContextMenu();
          onFileSelect(node);
        },
        showDividerBefore: items.length > 0,
      });
    }

    // 共用選單項目 - 複製
    if (onCopy) {
      items.push({
        key: 'copy',
        label: t('template.editor.fileManagement.contextMenu.copy'),
        icon: Copy,
        onSelect: () => {
          hideContextMenu();
          onCopy(node);
        },
        showDividerBefore: items.length > 0 && !isDirectory,
      });
    }

    // 共用選單項目 - 貼上（僅目錄）
    if (isDirectory && onMove) {
      items.push({
        key: 'paste',
        label: t('template.editor.fileManagement.contextMenu.paste'),
        icon: ClipboardPaste,
        onSelect: () => {
          hideContextMenu();
          onMove(node);
        },
      });
    }

    // 共用選單項目 - 重新命名
    if (onRename) {
      items.push({
        key: 'rename',
        label: t('template.editor.fileManagement.contextMenu.rename'),
        icon: Edit,
        onSelect: () => {
          hideContextMenu();
          onRename(node);
        },
        showDividerBefore: true,
      });
    }

    // 共用選單項目 - 刪除
    if (onDelete) {
      items.push({
        key: 'delete',
        label: t('template.editor.fileManagement.contextMenu.delete'),
        icon: Trash2,
        onSelect: () => {
          hideContextMenu();
          onDelete(node);
        },
        variant: 'destructive',
      });
    }

    return items;
  }, [contextMenuState.targetNode, onUpload, onCreateNew, onCopy, onMove, onRename, onDelete, onFileSelect, hideContextMenu, t]);

  const titleExtras = (
    <>
      <Badge variant="secondary" className="text-xs px-1.5 py-0.5">
        {t('template.editor.fileManagement.tree.itemCount', { count: files.length })}
      </Badge>
      {selectedFiles.size > 0 && (
        <Badge variant="default" className="text-xs px-1.5 py-0.5">
          {t('template.editor.fileManagement.tree.selectedCount', { count: selectedFiles.size })}
        </Badge>
      )}
    </>
  );

  const headerActions = (
    <>
      {onUpload && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onUpload}
          className="h-7 px-2 text-xs gap-1"
          title={t('template.editor.fileManagement.actions.create.upload')}
        >
          <Upload className="h-3 w-3" />
          {t('template.editor.fileManagement.actions.create.upload')}
        </Button>
      )}
      {onCreateNew && (
        <Button
          variant="ghost"
          size="sm"
          onClick={onCreateNew}
          className="h-7 px-2 text-xs gap-1"
          title={t('template.editor.fileManagement.actions.create.trigger')}
        >
          <Plus className="h-3 w-3" />
          {t('template.editor.fileManagement.actions.create.trigger')}
        </Button>
      )}
      <Button
        size="sm"
        variant="ghost"
        className="h-7 px-2 text-xs gap-1"
        onClick={onRefresh}
        disabled={loading}
        title={t('template.editor.fileManagement.actions.refresh')}
      >
        <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
        {t('template.editor.fileManagement.actions.refresh')}
      </Button>
    </>
  );

  const searchSummary =
    isSearchMode ? (
      <div>
        {t('template.editor.fileManagement.search.results', { count: searchResults.length })}
        {searchResults.length > 0 && (
          <Button
            variant="link"
            size="sm"
            onClick={onClearSearch}
            className="h-auto p-0 ml-2 text-xs"
          >
            {t('template.editor.fileManagement.search.clear')}
          </Button>
        )}
      </div>
    ) : null;

  return (
    <div className="h-full flex flex-col">
      <FileTreeToolbar
        title={title}
        titleExtras={titleExtras}
        actions={headerActions}
        variant="muted"
        actionsClassName="gap-2"
      />

      <FileTreeSearchBar
        value={searchTerm}
        placeholder={t('template.editor.fileManagement.search.contentPlaceholder')}
        onChange={onSearchChange}
        onSubmit={onSearch}
        onClear={onClearSearch}
        showSearchButton
        searchButtonContent={
          <span className="flex items-center gap-1">
            <Search className="h-3 w-3" />
            {t('template.editor.fileManagement.search.button')}
          </span>
        }
        searchButtonDisabled={!searchTerm.trim() || searching}
        showClearButton={isSearchMode}
        containerClassName="flex-shrink-0"
        inputClassName="h-7 text-xs pr-16"
        searchButtonClassName="h-7 px-2 text-xs"
        clearButtonClassName="absolute right-8 top-1/2 -translate-y-1/2 h-6 w-6 p-0"
        summary={searchSummary}
        summaryClassName="mt-2 text-xs text-muted-foreground"
      />

      {/* 批次操作工具列 */}
      {selectedFiles.size > 0 && (
        <div className="flex items-center justify-between px-3 py-2 bg-muted/50 border-b border-border text-xs">
          <span className="text-muted-foreground">
            {t('template.editor.fileManagement.multiSelect.summary', { count: selectedFiles.size })}
          </span>
          <div className="flex items-center gap-2">
            {onBatchDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onBatchDelete}
                className="h-6 px-2 hover:bg-red-100 text-red-600"
              >
                <Trash2 className="h-3 w-3 mr-1" />
                {t('template.editor.fileManagement.actions.delete')}
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={clearSelection}
              className="h-6 px-2"
            >
              {t('template.editor.fileManagement.multiSelect.unselectAll')}
            </Button>
          </div>
        </div>
      )}

      {/* File Tree */}
      <div ref={containerRef} className="flex-1 overflow-y-auto space-y-1 min-h-0" onClick={handleContainerClick}>
        {loading || searching ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          </div>
        ) : isSearchMode ? (
          searchResults.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-sm text-muted-foreground text-center">
                {t('template.editor.fileManagement.tree.filteredEmpty')}
              </p>
            </div>
          ) : (
            <div className="p-2">
              {searchResults.map((result: any) => (
                <div
                  key={result.path}
                  className="flex flex-col gap-1 px-3 py-2 hover:bg-accent cursor-pointer rounded"
                  onClick={() => {
                    // 這裡需要從 result 構建 FileNode
                    const fileNode: FileNode = {
                      id: `file-${result.path}`,
                      name: result.name,
                      path: result.path,
                      type: result.type as 'file' | 'directory',
                      size: result.size,
                    };
                    onFileSelect(fileNode);
                  }}
                >
                  <div className="flex items-center gap-2">
                    <File className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium text-sm">{result.name}</span>
                  </div>
                  <div className="text-xs text-muted-foreground">{result.path}</div>
                  {result.matches && result.matches.length > 0 && (
                    <div className="mt-1 space-y-1">
                      {result.matches.map((match: string, idx: number) => (
                        <div key={idx} className="text-xs text-muted-foreground bg-muted/50 px-2 py-1 rounded font-mono">
                          {match}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )
        ) : files.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-muted-foreground text-center">
              {t('template.editor.fileManagement.tree.empty')}
            </p>
          </div>
        ) : (
          <div className="p-2">
            <TreeView<FileNode>
              nodes={files}
              getNodeId={node => node.path}
              getNodeChildren={node => node.children ?? []}
              expandedIds={expandedPathSet}
              selectedId={selectedFile?.path ?? null}
              multiSelectedIds={selectedFiles}
              renderNode={({ node, depth, state: nodeState }) => {
                const isDirectory = node.type === 'directory';

                return (
                  <TreeNodeRow
                    depth={depth}
                    isSelected={nodeState.isSelected}
                    isMultiSelected={nodeState.isMultiSelected}
                    isExpanded={nodeState.isExpanded}
                    showExpandIcon={isDirectory}
                    icon={
                      isDirectory ? (
                        <Folder className="h-4 w-4 text-primary" />
                      ) : (
                        <File className="h-4 w-4 text-muted-foreground" />
                      )
                    }
                    label={<span className="truncate font-medium">{node.name}</span>}
                    className="text-sm text-sidebar-foreground hover:bg-sidebar-accent"
                    onClick={(e) => handleNodeClick(node, e)}
                    onDoubleClick={() => onFileSelect(node)}
                    onExpandToggle={() => onToggleFolder(node.id)}
                    onContextMenu={(event) => handleContextMenu(node, event)}
                  />
                );
              }}
            />
          </div>
        )}
      </div>

      {/* 右鍵選單 */}
      {contextMenuState.visible && contextMenuState.targetNode && (
        <div
          ref={contextMenuRef}
          className="fixed bg-background border border-border rounded-md shadow-lg py-1 z-50 min-w-40"
          style={{ left: contextMenuState.x, top: contextMenuState.y }}
        >
          <FileTreeContextMenuItems items={contextMenuItems} />
        </div>
      )}
    </div>
  );
};

export default TemplateFileTree;
