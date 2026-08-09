/**
 * useFileEditor Hook
 * 
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import type { FileContentResult, FileTreeNode, FileTab } from '../types';
import { DEFAULTS } from '../constants';

export interface UseFileEditorOptions {
  autoSaveDelay?: number;
  onAutoSave?: (path: string, content: string, revision?: string | null) => Promise<void>;
  onFileOpen?: (node: FileTreeNode) => void;
  onFileClose?: (path: string) => void;
  onContentChange?: (path: string, content: string) => void;
}

export interface SavedTabResult {
  savedContent: string;
  revision?: string | null;
}

export interface SaveTabOptions {
  clearAutoSaveTimer?: boolean;
}

export interface UseFileEditorReturn {

  tabs: FileTab[];
  activeTabPath: string | null;
  activeTab: FileTab | null;
  hasModifiedTabs: boolean;
  modifiedTabPaths: string[];


  openTab: (
    node: FileTreeNode,
    content: string,
    revision?: string | null,
    readability?: Pick<FileContentResult, 'readable' | 'unreadableReason'>,
  ) => void;
  closeTab: (path: string) => void;
  closeAllTabs: () => void;
  closeOtherTabs: (path: string) => void;
  closeTabsForPath: (path: string, recursive?: boolean) => void;
  setActiveTab: (path: string) => void;
  remapPath: (sourcePath: string, targetPath: string) => void;
  getTab: (path: string) => FileTab | undefined;
  isTabOpen: (path: string) => boolean;


  updateContent: (path: string, content: string) => void;
  saveTab: (path: string, savedContent: string, revision?: string | null, options?: SaveTabOptions) => void;
  saveAllTabs: (savedResultsByPath?: Record<string, SavedTabResult | undefined>) => void;
  revertTab: (path: string) => void;
  isTabModified: (path: string) => boolean;


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
  const tabsRef = useRef<FileTab[]>([]);


  const autoSaveTimers = useRef<Map<string, NodeJS.Timeout>>(new Map());


  const activeTab = tabs.find(tab => tab.path === activeTabPath) || null;
  const hasModifiedTabs = tabs.some(tab => tab.isModified);
  const modifiedTabPaths = tabs.filter(tab => tab.isModified).map(tab => tab.path);


  useEffect(() => {
    tabsRef.current = tabs;
  }, [tabs]);

  useEffect(() => {
    const timers = autoSaveTimers.current;
    return () => {
      timers.forEach(timer => clearTimeout(timer));
      timers.clear();
    };
  }, []);


  const openTab = useCallback((
    node: FileTreeNode,
    content: string,
    revision?: string | null,
    readability?: Pick<FileContentResult, 'readable' | 'unreadableReason'>,
  ) => {
    setTabs(prevTabs => {
      const existingTab = prevTabs.find(tab => tab.path === node.path);
      if (existingTab) {

        return prevTabs.map(tab =>
          tab.path === node.path
            ? {
                ...tab,
                content,
                originalContent: content,
                isModified: false,
                ...(revision !== undefined ? { revision } : {}),
                readable: readability?.readable,
                unreadableReason: readability?.unreadableReason,
              }
            : tab
        );
      }


      const newTab: FileTab = {
        path: node.path,
        name: node.name,
        content,
        originalContent: content,
        isModified: false,
        revision,
        readable: readability?.readable,
        unreadableReason: readability?.unreadableReason,
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


    autoSaveTimers.current.forEach(timer => clearTimeout(timer));
    autoSaveTimers.current.clear();
  }, []);

  const closeOtherTabs = useCallback((path: string) => {
    setTabs(prevTabs => prevTabs.filter(tab => tab.path === path));
    setActiveTabPath(path);


    autoSaveTimers.current.forEach((timer, timerPath) => {
      if (timerPath !== path) {
        clearTimeout(timer);
        autoSaveTimers.current.delete(timerPath);
      }
    });
  }, []);

  const closeTabsForPath = useCallback((path: string, recursive = false) => {
    const isTargetPath = (tabPath: string) => (
      tabPath === path || (recursive && tabPath.startsWith(`${path}/`))
    );

    setTabs(prevTabs => {
      const closedTabs = prevTabs.filter(tab => isTargetPath(tab.path));
      const newTabs = prevTabs.filter(tab => !isTargetPath(tab.path));

      setActiveTabPath(current => (
        current && isTargetPath(current) ? newTabs[0]?.path ?? null : current
      ));

      closedTabs.forEach((tab) => {
        const timer = autoSaveTimers.current.get(tab.path);
        if (timer) {
          clearTimeout(timer);
          autoSaveTimers.current.delete(tab.path);
        }

        onFileClose?.(tab.path);
      });

      return newTabs;
    });
  }, [onFileClose]);

  const setActiveTab = useCallback((path: string) => {
    setActiveTabPath(path);
  }, []);

  const remapPath = useCallback((sourcePath: string, targetPath: string) => {
    const isTargetPath = (tabPath: string) => (
      tabPath === sourcePath || tabPath.startsWith(`${sourcePath}/`)
    );

    const remapTabPath = (tabPath: string) => (
      tabPath === sourcePath
        ? targetPath
        : `${targetPath}${tabPath.slice(sourcePath.length)}`
    );

    setTabs(prevTabs => prevTabs.map(tab => {
      if (!isTargetPath(tab.path)) {
        return tab;
      }

      const nextPath = remapTabPath(tab.path);
      const nextName = nextPath.split('/').pop() || nextPath;
      const timer = autoSaveTimers.current.get(tab.path);
      if (timer) {
        autoSaveTimers.current.delete(tab.path);
        autoSaveTimers.current.set(nextPath, timer);
      }

      return {
        ...tab,
        path: nextPath,
        name: nextName,
        node: {
          ...tab.node,
          id: nextPath,
          path: nextPath,
          name: nextName,
        },
      };
    }));

    setActiveTabPath(current => (
      current && isTargetPath(current) ? remapTabPath(current) : current
    ));
  }, []);

  const getTab = useCallback((path: string) => {
    return tabs.find(tab => tab.path === path);
  }, [tabs]);

  const isTabOpen = useCallback((path: string) => {
    return tabs.some(tab => tab.path === path);
  }, [tabs]);


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


    if (onAutoSave) {
      const existingTimer = autoSaveTimers.current.get(path);
      if (existingTimer) {
        clearTimeout(existingTimer);
      }

      const timer = setTimeout(() => {
        const latestRevision = tabsRef.current.find(tab => tab.path === path)?.revision;
        onAutoSave(path, content, latestRevision);
        if (autoSaveTimers.current.get(path) === timer) {
          autoSaveTimers.current.delete(path);
        }
      }, autoSaveDelay);

      autoSaveTimers.current.set(path, timer);
    }
  }, [onContentChange, onAutoSave, autoSaveDelay]);

  const saveTab = useCallback((
    path: string,
    savedContent: string,
    revision?: string | null,
    saveOptions: SaveTabOptions = {},
  ) => {
    const { clearAutoSaveTimer = true } = saveOptions;

    setTabs(prevTabs =>
      prevTabs.map(tab => {
        if (tab.path === path) {
          return {
            ...tab,
            originalContent: savedContent,
            isModified: tab.content !== savedContent,
            ...(revision !== undefined ? { revision } : {}),
          };
        }
        return tab;
      })
    );


    if (clearAutoSaveTimer) {
      const timer = autoSaveTimers.current.get(path);
      if (timer) {
        clearTimeout(timer);
        autoSaveTimers.current.delete(path);
      }
    }
  }, []);

  const saveAllTabs = useCallback((savedResultsByPath: Record<string, SavedTabResult | undefined> = {}) => {
    setTabs(prevTabs =>
      prevTabs.map(tab => {
        const savedResult = savedResultsByPath[tab.path];
        if (!savedResult) {
          return tab;
        }

        return {
          ...tab,
          originalContent: savedResult.savedContent,
          isModified: tab.content !== savedResult.savedContent,
          ...(savedResult.revision !== undefined ? { revision: savedResult.revision } : {}),
        };
      })
    );


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

    tabs,
    activeTabPath,
    activeTab,
    hasModifiedTabs,
    modifiedTabPaths,


    openTab,
    closeTab,
    closeAllTabs,
    closeOtherTabs,
    closeTabsForPath,
    setActiveTab,
    remapPath,
    getTab,
    isTabOpen,


    updateContent,
    saveTab,
    saveAllTabs,
    revertTab,
    isTabModified,


    nextTab,
    previousTab,
  };
}
