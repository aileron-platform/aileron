import {
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from 'react';
import type {
  RepositorySetupCapability,
  RepositorySetupCommand,
  RepositorySetupCommandKind,
  RepositorySetupEvent,
  RepositorySetupError,
  RepositorySetupMutationKind,
  RepositorySetupOperationResult,
  RepositorySetupRemoteEffects,
  RepositorySetupState,
  RepositorySetupTarget,
  RepositorySetupViewModel,
} from './repositorySetupWorkflowCore';
import {
  createInitialRepositorySetupState,
  createRepositorySetupCommand,
  deriveRepositorySetupViewModel,
  reduceRepositorySetupState,
  repositorySetupBoundarySignature,
  repositorySetupErrorFromEffect,
  repositorySetupEventInvalidatesCommand,
} from './repositorySetupWorkflowCore';

export type {
  RepositorySetupCapability,
  RepositorySetupCommand,
  RepositorySetupCommandKind,
  RepositorySetupEvent,
  RepositorySetupError,
  RepositorySetupMutationKind,
  RepositorySetupOperationResult,
  RepositorySetupState,
  RepositorySetupTarget,
  RepositorySetupViewModel,
} from './repositorySetupWorkflowCore';
export type { RepositorySetupRemoteEffects } from './repositorySetupWorkflowCore';

export interface RepositorySetupWorkflowOptions {
  target: RepositorySetupTarget;
  capability: RepositorySetupCapability;
  remoteEffects: RepositorySetupRemoteEffects;
}

export interface RepositorySetupWorkflow {
  state: RepositorySetupViewModel;
  events: {
    openInitialize: () => void;
    closeInitialize: () => void;
    changeDefaultBranch: (defaultBranch: string) => void;
    openClone: () => void;
    closeClone: () => void;
    changeRemoteUrl: (remoteUrl: string) => void;
    selectBranch: (branch: string) => void;
    initialize: () => Promise<RepositorySetupOperationResult>;
    discoverBranches: () => Promise<RepositorySetupOperationResult>;
    clone: () => Promise<RepositorySetupOperationResult>;
  };
}

const isCurrentCommand = (
  command: RepositorySetupCommand,
  activeCommand: RepositorySetupCommand | null,
  generation: number,
): boolean => (
  generation === command.generation
  && activeCommand?.generation === command.generation
  && activeCommand.id === command.id
  && activeCommand.kind === command.kind
);

export const useRepositorySetupWorkflow = ({
  target,
  capability,
  remoteEffects,
}: RepositorySetupWorkflowOptions): RepositorySetupWorkflow => {
  const signature = repositorySetupBoundarySignature(target, capability);
  const boundaryRef = useRef({ signature, generation: 0 });
  if (boundaryRef.current.signature !== signature) {
    boundaryRef.current = {
      signature,
      generation: boundaryRef.current.generation + 1,
    };
  }

  const generation = boundaryRef.current.generation;
  const [storedState, dispatch] = useReducer(
    reduceRepositorySetupState,
    generation,
    createInitialRepositorySetupState,
  );
  const activeCommandRef = useRef<RepositorySetupCommand | null>(null);
  const commandSequence = useRef(0);
  const remoteEffectsRef = useRef(remoteEffects);
  remoteEffectsRef.current = remoteEffects;
  const boundarySettled = storedState.generation === generation;
  const state = boundarySettled
    ? storedState
    : createInitialRepositorySetupState(generation);

  const dispatchWorkflowEvent = useCallback((event: RepositorySetupEvent) => {
    if (repositorySetupEventInvalidatesCommand(event)) {
      activeCommandRef.current = null;
    }
    if (event.type === 'commandStarted') {
      activeCommandRef.current = event.command;
    }
    dispatch(event);
  }, []);

  useEffect(() => {
    dispatchWorkflowEvent({ type: 'boundaryReset', generation });
  }, [dispatchWorkflowEvent, generation]);

  const viewModel = deriveRepositorySetupViewModel(
    state,
    target,
    capability,
    boundarySettled,
  );

  const createCommand = useCallback((kind: RepositorySetupCommandKind) => (
    createRepositorySetupCommand(generation, ++commandSequence.current, kind)
  ), [generation]);

  const isCommandCurrent = useCallback((command: RepositorySetupCommand) => (
    isCurrentCommand(command, activeCommandRef.current, boundaryRef.current.generation)
  ), []);

  const openInitialize = useCallback(() => {
    if (viewModel.canOpenInitialize) {
      dispatchWorkflowEvent({ type: 'openInitialize', generation });
    }
  }, [dispatchWorkflowEvent, generation, viewModel.canOpenInitialize]);

  const closeInitialize = useCallback(() => {
    dispatchWorkflowEvent({ type: 'closeInitialize', generation });
  }, [dispatchWorkflowEvent, generation]);

  const changeDefaultBranch = useCallback((defaultBranch: string) => {
    dispatchWorkflowEvent({ type: 'defaultBranchChanged', generation, defaultBranch });
  }, [dispatchWorkflowEvent, generation]);

  const openClone = useCallback(() => {
    if (viewModel.canOpenClone) {
      dispatchWorkflowEvent({ type: 'openClone', generation });
    }
  }, [dispatchWorkflowEvent, generation, viewModel.canOpenClone]);

  const closeClone = useCallback(() => {
    dispatchWorkflowEvent({ type: 'closeClone', generation });
  }, [dispatchWorkflowEvent, generation]);

  const changeRemoteUrl = useCallback((remoteUrl: string) => {
    dispatchWorkflowEvent({ type: 'remoteUrlChanged', generation, remoteUrl });
  }, [dispatchWorkflowEvent, generation]);

  const selectBranch = useCallback((branch: string) => {
    dispatchWorkflowEvent({ type: 'branchSelected', generation, branch });
  }, [dispatchWorkflowEvent, generation]);

  const initialize = useCallback(async (): Promise<RepositorySetupOperationResult> => {
    const kind: RepositorySetupMutationKind = 'initialize';
    if (!viewModel.canSubmitInitialize) {
      return { status: 'blocked', kind };
    }
    const command = createCommand(kind);
    const defaultBranch = state.defaultBranch.trim();
    dispatchWorkflowEvent({ type: 'commandStarted', command });
    try {
      await remoteEffectsRef.current.initialize(defaultBranch);
      if (!isCommandCurrent(command)) {
        return { status: 'stale', kind };
      }
      dispatchWorkflowEvent({ type: 'initializeSucceeded', command });
      return { status: 'completed', kind };
    } catch (error) {
      if (!isCommandCurrent(command)) {
        return { status: 'stale', kind };
      }
      const setupError = repositorySetupErrorFromEffect(kind, error);
      dispatchWorkflowEvent({ type: 'initializeFailed', command });
      return { status: 'failed', kind, error: setupError };
    }
  }, [
    createCommand,
    dispatchWorkflowEvent,
    isCommandCurrent,
    state.defaultBranch,
    viewModel.canSubmitInitialize,
  ]);

  const discoverBranches = useCallback(async (): Promise<RepositorySetupOperationResult> => {
    const kind: RepositorySetupCommandKind = 'discovery';
    if (!viewModel.canDiscoverBranches) {
      return { status: 'blocked', kind };
    }
    const command = createCommand(kind);
    const remoteUrl = state.remoteUrl.trim();
    dispatchWorkflowEvent({ type: 'commandStarted', command });
    try {
      const result = await remoteEffectsRef.current.discoverBranches(remoteUrl);
      if (!isCommandCurrent(command)) {
        return { status: 'stale', kind };
      }
      dispatchWorkflowEvent({ type: 'discoverySucceeded', command, remoteUrl, result });
      return { status: 'completed', kind };
    } catch (error) {
      if (!isCommandCurrent(command)) {
        return { status: 'stale', kind };
      }
      const setupError = repositorySetupErrorFromEffect(kind, error);
      dispatchWorkflowEvent({
        type: 'discoveryFailed',
        command,
        remoteUrl,
        error: setupError as Extract<RepositorySetupError, 'discoveryFailed' | 'sshKeyRequired'>,
      });
      return { status: 'failed', kind, error: setupError };
    }
  }, [
    createCommand,
    dispatchWorkflowEvent,
    isCommandCurrent,
    state.remoteUrl,
    viewModel.canDiscoverBranches,
  ]);

  const clone = useCallback(async (): Promise<RepositorySetupOperationResult> => {
    const kind: RepositorySetupMutationKind = 'clone';
    if (!viewModel.canSubmitClone) {
      return { status: 'blocked', kind };
    }
    const command = createCommand(kind);
    const remoteUrl = state.remoteUrl.trim();
    const branch = state.selectedBranch.trim() || undefined;
    dispatchWorkflowEvent({ type: 'commandStarted', command });
    try {
      await remoteEffectsRef.current.clone(remoteUrl, branch);
      if (!isCommandCurrent(command)) {
        return { status: 'stale', kind };
      }
      dispatchWorkflowEvent({ type: 'cloneSucceeded', command });
      return { status: 'completed', kind };
    } catch (error) {
      if (!isCommandCurrent(command)) {
        return { status: 'stale', kind };
      }
      const setupError = repositorySetupErrorFromEffect(kind, error);
      dispatchWorkflowEvent({
        type: 'cloneFailed',
        command,
        error: setupError as Extract<RepositorySetupError, 'cloneFailed' | 'sshKeyRequired'>,
      });
      return { status: 'failed', kind, error: setupError };
    }
  }, [
    createCommand,
    dispatchWorkflowEvent,
    isCommandCurrent,
    state.remoteUrl,
    state.selectedBranch,
    viewModel.canSubmitClone,
  ]);

  return useMemo(() => ({
    state: viewModel,
    events: {
      openInitialize,
      closeInitialize,
      changeDefaultBranch,
      openClone,
      closeClone,
      changeRemoteUrl,
      selectBranch,
      initialize,
      discoverBranches,
      clone,
    },
  }), [
    changeDefaultBranch,
    changeRemoteUrl,
    clone,
    closeClone,
    closeInitialize,
    discoverBranches,
    initialize,
    openClone,
    openInitialize,
    selectBranch,
    viewModel,
  ]);
};
