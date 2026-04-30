import React, { useState, useMemo, useCallback, useEffect } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('ClaudeCodeFileManager');
import { useFileTreeManager } from '@/shared/components/file-workbench';
import {
  FileTreePanel,
  StandardFileTreeLayout,
  FileTreeToolbar,
  ScopeSelector,
  FileTreeContextMenu,
  useFileTreeContextMenu,
  type ScopeOption,
} from '@/shared/components/file-workbench';
import {
  FileCreateDialog,
  FileRenameDialog,
  FileDeleteDialog,
  BatchDeleteDialog,
} from '@/shared/components/file-workbench';
import type { FileTreeNode as FileTreeNodeType, SelectionModifier } from '@/shared/components/file-workbench';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { FolderGit, User, Puzzle } from 'lucide-react';
import { claudeCodeApi } from '../services/claudeCodeApi';
import { useQuery } from '@tanstack/react-query';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { CLAUDE_CODE_ICONS } from '../../../components/navigation-constants';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';
import { createClaudeCodeFileTreeDataAdapter } from '../adapters/claudeCodeFileTreeDataAdapter';

export interface SelectedFile {
  path: string;
  scope: 'project' | 'user' | 'plugin';
}

interface ClaudeCodeFileManagerProps {
  collectionType: 'skills' | 'scripts';
  onSelect: (file: SelectedFile) => void;
  workspaceId: string;
}

const ClaudeCodeFileManager: React.FC<ClaudeCodeFileManagerProps> = ({
  collectionType,
  onSelect,
  workspaceId,
}) => {
  const { t } = useI18n();
  const { layout, toggleSecondColumn, workspaceRuntime } = useWorkspace();
  const [scope, setScope] = useState<'project' | 'user' | 'plugin'>('project');
  const [selectedPlugin, setSelectedPlugin] = useState<string>('all');
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);
  const [draggingPath, setDraggingPath] = useState<string | null>(null);

  type DialogState =
    | { type: 'create-file'; parentPath: string }
    | { type: 'create-folder'; parentPath: string }
    | { type: 'rename'; node: FileTreeNodeType }
    | { type: 'delete'; node: FileTreeNodeType }
    | { type: 'batch-delete'; nodes: FileTreeNodeType[] }
    | null;

  const [dialogState, setDialogState] = useState<DialogState>(null);

  const closeDialog = useCallback(() => {
    setDialogState(null);
  }, []);
  const [clipboardItem, setClipboardItem] = useState<{ path: string; type: 'file' | 'directory'; scope: string } | null>(null);

  const i18nPrefix = `workspace.claudeCode.${collectionType}`;
  const HeaderIcon = CLAUDE_CODE_ICONS[collectionType];
  const isCollapsed = layout.secondColumnCollapsed;

  const { data: pluginSkillsData } = useQuery({
    queryKey: ['plugin-skills', workspaceId],
    queryFn: () => claudeCodeApi.listPluginSkills(workspaceRuntime?.runtimeBaseUrl || '', workspaceId),
    enabled: !!workspaceId && !!workspaceRuntime?.runtimeBaseUrl && collectionType === 'skills' && scope === 'plugin',
  });

  const pluginSkills = pluginSkillsData?.plugins || [];

  const fileTreeAdapter = useMemo(() => createClaudeCodeFileTreeDataAdapter({
    workspaceId,
    scope,
    collection: collectionType,
    runtimeBaseUrl: workspaceRuntime?.runtimeBaseUrl,
  }), [workspaceId, scope, collectionType, workspaceRuntime?.runtimeBaseUrl]);
  const fileTreeAdapterKey = useMemo(
    () => JSON.stringify({ workspaceId, scope, collection: collectionType, runtimeBaseUrl: workspaceRuntime?.runtimeBaseUrl ?? null }),
    [collectionType, scope, workspaceId, workspaceRuntime?.runtimeBaseUrl],
  );

  const isReadOnly = scope === 'plugin';

  const manager = useFileTreeManager({
    adapter: fileTreeAdapter,
    adapterKey: fileTreeAdapterKey,
    stateOptions: {
      enableMultiSelect: !isReadOnly,
    },
    autoLoad: false,
  });

  useEffect(() => {
    if (workspaceRuntime?.runtimeBaseUrl) {
      manager.loadTree();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceRuntime?.runtimeBaseUrl, fileTreeAdapterKey]);

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: [collectionType],
    onRefresh: manager.loadTree,
  });

  const handleNodeClick = useCallback((node: FileTreeNodeType, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);

    if (node.type === 'file' && modifier === 'none') {
      onSelect({ path: node.path, scope: node.scope || scope });
    }
  }, [manager.state, onSelect, scope]);

  const handleNodeDoubleClick = useCallback((node: FileTreeNodeType) => {
    if (node.type === 'file') {
      onSelect({ path: node.path, scope: node.scope || scope });
    }
  }, [onSelect, scope]);

  const handleContextMenu = useCallback((node: FileTreeNodeType, event: React.MouseEvent) => {
    manager.state.openContextMenu(event.clientX, event.clientY, node);
  }, [manager.state]);

  const handleCreateFile = useCallback(async () => {
    if (isReadOnly) return;
    const contextNode = manager.state.contextMenu?.node;
    let parentPath = '/';
    if (contextNode) {
      if (contextNode.type === 'directory') {
        parentPath = contextNode.path;
      } else {
        parentPath = contextNode.path.split('/').slice(0, -1).join('/') || '/';
      }
    }

    setDialogState({ type: 'create-file', parentPath });
  }, [manager, isReadOnly]);
  const handleCreateFolder = useCallback(async () => {
    if (isReadOnly) return;
    const contextNode = manager.state.contextMenu?.node;
    let parentPath = '/';
    if (contextNode) {
      if (contextNode.type === 'directory') {
        parentPath = contextNode.path;
      } else {
        parentPath = contextNode.path.split('/').slice(0, -1).join('/') || '/';
      }
    }

    setDialogState({ type: 'create-folder', parentPath });
  }, [manager, isReadOnly]);
  const handleUpload = useCallback(() => {
    if (isReadOnly) return;
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
        logger.error('uploadFailed', { collectionType, error });
      }
    };
    input.click();
  }, [isReadOnly, manager, t, collectionType]);
  const handleFilePaste = useCallback(async (files: File[]) => {
    if (isReadOnly || !files || files.length === 0) return;
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
      logger.error('pasteFileFailed', { collectionType, error });
    }
  }, [isReadOnly, manager, t, collectionType]);
  const handleRename = useCallback(async (node: FileTreeNodeType) => {
    if (isReadOnly) return;

    const newName = prompt(t(`workspace.claudeCode.${collectionType}.fileOperations.renamePrompt`, { name: node.name }), node.name);
    if (!newName || newName === node.name) return;

    try {
      const pathParts = node.path.split('/');
      pathParts[pathParts.length - 1] = newName;
      const newPath = pathParts.join('/');

      await manager.operations.renameFile(node.path, newPath);
      await manager.loadTree();
    } catch (error) {
      logger.error('renameFailed', { collectionType, error });
      alert(t(`workspace.claudeCode.${collectionType}.fileOperations.renameFailedAlert`));
    }
  }, [isReadOnly, manager, t, collectionType]);
  const handleRefresh = useCallback(async () => {
    try {
      await manager.loadTree();
    } catch (error) {
      logger.error('refreshFailed', { collectionType, error });
    }
  }, [manager, t, collectionType]);
  const handleBatchDelete = useCallback(async (paths: string[]) => {
    if (isReadOnly) return;
    const nodes: FileTreeNodeType[] = paths.map(path => ({
      id: path,
      name: path.split('/').pop() || path,
      path,
      type: 'file' as const,
      scope: null,
      size: 0,
      updatedAt: new Date().toISOString(),
      depth: 0,
      children: [],
      hasChildren: false,
      extension: null,
      fileType: null,
      metadata: null,
    }));

    setDialogState({ type: 'batch-delete', nodes });
  }, [manager, isReadOnly]);
  const handleScopeChange = (newScope: 'project' | 'user' | 'plugin') => {
    setScope(newScope);
    manager.state.clearSelection();
  };
  const handleDialogCreateFile = useCallback(async (name: string) => {
    if (!dialogState || dialogState.type !== 'create-file') return;

    try {
      const fullPath = dialogState.parentPath === '/'
        ? `/${name}`
        : `${dialogState.parentPath}/${name}`;
      await manager.createFileAndOpen(fullPath, '');
      closeDialog();
    } catch (error) {
      logger.error('createFileFailed', { collectionType, error });
    }
  }, [dialogState, manager, closeDialog, t, collectionType]);

  const handleDialogCreateFolder = useCallback(async (name: string) => {
    if (!dialogState || dialogState.type !== 'create-folder') return;

    try {
      const fullPath = dialogState.parentPath === '/'
        ? `/${name}/.gitkeep`
        : `${dialogState.parentPath}/${name}/.gitkeep`;
      await manager.operations.createFile(fullPath, '');
      await manager.loadTree();
      closeDialog();
    } catch (error) {
      logger.error('createFolderFailed', { collectionType, error });
    }
  }, [dialogState, manager, closeDialog, t, collectionType]);

  const handleDialogRename = useCallback(async (newName: string) => {
    if (!dialogState || dialogState.type !== 'rename') return;

    try {
      await manager.operations.renameFile(dialogState.node.path, newName);
      await manager.loadTree();
      closeDialog();
    } catch (error) {
      logger.error('renameFailed', { collectionType, error });
    }
  }, [dialogState, manager, closeDialog, t, collectionType]);

  const handleDialogDelete = useCallback(async () => {
    if (!dialogState || dialogState.type !== 'delete') return;

    try {
      const isDirectory = dialogState.node.type === 'directory';
      await manager.operations.deleteFile(dialogState.node.path, isDirectory);
      await manager.loadTree();
      closeDialog();
    } catch (error) {
      logger.error('deleteFailed', { collectionType, error });
    }
  }, [dialogState, manager, closeDialog, t, collectionType]);

  const handleDialogBatchDelete = useCallback(async () => {
    if (!dialogState || dialogState.type !== 'batch-delete') return;

    try {
      const paths = dialogState.nodes.map(node => node.path);
      await manager.batchDeleteAndCloseTabs(paths, true);
      manager.state.clearSelection();
      closeDialog();
    } catch (error) {
      logger.error('batchDeleteFailed', { collectionType, error });
    }
  }, [dialogState, manager, closeDialog, t, collectionType]);
  const handleDragStart = useCallback((node: FileTreeNodeType, event: React.DragEvent) => {
    if (isReadOnly) return;
    setDraggingPath(node.path);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', node.path);
  }, [isReadOnly]);
  const handleDragEnd = useCallback(() => {
    setDraggingPath(null);
    setDragOverPath(null);
  }, []);
  const handleDragOver = useCallback((node: FileTreeNodeType, event: React.DragEvent) => {
    if (isReadOnly || node.type !== 'directory') return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    setDragOverPath(node.path);
  }, [isReadOnly]);
  const handleDragLeave = useCallback(() => {
    setDragOverPath(null);
  }, []);
  const handleDrop = useCallback(async (node: FileTreeNodeType, event: React.DragEvent) => {
    if (isReadOnly || node.type !== 'directory') return;

    event.preventDefault();
    event.stopPropagation();

    const sourcePath = event.dataTransfer.getData('text/plain');
    if (!sourcePath || sourcePath === node.path) {
      setDragOverPath(null);
      return;
    }
    if (node.path.startsWith(sourcePath + '/') || node.path === sourcePath) {
      alert(t(`workspace.claudeCode.${collectionType}.fileOperations.moveFolderToSubfolderAlert`));
      setDragOverPath(null);
      return;
    }

    try {
      await manager.operations.moveFile(sourcePath, node.path);
      await manager.loadTree();
      setDragOverPath(null);
      setDraggingPath(null);
    } catch (error) {
      logger.error('moveFailed', { collectionType, error });
      alert(t(`workspace.claudeCode.${collectionType}.fileOperations.moveFailedAlert`));
      setDragOverPath(null);
    }
  }, [isReadOnly, manager, t, collectionType]);
  const handleCopy = useCallback(() => {
    if (!manager.state.contextMenu) return;

    const node = manager.state.contextMenu.node;
    setClipboardItem({
      path: node.path,
      type: node.type,
      scope: node.scope || scope,
    });
    manager.state.closeContextMenu();
  }, [manager, scope]);
  const handlePaste = useCallback(async () => {
    logger.debug('pasteStarted', { clipboardItem, hasContextMenu: !!manager.state.contextMenu });

    if (!clipboardItem || !manager.state.contextMenu) {
      return;
    }

    const targetNode = manager.state.contextMenu.node;
    const targetPath = targetNode.type === 'directory' ? targetNode.path : targetNode.path.split('/').slice(0, -1).join('/');

    logger.debug('pasteTargetPath', { targetPath });

    manager.state.closeContextMenu();

    try {
      const collection = collectionType;
      const copyMethod = collection === 'skills' ? claudeCodeApi.copySkill : claudeCodeApi.copyScript;

      logger.debug('pasteCallApi', {
        collection,
        sourcePath: clipboardItem.path,
        targetPath,
        scope: clipboardItem.scope,
        runtimeBaseUrl: workspaceRuntime?.runtimeBaseUrl
      });

      await copyMethod(
        workspaceRuntime?.runtimeBaseUrl || '',
        workspaceId,
        clipboardItem.path,
        targetPath,
        clipboardItem.scope as 'project' | 'user'
      );

      logger.debug('pasteSuccess');
      await manager.loadTree();

      logger.debug('pasteTreeReloaded');
    } catch (error) {
      logger.error('pasteFailed', { collectionType, error });
      alert(t(`workspace.claudeCode.${collectionType}.fileOperations.pasteFailedAlert`));
    }
  }, [clipboardItem, manager, collectionType, workspaceId, workspaceRuntime, t]);
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
    readOnly: isReadOnly,
    hasClipboard: !isPasteDisabled,
    features: {
      view: isReadOnly,
      upload: !isReadOnly,
      createFile: !isReadOnly,
      createFolder: !isReadOnly,
      copy: !isReadOnly,
      copyPath: !isReadOnly,
      paste: !isReadOnly,
      rename: !isReadOnly,
      delete: !isReadOnly,
    },
    callbacks: {
      onView: (node) => {
        onSelect({ path: node.path, scope: node.scope || scope });
      },
      onUpload: handleUpload,
      onCreateFile: handleCreateFile,
      onCreateFolder: handleCreateFolder,
      onCopy: handleCopy,
      onCopyPath: (path) => {
        navigator.clipboard.writeText(path).then(() => {
          logger.debug('pathCopied', { path });
        }).catch((error) => {
          logger.error('copyPathFailed', { collectionType, error });
        });
      },
      onPaste: handlePaste,
      onRename: (node) => handleRename(node),
      onDelete: (node) => setDialogState({ type: 'delete', node }),
      onClose: manager.state.closeContextMenu,
    },
    t,
  });
  const scopeOptions: ScopeOption[] = useMemo(() => {
    const options: ScopeOption[] = [
      {
        value: 'project',
        label: t(`${i18nPrefix}.scope.project`),
        icon: <FolderGit className="h-3 w-3" />,
      },
      {
        value: 'user',
        label: t(`${i18nPrefix}.scope.user`),
        icon: <User className="h-3 w-3" />,
      },
    ];
    if (collectionType === 'skills') {
      options.push({
        value: 'plugin',
        label: t(`${i18nPrefix}.scope.plugin`),
        icon: <Puzzle className="h-3 w-3" />,
      });
    }

    return options;
  }, [collectionType, t, i18nPrefix]);
  const toolbarContent = useMemo(() => {
    return (
      <FileTreeToolbar
        leftContent={
          <ScopeSelector
            value={scope}
            onChange={handleScopeChange}
            options={scopeOptions}
            label={t(`${i18nPrefix}.scope.label`)}
          />
        }
        rightContent={
          scope === 'plugin' && pluginSkills && pluginSkills.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {t(`${i18nPrefix}.plugin.label`)}
              </span>
              <Select value={selectedPlugin} onValueChange={setSelectedPlugin}>
                <SelectTrigger className="h-7 w-32 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    {t(`${i18nPrefix}.plugin.all`)}
                  </SelectItem>
                  {pluginSkills.map((plugin) => {
                    const pluginKey = `${plugin.pluginName}@${plugin.marketplaceName}:${plugin.skillName}`;
                    return (
                      <SelectItem key={pluginKey} value={pluginKey}>
                        {plugin.pluginName} - {plugin.skillName}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
          )
        }
        onCreateFile={handleCreateFile}
        onCreateFolder={handleCreateFolder}
        onUpload={handleUpload}
        onRefresh={handleRefresh}
        isLoading={manager.state.isLoading}
        isReadOnly={isReadOnly}
      />
    );
  }, [
    scope,
    handleScopeChange,
    scopeOptions,
    t,
    i18nPrefix,
    handleCreateFile,
    handleCreateFolder,
    handleUpload,
    handleRefresh,
    manager.state.isLoading,
    isReadOnly,
    pluginSkills,
    selectedPlugin,
    setSelectedPlugin,
  ]);

  return (
    <div className="flex h-full flex-col border-r border-sidebar-border">
      <StandardFileTreeLayout
        title={t(`${i18nPrefix}.title`)}
        icon={<HeaderIcon className="h-5 w-5 text-sidebar-primary" />}
        isCollapsed={isCollapsed}
        onToggleCollapse={toggleSecondColumn}
        searchValue={manager.state.searchQuery}
        onSearchChange={manager.state.setSearchQuery}
        onSearchClear={manager.state.clearSearch}
        searchPlaceholder={t(`workspace.claudeCode.${collectionType}.searchPlaceholder`)}
        showSearch={!isCollapsed}
        toolbarContent={toolbarContent}
        showToolbar={!isCollapsed}
      >
        {isCollapsed ? (
          <CollapsedSidebarPlaceholder
            icon={HeaderIcon}
            className="text-primary"
            iconClassName="text-primary"
          />
        ) : (
          <>
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
              onCreateFile={handleCreateFile}
              onCreateFolder={handleCreateFolder}
              onUpload={handleUpload}
              onPaste={handleFilePaste}
              onRefresh={handleRefresh}
              onBatchDelete={handleBatchDelete}
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
      <BatchDeleteDialog
        open={dialogState?.type === 'batch-delete'}
        files={dialogState?.type === 'batch-delete' ? dialogState.nodes.map(node => ({
          name: node.name,
          path: node.path,
          type: node.type,
        })) : []}
        onClose={closeDialog}
        onConfirm={handleDialogBatchDelete}
      />
    </div>
  );
};

export default ClaudeCodeFileManager;
