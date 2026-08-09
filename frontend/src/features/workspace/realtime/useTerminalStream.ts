import { useCallback } from 'react';
import { useSyncExternalStore } from 'react';
import type { Terminal } from '@xterm/xterm';
import { useWorkspaceRealtimeContext } from './WorkspaceRealtimeContext';
import type { TerminalCreateRequest } from './terminalRealtimeManager';

export const useTerminalStream = () => {
  const context = useWorkspaceRealtimeContext();
  const state = useSyncExternalStore(
    context.terminal.subscribe,
    context.terminal.getSnapshot,
  );

  const ensureConnected = useCallback(() => {
    context.terminal.ensureConnected();
  }, [context]);

  const ensureDefaultTab = useCallback(
    (workingDirectory?: string, size?: { cols: number; rows: number }) => {
      context.terminal.ensureDefaultTab(workingDirectory, size);
    },
    [context],
  );

  const createTab = useCallback(
    (request?: TerminalCreateRequest) => {
      context.terminal.createTab(request);
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

  const clearTerminal = useCallback(
    (tabId: string) => {
      context.terminal.clearTerminal(tabId);
    },
    [context],
  );

  return {
    state,
    ensureConnected,
    ensureDefaultTab,
    createTab,
    closeTab,
    switchTab,
    sendInput,
    sendResize,
    attachXterm,
    clearTerminal,
  };
};
