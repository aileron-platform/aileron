import React, { useEffect, useMemo, useRef, useState } from 'react';
import { WorkspaceRealtimeContext } from './WorkspaceRealtimeContext';
import { WebSocketConnectionRegistry } from '@/shared/realtime/webSocketConnectionRegistry';
import { TerminalRealtimeManager } from './terminalRealtimeManager';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import {
  disposeAllTerminalInstances,
  disposeTerminalInstance,
} from './terminalInstanceRegistry';

const logger = createLogger('WorkspaceRealtimeProvider');

export interface WorkspaceRealtimeProviderProps {
  workspaceId: string | null;
  runtimeUrl?: string | null;
  children: React.ReactNode;
}

export const WorkspaceRealtimeProvider: React.FC<WorkspaceRealtimeProviderProps> = ({
  workspaceId,
  runtimeUrl,
  children,
}) => {
  const { t } = useI18n();
  const registryRef = useRef<WebSocketConnectionRegistry>();
  if (!registryRef.current) {
    registryRef.current = new WebSocketConnectionRegistry();
  }

  const [terminalManager] = useState(() => new TerminalRealtimeManager(
    registryRef.current!,
    t,
    { onTabClosed: disposeTerminalInstance },
  ));
  const terminalUrl = runtimeUrl
    ? `${runtimeUrl.replace(/\/+$/, '')}/ws/terminal`
    : null;
  const terminalBinding = useMemo(
    () => terminalManager.declareScope(
      workspaceId,
      terminalUrl,
    ),
    [terminalManager, terminalUrl, workspaceId],
  );
  // Seeded from the mount-time props (not null) so a fresh mount whose
  // workspaceId is already known is not mistaken for a scope change: a
  // child terminal can be created in the same commit (React runs child
  // effects before parent effects), and disposing it here would destroy
  // an instance that is still in use.
  const previousTerminalScopeRef = useRef<{
    workspaceId: string | null;
    terminalUrl: string | null;
  }>({
    workspaceId,
    terminalUrl,
  });

  useEffect(() => {
    logger.debug('Updating workspace', {
      workspaceId,
      terminalUrl,
    });
    const previous = previousTerminalScopeRef.current;
    if (
      previous.workspaceId !== workspaceId
      || previous.terminalUrl !== terminalUrl
    ) {
      disposeAllTerminalInstances();
      previousTerminalScopeRef.current = {
        workspaceId,
        terminalUrl,
      };
    }
    terminalBinding.activate();
  }, [terminalBinding, terminalUrl, workspaceId]);

  useEffect(() => {
    return () => {
      terminalManager.dispose();
      disposeAllTerminalInstances();
      registryRef.current?.dispose();
    };
  }, [terminalManager]);

  const value = useMemo(() => ({
    terminal: terminalBinding.api,
  }), [terminalBinding]);

  return (
    <WorkspaceRealtimeContext.Provider value={value}>
      {children}
    </WorkspaceRealtimeContext.Provider>
  );
};
