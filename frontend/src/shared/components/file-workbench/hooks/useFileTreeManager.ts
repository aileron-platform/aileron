import { useEffect, useCallback, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createLogger } from '@/shared/services/logger';
import { getFileOperationResponseRevision } from '../adapters/fileResponseAdapter';
import { isImageFile } from '../model/fileTypeUtils';

const logger = createLogger('useFileTreeManager');
import { useFileTreeState, type UseFileTreeStateOptions } from './useFileTreeState';
import { useFileOperations, type UseFileOperationsOptions } from './useFileOperations';
import { useFileEditor, type UseFileEditorOptions } from './useFileEditor';
import {
  computeLoadedChildrenPaths,
  flattenTree,
  findNodeByPath,
  isDepthTruncatedDirectory,
  sortTreeNodes,
} from '../model/fileTreeModel';
import {
  FileTreeAsyncCoordinator,
  isStaleFileTreeRequestError,
  serializeFileTreeResourceIdentity,
  StaleFileTreeRequestError,
  type FileTreeAsyncRequest,
  type FileTreeResourceIdentity,
} from '../model/fileTreeAsyncCoordinator';
import type { FileTreeDataAdapter, FileTreeNode } from '../types';

const EXPANDED_PATHS_STORAGE_PREFIX = 'fileTree.expandedPaths.v1';

const getExpandedPathsStorageKey = (identityKey: string) => (
  `${EXPANDED_PATHS_STORAGE_PREFIX}:${encodeURIComponent(identityKey)}`
);

const readPersistedExpandedPaths = (identityKey: string): string[] => {
  if (typeof window === 'undefined') return [];

  const storageKey = getExpandedPathsStorageKey(identityKey);
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
    logger.warn('Failed to read persisted expanded file tree paths', { identityKey, error });
    window.localStorage.removeItem(storageKey);
    return [];
  }
};

const writePersistedExpandedPaths = (identityKey: string, expandedPaths: Set<string>) => {
  if (typeof window === 'undefined') return;

  const storageKey = getExpandedPathsStorageKey(identityKey);
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(Array.from(expandedPaths).sort()));
  } catch (error) {
    logger.warn('Failed to persist expanded file tree paths', { identityKey, error });
  }
};

const restoreExpandedNodes = async (
  nodes: FileTreeNode[],
  expandedPaths: Set<string>,
  adapter: FileTreeDataAdapter,
  assertCurrent: () => void,
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
        assertCurrent();
      } catch (error) {
        assertCurrent();
        logger.warn('Failed to restore expanded file tree directory', { path: node.path, error });
      }
    }

    restoredNodes.push({
      ...node,
      children: children
        ? await restoreExpandedNodes(children, expandedPaths, adapter, assertCurrent)
        : children,
    });
  }

  return sortTreeNodes(restoredNodes);
};

export interface UseFileTreeManagerOptions {
  adapter: FileTreeDataAdapter;
  resourceIdentity: FileTreeResourceIdentity;
  
  stateOptions?: Omit<UseFileTreeStateOptions, 'initialNodes'>;
  
  operationsOptions?: Omit<UseFileOperationsOptions, 'adapter' | 'resourceGeneration'>;
  
  editorOptions?: UseFileEditorOptions;
  
  autoLoad?: boolean;
  
  onTreeLoaded?: (nodes: FileTreeNode[]) => void;
  
  onFileSelect?: (node: FileTreeNode) => void;
  
  onFileDoubleClick?: (node: FileTreeNode) => void;
  
  onError?: (error: Error) => void;
}

interface FileTreeRenderResource {
  adapter: FileTreeDataAdapter;
  coordinator: FileTreeAsyncCoordinator;
  identityKey: string;
}

export function useFileTreeManager(options: UseFileTreeManagerOptions) {
  const {
    adapter,
    resourceIdentity,
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
  const {
    replaceExpandedIds,
    setError: setTreeError,
    setLoading: setTreeLoading,
    setNodes: setTreeNodes,
  } = state;
  const nextIdentityKey = serializeFileTreeResourceIdentity(resourceIdentity);
  const committedIdentityKeyRef = useRef(nextIdentityKey);
  const committedResourceRef = useRef<FileTreeRenderResource | null>(null);
  if (committedResourceRef.current === null) {
    committedResourceRef.current = {
      adapter,
      coordinator: new FileTreeAsyncCoordinator(resourceIdentity),
      identityKey: nextIdentityKey,
    };
  }
  const renderResource = useMemo<FileTreeRenderResource>(() => {
    const committedResource = committedResourceRef.current!;
    if (committedResource.identityKey === nextIdentityKey) {
      return committedResource;
    }
    return {
      adapter,
      coordinator: new FileTreeAsyncCoordinator(
        resourceIdentity,
        committedResource.coordinator.identityGeneration + 1,
      ),
      identityKey: nextIdentityKey,
    };
  }, [adapter, nextIdentityKey, resourceIdentity]);
  const { coordinator, identityKey } = renderResource;
  const identityGeneration = coordinator.identityGeneration;
  const stableAdapter = renderResource.adapter;
  const callbacksRef = useRef({ onError, onTreeLoaded });
  const hasLoadedTreeRef = useRef(false);

  useEffect(() => {
    callbacksRef.current = { onError, onTreeLoaded };
  }, [onError, onTreeLoaded]);


  const loadedChildrenPathsRef = useRef<Set<string>>(new Set());
  const [loadingChildrenPaths, setLoadingChildrenPaths] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!hasLoadedTreeRef.current) return;
    writePersistedExpandedPaths(identityKey, state.expandedIds);
  }, [identityKey, state.expandedIds]);

  const isCommittedRequestCurrent = useCallback((
    request: FileTreeAsyncRequest,
  ): boolean => (
    committedIdentityKeyRef.current === request.identityKey
    && coordinator.isCurrent(request)
  ), [coordinator]);

  const assertCommittedRequestCurrent = useCallback((
    request: FileTreeAsyncRequest,
  ): void => {
    if (!isCommittedRequestCurrent(request)) {
      throw new StaleFileTreeRequestError();
    }
  }, [isCommittedRequestCurrent]);


  const loadTree = useCallback(async () => {
    if (committedIdentityKeyRef.current !== identityKey) {
      return;
    }
    let request: FileTreeAsyncRequest;
    try {
      request = coordinator.beginRequestForGeneration(identityGeneration, 'tree');
    } catch (error) {
      if (!isStaleFileTreeRequestError(error)) throw error;
      return;
    }

    logger.debug('loadTree: starting file tree load', {
      identityKey: request.identityKey,
      requestId: request.requestId,
    });
    setTreeLoading(true);
    setTreeError(null);

    try {
      logger.debug('loadTree: calling adapter.getTree()');
      const persistedExpandedPaths = readPersistedExpandedPaths(request.identityKey);
      const persistedExpandedPathSet = new Set(persistedExpandedPaths);
      const nodes = await restoreExpandedNodes(
        await stableAdapter.getTree(),
        persistedExpandedPathSet,
        stableAdapter,
        () => assertCommittedRequestCurrent(request),
      );
      assertCommittedRequestCurrent(request);

      logger.debug('loadTree: received node count', { count: nodes.length });
      setTreeNodes(nodes);


      const newLoadedPaths = computeLoadedChildrenPaths(nodes);
      loadedChildrenPathsRef.current = newLoadedPaths;
      replaceExpandedIds(persistedExpandedPaths.filter((path) => newLoadedPaths.has(path)));
      hasLoadedTreeRef.current = true;

      logger.debug('loadTree: called state.setNodes()');

      if (callbacksRef.current.onTreeLoaded) {
        callbacksRef.current.onTreeLoaded(nodes);
      }
      return flattenTree(nodes);
    } catch (error) {
      if (!isCommittedRequestCurrent(request) || isStaleFileTreeRequestError(error)) {
        logger.debug('loadTree: ignoring stale file tree error', {
          identityKey: request.identityKey,
          requestId: request.requestId,
        });
        return;
      }

      logger.error('loadTree: failed to load file tree', { error });
      const errorMessage = error instanceof Error ? error.message : 'Failed to load file tree';
      setTreeError(errorMessage);
      if (callbacksRef.current.onError) {
        callbacksRef.current.onError(error instanceof Error ? error : new Error(errorMessage));
      }
      return undefined;
    } finally {
      const settlement = coordinator.finishRequest(request);
      if (
        committedIdentityKeyRef.current === request.identityKey
        && settlement.isCurrentChannelIdle
      ) {
        setTreeLoading(false);
        logger.debug('loadTree: load complete');
      } else {
        logger.debug('loadTree: load settled, other loads still in flight', {
          identityKey: request.identityKey,
          requestId: request.requestId,
          inFlight: settlement.currentChannelRequestCount,
        });
      }
    }
  }, [
    coordinator,
    assertCommittedRequestCurrent,
    identityGeneration,
    identityKey,
    isCommittedRequestCurrent,
    replaceExpandedIds,
    setTreeError,
    setTreeLoading,
    setTreeNodes,
    stableAdapter,
  ]);


  const guardedAdapter = useMemo(() => {
    const guard = async <T,>(
      channel: string,
      operation: () => Promise<T>,
    ): Promise<T> => {
      if (committedIdentityKeyRef.current !== identityKey) {
        throw new StaleFileTreeRequestError();
      }
      const request = coordinator.beginRequestForGeneration(identityGeneration, channel);
      try {
        const result = await operation();
        assertCommittedRequestCurrent(request);
        return result;
      } catch (error) {
        assertCommittedRequestCurrent(request);
        throw error;
      } finally {
        coordinator.finishRequest(request);
      }
    };

    return {
      getTree: () => guard('tree', () => stableAdapter.getTree()),
      getChildren: (path) => guard(
        `children:${path}`,
        () => stableAdapter.getChildren(path),
      ),
      getContent: (path) => guard(
        `content:${path}`,
        () => stableAdapter.getContent(path),
      ),
      create: (request) => guard(
        `create:${request.path}`,
        () => stableAdapter.create(request),
      ),
      update: (path, content, updateOptions) => guard(
        `update:${path}`,
        () => stableAdapter.update(path, content, updateOptions),
      ),
      delete: (path, recursive) => guard(
        `delete:${path}`,
        () => stableAdapter.delete(path, recursive),
      ),
      batchDelete: (request) => guard(
        `batch-delete:${[...request.paths].sort().join('\u0000')}`,
        () => stableAdapter.batchDelete(request),
      ),
      move: (sourcePath, targetPath) => guard(
        `move:${sourcePath}`,
        () => stableAdapter.move(sourcePath, targetPath),
      ),
      upload: (uploadOptions) => guard(
        `upload:${uploadOptions.targetPath}`,
        () => stableAdapter.upload(uploadOptions),
      ),
      ...(stableAdapter.extractArchive
        ? {
            extractArchive: (extractOptions) => guard(
              `extract:${extractOptions.archivePath}`,
              () => stableAdapter.extractArchive!(extractOptions),
            ),
          }
        : {}),
      download: (downloadOptions) => guard(
        `download:${downloadOptions.path}`,
        () => stableAdapter.download(downloadOptions),
      ),
    } satisfies FileTreeDataAdapter;
  }, [
    assertCommittedRequestCurrent,
    coordinator,
    identityGeneration,
    identityKey,
    stableAdapter,
  ]);

  const operations = useFileOperations({
    adapter: guardedAdapter,
    resourceGeneration: identityGeneration,
    onSuccess: (message) => {
      if (committedIdentityKeyRef.current !== identityKey) return;
      logger.debug('operation completed successfully', { message });
      operationsOptions.onSuccess?.(message);
    },
    onError: (error) => {
      if (
        coordinator.identityGeneration !== identityGeneration
        || committedIdentityKeyRef.current !== identityKey
        || isStaleFileTreeRequestError(error)
      ) {
        return;
      }
      state.setError(error.message);
      operationsOptions.onError?.(error);
      if (onError) {
        onError(error);
      }
    },
    onComplete: (settlement) => {
      if (
        coordinator.identityGeneration !== identityGeneration
        || committedIdentityKeyRef.current !== identityKey
        || isStaleFileTreeRequestError(settlement.error)
      ) {
        return;
      }
      operationsOptions.onComplete?.(settlement);
    },
  });


  const editor = useFileEditor({
    onAutoSave: async (path, content, revision) => {
      try {
        const response = await operations.updateFile(
          path,
          content,
          { revision: revision },
        );
        editor.saveTab(path, content, getFileOperationResponseRevision(response), {
          clearAutoSaveTimer: false,
        });
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

  useLayoutEffect(() => {
    const previousIdentityKey = committedResourceRef.current?.identityKey;
    committedIdentityKeyRef.current = identityKey;
    committedResourceRef.current = renderResource;
    if (previousIdentityKey === identityKey) return;
    hasLoadedTreeRef.current = false;
    loadedChildrenPathsRef.current = new Set();
    setLoadingChildrenPaths(new Set());
    state.resetState();
    editor.closeAllTabs();
  }, [editor, identityKey, renderResource, state]);

  const toggleDirectory = useCallback(async (node: FileTreeNode) => {
    if (committedIdentityKeyRef.current !== identityKey) return;
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


    const channel = `children:${path}`;
    let request: FileTreeAsyncRequest;
    try {
      request = coordinator.beginRequestForGeneration(identityGeneration, channel);
    } catch (error) {
      if (!isStaleFileTreeRequestError(error)) throw error;
      return;
    }

    setLoadingChildrenPaths(prev => new Set([...prev, path]));
    try {
      const children = await stableAdapter.getChildren(path);
      assertCommittedRequestCurrent(request);
      state.updateNode(path, { children });
      loadedChildrenPathsRef.current.add(path);
      state.expandNode(path);
    } catch (error) {
      if (!isCommittedRequestCurrent(request) || isStaleFileTreeRequestError(error)) return;
      logger.error('toggleDirectory: failed to lazy-load children', { path, error });

      state.expandNode(path);
      if (onError) {
        onError(error instanceof Error ? error : new Error('Failed to load child directory'));
      }
    } finally {
      const settlement = coordinator.finishRequest(request);
      if (
        committedIdentityKeyRef.current === request.identityKey
        && settlement.isCurrentChannelIdle
      ) {
        setLoadingChildrenPaths(prev => {
          const next = new Set(prev);
          next.delete(path);
          return next;
        });
      }
    }
  }, [
    assertCommittedRequestCurrent,
    coordinator,
    identityGeneration,
    identityKey,
    isCommittedRequestCurrent,
    onError,
    stableAdapter,
    state,
  ]);


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

        if (isImageFile(node.name)) {
          editor.openTab(node, '', undefined);
        } else {
          try {
            const fileContent = await operations.readFile(node.path);
            if (fileContent.readable === false) {
              editor.openTab(node, fileContent.content, fileContent.revision, {
                readable: false,
                unreadableReason: fileContent.unreadableReason,
              });
            } else {
              editor.openTab(node, fileContent.content, fileContent.revision);
            }
          } catch (error) {
            if (isStaleFileTreeRequestError(error)) return;
            logger.error('failed to load file', { error });
            if (onError) {
              onError(error instanceof Error ? error : new Error('Failed to load file'));
            }
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
    const tab = editor.activeTab;
    if (tab) {
      try {
        const response = await operations.updateFile(
          tab.path,
          tab.content,
          { revision: tab.revision },
        );
        editor.saveTab(tab.path, tab.content, getFileOperationResponseRevision(response));
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
        const response = await operations.updateFile(
          tab.path,
          tab.content,
          { revision: tab.revision },
        );
        editor.saveTab(tab.path, tab.content, getFileOperationResponseRevision(response));
      } catch (error) {
        logger.error('failed to save file', { path: tab.path, error });
      }
    }
  }, [editor, operations]);


  const deleteFileAndCloseTab = useCallback(async (path: string, recursive = false) => {
    const response = await operations.deleteFile(path, recursive);
    if (response.success) {
      editor.closeTabsForPath(path, recursive);
      await loadTree();
    }
    return response;
  }, [operations, editor, loadTree]);


  const batchDeleteAndCloseTabs = useCallback(async (paths: string[], recursive = false) => {
    const response = await operations.batchDelete(paths, recursive);

    if (response.successCount > 0) {
      response.deleted.forEach(path => {
        editor.closeTabsForPath(path, recursive);
      });
      await loadTree();
    }

    return response;
  }, [operations, editor, loadTree]);

  const reloadFileTab = useCallback(async (path: string) => {
    const tab = editor.getTab(path);
    if (!tab) return false;

    try {
      const fileContent = await operations.readFile(path);
      editor.openTab(tab.node, fileContent.content, fileContent.revision, {
        readable: fileContent.readable,
        unreadableReason: fileContent.unreadableReason,
      });
      return true;
    } catch (error) {
      editor.closeTabsForPath(path);
      logger.error('failed to reload file', { path, error });
      return false;
    }
  }, [editor, operations]);


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
    reloadFileTab,
    renameFileAndUpdateTab,
    moveFileAndUpdateTabs,
  };
}
