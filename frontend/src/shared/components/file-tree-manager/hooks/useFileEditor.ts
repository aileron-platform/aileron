/**
 * useFileEditor Hook
 * 
 * 管理檔案編輯器狀態，包括：
 * - 開啟的檔案標籤
 * - 當前活動標籤
 * - 檔案內容
 * - 修改狀態
 * - 自動儲存
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { FileTreeNode, FileTab } from '../types';
import { DEFAULTS } from '../constants';

export interface UseFileEditorOptions {
  /** 自動儲存延遲（毫秒） */
  autoSaveDelay?: number;
  /** 自動儲存回調 */
  onAutoSave?: (path: string, content: string) => Promise<void>;
  /** 檔案開啟回調 */
  onFileOpen?: (node: FileTreeNode) => void;
  /** 檔案關閉回調 */
  onFileClose?: (path: string) => void;
  /** 內容變更回調 */
  onContentChange?: (path: string, content: string) => void;
}

export interface UseFileEditorReturn {
  // 狀態
  tabs: FileTab[];
  activeTabPath: string | null;
  activeTab: FileTab | null;
  hasModifiedTabs: boolean;
  modifiedTabPaths: string[];

  // 標籤操作
  openTab: (node: FileTreeNode, content: string) => void;
  closeTab: (path: string) => void;
  closeAllTabs: () => void;
  closeOtherTabs: (path: string) => void;
  setActiveTab: (path: string) => void;
  getTab: (path: string) => FileTab | undefined;
  isTabOpen: (path: string) => boolean;

  // 內容操作
  updateContent: (path: string, content: string) => void;
  saveTab: (path: string) => void;
  saveAllTabs: () => void;
  revertTab: (path: string) => void;
  isTabModified: (path: string) => boolean;

  // 導航
  nextTab: () => void;
  previousTab: () => void;
}

export function useFileEditor(
  options: UseFileEditorOptions = {}
): UseFileEditorReturn {
  const {
    autoSaveDelay = DEFAULTS.AUTO_SAVE_DELAY,
    onAutoSave,
    onFileOpen,
    onFileClose,
    onContentChange,
  } = options;

  const [tabs, setTabs] = useState<FileTab[]>([]);
  const [activeTabPath, setActiveTabPath] = useState<string | null>(null);

  // 自動儲存計時器
  const autoSaveTimers = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // 計算屬性
  const activeTab = tabs.find(tab => tab.path === activeTabPath) || null;
  const hasModifiedTabs = tabs.some(tab => tab.isModified);
  const modifiedTabPaths = tabs.filter(tab => tab.isModified).map(tab => tab.path);

  // 清理自動儲存計時器
  useEffect(() => {
    return () => {
      autoSaveTimers.current.forEach(timer => clearTimeout(timer));
      autoSaveTimers.current.clear();
    };
  }, []);

  // 標籤操作
  const openTab = useCallback((node: FileTreeNode, content: string) => {
    setTabs(prevTabs => {
      const existingTab = prevTabs.find(tab => tab.path === node.path);
      if (existingTab) {
        // 標籤已存在，更新內容
        return prevTabs.map(tab =>
          tab.path === node.path
            ? { ...tab, content, originalContent: content, isModified: false }
            : tab
        );
      }

      // 創建新標籤
      const newTab: FileTab = {
        path: node.path,
        name: node.name,
        content,
        originalContent: content,
        isModified: false,
        node,
      };

      return [...prevTabs, newTab];
    });

    setActiveTabPath(node.path);

    if (onFileOpen) {
      onFileOpen(node);
    }
  }, [onFileOpen]);

  const closeTab = useCallback((path: string) => {
    setTabs(prevTabs => {
      const newTabs = prevTabs.filter(tab => tab.path !== path);

      // 如果關閉的是當前活動標籤，切換到下一個標籤
      if (activeTabPath === path) {
        const closedIndex = prevTabs.findIndex(tab => tab.path === path);
        if (newTabs.length > 0) {
          const nextIndex = Math.min(closedIndex, newTabs.length - 1);
          setActiveTabPath(newTabs[nextIndex].path);
        } else {
          setActiveTabPath(null);
        }
      }

      return newTabs;
    });

    // 清理自動儲存計時器
    const timer = autoSaveTimers.current.get(path);
    if (timer) {
      clearTimeout(timer);
      autoSaveTimers.current.delete(path);
    }

    if (onFileClose) {
      onFileClose(path);
    }
  }, [activeTabPath, onFileClose]);

  const closeAllTabs = useCallback(() => {
    setTabs([]);
    setActiveTabPath(null);

    // 清理所有自動儲存計時器
    autoSaveTimers.current.forEach(timer => clearTimeout(timer));
    autoSaveTimers.current.clear();
  }, []);

  const closeOtherTabs = useCallback((path: string) => {
    setTabs(prevTabs => prevTabs.filter(tab => tab.path === path));
    setActiveTabPath(path);

    // 清理其他標籤的自動儲存計時器
    autoSaveTimers.current.forEach((timer, timerPath) => {
      if (timerPath !== path) {
        clearTimeout(timer);
        autoSaveTimers.current.delete(timerPath);
      }
    });
  }, []);

  const setActiveTab = useCallback((path: string) => {
    setActiveTabPath(path);
  }, []);

  const getTab = useCallback((path: string) => {
    return tabs.find(tab => tab.path === path);
  }, [tabs]);

  const isTabOpen = useCallback((path: string) => {
    return tabs.some(tab => tab.path === path);
  }, [tabs]);

  // 內容操作
  const updateContent = useCallback((path: string, content: string) => {
    setTabs(prevTabs =>
      prevTabs.map(tab => {
        if (tab.path === path) {
          const isModified = content !== tab.originalContent;
          return { ...tab, content, isModified };
        }
        return tab;
      })
    );

    if (onContentChange) {
      onContentChange(path, content);
    }

    // 設置自動儲存計時器
    if (onAutoSave) {
      const existingTimer = autoSaveTimers.current.get(path);
      if (existingTimer) {
        clearTimeout(existingTimer);
      }

      const timer = setTimeout(() => {
        onAutoSave(path, content);
        autoSaveTimers.current.delete(path);
      }, autoSaveDelay);

      autoSaveTimers.current.set(path, timer);
    }
  }, [onContentChange, onAutoSave, autoSaveDelay]);

  const saveTab = useCallback((path: string) => {
    setTabs(prevTabs =>
      prevTabs.map(tab => {
        if (tab.path === path) {
          return { ...tab, originalContent: tab.content, isModified: false };
        }
        return tab;
      })
    );

    // 清理自動儲存計時器
    const timer = autoSaveTimers.current.get(path);
    if (timer) {
      clearTimeout(timer);
      autoSaveTimers.current.delete(path);
    }
  }, []);

  const saveAllTabs = useCallback(() => {
    setTabs(prevTabs =>
      prevTabs.map(tab => ({
        ...tab,
        originalContent: tab.content,
        isModified: false,
      }))
    );

    // 清理所有自動儲存計時器
    autoSaveTimers.current.forEach(timer => clearTimeout(timer));
    autoSaveTimers.current.clear();
  }, []);

  const revertTab = useCallback((path: string) => {
    setTabs(prevTabs =>
      prevTabs.map(tab => {
        if (tab.path === path) {
          return { ...tab, content: tab.originalContent, isModified: false };
        }
        return tab;
      })
    );

    // 清理自動儲存計時器
    const timer = autoSaveTimers.current.get(path);
    if (timer) {
      clearTimeout(timer);
      autoSaveTimers.current.delete(path);
    }
  }, []);

  const isTabModified = useCallback((path: string) => {
    const tab = tabs.find(t => t.path === path);
    return tab?.isModified || false;
  }, [tabs]);

  // 導航
  const nextTab = useCallback(() => {
    if (tabs.length === 0) return;

    const currentIndex = tabs.findIndex(tab => tab.path === activeTabPath);
    const nextIndex = (currentIndex + 1) % tabs.length;
    setActiveTabPath(tabs[nextIndex].path);
  }, [tabs, activeTabPath]);

  const previousTab = useCallback(() => {
    if (tabs.length === 0) return;

    const currentIndex = tabs.findIndex(tab => tab.path === activeTabPath);
    const prevIndex = currentIndex <= 0 ? tabs.length - 1 : currentIndex - 1;
    setActiveTabPath(tabs[prevIndex].path);
  }, [tabs, activeTabPath]);

  return {
    // 狀態
    tabs,
    activeTabPath,
    activeTab,
    hasModifiedTabs,
    modifiedTabPaths,

    // 標籤操作
    openTab,
    closeTab,
    closeAllTabs,
    closeOtherTabs,
    setActiveTab,
    getTab,
    isTabOpen,

    // 內容操作
    updateContent,
    saveTab,
    saveAllTabs,
    revertTab,
    isTabModified,

    // 導航
    nextTab,
    previousTab,
  };
}

