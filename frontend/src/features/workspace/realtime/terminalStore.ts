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
}

export interface TerminalTab {
  tabId: string;
  sessionId: string | null;
  name: string;
  history: TerminalHistoryEntry[];
  lastActivityAt: number | null;
  workspacePath?: string;
}

export interface TerminalState {
  tabs: TerminalTab[];
  activeTabId: string | null;
  status: TerminalConnectionStatus;
  error?: string;
  clientId: string | null;
}

export type TerminalStoreListener = () => void;

export interface TerminalStore {
  getSnapshot: () => TerminalState;
  subscribe: (listener: TerminalStoreListener) => () => void;
  setStatus: (status: TerminalConnectionStatus, error?: string) => void;
  setClientId: (clientId: string | null) => void;
  createTab: (tabId: string, name: string, sessionId: string, workspacePath?: string) => void;
  closeTab: (tabId: string) => void;
  switchTab: (tabId: string) => void;
  appendOutput: (tabId: string, data: string) => void;
  updateTabSession: (tabId: string, sessionId: string) => void;
  renameTab: (tabId: string, name: string) => void;
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

  const appendOutput = (tabId: string, data: string) => {
    const tabs = state.tabs.map((tab) => {
      if (tab.tabId !== tabId) return tab;

      let history = [...tab.history, { id: createHistoryEntryId(), data }];
      if (history.length > MAX_HISTORY_LENGTH) {
        const trimCount = Math.max(history.length - MAX_HISTORY_LENGTH, HISTORY_TRIM_CHUNK);
        history = history.slice(trimCount);
      }

      return {
        ...tab,
        history,
        lastActivityAt: Date.now(),
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
    createTab: (tabId: string, name: string, sessionId: string, workspacePath?: string) => {
      const newTab: TerminalTab = {
        tabId,
        sessionId,
        name,
        history: [],
        lastActivityAt: Date.now(),
        workspacePath,
      };
      const tabs = [...state.tabs, newTab];
      setState({
        tabs,
        activeTabId: state.activeTabId || tabId,
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
