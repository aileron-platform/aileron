import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useWorkspace } from '../../../providers/WorkspaceProvider';
import type { ClaudeDocument } from '../data';
import { claudeCodeApi } from '../services/claudeCodeApi';

type DocumentCollectionState = {
  items: ClaudeDocument[];
  loading: boolean;
  error: string | null;
  selectedId: string | null;
  loaded?: boolean;
};

type DocumentCollectionController = DocumentCollectionState & {
  select: (id: string | null) => void;
  refresh: () => Promise<void>;
  create: (document: ClaudeDocument) => Promise<ClaudeDocument>;
  update: (document: ClaudeDocument) => Promise<ClaudeDocument>;
  remove: (id: string) => Promise<void>;
};

interface ClaudeCodeContextValue {
  slashCommands: DocumentCollectionController;
  outputStyles: DocumentCollectionController;
  subagents: DocumentCollectionController;
  memory: Omit<DocumentCollectionController, 'create'>;
}

const createInitialState = (): DocumentCollectionState => ({
  items: [],
  loading: false,
  error: null,
  selectedId: null,
  loaded: false,
});

export const ClaudeCodeContext = createContext<ClaudeCodeContextValue | null>(null);

interface ClaudeCodeProviderProps {
  isActive: boolean;
  activeSubView?: string | null;
  children: React.ReactNode;
}

const useSortedDocuments = () =>
  useCallback(
    (documents: ClaudeDocument[]) => [...documents].sort((a, b) => a.title.localeCompare(b.title)),
    [],
  );

export const ClaudeCodeProvider: React.FC<ClaudeCodeProviderProps> = ({ isActive, activeSubView, children }) => {
  const { workspaceRuntime } = useWorkspace();
  const runtimeBaseUrl = workspaceRuntime.runtimeBaseUrl;
  const workspaceId = workspaceRuntime.workspaceId;
  const runtimeError = workspaceRuntime.error;
  const workspaceKey = runtimeBaseUrl && workspaceId ? `${runtimeBaseUrl}:${workspaceId}` : null;
  const previousWorkspaceKey = useRef<string | null>(null);

  const sortDocuments = useSortedDocuments();

  const [slashCommands, setSlashCommands] = useState<DocumentCollectionState>(createInitialState);
  const [outputStyles, setOutputStyles] = useState<DocumentCollectionState>(createInitialState);
  const [subagents, setSubagents] = useState<DocumentCollectionState>(createInitialState);
  const [memory, setMemory] = useState<DocumentCollectionState>(createInitialState);

  const ensureRuntimeReady = useCallback(() => {
    if (!runtimeBaseUrl || !workspaceId) {
      throw new Error(runtimeError ?? 'Workspace Runtime 尚未就緒');
    }
    return { runtimeBaseUrl, workspaceId } as const;
  }, [runtimeBaseUrl, workspaceId, runtimeError]);

  const resetCollections = useCallback(() => {
    setSlashCommands(createInitialState());
    setOutputStyles(createInitialState());
    setSubagents(createInitialState());
    setMemory(createInitialState());
  }, []);

  useEffect(() => {
    if (previousWorkspaceKey.current !== workspaceKey) {
      previousWorkspaceKey.current = workspaceKey;
      resetCollections();
    }
  }, [workspaceKey, resetCollections]);

  const refreshSlashCommands = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId) {
      setSlashCommands(createInitialState());
      return;
    }
    const requestWorkspaceKey = workspaceKey;
    setSlashCommands((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const documents = await claudeCodeApi.listSlashCommands(runtimeBaseUrl, workspaceId);
      if (previousWorkspaceKey.current !== requestWorkspaceKey) {
        return;
      }
      setSlashCommands((prev) => {
        const sorted = sortDocuments(documents);
        const nextSelected = prev.selectedId && sorted.some((doc) => doc.id === prev.selectedId)
          ? prev.selectedId
          : sorted[0]?.id ?? null;
        return { items: sorted, loading: false, error: null, selectedId: nextSelected, loaded: true };
      });
    } catch (error) {
      if (previousWorkspaceKey.current !== requestWorkspaceKey) {
        return;
      }
      const message = error instanceof Error ? error.message : '載入 Slash Commands 失敗';
      setSlashCommands((prev) => ({ ...prev, loading: false, error: message, loaded: true }));
    }
  }, [runtimeBaseUrl, workspaceId, workspaceKey, sortDocuments]);

  const refreshOutputStyles = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId) {
      setOutputStyles(createInitialState());
      return;
    }
    const requestWorkspaceKey = workspaceKey;
    setOutputStyles((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const documents = await claudeCodeApi.listOutputStyles(runtimeBaseUrl, workspaceId);
      if (previousWorkspaceKey.current !== requestWorkspaceKey) {
        return;
      }
      setOutputStyles((prev) => {
        const sorted = sortDocuments(documents);
        const nextSelected = prev.selectedId && sorted.some((doc) => doc.id === prev.selectedId)
          ? prev.selectedId
          : sorted[0]?.id ?? null;
        return { items: sorted, loading: false, error: null, selectedId: nextSelected, loaded: true };
      });
    } catch (error) {
      if (previousWorkspaceKey.current !== requestWorkspaceKey) {
        return;
      }
      const message = error instanceof Error ? error.message : '載入 Output Styles 失敗';
      setOutputStyles((prev) => ({ ...prev, loading: false, error: message, loaded: true }));
    }
  }, [runtimeBaseUrl, workspaceId, workspaceKey, sortDocuments]);

  const refreshSubagents = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId) {
      setSubagents(createInitialState());
      return;
    }
    const requestWorkspaceKey = workspaceKey;
    setSubagents((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const documents = await claudeCodeApi.listSubagents(runtimeBaseUrl, workspaceId);
      if (previousWorkspaceKey.current !== requestWorkspaceKey) {
        return;
      }
      setSubagents((prev) => {
        const sorted = sortDocuments(documents);
        const nextSelected = prev.selectedId && sorted.some((doc) => doc.id === prev.selectedId)
          ? prev.selectedId
          : sorted[0]?.id ?? null;
        return { items: sorted, loading: false, error: null, selectedId: nextSelected, loaded: true };
      });
    } catch (error) {
      if (previousWorkspaceKey.current !== requestWorkspaceKey) {
        return;
      }
      const message = error instanceof Error ? error.message : '載入 Subagents 失敗';
      setSubagents((prev) => ({ ...prev, loading: false, error: message, loaded: true }));
    }
  }, [runtimeBaseUrl, workspaceId, workspaceKey, sortDocuments]);

  const refreshMemory = useCallback(async () => {
    if (!runtimeBaseUrl || !workspaceId) {
      setMemory(createInitialState());
      return;
    }
    const requestWorkspaceKey = workspaceKey;
    setMemory((prev) => ({ ...prev, loading: true, error: null }));
    try {
      const documents = await claudeCodeApi.listMemoryDocuments(runtimeBaseUrl, workspaceId);
      if (previousWorkspaceKey.current !== requestWorkspaceKey) {
        return;
      }
      setMemory((prev) => {
        const sorted = sortDocuments(documents);
        const nextSelected = prev.selectedId && sorted.some((doc) => doc.id === prev.selectedId)
          ? prev.selectedId
          : sorted[0]?.id ?? null;
        return { items: sorted, loading: false, error: null, selectedId: nextSelected, loaded: true };
      });
    } catch (error) {
      if (previousWorkspaceKey.current !== requestWorkspaceKey) {
        return;
      }
      const message = error instanceof Error ? error.message : '載入 Memory 失敗';
      setMemory((prev) => ({ ...prev, loading: false, error: message, loaded: true }));
    }
  }, [runtimeBaseUrl, workspaceId, workspaceKey, sortDocuments]);

  const selectSlashCommand = useCallback((id: string | null) => {
    setSlashCommands((prev) => ({ ...prev, selectedId: id }));
  }, []);

  const selectOutputStyle = useCallback((id: string | null) => {
    setOutputStyles((prev) => ({ ...prev, selectedId: id }));
  }, []);

  const selectSubagent = useCallback((id: string | null) => {
    setSubagents((prev) => ({ ...prev, selectedId: id }));
  }, []);

  const selectMemory = useCallback((id: string | null) => {
    setMemory((prev) => ({ ...prev, selectedId: id }));
  }, []);

  const createSlashCommand = useCallback(
    async (document: ClaudeDocument) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const created = await claudeCodeApi.createSlashCommand(baseUrl, targetWorkspaceId, document);
        setSlashCommands((prev) => {
          const items = prev.items.some((item) => item.id === created.id)
            ? prev.items.map((item) => (item.id === created.id ? created : item))
            : [...prev.items, created];
          return {
            ...prev,
            items: sortDocuments(items),
            error: null,
            selectedId: created.id,
          };
        });
        return created;
      } catch (error) {
        const message = error instanceof Error ? error.message : '新增 Slash Command 失敗';
        setSlashCommands((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, sortDocuments],
  );

  const updateSlashCommand = useCallback(
    async (document: ClaudeDocument) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const updated = await claudeCodeApi.updateSlashCommand(baseUrl, targetWorkspaceId, document);
        setSlashCommands((prev) => ({
          ...prev,
          items: sortDocuments(prev.items.map((item) => (item.id === updated.id ? updated : item))),
          error: null,
        }));
        return updated;
      } catch (error) {
        const message = error instanceof Error ? error.message : '更新 Slash Command 失敗';
        setSlashCommands((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, sortDocuments],
  );

  const deleteSlashCommand = useCallback(
    async (id: string) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const target = slashCommands.items.find((item) => item.id === id);
        if (!target) {
          return;
        }
        await claudeCodeApi.deleteSlashCommand(baseUrl, targetWorkspaceId, target);
        setSlashCommands((prev) => {
          const items = prev.items.filter((item) => item.id !== id);
          const nextSelected = prev.selectedId === id ? items[0]?.id ?? null : prev.selectedId;
          return { ...prev, items, error: null, selectedId: nextSelected };
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : '刪除 Slash Command 失敗';
        setSlashCommands((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, slashCommands.items],
  );

  const createOutputStyle = useCallback(
    async (document: ClaudeDocument) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const created = await claudeCodeApi.createOutputStyle(baseUrl, targetWorkspaceId, document);
        setOutputStyles((prev) => {
          const items = prev.items.some((item) => item.id === created.id)
            ? prev.items.map((item) => (item.id === created.id ? created : item))
            : [...prev.items, created];
          return {
            ...prev,
            items: sortDocuments(items),
            error: null,
            selectedId: created.id,
          };
        });
        return created;
      } catch (error) {
        const message = error instanceof Error ? error.message : '新增 Output Style 失敗';
        setOutputStyles((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, sortDocuments],
  );

  const updateOutputStyle = useCallback(
    async (document: ClaudeDocument) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const updated = await claudeCodeApi.updateOutputStyle(baseUrl, targetWorkspaceId, document);
        setOutputStyles((prev) => ({
          ...prev,
          items: sortDocuments(prev.items.map((item) => (item.id === updated.id ? updated : item))),
          error: null,
        }));
        return updated;
      } catch (error) {
        const message = error instanceof Error ? error.message : '更新 Output Style 失敗';
        setOutputStyles((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, sortDocuments],
  );

  const deleteOutputStyle = useCallback(
    async (id: string) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const target = outputStyles.items.find((item) => item.id === id);
        if (!target) {
          return;
        }
        await claudeCodeApi.deleteOutputStyle(baseUrl, targetWorkspaceId, target);
        setOutputStyles((prev) => {
          const items = prev.items.filter((item) => item.id !== id);
          const nextSelected = prev.selectedId === id ? items[0]?.id ?? null : prev.selectedId;
          return { ...prev, items, error: null, selectedId: nextSelected };
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : '刪除 Output Style 失敗';
        setOutputStyles((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, outputStyles.items],
  );

  const createSubagent = useCallback(
    async (document: ClaudeDocument) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const created = await claudeCodeApi.createSubagent(baseUrl, targetWorkspaceId, document);
        setSubagents((prev) => {
          const items = prev.items.some((item) => item.id === created.id)
            ? prev.items.map((item) => (item.id === created.id ? created : item))
            : [...prev.items, created];
          return {
            ...prev,
            items: sortDocuments(items),
            error: null,
            selectedId: created.id,
          };
        });
        return created;
      } catch (error) {
        const message = error instanceof Error ? error.message : '新增 Subagent 失敗';
        setSubagents((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, sortDocuments],
  );

  const updateSubagent = useCallback(
    async (document: ClaudeDocument) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const updated = await claudeCodeApi.updateSubagent(baseUrl, targetWorkspaceId, document);
        setSubagents((prev) => ({
          ...prev,
          items: sortDocuments(prev.items.map((item) => (item.id === updated.id ? updated : item))),
          error: null,
        }));
        return updated;
      } catch (error) {
        const message = error instanceof Error ? error.message : '更新 Subagent 失敗';
        setSubagents((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, sortDocuments],
  );

  const deleteSubagent = useCallback(
    async (id: string) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const target = subagents.items.find((item) => item.id === id);
        if (!target) {
          return;
        }
        await claudeCodeApi.deleteSubagent(baseUrl, targetWorkspaceId, target);
        setSubagents((prev) => {
          const items = prev.items.filter((item) => item.id !== id);
          const nextSelected = prev.selectedId === id ? items[0]?.id ?? null : prev.selectedId;
          return { ...prev, items, error: null, selectedId: nextSelected };
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : '刪除 Subagent 失敗';
        setSubagents((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, subagents.items],
  );

  const updateMemoryDocument = useCallback(
    async (document: ClaudeDocument) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const updated = await claudeCodeApi.updateMemoryDocument(baseUrl, targetWorkspaceId, document);
        setMemory((prev) => ({
          ...prev,
          items: sortDocuments(prev.items.map((item) => (item.id === updated.id ? updated : item))),
          error: null,
        }));
        return updated;
      } catch (error) {
        const message = error instanceof Error ? error.message : '更新 Memory 檔案失敗';
        setMemory((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, sortDocuments],
  );

  const deleteMemoryDocument = useCallback(
    async (id: string) => {
      try {
        const { runtimeBaseUrl: baseUrl, workspaceId: targetWorkspaceId } = ensureRuntimeReady();
        const target = memory.items.find((item) => item.id === id);
        if (!target) {
          return;
        }
        await claudeCodeApi.deleteMemoryDocument(baseUrl, targetWorkspaceId, target);
        setMemory((prev) => {
          const items = prev.items.filter((item) => item.id !== id);
          const nextSelected = prev.selectedId === id ? items[0]?.id ?? null : prev.selectedId;
          return { ...prev, items, error: null, selectedId: nextSelected };
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : '刪除 Memory 檔案失敗';
        setMemory((prev) => ({ ...prev, error: message }));
        throw error instanceof Error ? error : new Error(message);
      }
    },
    [ensureRuntimeReady, memory.items],
  );

  useEffect(() => {
    if (!isActive) {
      return;
    }
    if (!runtimeBaseUrl || !workspaceId) {
      return;
    }
    if (activeSubView === 'slash-commands' && !slashCommands.loaded && !slashCommands.loading) {
      void refreshSlashCommands();
      return;
    }
    if (activeSubView === 'output-styles' && !outputStyles.loaded && !outputStyles.loading) {
      void refreshOutputStyles();
      return;
    }
    if (activeSubView === 'subagents' && !subagents.loaded && !subagents.loading) {
      void refreshSubagents();
      return;
    }
    if (activeSubView === 'memory' && !memory.loaded && !memory.loading) {
      void refreshMemory();
    }
  }, [
    isActive,
    activeSubView,
    runtimeBaseUrl,
    workspaceId,
    slashCommands.loaded,
    slashCommands.loading,
    outputStyles.loaded,
    outputStyles.loading,
    subagents.loaded,
    subagents.loading,
    memory.loaded,
    memory.loading,
    refreshSlashCommands,
    refreshOutputStyles,
    refreshSubagents,
    refreshMemory,
  ]);

  const value = useMemo<ClaudeCodeContextValue>(() => ({
    slashCommands: {
      ...slashCommands,
      select: selectSlashCommand,
      refresh: refreshSlashCommands,
      create: createSlashCommand,
      update: updateSlashCommand,
      remove: deleteSlashCommand,
    },
    outputStyles: {
      ...outputStyles,
      select: selectOutputStyle,
      refresh: refreshOutputStyles,
      create: createOutputStyle,
      update: updateOutputStyle,
      remove: deleteOutputStyle,
    },
    subagents: {
      ...subagents,
      select: selectSubagent,
      refresh: refreshSubagents,
      create: createSubagent,
      update: updateSubagent,
      remove: deleteSubagent,
    },
    memory: {
      ...memory,
      select: selectMemory,
      refresh: refreshMemory,
      update: updateMemoryDocument,
      remove: deleteMemoryDocument,
    },
  }), [
    slashCommands,
    selectSlashCommand,
    refreshSlashCommands,
    createSlashCommand,
    updateSlashCommand,
    deleteSlashCommand,
    outputStyles,
    selectOutputStyle,
    refreshOutputStyles,
    createOutputStyle,
    updateOutputStyle,
    deleteOutputStyle,
    subagents,
    selectSubagent,
    refreshSubagents,
    createSubagent,
    updateSubagent,
    deleteSubagent,
    memory,
    selectMemory,
    refreshMemory,
    updateMemoryDocument,
    deleteMemoryDocument,
  ]);

  return <ClaudeCodeContext.Provider value={value}>{children}</ClaudeCodeContext.Provider>;
};

export const useClaudeCode = (): ClaudeCodeContextValue => {
  const context = useContext(ClaudeCodeContext);
  if (!context) {
    throw new Error(
      'useClaudeCode 必須在 ClaudeCodeProvider 中使用。' +
      '請確認組件層級結構：ClaudeCodeProvider > ... > useClaudeCode()'
    );
  }
  return context;
};
