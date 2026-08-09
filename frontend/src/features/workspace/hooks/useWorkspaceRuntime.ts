/**
 * useWorkspaceRuntime Hook
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import {
  fetchDefaultWorkspaceId,
  resolveRuntimeBaseUrlWithDetail,
} from '../api/workspaceRuntimeApi';
import { createLogger } from '@/shared/services/logger';
import type { AgenticTool } from '@/shared/types/agenticTool';
import { AGENTIC_TOOLS, isAgenticTool } from '@/shared/types/agenticTool';
import type {
  BrowserConnectivityProjectionResponse,
  WorkspaceRuntimeStatus,
} from '../api/workspaceApiTypes';
import { isWorkspaceAuthorizationDenialCode } from '@/shared/authorization/authorizationErrorCodes';
import type { OperationId } from '@/shared/authorization/operationIds';
import type { ResourceAccessRole } from '@/shared/authorization/resourceAccessRole';
import {
  normalizeResourceAuthorization,
  type ResourceAccessSource,
} from '@/shared/authorization/resourceAuthorization';

const logger = createLogger('useWorkspaceRuntime');
const AGENTIC_TOOLS_UNAVAILABLE_ERROR = 'workspace.runtime.errors.agenticToolsUnavailable';
const WORKSPACE_AUTHORIZATION_UNAVAILABLE_ERROR =
  'common.authorization.accessDeniedDescription';
const NO_VALID_WORKSPACE_ERROR = 'common.error.workspaceRuntime.invalidWorkspaceErrorMessage';
const WORKSPACE_RUNTIME_INITIALIZATION_FAILED_ERROR =
  'common.error.workspaceRuntime.connectionFailed';

const normalizeWorkspaceDetailAgenticTools = (
  value: readonly string[] | null | undefined,
): AgenticTool[] => {
  const unique = new Set((value ?? []).filter(isAgenticTool));
  return AGENTIC_TOOLS.filter(tool => unique.has(tool));
};

export interface UseWorkspaceRuntimeReturn {
  workspaceId: string | null;
  workspaceName: string | null;
  runtimeBaseUrl: string | null;
  agenticTools: AgenticTool[];
  accessRole: ResourceAccessRole | null;
  accessSource: ResourceAccessSource | null;
  accessSources: ResourceAccessSource[];
  allowedOperations: OperationId[];
  runtimeStatus: WorkspaceRuntimeStatus | null;
  browserConnectivity: BrowserConnectivityProjectionResponse | null;
  isLoading: boolean;
  isAuthorizationResolved: boolean;
  error: string | null;
  errorCode: string | null;
  reload: () => Promise<void>;
  changeWorkspace: (workspaceId: string) => Promise<void>;
}

export const useWorkspaceRuntime = (initialWorkspaceId?: string | null): UseWorkspaceRuntimeReturn => {
  const [workspaceId, setWorkspaceId] = useState<string | null>(initialWorkspaceId ?? null);
  const [workspaceName, setWorkspaceName] = useState<string | null>(null);
  const [runtimeBaseUrl, setRuntimeBaseUrl] = useState<string | null>(null);
  const [agenticTools, setAgenticTools] = useState<AgenticTool[]>(['claude-code']);
  const [accessRole, setAccessRole] = useState<ResourceAccessRole | null>(null);
  const [accessSource, setAccessSource] = useState<ResourceAccessSource | null>(null);
  const [accessSources, setAccessSources] = useState<ResourceAccessSource[]>([]);
  const [allowedOperations, setAllowedOperations] = useState<OperationId[]>([]);
  const [runtimeStatus, setRuntimeStatus] = useState<WorkspaceRuntimeStatus | null>(null);
  const [browserConnectivity, setBrowserConnectivity] =
    useState<BrowserConnectivityProjectionResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isAuthorizationResolved, setIsAuthorizationResolved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const requestGenerationRef = useRef(0);
  const isMountedRef = useRef(true);

  const isCurrentRequest = useCallback(
    (requestGeneration: number) => (
      isMountedRef.current
      && requestGenerationRef.current === requestGeneration
    ),
    [],
  );

  const resetRuntimeState = useCallback((nextWorkspaceId: string | null) => {
    setWorkspaceId(nextWorkspaceId);
    setWorkspaceName(null);
    setRuntimeBaseUrl(null);
    setAgenticTools(['claude-code']);
    setAccessRole(null);
    setAccessSource(null);
    setAccessSources([]);
    setAllowedOperations([]);
    setRuntimeStatus(null);
    setBrowserConnectivity(null);
    setError(null);
    setErrorCode(null);
    setIsAuthorizationResolved(false);
  }, []);

  const initializeWorkspaceRuntime = useCallback(
    async (preferredWorkspaceId?: string | null, options?: { force?: boolean }) => {
      const requestedWorkspaceId = preferredWorkspaceId ?? workspaceId ?? null;
      const preserveConfirmedSnapshot = Boolean(
        options?.force
        && requestedWorkspaceId
        && requestedWorkspaceId === workspaceId
        && isAuthorizationResolved
        && accessRole
        && allowedOperations.length > 0,
      );
      if (
        !options?.force &&
        requestedWorkspaceId &&
        requestedWorkspaceId === workspaceId &&
        runtimeBaseUrl
      ) {
        return;
      }

      const requestGeneration = requestGenerationRef.current + 1;
      requestGenerationRef.current = requestGeneration;
      if (!isMountedRef.current) {
        return;
      }

      if (!preserveConfirmedSnapshot) {
        setIsLoading(true);
        setIsAuthorizationResolved(false);
        setAccessRole(null);
        setAccessSource(null);
        setAccessSources([]);
        setAllowedOperations([]);
      }
      try {
        let targetId = requestedWorkspaceId;
        if (preferredWorkspaceId === null) {
          if (isCurrentRequest(requestGeneration)) {
            resetRuntimeState(null);
          }
          return;
        }
        if (!targetId) {
          targetId = await fetchDefaultWorkspaceId();
        }
        if (!isCurrentRequest(requestGeneration)) {
          return;
        }
        if (!targetId) {
          throw new Error(NO_VALID_WORKSPACE_ERROR);
        }

        const { url: resolvedUrl, detail: workspaceDetail } =
          await resolveRuntimeBaseUrlWithDetail(targetId);
        if (!isCurrentRequest(requestGeneration)) {
          return;
        }

        if (workspaceDetail) {
          const authorization = normalizeResourceAuthorization(workspaceDetail);
          if (!authorization) {
            throw Object.assign(
              new Error(WORKSPACE_AUTHORIZATION_UNAVAILABLE_ERROR),
              { errorCode: 'WORKSPACE_ACCESS_DENIED' },
            );
          }
          const enabledTools = normalizeWorkspaceDetailAgenticTools(workspaceDetail.agenticTools);
          if (enabledTools.length === 0) {
            throw new Error(AGENTIC_TOOLS_UNAVAILABLE_ERROR);
          }
          setAgenticTools(enabledTools);
          setWorkspaceName(workspaceDetail.name);
          setAccessRole(authorization.accessRole);
          setAccessSource(authorization.accessSource);
          setAccessSources(authorization.accessSources);
          setAllowedOperations(authorization.allowedOperations);
          setRuntimeStatus(workspaceDetail.runtimeStatus || null);
          setBrowserConnectivity(workspaceDetail.browserConnectivity || null);
        } else if (!preserveConfirmedSnapshot) {
          throw Object.assign(
            new Error(WORKSPACE_AUTHORIZATION_UNAVAILABLE_ERROR),
            { errorCode: 'WORKSPACE_ACCESS_DENIED' },
          );
        }

        setWorkspaceId(targetId);
        setRuntimeBaseUrl(resolvedUrl);
        setError(null);
        setErrorCode(null);
      } catch (error) {
        const message = error instanceof Error
          ? error.message
          : WORKSPACE_RUNTIME_INITIALIZATION_FAILED_ERROR;
        const nextErrorCode = (
          error
          && typeof error === 'object'
          && 'errorCode' in error
          && typeof error.errorCode === 'string'
        )
          ? error.errorCode
          : null;
        if (!isCurrentRequest(requestGeneration)) {
          return;
        }
        if (
          preserveConfirmedSnapshot
          && !isWorkspaceAuthorizationDenialCode(nextErrorCode)
        ) {
          logger.warn('Workspace runtime background refresh failed; preserving confirmed snapshot', {
            error,
            workspaceId: requestedWorkspaceId,
          });
          return;
        }
        setError(message);
        setErrorCode(nextErrorCode);
        setRuntimeBaseUrl(null);
        setAgenticTools([]);
        setWorkspaceName(null);
        setAccessRole(null);
        setAccessSource(null);
        setAccessSources([]);
        setAllowedOperations([]);
        setRuntimeStatus(null);
        setBrowserConnectivity(null);
      } finally {
        if (isCurrentRequest(requestGeneration)) {
          setIsLoading(false);
          setIsAuthorizationResolved(true);
        }
      }
    },
    [
      accessRole,
      allowedOperations.length,
      workspaceId,
      runtimeBaseUrl,
      isAuthorizationResolved,
      isCurrentRequest,
      resetRuntimeState,
    ]
  );

  const initializeWorkspaceRuntimeRef = useRef(initializeWorkspaceRuntime);

  useEffect(() => {
    initializeWorkspaceRuntimeRef.current = initializeWorkspaceRuntime;
  }, [initializeWorkspaceRuntime]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      requestGenerationRef.current += 1;
    };
  }, []);

  useEffect(() => {
    const nextWorkspaceId = initialWorkspaceId ?? null;
    if (nextWorkspaceId === workspaceId) {
      return;
    }

    requestGenerationRef.current += 1;
    resetRuntimeState(nextWorkspaceId);
  }, [initialWorkspaceId, resetRuntimeState, workspaceId]);

  useEffect(() => {
    if (initialWorkspaceId === null) {
      return;
    }

    if (initialWorkspaceId === undefined && workspaceId === null) {
      return;
    }

    if ((initialWorkspaceId ?? null) !== workspaceId) {
      return;
    }

    void initializeWorkspaceRuntimeRef.current(initialWorkspaceId);
  }, [initialWorkspaceId, workspaceId]);

  const reload = useCallback(async () => {
    const targetId = workspaceId ?? initialWorkspaceId ?? undefined;
    await initializeWorkspaceRuntime(targetId, { force: true });
  }, [workspaceId, initialWorkspaceId, initializeWorkspaceRuntime]);

  const changeWorkspace = useCallback(
    async (nextWorkspaceId: string) => {
      await initializeWorkspaceRuntime(nextWorkspaceId, { force: true });
    },
    [initializeWorkspaceRuntime]
  );

  return {
    workspaceId,
    workspaceName,
    runtimeBaseUrl,
    agenticTools,
    accessRole,
    accessSource,
    accessSources,
    allowedOperations,
    runtimeStatus,
    browserConnectivity,
    isLoading,
    isAuthorizationResolved,
    error,
    errorCode,
    reload,
    changeWorkspace,
  };
};
