import type { FileTreeNode as ManagerFileTreeNode } from '@/shared/components/file-workbench';
import type { FileNode } from './fileManagementTypes';
import { ensureLeadingSlash } from './filePathModel';

const mapManagerNodeToFileNode = (
  node: ManagerFileTreeNode,
  expandedIds: Set<string>,
  depth: number,
): FileNode => {
  const children = node.children?.map(child => (
    mapManagerNodeToFileNode(child, expandedIds, depth + 1)
  )) ?? [];
  const normalizedPath = ensureLeadingSlash(node.path);
  const hasChildren = node.type === 'directory' && (
    node.hasChildren === true
    || (node.hasChildren === undefined && (node.children ? node.children.length > 0 : true))
  );

  return {
    id: node.id ?? normalizedPath,
    name: node.name,
    path: normalizedPath,
    type: node.type,
    size: node.size,
    lastModified: node.modifiedAt,
    children,
    hasChildren,
    isExpanded: expandedIds.has(normalizedPath),
    isLoading: false,
    depth,
  };
};

export const mapManagerNodes = (
  nodes: ManagerFileTreeNode[],
  expandedIds: Set<string>,
): FileNode[] => nodes.map(node => mapManagerNodeToFileNode(node, expandedIds, 0));
