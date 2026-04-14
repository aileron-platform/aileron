/**
 * useFileTreeSelection Hook
 *
 * 提供統一的檔案樹選擇邏輯，支援：
 * - 單選
 * - Ctrl/Cmd + Click 多選
 * - Shift + Click 範圍選擇
 * - 資料夾選擇自動包含子節點
 * - Ctrl/Cmd + A 全選
 * - Escape 清除選擇
 * - 點擊空白區域清除選擇
 */

import { useState, useCallback, useEffect } from 'react';

// 重新導出 SelectionModifier 型別和工具函數
export type { SelectionModifier } from '@/features/workspace/features/file-management/types';
export {
  getSelectionModifierFromEvent,
  isMacOS
} from '@/features/workspace/features/file-management/utils/selectionUtils';

// 導入內部使用的工具函數
import {
  getVisibleFileNodes,
  calculateRangeSelection,
  getAllFileNodes,
  getDescendantPaths,
  findNodeByPath,
  isMacOS as checkIsMacOS,
} from '@/features/workspace/features/file-management/utils/selectionUtils';

export interface FileTreeNode {
  id?: string;
  path: string;
  name: string;
  type: 'file' | 'directory';
  children?: FileTreeNode[];
}

export interface UseFileTreeSelectionOptions {
  nodes: FileTreeNode[];
  expandedNodes: Set<string>;
  onSelectionChange?: (selectedPaths: Set<string>) => void;
}

export interface UseFileTreeSelectionReturn {
  selectedFiles: Set<string>;
  lastSelectedFile: string | null;
  selectFile: (path: string) => void;
  selectFileWithModifier: (path: string, modifier: import('@/features/workspace/features/file-management/types').SelectionModifier) => void;
  selectRange: (fromPath: string, toPath: string) => void;
  selectAllFiles: (paths: string[]) => void;
  clearSelection: () => void;
  toggleMultiSelect: (path: string) => void;
}

/**
 * useFileTreeSelection Hook
 */
export function useFileTreeSelection({
  nodes,
  expandedNodes,
  onSelectionChange,
}: UseFileTreeSelectionOptions): UseFileTreeSelectionReturn {
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [lastSelectedFile, setLastSelectedFile] = useState<string | null>(null);

  // 當選擇變更時通知外部
  useEffect(() => {
    onSelectionChange?.(selectedFiles);
  }, [selectedFiles, onSelectionChange]);

  const selectFile = useCallback((path: string) => {
    setSelectedFiles(new Set([path]));
    setLastSelectedFile(path);
  }, []);

  const selectFileWithModifier = useCallback((path: string, modifier: import('@/features/workspace/features/file-management/types').SelectionModifier) => {
    if (modifier === 'shift') {
      // Shift 範圍選擇
      if (lastSelectedFile) {
        const visibleNodes = getVisibleFileNodes(nodes, expandedNodes);
        const rangeFiles = calculateRangeSelection(visibleNodes, lastSelectedFile, path);
        
        // 對於範圍內的每個節點，如果是資料夾，也要選擇其子節點
        const allPaths = new Set<string>();
        for (const nodePath of rangeFiles) {
          const node = findNodeByPath(nodes, nodePath);
          if (node) {
            const descendantPaths = getDescendantPaths(node);
            descendantPaths.forEach(p => allPaths.add(p));
          }
        }
        
        setSelectedFiles(allPaths);
        setLastSelectedFile(path);
      } else {
        // 如果沒有上次選擇，當作普通選擇
        selectFile(path);
      }
    } else if (modifier === 'ctrl') {
      // Ctrl/Cmd 切換選擇
      const node = findNodeByPath(nodes, path);
      const newSelected = new Set(selectedFiles);
      
      if (node && node.type === 'directory') {
        // 資料夾：切換資料夾及其所有子節點
        const descendantPaths = getDescendantPaths(node);
        const isCurrentlySelected = newSelected.has(path);
        
        if (isCurrentlySelected) {
          descendantPaths.forEach(p => newSelected.delete(p));
        } else {
          descendantPaths.forEach(p => newSelected.add(p));
        }
      } else {
        // 檔案：切換單個檔案
        if (newSelected.has(path)) {
          newSelected.delete(path);
        } else {
          newSelected.add(path);
        }
      }
      
      setSelectedFiles(newSelected);
      setLastSelectedFile(path);
    } else {
      // none: 清除其他選擇，只選當前
      const node = findNodeByPath(nodes, path);
      
      if (node && node.type === 'directory') {
        // 資料夾：選擇資料夾及其所有子節點
        const descendantPaths = getDescendantPaths(node);
        setSelectedFiles(new Set(descendantPaths));
      } else {
        // 檔案：只選擇當前檔案
        setSelectedFiles(new Set([path]));
      }
      
      setLastSelectedFile(path);
    }
  }, [nodes, expandedNodes, selectedFiles, lastSelectedFile, selectFile]);

  const selectRange = useCallback((fromPath: string, toPath: string) => {
    const visibleNodes = getVisibleFileNodes(nodes, expandedNodes);
    const rangeFiles = calculateRangeSelection(visibleNodes, fromPath, toPath);
    
    // 對於範圍內的每個節點，如果是資料夾，也要選擇其子節點
    const allPaths = new Set<string>();
    for (const path of rangeFiles) {
      const node = findNodeByPath(nodes, path);
      if (node) {
        const descendantPaths = getDescendantPaths(node);
        descendantPaths.forEach(p => allPaths.add(p));
      }
    }
    
    setSelectedFiles(allPaths);
    setLastSelectedFile(toPath);
  }, [nodes, expandedNodes]);

  const selectAllFiles = useCallback((paths: string[]) => {
    setSelectedFiles(new Set(paths));
  }, []);

  const clearSelection = useCallback(() => {
    setSelectedFiles(new Set());
    setLastSelectedFile(null);
  }, []);

  const toggleMultiSelect = useCallback((path: string) => {
    const newSelected = new Set(selectedFiles);
    if (newSelected.has(path)) {
      newSelected.delete(path);
    } else {
      newSelected.add(path);
    }
    setSelectedFiles(newSelected);
  }, [selectedFiles]);

  // 鍵盤事件處理
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const isMac = checkIsMacOS();
      const isCtrlOrCmd = isMac ? event.metaKey : event.ctrlKey;

      // Ctrl/Cmd + A: 全選
      if (isCtrlOrCmd && event.key === 'a') {
        event.preventDefault();
        const allFileNodes = getAllFileNodes(nodes);
        const allFilePaths = allFileNodes.map(node => node.path);
        selectAllFiles(allFilePaths);
      }

      // Escape: 取消選擇
      if (event.key === 'Escape') {
        event.preventDefault();
        clearSelection();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nodes, selectAllFiles, clearSelection]);

  return {
    selectedFiles,
    lastSelectedFile,
    selectFile,
    selectFileWithModifier,
    selectRange,
    selectAllFiles,
    clearSelection,
    toggleMultiSelect,
  };
}
