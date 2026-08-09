import { createContext, useContext } from 'react';

interface ToolResultContextValue {
  workspaceId: string;
  threadId: string;
  runtimeBaseUrl?: string | null;
}

export const ToolResultContext = createContext<ToolResultContextValue | null>(null);

export const useToolResultContext = (): ToolResultContextValue | null =>
  useContext(ToolResultContext);
