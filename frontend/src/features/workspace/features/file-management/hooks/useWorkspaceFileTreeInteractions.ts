import { useCallback, useState } from 'react';
import { findNodeByPath as findManagerNode } from '@/shared/components/file-workbench';
import type {
  SelectionModifier,
  useFileTreeManager,
} from '@/shared/components/file-workbench';
import { ensureLeadingSlash } from '../model/filePathModel';

type WorkspaceFileTreeManager = ReturnType<typeof useFileTreeManager>;

interface UseWorkspaceFileTreeInteractionsOptions {
  manager: WorkspaceFileTreeManager;
}

export const useWorkspaceFileTreeInteractions = ({
  manager,
}: UseWorkspaceFileTreeInteractionsOptions) => {
  const [draggedNode, setDraggedNode] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<string | null>(null);

  const selectFile = useCallback((filePath: string) => {
    manager.state.selectNode(ensureLeadingSlash(filePath));
  }, [manager.state]);

  const selectFileWithModifier = useCallback((filePath: string, modifier: SelectionModifier) => {
    manager.state.selectNodeWithModifier(ensureLeadingSlash(filePath), modifier);
  }, [manager.state]);

  const selectRange = useCallback((fromPath: string, toPath: string) => {
    const normalizedFrom = ensureLeadingSlash(fromPath);
    const normalizedTo = ensureLeadingSlash(toPath);
    manager.state.selectNode(normalizedFrom);
    manager.state.selectNodeWithModifier(normalizedTo, 'shift');
  }, [manager.state]);

  const toggleMultiSelect = useCallback((filePath: string) => {
    manager.state.selectNodeWithModifier(ensureLeadingSlash(filePath), 'ctrl');
  }, [manager.state]);

  const clearSelection = useCallback(() => {
    manager.state.clearSelection();
  }, [manager.state]);

  const selectAllFiles = useCallback((filePaths: string[]) => {
    const normalized = filePaths.map(ensureLeadingSlash);
    if (normalized.length === 0) {
      manager.state.clearSelection();
      return;
    }

    const [first, ...rest] = normalized;
    manager.state.selectNode(first);
    rest.forEach(path => manager.state.selectNodeWithModifier(path, 'ctrl'));
  }, [manager.state]);

  const expandNode = useCallback(async (nodePath: string) => {
    const normalized = ensureLeadingSlash(nodePath);
    const node = findManagerNode(manager.state.nodes, normalized);
    if (!node) return;
    await manager.toggleDirectory(node);
  }, [manager]);

  const collapseNode = useCallback((nodePath: string) => {
    manager.state.collapseNode(ensureLeadingSlash(nodePath));
  }, [manager.state]);

  const resetInteractionState = useCallback(() => {
    setDraggedNode(null);
    setDropTarget(null);
  }, []);

  return {
    draggedNode,
    setDraggedNode,
    dropTarget,
    setDropTarget,
    selectFile,
    selectFileWithModifier,
    selectRange,
    toggleMultiSelect,
    clearSelection,
    selectAllFiles,
    expandNode,
    collapseNode,
    resetInteractionState,
  };
};
