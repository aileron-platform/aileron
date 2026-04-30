import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FolderGit, Puzzle, User, Wand2, ScrollText } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import {
  FileCreateDialog,
  FileDeleteDialog,
  FileRenameDialog,
  FileTreeContextMenu,
  FileTreePanel,
  FileTreeToolbar,
  ScopeSelector,
  StandardFileTreeLayout,
  useFileTreeContextMenu,
  useFileTreeManager,
  type FileTreeNode as FileTreeNodeType,
  type ScopeOption,
  type SelectionModifier,
} from '@/shared/components/file-workbench';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { createAgentFileTreeDataAdapter } from '../adapters/agentFileTreeDataAdapter';
import { createAgentSettingsApi } from '../services/agentSettingsApi';
import type { AgentFileCollection, AgentSelectedFile, AgentToolConfig } from '../types';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';

const logger = createLogger('AgentFileManager');

interface AgentFileManagerProps {
  config: AgentToolConfig;
  collectionType: AgentFileCollection;
  onSelect: (file: AgentSelectedFile) => void;
  workspaceId: string;
}

type DialogState =
  | { type: 'create-file'; parentPath: string }
  | { type: 'create-folder'; parentPath: string }
  | { type: 'rename'; node: FileTreeNodeType }
  | { type: 'delete'; node: FileTreeNodeType }
  | null;

const collectionIcons = {
  skills: Wand2,
  scripts: ScrollText,
};

const scopeIcons = {
  project: FolderGit,
  user: User,
  plugin: Puzzle,
};

const getParentPath = (node: FileTreeNodeType | null | undefined) => {
  if (!node) return '/';
  if (node.type === 'directory') return node.path;
  return node.path.split('/').slice(0, -1).join('/') || '/';
};

const buildChildPath = (parentPath: string, name: string) =>
  parentPath === '/' ? `/${name}` : `${parentPath}/${name}`;

const AgentFileManager: React.FC<AgentFileManagerProps> = ({
  config,
  collectionType,
  onSelect,
  workspaceId,
}) => {
  const { t } = useI18n();
  const { layout, toggleSecondColumn, workspaceRuntime } = useWorkspace();
  const capability = config.capabilities[collectionType];
  const scopes = capability?.scopes.length ? capability.scopes : ['project', 'user'];
  const [scope, setScope] = useState<AgentSelectedFile['scope']>(scopes[0] ?? 'project');
  const [selectedPlugin, setSelectedPlugin] = useState('all');
  const [dialogState, setDialogState] = useState<DialogState>(null);
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);
  const [draggingPath, setDraggingPath] = useState<string | null>(null);

  const i18nPrefix = `${config.i18nNamespace}.${collectionType}`;
  const HeaderIcon = collectionIcons[collectionType];
  const isCollapsed = layout.secondColumnCollapsed;
  const readOnlyScopes = capability?.readOnlyScopes ?? [];
  const isReadOnly = readOnlyScopes.includes(scope);
  const api = useMemo(() => createAgentSettingsApi(config.apiPathPrefix), [config.apiPathPrefix]);

  const { data: pluginSkillsData } = useQuery({
    queryKey: ['agent-plugin-skills', config.apiPathPrefix, workspaceId],
    queryFn: () => api.listPluginSkills(workspaceRuntime.runtimeBaseUrl || '', workspaceId),
    enabled: Boolean(workspaceId && workspaceRuntime.runtimeBaseUrl && collectionType === 'skills' && scope === 'plugin' && capability?.supportsPlugin),
  });

  const pluginSkills = pluginSkillsData?.plugins ?? [];

  const fileTreeAdapter = useMemo(() => createAgentFileTreeDataAdapter({
    workspaceId,
    apiPrefix: config.apiPathPrefix,
    scope,
    collection: collectionType,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
  }), [collectionType, config.apiPathPrefix, scope, workspaceId, workspaceRuntime.runtimeBaseUrl]);

  const fileTreeAdapterKey = useMemo(
    () => JSON.stringify({
      workspaceId,
      apiPrefix: config.apiPathPrefix,
      scope,
      collection: collectionType,
      runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl ?? null,
    }),
    [collectionType, config.apiPathPrefix, scope, workspaceId, workspaceRuntime.runtimeBaseUrl],
  );

  const manager = useFileTreeManager({
    adapter: fileTreeAdapter,
    adapterKey: fileTreeAdapterKey,
    stateOptions: { enableMultiSelect: !isReadOnly },
    autoLoad: false,
  });
  const loadTree = manager.loadTree;

  useEffect(() => {
    if (workspaceRuntime.runtimeBaseUrl) {
      void loadTree();
    }
  }, [fileTreeAdapterKey, loadTree, workspaceRuntime.runtimeBaseUrl]);

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: [collectionType],
    onRefresh: loadTree,
  });

  const closeDialog = useCallback(() => setDialogState(null), []);

  const handleSelectNode = useCallback((node: FileTreeNodeType, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file' && modifier === 'none') {
      onSelect({ path: node.path, scope: (node.scope as AgentSelectedFile['scope'] | null) || scope });
    }
  }, [manager.state, onSelect, scope]);

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
      logger.error('refreshFailed', { collectionType, apiPrefix: config.apiPathPrefix, error });
    }
  }, [collectionType, config.apiPathPrefix, loadTree]);

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
        logger.error('uploadFailed', { collectionType, apiPrefix: config.apiPathPrefix, error });
      }
    };
    input.click();
  }, [collectionType, config.apiPathPrefix, isReadOnly, loadTree, manager.operations, manager.state.contextMenu?.node]);

  const handleDialogCreateFile = useCallback(async (name: string) => {
    if (dialogState?.type !== 'create-file') return;
    try {
      await manager.createFileAndOpen(buildChildPath(dialogState.parentPath, name), '');
      closeDialog();
    } catch (error) {
      logger.error('createFileFailed', { collectionType, apiPrefix: config.apiPathPrefix, error });
    }
  }, [closeDialog, collectionType, config.apiPathPrefix, dialogState, manager]);

  const handleDialogCreateFolder = useCallback(async (name: string) => {
    if (dialogState?.type !== 'create-folder') return;
    try {
      await manager.operations.createFile(`${buildChildPath(dialogState.parentPath, name)}/.gitkeep`, '');
      await loadTree();
      closeDialog();
    } catch (error) {
      logger.error('createFolderFailed', { collectionType, apiPrefix: config.apiPathPrefix, error });
    }
  }, [closeDialog, collectionType, config.apiPathPrefix, dialogState, loadTree, manager.operations]);

  const handleDialogRename = useCallback(async (newName: string) => {
    if (dialogState?.type !== 'rename') return;
    try {
      await manager.operations.renameFile(dialogState.node.path, newName);
      await loadTree();
      closeDialog();
    } catch (error) {
      logger.error('renameFailed', { collectionType, apiPrefix: config.apiPathPrefix, error });
    }
  }, [closeDialog, collectionType, config.apiPathPrefix, dialogState, loadTree, manager.operations]);

  const handleDialogDelete = useCallback(async () => {
    if (dialogState?.type !== 'delete') return;
    try {
      await manager.operations.deleteFile(dialogState.node.path, dialogState.node.type === 'directory');
      await loadTree();
      closeDialog();
    } catch (error) {
      logger.error('deleteFailed', { collectionType, apiPrefix: config.apiPathPrefix, error });
    }
  }, [closeDialog, collectionType, config.apiPathPrefix, dialogState, loadTree, manager.operations]);

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
      logger.error('moveFailed', { collectionType, apiPrefix: config.apiPathPrefix, error });
    } finally {
      setDragOverPath(null);
      setDraggingPath(null);
    }
  }, [collectionType, config.apiPathPrefix, isReadOnly, loadTree, manager.operations]);

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
      onView: (node) => onSelect({ path: node.path, scope: (node.scope as AgentSelectedFile['scope'] | null) || scope }),
      onUpload: handleUpload,
      onCreateFile: handleCreateFile,
      onCreateFolder: handleCreateFolder,
      onCopyPath: (path) => {
        void navigator.clipboard.writeText(path).catch((error) => {
          logger.error('copyPathFailed', { collectionType, apiPrefix: config.apiPathPrefix, error });
        });
      },
      onRename: (node) => setDialogState({ type: 'rename', node }),
      onDelete: (node) => setDialogState({ type: 'delete', node }),
      onClose: manager.state.closeContextMenu,
    },
    t,
  });

  const scopeOptions: ScopeOption[] = useMemo(() => scopes.map((scopeValue) => {
    const Icon = scopeIcons[scopeValue] ?? FolderGit;
    return {
      value: scopeValue,
      label: t(`${i18nPrefix}.scope.${scopeValue}`),
      icon: <Icon className="h-3 w-3" />,
    };
  }), [i18nPrefix, scopes, t]);

  const toolbarContent = (
    <FileTreeToolbar
      leftContent={
        <ScopeSelector
          value={scope}
          onChange={(value) => {
            setScope(value as AgentSelectedFile['scope']);
            manager.state.clearSelection();
          }}
          options={scopeOptions}
          label={t(`${i18nPrefix}.scope.label`)}
        />
      }
      rightContent={
        scope === 'plugin' && pluginSkills.length > 0 ? (
          <div className="flex items-center gap-2">
            <span className="whitespace-nowrap text-xs text-muted-foreground">
              {t(`${i18nPrefix}.plugin.label`)}
            </span>
            <Select value={selectedPlugin} onValueChange={setSelectedPlugin}>
              <SelectTrigger className="h-7 w-32 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t(`${i18nPrefix}.plugin.all`)}</SelectItem>
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
        ) : null
      }
      onCreateFile={handleCreateFile}
      onCreateFolder={handleCreateFolder}
      onUpload={handleUpload}
      onRefresh={handleRefresh}
      isLoading={manager.state.isLoading}
      isReadOnly={isReadOnly}
    />
  );

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
        searchPlaceholder={t(`${i18nPrefix}.searchPlaceholder`)}
        showSearch={!isCollapsed}
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
                  onSelect({ path: node.path, scope: (node.scope as AgentSelectedFile['scope'] | null) || scope });
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

export default AgentFileManager;
