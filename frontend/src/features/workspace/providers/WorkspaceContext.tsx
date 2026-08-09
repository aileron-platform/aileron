/**
 */

import { createContext, useContext } from 'react';
import type { WorkspaceContextType } from './workspaceStateTypes';

export const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

// Hook for consuming context
export const useWorkspace = () => {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within WorkspaceProvider');
  }
  return context;
};
