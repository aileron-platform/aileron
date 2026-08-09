import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AiChatIntegrationProvider,
  type AiChatCodeReference,
  type AiChatHandoffInput,
  type AiChatHandoffRequest,
  type AiChatIntegrationValue,
} from '@/features/ai-chat/public';
import { ROUTES } from '@/shared/constants/routes';
import { createLogger } from '@/shared/services/logger';
import { useWorkspace } from '../../providers/WorkspaceContext';
import { syncCanvas } from '../../api/workspaceRuntimeApi';
import { WorkspaceFileChooserDialog } from './WorkspaceFileChooserDialog';
import { WorkspaceAiChatSelectionProvider } from './WorkspaceAiChatSelectionContext';

const logger = createLogger('WorkspaceAiChatIntegration');

export const WorkspaceAiChatIntegration: React.FC<React.PropsWithChildren> = ({ children }) => {
  const navigate = useNavigate();
  const { dispatch, permissions, workspaceRuntime } = useWorkspace();
  const [codeReference, setCodeReference] = useState<AiChatCodeReference | null>(null);
  const [companionRevealRequestId, setCompanionRevealRequestId] = useState(0);
  const [handoffQueue, setHandoffQueue] = useState<AiChatHandoffRequest[]>([]);
  const handoffResolversRef = useRef(new Map<string, {
    resolve: () => void;
    reject: (error: unknown) => void;
  }>());
  const canSelectCodeReference = permissions.canUseChat;

  useEffect(() => {
    setCodeReference(null);
    setCompanionRevealRequestId(0);
    setHandoffQueue((current) => {
      const retained = current.filter((request) => request.workspaceId === workspaceRuntime.workspaceId);
      for (const request of current) {
        if (request.workspaceId === workspaceRuntime.workspaceId) continue;
        handoffResolversRef.current.get(request.id)?.reject(new Error('Workspace changed before AI Chat handoff completed'));
        handoffResolversRef.current.delete(request.id);
      }
      return retained;
    });
  }, [workspaceRuntime.workspaceId]);

  useEffect(() => () => {
    for (const resolver of handoffResolversRef.current.values()) {
      resolver.reject(new Error('AI Chat integration unmounted before handoff completed'));
    }
    handoffResolversRef.current.clear();
  }, []);

  useEffect(() => {
    if (!canSelectCodeReference) {
      setCodeReference(null);
    }
  }, [canSelectCodeReference]);

  const selectCodeReference = useCallback((reference: AiChatCodeReference) => {
    if (!canSelectCodeReference) {
      return;
    }
    setCodeReference(reference);
    setCompanionRevealRequestId((current) => current + 1);
    dispatch({
      type: 'SET_COMPANION_ACTIVE_TAB',
      payload: 'ai-chat',
    });
  }, [canSelectCodeReference, dispatch]);

  const clearCodeReference = useCallback(() => {
    setCodeReference(null);
  }, []);

  const handoffToAiChat = useCallback((input: AiChatHandoffInput): Promise<void> => {
    if (!workspaceRuntime.workspaceId || !canSelectCodeReference) {
      return Promise.reject(new Error('AI Chat is unavailable for this workspace'));
    }

    const request: AiChatHandoffRequest = {
      ...input,
      id: crypto.randomUUID(),
      workspaceId: workspaceRuntime.workspaceId,
    };
    dispatch({
      type: 'SET_COMPANION_ACTIVE_TAB',
      payload: 'ai-chat',
    });
    setHandoffQueue((current) => [...current, request]);
    return new Promise<void>((resolve, reject) => {
      handoffResolversRef.current.set(request.id, { resolve, reject });
    });
  }, [canSelectCodeReference, dispatch, workspaceRuntime.workspaceId]);

  const completeHandoff = useCallback((handoffId: string) => {
    const resolver = handoffResolversRef.current.get(handoffId);
    handoffResolversRef.current.delete(handoffId);
    setHandoffQueue((current) => current.filter((request) => request.id !== handoffId));
    resolver?.resolve();
  }, []);

  const failHandoff = useCallback((handoffId: string, error: unknown) => {
    const resolver = handoffResolversRef.current.get(handoffId);
    handoffResolversRef.current.delete(handoffId);
    setHandoffQueue((current) => current.filter((request) => request.id !== handoffId));
    resolver?.reject(error);
  }, []);

  const openCanvas = useCallback(() => {
    dispatch({ type: 'SET_CURRENT_FEATURE', payload: 'canvas' });

    if (workspaceRuntime.workspaceId) {
      navigate(ROUTES.workspace.canvas(workspaceRuntime.workspaceId));
    }
    if (
      permissions.canWrite
      && workspaceRuntime.runtimeBaseUrl
      && workspaceRuntime.workspaceId
    ) {
      void syncCanvas(workspaceRuntime.runtimeBaseUrl, workspaceRuntime.workspaceId).catch((error) => {
        logger.error('Canvas sync failed from artifact preview', { error });
      });
    }
  }, [
    dispatch,
    navigate,
    permissions.canWrite,
    workspaceRuntime.runtimeBaseUrl,
    workspaceRuntime.workspaceId,
  ]);

  const value = useMemo<AiChatIntegrationValue>(() => ({
    workspaceId: workspaceRuntime.workspaceId,
    runtimeBaseUrl: workspaceRuntime.runtimeBaseUrl,
    fileChooser: WorkspaceFileChooserDialog,
    openCanvas,
    codeReference,
    clearCodeReference,
    pendingHandoff: handoffQueue[0] ?? null,
    handoffToAiChat,
    completeHandoff,
    failHandoff,
  }), [
    clearCodeReference,
    codeReference,
    completeHandoff,
    failHandoff,
    handoffQueue,
    handoffToAiChat,
    openCanvas,
    workspaceRuntime.runtimeBaseUrl,
    workspaceRuntime.workspaceId,
  ]);

  const selectionValue = useMemo(() => ({
    canSelectCodeReference,
    selectCodeReference,
    companionRevealRequestId,
  }), [canSelectCodeReference, companionRevealRequestId, selectCodeReference]);

  return (
    <WorkspaceAiChatSelectionProvider value={selectionValue}>
      <AiChatIntegrationProvider value={value}>
        {children}
      </AiChatIntegrationProvider>
    </WorkspaceAiChatSelectionProvider>
  );
};
