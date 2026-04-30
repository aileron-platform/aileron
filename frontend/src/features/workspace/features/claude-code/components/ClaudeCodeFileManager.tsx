/**
 * Claude Code 檔案管理組件
 *
 * 使用統一的檔案樹組件來管理 Claude Code 的 skills 和 scripts 檔案
 * 支援 project、user、plugin 三種 scope
 */

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
import type { FileTreeApiConfig, FileTreeNode as FileTreeNodeType, SelectionModifier } from '@/shared/components/file-workbench';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import { FolderGit, User, Puzzle } from 'lucide-react';
import { claudeCodeApi } from '../services/claudeCodeApi';
import { useQuery } from '@tanstack/react-query';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import { CollapsedSidebarPlaceholder } from '@/shared/components/layout/CollapsedSidebarPlaceholder';
import { CLAUDE_CODE_ICONS } from '../../../components/navigation-constants';
import { useWorkspaceTemplateInstallRefresh } from '@/features/workspace/events/templateInstallCoordinator';

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

  // Dialog 狀態管理
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

  // 根據 collectionType 設置翻譯前綴和 icon
  const i18nPrefix = `workspace.claudeCode.${collectionType}`;
  const HeaderIcon = CLAUDE_CODE_ICONS[collectionType];
  const isCollapsed = layout.secondColumnCollapsed;

  // 使用 useQuery 獲取 plugin skills 資訊（僅在 skills 且 scope 為 plugin 時）
  const { data: pluginSkillsData } = useQuery({
    queryKey: ['plugin-skills', workspaceId],
    queryFn: () => claudeCodeApi.listPluginSkills(workspaceRuntime?.runtimeBaseUrl || '', workspaceId),
    enabled: !!workspaceId && !!workspaceRuntime?.runtimeBaseUrl && collectionType === 'skills' && scope === 'plugin',
  });

  const pluginSkills = pluginSkillsData?.plugins || [];

  // 構建 API 配置
  const apiConfig: FileTreeApiConfig = useMemo(() => ({
    type: 'claude-code' as const,
    workspaceId,
    scope,
    collection: collectionType, // 傳遞 collection 類型
    baseUrl: workspaceRuntime?.runtimeBaseUrl, // 使用 workspace runtime 的 baseUrl
  }), [workspaceId, scope, collectionType, workspaceRuntime?.runtimeBaseUrl]);

  // 判斷是否為唯讀模式（plugin scope 是唯讀的）
  const isReadOnly = scope === 'plugin';

  // 使用 FileTreeManager Hook
  const manager = useFileTreeManager({
    apiConfig,
    stateOptions: {
      enableMultiSelect: !isReadOnly,
    },
    autoLoad: false, // 手動控制載入時機
  });

  // 當 runtimeBaseUrl 或 apiConfig 變更時，重新載入檔案樹
  useEffect(() => {
    if (workspaceRuntime?.runtimeBaseUrl) {
      manager.loadTree();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceRuntime?.runtimeBaseUrl, apiConfig]);

  useWorkspaceTemplateInstallRefresh({
    workspaceId,
    features: [collectionType],
    onRefresh: manager.loadTree,
  });

  // 處理節點點擊
  const handleNodeClick = useCallback((node: FileTreeNodeType, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);

    // 如果是檔案且無修飾鍵，通知父組件
    if (node.type === 'file' && modifier === 'none') {
      onSelect({ path: node.path, scope: node.scope || scope });
    }
  }, [manager.state, onSelect, scope]);

  // 處理節點雙擊
  const handleNodeDoubleClick = useCallback((node: FileTreeNodeType) => {
    if (node.type === 'file') {
      onSelect({ path: node.path, scope: node.scope || scope });
    }
  }, [onSelect, scope]);

  // 處理右鍵選單
  const handleContextMenu = useCallback((node: FileTreeNodeType, event: React.MouseEvent) => {
    manager.state.openContextMenu(event.clientX, event.clientY, node);
  }, [manager.state]);

  // 處理新增檔案
  const handleCreateFile = useCallback(async () => {
    if (isReadOnly) return;

    // 取得當前右鍵選單的節點
    const contextNode = manager.state.contextMenu?.node;
    let parentPath = '/';

    // 如果右鍵點擊的是資料夾，則在該資料夾內創建檔案
    if (contextNode) {
      if (contextNode.type === 'directory') {
        parentPath = contextNode.path;
      } else {
        // 如果是檔案，則在同一層級創建（取得父目錄）
        parentPath = contextNode.path.split('/').slice(0, -1).join('/') || '/';
      }
    }

    setDialogState({ type: 'create-file', parentPath });
  }, [manager, isReadOnly]);

  // 處理新增資料夾
  const handleCreateFolder = useCallback(async () => {
    if (isReadOnly) return;

    // 取得當前右鍵選單的節點
    const contextNode = manager.state.contextMenu?.node;
    let parentPath = '/';

    // 如果右鍵點擊的是資料夾，則在該資料夾內創建
    if (contextNode) {
      if (contextNode.type === 'directory') {
        parentPath = contextNode.path;
      } else {
        // 如果是檔案，則在同一層級創建（取得父目錄）
        parentPath = contextNode.path.split('/').slice(0, -1).join('/') || '/';
      }
    }

    setDialogState({ type: 'create-folder', parentPath });
  }, [manager, isReadOnly]);

  // 處理上傳
  const handleUpload = useCallback(() => {
    if (isReadOnly) return;

    // 獲取當前選中的資料夾路徑（如果有右鍵選單，使用右鍵選單的節點）
    // 注意：使用空字串 '' 而不是 '/' 來表示根目錄，避免 Path 處理問題
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

  // 處理檔案貼上（從剪貼簿）
  const handleFilePaste = useCallback(async (files: File[]) => {
    if (isReadOnly || !files || files.length === 0) return;

    // 獲取目標路徑（如果有選中的資料夾，使用該資料夾；否則使用根目錄）
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

  // 處理重新命名
  const handleRename = useCallback(async (node: FileTreeNodeType) => {
    if (isReadOnly) return;

    const newName = prompt(t(`workspace.claudeCode.${collectionType}.fileOperations.renamePrompt`, { name: node.name }), node.name);
    if (!newName || newName === node.name) return;

    try {
      // 計算新路徑
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

  // 處理重新整理
  const handleRefresh = useCallback(async () => {
    try {
      await manager.loadTree();
    } catch (error) {
      logger.error('refreshFailed', { collectionType, error });
    }
  }, [manager, t, collectionType]);

  // 處理批次刪除
  const handleBatchDelete = useCallback(async (paths: string[]) => {
    if (isReadOnly) return;

    // 構建節點列表用於 Dialog
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

  // 處理 scope 變更
  const handleScopeChange = (newScope: 'project' | 'user' | 'plugin') => {
    setScope(newScope);
    // 切換 scope 時清除選擇
    manager.state.clearSelection();
  };

  // Dialog 處理函數
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

  // 處理拖曳開始
  const handleDragStart = useCallback((node: FileTreeNodeType, event: React.DragEvent) => {
    if (isReadOnly) return;
    setDraggingPath(node.path);
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', node.path);
  }, [isReadOnly]);

  // 處理拖曳結束
  const handleDragEnd = useCallback(() => {
    setDraggingPath(null);
    setDragOverPath(null);
  }, []);

  // 處理拖曳經過
  const handleDragOver = useCallback((node: FileTreeNodeType, event: React.DragEvent) => {
    if (isReadOnly || node.type !== 'directory') return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    setDragOverPath(node.path);
  }, [isReadOnly]);

  // 處理拖曳離開
  const handleDragLeave = useCallback(() => {
    setDragOverPath(null);
  }, []);

  // 處理放置
  const handleDrop = useCallback(async (node: FileTreeNodeType, event: React.DragEvent) => {
    if (isReadOnly || node.type !== 'directory') return;

    event.preventDefault();
    event.stopPropagation();

    const sourcePath = event.dataTransfer.getData('text/plain');
    if (!sourcePath || sourcePath === node.path) {
      setDragOverPath(null);
      return;
    }

    // 檢查是否拖曳到自己的子目錄
    // 正確邏輯：目標路徑不能是源路徑的子目錄
    // 例如：不能將 /a 移動到 /a/b，但可以將 /a/b/c 移動到 /a
    if (node.path.startsWith(sourcePath + '/') || node.path === sourcePath) {
      alert(t(`workspace.claudeCode.${collectionType}.fileOperations.moveFolderToSubfolderAlert`));
      setDragOverPath(null);
      return;
    }

    try {
      // 執行移動操作
      await manager.operations.moveFile(sourcePath, node.path);

      // 重新載入檔案樹
      await manager.loadTree();

      // 清除拖曳狀態
      setDragOverPath(null);
      setDraggingPath(null);
    } catch (error) {
      logger.error('moveFailed', { collectionType, error });
      alert(t(`workspace.claudeCode.${collectionType}.fileOperations.moveFailedAlert`));
      setDragOverPath(null);
    }
  }, [isReadOnly, manager, t, collectionType]);

  // 複製處理
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

  // 貼上處理
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
      // 使用 claudeCodeApi 調用複製 API
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

      // 重新載入檔案樹
      await manager.loadTree();

      logger.debug('pasteTreeReloaded');
    } catch (error) {
      logger.error('pasteFailed', { collectionType, error });
      alert(t(`workspace.claudeCode.${collectionType}.fileOperations.pasteFailedAlert`));
    }
  }, [clipboardItem, manager, collectionType, workspaceId, workspaceRuntime, t]);

  // 判斷是否可以貼上
  const isPasteDisabled = useMemo(() => {
    if (!clipboardItem || !manager.state.contextMenu) return true;

    const targetNode = manager.state.contextMenu.node;
    const isDirectoryTarget = targetNode.type === 'directory';

    // 只能貼到資料夾
    if (!isDirectoryTarget) return true;

    // 不能貼到自己
    if (clipboardItem.path === targetNode.path) return true;

    // 不能貼到自己的子目錄
    if (clipboardItem.type === 'directory' && targetNode.path.startsWith(clipboardItem.path + '/')) {
      return true;
    }

    return false;
  }, [clipboardItem, manager.state.contextMenu]);

  // 右鍵選單項目
  // 使用統一的右鍵選單 Hook
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

  // Scope 選項配置
  const scopeOptions: ScopeOption[] = useMemo(() => {
    const options: ScopeOption[] = [
      {
        value: 'project',
        label: t(`${i18nPrefix}.scope.project`, { defaultValue: 'Project' }),
        icon: <FolderGit className="h-3 w-3" />,
      },
      {
        value: 'user',
        label: t(`${i18nPrefix}.scope.user`, { defaultValue: 'User' }),
        icon: <User className="h-3 w-3" />,
      },
    ];

    // Skills 才有 Plugin scope
    if (collectionType === 'skills') {
      options.push({
        value: 'plugin',
        label: t(`${i18nPrefix}.scope.plugin`, { defaultValue: 'Plugin' }),
        icon: <Puzzle className="h-3 w-3" />,
      });
    }

    return options;
  }, [collectionType, t, i18nPrefix]);

  // 工具列內容
  const toolbarContent = useMemo(() => {
    return (
      <FileTreeToolbar
        leftContent={
          <ScopeSelector
            value={scope}
            onChange={handleScopeChange}
            options={scopeOptions}
            label={t(`${i18nPrefix}.scope.label`, { defaultValue: 'Scope:' })}
          />
        }
        rightContent={
          /* 第二行：Plugin 選擇器（僅在 plugin scope 時顯示） */
          scope === 'plugin' && pluginSkills && pluginSkills.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {t(`${i18nPrefix}.plugin.label`, { defaultValue: 'Plugin:' })}
              </span>
              <Select value={selectedPlugin} onValueChange={setSelectedPlugin}>
                <SelectTrigger className="h-7 w-32 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">
                    {t(`${i18nPrefix}.plugin.all`, { defaultValue: 'All Plugins' })}
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
        title={t(`${i18nPrefix}.title`, { defaultValue: collectionType === 'skills' ? 'Skills' : 'Scripts' })}
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

            {/* 右鍵選單 */}
            <FileTreeContextMenu
              contextMenu={manager.state.contextMenu}
              items={contextMenuItems}
              onClose={manager.state.closeContextMenu}
            />
          </>
        )}
      </StandardFileTreeLayout>

      {/* Dialog 組件 */}
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
