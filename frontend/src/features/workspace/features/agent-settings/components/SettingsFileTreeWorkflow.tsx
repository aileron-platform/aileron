import React, { useCallback, useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { Button } from '@/shared/components/ui/button';
import {
  FileCreateDialog,
  FileDeleteDialog,
  FileRenameDialog,
  FileTreeContextMenu,
  FileTreePanel,
  FileTreeToolbar,
  StandardFileTreeLayout,
  useFileTreeContextMenu,
  useFileTreeManager,
  type FileTreeDataAdapter,
  type FileTreeNode as FileTreeNodeType,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { AgentSettingsLayerSelector } from './SettingsSourcePrimitives';

const logger = createLogger('SettingsFileTreeWorkflow');

export interface SettingsFileTreeScopeOption<TScope extends string = string> {
  value: TScope;
  label: string;
  icon?: React.ReactNode;
}

export interface SettingsFileSelection<TScope extends string = string> {
  path: string;
  scope: TScope;
  pluginId?: string;
  pluginName?: string;
  marketplaceName?: string;
}

export interface SettingsFileTreeWorkflowLabels {
  title: string;
  scopeLabel: string;
  searchPlaceholder: string;
}

export interface SettingsFileTreeWorkflowProps<TScope extends string = string> {
  adapter: FileTreeDataAdapter;
  adapterKey: string;
  scope: TScope;
  scopeOptions: Array<SettingsFileTreeScopeOption<TScope>>;
  readOnlyScopes?: TScope[];
  labels: SettingsFileTreeWorkflowLabels;
  icon: React.ComponentType<{ className?: string }>;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  onScopeChange: (scope: TScope) => void;
  onSelect: (file: SettingsFileSelection<TScope>) => void;
  toolbarRightContent?: React.ReactNode;
  autoLoad?: boolean;
  loadEnabled?: boolean;
  refreshSignal?: unknown;
  loggerContext?: Record<string, unknown>;
}

type DialogState =
  | { type: 'create-file'; parentPath: string }
  | { type: 'create-folder'; parentPath: string }
  | { type: 'rename'; node: FileTreeNodeType }
  | { type: 'delete'; node: FileTreeNodeType }
  | null;

const getParentPath = (node: FileTreeNodeType | null | undefined) => {
  if (!node) return '/';
  if (node.type === 'directory') return node.path;
  return node.path.split('/').slice(0, -1).join('/') || '/';
};

const buildChildPath = (parentPath: string, name: string) =>
  parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;

export const SettingsFileTreeWorkflow = <TScope extends string = string>({
  adapter,
  adapterKey,
  scope,
  scopeOptions,
  readOnlyScopes = [],
  labels,
  icon: HeaderIcon,
  isCollapsed,
  onToggleCollapse,
  onScopeChange,
  onSelect,
  toolbarRightContent,
  autoLoad = false,
  loadEnabled = true,
  refreshSignal,
  loggerContext = {},
}: SettingsFileTreeWorkflowProps<TScope>) => {
  const { t } = useI18n();
  const [dialogState, setDialogState] = useState<DialogState>(null);
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);
  const [draggingPath, setDraggingPath] = useState<string | null>(null);
  const isReadOnly = readOnlyScopes.includes(scope);

  const manager = useFileTreeManager({
    adapter,
    adapterKey,
    stateOptions: { enableMultiSelect: !isReadOnly },
    autoLoad,
  });
  const loadTree = manager.loadTree;

  useEffect(() => {
    if (loadEnabled) {
      void loadTree();
    }
  }, [adapterKey, loadEnabled, loadTree, refreshSignal]);

  const closeDialog = useCallback(() => setDialogState(null), []);

  const selectFile = useCallback((node: FileTreeNodeType) => {
    onSelect({
      path: node.path,
      scope: ((node.scope as TScope | null) || scope),
      pluginId: node.pluginId,
      pluginName: node.pluginName,
      marketplaceName: node.marketplaceName,
    });
  }, [onSelect, scope]);

  const handleSelectNode = useCallback((node: FileTreeNodeType, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file' && modifier === 'none') {
      selectFile(node);
    }
  }, [manager.state, selectFile]);

  const handleCreateFile = useCallback(() => {
    if (isReadOnly) return;
    setDialogState({ type: 'create-file', parentPath: getParentPath(manager.state.contextMenu?.node) });
  }, [isReadOnly, manager.state.contextMenu?.node]);

  const handleCreateFolder = useCallback(() => {
    if (isReadOnly) return;
    setDialogState({ type: 'create-folder', parentPath: getParentPath(manager.state.contextMenu?.node) });
  }, [isReadOnly, manager.state.contextMenu?.node]);

  const handleRefresh = useCallback(async () => {
    try {
      await loadTree();
    } catch (error) {
      logger.error('refreshFailed', { ...loggerContext, error });
    }
  }, [loadTree, loggerContext]);

  const handleUpload = useCallback(() => {
    if (isReadOnly) return;
    const targetPath = manager.state.contextMenu?.node?.type === 'directory' ? manager.state.contextMenu.node.path : '';
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = async (event) => {
      const files = (event.target as HTMLInputElement).files;
      if (!files || files.length === 0) return;
      try {
        await manager.operations.uploadFiles({ targetPath, files: Array.from(files) });
        await loadTree();
      } catch (error) {
        logger.error('uploadFailed', { ...loggerContext, error });
      }
    };
    input.click();
  }, [isReadOnly, loadTree, loggerContext, manager.operations, manager.state.contextMenu?.node]);

  const handleDialogCreateFile = useCallback(async (name: string) => {
    if (dialogState?.type !== 'create-file') return;
    try {
      await manager.createFileAndOpen(buildChildPath(dialogState.parentPath, name), '');
      closeDialog();
    } catch (error) {
      logger.error('createFileFailed', { ...loggerContext, error });
    }
  }, [closeDialog, dialogState, loggerContext, manager]);

  const handleDialogCreateFolder = useCallback(async (name: string) => {
    if (dialogState?.type !== 'create-folder') return;
    try {
      await manager.operations.createFile(`${buildChildPath(dialogState.parentPath, name)}/.gitkeep`, '');
      await loadTree();
      closeDialog();
    } catch (error) {
      logger.error('createFolderFailed', { ...loggerContext, error });
    }
  }, [closeDialog, dialogState, loadTree, loggerContext, manager.operations]);

  const handleDialogRename = useCallback(async (newName: string) => {
    if (dialogState?.type !== 'rename') return;
    try {
      await manager.operations.renameFile(dialogState.node.path, newName);
      await loadTree();
      closeDialog();
    } catch (error) {
      logger.error('renameFailed', { ...loggerContext, error });
    }
  }, [closeDialog, dialogState, loadTree, loggerContext, manager.operations]);

  const handleDialogDelete = useCallback(async () => {
    if (dialogState?.type !== 'delete') return;
    try {
      await manager.operations.deleteFile(dialogState.node.path, dialogState.node.type === 'directory');
      await loadTree();
      closeDialog();
    } catch (error) {
      logger.error('deleteFailed', { ...loggerContext, error });
    }
  }, [closeDialog, dialogState, loadTree, loggerContext, manager.operations]);

  const handleDragStart = useCallback((node: FileTreeNodeType, event: React.DragEvent) => {
    if (isReadOnly) return;
    setDraggingPath(node.path);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', node.path);
  }, [isReadOnly]);

  const handleDrop = useCallback(async (node: FileTreeNodeType, event: React.DragEvent) => {
    if (isReadOnly || node.type !== 'directory') return;
    event.preventDefault();
    const sourcePath = event.dataTransfer.getData('text/plain');
    if (!sourcePath || sourcePath === node.path || node.path.startsWith(`${sourcePath}/`)) {
      setDragOverPath(null);
      return;
    }
    try {
      await manager.operations.moveFile(sourcePath, node.path);
      await loadTree();
    } catch (error) {
      logger.error('moveFailed', { ...loggerContext, error });
    } finally {
      setDragOverPath(null);
      setDraggingPath(null);
    }
  }, [isReadOnly, loadTree, loggerContext, manager.operations]);

  const contextMenuItems = useFileTreeContextMenu({
    node: manager.state.contextMenu?.node || null,
    readOnly: isReadOnly,
    hasClipboard: false,
    features: {
      view: isReadOnly,
      upload: !isReadOnly,
      createFile: !isReadOnly,
      createFolder: !isReadOnly,
      copy: false,
      copyPath: !isReadOnly,
      paste: false,
      rename: !isReadOnly,
      delete: !isReadOnly,
    },
    callbacks: {
      onView: selectFile,
      onUpload: handleUpload,
      onCreateFile: handleCreateFile,
      onCreateFolder: handleCreateFolder,
      onCopyPath: (path) => {
        void navigator.clipboard.writeText(path).catch((error) => {
          logger.error('copyPathFailed', { ...loggerContext, error });
        });
      },
      onRename: (node) => setDialogState({ type: 'rename', node }),
      onDelete: (node) => setDialogState({ type: 'delete', node }),
      onClose: manager.state.closeContextMenu,
    },
    t,
  });

  const toolbarContent = (
    <FileTreeToolbar
      leftContent={
        <AgentSettingsLayerSelector
          value={scope}
          onChange={(value) => {
            onScopeChange(value as TScope);
            manager.state.clearSelection();
          }}
          options={scopeOptions}
          label={labels.scopeLabel}
        />
      }
      rightContent={toolbarRightContent}
      onCreateFile={handleCreateFile}
      onCreateFolder={handleCreateFolder}
      onUpload={handleUpload}
      onRefresh={handleRefresh}
      isLoading={manager.state.isLoading}
      isReadOnly={isReadOnly}
      showRefreshButton={false}
    />
  );

  const headerActions = (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="h-7 w-7 p-0"
      onClick={handleRefresh}
      disabled={manager.state.isLoading}
      aria-label={t('common.fileTree.contextMenu.refresh')}
      title={t('common.fileTree.contextMenu.refresh')}
    >
      <RefreshCw className={`h-3.5 w-3.5 ${manager.state.isLoading ? 'animate-spin' : ''}`} />
    </Button>
  );

  return (
    <div className="flex h-full flex-col border-r border-sidebar-border">
      <StandardFileTreeLayout
        title={labels.title}
        icon={<HeaderIcon className="h-5 w-5 text-sidebar-primary" />}
        isCollapsed={isCollapsed}
        onToggleCollapse={onToggleCollapse}
        searchValue={manager.state.searchQuery}
        onSearchChange={manager.state.setSearchQuery}
        onSearchClear={manager.state.clearSearch}
        searchPlaceholder={labels.searchPlaceholder}
        showSearch={!isCollapsed}
        headerActions={headerActions}
        toolbarContent={toolbarContent}
        showToolbar={!isCollapsed}
      >
        {isCollapsed ? (
          <CollapsedSidebarPlaceholder icon={HeaderIcon} className="text-primary" iconClassName="text-primary" />
        ) : (
          <>
            <FileTreePanel
              state={manager.state}
              onNodeClick={handleSelectNode}
              onNodeDoubleClick={(node) => {
                if (node.type === 'file') {
                  selectFile(node);
                }
              }}
              onContextMenu={(node, event) => manager.state.openContextMenu(event.clientX, event.clientY, node)}
              onDragStart={handleDragStart}
              onDragEnd={() => {
                setDraggingPath(null);
                setDragOverPath(null);
              }}
              onDragOver={(node, event) => {
                if (isReadOnly || node.type !== 'directory') return;
                event.preventDefault();
                event.dataTransfer.dropEffect = 'move';
                setDragOverPath(node.path);
              }}
              onDragLeave={() => setDragOverPath(null)}
              onDrop={handleDrop}
              onCreateFile={handleCreateFile}
              onCreateFolder={handleCreateFolder}
              onUpload={handleUpload}
              onPaste={(files) => {
                void manager.operations.uploadFiles({ targetPath: '', files }).then(loadTree);
              }}
              onRefresh={handleRefresh}
              onBatchDelete={(paths) => {
                void manager.batchDeleteAndCloseTabs(paths, true).then(loadTree);
              }}
              enableSearch={false}
              enableToolbar={false}
              enableMultiSelectBar={!isReadOnly}
              enableDragDrop={!isReadOnly}
              draggingPath={draggingPath}
              dragOverPath={dragOverPath}
              className="flex-1"
            />
            <FileTreeContextMenu
              contextMenu={manager.state.contextMenu}
              items={contextMenuItems}
              onClose={manager.state.closeContextMenu}
            />
          </>
        )}
      </StandardFileTreeLayout>

      <FileCreateDialog
        open={dialogState?.type === 'create-file'}
        type="file"
        onClose={closeDialog}
        onConfirm={handleDialogCreateFile}
      />
      <FileCreateDialog
        open={dialogState?.type === 'create-folder'}
        type="folder"
        onClose={closeDialog}
        onConfirm={handleDialogCreateFolder}
      />
      <FileRenameDialog
        open={dialogState?.type === 'rename'}
        onClose={closeDialog}
        onConfirm={handleDialogRename}
        currentName={dialogState?.type === 'rename' ? dialogState.node.name : ''}
      />
      <FileDeleteDialog
        open={dialogState?.type === 'delete'}
        onClose={closeDialog}
        onConfirm={handleDialogDelete}
        fileName={dialogState?.type === 'delete' ? dialogState.node.name : ''}
        fileType={dialogState?.type === 'delete' ? dialogState.node.type : 'file'}
      />
    </div>
  );
};

SettingsFileTreeWorkflow.displayName = 'SettingsFileTreeWorkflow';

export default SettingsFileTreeWorkflow;
