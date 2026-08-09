import React, { createContext, useContext } from 'react';
import type { TerminalRealtimeAPI } from './terminalRealtimeManager';

export interface WorkspaceRealtimeContextValue {
  terminal: TerminalRealtimeAPI;
}

export const WorkspaceRealtimeContext = createContext<WorkspaceRealtimeContextValue | null>(null);

export const useWorkspaceRealtimeContext = (): WorkspaceRealtimeContextValue => {
  const context = useContext(WorkspaceRealtimeContext);
  if (!context) {
    throw new Error('WorkspaceRealtimeContext has not been initialized.');
  }
  return context;
};
