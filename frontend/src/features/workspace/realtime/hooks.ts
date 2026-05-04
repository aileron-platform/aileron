import { useCallback } from 'react';
import { useSyncExternalStore } from 'react';
import type { Terminal } from '@xterm/xterm';
import { useWorkspaceRealtimeContext } from './WorkspaceRealtimeContext';

export const useTerminalStream = () => {
  const context = useWorkspaceRealtimeContext();
  const state = useSyncExternalStore(
    context.terminal.subscribe,
    context.terminal.getSnapshot,
  );

  const connect = useCallback(
    (options?: { force?: boolean }) => {
      context.terminal.connect(options);
    },
    [context],
  );

  const disconnect = useCallback(
    (options?: { allowReconnect?: boolean }) => {
      context.terminal.disconnect(options);
    },
    [context],
  );

  const createTab = useCallback(
    (name: string, workspacePath?: string, size?: { cols: number; rows: number }) => {
      context.terminal.createTab(name, workspacePath, size);
    },
    [context],
  );

  const closeTab = useCallback(
    (tabId: string) => {
      context.terminal.closeTab(tabId);
    },
    [context],
  );

  const switchTab = useCallback(
    (tabId: string) => {
      context.terminal.switchTab(tabId);
    },
    [context],
  );

  const renameTab = useCallback(
    (tabId: string, name: string) => {
      context.terminal.renameTab(tabId, name);
    },
    [context],
  );

  const sendInput = useCallback(
    (tabId: string, data: string) => {
      context.terminal.sendInput(tabId, data);
    },
    [context],
  );

  const sendResize = useCallback(
    (tabId: string, cols: number, rows: number) => {
      context.terminal.sendResize(tabId, cols, rows);
    },
    [context],
  );

  const attachXterm = useCallback(
    (tabId: string, terminal: Terminal) => context.terminal.attachXterm(tabId, terminal),
    [context],
  );

  const clearHistory = useCallback(
    (tabId: string) => {
      context.terminal.clearHistory(tabId);
    },
    [context],
  );

  return {
    state,
    connect,
    disconnect,
    createTab,
    closeTab,
    switchTab,
    renameTab,
    sendInput,
    sendResize,
    attachXterm,
    clearHistory,
  };
};
