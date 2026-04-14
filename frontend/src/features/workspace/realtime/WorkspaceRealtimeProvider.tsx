import React, { useEffect, useMemo, useRef, useState } from 'react';
import { WorkspaceRealtimeContext } from './WorkspaceRealtimeContext';
import { WebSocketConnectionRegistry } from './core/websocketRegistry';
import { TerminalRealtimeManager } from './terminalRealtimeManager';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('WorkspaceRealtimeProvider');

export interface WorkspaceRealtimeProviderProps {
  workspaceId: string | null;
  runtimeBaseUrl: string | null;
  terminalExternalUrl?: string | null;
  children: React.ReactNode;
}

export const WorkspaceRealtimeProvider: React.FC<WorkspaceRealtimeProviderProps> = ({
  workspaceId,
  runtimeBaseUrl,
  terminalExternalUrl,
  children,
}) => {
  const { t } = useI18n();
  const registryRef = useRef<WebSocketConnectionRegistry>();
  if (!registryRef.current) {
    registryRef.current = new WebSocketConnectionRegistry();
  }

  const [terminalManager] = useState(() => new TerminalRealtimeManager(registryRef.current!, t));

  useEffect(() => {
    logger.debug('Updating workspace', {
      workspaceId,
      terminalExternalUrl,
      runtimeBaseUrl,
    });
    terminalManager.updateWorkspace(workspaceId, terminalExternalUrl || null);
    // terminalManager 是通過 useState 創建的，引用穩定，不需要放在依賴數組中
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId, runtimeBaseUrl, terminalExternalUrl]);

  useEffect(() => {
    return () => {
      terminalManager.dispose();
      registryRef.current?.dispose();
    };
  }, [terminalManager]);

  const value = useMemo(
    () => ({
      terminal: terminalManager.api,
    }),
    [terminalManager],
  );

  return (
    <WorkspaceRealtimeContext.Provider value={value}>
      {children}
    </WorkspaceRealtimeContext.Provider>
  );
};
