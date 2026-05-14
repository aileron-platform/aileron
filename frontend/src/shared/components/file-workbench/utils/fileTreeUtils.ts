/**
 */

import type { FileTreeNode } from '../types';

/**
 */
export function findNodeByPath(
  nodes: FileTreeNode[],
  path: string
): FileTreeNode | null {
  for (const node of nodes) {
    if (node.path === path) {
      return node;
    }
    if (node.children) {
      const found = findNodeByPath(node.children, path);
      if (found) {
        return found;
      }
    }
  }
  return null;
}

/**
 */
export function filterNodesBySearch(
  nodes: FileTreeNode[],
  searchQuery: string
): FileTreeNode[] {
  const query = searchQuery.toLowerCase().trim();
  if (!query) {
    return nodes;
  }

  const filtered: FileTreeNode[] = [];

  for (const node of nodes) {
    const nameMatches = node.name.toLowerCase().includes(query);
    const pathMatches = node.path.toLowerCase().includes(query);

    if (nameMatches || pathMatches) {

      filtered.push(node);
    } else if (node.children) {

      const filteredChildren = filterNodesBySearch(node.children, searchQuery);
      if (filteredChildren.length > 0) {
        filtered.push({
          ...node,
          children: filteredChildren,
        });
      }
    }
  }

  return filtered;
}

/**
 */
export function flattenTree(nodes: FileTreeNode[]): FileTreeNode[] {
  const result: FileTreeNode[] = [];

  function traverse(list: FileTreeNode[]) {
    for (const node of list) {
      result.push(node);
      if (node.children) {
        traverse(node.children);
      }
    }
  }

  traverse(nodes);
  return result;
}

/**
 */
export function buildTree(flatList: FileTreeNode[]): FileTreeNode[] {
  const map = new Map<string, FileTreeNode>();
  const roots: FileTreeNode[] = [];


  for (const node of flatList) {
    map.set(node.path, { ...node, children: [] });
  }


  for (const node of flatList) {
    const current = map.get(node.path)!;
    const parentPath = getParentPath(node.path);

    if (parentPath && map.has(parentPath)) {
      const parent = map.get(parentPath)!;
      if (!parent.children) {
        parent.children = [];
      }
      parent.children.push(current);
    } else {
      roots.push(current);
    }
  }

  return roots;
}

/**
 */
export function getParentPath(path: string): string | null {
  const parts = path.split('/').filter(Boolean);
  if (parts.length <= 1) {
    return null;
  }
  return parts.slice(0, -1).join('/');
}

/**
 */
export function getNodeDepth(path: string): number {
  return path.split('/').filter(Boolean).length;
}

/**
 */
export function isAncestor(ancestorPath: string, descendantPath: string): boolean {
  if (ancestorPath === descendantPath) {
    return false;
  }
  return descendantPath.startsWith(ancestorPath + '/');
}

/**
 */
export function getFileExtension(fileName: string): string {
  const parts = fileName.split('.');
  if (parts.length <= 1) {
    return '';
  }
  return parts[parts.length - 1].toLowerCase();
}

/**
 */
export function getLanguageFromExtension(extension: string): string {

  const { getLanguageFromExtension: getLang } = require('@/shared/utils/languageUtils');
  return getLang(extension);
}

/**
 */
export function isImageFile(fileName: string): boolean {
  const extension = getFileExtension(fileName);
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico'];
  return imageExtensions.includes(extension);
}

/**
 */
export function isMarkdownFile(fileName: string): boolean {
  const extension = getFileExtension(fileName);
  return extension === 'md' || extension === 'markdown';
}

/**
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

/**
 */
export function getAllFileNodes(nodes: FileTreeNode[]): FileTreeNode[] {
  const files: FileTreeNode[] = [];

  function traverse(list: FileTreeNode[]) {
    for (const node of list) {
      if (node.type === 'file') {
        files.push(node);
      }
      if (node.children) {
        traverse(node.children);
      }
    }
  }

  traverse(nodes);
  return files;
}

/**
 */
export function getAllDirectoryNodes(nodes: FileTreeNode[]): FileTreeNode[] {
  const directories: FileTreeNode[] = [];

  function traverse(list: FileTreeNode[]) {
    for (const node of list) {
      if (node.type === 'directory') {
        directories.push(node);
      }
      if (node.children) {
        traverse(node.children);
      }
    }
  }

  traverse(nodes);
  return directories;
}

/**
 * Returns true when the node is a directory whose response was truncated by
 * the maxDepth limit. The backend signals this by returning `children: []`
 * together with `hasChildren: true`, which the rest of the tree-restoration
 * code uses to know it must call `getChildren` to load the real list.
 */
export function isDepthTruncatedDirectory(node: FileTreeNode): boolean {
  return (
    node.type === 'directory' &&
    Array.isArray(node.children) &&
    node.children.length === 0 &&
    node.hasChildren === true
  );
}

/**
 */
export function getDescendantPaths(node: FileTreeNode): string[] {
  const paths: string[] = [node.path];

  function traverse(n: FileTreeNode) {
    if (n.children) {
      for (const child of n.children) {
        paths.push(child.path);
        traverse(child);
      }
    }
  }

  traverse(node);
  return paths;
}

/**
 */
export function computeLoadedChildrenPaths(nodes: FileTreeNode[]): Set<string> {
  const loaded = new Set<string>();

  function traverse(list: FileTreeNode[]) {
    for (const node of list) {
      if (node.type === 'directory') {
        const childrenReturned = node.children !== undefined && node.children.length > 0;
        const trulyEmpty = node.hasChildren === false;
        if (childrenReturned || trulyEmpty) {
          loaded.add(node.path);
        }
        if (node.children) {
          traverse(node.children);
        }
      }
    }
  }

  traverse(nodes);
  return loaded;
}

/**
 */
export function sortNodes(nodes: FileTreeNode[]): FileTreeNode[] {
  return [...nodes].sort((a, b) => {

    if (a.type === 'directory' && b.type === 'file') {
      return -1;
    }
    if (a.type === 'file' && b.type === 'directory') {
      return 1;
    }

    if (a.type === 'file' && b.type === 'file') {
      const extensionCompare = getSortableFileExtension(a).localeCompare(
        getSortableFileExtension(b),
        undefined,
        { numeric: true, sensitivity: 'base' },
      );
      if (extensionCompare !== 0) {
        return extensionCompare;
      }
    }

    return a.name.localeCompare(b.name, undefined, { numeric: true, sensitivity: 'base' });
  });
}

export function sortTreeNodes(nodes: FileTreeNode[]): FileTreeNode[] {
  return sortNodes(nodes).map((node) => ({
    ...node,
    children: node.children ? sortTreeNodes(node.children) : node.children,
  }));
}

function getSortableFileExtension(node: FileTreeNode): string {
  if (typeof node.extension === 'string') {
    return node.extension.toLowerCase();
  }
  return getFileExtension(node.name);
}

/**
 */
export function validateFileName(fileName: string): { valid: boolean; error?: string } {
  if (!fileName || fileName.trim() === '') {
    return { valid: false, error: 'File name cannot be empty' };
  }


  const invalidChars = /[<>:"|?*\x00-\x1F]/;
  if (invalidChars.test(fileName)) {
    return { valid: false, error: 'File name contains invalid characters' };
  }


  const reservedNames = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1', 'LPT2', 'LPT3'];
  if (reservedNames.includes(fileName.toUpperCase())) {
    return { valid: false, error: 'File name is reserved by the system' };
  }

  return { valid: true };
}
