/**
 * WorkspaceContext 定義
 */

import { createContext, useContext } from 'react';
import type { WorkspaceContextType } from './workspaceState.types';

// Context 建立
export const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

// Hook for consuming context
export const useWorkspace = () => {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within WorkspaceProvider');
  }
  return context;
};

// Optional hook that returns undefined if not within WorkspaceProvider
export const useWorkspaceOptional = () => {
  return useContext(WorkspaceContext);
};

