import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { FileViewerWorkbenchAdapter, FileViewerWorkbenchTab } from './types';

export interface ManagedDocumentWorkbenchAdapter<TDocument> {
  getKey: (document: TDocument) => string;
  getName: (document: TDocument) => string;
  readFile: (document: TDocument) => Promise<string>;
  saveFile?: (document: TDocument, content: string) => Promise<void>;
  isWritable?: (document: TDocument) => boolean;
}

export type SkillsFileTreePersistenceAdapter<TDocument> = ManagedDocumentWorkbenchAdapter<TDocument>;

export interface UseManagedDocumentWorkbenchTabsOptions<TDocument> {
  adapter: ManagedDocumentWorkbenchAdapter<TDocument>;
}

export interface UseManagedDocumentWorkbenchTabsReturn<TDocument> {
  tabs: FileViewerWorkbenchTab[];
  activeTabId: string | null;
  activeTab: FileViewerWorkbenchTab | null;
  contents: Record<string, string>;
  openDocument: (document: TDocument) => void;
  setActiveTabId: (tabId: string | null) => void;
  applyTabsChange: (nextTabs: FileViewerWorkbenchTab[]) => void;
  renamePath: (oldPath: string, newPath: string, newName: string) => void;
  removePaths: (paths: string[]) => void;
  setDocumentContent: (path: string, content: string) => void;
  adapter: FileViewerWorkbenchAdapter;
  isPathWritable: (path: string) => boolean;
  isSavingActive: boolean;
  canSaveActive: boolean;
  getDocumentByPath: (path: string) => TDocument | undefined;
  getDocumentContent: (path: string) => string;
}

const isPathUnder = (path: string, base: string): boolean => (
  path === base || path.startsWith(`${base}/`)
);

const remapPath = (path: string, from: string, to: string): string => (
  path === from ? to : path.startsWith(`${from}/`) ? `${to}${path.slice(from.length)}` : path
);

export const useManagedDocumentWorkbenchTabs = <TDocument,>({
  adapter,
}: UseManagedDocumentWorkbenchTabsOptions<TDocument>): UseManagedDocumentWorkbenchTabsReturn<TDocument> => {
  const [documents, setDocuments] = useState<TDocument[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [contents, setContents] = useState<Record<string, string>>({});
  const [originalContents, setOriginalContents] = useState<Record<string, string>>({});
  const [loadingPaths, setLoadingPaths] = useState<string[]>([]);
  const [savingPaths, setSavingPaths] = useState<string[]>([]);

  const documentsRef = useRef(documents);
  const contentsRef = useRef(contents);
  const loadingPathsRef = useRef(new Set<string>());
  const savingPathsRef = useRef(savingPaths);

  useEffect(() => {
    documentsRef.current = documents;
  }, [documents]);

  useEffect(() => {
    contentsRef.current = contents;
  }, [contents]);

  useEffect(() => {
    loadingPathsRef.current = new Set(loadingPaths);
  }, [loadingPaths]);

  useEffect(() => {
    savingPathsRef.current = savingPaths;
  }, [savingPaths]);

  const getDocumentByPath = useCallback((path: string) => (
    documentsRef.current.find(document => adapter.getKey(document) === path)
  ), [adapter]);

  const loadDocument = useCallback(async (document: TDocument) => {
    const path = adapter.getKey(document);
    if (!path || loadingPathsRef.current.has(path)) return;

    loadingPathsRef.current.add(path);
    setLoadingPaths(prev => (prev.includes(path) ? prev : [...prev, path]));
    try {
      const content = await adapter.readFile(document);
      setContents(prev => ({ ...prev, [path]: content }));
      setOriginalContents(prev => ({ ...prev, [path]: content }));
    } finally {
      loadingPathsRef.current.delete(path);
      setLoadingPaths(prev => prev.filter(item => item !== path));
    }
  }, [adapter]);

  const openDocument = useCallback((document: TDocument) => {
    const path = adapter.getKey(document);
    if (!path) return;

    setDocuments(prev => (prev.some(item => adapter.getKey(item) === path) ? prev : [...prev, document]));
    setActiveTabId(path);

    if (contentsRef.current[path] === undefined) {
      void loadDocument(document);
    }
  }, [adapter, loadDocument]);

  const applyTabsChange = useCallback((nextTabs: FileViewerWorkbenchTab[]) => {
    const nextPaths = new Set(nextTabs.map(tab => tab.id));
    setDocuments(prev => {
      const documentsByPath = new Map(prev.map(document => [adapter.getKey(document), document]));
      return nextTabs
        .map(tab => documentsByPath.get(tab.id))
        .filter((document): document is TDocument => Boolean(document));
    });
    setContents(prev => {
      const nextContents: Record<string, string> = {};
      nextTabs.forEach(tab => {
        nextContents[tab.id] = tab.content;
      });
      return nextContents;
    });
    setOriginalContents(prev => {
      const nextOriginalContents: Record<string, string> = {};
      nextTabs.forEach(tab => {
        nextOriginalContents[tab.id] = tab.originalContent;
      });
      return nextOriginalContents;
    });
    setActiveTabId(current => {
      if (current && nextPaths.has(current)) return current;
      return nextTabs.at(-1)?.id ?? null;
    });
  }, [adapter]);

  const renamePath = useCallback((oldPath: string, newPath: string, newName: string) => {
    setDocuments(prev => prev.map(document => {
      const path = adapter.getKey(document);
      if (path === oldPath) {
        return { ...document, path: newPath, name: newName } as TDocument;
      }
      if (isPathUnder(path, oldPath)) {
        const nextPath = remapPath(path, oldPath, newPath);
        return { ...document, path: nextPath } as TDocument;
      }
      return document;
    }));
    setContents(prev => {
      const nextContents: Record<string, string> = {};
      Object.entries(prev).forEach(([path, value]) => {
        nextContents[remapPath(path, oldPath, newPath)] = value;
      });
      return nextContents;
    });
    setOriginalContents(prev => {
      const nextOriginalContents: Record<string, string> = {};
      Object.entries(prev).forEach(([path, value]) => {
        nextOriginalContents[remapPath(path, oldPath, newPath)] = value;
      });
      return nextOriginalContents;
    });
    setActiveTabId(current => {
      if (!current) return current;
      return remapPath(current, oldPath, newPath);
    });
  }, [adapter]);

  const removePaths = useCallback((paths: string[]) => {
    if (!paths.length) return;
    setDocuments(prev => prev.filter(document => {
      const path = adapter.getKey(document);
      return !paths.some(candidate => isPathUnder(path, candidate));
    }));
    setContents(prev => {
      const nextContents: Record<string, string> = {};
      Object.entries(prev).forEach(([path, value]) => {
        if (!paths.some(candidate => isPathUnder(path, candidate))) {
          nextContents[path] = value;
        }
      });
      return nextContents;
    });
    setOriginalContents(prev => {
      const nextOriginalContents: Record<string, string> = {};
      Object.entries(prev).forEach(([path, value]) => {
        if (!paths.some(candidate => isPathUnder(path, candidate))) {
          nextOriginalContents[path] = value;
        }
      });
      return nextOriginalContents;
    });
    setLoadingPaths(prev => prev.filter(path => !paths.some(candidate => isPathUnder(path, candidate))));
    setSavingPaths(prev => prev.filter(path => !paths.some(candidate => isPathUnder(path, candidate))));
    setActiveTabId(current => {
      if (!current) return current;
      return paths.some(candidate => isPathUnder(current, candidate)) ? null : current;
    });
  }, [adapter]);

  const setDocumentContent = useCallback((path: string, content: string) => {
    setContents(prev => ({ ...prev, [path]: content }));
    setOriginalContents(prev => (prev[path] === undefined ? { ...prev, [path]: content } : prev));
  }, []);

  const adapterBridge = useMemo<FileViewerWorkbenchAdapter>(() => ({
    readFile: async (path: string) => {
      if (contentsRef.current[path] !== undefined) {
        return contentsRef.current[path];
      }
      const document = getDocumentByPath(path);
      if (!document) return '';
      const content = await adapter.readFile(document);
      setContents(prev => ({ ...prev, [path]: content }));
      setOriginalContents(prev => ({ ...prev, [path]: content }));
      return content;
    },
    saveFile: adapter.saveFile
      ? async (path: string, content: string) => {
          const document = getDocumentByPath(path);
          if (!document) return;
          if (savingPathsRef.current.includes(path)) return;
          setSavingPaths(prev => (prev.includes(path) ? prev : [...prev, path]));
          try {
            await adapter.saveFile(document, content);
            setContents(prev => ({ ...prev, [path]: content }));
            setOriginalContents(prev => ({ ...prev, [path]: content }));
          } finally {
            setSavingPaths(prev => prev.filter(item => item !== path));
          }
        }
      : undefined,
  }), [adapter, getDocumentByPath]);

  const tabs = useMemo<FileViewerWorkbenchTab[]>(() => documents.map((document) => {
    const path = adapter.getKey(document);
    const name = adapter.getName(document);
    const content = contents[path] ?? '';
    const originalContent = originalContents[path] ?? '';
    return {
      id: path,
      path,
      name,
      content,
      originalContent,
      isModified: content !== originalContent,
      isLoading: loadingPaths.includes(path),
    };
  }), [adapter, contents, documents, loadingPaths, originalContents]);

  const activeTab = useMemo(
    () => tabs.find(tab => tab.id === activeTabId) ?? null,
    [activeTabId, tabs],
  );

  const isPathWritable = useCallback((path: string) => {
    const document = getDocumentByPath(path);
    if (!document) return false;
    return adapter.isWritable ? adapter.isWritable(document) : true;
  }, [adapter, getDocumentByPath]);

  const isSavingActive = activeTabId ? savingPaths.includes(activeTabId) : false;
  const canSaveActive = activeTab ? isPathWritable(activeTab.path) : false;

  return {
    tabs,
    activeTabId,
    activeTab,
    contents,
    openDocument,
    setActiveTabId,
    applyTabsChange,
    renamePath,
    removePaths,
    setDocumentContent,
    adapter: adapterBridge,
    isPathWritable,
    isSavingActive,
    canSaveActive,
    getDocumentByPath,
    getDocumentContent: (path: string) => contents[path] ?? '',
  };
};
