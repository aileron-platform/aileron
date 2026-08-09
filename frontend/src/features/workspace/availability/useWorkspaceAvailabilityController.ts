import { useCallback, useEffect, useReducer, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  ApiError,
  type ApiErrorEvent,
  subscribeApiError,
} from '@/shared/api/apiClient';
import { createLogger } from '@/shared/services/logger';
import {
  type WorkspaceAvailabilityMutationAction,
  type WorkspaceAvailabilityResponse,
  workspaceLifecycleApi,
} from '../api/workspaceLifecycleApi';
import {
  createWorkspaceAvailabilityMachine,
  transitionWorkspaceAvailability,
  type WorkspaceAvailabilityCommand,
  type WorkspaceAvailabilityEvent,
  type WorkspaceAvailabilityMachine,
  type WorkspaceAvailabilityView,
} from './workspaceAvailabilityMachine';
import {
  clearRevokedWorkspaceAvailabilitySession,
  clearWorkspaceAvailabilityReturnTarget,
  clearWorkspaceExecutionQueries,
  persistWorkspaceAvailabilityReturnTarget,
  readWorkspaceAvailabilityReturnTarget,
  workspaceAvailabilityQueryKey,
} from './workspaceAvailabilitySession';

const logger = createLogger('WorkspaceAvailabilityController');
let nextControllerGeneration = 0;

const MIN_AVAILABILITY_POLL_INTERVAL_MS = 1_000;
const MAX_AVAILABILITY_POLL_INTERVAL_MS = 15_000;
const DEFAULT_AVAILABILITY_POLL_INTERVAL_MS = 10_000;

interface WorkspaceAvailabilityQueryResult {
  controllerGeneration: number;
  requestId: number;
  availability: WorkspaceAvailabilityResponse;
}

class WorkspaceAvailabilityRequestError extends Error {
  readonly controllerGeneration: number;
  readonly requestId: number;
  readonly originalError: Error;

  constructor(controllerGeneration: number, requestId: number, error: unknown) {
    const originalError = error instanceof Error ? error : new Error('workspace_availability_failed');
    super(originalError.message);
    this.name = 'WorkspaceAvailabilityRequestError';
    this.controllerGeneration = controllerGeneration;
    this.requestId = requestId;
    this.originalError = originalError;
  }
}

interface UseWorkspaceAvailabilityControllerInput {
  workspaceId: string;
  authorizationResolved: boolean;
  canRead: boolean;
  canRunLifecycle: boolean;
}

export interface WorkspaceAvailabilityController {
  view: WorkspaceAvailabilityView;
  refresh: () => void;
  runAction: (action: WorkspaceAvailabilityMutationAction) => void;
  returnToWorkspaceList: () => void;
}

const locationToString = (location: {
  pathname: string;
  search: string;
  hash: string;
}): string => `${location.pathname}${location.search}${location.hash}`;

const workspaceIdFromApiError = (event: ApiErrorEvent): string | null => {
  if (!event.responseUrl) return null;
  try {
    const segments = new URL(event.responseUrl, window.location.origin).pathname.split('/');
    const workspaceIndex = segments.indexOf('workspaces');
    const encodedWorkspaceId = segments[workspaceIndex + 1];
    return workspaceIndex >= 0 && encodedWorkspaceId
      ? decodeURIComponent(encodedWorkspaceId)
      : null;
  } catch {
    return null;
  }
};

const originalQueryError = (error: unknown): unknown =>
  error instanceof WorkspaceAvailabilityRequestError ? error.originalError : error;

const isStableClientError = (error: unknown): boolean => {
  const candidate = originalQueryError(error);
  return candidate instanceof ApiError
    && candidate.status >= 400
    && candidate.status < 500
    && candidate.status !== 408
    && candidate.status !== 429;
};

const workspaceAvailabilityActionErrorCode = (error: unknown): string =>
  error instanceof ApiError && error.errorCode
    ? error.errorCode
    : 'WORKSPACE_AVAILABILITY_ACTION_FAILED';

const boundAvailabilityPollInterval = (
  retryAfterMs: number | null | undefined,
): number => {
  if (!Number.isFinite(retryAfterMs)) return DEFAULT_AVAILABILITY_POLL_INTERVAL_MS;
  return Math.min(
    MAX_AVAILABILITY_POLL_INTERVAL_MS,
    Math.max(MIN_AVAILABILITY_POLL_INTERVAL_MS, Math.round(retryAfterMs as number)),
  );
};

const reducer = (
  machine: WorkspaceAvailabilityMachine,
  event: WorkspaceAvailabilityEvent,
): WorkspaceAvailabilityMachine => transitionWorkspaceAvailability(machine, event);

export const useWorkspaceAvailabilityController = ({
  workspaceId,
  authorizationResolved,
  canRead,
  canRunLifecycle,
}: UseWorkspaceAvailabilityControllerInput): WorkspaceAvailabilityController => {
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const controllerGenerationRef = useRef<number | null>(null);
  if (controllerGenerationRef.current === null) {
    controllerGenerationRef.current = ++nextControllerGeneration;
  }
  const controllerGeneration = controllerGenerationRef.current;
  const requestIdRef = useRef(0);
  const observedResultIdRef = useRef(0);
  const observedErrorIdRef = useRef(0);
  const executedCommandsRef = useRef(new Set<string>());
  const timersRef = useRef(new Map<string, number>());
  const initialRoute = {
    pathname: location.pathname,
    returnTarget: locationToString(location),
    navigationReturnTarget: (
      location.state as { workspaceAvailabilityReturnTo?: string } | null
    )?.workspaceAvailabilityReturnTo,
  };
  const [machine, dispatch] = useReducer(reducer, undefined, () =>
    createWorkspaceAvailabilityMachine({
      workspaceId,
      authorizationResolved,
      canRead,
      canRunLifecycle,
      route: initialRoute,
      restoredReturnTarget: readWorkspaceAvailabilityReturnTarget(workspaceId),
      epoch: controllerGeneration,
    }));
  const epoch = machine.state.epoch;

  useEffect(() => {
    dispatch({
      type: 'authorization-changed',
      authorizationResolved,
      canRead,
      canRunLifecycle,
    });
  }, [authorizationResolved, canRead, canRunLifecycle]);

  useEffect(() => {
    dispatch({
      type: 'route-observed',
      route: {
        pathname: location.pathname,
        returnTarget: locationToString(location),
        navigationReturnTarget: (
          location.state as { workspaceAvailabilityReturnTo?: string } | null
        )?.workspaceAvailabilityReturnTo,
      },
    });
  }, [location]);

  const availabilityQuery = useQuery<
    WorkspaceAvailabilityQueryResult,
    WorkspaceAvailabilityRequestError
  >({
    queryKey: workspaceAvailabilityQueryKey(workspaceId),
    queryFn: async ({ signal }) => {
      const requestId = ++requestIdRef.current;
      dispatch({ type: 'availability-request-started', epoch, requestId });
      try {
        const availability = await workspaceLifecycleApi.getAvailability(workspaceId, signal);
        return { controllerGeneration, requestId, availability };
      } catch (error) {
        throw new WorkspaceAvailabilityRequestError(
          controllerGeneration,
          requestId,
          error,
        );
      }
    },
    enabled: authorizationResolved
      && canRead
      && machine.state.authorization === 'authorized'
      && Boolean(workspaceId),
    retry: (failureCount, error) => !isStableClientError(error) && failureCount < 1,
    refetchInterval: (query) => {
      if (query.state.error && isStableClientError(query.state.error)) return false;
      return boundAvailabilityPollInterval(query.state.data?.availability.retryAfterMs);
    },
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    staleTime: 0,
  });

  useEffect(() => {
    dispatch({ type: 'fetching-changed', epoch, isFetching: availabilityQuery.isFetching });
  }, [availabilityQuery.isFetching, epoch]);

  useEffect(() => {
    const result = availabilityQuery.data;
    if (!result
      || result.controllerGeneration !== controllerGeneration
      || result.requestId <= observedResultIdRef.current) return;
    observedResultIdRef.current = result.requestId;
    dispatch({
      type: 'availability-resolved',
      epoch,
      requestId: result.requestId,
      availability: result.availability,
      now: Date.now(),
    });
  }, [availabilityQuery.data, controllerGeneration, epoch]);

  useEffect(() => {
    const error = availabilityQuery.error;
    if (!error
      || error.controllerGeneration !== controllerGeneration
      || error.requestId <= observedErrorIdRef.current) return;
    observedErrorIdRef.current = error.requestId;
    dispatch({
      type: 'availability-rejected',
      epoch,
      requestId: error.requestId,
      error: error.originalError,
    });
  }, [availabilityQuery.error, controllerGeneration, epoch]);

  useEffect(() => subscribeApiError((event) => {
    if (event.status !== 423
      || event.errorCode !== 'WORKSPACE_RUNTIME_INSTANCE_MISMATCH') return;
    dispatch({
      type: 'runtime-generation-mismatch',
      epoch,
      affectedWorkspaceId: workspaceIdFromApiError(event),
      now: Date.now(),
    });
  }), [epoch]);

  useEffect(() => {
    const complete = (command: WorkspaceAvailabilityCommand): void => {
      dispatch({ type: 'command-completed', epoch: command.epoch, commandId: command.id });
    };
    const fail = (command: WorkspaceAvailabilityCommand, error: unknown): void => {
      logger.warn('Workspace availability command failed', {
        command: command.kind,
        error,
        workspaceId,
      });
      dispatch({ type: 'command-failed', epoch: command.epoch, commandId: command.id });
    };

    for (const command of machine.state.pendingCommands) {
      const commandKey = `${command.epoch}:${command.id}`;
      if (executedCommandsRef.current.has(commandKey)) continue;
      executedCommandsRef.current.add(commandKey);

      if (command.kind === 'schedule-loading-delay'
        || command.kind === 'schedule-minimum-loading') {
        const timeoutId = window.setTimeout(() => {
          timersRef.current.delete(commandKey);
          dispatch(command.kind === 'schedule-loading-delay'
            ? {
                type: 'loading-delay-elapsed',
                epoch: command.epoch,
                loadingToken: command.loadingToken,
                now: Date.now(),
                commandId: command.id,
              }
            : {
                type: 'minimum-loading-elapsed',
                epoch: command.epoch,
                loadingToken: command.loadingToken,
                commandId: command.id,
              });
        }, command.delayMs);
        timersRef.current.set(commandKey, timeoutId);
        continue;
      }

      if (command.kind === 'clear-execution-queries') {
        void clearWorkspaceExecutionQueries(queryClient, command.workspaceId)
          .then(() => complete(command))
          .catch(error => fail(command, error));
        continue;
      }
      if (command.kind === 'clear-revoked-session') {
        void clearRevokedWorkspaceAvailabilitySession(queryClient, command.workspaceId)
          .then(() => complete(command))
          .catch(error => fail(command, error));
        continue;
      }
      if (command.kind === 'invalidate-availability') {
        void queryClient.invalidateQueries({
          queryKey: workspaceAvailabilityQueryKey(command.workspaceId),
          refetchType: 'active',
        }).then(() => complete(command)).catch(error => fail(command, error));
        continue;
      }
      if (command.kind === 'run-lifecycle-action') {
        if (!canRead || !canRunLifecycle) {
          complete(command);
          continue;
        }
        void workspaceLifecycleApi.runAvailabilityAction(command.workspaceId, command.action)
          .then(() => dispatch({
            type: 'lifecycle-accepted',
            epoch: command.epoch,
            commandId: command.id,
          }))
          .catch(error => dispatch({
            type: 'lifecycle-rejected',
            epoch: command.epoch,
            commandId: command.id,
            errorCode: workspaceAvailabilityActionErrorCode(error),
          }));
        continue;
      }
      if (command.kind === 'navigate') {
        navigate(command.target, {
          replace: true,
          state: command.returnTarget === undefined
            ? undefined
            : { workspaceAvailabilityReturnTo: command.returnTarget },
        });
        complete(command);
        continue;
      }
      if (command.kind === 'persist-return-target') {
        persistWorkspaceAvailabilityReturnTarget(command.workspaceId, command.target);
        complete(command);
        continue;
      }
      if (command.kind === 'clear-return-target') {
        clearWorkspaceAvailabilityReturnTarget(command.workspaceId);
        complete(command);
        continue;
      }
      logger.info('Workspace execution plane blocked by availability gate', {
        workspaceId: command.workspaceId,
        availability: command.availability.availability,
        reasonCode: command.availability.reasonCode,
        runtimeStatus: command.availability.runtimeStatus,
        runtimeInstanceId: command.availability.runtimeInstanceId,
      });
      complete(command);
    }
  }, [
    canRead,
    canRunLifecycle,
    machine.state.pendingCommands,
    navigate,
    queryClient,
    workspaceId,
  ]);

  useEffect(() => () => {
    for (const timeoutId of timersRef.current.values()) window.clearTimeout(timeoutId);
    timersRef.current.clear();
  }, []);

  const refresh = useCallback(() => dispatch({ type: 'refresh-requested' }), []);
  const runAction = useCallback((action: WorkspaceAvailabilityMutationAction) => {
    if (!canRead || !canRunLifecycle) return;
    dispatch({ type: 'lifecycle-requested', action });
  }, [canRead, canRunLifecycle]);
  const returnToWorkspaceList = useCallback(() => {
    dispatch({ type: 'return-requested' });
  }, []);

  const currentView: WorkspaceAvailabilityView = !authorizationResolved
    ? { kind: 'authorization-check' }
    : !canRead
      ? { kind: 'authorization-denied' }
      : machine.view.kind === 'unavailable'
        ? {
            ...machine.view,
            canRunLifecycle: canRunLifecycle && canRead,
          }
        : machine.view;

  return {
    view: currentView,
    refresh,
    runAction,
    returnToWorkspaceList,
  };
};
