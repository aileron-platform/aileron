export type TerminalConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  | 'closed'
  | 'error';

export interface TerminalHistoryEntry {
  id: string;
  data: string;
  seq?: number;
}

export interface TerminalTabMetadata {
  tab_id: string;
  session_id: string;
  name: string;
  workspace_path: string;
  cols: number;
  rows: number;
  created_at: number;
  last_active_at: number;
  status: 'running' | 'exited';
  exit_code?: number | null;
}

export interface TerminalTab {
  tabId: string;
  sessionId: string | null;
  name: string;
  history: TerminalHistoryEntry[];
  lastActivityAt: number | null;
  workspacePath?: string;
  cols?: number;
  rows?: number;
  createdAt?: number;
  status?: 'running' | 'exited';
  exitCode?: number | null;
  lastOutputSeq: number;
}

export interface TerminalState {
  tabs: TerminalTab[];
  activeTabId: string | null;
  status: TerminalConnectionStatus;
  error?: string;
  clientId: string | null;
  isSynced: boolean;
}

export type TerminalStoreListener = () => void;

export interface TerminalStore {
  getSnapshot: () => TerminalState;
  subscribe: (listener: TerminalStoreListener) => () => void;
  setStatus: (status: TerminalConnectionStatus, error?: string) => void;
  setClientId: (clientId: string | null) => void;
  upsertTab: (metadata: TerminalTabMetadata) => void;
  applyTabList: (tabs: TerminalTabMetadata[]) => void;
  closeTab: (tabId: string) => void;
  switchTab: (tabId: string) => void;
  appendOutput: (tabId: string, data: string, seq?: number) => void;
  updateTabSession: (tabId: string, sessionId: string) => void;
  renameTab: (tabId: string, name: string) => void;
  setSynced: (isSynced: boolean) => void;
  reset: () => void;
  clearHistory: (tabId: string) => void;
  getActiveTab: () => TerminalTab | null;
}

const MAX_HISTORY_LENGTH = 2_000;
const HISTORY_TRIM_CHUNK = 200;

const createHistoryEntryId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `terminal-entry-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const INITIAL_STATE: TerminalState = {
  tabs: [],
  activeTabId: null,
  status: 'idle',
  clientId: null,
  isSynced: false,
};

export const createTerminalStore = (): TerminalStore => {
  let state: TerminalState = { ...INITIAL_STATE };
  const listeners = new Set<TerminalStoreListener>();

  const notify = () => {
    listeners.forEach((listener) => listener());
  };

  const setState = (partial: Partial<TerminalState>) => {
    state = { ...state, ...partial };
    notify();
  };

  const findTab = (tabId: string): TerminalTab | undefined => {
    return state.tabs.find((tab) => tab.tabId === tabId);
  };

  const toTerminalTab = (
    metadata: TerminalTabMetadata,
    existing?: TerminalTab,
  ): TerminalTab => ({
    tabId: metadata.tab_id,
    sessionId: metadata.session_id,
    name: metadata.name,
    history: existing?.history ?? [],
    lastActivityAt: metadata.last_active_at ? metadata.last_active_at * 1000 : existing?.lastActivityAt ?? Date.now(),
    workspacePath: metadata.workspace_path,
    cols: metadata.cols,
    rows: metadata.rows,
    createdAt: metadata.created_at,
    status: metadata.status,
    exitCode: metadata.exit_code ?? null,
    lastOutputSeq: existing?.lastOutputSeq ?? 0,
  });

  const sortTabs = (tabs: TerminalTab[]) => {
    return [...tabs].sort((a, b) => {
      const createdDiff = (a.createdAt ?? 0) - (b.createdAt ?? 0);
      if (createdDiff !== 0) return createdDiff;
      return a.tabId.localeCompare(b.tabId);
    });
  };

  const appendOutput = (tabId: string, data: string, seq?: number) => {
    const tabs = state.tabs.map((tab) => {
      if (tab.tabId !== tabId) return tab;

      let history = [...tab.history, { id: createHistoryEntryId(), data, seq }];
      if (history.length > MAX_HISTORY_LENGTH) {
        const trimCount = Math.max(history.length - MAX_HISTORY_LENGTH, HISTORY_TRIM_CHUNK);
        history = history.slice(trimCount);
      }

      return {
        ...tab,
        history,
        lastActivityAt: Date.now(),
        lastOutputSeq: seq ?? tab.lastOutputSeq,
      };
    });

    state = { ...state, tabs };
    notify();
  };

  const clearHistory = (tabId: string) => {
    const tabs = state.tabs.map((tab) =>
      tab.tabId === tabId ? { ...tab, history: [] } : tab
    );
    setState({ tabs });
  };

  return {
    getSnapshot: () => state,
    subscribe: (listener: TerminalStoreListener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    setStatus: (status: TerminalConnectionStatus, error?: string) => {
      setState({ status, error });
    },
    setClientId: (clientId: string | null) => {
      setState({ clientId });
    },
    upsertTab: (metadata: TerminalTabMetadata) => {
      const existing = state.tabs.find((tab) => tab.tabId === metadata.tab_id);
      const tabs = existing
        ? state.tabs.map((tab) => (tab.tabId === metadata.tab_id ? toTerminalTab(metadata, tab) : tab))
        : [...state.tabs, toTerminalTab(metadata)];
      setState({
        tabs: sortTabs(tabs),
        activeTabId: state.activeTabId || metadata.tab_id,
      });
    },
    applyTabList: (metadataTabs: TerminalTabMetadata[]) => {
      const nextTabs = metadataTabs.map((metadata) =>
        toTerminalTab(metadata, state.tabs.find((tab) => tab.tabId === metadata.tab_id)),
      );
      const activeTabId =
        state.activeTabId && nextTabs.some((tab) => tab.tabId === state.activeTabId)
          ? state.activeTabId
          : nextTabs[0]?.tabId ?? null;
      setState({
        tabs: sortTabs(nextTabs),
        activeTabId,
        isSynced: true,
      });
    },
    closeTab: (tabId: string) => {
      const tabs = state.tabs.filter((tab) => tab.tabId !== tabId);
      let activeTabId = state.activeTabId;

      if (activeTabId === tabId) {
        activeTabId = tabs.length > 0 ? tabs[0].tabId : null;
      }

      setState({ tabs, activeTabId });
    },
    switchTab: (tabId: string) => {
      if (findTab(tabId)) {
        setState({ activeTabId: tabId });
      }
    },
    updateTabSession: (tabId: string, sessionId: string) => {
      const tabs = state.tabs.map((tab) =>
        tab.tabId === tabId ? { ...tab, sessionId } : tab
      );
      setState({ tabs });
    },
    renameTab: (tabId: string, name: string) => {
      const tabs = state.tabs.map((tab) =>
        tab.tabId === tabId ? { ...tab, name } : tab
      );
      setState({ tabs });
    },
    setSynced: (isSynced: boolean) => {
      setState({ isSynced });
    },
    appendOutput,
    reset: () => {
      state = { ...INITIAL_STATE };
      notify();
    },
    clearHistory,
    getActiveTab: () => {
      if (!state.activeTabId) return null;
      return findTab(state.activeTabId) || null;
    },
  };
};

export type TerminalStoreType = ReturnType<typeof createTerminalStore>;
