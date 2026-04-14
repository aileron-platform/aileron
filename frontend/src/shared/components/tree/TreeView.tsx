import React from 'react';
import { cn } from '@/shared/utils/cn';

export interface TreeViewRenderState {
  isExpanded: boolean;
  isSelected: boolean;
  isMultiSelected: boolean;
}

export interface TreeViewRenderHandlers<TNode> {
  toggleExpand: () => void;
  select: () => void;
  toggleMultiSelect: () => void;
  node: TNode;
}

export interface TreeViewRenderProps<TNode> {
  node: TNode;
  depth: number;
  isLeaf: boolean;
  state: TreeViewRenderState;
  handlers: TreeViewRenderHandlers<TNode>;
}

export interface TreeViewProps<TNode> {
  nodes: TNode[];
  className?: string;
  expandedIds?: Set<string> | null;
  selectedId?: string | null;
  multiSelectedIds?: Set<string> | null;
  expandAll?: boolean;
  getNodeId?: (node: TNode) => string;
  getNodeChildren?: (node: TNode) => TNode[] | undefined;
  renderNode: (props: TreeViewRenderProps<TNode>) => React.ReactNode;
  onToggleExpand?: (node: TNode) => void;
  onSelect?: (node: TNode) => void;
  onToggleMultiSelect?: (node: TNode) => void;
}

const defaultGetNodeId = (node: unknown) => {
  if (node && typeof node === 'object') {
    const record = node as Record<string, unknown>;
    if (typeof record.id === 'string') {
      return record.id;
    }
    if (typeof record.path === 'string') {
      return record.path;
    }
    if (typeof record.key === 'string') {
      return record.key;
    }
  }
  return String(node);
};

const defaultGetNodeChildren = <TNode,>(node: TNode): TNode[] | undefined => {
  if (node && typeof node === 'object') {
    const record = node as Record<string, unknown>;
    const children = record.children;
    if (Array.isArray(children)) {
      return children as TNode[];
    }
  }
  return undefined;
};

export function TreeView<TNode>({
  nodes,
  className,
  expandedIds,
  selectedId,
  multiSelectedIds,
  expandAll = false,
  getNodeId = defaultGetNodeId,
  getNodeChildren = defaultGetNodeChildren,
  renderNode,
  onToggleExpand,
  onSelect,
  onToggleMultiSelect,
}: TreeViewProps<TNode>) {
  const renderNodes = React.useCallback(
    (nodeList: TNode[], depth: number): React.ReactNode[] =>
      nodeList.map(node => {
        const nodeId = getNodeId(node);
        const children = getNodeChildren(node) ?? [];
        const hasChildren = Array.isArray(children) && children.length > 0;
        // 修改：即使沒有子項，只要在 expandedIds 中就視為展開（用於顯示正確的資料夾圖示）
        const isExpanded = expandAll || expandedIds?.has(nodeId) === true;
        const isSelected = selectedId != null && nodeId === selectedId;
        const isMultiSelected = multiSelectedIds?.has?.(nodeId) ?? false;

        const state: TreeViewRenderState = {
          isExpanded,
          isSelected,
          isMultiSelected,
        };

        const handlers: TreeViewRenderHandlers<TNode> = {
          node,
          toggleExpand: () => {
            onToggleExpand?.(node);
          },
          select: () => {
            onSelect?.(node);
          },
          toggleMultiSelect: () => {
            onToggleMultiSelect?.(node);
          },
        };

        return (
          <React.Fragment key={nodeId}>
            {renderNode({ node, depth, isLeaf: !hasChildren, state, handlers })}
            {hasChildren && (expandAll || isExpanded)
              ? renderNodes(children, depth + 1)
              : null}
          </React.Fragment>
        );
      }),
    [expandAll, expandedIds, getNodeChildren, getNodeId, multiSelectedIds, onSelect, onToggleExpand, onToggleMultiSelect, renderNode, selectedId],
  );

  return <div className={cn('space-y-1', className)}>{renderNodes(nodes, 0)}</div>;
}
