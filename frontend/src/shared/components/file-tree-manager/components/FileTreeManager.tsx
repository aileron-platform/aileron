/**
 * FileTreeManager 組件
 *
 * 統一的檔案樹管理組件，整合：
 * - FileTreePanel（左側檔案樹）
 * - FileEditorPanel（右側編輯器）
 * - 完整的檔案管理功能
 */

import React, { useEffect } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('FileTreeManager');
import { useFileTreeManager } from '../hooks/useFileTreeManager';
import { FileTreePanel } from './FileTreePanel';
import { FileEditorPanel } from './FileEditorPanel';
import type { FileTreeManagerProps } from '../types';
import { cn } from '@/shared/utils/cn';

export const FileTreeManager: React.FC<FileTreeManagerProps> = ({
  apiConfig,
  features = {},
  className,
  height = '100%',
  onFileSelect,
  onFileDoubleClick,
  onFilesChange,
  onError,
  renderToolbar,
  renderEditor,
}) => {
  const {
    enableMultiSelect = true,
    enableDragDrop = true,
    enableUpload = true,
    // enableDownload = true,  // 未來實作下載功能時使用
    // enableRename = true,    // 未來實作重新命名功能時使用
    enableDelete = true,
    enableCreate = true,
    enableContextMenu = true,
    enableSearch = true,
    enableEditor = true,
    readOnly = false,
  } = features;

  // 使用主 Hook
  const manager = useFileTreeManager({
    apiConfig,
    stateOptions: {
      enableMultiSelect,
    },
    operationsOptions: {
      onError,
    },
    editorOptions: {
      onFileOpen: onFileSelect,
    },
    autoLoad: true,
    onError,
  });

  // 監聽檔案變更
  useEffect(() => {
    if (onFilesChange) {
      onFilesChange(manager.state.nodes);
    }
  }, [manager.state.nodes, onFilesChange]);

  // 處理節點點擊
  const handleNodeClick = (node: any, modifier: any) => {
    manager.state.selectNodeWithModifier(node.path, modifier);
    
    // 如果是檔案且無修飾鍵，開啟檔案
    if (node.type === 'file' && modifier === 'none') {
      manager.handleFileSelect(node);
    }
  };

  // 處理節點雙擊
  const handleNodeDoubleClick = (node: any) => {
    manager.handleFileDoubleClick(node);
    
    if (onFileDoubleClick) {
      onFileDoubleClick(node);
    }
  };

  // 處理右鍵選單
  const handleContextMenu = (node: any, event: React.MouseEvent) => {
    if (!enableContextMenu) return;
    
    manager.state.openContextMenu(event.clientX, event.clientY, node);
  };

  // 處理新增檔案
  const handleCreateFile = async () => {
    if (!enableCreate || readOnly) return;
    
    const fileName = prompt('請輸入檔案名稱：');
    if (!fileName) return;
    
    try {
      await manager.createFileAndOpen(fileName, '');
    } catch (error) {
      logger.error('建立檔案失敗', { error });
    }
  };

  // 處理新增資料夾
  const handleCreateFolder = async () => {
    if (!enableCreate || readOnly) return;

    const folderName = prompt('請輸入資料夾名稱：');
    if (!folderName) return;

    try {
      await manager.operations.createDirectory(folderName);
      await manager.loadTree();
    } catch (error) {
      logger.error('建立資料夾失敗', { error });
    }
  };

  // 處理上傳
  const handleUpload = () => {
    if (!enableUpload || readOnly) return;

    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.onchange = async (e) => {
      const files = (e.target as HTMLInputElement).files;
      if (!files || files.length === 0) return;

      try {
        await manager.operations.uploadFiles({
          targetPath: '/',
          files: Array.from(files),
        });
        await manager.loadTree();
      } catch (error) {
        logger.error('上傳檔案失敗', { error });
      }
    };
    input.click();
  };

  // 處理重新整理
  const handleRefresh = () => {
    manager.loadTree();
  };

  // 處理批次刪除
  const handleBatchDelete = async (paths: string[]) => {
    if (!enableDelete || readOnly) return;

    const confirmed = confirm(`確定要刪除 ${paths.length} 個項目嗎？`);
    if (!confirmed) return;

    try {
      await manager.batchDeleteAndCloseTabs(paths, true);
      manager.state.clearSelection();
    } catch (error) {
      logger.error('批次刪除失敗', { error });
    }
  };

  // 處理儲存
  const handleSave = async (path: string, content: string) => {
    if (readOnly) return;

    try {
      await manager.operations.updateFile(path, content);
    } catch (error) {
      logger.error('儲存檔案失敗', { error });
    }
  };

  return (
    <div
      className={cn('flex border rounded-lg overflow-hidden bg-background', className)}
      style={{ height }}
    >
      {/* 左側檔案樹面板 */}
      <div className="w-64 border-r">
        <FileTreePanel
          state={manager.state}
          onNodeClick={handleNodeClick}
          onNodeDoubleClick={handleNodeDoubleClick}
          onContextMenu={handleContextMenu}
          onCreateFile={handleCreateFile}
          onCreateFolder={handleCreateFolder}
          onUpload={handleUpload}
          onRefresh={handleRefresh}
          onBatchDelete={handleBatchDelete}
          enableSearch={enableSearch}
          enableToolbar={!readOnly}
          enableMultiSelectBar={enableMultiSelect && !readOnly}
          enableDragDrop={enableDragDrop && !readOnly}
          renderToolbar={renderToolbar}
        />
      </div>

      {/* 右側編輯器面板 */}
      {enableEditor && (
        <div className="flex-1">
          <FileEditorPanel
            editor={manager.editor}
            onSave={handleSave}
            renderEditor={renderEditor}
          />
        </div>
      )}
    </div>
  );
};

