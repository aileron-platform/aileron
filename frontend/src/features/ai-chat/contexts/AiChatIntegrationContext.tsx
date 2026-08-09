import React, { createContext, useContext } from 'react';
import type {
  AiChatHandoffInput,
  AiChatHandoffRequest,
} from '../model/chatHandoffModel';

export interface AiChatFileChooserProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onFileSelect: (path: string) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

export interface AiChatCodeReference {
  filePath: string;
  fileName: string;
  startLine: number;
  endLine: number;
}

export interface AiChatIntegrationValue {
  workspaceId: string | null;
  runtimeBaseUrl: string | null;
  fileChooser: React.ComponentType<AiChatFileChooserProps> | null;
  openCanvas: (() => void) | null;
  codeReference: AiChatCodeReference | null;
  clearCodeReference: (() => void) | null;
  pendingHandoff: AiChatHandoffRequest | null;
  handoffToAiChat: ((input: AiChatHandoffInput) => Promise<void>) | null;
  completeHandoff: ((handoffId: string) => void) | null;
  failHandoff: ((handoffId: string, error: unknown) => void) | null;
}

const DEFAULT_INTEGRATION: AiChatIntegrationValue = {
  workspaceId: null,
  runtimeBaseUrl: null,
  fileChooser: null,
  openCanvas: null,
  codeReference: null,
  clearCodeReference: null,
  pendingHandoff: null,
  handoffToAiChat: null,
  completeHandoff: null,
  failHandoff: null,
};

const AiChatIntegrationContext = createContext<AiChatIntegrationValue>(DEFAULT_INTEGRATION);

interface AiChatIntegrationProviderProps {
  children: React.ReactNode;
  value: AiChatIntegrationValue;
}

export const AiChatIntegrationProvider: React.FC<AiChatIntegrationProviderProps> = ({
  children,
  value,
}) => (
  <AiChatIntegrationContext.Provider value={value}>
    {children}
  </AiChatIntegrationContext.Provider>
);

export const useAiChatIntegration = (): AiChatIntegrationValue => (
  useContext(AiChatIntegrationContext)
);
