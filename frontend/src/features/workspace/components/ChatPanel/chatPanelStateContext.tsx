import React, { createContext, useContext, useMemo } from 'react';
import type { ChatPanelUIState, ChatPanelUIActions } from './hooks/useChatPanelState';
import { useChatPanelState } from './hooks/useChatPanelState';

const ChatPanelStateContext = createContext<[ChatPanelUIState, ChatPanelUIActions] | null>(null);

export const ChatPanelStateProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, actions] = useChatPanelState();
  const value = useMemo(() => [state, actions] as [ChatPanelUIState, ChatPanelUIActions], [state, actions]);
  return <ChatPanelStateContext.Provider value={value}>{children}</ChatPanelStateContext.Provider>;
};

export const useChatPanelStateContext = (): [ChatPanelUIState, ChatPanelUIActions] => {
  const context = useContext(ChatPanelStateContext);
  if (!context) {
    throw new Error('useChatPanelStateContext 必須在 ChatPanelStateProvider 內使用');
  }
  return context;
};
