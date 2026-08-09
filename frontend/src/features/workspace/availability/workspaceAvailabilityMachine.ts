import { ROUTES } from '@/shared/constants/routes';
import type {
  WorkspaceAvailabilityMutationAction,
  WorkspaceAvailabilityResponse,
} from '../api/workspaceLifecycleApi';

export const AVAILABILITY_LOADING_DELAY_MS = 500;
export const AVAILABILITY_LOADING_MIN_VISIBLE_MS = 500;

export interface WorkspaceAvailabilityRoute {
  pathname: string;
  returnTarget: string;
  navigationReturnTarget?: string | null;
}

export type WorkspaceAvailabilityCommand =
  | {
      id: number;
      epoch: number;
      kind: 'schedule-loading-delay';
      delayMs: number;
      loadingToken: number;
    }
  | {
      id: number;
      epoch: number;
      kind: 'schedule-minimum-loading';
      delayMs: number;
      loadingToken: number;
    }
  | {
      id: number;
      epoch: number;
      kind: 'clear-execution-queries';
      workspaceId: string;
    }
  | {
      id: number;
      epoch: number;
      kind: 'clear-revoked-session';
      workspaceId: string;
    }
  | {
      id: number;
      epoch: number;
      kind: 'invalidate-availability';
      workspaceId: string;
    }
  | {
      id: number;
      epoch: number;
      kind: 'run-lifecycle-action';
      workspaceId: string;
      action: WorkspaceAvailabilityMutationAction;
    }
  | {
      id: number;
      epoch: number;
      kind: 'navigate';
      target: string;
      returnTarget?: string | null;
    }
  | {
      id: number;
      epoch: number;
      kind: 'persist-return-target';
      workspaceId: string;
      target: string;
    }
  | {
      id: number;
      epoch: number;
      kind: 'clear-return-target';
      workspaceId: string;
    }
  | {
      id: number;
      epoch: number;
      kind: 'log-gate-blocked';
      workspaceId: string;
      availability: WorkspaceAvailabilityResponse;
    };

type WorkspaceAvailabilityCommandInput =
  WorkspaceAvailabilityCommand extends infer Command
    ? Command extends WorkspaceAvailabilityCommand
      ? Omit<Command, 'id' | 'epoch'>
      : never
    : never;

type AuthorizationState = 'checking' | 'denied' | 'authorized';

type GateState =
  | { kind: 'checking' }
  | { kind: 'ready'; availability: WorkspaceAvailabilityResponse }
  | {
      kind: 'ready-waiting-for-loading';
      availability: WorkspaceAvailabilityResponse;
    }
  | {
      kind: 'unavailable';
      availability: WorkspaceAvailabilityResponse | null;
      loadError: Error | null;
    }
  | { kind: 'generation-fenced' };

type LoadingState =
  | { kind: 'hidden'; token: number }
  | { kind: 'waiting'; token: number }
  | { kind: 'visible'; token: number; visibleAt: number };

interface GenerationFence {
  afterRequestId: number;
  runtimeInstanceId: string | null;
}

export interface WorkspaceAvailabilityMachineState {
  workspaceId: string;
  epoch: number;
  authorization: AuthorizationState;
  canRunLifecycle: boolean;
  route: WorkspaceAvailabilityRoute;
  returnTarget: string | null;
  gate: GateState;
  loading: LoadingState;
  generationFence: GenerationFence | null;
  latestRequestId: number;
  isFetching: boolean;
  actionInFlight: WorkspaceAvailabilityMutationAction | null;
  actionCommandId: number | null;
  actionErrorCode: string | null;
  lastBlockedSignature: string | null;
  nextCommandId: number;
  pendingCommands: readonly WorkspaceAvailabilityCommand[];
}

export type WorkspaceAvailabilityView =
  | { kind: 'authorization-check' }
  | { kind: 'authorization-denied' }
  | { kind: 'pending-shell' }
  | { kind: 'redirecting' }
  | { kind: 'execution' }
  | {
      kind: 'unavailable';
      availability: WorkspaceAvailabilityResponse | null;
      loadError: Error | null;
      actionErrorCode: string | null;
      isRefreshing: boolean;
      actionInFlight: WorkspaceAvailabilityMutationAction | null;
      canRunLifecycle: boolean;
    };

export interface WorkspaceAvailabilityMachine {
  state: WorkspaceAvailabilityMachineState;
  view: WorkspaceAvailabilityView;
}

export type WorkspaceAvailabilityEvent =
  | {
      type: 'authorization-changed';
      authorizationResolved: boolean;
      canRead: boolean;
      canRunLifecycle: boolean;
    }
  | { type: 'route-observed'; route: WorkspaceAvailabilityRoute }
  | { type: 'availability-request-started'; epoch: number; requestId: number }
  | {
      type: 'availability-resolved';
      epoch: number;
      requestId: number;
      availability: WorkspaceAvailabilityResponse;
      now: number;
    }
  | {
      type: 'availability-rejected';
      epoch: number;
      requestId: number;
      error: Error;
    }
  | { type: 'fetching-changed'; epoch: number; isFetching: boolean }
  | {
      type: 'loading-delay-elapsed';
      epoch: number;
      loadingToken: number;
      now: number;
      commandId: number;
    }
  | {
      type: 'minimum-loading-elapsed';
      epoch: number;
      loadingToken: number;
      commandId: number;
    }
  | {
      type: 'runtime-generation-mismatch';
      epoch: number;
      affectedWorkspaceId: string | null;
      now: number;
    }
  | { type: 'refresh-requested' }
  | { type: 'lifecycle-requested'; action: WorkspaceAvailabilityMutationAction }
  | { type: 'lifecycle-accepted'; epoch: number; commandId: number }
  | {
      type: 'lifecycle-rejected';
      epoch: number;
      commandId: number;
      errorCode: string;
    }
  | { type: 'return-requested' }
  | { type: 'command-completed'; epoch: number; commandId: number }
  | { type: 'command-failed'; epoch: number; commandId: number };

interface CreateWorkspaceAvailabilityMachineInput {
  workspaceId: string;
  authorizationResolved: boolean;
  canRead: boolean;
  canRunLifecycle: boolean;
  route: WorkspaceAvailabilityRoute;
  restoredReturnTarget: string | null;
  epoch?: number;
}

const authorizationFrom = (
  authorizationResolved: boolean,
  canRead: boolean,
): AuthorizationState => {
  if (!authorizationResolved) return 'checking';
  return canRead ? 'authorized' : 'denied';
};

const isUnavailableRoute = (state: WorkspaceAvailabilityMachineState): boolean =>
  state.route.pathname === ROUTES.workspace.unavailable(state.workspaceId);

export const isSafeWorkspaceAvailabilityReturnTarget = (
  target: string | null | undefined,
  workspaceId: string,
): target is string => {
  if (!target) return false;
  const workspacePrefix = `${ROUTES.workspace.root}/${workspaceId}/`;
  return target.startsWith(workspacePrefix)
    && !target.startsWith(ROUTES.workspace.unavailable(workspaceId));
};

const removeCommand = (
  state: WorkspaceAvailabilityMachineState,
  commandId: number,
): WorkspaceAvailabilityMachineState => ({
  ...state,
  pendingCommands: state.pendingCommands.filter(command => command.id !== commandId),
});

const appendCommand = (
  state: WorkspaceAvailabilityMachineState,
  command: WorkspaceAvailabilityCommandInput,
): WorkspaceAvailabilityMachineState => {
  const pendingCommand = {
    ...command,
    id: state.nextCommandId,
    epoch: state.epoch,
  } as WorkspaceAvailabilityCommand;
  return {
    ...state,
    nextCommandId: state.nextCommandId + 1,
    pendingCommands: [...state.pendingCommands, pendingCommand],
  };
};

const hideLoading = (
  state: WorkspaceAvailabilityMachineState,
): WorkspaceAvailabilityMachineState => ({
  ...state,
  loading: { kind: 'hidden', token: state.loading.token + 1 },
});

const scheduleInitialLoading = (
  state: WorkspaceAvailabilityMachineState,
): WorkspaceAvailabilityMachineState => {
  const token = state.loading.token + 1;
  return appendCommand({
    ...state,
    loading: { kind: 'waiting', token },
  }, {
    kind: 'schedule-loading-delay',
    delayMs: AVAILABILITY_LOADING_DELAY_MS,
    loadingToken: token,
  });
};

const workspaceBlockSignature = (
  workspaceId: string,
  availability: WorkspaceAvailabilityResponse,
): string => [
  workspaceId,
  availability.availability,
  availability.reasonCode ?? 'none',
  availability.runtimeInstanceId ?? 'none',
].join(':');

const captureReturnTargetAndRedirect = (
  state: WorkspaceAvailabilityMachineState,
): WorkspaceAvailabilityMachineState => {
  if (isUnavailableRoute(state)) return state;
  const safeTarget = isSafeWorkspaceAvailabilityReturnTarget(
    state.route.returnTarget,
    state.workspaceId,
  ) ? state.route.returnTarget : state.returnTarget;
  let next = { ...state, returnTarget: safeTarget };
  if (safeTarget) {
    next = appendCommand(next, {
      kind: 'persist-return-target',
      workspaceId: state.workspaceId,
      target: safeTarget,
    });
  }
  return appendCommand(next, {
    kind: 'navigate',
    target: ROUTES.workspace.unavailable(state.workspaceId),
    returnTarget: safeTarget,
  });
};

const closeExecutionPlane = (
  state: WorkspaceAvailabilityMachineState,
): WorkspaceAvailabilityMachineState => appendCommand(state, {
  kind: 'clear-execution-queries',
  workspaceId: state.workspaceId,
});

const openReadyRoute = (
  state: WorkspaceAvailabilityMachineState,
): WorkspaceAvailabilityMachineState => {
  if (!isUnavailableRoute(state)) return state;
  const target = isSafeWorkspaceAvailabilityReturnTarget(
    state.returnTarget,
    state.workspaceId,
  ) ? state.returnTarget : ROUTES.workspace.home(state.workspaceId);
  let next = appendCommand(state, {
    kind: 'clear-return-target',
    workspaceId: state.workspaceId,
  });
  next = appendCommand(next, { kind: 'navigate', target });
  return { ...next, returnTarget: null };
};

const initializeState = (
  input: CreateWorkspaceAvailabilityMachineInput,
): WorkspaceAvailabilityMachineState => {
  const authorization = authorizationFrom(input.authorizationResolved, input.canRead);
  const restoredReturnTarget = isSafeWorkspaceAvailabilityReturnTarget(
    input.route.navigationReturnTarget,
    input.workspaceId,
  )
    ? input.route.navigationReturnTarget
    : isSafeWorkspaceAvailabilityReturnTarget(input.restoredReturnTarget, input.workspaceId)
      ? input.restoredReturnTarget
      : null;
  let state: WorkspaceAvailabilityMachineState = {
    workspaceId: input.workspaceId,
    epoch: input.epoch ?? 1,
    authorization,
    canRunLifecycle: input.canRunLifecycle,
    route: input.route,
    returnTarget: restoredReturnTarget,
    gate: { kind: 'checking' },
    loading: { kind: 'hidden', token: 0 },
    generationFence: null,
    latestRequestId: 0,
    isFetching: false,
    actionInFlight: null,
    actionCommandId: null,
    actionErrorCode: null,
    lastBlockedSignature: null,
    nextCommandId: 1,
    pendingCommands: [],
  };
  if (authorization === 'authorized') {
    state = closeExecutionPlane(scheduleInitialLoading(state));
  } else if (authorization === 'denied') {
    state = appendCommand(state, {
      kind: 'clear-revoked-session',
      workspaceId: state.workspaceId,
    });
  }
  return state;
};

export const projectWorkspaceAvailability = (
  state: WorkspaceAvailabilityMachineState,
): WorkspaceAvailabilityView => {
  if (state.authorization === 'checking') return { kind: 'authorization-check' };
  if (state.authorization === 'denied') return { kind: 'authorization-denied' };
  if (state.gate.kind === 'ready') {
    return isUnavailableRoute(state) ? { kind: 'redirecting' } : { kind: 'execution' };
  }
  if (state.gate.kind === 'checking') {
    if (state.loading.kind !== 'visible') return { kind: 'pending-shell' };
    return {
      kind: 'unavailable',
      availability: null,
      loadError: null,
      actionErrorCode: null,
      isRefreshing: state.isFetching,
      actionInFlight: null,
      canRunLifecycle: state.canRunLifecycle,
    };
  }
  if (state.gate.kind === 'ready-waiting-for-loading'
    || state.gate.kind === 'generation-fenced') {
    if (!isUnavailableRoute(state) && state.gate.kind === 'generation-fenced') {
      return { kind: 'redirecting' };
    }
    return {
      kind: 'unavailable',
      availability: null,
      loadError: null,
      actionErrorCode: null,
      isRefreshing: state.gate.kind === 'generation-fenced' && state.isFetching,
      actionInFlight: null,
      canRunLifecycle: state.canRunLifecycle,
    };
  }
  if (!isUnavailableRoute(state)) return { kind: 'redirecting' };
  return {
    kind: 'unavailable',
    availability: state.gate.availability,
    loadError: state.gate.loadError,
    actionErrorCode: state.actionErrorCode,
    isRefreshing: state.isFetching,
    actionInFlight: state.actionInFlight,
    canRunLifecycle: state.canRunLifecycle,
  };
};

export const createWorkspaceAvailabilityMachine = (
  input: CreateWorkspaceAvailabilityMachineInput,
): WorkspaceAvailabilityMachine => {
  const state = initializeState(input);
  return { state, view: projectWorkspaceAvailability(state) };
};

const transitionState = (
  current: WorkspaceAvailabilityMachineState,
  event: WorkspaceAvailabilityEvent,
): WorkspaceAvailabilityMachineState => {
  if ('epoch' in event && event.epoch !== current.epoch) return current;

  switch (event.type) {
    case 'authorization-changed': {
      const authorization = authorizationFrom(event.authorizationResolved, event.canRead);
      if (authorization === current.authorization
        && event.canRunLifecycle === current.canRunLifecycle) return current;
      let next = {
        ...current,
        authorization,
        canRunLifecycle: event.canRunLifecycle,
      };
      if (!event.canRunLifecycle && next.actionCommandId !== null) {
        next = {
          ...removeCommand(next, next.actionCommandId),
          actionInFlight: null,
          actionCommandId: null,
          actionErrorCode: null,
        };
      }
      if (authorization === 'denied') {
        next = hideLoading({
          ...next,
          gate: { kind: 'checking' },
          actionInFlight: null,
          actionCommandId: null,
        });
        return appendCommand(next, {
          kind: 'clear-revoked-session',
          workspaceId: current.workspaceId,
        });
      }
      if (authorization === 'authorized' && current.authorization !== 'authorized') {
        return closeExecutionPlane(scheduleInitialLoading({
          ...next,
          gate: { kind: 'checking' },
        }));
      }
      return next;
    }
    case 'route-observed': {
      const next = { ...current, route: event.route };
      if (next.authorization !== 'authorized') return next;
      if (next.gate.kind === 'ready') return openReadyRoute(next);
      if (next.gate.kind === 'unavailable'
        || next.gate.kind === 'generation-fenced') {
        return captureReturnTargetAndRedirect(next);
      }
      return next;
    }
    case 'availability-request-started':
      return {
        ...current,
        latestRequestId: Math.max(current.latestRequestId, event.requestId),
        isFetching: true,
      };
    case 'fetching-changed':
      return { ...current, isFetching: event.isFetching };
    case 'loading-delay-elapsed': {
      let next = removeCommand(current, event.commandId);
      if (next.loading.kind !== 'waiting'
        || next.loading.token !== event.loadingToken
        || next.gate.kind !== 'checking') return next;
      return {
        ...next,
        loading: {
          kind: 'visible',
          token: event.loadingToken,
          visibleAt: event.now,
        },
      };
    }
    case 'minimum-loading-elapsed': {
      let next = removeCommand(current, event.commandId);
      if (next.loading.token !== event.loadingToken
        || next.gate.kind !== 'ready-waiting-for-loading') return next;
      next = hideLoading({
        ...next,
        gate: { kind: 'ready', availability: next.gate.availability },
      });
      return openReadyRoute(next);
    }
    case 'availability-resolved': {
      if (event.requestId < current.latestRequestId) return current;
      if (current.generationFence) {
        if (event.requestId <= current.generationFence.afterRequestId) return current;
        const isSameReadyGeneration = event.availability.availability === 'ready'
          && event.availability.runtimeInstanceId !== null
          && event.availability.runtimeInstanceId === current.generationFence.runtimeInstanceId;
        if (isSameReadyGeneration) return { ...current, isFetching: false };
      }
      let next = {
        ...current,
        latestRequestId: event.requestId,
        isFetching: false,
        generationFence: null,
        actionErrorCode: null,
      };
      if (event.availability.availability === 'ready') {
        if (next.loading.kind === 'visible') {
          const elapsed = event.now - next.loading.visibleAt;
          const delayMs = Math.max(0, AVAILABILITY_LOADING_MIN_VISIBLE_MS - elapsed);
          if (delayMs > 0) {
            next = appendCommand({
              ...next,
              gate: {
                kind: 'ready-waiting-for-loading',
                availability: event.availability,
              },
              lastBlockedSignature: null,
            }, {
              kind: 'schedule-minimum-loading',
              delayMs,
              loadingToken: next.loading.token,
            });
            return next;
          }
        }
        next = hideLoading({
          ...next,
          gate: { kind: 'ready', availability: event.availability },
          lastBlockedSignature: null,
        });
        return openReadyRoute(next);
      }

      next = hideLoading({
        ...next,
        gate: {
          kind: 'unavailable',
          availability: event.availability,
          loadError: null,
        },
      });
      next = closeExecutionPlane(next);
      const signature = workspaceBlockSignature(current.workspaceId, event.availability);
      if (signature !== current.lastBlockedSignature) {
        next = appendCommand({ ...next, lastBlockedSignature: signature }, {
          kind: 'log-gate-blocked',
          workspaceId: current.workspaceId,
          availability: event.availability,
        });
      }
      return captureReturnTargetAndRedirect(next);
    }
    case 'availability-rejected': {
      if (event.requestId < current.latestRequestId || current.generationFence) return current;
      let next = hideLoading({
        ...current,
        latestRequestId: event.requestId,
        isFetching: false,
        gate: { kind: 'unavailable', availability: null, loadError: event.error },
      });
      next = closeExecutionPlane(next);
      return captureReturnTargetAndRedirect(next);
    }
    case 'runtime-generation-mismatch': {
      if (event.affectedWorkspaceId
        && event.affectedWorkspaceId !== current.workspaceId) return current;
      const currentRuntimeInstanceId = current.gate.kind === 'ready'
        ? current.gate.availability.runtimeInstanceId
        : null;
      let next: WorkspaceAvailabilityMachineState = {
        ...current,
        gate: { kind: 'generation-fenced' },
        generationFence: {
          afterRequestId: current.latestRequestId,
          runtimeInstanceId: currentRuntimeInstanceId,
        },
        loading: {
          kind: 'visible',
          token: current.loading.token + 1,
          visibleAt: event.now,
        },
        actionInFlight: null,
        actionCommandId: null,
        actionErrorCode: null,
      };
      next = closeExecutionPlane(next);
      next = appendCommand(next, {
        kind: 'invalidate-availability',
        workspaceId: current.workspaceId,
      });
      return captureReturnTargetAndRedirect(next);
    }
    case 'refresh-requested':
      return appendCommand({ ...current, actionErrorCode: null }, {
        kind: 'invalidate-availability',
        workspaceId: current.workspaceId,
      });
    case 'lifecycle-requested': {
      const allowed = current.gate.kind === 'unavailable'
        && current.gate.availability?.allowedActions.includes(event.action);
      if (!current.canRunLifecycle || !allowed || current.actionInFlight) return current;
      const next = appendCommand({
        ...current,
        actionInFlight: event.action,
        actionErrorCode: null,
      }, {
        kind: 'run-lifecycle-action',
        workspaceId: current.workspaceId,
        action: event.action,
      });
      return {
        ...next,
        actionCommandId: next.nextCommandId - 1,
      };
    }
    case 'lifecycle-accepted': {
      if (event.commandId !== current.actionCommandId) return current;
      let next = removeCommand(current, event.commandId);
      next = {
        ...next,
        actionInFlight: null,
        actionCommandId: null,
      };
      return appendCommand(next, {
        kind: 'invalidate-availability',
        workspaceId: current.workspaceId,
      });
    }
    case 'lifecycle-rejected':
      if (event.commandId !== current.actionCommandId) return current;
      return {
        ...removeCommand(current, event.commandId),
        actionInFlight: null,
        actionCommandId: null,
        actionErrorCode: event.errorCode,
      };
    case 'return-requested': {
      let next = appendCommand(current, {
        kind: 'clear-return-target',
        workspaceId: current.workspaceId,
      });
      next = appendCommand(next, {
        kind: 'navigate',
        target: ROUTES.workspace.root,
      });
      return { ...next, returnTarget: null };
    }
    case 'command-completed': {
      const next = removeCommand(current, event.commandId);
      return event.commandId === current.actionCommandId
        ? {
            ...next,
            actionInFlight: null,
            actionCommandId: null,
            actionErrorCode: null,
          }
        : next;
    }
    case 'command-failed':
      return removeCommand(current, event.commandId);
    default:
      return current;
  }
};

export const transitionWorkspaceAvailability = (
  machine: WorkspaceAvailabilityMachine,
  event: WorkspaceAvailabilityEvent,
): WorkspaceAvailabilityMachine => {
  const state = transitionState(machine.state, event);
  return { state, view: projectWorkspaceAvailability(state) };
};
