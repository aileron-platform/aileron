/**
 * 模板檔案管理組件
 *
 * 使用統一的 sidebar shell + 檔案樹組件，讓模板中心不同區塊的左側欄節奏一致
 */

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
import SectionSidebarShell from '@/shared/components/template/SectionSidebarShell';

const logger = createLogger('TemplateFileManager');
import { useFileTreeManager } from '@/shared/components/file-tree-manager/hooks/useFileTreeManager';
import { useFileOperationsWithDialog } from '@/shared/components/file-tree-manager/hooks/useFileOperationsWithDialog';
import {
  FileTreePanel,
  FileTreeContextMenu,
  useFileTreeContextMenu,
  type FileTreeApiConfig,
  type FileTreeNode as FileTreeNodeType,
  type SelectionModifier,
} from '@/shared/components/file-tree-manager';
import {
  FileCreateDialog,
  FileRenameDialog,
  FileDeleteDialog,
  BatchDeleteDialog,
} from '@/shared/components/file-tree-manager/components';
import { useI18n } from '@/shared/hooks/useI18n';
import { FileEditor } from '@/shared/components/file-editors';
import { apiClient } from '@/shared/api/apiClient';

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

const TemplateFileManager: React.FC<TemplateFileManagerProps> = ({
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

  // 如果沒有 templateId，顯示空狀態
  if (!templateId) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center text-muted-foreground">
          <p className="text-sm">{t('template.editor.fileManagement.viewer.noTemplate')}</p>
        </div>
      </div>
    );
  }

  // 構建 API 配置
  const apiConfig: FileTreeApiConfig = useMemo(() => ({
    type: 'template',
    templateId,
    scope: basePath,
  }), [templateId, basePath]);

  // 使用 FileTreeManager Hook
  const manager = useFileTreeManager({
    apiConfig,
    stateOptions: {
      enableMultiSelect: true,
    },
    autoLoad: false,  // 關閉自動載入，改用 useEffect 控制
  });

  // 使用 useEffect 控制載入時機，只在 apiConfig 變更時載入
  useEffect(() => {
    if (templateId && basePath) {
      manager.loadTree();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiConfig]);

  // 使用 useCallback 穩定 onContentChange 回調
  const handleContentChange = useCallback((content: string) => {
    if (manager.editor.activeTab) {
      manager.editor.updateContent(manager.editor.activeTab.path, content);
    }
  }, []);

  // 使用 Dialog Hook 管理檔案操作
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
      // 資料夾需要使用 recursive=true
      const isDirectory = node?.type === 'directory';
      await manager.operations.deleteFile(path, isDirectory);
      await manager.loadTree();
    },
    onBatchDelete: async (paths) => {
      await manager.batchDeleteAndCloseTabs(paths, true);
      manager.state.clearSelection();
    },
  });

  // 處理節點點擊
  const handleNodeClick = useCallback((node: FileTreeNodeType, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(node.path, modifier);

    // 如果是檔案且無修飾鍵，開啟檔案
    if (node.type === 'file' && modifier === 'none') {
      manager.handleFileSelect(node);
    }
  }, [manager]);

  // 處理節點雙擊
  const handleNodeDoubleClick = useCallback((node: FileTreeNodeType) => {
    manager.handleFileDoubleClick(node);
  }, [manager]);

  // 處理右鍵選單
  const handleContextMenu = useCallback((node: FileTreeNodeType, event: React.MouseEvent) => {
    manager.state.openContextMenu(event.clientX, event.clientY, node);
  }, [manager]);

  // 處理上傳
  const handleUpload = useCallback(() => {
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
        logger.error('上傳檔案失敗', { error });
      }
    };
    input.click();
  }, [manager]);

  // 處理檔案貼上（從剪貼簿）
  const handleFilePaste = useCallback(async (files: File[]) => {
    if (!files || files.length === 0) return;

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
      logger.error('貼上檔案失敗', { error });
    }
  }, [manager]);

  // 處理重新整理
  const handleRefresh = useCallback(() => {
    manager.loadTree();
  }, [manager]);

  // 處理儲存
  const handleSaveFile = useCallback(async (content: string) => {
    if (!manager.editor.activeTab) return;

    await manager.operations.updateFile(manager.editor.activeTab.path, content);
    manager.editor.updateContent(manager.editor.activeTab.path, content);
    manager.editor.saveTab(manager.editor.activeTab.path);
  }, [manager]);

  // 拖曳處理
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
      // 構建完整的目標路徑：目標資料夾路徑 + 檔案名稱
      const fileName = draggingPath.split('/').pop() || draggingPath;
      const targetPath = `${targetNode.path}/${fileName}`;

      await manager.operations.moveFile(draggingPath, targetPath);
      await manager.loadTree();
    } catch (error) {
      logger.error('移動檔案失敗', { error });
    } finally {
      setDragOverPath(null);
      setDraggingPath(null);
    }
  }, [draggingPath, manager]);

  // 複製處理
  const handleCopy = useCallback(() => {
    if (!manager.state.contextMenu) return;

    const node = manager.state.contextMenu.node;
    setClipboardItem({
      path: node.path,
      type: node.type,
    });
    manager.state.closeContextMenu();
  }, [manager]);

  // 貼上處理
  const handlePaste = useCallback(async () => {
    if (!clipboardItem || !manager.state.contextMenu || !templateId) return;

    const targetNode = manager.state.contextMenu.node;
    const targetPath = targetNode.type === 'directory' ? targetNode.path : targetNode.path.split('/').slice(0, -1).join('/');

    manager.state.closeContextMenu();

    try {
      // 調用 Template API 的複製端點
      await apiClient.post(`/templates/${templateId}/files/copy?scope=${basePath}&source_path=${encodeURIComponent(clipboardItem.path)}&dest_path=${encodeURIComponent(targetPath)}`);

      // 重新載入檔案樹
      await manager.loadTree();
    } catch (error) {
      logger.error('貼上失敗', { error });
      alert(t('template.editor.fileManagement.toasts.paste.error.description'));
    }
  }, [clipboardItem, manager, templateId, basePath]);

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

  // 使用統一的右鍵選單 Hook
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
          logger.debug('路徑已複製', { path });
        }).catch((error) => {
          logger.error('複製路徑失敗', { error });
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
      {/* 左側檔案樹面板 */}
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
              // 簡化：直接使用 paths 創建臨時節點
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

        {/* 右鍵選單 */}
        <FileTreeContextMenu
          contextMenu={manager.state.contextMenu}
          items={contextMenuItems}
          onClose={manager.state.closeContextMenu}
        />
      </div>

      {/* 右側編輯器面板 */}
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

      {/* Dialog 組件 */}
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

export default TemplateFileManager;
