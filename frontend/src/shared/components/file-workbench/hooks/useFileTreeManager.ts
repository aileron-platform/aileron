/**
 * useFileTreeManager Hook
 *
 *
 */

import { useEffect, useCallback, useMemo, useRef, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { FileTreeApiAdapter } from '../services/fileTreeAdapter';

const logger = createLogger('useFileTreeManager');
import { useFileTreeState, type UseFileTreeStateOptions } from './useFileTreeState';
import { useFileOperations, type UseFileOperationsOptions } from './useFileOperations';
import { useFileEditor, type UseFileEditorOptions } from './useFileEditor';
import { computeLoadedChildrenPaths, findNodeByPath } from '../utils/fileTreeUtils';
import type { FileTreeApiConfig, FileTreeNode } from '../types';

const buildApiConfigKey = (apiConfig: FileTreeApiConfig): string =>
  JSON.stringify({
    type: apiConfig.type,
    workspaceId: apiConfig.workspaceId ?? null,
    contextId: apiConfig.contextId ?? null,
    templateId: apiConfig.templateId ?? null,
    knowledgeBaseId: apiConfig.knowledgeBaseId ?? null,
    scope: apiConfig.scope ?? null,
    collection: apiConfig.collection ?? null,
    baseUrl: apiConfig.baseUrl ?? null,
    includeHidden: apiConfig.includeHidden ?? null,
  });

export interface UseFileTreeManagerOptions {
  apiConfig: FileTreeApiConfig;
  
  stateOptions?: Omit<UseFileTreeStateOptions, 'initialNodes'>;
  
  operationsOptions?: Omit<UseFileOperationsOptions, 'apiConfig'>;
  
  editorOptions?: UseFileEditorOptions;
  
  autoLoad?: boolean;
  
  onTreeLoaded?: (nodes: FileTreeNode[]) => void;
  
  onFileSelect?: (node: FileTreeNode) => void;
  
  onFileDoubleClick?: (node: FileTreeNode) => void;
  
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


  const state = useFileTreeState(stateOptions);
  const apiConfigKey = useMemo(() => buildApiConfigKey(apiConfig), [apiConfig]);
  const stableApiConfigRef = useRef(apiConfig);
  const stableApiConfigKeyRef = useRef(apiConfigKey);
  if (stableApiConfigKeyRef.current !== apiConfigKey) {
    stableApiConfigRef.current = apiConfig;
    stableApiConfigKeyRef.current = apiConfigKey;
  }
  const stableApiConfig = stableApiConfigRef.current;
  const latestLoadIdRef = useRef(0);
  const activeApiConfigKeyRef = useRef(apiConfigKey);


  const loadedChildrenPathsRef = useRef<Set<string>>(new Set());
  const [loadingChildrenPaths, setLoadingChildrenPaths] = useState<Set<string>>(new Set());

  useEffect(() => {
    activeApiConfigKeyRef.current = apiConfigKey;
    latestLoadIdRef.current += 1;
  }, [apiConfigKey]);


  const loadTree = useCallback(async () => {
    const requestId = latestLoadIdRef.current + 1;
    latestLoadIdRef.current = requestId;
    const requestApiConfigKey = apiConfigKey;

    logger.debug('loadTree: starting file tree load');
    state.setLoading(true);
    state.setError(null);

    try {
      const adapter = new FileTreeApiAdapter(stableApiConfig);
      logger.debug('loadTree: calling adapter.getTree()');
      const nodes = await adapter.getTree();

      if (
        latestLoadIdRef.current !== requestId ||
        activeApiConfigKeyRef.current !== requestApiConfigKey
      ) {
        logger.debug('loadTree: ignoring stale file tree response', {
          requestId,
          requestApiConfigKey,
          latestLoadId: latestLoadIdRef.current,
          activeApiConfigKey: activeApiConfigKeyRef.current,
        });
        return;
      }

      logger.debug('loadTree: received node count', { count: nodes.length });
      state.setNodes(nodes);


      const newLoadedPaths = computeLoadedChildrenPaths(nodes);
      loadedChildrenPathsRef.current = newLoadedPaths;
      state.syncExpandedWithLoaded(newLoadedPaths);

      logger.debug('loadTree: called state.setNodes()');

      if (onTreeLoaded) {
        onTreeLoaded(nodes);
      }
    } catch (error) {
      if (
        latestLoadIdRef.current !== requestId ||
        activeApiConfigKeyRef.current !== requestApiConfigKey
      ) {
        logger.debug('loadTree: ignoring stale file tree error', {
          requestId,
          requestApiConfigKey,
          latestLoadId: latestLoadIdRef.current,
          activeApiConfigKey: activeApiConfigKeyRef.current,
        });
        return;
      }

      logger.error('loadTree: failed to load file tree', { error });
      const errorMessage = error instanceof Error ? error.message : 'Failed to load file tree';
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
        logger.debug('loadTree: load complete');
      } else {
        logger.debug('loadTree: skipping completion update for stale request', {
          requestId,
          requestApiConfigKey,
          latestLoadId: latestLoadIdRef.current,
          activeApiConfigKey: activeApiConfigKeyRef.current,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    apiConfigKey,
    onError,
    onTreeLoaded,
    stableApiConfig,
    state.setError,
    state.setLoading,
    state.setNodes,
  ]);


  const operations = useFileOperations({
    apiConfig,
    onSuccess: (message) => {
      logger.debug('operation completed successfully', { message });
    },
    onError: (error) => {
      state.setError(error.message);
      if (onError) {
        onError(error);
      }
    },
    onComplete: () => {

      void loadTree();
    },
    ...operationsOptions,
  });


  const editor = useFileEditor({
    onAutoSave: async (path, content) => {
      try {
        await operations.updateFile(path, content);
        editor.saveTab(path);
      } catch (error) {
        logger.error('auto save failed', { error });
      }
    },
    onFileOpen: (node) => {
      if (onFileSelect) {
        onFileSelect(node);
      }
    },
    ...editorOptions,
  });

  /**
   */
  const toggleDirectory = useCallback(async (node: FileTreeNode) => {
    if (node.type !== 'directory') return;

    const { path } = node;


    if (state.expandedIds.has(path)) {
      state.collapseNode(path);
      return;
    }


    if (loadedChildrenPathsRef.current.has(path)) {
      state.expandNode(path);
      return;
    }


    setLoadingChildrenPaths(prev => new Set([...prev, path]));
    try {
      const adapter = new FileTreeApiAdapter(stableApiConfig);
      const children = await adapter.getChildren(path);
      state.updateNode(path, { children });
      loadedChildrenPathsRef.current.add(path);
      state.expandNode(path);
    } catch (error) {
      logger.error('toggleDirectory: failed to lazy-load children', { path, error });

      state.expandNode(path);
      if (onError) {
        onError(error instanceof Error ? error : new Error('Failed to load child directory'));
      }
    } finally {
      setLoadingChildrenPaths(prev => {
        const next = new Set(prev);
        next.delete(path);
        return next;
      });
    }
  }, [state, stableApiConfig, onError]);


  useEffect(() => {
    if (autoLoad) {
      loadTree();
    }
  }, [autoLoad, loadTree]);


  const handleFileSelect = useCallback(async (node: FileTreeNode) => {
    if (node.type === 'file') {

      if (editor.isTabOpen(node.path)) {
        editor.setActiveTab(node.path);
      } else {

        try {
          const content = await operations.readFile(node.path);
          editor.openTab(node, content);
        } catch (error) {
          logger.error('failed to load file', { error });
          if (onError) {
            onError(error instanceof Error ? error : new Error('Failed to load file'));
          }
        }
      }

      if (onFileSelect) {
        onFileSelect(node);
      }
    }
  }, [editor, operations, onFileSelect, onError]);


  const handleFileDoubleClick = useCallback(async (node: FileTreeNode) => {
    if (node.type === 'file') {
      await handleFileSelect(node);

      if (onFileDoubleClick) {
        onFileDoubleClick(node);
      }
    } else {

      state.toggleNode(node.path);
    }
  }, [handleFileSelect, state, onFileDoubleClick]);


  const createFileAndOpen = useCallback(async (path: string, content = '') => {
    const response = await operations.createFile(path, content);
    if (response.success) {

      await loadTree();
      

      const node = state.flatNodes.find(n => n.path === path);
      if (node) {
        editor.openTab(node, content);
      }
    }
    return response;
  }, [operations, loadTree, state.flatNodes, editor]);


  const saveActiveTab = useCallback(async () => {
    if (editor.activeTab) {
      try {
        await operations.updateFile(editor.activeTab.path, editor.activeTab.content);
        editor.saveTab(editor.activeTab.path);
      } catch (error) {
        logger.error('failed to save file', { error });
        if (onError) {
          onError(error instanceof Error ? error : new Error('Failed to save file'));
        }
      }
    }
  }, [editor, operations, onError]);


  const saveAllTabs = useCallback(async () => {
    const modifiedTabs = editor.tabs.filter(tab => tab.isModified);
    
    for (const tab of modifiedTabs) {
      try {
        await operations.updateFile(tab.path, tab.content);
      } catch (error) {
        logger.error('failed to save file', { path: tab.path, error });
      }
    }
    
    editor.saveAllTabs();
  }, [editor, operations]);


  const deleteFileAndCloseTab = useCallback(async (path: string, recursive = false) => {
    const response = await operations.deleteFile(path, recursive);
    if (response.success) {
      editor.closeTabsForPath(path, recursive);
      

      state.removeNode(path);
    }
    return response;
  }, [operations, editor, state]);


  const batchDeleteAndCloseTabs = useCallback(async (paths: string[], recursive = false) => {
    const response = await operations.batchDelete(paths, recursive);
    

    paths.forEach(path => {
      editor.closeTabsForPath(path, recursive);
      state.removeNode(path);
    });
    
    return response;
  }, [operations, editor, state]);


  const renameFileAndUpdateTab = useCallback(async (oldPath: string, newPath: string) => {
    const response = await operations.renameFile(oldPath, newPath);
    if (response.success) {
      editor.remapPath(oldPath, newPath);
      

      await loadTree();
    }
    return response;
  }, [operations, editor, loadTree]);


  const moveFileAndUpdateTabs = useCallback(async (sourcePath: string, targetPath: string) => {
    const response = await operations.moveFile(sourcePath, targetPath);
    if (response.success) {
      editor.remapPath(sourcePath, targetPath);
      await loadTree();
    }
    return response;
  }, [operations, editor, loadTree]);

  return {

    state,
    operations,
    editor,


    loadTree,
    handleFileSelect,
    handleFileDoubleClick,


    toggleDirectory,
    loadingChildrenPaths,


    createFileAndOpen,
    saveActiveTab,
    saveAllTabs,
    deleteFileAndCloseTab,
    batchDeleteAndCloseTabs,
    renameFileAndUpdateTab,
    moveFileAndUpdateTabs,
  };
}
