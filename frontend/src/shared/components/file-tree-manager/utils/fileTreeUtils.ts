/**
 * 統一檔案樹管理組件 - 工具函數
 */

import type { FileTreeNode } from '../types';

/**
 * 根據路徑查找節點
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
 * 搜尋過濾節點
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
      // 節點本身符合，包含所有子節點
      filtered.push(node);
    } else if (node.children) {
      // 節點本身不符合，但可能有子節點符合
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
 * 扁平化樹狀結構
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
 * 建立樹狀結構（從扁平列表）
 */
export function buildTree(flatList: FileTreeNode[]): FileTreeNode[] {
  const map = new Map<string, FileTreeNode>();
  const roots: FileTreeNode[] = [];

  // 建立映射
  for (const node of flatList) {
    map.set(node.path, { ...node, children: [] });
  }

  // 建立樹狀結構
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
 * 取得父路徑
 */
export function getParentPath(path: string): string | null {
  const parts = path.split('/').filter(Boolean);
  if (parts.length <= 1) {
    return null;
  }
  return parts.slice(0, -1).join('/');
}

/**
 * 取得節點深度
 */
export function getNodeDepth(path: string): number {
  return path.split('/').filter(Boolean).length;
}

/**
 * 判斷是否為祖先節點
 */
export function isAncestor(ancestorPath: string, descendantPath: string): boolean {
  if (ancestorPath === descendantPath) {
    return false;
  }
  return descendantPath.startsWith(ancestorPath + '/');
}

/**
 * 取得檔案副檔名
 */
export function getFileExtension(fileName: string): string {
  const parts = fileName.split('.');
  if (parts.length <= 1) {
    return '';
  }
  return parts[parts.length - 1].toLowerCase();
}

/**
 * 根據副檔名取得語言
 * @deprecated 請使用 @/shared/utils/languageUtils 中的 getLanguageFromExtension
 */
export function getLanguageFromExtension(extension: string): string {
  // 使用統一的語言工具函數
  const { getLanguageFromExtension: getLang } = require('@/shared/utils/languageUtils');
  return getLang(extension);
}

/**
 * 判斷是否為圖片檔案
 */
export function isImageFile(fileName: string): boolean {
  const extension = getFileExtension(fileName);
  const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'bmp', 'ico'];
  return imageExtensions.includes(extension);
}

/**
 * 判斷是否為 Markdown 檔案
 */
export function isMarkdownFile(fileName: string): boolean {
  const extension = getFileExtension(fileName);
  return extension === 'md' || extension === 'markdown';
}

/**
 * 格式化檔案大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
}

/**
 * 取得所有檔案節點（不包含資料夾）
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
 * 取得所有資料夾節點
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
 * 取得節點的所有後代路徑
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
 * 排序節點（資料夾優先，然後按名稱排序）
 */
export function sortNodes(nodes: FileTreeNode[]): FileTreeNode[] {
  return [...nodes].sort((a, b) => {
    // 資料夾優先
    if (a.type === 'directory' && b.type === 'file') {
      return -1;
    }
    if (a.type === 'file' && b.type === 'directory') {
      return 1;
    }
    // 按名稱排序
    return a.name.localeCompare(b.name);
  });
}

/**
 * 驗證檔案名稱
 */
export function validateFileName(fileName: string): { valid: boolean; error?: string } {
  if (!fileName || fileName.trim() === '') {
    return { valid: false, error: '檔案名稱不能為空' };
  }

  // 不允許的字元
  const invalidChars = /[<>:"|?*\x00-\x1F]/;
  if (invalidChars.test(fileName)) {
    return { valid: false, error: '檔案名稱包含不允許的字元' };
  }

  // 不允許的名稱
  const reservedNames = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'LPT1', 'LPT2', 'LPT3'];
  if (reservedNames.includes(fileName.toUpperCase())) {
    return { valid: false, error: '檔案名稱為系統保留名稱' };
  }

  return { valid: true };
}

