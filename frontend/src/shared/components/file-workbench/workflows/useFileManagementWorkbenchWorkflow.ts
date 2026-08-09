import { useCallback, useEffect, useRef } from 'react';
import type React from 'react';
import { useFileTreeState, type UseFileTreeStateOptions, type UseFileTreeStateReturn } from '../hooks/useFileTreeState';
import type { FileTreeNode, SelectionModifier } from '../types';

export interface UseFileManagementWorkbenchWorkflowOptions extends UseFileTreeStateOptions {
  onOpenFile?: (node: FileTreeNode) => void;
}

export interface UseFileManagementWorkbenchWorkflowReturn {
  treeState: UseFileTreeStateReturn;
  flatNodesRef: React.MutableRefObject<FileTreeNode[]>;
  handleNodeClick: (node: FileTreeNode, modifier: SelectionModifier) => void;
  handleNodeDoubleClick: (node: FileTreeNode) => void;
  handleContextMenu: (node: FileTreeNode, event: React.MouseEvent) => void;
}

export const useFileManagementWorkbenchWorkflow = ({
  onOpenFile,
  ...stateOptions
}: UseFileManagementWorkbenchWorkflowOptions): UseFileManagementWorkbenchWorkflowReturn => {
  const treeState = useFileTreeState(stateOptions);
  const flatNodesRef = useRef(treeState.flatNodes);

  useEffect(() => {
    flatNodesRef.current = treeState.flatNodes;
  }, [treeState.flatNodes]);

  const handleNodeClick = useCallback((node: FileTreeNode, modifier: SelectionModifier) => {
    treeState.selectNodeWithModifier(node.path, modifier);
    if (node.type === 'file' && modifier === 'none') {
      onOpenFile?.(node);
    }
  }, [onOpenFile, treeState]);

  const handleNodeDoubleClick = useCallback((node: FileTreeNode) => {
    if (node.type === 'file') {
      onOpenFile?.(node);
      return;
    }
    treeState.toggleNode(node.path);
  }, [onOpenFile, treeState]);

  const handleContextMenu = useCallback((node: FileTreeNode, event: React.MouseEvent) => {
    treeState.openContextMenu(event.clientX, event.clientY, node);
  }, [treeState]);

  return {
    treeState,
    flatNodesRef,
    handleNodeClick,
    handleNodeDoubleClick,
    handleContextMenu,
  };
};
