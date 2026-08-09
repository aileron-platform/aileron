import { useCallback, useMemo, useState } from 'react';
import type { FileTreeNode } from '../types';
import type { FileViewerWorkbenchTab } from './types';

export interface UseFileViewerTabsReturn {
  tabs: FileViewerWorkbenchTab[];
  activeTabId: string | null;
  activeTab: FileViewerWorkbenchTab | null;
  openFile: (node: FileTreeNode, content: string) => void;
  replaceFileContent: (path: string, content: string, readability?: Pick<FileViewerWorkbenchTab, 'readable' | 'unreadableReason'>) => void;
  setActiveTabId: (id: string | null) => void;
  applyTabsChange: (nextTabs: FileViewerWorkbenchTab[]) => void;
  renamePath: (oldPath: string, newPath: string, newName: string) => void;
  removePaths: (paths: string[]) => void;
}

const isPathUnder = (id: string, base: string): boolean => (
  id === base || id.startsWith(`${base}/`)
);

export const useFileViewerTabs = (): UseFileViewerTabsReturn => {
  const [tabs, setTabs] = useState<FileViewerWorkbenchTab[]>([]);
  const [activeTabId, setActiveTabIdState] = useState<string | null>(null);

  const setActiveTabId = useCallback((id: string | null) => {
    setActiveTabIdState(id);
  }, []);

  const openFile = useCallback((node: FileTreeNode, content: string) => {
    setTabs(prev => {
      if (prev.some(tab => tab.id === node.path)) {
        return prev;
      }
      return [
        ...prev,
        {
          id: node.path,
          path: node.path,
          name: node.name,
          content,
          originalContent: content,
          isModified: false,
        },
      ];
    });
    setActiveTabIdState(node.path);
  }, []);

  const replaceFileContent = useCallback((
    path: string,
    content: string,
    readability?: Pick<FileViewerWorkbenchTab, 'readable' | 'unreadableReason'>,
  ) => {
    setTabs(prev => prev.map(tab => (
      tab.path === path
        ? {
            ...tab,
            content,
            originalContent: content,
            isModified: false,
            readable: readability?.readable,
            unreadableReason: readability?.unreadableReason,
          }
        : tab
    )));
  }, []);

  const applyTabsChange = useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    setTabs(nextTabs);
    setActiveTabIdState(prev => {
      if (prev && nextTabs.some(tab => tab.id === prev)) {
        return prev;
      }
      const fallback = nextTabs[nextTabs.length - 1];
      return fallback ? fallback.id : null;
    });
  }, []);

  const renamePath = useCallback((oldPath: string, newPath: string, newName: string) => {
    setTabs(prev => prev.map(tab => {
      if (tab.id === oldPath) {
        return { ...tab, id: newPath, path: newPath, name: newName };
      }
      if (tab.path.startsWith(`${oldPath}/`)) {
        const nextTabPath = tab.path.replace(oldPath, newPath);
        return { ...tab, id: nextTabPath, path: nextTabPath };
      }
      return tab;
    }));
    setActiveTabIdState(prev => {
      if (!prev) return prev;
      if (prev === oldPath) return newPath;
      if (prev.startsWith(`${oldPath}/`)) return prev.replace(oldPath, newPath);
      return prev;
    });
  }, []);

  const removePaths = useCallback((paths: string[]) => {
    if (!paths.length) return;
    const isAffected = (id: string) => paths.some(path => isPathUnder(id, path));
    setTabs(prev => prev.filter(tab => !isAffected(tab.id)));
    setActiveTabIdState(prev => (prev && isAffected(prev) ? null : prev));
  }, []);

  const activeTab = useMemo(
    () => tabs.find(tab => tab.id === activeTabId) ?? null,
    [activeTabId, tabs],
  );

  return {
    tabs,
    activeTabId,
    activeTab,
    openFile,
    replaceFileContent,
    setActiveTabId,
    applyTabsChange,
    renamePath,
    removePaths,
  };
};
