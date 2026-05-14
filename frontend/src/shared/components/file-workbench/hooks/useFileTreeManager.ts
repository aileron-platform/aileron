import { useEffect, useCallback, useRef, useState } from 'react';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useFileTreeManager');
import { useFileTreeState, type UseFileTreeStateOptions } from './useFileTreeState';
import { useFileOperations, type UseFileOperationsOptions } from './useFileOperations';
import { useFileEditor, type UseFileEditorOptions } from './useFileEditor';
import {
  computeLoadedChildrenPaths,
  findNodeByPath,
  isDepthTruncatedDirectory,
  sortTreeNodes,
} from '../utils/fileTreeUtils';
import type { FileTreeDataAdapter, FileTreeNode } from '../types';

const EXPANDED_PATHS_STORAGE_PREFIX = 'fileTree.expandedPaths.v1';

const getExpandedPathsStorageKey = (adapterKey: string) => (
  `${EXPANDED_PATHS_STORAGE_PREFIX}:${encodeURIComponent(adapterKey)}`
);

const readPersistedExpandedPaths = (adapterKey: string): string[] => {
  if (typeof window === 'undefined') return [];

  const storageKey = getExpandedPathsStorageKey(adapterKey);
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return [];

    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      window.localStorage.removeItem(storageKey);
      return [];
    }

    return parsed.filter((path): path is string => typeof path === 'string' && path.length > 0);
  } catch (error) {
    logger.warn('Failed to read persisted expanded file tree paths', { adapterKey, error });
    window.localStorage.removeItem(storageKey);
    return [];
  }
};

const writePersistedExpandedPaths = (adapterKey: string, expandedPaths: Set<string>) => {
  if (typeof window === 'undefined') return;

  const storageKey = getExpandedPathsStorageKey(adapterKey);
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(Array.from(expandedPaths).sort()));
  } catch (error) {
    logger.warn('Failed to persist expanded file tree paths', { adapterKey, error });
  }
};

const restoreExpandedNodes = async (
  nodes: FileTreeNode[],
  expandedPaths: Set<string>,
  adapter: FileTreeDataAdapter,
): Promise<FileTreeNode[]> => {
  const restoredNodes: FileTreeNode[] = [];

  for (const node of nodes) {
    if (node.type !== 'directory') {
      restoredNodes.push(node);
      continue;
    }

    let children = node.children;

    const needsLoad =
      children === undefined ||
      isDepthTruncatedDirectory(node);
    if (expandedPaths.has(node.path) && needsLoad && node.hasChildren !== false) {
      try {
        children = await adapter.getChildren(node.path);
      } catch (error) {
        logger.warn('Failed to restore expanded file tree directory', { path: node.path, error });
      }
    }

    restoredNodes.push({
      ...node,
      children: children ? await restoreExpandedNodes(children, expandedPaths, adapter) : children,
    });
  }

  return sortTreeNodes(restoredNodes);
};

export interface UseFileTreeManagerOptions {
  adapter: FileTreeDataAdapter;
  adapterKey: string;
  
  stateOptions?: Omit<UseFileTreeStateOptions, 'initialNodes'>;
  
  operationsOptions?: Omit<UseFileOperationsOptions, 'adapter'>;
  
  editorOptions?: UseFileEditorOptions;
  
  autoLoad?: boolean;
  
  onTreeLoaded?: (nodes: FileTreeNode[]) => void;
  
  onFileSelect?: (node: FileTreeNode) => void;
  
  onFileDoubleClick?: (node: FileTreeNode) => void;
  
  onError?: (error: Error) => void;
}

export function useFileTreeManager(options: UseFileTreeManagerOptions) {
  const {
    adapter,
    adapterKey,
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
  const stableAdapterRef = useRef(adapter);
  const stableAdapterKeyRef = useRef(adapterKey);
  if (stableAdapterKeyRef.current !== adapterKey) {
    stableAdapterRef.current = adapter;
    stableAdapterKeyRef.current = adapterKey;
  }
  const stableAdapter = stableAdapterRef.current;
  const latestLoadIdRef = useRef(0);
  const activeAdapterKeyRef = useRef(adapterKey);
  const hasLoadedTreeRef = useRef(false);


  const loadedChildrenPathsRef = useRef<Set<string>>(new Set());
  const [loadingChildrenPaths, setLoadingChildrenPaths] = useState<Set<string>>(new Set());

  useEffect(() => {
    activeAdapterKeyRef.current = adapterKey;
    latestLoadIdRef.current += 1;
    hasLoadedTreeRef.current = false;
  }, [adapterKey]);

  useEffect(() => {
    if (!hasLoadedTreeRef.current) return;
    writePersistedExpandedPaths(adapterKey, state.expandedIds);
  }, [adapterKey, state.expandedIds]);


  const loadTree = useCallback(async () => {
    const requestId = latestLoadIdRef.current + 1;
    latestLoadIdRef.current = requestId;
    const requestAdapterKey = adapterKey;

    logger.debug('loadTree: starting file tree load');
    state.setLoading(true);
    state.setError(null);

    try {
      logger.debug('loadTree: calling adapter.getTree()');
      const persistedExpandedPaths = readPersistedExpandedPaths(requestAdapterKey);
      const persistedExpandedPathSet = new Set(persistedExpandedPaths);
      const nodes = await restoreExpandedNodes(
        await stableAdapter.getTree(),
        persistedExpandedPathSet,
        stableAdapter,
      );

      if (
        latestLoadIdRef.current !== requestId ||
        activeAdapterKeyRef.current !== requestAdapterKey
      ) {
        logger.debug('loadTree: ignoring stale file tree response', {
          requestId,
          requestAdapterKey,
          latestLoadId: latestLoadIdRef.current,
          activeAdapterKey: activeAdapterKeyRef.current,
        });
        return;
      }

      logger.debug('loadTree: received node count', { count: nodes.length });
      state.setNodes(nodes);


      const newLoadedPaths = computeLoadedChildrenPaths(nodes);
      loadedChildrenPathsRef.current = newLoadedPaths;
      state.replaceExpandedIds(persistedExpandedPaths.filter((path) => newLoadedPaths.has(path)));
      hasLoadedTreeRef.current = true;

      logger.debug('loadTree: called state.setNodes()');

      if (onTreeLoaded) {
        onTreeLoaded(nodes);
      }
    } catch (error) {
      if (
        latestLoadIdRef.current !== requestId ||
        activeAdapterKeyRef.current !== requestAdapterKey
      ) {
        logger.debug('loadTree: ignoring stale file tree error', {
          requestId,
          requestAdapterKey,
          latestLoadId: latestLoadIdRef.current,
          activeAdapterKey: activeAdapterKeyRef.current,
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
        activeAdapterKeyRef.current === requestAdapterKey
      ) {
        state.setLoading(false);
        logger.debug('loadTree: load complete');
      } else {
        logger.debug('loadTree: skipping completion update for stale request', {
          requestId,
          requestAdapterKey,
          latestLoadId: latestLoadIdRef.current,
          activeAdapterKey: activeAdapterKeyRef.current,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    adapterKey,
    onError,
    onTreeLoaded,
    stableAdapter,
    state.setError,
    state.setLoading,
    state.setNodes,
    state.replaceExpandedIds,
  ]);


  const operations = useFileOperations({
    adapter: stableAdapter,
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
      const children = await stableAdapter.getChildren(path);
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
  }, [state, stableAdapter, onError]);


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
      await toggleDirectory(node);
    }
  }, [handleFileSelect, onFileDoubleClick, toggleDirectory]);


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
