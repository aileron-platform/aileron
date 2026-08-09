export type TerminalConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'open'
  | 'reconnecting'
  | 'closed'
  | 'error';

export interface TerminalTabMetadata {
  tab_id: string;
  session_id: string;
  working_directory: string;
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
  workingDirectory: string;
  lastActivityAt: number | null;
  cols?: number;
  rows?: number;
  createdAt?: number;
  status?: 'running' | 'exited';
  exitCode?: number | null;
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
  setSynced: (isSynced: boolean) => void;
  reset: () => void;
}

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
    workingDirectory: metadata.working_directory,
    lastActivityAt: metadata.last_active_at ? metadata.last_active_at * 1000 : existing?.lastActivityAt ?? Date.now(),
    cols: metadata.cols,
    rows: metadata.rows,
    createdAt: metadata.created_at,
    status: metadata.status,
    exitCode: metadata.exit_code ?? null,
  });

  const sortTabs = (tabs: TerminalTab[]) => {
    return [...tabs].sort((a, b) => {
      const createdDiff = (a.createdAt ?? 0) - (b.createdAt ?? 0);
      if (createdDiff !== 0) return createdDiff;
      return a.tabId.localeCompare(b.tabId);
    });
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
    setSynced: (isSynced: boolean) => {
      setState({ isSynced });
    },
    reset: () => {
      state = { ...INITIAL_STATE };
      notify();
    },
  };
};
