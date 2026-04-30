import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { createLogger } from '@/shared/services/logger';
import { FolderPlus, Plus, RefreshCw, Upload } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import SectionSidebarShell from '@/features/template-management/components/metadata-viewers/SectionSidebarShell';

const logger = createLogger('TemplateFileManager');
import { useFileTreeManager } from '@/shared/components/file-workbench';
import { useFileOperationsWithDialog } from '@/shared/components/file-workbench';
import {
  FileTreePanel,
  FileTreeContextMenu,
  useFileTreeContextMenu,
  type FileTreeNode as FileTreeNodeType,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import {
  FileCreateDialog,
  FileRenameDialog,
  FileDeleteDialog,
  BatchDeleteDialog,
} from '@/shared/components/file-workbench';
import { useI18n } from '@/shared/hooks/useI18n';
import { FileEditor } from '@/shared/components/file-workbench';
import { apiClient } from '@/shared/api/apiClient';
import { createTemplateFileTreeDataAdapter } from '@/features/template-management/components/file-workbench/templateFileTreeDataAdapter';

export interface FileNode {
  id: string;
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
  content?: string;
  size?: number;
  extension?: string;
}

interface TemplateFileManagerProps {
  templateId?: string;
  basePath: 'scripts' | 'skills';
  title?: string;
  leadingIcon?: React.ReactNode;
  onFilesChange?: (files: FileNode[]) => void;
}

type TemplateFileManagerContentProps = Omit<TemplateFileManagerProps, 'templateId'> & {
  templateId: string;
};

const TemplateFileManagerEmptyState: React.FC = () => {
  const { t } = useI18n();

  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center text-muted-foreground">
        <p className="text-sm">{t('template.editor.fileManagement.viewer.noTemplate')}</p>
      </div>
    </div>
  );
};

const TemplateFileManagerContent: React.FC<TemplateFileManagerContentProps> = ({
  templateId,
  basePath,
  title,
  leadingIcon,
  onFilesChange: _onFilesChange,
}) => {
  const { t } = useI18n();
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);
  const [draggingPath, setDraggingPath] = useState<string | null>(null);
  const [clipboardItem, setClipboardItem] = useState<{ path: string; type: 'file' | 'directory' } | null>(null);

  const fileTreeAdapter = useMemo(() => createTemplateFileTreeDataAdapter({
    templateId,
    scope: basePath,
  }), [templateId, basePath]);
  const fileTreeAdapterKey = useMemo(
    () => JSON.stringify({ templateId, scope: basePath }),
    [basePath, templateId],
  );

  const manager = useFileTreeManager({
    adapter: fileTreeAdapter,
    adapterKey: fileTreeAdapterKey,
    stateOptions: {
      enableMultiSelect: true,
    },
    autoLoad: false,
  });

  useEffect(() => {
    if (templateId && basePath) {
      manager.loadTree();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fileTreeAdapterKey]);

  const handleContentChange = useCallback((content: string) => {
    if (manager.editor.activeTab) {
      manager.editor.updateContent(manager.editor.activeTab.path, content);
    }
  }, []);

  const fileOps = useFileOperationsWithDialog({
    onCreateFile: async (name, parentPath = '/') => {
      const fullPath = parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;
      await manager.createFileAndOpen(fullPath, '');
    },
    onCreateFolder: async (name, parentPath = '/') => {
      const fullPath = parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;
      await manager.operations.createDirectory(fullPath);
      await manager.loadTree();
    },
    onRename: async (oldPath, newName) => {
      await manager.operations.renameFile(oldPath, newName);
      await manager.loadTree();
    },
    onDelete: async (path: string, node) => {
      const isDirectory = node?.type === 'directory';
      await manager.operations.deleteFile(path, isDirectory);
      await manager.loadTree();
    },
    onBatchDelete: async (paths) => {
      await manager.batchDeleteAndCloseTabs(paths, true);
      manager.state.clearSelection();
    },
  });

  const handleNodeClick = useCallback((node: FileTreeNodeType, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);

    if (node.type === 'file' && modifier === 'none') {
      manager.handleFileSelect(node);
    }
  }, [manager]);

  const handleNodeDoubleClick = useCallback((node: FileTreeNodeType) => {
    manager.handleFileDoubleClick(node);
  }, [manager]);

  const handleContextMenu = useCallback((node: FileTreeNodeType, event: React.MouseEvent) => {
    manager.state.openContextMenu(event.clientX, event.clientY, node);
  }, [manager]);

  const handleUpload = useCallback(() => {
    // Use an empty path for the root because the template API normalizes it differently from slash.
    let targetPath = '';
    if (manager.state.contextMenu?.node?.type === 'directory') {
      targetPath = manager.state.contextMenu.node.path;
    }

    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = async (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (!files || files.length === 0) return;

      try {
        await manager.operations.uploadFiles({
          targetPath,
          files: Array.from(files),
        });
        await manager.loadTree();
      } catch (error) {
        logger.error('Failed to upload template files', { error });
      }
    };
    input.click();
  }, [manager]);

  const handleFilePaste = useCallback(async (files: File[]) => {
    if (!files || files.length === 0) return;

    let targetPath = '';
    if (manager.state.selectedId) {
      const selectedNode = manager.state.flatNodes.find(n => n.path === manager.state.selectedId);
      if (selectedNode?.type === 'directory') {
        targetPath = selectedNode.path;
      }
    }

    try {
      await manager.operations.uploadFiles({
        targetPath,
        files,
      });
      await manager.loadTree();
    } catch (error) {
      logger.error('Failed to paste uploaded template files', { error });
    }
  }, [manager]);

  const handleRefresh = useCallback(() => {
    manager.loadTree();
  }, [manager]);

  const handleSaveFile = useCallback(async (content: string) => {
    if (!manager.editor.activeTab) return;

    await manager.operations.updateFile(manager.editor.activeTab.path, content);
    manager.editor.updateContent(manager.editor.activeTab.path, content);
    manager.editor.saveTab(manager.editor.activeTab.path);
  }, [manager]);

  const handleDragStart = useCallback((node: FileTreeNodeType) => {
    setDraggingPath(node.path);
  }, []);

  const handleDragEnd = useCallback(() => {
    setDraggingPath(null);
    setDragOverPath(null);
  }, []);

  const handleDragOver = useCallback((node: FileTreeNodeType, event: React.DragEvent) => {
    event.preventDefault();
    if (node.type === 'directory') {
      setDragOverPath(node.path);
    }
  }, []);

  const handleDragLeave = useCallback(() => {
    setDragOverPath(null);
  }, []);

  const handleDrop = useCallback(async (targetNode: FileTreeNodeType, event: React.DragEvent) => {
    event.preventDefault();

    if (!draggingPath || targetNode.type !== 'directory') {
      setDragOverPath(null);
      return;
    }

    try {
      const fileName = draggingPath.split('/').pop() || draggingPath;
      const targetPath = `${targetNode.path}/${fileName}`;

      await manager.operations.moveFile(draggingPath, targetPath);
      await manager.loadTree();
    } catch (error) {
      logger.error('Failed to move template file', { error });
    } finally {
      setDragOverPath(null);
      setDraggingPath(null);
    }
  }, [draggingPath, manager]);

  const handleCopy = useCallback(() => {
    if (!manager.state.contextMenu) return;

    const node = manager.state.contextMenu.node;
    setClipboardItem({
      path: node.path,
      type: node.type,
    });
    manager.state.closeContextMenu();
  }, [manager]);

  const handlePaste = useCallback(async () => {
    if (!clipboardItem || !manager.state.contextMenu || !templateId) return;

    const targetNode = manager.state.contextMenu.node;
    const targetPath = targetNode.type === 'directory' ? targetNode.path : targetNode.path.split('/').slice(0, -1).join('/');

    manager.state.closeContextMenu();

    try {
      await apiClient.post(`/templates/${templateId}/files/copy?scope=${basePath}&source_path=${encodeURIComponent(clipboardItem.path)}&dest_path=${encodeURIComponent(targetPath)}`);

      await manager.loadTree();
    } catch (error) {
      logger.error('Failed to paste template file', { error });
      alert(t('template.editor.fileManagement.toasts.paste.error.description'));
    }
  }, [clipboardItem, manager, templateId, basePath]);

  const isPasteDisabled = useMemo(() => {
    if (!clipboardItem || !manager.state.contextMenu) return true;

    const targetNode = manager.state.contextMenu.node;
    const isDirectoryTarget = targetNode.type === 'directory';

    if (!isDirectoryTarget) return true;

    if (clipboardItem.path === targetNode.path) return true;

    if (clipboardItem.type === 'directory' && targetNode.path.startsWith(clipboardItem.path + '/')) {
      return true;
    }

    return false;
  }, [clipboardItem, manager.state.contextMenu]);

  const contextMenuItems = useFileTreeContextMenu({
    node: manager.state.contextMenu?.node || null,
    hasClipboard: !isPasteDisabled,
    features: {
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
      onUpload: handleUpload,
      onCreateFile: () => {
        const node = manager.state.contextMenu?.node;
        if (node) {
          fileOps.openCreateFileDialog(node);
        }
      },
      onCreateFolder: () => {
        const node = manager.state.contextMenu?.node;
        if (node) {
          fileOps.openCreateFolderDialog(node);
        }
      },
      onCopy: handleCopy,
      onCopyPath: (path) => {
        navigator.clipboard.writeText(path).then(() => {
          logger.debug('Template file path copied', { path });
        }).catch((error) => {
          logger.error('Failed to copy template file path', { error });
        });
      },
      onPaste: handlePaste,
      onRename: (node) => fileOps.openRenameDialog(node),
      onDelete: (node) => fileOps.openDeleteDialog(node),
      onRefresh: handleRefresh,
      onClose: manager.state.closeContextMenu,
    },
    t,
  });

  const headerActions = (
    <>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        onClick={handleRefresh}
        disabled={manager.state.isLoading}
        title={t('template.editor.fileManagement.sidebar.refresh')}
        aria-label={t('template.editor.fileManagement.sidebar.refresh')}
      >
        <RefreshCw className={`h-4 w-4 ${manager.state.isLoading ? 'animate-spin' : ''}`} />
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 w-7 p-0"
        onClick={handleUpload}
        title={t('template.editor.fileManagement.sidebar.upload')}
        aria-label={t('template.editor.fileManagement.sidebar.upload')}
      >
        <Upload className="h-4 w-4" />
      </Button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0"
            title={t('template.editor.fileManagement.actions.create.trigger')}
            aria-label={t('template.editor.fileManagement.actions.create.trigger')}
          >
            <Plus className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={() => fileOps.openCreateFileDialog()} className="text-xs">
            <Plus className="mr-2 h-4 w-4" />
            {t('template.editor.fileManagement.sidebar.createFile')}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => fileOps.openCreateFolderDialog()} className="text-xs">
            <FolderPlus className="mr-2 h-4 w-4" />
            {t('template.editor.fileManagement.sidebar.createFolder')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  );

  return (
    <div className="flex h-full border-x border-b overflow-hidden bg-background">
      <div className="w-80">
        <SectionSidebarShell
          title={title || t('template.editor.fileManagement.header.title')}
          icon={
            leadingIcon && React.isValidElement(leadingIcon)
              ? React.cloneElement(leadingIcon as React.ReactElement, {
                className: 'h-4 w-4',
              })
              : undefined
          }
          actions={headerActions}
          searchValue={manager.state.searchQuery}
          onSearchChange={manager.state.setSearchQuery}
          onSearchClear={manager.state.clearSearch}
          searchPlaceholder={t('template.editor.fileManagement.search.placeholder')}
          body={(
          <FileTreePanel
            state={manager.state}
            onNodeClick={handleNodeClick}
            onNodeDoubleClick={handleNodeDoubleClick}
            onContextMenu={handleContextMenu}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onCreateFile={() => fileOps.openCreateFileDialog()}
            onCreateFolder={() => fileOps.openCreateFolderDialog()}
            onUpload={handleUpload}
            onPaste={handleFilePaste}
            onRefresh={handleRefresh}
            onBatchDelete={async (paths) => {
              const nodes: FileTreeNodeType[] = paths.map(path => ({
                id: path,
                name: path.split('/').pop() || path,
                path,
                type: 'file' as const,
              }));
              fileOps.openBatchDeleteDialog(nodes);
            }}
            enableSearch={false}
            enableToolbar={false}
            enableMultiSelectBar={true}
            enableDragDrop={true}
            draggingPath={draggingPath}
            dragOverPath={dragOverPath}
            className="flex-1"
          />
          )}
        />

        <FileTreeContextMenu
          contextMenu={manager.state.contextMenu}
          items={contextMenuItems}
          onClose={manager.state.closeContextMenu}
        />
      </div>

      <div className="flex-1 overflow-hidden">
        {!manager.editor.activeTab ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            {t('template.editor.fileManagement.viewer.noFile')}
          </div>
        ) : (
          <FileEditor
            fileName={manager.editor.activeTab.name}
            filePath={manager.editor.activeTab.path}
            fileContent={manager.editor.activeTab.content}
            onSave={handleSaveFile}
            onContentChange={handleContentChange}
            isLoading={false}
            isSaving={fileOps.isLoading}
          />
        )}
      </div>

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
        files={(fileOps.dialogState.data?.nodes || []).map(n => ({ name: n.name, path: n.path, type: n.type }))}
      />
    </div>
  );
};

const TemplateFileManager: React.FC<TemplateFileManagerProps> = ({ templateId, ...props }) => {
  if (!templateId) {
    return <TemplateFileManagerEmptyState />;
  }

  return <TemplateFileManagerContent templateId={templateId} {...props} />;
};

export default TemplateFileManager;
