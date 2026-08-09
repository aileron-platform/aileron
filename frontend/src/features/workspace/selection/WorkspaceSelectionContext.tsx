import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import {
  readSelectedWorkspaceId,
  writeSelectedWorkspaceId,
} from './workspaceSelectionStorage';

interface WorkspaceSelectionContextValue {
  selectedWorkspaceId: string | null;
  setSelectedWorkspaceId: (workspaceId: string | null) => void;
}

const WorkspaceSelectionContext = createContext<WorkspaceSelectionContextValue | undefined>(undefined);

export const WorkspaceSelectionProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  const [selectedWorkspaceId, setSelectedWorkspaceIdState] = useState(readSelectedWorkspaceId);

  const setSelectedWorkspaceId = useCallback((workspaceId: string | null) => {
    writeSelectedWorkspaceId(workspaceId);
    setSelectedWorkspaceIdState(workspaceId);
  }, []);

  const value = useMemo<WorkspaceSelectionContextValue>(() => ({
    selectedWorkspaceId,
    setSelectedWorkspaceId,
  }), [selectedWorkspaceId, setSelectedWorkspaceId]);

  return (
    <WorkspaceSelectionContext.Provider value={value}>
      {children}
    </WorkspaceSelectionContext.Provider>
  );
};

export const useWorkspaceSelection = (): WorkspaceSelectionContextValue => {
  const context = useContext(WorkspaceSelectionContext);
  if (!context) {
    throw new Error('useWorkspaceSelection must be used within a WorkspaceSelectionProvider');
  }
  return context;
};

export const useOptionalWorkspaceSelection = (): WorkspaceSelectionContextValue | undefined => (
  useContext(WorkspaceSelectionContext)
);
