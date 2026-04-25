/**
 * useWorkspaceRuntime Hook
 * 管理 Workspace Runtime 的初始化與狀態
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  fetchDefaultWorkspaceId,
  resolveRuntimeBaseUrlWithDetail,
} from '../services/workspaceRuntimeApi';
import { createLogger } from '@/shared/services/logger';

const logger = createLogger('useWorkspaceRuntime');

export interface RuntimeStatus {
  status: string;
  containerId: string | null;
  internalUrl: string | null;
  externalUrl: string | null;
  internalPort: number;
  externalPort: number | null;
  lastSeen: string | null;
  terminalExternalPort: number | null;
  terminalExternalUrl: string | null;
  // Browser container fields
  browserContainerId: string | null;
  browserStatus: string;
  browserCreatedAt: string | null;
  browserLastSeen: string | null;
  // Browser WebRTC fields
  browserWebrtcInternalUrl: string | null;
  browserWebrtcExternalUrl: string | null;
  browserWebrtcInternalPort: number;
  browserWebrtcExternalPort: number | null;
  // Browser CDP fields
  browserCdpInternalPort: number;
  browserCdpExternalPort: number | null;
}

export interface UseWorkspaceRuntimeReturn {
  workspaceId: string | null;
  runtimeBaseUrl: string | null;
  terminalExternalUrl: string | null;
  cliType: string | null;
  runtimeStatus: RuntimeStatus | null;
  isLoading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  changeWorkspace: (workspaceId: string) => Promise<void>;
}

export const useWorkspaceRuntime = (initialWorkspaceId?: string | null): UseWorkspaceRuntimeReturn => {
  const [workspaceId, setWorkspaceId] = useState<string | null>(initialWorkspaceId ?? null);
  const [runtimeBaseUrl, setRuntimeBaseUrl] = useState<string | null>(null);
  const [terminalExternalUrl, setTerminalExternalUrl] = useState<string | null>(null);
  const [cliType, setCliType] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const runtimeUrlCache = useRef<Map<string, string>>(new Map());

  const resetRuntimeState = useCallback((nextWorkspaceId: string | null) => {
    setWorkspaceId(nextWorkspaceId);
    setRuntimeBaseUrl(null);
    setTerminalExternalUrl(null);
    setCliType(null);
    setRuntimeStatus(null);
    setError(null);
  }, []);

  const initializeWorkspaceRuntime = useCallback(
    async (preferredWorkspaceId?: string | null, options?: { force?: boolean }) => {
      if (
        !options?.force &&
        !preferredWorkspaceId &&
        workspaceId &&
        runtimeBaseUrl
      ) {
        return;
      }

      setIsLoading(true);
      try {
        let targetId = preferredWorkspaceId ?? workspaceId ?? null;
        if (preferredWorkspaceId === null) {
          resetRuntimeState(null);
          return;
        }
        if (!targetId) {
          targetId = await fetchDefaultWorkspaceId();
        }
        if (!targetId) {
          throw new Error('找不到有效的工作區');
        }

        const { url: resolvedUrl, detail: workspaceDetail } = await resolveRuntimeBaseUrlWithDetail(
          targetId,
          runtimeUrlCache.current
        );

        if (workspaceDetail) {
          setCliType(workspaceDetail.cliType || 'claude-code');
          setTerminalExternalUrl(workspaceDetail.runtimeStatus?.terminalExternalUrl || null);
          setRuntimeStatus(workspaceDetail.runtimeStatus || null);
        } else {
          setCliType('claude-code');
          setTerminalExternalUrl(null);
          setRuntimeStatus(null);
        }

        setWorkspaceId(targetId);
        setRuntimeBaseUrl(resolvedUrl);
        setError(null);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Workspace Runtime 初始化失敗';
        setError(message);
        setRuntimeBaseUrl(null);
        setTerminalExternalUrl(null);
        setCliType(null);
        setRuntimeStatus(null);
      } finally {
        setIsLoading(false);
      }
    },
    [workspaceId, runtimeBaseUrl]
  );

  useEffect(() => {
    const nextWorkspaceId = initialWorkspaceId ?? null;
    if (nextWorkspaceId === workspaceId) {
      return;
    }

    resetRuntimeState(nextWorkspaceId);
  }, [initialWorkspaceId, resetRuntimeState, workspaceId]);

  useEffect(() => {
    if (initialWorkspaceId === null) {
      return;
    }

    if (initialWorkspaceId === undefined && workspaceId === null) {
      return;
    }

    initializeWorkspaceRuntime(initialWorkspaceId);
  }, [initialWorkspaceId, initializeWorkspaceRuntime]);

  const reload = useCallback(async () => {
    const targetId = workspaceId ?? initialWorkspaceId ?? undefined;
    if (targetId) {
      runtimeUrlCache.current.delete(targetId);
    }
    await initializeWorkspaceRuntime(targetId, { force: true });
  }, [workspaceId, initialWorkspaceId, initializeWorkspaceRuntime]);

  const changeWorkspace = useCallback(
    async (nextWorkspaceId: string) => {
      runtimeUrlCache.current.delete(nextWorkspaceId);
      await initializeWorkspaceRuntime(nextWorkspaceId, { force: true });
    },
    [initializeWorkspaceRuntime]
  );

  return {
    workspaceId,
    runtimeBaseUrl,
    terminalExternalUrl,
    cliType,
    runtimeStatus,
    isLoading,
    error,
    reload,
    changeWorkspace,
  };
};
