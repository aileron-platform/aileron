/**
 * useFileTreeState Hook
 * 
 */

import { useState, useCallback, useMemo } from 'react';
import type {
  FileTreeNode,
  SelectionModifier,
  ContextMenuState,
} from '../types';
import {
  findNodeByPath,
  filterNodesBySearch,
  flattenTree,
  getDescendantPaths,
  getAllFileNodes,
  sortNodes,
} from '../model/fileTreeModel';

/**
 */
function getVisibleNodes(
  nodes: FileTreeNode[],
  expandedIds: Set<string>
): FileTreeNode[] {
  const visible: FileTreeNode[] = [];

  function traverse(nodeList: FileTreeNode[]) {
    for (const node of nodeList) {
      visible.push(node);
      if (node.type === 'directory' && node.children && expandedIds.has(node.path)) {
        traverse(node.children);
      }
    }
  }

  traverse(nodes);
  return visible;
}

/**
 */
function calculateRangeSelection(
  visibleNodes: FileTreeNode[],
  startPath: string,
  endPath: string
): string[] {
  const startIndex = visibleNodes.findIndex(n => n.path === startPath);
  const endIndex = visibleNodes.findIndex(n => n.path === endPath);

  if (startIndex === -1 || endIndex === -1) {
    return [endPath];
  }

  const [from, to] = startIndex <= endIndex
    ? [startIndex, endIndex]
    : [endIndex, startIndex];

  return visibleNodes.slice(from, to + 1).map(n => n.path);
}

export interface UseFileTreeStateOptions {
  initialNodes?: FileTreeNode[];
  initialExpandedIds?: string[];
  initialSelectedId?: string;
  enableMultiSelect?: boolean;
}

export interface UseFileTreeStateReturn {

  nodes: FileTreeNode[];
  selectedId: string | null;
  selectedIds: Set<string>;
  lastSelectedId: string | null;
  expandedIds: Set<string>;
  isLoading: boolean;
  error: string | null;
  searchQuery: string;
  contextMenu: ContextMenuState | null;


  visibleNodes: FileTreeNode[];
  filteredNodes: FileTreeNode[];
  flatNodes: FileTreeNode[];
  selectedNodes: FileTreeNode[];
  hasSelection: boolean;
  isSearching: boolean;


  setNodes: (nodes: FileTreeNode[]) => void;
  updateNode: (path: string, updates: Partial<FileTreeNode>) => void;
  removeNode: (path: string) => void;
  addNode: (parentPath: string | null, node: FileTreeNode) => void;
  resetState: () => void;


  selectNode: (path: string) => void;
  selectNodeWithModifier: (path: string, modifier: SelectionModifier) => void;
  selectAll: () => void;
  clearSelection: () => void;
  isNodeSelected: (path: string) => boolean;
  isNodeMultiSelected: (path: string) => boolean;


  expandNode: (path: string) => void;
  collapseNode: (path: string) => void;
  toggleNode: (path: string) => void;
  expandAll: () => void;
  collapseAll: () => void;
  isNodeExpanded: (path: string) => boolean;
  syncExpandedWithLoaded: (loadedPaths: Set<string>) => void;
  replaceExpandedIds: (paths: Iterable<string>) => void;


  setSearchQuery: (query: string) => void;
  clearSearch: () => void;


  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;


  openContextMenu: (x: number, y: number, node: FileTreeNode) => void;
  closeContextMenu: () => void;
}

export function useFileTreeState(
  options: UseFileTreeStateOptions = {}
): UseFileTreeStateReturn {
  const {
    initialNodes = [],
    initialExpandedIds = [],
    initialSelectedId = null,
    enableMultiSelect = true,
  } = options;


  const [nodes, setNodes] = useState<FileTreeNode[]>(initialNodes);
  const [selectedId, setSelectedId] = useState<string | null>(initialSelectedId);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [lastSelectedId, setLastSelectedId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set(initialExpandedIds));
  const [isLoading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);


  const visibleNodes = useMemo(
    () => getVisibleNodes(nodes, expandedIds),
    [nodes, expandedIds]
  );

  const filteredNodes = useMemo(
    () => searchQuery ? filterNodesBySearch(nodes, searchQuery) : nodes,
    [nodes, searchQuery]
  );

  const flatNodes = useMemo(() => flattenTree(nodes), [nodes]);

  const selectedNodes = useMemo(
    () => Array.from(selectedIds).map(path => findNodeByPath(nodes, path)).filter(Boolean) as FileTreeNode[],
    [nodes, selectedIds]
  );

  const hasSelection = selectedIds.size > 0;
  const isSearching = searchQuery.trim().length > 0;


  const updateNode = useCallback((path: string, updates: Partial<FileTreeNode>) => {
    setNodes(prevNodes => {
      const updateInTree = (nodeList: FileTreeNode[]): FileTreeNode[] => {
        return nodeList.map(node => {
          if (node.path === path) {
            return { ...node, ...updates };
          }
          if (node.children) {
            return { ...node, children: updateInTree(node.children) };
          }
          return node;
        });
      };
      return updateInTree(prevNodes);
    });
  }, []);

  const removeNode = useCallback((path: string) => {
    setNodes(prevNodes => {
      const removeFromTree = (nodeList: FileTreeNode[]): FileTreeNode[] => {
        return nodeList
          .filter(node => node.path !== path)
          .map(node => (
            node.children
              ? { ...node, children: removeFromTree(node.children) }
              : node
          ));
      };
      return removeFromTree(prevNodes);
    });


    setSelectedIds(prev => {
      const next = new Set(prev);
      next.delete(path);
      return next;
    });
    if (selectedId === path) {
      setSelectedId(null);
    }
  }, [selectedId]);

  const addNode = useCallback((parentPath: string | null, node: FileTreeNode) => {
    setNodes(prevNodes => {
      if (!parentPath) {

        return sortNodes([...prevNodes, node]);
      }

      const addToTree = (nodeList: FileTreeNode[]): FileTreeNode[] => {
        return nodeList.map(n => {
          if (n.path === parentPath) {
            const children = sortNodes([...(n.children || []), node]);
            return { ...n, children };
          }
          if (n.children) {
            return { ...n, children: addToTree(n.children) };
          }
          return n;
        });
      };
      return addToTree(prevNodes);
    });
  }, []);

  const resetState = useCallback(() => {
    setNodes([]);
    setSelectedId(null);
    setSelectedIds(new Set());
    setLastSelectedId(null);
    setExpandedIds(new Set());
    setLoading(false);
    setError(null);
    setSearchQuery('');
    setContextMenu(null);
  }, []);


  const selectNode = useCallback((path: string) => {
    setSelectedId(path);
    setSelectedIds(new Set([path]));
    setLastSelectedId(path);
  }, []);

  const selectNodeWithModifier = useCallback((path: string, modifier: SelectionModifier) => {

    if (!enableMultiSelect || modifier === 'none') {
      const node = findNodeByPath(nodes, path);

      if (node?.type === 'file') {
        selectNode(path);
      }
      return;
    }

    if (modifier === 'ctrl') {

      const node = findNodeByPath(nodes, path);
      const newSelected = new Set(selectedIds);

      if (node?.type === 'directory') {

        const descendantPaths = getDescendantPaths(node);
        const isCurrentlySelected = newSelected.has(path);

        if (isCurrentlySelected) {
          descendantPaths.forEach(p => newSelected.delete(p));
        } else {
          descendantPaths.forEach(p => newSelected.add(p));
        }
      } else {

        if (newSelected.has(path)) {
          newSelected.delete(path);
        } else {
          newSelected.add(path);
        }
      }

      setSelectedIds(newSelected);
      setSelectedId(path);
      setLastSelectedId(path);
    } else if (modifier === 'shift') {

      if (lastSelectedId) {
        const rangeFiles = calculateRangeSelection(visibleNodes, lastSelectedId, path);


        const allPaths = new Set<string>();
        for (const nodePath of rangeFiles) {
          const node = findNodeByPath(nodes, nodePath);
          if (node) {
            const descendantPaths = getDescendantPaths(node);
            descendantPaths.forEach(p => allPaths.add(p));
          }
        }

        setSelectedIds(allPaths);
        setSelectedId(path);
        setLastSelectedId(path);
      } else {
        selectNode(path);
      }
    }
  }, [enableMultiSelect, nodes, selectedIds, lastSelectedId, visibleNodes, selectNode]);

  const selectAll = useCallback(() => {
    const allFileNodes = getAllFileNodes(nodes);
    const allPaths = allFileNodes.map(n => n.path);
    setSelectedIds(new Set(allPaths));
  }, [nodes]);

  const clearSelection = useCallback(() => {
    setSelectedId(null);
    setSelectedIds(new Set());
    setLastSelectedId(null);
  }, []);

  const isNodeSelected = useCallback((path: string) => selectedId === path, [selectedId]);
  const isNodeMultiSelected = useCallback((path: string) => selectedIds.has(path), [selectedIds]);


  const expandNode = useCallback((path: string) => {
    setExpandedIds(prev => new Set([...prev, path]));
  }, []);

  const collapseNode = useCallback((path: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      next.delete(path);
      return next;
    });
  }, []);

  const toggleNode = useCallback((path: string) => {
    setExpandedIds(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const expandAll = useCallback(() => {
    const allDirPaths = flatNodes
      .filter(n => n.type === 'directory')
      .map(n => n.path);
    setExpandedIds(new Set(allDirPaths));
  }, [flatNodes]);

  const collapseAll = useCallback(() => {
    setExpandedIds(new Set());
  }, []);

  const isNodeExpanded = useCallback((path: string) => expandedIds.has(path), [expandedIds]);

  const syncExpandedWithLoaded = useCallback((loadedPaths: Set<string>) => {
    setExpandedIds(prev => {
      const next = new Set<string>();
      for (const id of prev) {
        if (loadedPaths.has(id)) next.add(id);
      }
      return next;
    });
  }, []);

  const replaceExpandedIds = useCallback((paths: Iterable<string>) => {
    setExpandedIds(new Set(paths));
  }, []);


  const clearSearch = useCallback(() => {
    setSearchQuery('');
  }, []);


  const openContextMenu = useCallback((x: number, y: number, node: FileTreeNode) => {
    setContextMenu({ x, y, node });
  }, []);

  const closeContextMenu = useCallback(() => {
    setContextMenu(null);
  }, []);

  return {

    nodes,
    selectedId,
    selectedIds,
    lastSelectedId,
    expandedIds,
    isLoading,
    error,
    searchQuery,
    contextMenu,


    visibleNodes,
    filteredNodes,
    flatNodes,
    selectedNodes,
    hasSelection,
    isSearching,


    setNodes,
    updateNode,
    removeNode,
    addNode,
    resetState,


    selectNode,
    selectNodeWithModifier,
    selectAll,
    clearSelection,
    isNodeSelected,
    isNodeMultiSelected,


    expandNode,
    collapseNode,
    toggleNode,
    expandAll,
    collapseAll,
    isNodeExpanded,
    syncExpandedWithLoaded,
    replaceExpandedIds,


    setSearchQuery,
    clearSearch,


    setLoading,
    setError,


    openContextMenu,
    closeContextMenu,
  };
}
