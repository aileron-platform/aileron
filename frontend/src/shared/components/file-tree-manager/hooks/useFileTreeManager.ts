/**
 * useFileTreeManager Hook
 *
 * 統一檔案樹管理的主 Hook，整合：
 * - useFileTreeState（狀態管理）
 * - useFileOperations（檔案操作）
 * - useFileEditor（編輯器管理）
 *
 * 提供完整的檔案樹管理功能
 */

import { useEffect, useCallback, useMemo, useRef } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useFileTreeManager');
import { useFileTreeState, type UseFileTreeStateOptions } from './useFileTreeState';
import { useFileOperations, type UseFileOperationsOptions } from './useFileOperations';
import { useFileEditor, type UseFileEditorOptions } from './useFileEditor';
import type { FileTreeApiConfig, FileTreeNode } from '../types';

const buildApiConfigKey = (apiConfig: FileTreeApiConfig): string =>
  JSON.stringify({
    type: apiConfig.type,
    workspaceId: apiConfig.workspaceId ?? null,
    contextId: apiConfig.contextId ?? null,
    templateId: apiConfig.templateId ?? null,
    scope: apiConfig.scope ?? null,
    collection: apiConfig.collection ?? null,
    baseUrl: apiConfig.baseUrl ?? null,
  });

export interface UseFileTreeManagerOptions {
  /** API 配置 */
  apiConfig: FileTreeApiConfig;
  
  /** 狀態管理選項 */
  stateOptions?: Omit<UseFileTreeStateOptions, 'initialNodes'>;
  
  /** 檔案操作選項 */
  operationsOptions?: Omit<UseFileOperationsOptions, 'apiConfig'>;
  
  /** 編輯器選項 */
  editorOptions?: UseFileEditorOptions;
  
  /** 是否自動載入檔案樹 */
  autoLoad?: boolean;
  
  /** 檔案樹載入完成回調 */
  onTreeLoaded?: (nodes: FileTreeNode[]) => void;
  
  /** 檔案選擇回調 */
  onFileSelect?: (node: FileTreeNode) => void;
  
  /** 檔案雙擊回調 */
  onFileDoubleClick?: (node: FileTreeNode) => void;
  
  /** 錯誤回調 */
  onError?: (error: Error) => void;
}

export function useFileTreeManager(options: UseFileTreeManagerOptions) {
  const {
    apiConfig,
    stateOptions = {},
    operationsOptions = {},
    editorOptions = {},
    autoLoad = true,
    onTreeLoaded,
    onFileSelect,
    onFileDoubleClick,
    onError,
  } = options;

  // 狀態管理
  const state = useFileTreeState(stateOptions);
  const apiConfigKey = useMemo(() => buildApiConfigKey(apiConfig), [apiConfig]);
  const latestLoadIdRef = useRef(0);
  const activeApiConfigKeyRef = useRef(apiConfigKey);

  useEffect(() => {
    activeApiConfigKeyRef.current = apiConfigKey;
    latestLoadIdRef.current += 1;
  }, [apiConfigKey]);

  // 載入檔案樹 - 需要在 operations 之前定義
  const loadTree = useCallback(async () => {
    const requestId = latestLoadIdRef.current + 1;
    latestLoadIdRef.current = requestId;
    const requestApiConfigKey = apiConfigKey;

    logger.debug('loadTree: 開始載入檔案樹');
    state.setLoading(true);
    state.setError(null);

    try {
      const adapter = new (await import('../services/fileTreeAdapter')).FileTreeApiAdapter(apiConfig);
      logger.debug('loadTree: 調用 adapter.getTree()');
      const nodes = await adapter.getTree();

      if (
        latestLoadIdRef.current !== requestId ||
        activeApiConfigKeyRef.current !== requestApiConfigKey
      ) {
        logger.debug('loadTree: 忽略過期的檔案樹回應', {
          requestId,
          requestApiConfigKey,
          latestLoadId: latestLoadIdRef.current,
          activeApiConfigKey: activeApiConfigKeyRef.current,
        });
        return;
      }

      logger.debug('loadTree: 獲取到節點數量', { count: nodes.length });
      state.setNodes(nodes);
      logger.debug('loadTree: 已調用 state.setNodes()');

      if (onTreeLoaded) {
        onTreeLoaded(nodes);
      }
    } catch (error) {
      if (
        latestLoadIdRef.current !== requestId ||
        activeApiConfigKeyRef.current !== requestApiConfigKey
      ) {
        logger.debug('loadTree: 忽略過期的檔案樹錯誤', {
          requestId,
          requestApiConfigKey,
          latestLoadId: latestLoadIdRef.current,
          activeApiConfigKey: activeApiConfigKeyRef.current,
        });
        return;
      }

      logger.error('loadTree: 載入失敗', { error });
      const errorMessage = error instanceof Error ? error.message : '載入檔案樹失敗';
      state.setError(errorMessage);
      if (onError) {
        onError(error instanceof Error ? error : new Error(errorMessage));
      }
    } finally {
      if (
        latestLoadIdRef.current === requestId &&
        activeApiConfigKeyRef.current === requestApiConfigKey
      ) {
        state.setLoading(false);
        logger.debug('loadTree: 載入完成');
      } else {
        logger.debug('loadTree: 跳過過期請求的完成狀態更新', {
          requestId,
          requestApiConfigKey,
          latestLoadId: latestLoadIdRef.current,
          activeApiConfigKey: activeApiConfigKeyRef.current,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiConfig, apiConfigKey, state]);

  // 檔案操作 - 在 loadTree 之後定義，這樣 onComplete 才能正確引用
  const operations = useFileOperations({
    apiConfig,
    onSuccess: (message) => {
      logger.debug('操作成功', { message });
    },
    onError: (error) => {
      state.setError(error.message);
      if (onError) {
        onError(error);
      }
    },
    onComplete: () => {
      // 操作完成後重新載入檔案樹
      void loadTree();
    },
    ...operationsOptions,
  });

  // 編輯器管理
  const editor = useFileEditor({
    onAutoSave: async (path, content) => {
      try {
        await operations.updateFile(path, content);
        editor.saveTab(path);
      } catch (error) {
        logger.error('自動儲存失敗', { error });
      }
    },
    onFileOpen: (node) => {
      if (onFileSelect) {
        onFileSelect(node);
      }
    },
    ...editorOptions,
  });

  // 自動載入
  useEffect(() => {
    if (autoLoad) {
      loadTree();
    }
  }, [autoLoad, loadTree]);

  // 檔案選擇處理
  const handleFileSelect = useCallback(async (node: FileTreeNode) => {
    if (node.type === 'file') {
      // 如果標籤已開啟，直接切換
      if (editor.isTabOpen(node.path)) {
        editor.setActiveTab(node.path);
      } else {
        // 載入檔案內容並開啟標籤
        try {
          const content = await operations.readFile(node.path);
          editor.openTab(node, content);
        } catch (error) {
          logger.error('載入檔案失敗', { error });
          if (onError) {
            onError(error instanceof Error ? error : new Error('載入檔案失敗'));
          }
        }
      }

      if (onFileSelect) {
        onFileSelect(node);
      }
    }
  }, [editor, operations, onFileSelect, onError]);

  // 檔案雙擊處理
  const handleFileDoubleClick = useCallback(async (node: FileTreeNode) => {
    if (node.type === 'file') {
      await handleFileSelect(node);

      if (onFileDoubleClick) {
        onFileDoubleClick(node);
      }
    } else {
      // 資料夾雙擊切換展開狀態
      state.toggleNode(node.path);
    }
  }, [handleFileSelect, state, onFileDoubleClick]);

  // 建立檔案（帶自動開啟）
  const createFileAndOpen = useCallback(async (path: string, content = '') => {
    const response = await operations.createFile(path, content);
    if (response.success) {
      // 重新載入檔案樹
      await loadTree();
      
      // 開啟新建立的檔案
      const node = state.flatNodes.find(n => n.path === path);
      if (node) {
        editor.openTab(node, content);
      }
    }
    return response;
  }, [operations, loadTree, state.flatNodes, editor]);

  // 儲存當前活動標籤
  const saveActiveTab = useCallback(async () => {
    if (editor.activeTab) {
      try {
        await operations.updateFile(editor.activeTab.path, editor.activeTab.content);
        editor.saveTab(editor.activeTab.path);
      } catch (error) {
        logger.error('儲存檔案失敗', { error });
        if (onError) {
          onError(error instanceof Error ? error : new Error('儲存檔案失敗'));
        }
      }
    }
  }, [editor, operations, onError]);

  // 儲存所有標籤
  const saveAllTabs = useCallback(async () => {
    const modifiedTabs = editor.tabs.filter(tab => tab.isModified);
    
    for (const tab of modifiedTabs) {
      try {
        await operations.updateFile(tab.path, tab.content);
      } catch (error) {
        logger.error('儲存檔案失敗', { path: tab.path, error });
      }
    }
    
    editor.saveAllTabs();
  }, [editor, operations]);

  // 刪除檔案（帶標籤關閉）
  const deleteFileAndCloseTab = useCallback(async (path: string, recursive = false) => {
    const response = await operations.deleteFile(path, recursive);
    if (response.success) {
      // 關閉相關標籤
      if (editor.isTabOpen(path)) {
        editor.closeTab(path);
      }
      
      // 從狀態中移除節點
      state.removeNode(path);
    }
    return response;
  }, [operations, editor, state]);

  // 批次刪除（帶標籤關閉）
  const batchDeleteAndCloseTabs = useCallback(async (paths: string[], recursive = false) => {
    const response = await operations.batchDelete(paths, recursive);
    
    // 關閉所有相關標籤
    paths.forEach(path => {
      if (editor.isTabOpen(path)) {
        editor.closeTab(path);
      }
      state.removeNode(path);
    });
    
    return response;
  }, [operations, editor, state]);

  // 重新命名檔案（帶標籤更新）
  const renameFileAndUpdateTab = useCallback(async (oldPath: string, newPath: string) => {
    const response = await operations.renameFile(oldPath, newPath);
    if (response.success) {
      // 如果標籤開啟，更新標籤路徑
      if (editor.isTabOpen(oldPath)) {
        const tab = editor.getTab(oldPath);
        if (tab) {
          editor.closeTab(oldPath);
          const newNode = { ...tab.node, path: newPath, name: newPath.split('/').pop() || newPath };
          editor.openTab(newNode, tab.content);
        }
      }
      
      // 重新載入檔案樹
      await loadTree();
    }
    return response;
  }, [operations, editor, loadTree]);

  return {
    // 狀態
    state,
    operations,
    editor,

    // 檔案樹操作
    loadTree,
    handleFileSelect,
    handleFileDoubleClick,

    // 增強的檔案操作
    createFileAndOpen,
    saveActiveTab,
    saveAllTabs,
    deleteFileAndCloseTab,
    batchDeleteAndCloseTabs,
    renameFileAndUpdateTab,
  };
}
