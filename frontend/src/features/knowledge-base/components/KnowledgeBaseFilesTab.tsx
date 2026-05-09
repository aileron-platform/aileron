import React from 'react';
import { AlertCircle, ChevronLeft, Database, Eye, EyeOff, FilePlus, FolderPlus, RefreshCw, Upload } from 'lucide-react';
import {
  BatchDeleteDialog,
  FileCreateDialog,
  FileDeleteDialog,
  FileRenameDialog,
  FileTreeContextMenu,
  FileTreePanel,
  StandardFileTreeLayout,
  useFileOperationsWithDialog,
  useFileTreeContextMenu,
  useFileTreeManager,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { createKnowledgeBaseFileWorkbenchAdapter } from './file-workbench/knowledgeBaseFileWorkbenchAdapter';
import {
  createKnowledgeBaseFileTreeDataAdapter,
  knowledgeBaseFileEndpoints,
} from './file-workbench/knowledgeBaseFileTreeDataAdapter';
import {
  FileViewerWorkbench,
  toFileWorkbenchTab,
  type FileViewerWorkbenchTab,
} from '@/shared/components/file-workbench/viewer-entry';
import { apiClient } from '@/shared/api/apiClient';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/shared/components/ui/tooltip';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { cn } from '@/shared/utils/cn';
import { isPathWritable } from '../utils/pathWritability';
import {
  KNOWLEDGE_BASE_COLLAPSED_COLUMN_WIDTH,
  KNOWLEDGE_BASE_DEFAULT_COLUMN_WIDTH,
  KNOWLEDGE_BASE_MAX_COLUMN_WIDTH,
  KNOWLEDGE_BASE_MIN_COLUMN_WIDTH,
} from './knowledgeBasePanelLayout';

interface KnowledgeBaseFilesTabProps {
  knowledgeBaseId: string;
  readOnly: boolean;
}

const ROOT_PATH = '/';
const DEFAULT_WRITABLE_PARENT = 'raw/sources';

const joinPath = (parentPath: string, name: string): string => {
  if (!parentPath || parentPath === ROOT_PATH) {
    return `/${name}`;
  }

  return `${parentPath}/${name}`;
};

const getTargetPath = (node?: FileTreeNode): string => {
  if (!node || node.type !== 'directory') {
    return ROOT_PATH;
  }

  return node.path;
};

const getParentPath = (path: string): string => {
  const segments = path.split('/').filter(Boolean);
  segments.pop();
  return segments.length > 0 ? `/${segments.join('/')}` : ROOT_PATH;
};

const getNodeName = (path: string): string => {
  const segments = path.split('/').filter(Boolean);
  return segments[segments.length - 1] ?? '';
};

const getApiErrorCode = (error: unknown): string | undefined => {
  if (
    typeof error === 'object' &&
    error !== null &&
    'errorCode' in error &&
    typeof (error as { errorCode?: unknown }).errorCode === 'string'
  ) {
    return (error as { errorCode: string }).errorCode;
  }

  return undefined;
};

export const KnowledgeBaseFilesTab: React.FC<KnowledgeBaseFilesTabProps> = ({
  knowledgeBaseId,
  readOnly,
}) => {
  const { toast } = useToast();
  const { t } = useI18n();
  const [draggingPath, setDraggingPath] = React.useState<string | null>(null);
  const [dragOverPath, setDragOverPath] = React.useState<string | null>(null);
  const [isExternalDragActive, setIsExternalDragActive] = React.useState(false);
  const [treeWidth, setTreeWidth] = React.useState(KNOWLEDGE_BASE_DEFAULT_COLUMN_WIDTH);
  const [treeCollapsed, setTreeCollapsed] = React.useState(false);
  const [isDragging, setIsDragging] = React.useState(false);
  const [showHiddenEntries, setShowHiddenEntries] = React.useState(false);
  const [isWorkbenchExpanded, setIsWorkbenchExpanded] = React.useState(false);
  const [clipboardItem, setClipboardItem] = React.useState<{ path: string; type: 'file' | 'directory' } | null>(null);
  const [showWritableParentHint, setShowWritableParentHint] = React.useState(false);
  const dragDepthRef = React.useRef(0);
  const dragStateRef = React.useRef<{ startX: number; startWidth: number } | null>(null);

  const fileTreeAdapter = React.useMemo(
    () => createKnowledgeBaseFileTreeDataAdapter({
      knowledgeBaseId,
      includeHidden: showHiddenEntries,
    }),
    [knowledgeBaseId, showHiddenEntries],
  );

  const manager = useFileTreeManager({
    adapter: fileTreeAdapter,
    adapterKey: `knowledge-base:${knowledgeBaseId}:${showHiddenEntries ? 'hidden' : 'visible'}`,
    stateOptions: {
      enableMultiSelect: !readOnly,
    },
    autoLoad: true,
  });

  const showErrorToast = React.useCallback((error: unknown, fallback: string) => {
    const message = error instanceof Error ? error.message : fallback;
    toast({
      title: fallback,
      description: message,
      variant: 'destructive',
    });
  }, [toast]);

  const uploadFilesToPath = React.useCallback(async (files: File[], targetPath: string) => {
    if (readOnly || files.length === 0) {
      return;
    }

    const resolvedTargetPath = isPathWritable(targetPath) ? targetPath : DEFAULT_WRITABLE_PARENT;

    try {
      await manager.operations.uploadFiles({
        targetPath: resolvedTargetPath,
        files,
      });
      await manager.loadTree();
      toast({
        title: t('knowledgeBase.files.uploadSuccessTitle'),
        description: t('knowledgeBase.files.uploadSuccessDescription', { count: files.length }),
      });
    } catch (error) {
      showErrorToast(error, t('knowledgeBase.files.uploadFailed'));
    }
  }, [manager, readOnly, showErrorToast, t, toast]);

  const handleUpload = React.useCallback((targetPath = DEFAULT_WRITABLE_PARENT) => {
    if (readOnly) {
      return;
    }
    const resolvedTargetPath = isPathWritable(targetPath) ? targetPath : DEFAULT_WRITABLE_PARENT;

    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = async (event) => {
      const files = (event.target as HTMLInputElement).files;
      if (!files || files.length === 0) {
        return;
      }

      await uploadFilesToPath(Array.from(files), resolvedTargetPath);
    };
    input.click();
  }, [readOnly, uploadFilesToPath]);

  const handleSave = React.useCallback(async (path: string, content: string) => {
    if (readOnly || !isPathWritable(path)) {
      return;
    }

    try {
      await manager.operations.updateFile(path, content);
      manager.editor.saveTab(path);
      toast({
        title: t('knowledgeBase.files.saveSuccessTitle'),
        description: path,
      });
    } catch (error) {
      showErrorToast(error, t('knowledgeBase.files.saveFailed'));
    }
  }, [manager, readOnly, showErrorToast, t, toast]);

  const fileOps = useFileOperationsWithDialog({
    onCreateFile: async (name, parentPath = ROOT_PATH) => {
      await manager.createFileAndOpen(joinPath(parentPath, name), '');
    },
    onCreateFolder: async (name, parentPath = ROOT_PATH) => {
      await manager.operations.createDirectory(joinPath(parentPath, name));
      await manager.loadTree();
    },
    onRename: async (oldPath, newName) => {
      const parentPath = oldPath.split('/').slice(0, -1).join('/') || ROOT_PATH;
      await manager.renameFileAndUpdateTab(oldPath, joinPath(parentPath, newName));
    },
    onDelete: async (path, node) => {
      await manager.deleteFileAndCloseTab(path, node?.type === 'directory');
      manager.state.clearSelection();
    },
    onBatchDelete: async (paths) => {
      await manager.batchDeleteAndCloseTabs(paths, true);
      manager.state.clearSelection();
    },
    isPathWritable,
    defaultWritableParent: DEFAULT_WRITABLE_PARENT,
    onUnwriteableContextHint: () => setShowWritableParentHint(true),
  });

  const handleNodeClick = React.useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);

    if (node.type === 'file' && modifier === 'none') {
      void manager.handleFileSelect(node);
    }
  }, [manager]);

  const handleNodeDoubleClick = React.useCallback((node: FileTreeNode) => {
    void manager.handleFileDoubleClick(node);
  }, [manager]);

  const handleContextMenu = React.useCallback((node: FileTreeNode, event: React.MouseEvent) => {
    manager.state.openContextMenu(event.clientX, event.clientY, node);
  }, [manager.state]);

  const handleMove = React.useCallback(async (sourcePath: string, destinationDirectory: string) => {
    const targetPath = joinPath(destinationDirectory, sourcePath.split('/').pop() || sourcePath);
    if (sourcePath === targetPath || destinationDirectory.startsWith(`${sourcePath}/`)) {
      return;
    }

    try {
      await manager.moveFileAndUpdateTabs(sourcePath, targetPath);
    } catch (error) {
      showErrorToast(error, t('knowledgeBase.files.moveFailed'));
    }
  }, [manager, showErrorToast, t]);

  const handleCopy = React.useCallback((node: FileTreeNode) => {
    setClipboardItem({ path: node.path, type: node.type });
    toast({
      title: t('knowledgeBase.files.copySuccessTitle'),
      description: t('knowledgeBase.files.copySuccessDescription', { path: node.path }),
    });
  }, [t, toast]);

  const handleCopyPath = React.useCallback(async (path: string) => {
    try {
      await navigator.clipboard.writeText(path);
      toast({
        title: t('knowledgeBase.files.copyPathSuccessTitle'),
        description: path,
      });
    } catch (error) {
      showErrorToast(error, t('knowledgeBase.files.copyPathFailed'));
    }
  }, [showErrorToast, t, toast]);

  const workbenchTabs = React.useMemo(
    () => manager.editor.tabs.map((tab): FileViewerWorkbenchTab => toFileWorkbenchTab(tab)),
    [manager.editor.tabs],
  );

  const workbenchAdapter = React.useMemo(() => createKnowledgeBaseFileWorkbenchAdapter({
    knowledgeBaseId,
    readFile: (path) => manager.operations.readFile(path),
    saveFile: handleSave,
    copyPath: handleCopyPath,
    revealInTree: (path) => {
      manager.state.selectNode(path);
    },
  }), [handleCopyPath, handleSave, knowledgeBaseId, manager.operations, manager.state]);

  const handleWorkbenchTabsChange = React.useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    const nextPaths = new Set(nextTabs.map((tab) => tab.path));

    manager.editor.tabs.forEach((tab) => {
      if (!nextPaths.has(tab.path)) {
        manager.editor.closeTab(tab.path);
      }
    });

    nextTabs.forEach((nextTab) => {
      const currentTab = manager.editor.getTab(nextTab.path);
      if (!currentTab) {
        return;
      }

      if (currentTab.content !== nextTab.content) {
        manager.editor.updateContent(nextTab.path, nextTab.content);
      }

      if (!nextTab.isModified && currentTab.isModified) {
        manager.editor.saveTab(nextTab.path);
      }
    });
  }, [manager.editor]);

  const handleWorkbenchActiveTabChange = React.useCallback((tabId: string | null) => {
    if (tabId) {
      manager.editor.setActiveTab(tabId);
    }
  }, [manager.editor]);

  const handlePaste = React.useCallback(async () => {
    const targetNode = manager.state.contextMenu?.node;
    if (!clipboardItem || !targetNode) {
      return;
    }

    const targetDirectory = targetNode.type === 'directory' ? targetNode.path : getParentPath(targetNode.path);
    const targetPath = joinPath(targetDirectory, getNodeName(clipboardItem.path));

    try {
      const queryParams = new URLSearchParams({
        source_path: clipboardItem.path,
        dest_path: targetPath,
        overwrite: 'false',
      });
      await apiClient.post(`${knowledgeBaseFileEndpoints.copy(knowledgeBaseId)}?${queryParams.toString()}`);
      await manager.loadTree();
      setClipboardItem(null);
      toast({
        title: t('knowledgeBase.files.pasteSuccessTitle'),
        description: t('knowledgeBase.files.pasteSuccessDescription', { path: targetPath }),
      });
    } catch (error) {
      const errorCode = getApiErrorCode(error);
      if (errorCode === 'KB_QUOTA_EXCEEDED' || errorCode === 'USER_KB_QUOTA_EXCEEDED') {
        showErrorToast(error, t('knowledgeBase.files.quotaExceeded'));
        return;
      }
      if (errorCode === 'FILE_ALREADY_EXISTS') {
        showErrorToast(error, t('knowledgeBase.files.targetExists'));
        return;
      }
      showErrorToast(error, t('knowledgeBase.files.pasteFailed'));
    }
  }, [clipboardItem, knowledgeBaseId, manager, showErrorToast, t, toast]);

  const handleDragStart = React.useCallback((node: FileTreeNode) => {
    if (readOnly || !isPathWritable(node.path)) {
      return;
    }
    setDraggingPath(node.path);
  }, [readOnly]);

  const handleDragEnd = React.useCallback(() => {
    setDraggingPath(null);
    setDragOverPath(null);
  }, []);

  const handleDragOverNode = React.useCallback((node: FileTreeNode) => {
    if (readOnly || !isPathWritable(node.path)) {
      return;
    }
    setDragOverPath(node.path);
  }, [readOnly]);

  const handleDragLeaveNode = React.useCallback(() => {
    setDragOverPath(null);
  }, []);

  const handleDropOnNode = React.useCallback(async (node: FileTreeNode, event: React.DragEvent) => {
    if (readOnly || !isPathWritable(node.path)) {
      return;
    }

    setDragOverPath(null);
    setDraggingPath(null);

    const externalFiles = Array.from(event.dataTransfer.files ?? []);
    if (externalFiles.length > 0) {
      await uploadFilesToPath(externalFiles, getTargetPath(node));
      return;
    }

    const sourcePath = event.dataTransfer.getData('text/plain');
    if (!sourcePath || node.type !== 'directory' || sourcePath === node.path) {
      return;
    }

    await handleMove(sourcePath, node.path);
  }, [handleMove, readOnly, uploadFilesToPath]);

  const handleExternalDragEnter = React.useCallback((event: React.DragEvent<HTMLDivElement>) => {
    if (readOnly || !Array.from(event.dataTransfer.types).includes('Files')) {
      return;
    }

    dragDepthRef.current += 1;
    setIsExternalDragActive(true);
    event.preventDefault();
  }, [readOnly]);

  const handleExternalDragOver = React.useCallback((event: React.DragEvent<HTMLDivElement>) => {
    if (readOnly || !Array.from(event.dataTransfer.types).includes('Files')) {
      return;
    }

    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  }, [readOnly]);

  const handleExternalDragLeave = React.useCallback(() => {
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) {
      setIsExternalDragActive(false);
    }
  }, []);

  const handleExternalDrop = React.useCallback(async (event: React.DragEvent<HTMLDivElement>) => {
    if (readOnly) {
      return;
    }

    event.preventDefault();
    dragDepthRef.current = 0;
    setIsExternalDragActive(false);

    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length > 0) {
      await uploadFilesToPath(files, DEFAULT_WRITABLE_PARENT);
    }
  }, [readOnly, uploadFilesToPath]);

  const selectedNodes = React.useMemo(() => (
    Array.from(manager.state.selectedIds)
      .map((path) => manager.state.flatNodes.find((node) => node.path === path))
      .filter((node): node is FileTreeNode => Boolean(node))
  ), [manager.state.flatNodes, manager.state.selectedIds]);

  const getDirectoryNodeForPath = React.useCallback((path: string): FileTreeNode | undefined => (
    manager.state.flatNodes.find((node) => node.path === path && node.type === 'directory')
  ), [manager.state.flatNodes]);

  const getPrimaryTargetDirectoryNode = React.useCallback((): FileTreeNode | undefined => {
    if (selectedNodes.length !== 1) {
      return undefined;
    }

    const [selectedNode] = selectedNodes;
    if (selectedNode.type === 'directory') {
      return selectedNode;
    }

    return getDirectoryNodeForPath(getParentPath(selectedNode.path));
  }, [getDirectoryNodeForPath, selectedNodes]);

  const handleToolbarCreateFile = React.useCallback(() => {
    fileOps.openCreateFileDialog(getPrimaryTargetDirectoryNode());
  }, [fileOps, getPrimaryTargetDirectoryNode]);

  const handleToolbarCreateFolder = React.useCallback(() => {
    fileOps.openCreateFolderDialog(getPrimaryTargetDirectoryNode());
  }, [fileOps, getPrimaryTargetDirectoryNode]);

  const handleToolbarUpload = React.useCallback(() => {
    handleUpload(getPrimaryTargetDirectoryNode()?.path ?? ROOT_PATH);
  }, [getPrimaryTargetDirectoryNode, handleUpload]);

  const handleToggleHiddenEntries = React.useCallback(() => {
    setShowHiddenEntries((current) => !current);
  }, []);

  const contextMenuItems = useFileTreeContextMenu({
    node: manager.state.contextMenu?.node ?? null,
    readOnly,
    enableMultiSelect: !readOnly,
    selectedCount: manager.state.selectedIds.size,
    selectedIds: manager.state.selectedIds,
    hasClipboard: !!clipboardItem,
    isPathWritable,
    features: {
      open: true,
      view: true,
      upload: true,
      createFile: true,
      createFolder: true,
      copy: true,
      copyPath: true,
      paste: true,
      rename: true,
      delete: true,
      refresh: true,
    },
    callbacks: {
      onOpen: (node) => {
        void manager.handleFileSelect(node);
      },
      onView: (node) => {
        void manager.handleFileSelect(node);
      },
      onUpload: () => handleUpload(getTargetPath(manager.state.contextMenu?.node)),
      onCreateFile: () => fileOps.openCreateFileDialog(manager.state.contextMenu?.node ?? undefined),
      onCreateFolder: () => fileOps.openCreateFolderDialog(manager.state.contextMenu?.node ?? undefined),
      onCopy: handleCopy,
      onCopyPath: (path) => {
        void handleCopyPath(path);
      },
      onPaste: () => {
        void handlePaste();
      },
      onRename: (node) => fileOps.openRenameDialog(node),
      onDelete: (node) => fileOps.openDeleteDialog(node),
      onBatchDelete: () => fileOps.openBatchDeleteDialog(selectedNodes),
      onRefresh: () => {
        void manager.loadTree();
      },
      onClose: manager.state.closeContextMenu,
    },
    t,
  });

  const handleTreeResizeStart = React.useCallback((event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    dragStateRef.current = {
      startX: event.clientX,
      startWidth: treeWidth,
    };
    document.body.classList.add('select-none', 'cursor-col-resize');
    setIsDragging(true);
  }, [treeWidth]);

  React.useEffect(() => {
    if (!isDragging) {
      return;
    }

    const handleMouseMove = (event: MouseEvent) => {
      const dragState = dragStateRef.current;
      if (!dragState) {
        return;
      }

      const deltaX = event.clientX - dragState.startX;
      const nextWidth = Math.min(
        Math.max(dragState.startWidth + deltaX, KNOWLEDGE_BASE_MIN_COLUMN_WIDTH),
        KNOWLEDGE_BASE_MAX_COLUMN_WIDTH,
      );
      setTreeWidth(nextWidth);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      dragStateRef.current = null;
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      dragStateRef.current = null;
      document.body.classList.remove('select-none', 'cursor-col-resize');
    };
  }, [isDragging]);

  return (
    <div
      className="relative flex h-full overflow-hidden bg-background"
      onDragEnter={handleExternalDragEnter}
      onDragOver={handleExternalDragOver}
      onDragLeave={handleExternalDragLeave}
      onDrop={handleExternalDrop}
    >
      <div
        className={cn(
          'relative border-r transition-[width] duration-200',
          !treeCollapsed && 'shrink-0',
        )}
        style={{ width: treeCollapsed ? KNOWLEDGE_BASE_COLLAPSED_COLUMN_WIDTH : treeWidth }}
      >
        <div
          className={cn(
            'flex h-10 items-center border-b border-sidebar-border bg-card px-3',
            treeCollapsed ? 'justify-center' : 'justify-between',
          )}
        >
          {!treeCollapsed ? (
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-sky-600" />
              <span className="text-sm font-medium">{t('knowledgeBase.files.toolbarTitle')}</span>
              {readOnly && <Badge variant="outline">{t('knowledgeBase.files.readOnlyBadge')}</Badge>}
            </div>
          ) : null}
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setTreeCollapsed((value) => !value)}
            title={treeCollapsed ? t('workspace.layout.expandSidebar') : t('workspace.layout.collapseSidebar')}
            aria-label={treeCollapsed ? t('workspace.layout.expandSidebar') : t('workspace.layout.collapseSidebar')}
          >
            <ChevronLeft className={cn('h-3.5 w-3.5 transition-transform', treeCollapsed && 'rotate-180')} />
          </Button>
        </div>
        {treeCollapsed ? (
          <div className="flex flex-1 items-start justify-center pt-3">
            <Database className="h-4 w-4 text-sky-600" />
          </div>
        ) : (
          <StandardFileTreeLayout
            searchValue={manager.state.searchQuery}
            onSearchChange={manager.state.setSearchQuery}
            onSearchClear={manager.state.clearSearch}
            showSearch
            showToolbar={false}
          >
            <FileTreePanel
                state={manager.state}
                onNodeClick={handleNodeClick}
                onNodeDoubleClick={handleNodeDoubleClick}
                onContextMenu={handleContextMenu}
                onDragStart={handleDragStart}
                onDragEnd={handleDragEnd}
                onDragOver={handleDragOverNode}
                onDragLeave={handleDragLeaveNode}
                onDrop={handleDropOnNode}
                onCreateFile={() => fileOps.openCreateFileDialog()}
                onCreateFolder={() => fileOps.openCreateFolderDialog()}
                onUpload={() => handleUpload(ROOT_PATH)}
                onPaste={(files) => {
                  void uploadFilesToPath(files, ROOT_PATH);
                }}
                onRefresh={() => { void manager.loadTree(); }}
                onBatchDelete={() => fileOps.openBatchDeleteDialog(selectedNodes)}
                isPathWritable={isPathWritable}
                enableSearch={false}
                enableToolbar
                enableMultiSelectBar={!readOnly}
                enableDragDrop={!readOnly}
                draggingPath={draggingPath}
                dragOverPath={dragOverPath}
                renderToolbar={() => (
                  <div className="flex w-full items-center justify-between gap-2">
                    <div className="flex items-center gap-1">
                      {!readOnly && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0"
                            onClick={handleToolbarCreateFile}
                            disabled={manager.state.isLoading}
                            title={t('knowledgeBase.files.actions.createFile')}
                            aria-label={t('knowledgeBase.files.actions.createFile')}
                          >
                            <FilePlus className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0"
                            onClick={handleToolbarCreateFolder}
                            disabled={manager.state.isLoading}
                            title={t('knowledgeBase.files.actions.createFolder')}
                            aria-label={t('knowledgeBase.files.actions.createFolder')}
                          >
                            <FolderPlus className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 w-7 p-0"
                            onClick={handleToolbarUpload}
                            disabled={manager.state.isLoading}
                            title={t('knowledgeBase.files.actions.upload')}
                            aria-label={t('knowledgeBase.files.actions.upload')}
                          >
                            <Upload className="h-3.5 w-3.5" />
                          </Button>
                        </>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 w-7 p-0"
                        onClick={handleToggleHiddenEntries}
                        disabled={manager.state.isLoading}
                        title={t(
                          showHiddenEntries
                            ? 'knowledgeBase.files.actions.hidden.hideTooltip'
                            : 'knowledgeBase.files.actions.hidden.showTooltip'
                        )}
                        aria-label={t(
                          showHiddenEntries
                            ? 'knowledgeBase.files.actions.hidden.hideLabel'
                            : 'knowledgeBase.files.actions.hidden.showLabel'
                        )}
                      >
                        {showHiddenEntries ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                      </Button>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0"
                      onClick={() => { void manager.loadTree(); }}
                      disabled={manager.state.isLoading}
                      title={t('knowledgeBase.files.actions.refresh')}
                      aria-label={t('knowledgeBase.files.actions.refresh')}
                    >
                      <RefreshCw className={cn('h-3.5 w-3.5', manager.state.isLoading && 'animate-spin')} />
                    </Button>
                  </div>
                )}
                className="flex-1"
              />
              <FileTreeContextMenu
                contextMenu={manager.state.contextMenu}
                items={contextMenuItems}
                onClose={manager.state.closeContextMenu}
              />
          </StandardFileTreeLayout>
        )}
        {!treeCollapsed && (
          <div
            className={cn(
              'absolute right-0 top-0 h-full w-1 cursor-col-resize transition-colors',
              isDragging ? 'bg-primary/40' : 'bg-transparent hover:bg-primary/20',
            )}
            onMouseDown={handleTreeResizeStart}
          />
        )}
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        {manager.state.error && (
          <Alert variant="destructive" className="m-4 mb-0">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t('knowledgeBase.files.operationFailedTitle')}</AlertTitle>
            <AlertDescription>{manager.state.error}</AlertDescription>
          </Alert>
        )}

        <div className="min-h-0 flex-1">
          <FileViewerWorkbench
            tabs={workbenchTabs}
            activeTabId={manager.editor.activeTabPath}
            adapter={workbenchAdapter}
            capabilities={{
              canEdit: !readOnly,
              canSave: !readOnly,
              canReadBlob: true,
              canCopyPath: true,
              canRevealInTree: true,
              canCloseTabs: true,
            }}
            readOnly={readOnly}
            isExpanded={isWorkbenchExpanded}
            onExpandedChange={setIsWorkbenchExpanded}
            isPathWritable={isPathWritable}
            renderReadOnlyBadge={() => (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
                      {t('knowledgeBase.files.readOnlyPathBadge')}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>{t('knowledgeBase.files.readOnlyPathBadgeTooltip')}</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
            onTabsChange={handleWorkbenchTabsChange}
            onActiveTabChange={handleWorkbenchActiveTabChange}
          />
        </div>
      </div>

      {isExternalDragActive && !readOnly && (
        <div className="pointer-events-none absolute inset-0 z-20 flex items-center justify-center bg-sky-500/10">
          <div className="rounded-xl border border-sky-300 bg-background/95 px-6 py-4 text-sm font-medium text-sky-700 shadow-lg">
            {t('knowledgeBase.files.dropOverlay')}
          </div>
        </div>
      )}

      <FileCreateDialog
        open={fileOps.dialogState.type === 'create-file'}
        type="file"
        onClose={() => {
          setShowWritableParentHint(false);
          fileOps.closeDialog();
        }}
        onConfirm={fileOps.handleCreateFile}
        hint={showWritableParentHint || fileOps.dialogState.data?.parentPathWasOverridden
          ? t('knowledgeBase.files.actions.uploadParentPickerHint')
          : undefined}
      />
      <FileCreateDialog
        open={fileOps.dialogState.type === 'create-folder'}
        type="folder"
        onClose={() => {
          setShowWritableParentHint(false);
          fileOps.closeDialog();
        }}
        onConfirm={fileOps.handleCreateFolder}
        hint={showWritableParentHint || fileOps.dialogState.data?.parentPathWasOverridden
          ? t('knowledgeBase.files.actions.uploadParentPickerHint')
          : undefined}
      />
      <FileRenameDialog
        open={fileOps.dialogState.type === 'rename'}
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleRename}
        currentName={fileOps.dialogState.data?.currentName || ''}
      />
      <FileDeleteDialog
        open={fileOps.dialogState.type === 'delete'}
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleDelete}
        fileName={fileOps.dialogState.data?.node?.name || ''}
        fileType={fileOps.dialogState.data?.node?.type || 'file'}
      />
      <BatchDeleteDialog
        open={fileOps.dialogState.type === 'batch-delete'}
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleBatchDelete}
        files={(fileOps.dialogState.data?.nodes || []).map((node) => ({
          name: node.name,
          path: node.path,
          type: node.type,
        }))}
      />
    </div>
  );
};

export default KnowledgeBaseFilesTab;
