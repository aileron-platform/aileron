/**
 * 檔案操作工具函數
 * 完全按照原始設計重構
 */

import type { FileNode } from '../types';

/**
 * 獲取所有檔案節點（不包含目錄）
 */
export const getAllFileNodes = (nodes: FileNode[]): FileNode[] => {
  const fileNodes: FileNode[] = [];
  
  const traverse = (nodeList: FileNode[]) => {
    for (const node of nodeList) {
      if (node.type === 'file') {
        fileNodes.push(node);
      }
      if (node.children) {
        traverse(node.children);
      }
    }
  };
  
  traverse(nodes);
  return fileNodes;
};

/**
 * 獲取所有節點（包含目錄和檔案）
 */
export const getAllNodes = (nodes: FileNode[]): FileNode[] => {
  const allNodes: FileNode[] = [];
  
  const traverse = (nodeList: FileNode[]) => {
    for (const node of nodeList) {
      allNodes.push(node);
      if (node.children) {
        traverse(node.children);
      }
    }
  };
  
  traverse(nodes);
  return allNodes;
};

/**
 * 根據路徑查找節點
 */
export const findNodeByPath = (nodes: FileNode[], path: string): FileNode | null => {
  const traverse = (nodeList: FileNode[]): FileNode | null => {
    for (const node of nodeList) {
      if (node.path === path) {
        return node;
      }
      if (node.children) {
        const found = traverse(node.children);
        if (found) return found;
      }
    }
    return null;
  };
  
  return traverse(nodes);
};

/**
 * 獲取節點的父節點
 */
export const getParentNode = (nodes: FileNode[], targetPath: string): FileNode | null => {
  const traverse = (nodeList: FileNode[]): FileNode | null => {
    for (const node of nodeList) {
      if (node.children) {
        // 檢查是否為直接子節點
        const directChild = node.children.find(child => child.path === targetPath);
        if (directChild) {
          return node;
        }
        
        // 遞歸搜尋
        const found = traverse(node.children);
        if (found) return found;
      }
    }
    return null;
  };
  
  return traverse(nodes);
};

/**
 * 獲取節點的所有子節點路徑
 */
export const getChildPaths = (node: FileNode): string[] => {
  const paths: string[] = [];
  
  const traverse = (currentNode: FileNode) => {
    if (currentNode.children) {
      for (const child of currentNode.children) {
        paths.push(child.path);
        traverse(child);
      }
    }
  };
  
  traverse(node);
  return paths;
};

/**
 * 檢查路徑是否為另一個路徑的子路徑
 */
export const isChildPath = (childPath: string, parentPath: string): boolean => {
  if (childPath === parentPath) return false;
  return childPath.startsWith(parentPath + '/');
};

/**
 * 獲取路徑的深度
 */
export const getPathDepth = (path: string): number => {
  if (path === '/' || path === '') return 0;
  return path.split('/').filter(segment => segment.length > 0).length;
};

/**
 * 獲取路徑的父路徑
 */
export const getParentPath = (path: string): string => {
  if (path === '/' || path === '') return '';
  const segments = path.split('/').filter(segment => segment.length > 0);
  if (segments.length <= 1) return '/';
  return '/' + segments.slice(0, -1).join('/');
};

/**
 * 獲取路徑的檔案名稱
 */
export const getFileName = (path: string): string => {
  if (path === '/' || path === '') return '';
  const segments = path.split('/').filter(segment => segment.length > 0);
  return segments[segments.length - 1] || '';
};

/**
 * 組合路徑
 */
export const joinPath = (parentPath: string, childName: string): string => {
  if (parentPath === '/' || parentPath === '') {
    return '/' + childName;
  }
  return parentPath + '/' + childName;
};

/**
 * 標準化路徑
 */
export const normalizePath = (path: string): string => {
  // 移除重複的斜線
  let normalized = path.replace(/\/+/g, '/');
  
  // 確保以斜線開頭
  if (!normalized.startsWith('/')) {
    normalized = '/' + normalized;
  }
  
  // 移除結尾的斜線（除非是根路徑）
  if (normalized.length > 1 && normalized.endsWith('/')) {
    normalized = normalized.slice(0, -1);
  }
  
  return normalized;
};

/**
 * 排序檔案節點
 */
export const sortFileNodes = (nodes: FileNode[]): FileNode[] => {
  return [...nodes].sort((a, b) => {
    // 目錄優先
    if (a.type !== b.type) {
      return a.type === 'directory' ? -1 : 1;
    }
    
    // 同類型按名稱排序
    return a.name.localeCompare(b.name, 'zh-TW', { 
      numeric: true, 
      sensitivity: 'base' 
    });
  });
};

/**
 * 搜尋檔案節點
 */
export const searchFileNodes = (nodes: FileNode[], searchTerm: string): FileNode[] => {
  if (!searchTerm.trim()) return nodes;
  
  const results: FileNode[] = [];
  const lowerSearchTerm = searchTerm.toLowerCase();
  
  const traverse = (nodeList: FileNode[]) => {
    for (const node of nodeList) {
      if (node.name.toLowerCase().includes(lowerSearchTerm)) {
        results.push(node);
      }
      if (node.children) {
        traverse(node.children);
      }
    }
  };
  
  traverse(nodes);
  return results;
};

/**
 * 建立檔案樹結構
 */
export const buildFileTree = (flatFiles: Array<{ path: string; type: 'file' | 'directory'; size?: number; lastModified?: string }>): FileNode[] => {
  const nodeMap = new Map<string, FileNode>();
  const rootNodes: FileNode[] = [];
  
  // 首先創建所有節點
  for (const file of flatFiles) {
    const segments = file.path.split('/').filter(segment => segment.length > 0);
    let currentPath = '';
    
    for (let i = 0; i < segments.length; i++) {
      const segment = segments[i];
      const parentPath = currentPath;
      currentPath = currentPath ? `${currentPath}/${segment}` : `/${segment}`;
      
      if (!nodeMap.has(currentPath)) {
        const isFile = i === segments.length - 1 && file.type === 'file';
        const node: FileNode = {
          id: currentPath,
          name: segment,
          path: currentPath,
          type: isFile ? 'file' : 'directory',
          size: isFile ? file.size : undefined,
          lastModified: isFile ? file.lastModified : undefined,
          children: isFile ? undefined : [],
          depth: i,
          isExpanded: false
        };
        
        nodeMap.set(currentPath, node);
        
        // 添加到父節點或根節點
        if (parentPath) {
          const parentNode = nodeMap.get(parentPath);
          if (parentNode && parentNode.children) {
            parentNode.children.push(node);
          }
        } else {
          rootNodes.push(node);
        }
      }
    }
  }
  
  // 排序所有節點的子節點
  const sortChildren = (nodes: FileNode[]) => {
    for (const node of nodes) {
      if (node.children) {
        node.children = sortFileNodes(node.children);
        sortChildren(node.children);
      }
    }
  };
  
  const sortedRootNodes = sortFileNodes(rootNodes);
  sortChildren(sortedRootNodes);
  
  return sortedRootNodes;
};
