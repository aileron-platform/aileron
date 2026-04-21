import React from 'react';
import { AlertCircle, Database, FolderTree, Lock } from 'lucide-react';
import {
  BatchDeleteDialog,
  FileCreateDialog,
  FileDeleteDialog,
  FileEditorPanel,
  FileRenameDialog,
  FileTreeContextMenu,
  FileTreePanel,
  FileTreeToolbar,
  StandardFileTreeLayout,
  useFileOperationsWithDialog,
  useFileTreeContextMenu,
  useFileTreeManager,
  type FileTreeNode,
  type SelectionModifier,
} from '@/shared/components/file-tree-manager';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';

interface KnowledgeBaseFilesTabProps {
  knowledgeBaseId: string;
  readOnly: boolean;
}

const ROOT_PATH = '/';

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

export const KnowledgeBaseFilesTab: React.FC<KnowledgeBaseFilesTabProps> = ({
  knowledgeBaseId,
  readOnly,
}) => {
  const { toast } = useToast();
  const { t } = useI18n();
  const [draggingPath, setDraggingPath] = React.useState<string | null>(null);
  const [dragOverPath, setDragOverPath] = React.useState<string | null>(null);
  const [isExternalDragActive, setIsExternalDragActive] = React.useState(false);
  const dragDepthRef = React.useRef(0);

  const manager = useFileTreeManager({
    apiConfig: {
      type: 'knowledge-base',
      knowledgeBaseId,
      includeHidden: false,
    },
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

    try {
      await manager.operations.uploadFiles({
        targetPath,
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

  const handleUpload = React.useCallback((targetPath = ROOT_PATH) => {
    if (readOnly) {
      return;
    }

    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = async (event) => {
      const files = (event.target as HTMLInputElement).files;
      if (!files || files.length === 0) {
        return;
      }

      await uploadFilesToPath(Array.from(files), targetPath);
    };
    input.click();
  }, [readOnly, uploadFilesToPath]);

  const handleSave = React.useCallback(async (path: string, content: string) => {
    if (readOnly) {
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
      await manager.operations.moveFile(sourcePath, targetPath);
      await manager.loadTree();
    } catch (error) {
      showErrorToast(error, t('knowledgeBase.files.moveFailed'));
    }
  }, [manager, showErrorToast, t]);

  const handleDragStart = React.useCallback((node: FileTreeNode) => {
    if (readOnly) {
      return;
    }
    setDraggingPath(node.path);
  }, [readOnly]);

  const handleDragEnd = React.useCallback(() => {
    setDraggingPath(null);
    setDragOverPath(null);
  }, []);

  const handleDragOverNode = React.useCallback((node: FileTreeNode) => {
    if (readOnly) {
      return;
    }
    setDragOverPath(node.path);
  }, [readOnly]);

  const handleDragLeaveNode = React.useCallback(() => {
    setDragOverPath(null);
  }, []);

  const handleDropOnNode = React.useCallback(async (node: FileTreeNode, event: React.DragEvent) => {
    if (readOnly) {
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
      await uploadFilesToPath(files, ROOT_PATH);
    }
  }, [readOnly, uploadFilesToPath]);

  const selectedNodes = React.useMemo(() => (
    Array.from(manager.state.selectedIds)
      .map((path) => manager.state.flatNodes.find((node) => node.path === path))
      .filter((node): node is FileTreeNode => Boolean(node))
  ), [manager.state.flatNodes, manager.state.selectedIds]);

  const contextMenuItems = useFileTreeContextMenu({
    node: manager.state.contextMenu?.node ?? null,
    readOnly,
    enableMultiSelect: !readOnly,
    selectedCount: manager.state.selectedIds.size,
    selectedIds: manager.state.selectedIds,
    features: {
      open: true,
      view: true,
      upload: !readOnly,
      createFile: !readOnly,
      createFolder: !readOnly,
      rename: !readOnly,
      delete: !readOnly,
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

  const renderReadOnlyEditor = React.useCallback((tab: {
    path: string;
    content: string;
  }) => (
    <div className="flex h-full flex-col bg-background">
      <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-2 text-xs text-muted-foreground">
        <span>{tab.path}</span>
        <span className="inline-flex items-center gap-1">
          <Lock className="h-3.5 w-3.5" />
          {t('knowledgeBase.files.viewerNotice')}
        </span>
      </div>
      <textarea
        readOnly
        value={tab.content}
        className="h-full w-full resize-none border-0 bg-background p-4 font-mono text-sm outline-none"
        spellCheck={false}
      />
    </div>
  ), []);

  return (
    <div
      className="relative flex h-[680px] overflow-hidden rounded-xl border bg-background"
      onDragEnter={handleExternalDragEnter}
      onDragOver={handleExternalDragOver}
      onDragLeave={handleExternalDragLeave}
      onDrop={handleExternalDrop}
    >
      <div className="w-80 border-r">
        <StandardFileTreeLayout
          searchValue={manager.state.searchQuery}
          onSearchChange={manager.state.setSearchQuery}
          onSearchClear={manager.state.clearSearch}
          toolbarContent={(
            <FileTreeToolbar
              leftContent={(
                <div className="flex items-center gap-2">
                  <Database className="h-4 w-4 text-sky-600" />
                  <span className="text-sm font-medium">{t('knowledgeBase.files.toolbarTitle')}</span>
                  {readOnly && <Badge variant="outline">{t('knowledgeBase.files.readOnlyBadge')}</Badge>}
                </div>
              )}
              onCreateFile={() => fileOps.openCreateFileDialog()}
              onCreateFolder={() => fileOps.openCreateFolderDialog()}
              onUpload={() => handleUpload(ROOT_PATH)}
              onRefresh={() => { void manager.loadTree(); }}
              isLoading={manager.state.isLoading}
              isReadOnly={readOnly}
              className="border-b border-sidebar-border bg-sidebar-accent/20 p-2"
            />
          )}
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
            enableSearch={false}
            enableToolbar={false}
            enableMultiSelectBar={!readOnly}
            enableDragDrop={!readOnly}
            draggingPath={draggingPath}
            dragOverPath={dragOverPath}
            className="flex-1"
          />
          <FileTreeContextMenu
            contextMenu={manager.state.contextMenu}
            items={contextMenuItems}
            onClose={manager.state.closeContextMenu}
          />
        </StandardFileTreeLayout>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b bg-muted/20 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <FolderTree className="h-4 w-4 text-sky-600" />
                {t('knowledgeBase.files.headerTitle')}
              </h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {t('knowledgeBase.files.headerDescription')}
              </p>
            </div>
            {readOnly && (
              <Badge variant="secondary" className="gap-1">
                <Lock className="h-3.5 w-3.5" />
                {t('knowledgeBase.files.viewerBadge')}
              </Badge>
            )}
          </div>
        </div>

        {manager.state.error && (
          <Alert variant="destructive" className="m-4 mb-0">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t('knowledgeBase.files.operationFailedTitle')}</AlertTitle>
            <AlertDescription>{manager.state.error}</AlertDescription>
          </Alert>
        )}

        <div className="min-h-0 flex-1">
          <FileEditorPanel
            editor={manager.editor}
            onSave={handleSave}
            renderEditor={readOnly ? renderReadOnlyEditor : undefined}
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
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleCreateFile}
      />
      <FileCreateDialog
        open={fileOps.dialogState.type === 'create-folder'}
        type="folder"
        onClose={fileOps.closeDialog}
        onConfirm={fileOps.handleCreateFolder}
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
