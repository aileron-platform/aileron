/**
 * useWorkspaceRuntime Hook
 * 管理 Workspace Runtime 的初始化與狀態
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  fetchDefaultWorkspaceId,
  resolveRuntimeBaseUrl,
  fetchWorkspaceDetail,
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
  webPreviewInternalPort: number;
  webPreviewExternalPort: number | null;
  webPreviewInternalUrl: string | null;
  webPreviewExternalUrl: string | null;
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

export const useWorkspaceRuntime = (initialWorkspaceId?: string): UseWorkspaceRuntimeReturn => {
  const [workspaceId, setWorkspaceId] = useState<string | null>(initialWorkspaceId ?? null);
  const [runtimeBaseUrl, setRuntimeBaseUrl] = useState<string | null>(null);
  const [terminalExternalUrl, setTerminalExternalUrl] = useState<string | null>(null);
  const [cliType, setCliType] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<RuntimeStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const runtimeUrlCache = useRef<Map<string, string>>(new Map());

  const initializeWorkspaceRuntime = useCallback(
    async (preferredWorkspaceId?: string, options?: { force?: boolean }) => {
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
        if (!targetId) {
          targetId = await fetchDefaultWorkspaceId();
        }
        if (!targetId) {
          throw new Error('找不到有效的工作區');
        }

        const resolvedUrl = await resolveRuntimeBaseUrl(targetId, runtimeUrlCache.current);

        // 獲取 workspace detail 以取得 cliType、terminalExternalUrl 和 runtimeStatus
        try {
          const workspaceDetail = await fetchWorkspaceDetail(targetId);
          setCliType(workspaceDetail.cliType || 'claude-code');
          setTerminalExternalUrl(workspaceDetail.runtimeStatus?.terminalExternalUrl || null);
          setRuntimeStatus(workspaceDetail.runtimeStatus || null);
        } catch (error) {
          // 使用預設值，但記錄錯誤以便監控
          // 這可能是暫時性網路問題或後端服務問題
          logger.error('Failed to fetch workspace detail, using defaults', { error, workspaceId: targetId });
          setCliType('claude-code');
          setTerminalExternalUrl(null);
          setRuntimeStatus(null);
          // 注意：不設置 error 狀態，因為使用預設值是可接受的降級
          // 使用者仍可使用基本功能，但 Chrome 預覽等高級功能可能不可用
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
    if (initialWorkspaceId && initialWorkspaceId !== workspaceId) {
      setWorkspaceId(initialWorkspaceId);
    }
  }, [initialWorkspaceId, workspaceId]);

  useEffect(() => {
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
