import React, { createContext, useContext } from 'react';
import type { AiChatCodeReference } from '@/features/ai-chat/public';

interface WorkspaceAiChatSelectionValue {
  canSelectCodeReference: boolean;
  selectCodeReference: (reference: AiChatCodeReference) => void;
  companionRevealRequestId: number;
}

const WorkspaceAiChatSelectionContext = createContext<WorkspaceAiChatSelectionValue | null>(null);

interface WorkspaceAiChatSelectionProviderProps {
  children: React.ReactNode;
  value: WorkspaceAiChatSelectionValue;
}

export const WorkspaceAiChatSelectionProvider: React.FC<WorkspaceAiChatSelectionProviderProps> = ({
  children,
  value,
}) => (
  <WorkspaceAiChatSelectionContext.Provider value={value}>
    {children}
  </WorkspaceAiChatSelectionContext.Provider>
);

export const useWorkspaceAiChatSelection = (): WorkspaceAiChatSelectionValue => {
  const value = useContext(WorkspaceAiChatSelectionContext);
  if (!value) {
    throw new Error('useWorkspaceAiChatSelection must be used within WorkspaceAiChatSelectionProvider');
  }
  return value;
};

export const useOptionalWorkspaceAiChatSelection = (): WorkspaceAiChatSelectionValue | null => (
  useContext(WorkspaceAiChatSelectionContext)
);
