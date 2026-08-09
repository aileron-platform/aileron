import type {
  VersionControlRemoteBranches,
  VersionControlRepositoryStatus,
} from './types';

export type RepositorySetupError =
  | 'initializeFailed'
  | 'cloneFailed'
  | 'discoveryFailed'
  | 'sshKeyRequired'
  | null;

export type RepositorySetupPhase = 'idle' | 'initializing' | 'discovering' | 'cloning';
export type RepositorySetupCommandKind = 'initialize' | 'discovery' | 'clone';
export type RepositorySetupMutationKind = Exclude<RepositorySetupCommandKind, 'discovery'>;

export interface RepositorySetupRemoteEffects {
  initialize: (defaultBranch: string) => Promise<unknown>;
  clone: (remoteUrl: string, branch?: string) => Promise<unknown>;
  discoverBranches: (remoteUrl: string) => Promise<VersionControlRemoteBranches>;
}

export interface RepositorySetupCommand {
  generation: number;
  id: number;
  kind: RepositorySetupCommandKind;
}

export interface RepositorySetupTarget {
  scopeKey: string;
  repository: VersionControlRepositoryStatus | null;
}

export interface RepositorySetupCapability {
  canMutate: boolean;
}

export interface RepositorySetupState {
  generation: number;
  initializeDialogOpen: boolean;
  defaultBranch: string;
  cloneDialogOpen: boolean;
  remoteUrl: string;
  branches: string[];
  selectedBranch: string;
  hasDiscoveredBranches: boolean;
  phase: RepositorySetupPhase;
  error: RepositorySetupError;
  activeCommand: RepositorySetupCommand | null;
}

export type RepositorySetupEvent =
  | { type: 'boundaryReset'; generation: number }
  | { type: 'openInitialize'; generation: number }
  | { type: 'closeInitialize'; generation: number }
  | { type: 'defaultBranchChanged'; generation: number; defaultBranch: string }
  | { type: 'openClone'; generation: number }
  | { type: 'closeClone'; generation: number }
  | { type: 'remoteUrlChanged'; generation: number; remoteUrl: string }
  | { type: 'branchSelected'; generation: number; branch: string }
  | { type: 'commandStarted'; command: RepositorySetupCommand }
  | { type: 'initializeSucceeded'; command: RepositorySetupCommand }
  | { type: 'initializeFailed'; command: RepositorySetupCommand }
  | {
    type: 'discoverySucceeded';
    command: RepositorySetupCommand;
    remoteUrl: string;
    result: VersionControlRemoteBranches;
  }
  | {
    type: 'discoveryFailed';
    command: RepositorySetupCommand;
    remoteUrl: string;
    error: Extract<RepositorySetupError, 'discoveryFailed' | 'sshKeyRequired'>;
  }
  | { type: 'cloneSucceeded'; command: RepositorySetupCommand }
  | {
    type: 'cloneFailed';
    command: RepositorySetupCommand;
    error: Extract<RepositorySetupError, 'cloneFailed' | 'sshKeyRequired'>;
  };

export type RepositorySetupOperationResult =
  | { status: 'completed'; kind: RepositorySetupCommandKind }
  | { status: 'failed'; kind: RepositorySetupCommandKind; error: Exclude<RepositorySetupError, null> }
  | { status: 'stale'; kind: RepositorySetupCommandKind }
  | { status: 'blocked'; kind: RepositorySetupCommandKind };

export interface RepositorySetupViewModel {
  initializeDialogOpen: boolean;
  defaultBranch: string;
  cloneDialogOpen: boolean;
  remoteUrl: string;
  branches: string[];
  selectedBranch: string;
  hasDiscoveredBranches: boolean;
  hasLocalContent: boolean;
  canMutate: boolean;
  safetyKnown: boolean;
  phase: RepositorySetupPhase;
  error: RepositorySetupError;
  canOpenInitialize: boolean;
  canSubmitInitialize: boolean;
  isCloneSafetyConfirmed: boolean;
  canOpenClone: boolean;
  canDiscoverBranches: boolean;
  canSubmitClone: boolean;
}

export const createInitialRepositorySetupState = (
  generation: number,
): RepositorySetupState => ({
  generation,
  initializeDialogOpen: false,
  defaultBranch: 'main',
  cloneDialogOpen: false,
  remoteUrl: '',
  branches: [],
  selectedBranch: '',
  hasDiscoveredBranches: false,
  phase: 'idle',
  error: null,
  activeCommand: null,
});

const isCurrentGeneration = (
  state: RepositorySetupState,
  generation: number,
): boolean => state.generation === generation;

export const isRepositorySetupCommandActive = (
  state: RepositorySetupState,
  command: RepositorySetupCommand,
): boolean => (
  state.generation === command.generation
  && state.activeCommand?.generation === command.generation
  && state.activeCommand.id === command.id
  && state.activeCommand.kind === command.kind
);

export const createRepositorySetupCommand = (
  generation: number,
  id: number,
  kind: RepositorySetupCommandKind,
): RepositorySetupCommand => ({ generation, id, kind });

const normalizeBranches = (result: VersionControlRemoteBranches): string[] => (
  [...new Set(result.branches.map(branch => branch.trim()).filter(Boolean))]
);

const getSelectedBranch = (
  branches: string[],
  defaultBranch: string | null,
): string => {
  const normalizedDefaultBranch = defaultBranch?.trim() ?? '';
  return normalizedDefaultBranch && branches.includes(normalizedDefaultBranch)
    ? normalizedDefaultBranch
    : branches[0] ?? '';
};

export const reduceRepositorySetupState = (
  state: RepositorySetupState,
  event: RepositorySetupEvent,
): RepositorySetupState => {
  switch (event.type) {
    case 'boundaryReset':
      return event.generation > state.generation
        ? createInitialRepositorySetupState(event.generation)
        : state;
    case 'openInitialize':
      return isCurrentGeneration(state, event.generation) && state.phase === 'idle'
        ? { ...createInitialRepositorySetupState(event.generation), initializeDialogOpen: true }
        : state;
    case 'closeInitialize':
      return isCurrentGeneration(state, event.generation)
        ? createInitialRepositorySetupState(event.generation)
        : state;
    case 'defaultBranchChanged':
      return isCurrentGeneration(state, event.generation)
        && state.initializeDialogOpen
        && state.phase === 'idle'
        ? { ...state, defaultBranch: event.defaultBranch, error: null }
        : state;
    case 'openClone':
      return isCurrentGeneration(state, event.generation) && state.phase === 'idle'
        ? { ...createInitialRepositorySetupState(event.generation), cloneDialogOpen: true }
        : state;
    case 'closeClone':
      return isCurrentGeneration(state, event.generation)
        ? createInitialRepositorySetupState(event.generation)
        : state;
    case 'remoteUrlChanged':
      return isCurrentGeneration(state, event.generation)
        && state.cloneDialogOpen
        && state.phase !== 'cloning'
        ? {
          ...state,
          remoteUrl: event.remoteUrl,
          branches: [],
          selectedBranch: '',
          hasDiscoveredBranches: false,
          phase: 'idle',
          error: null,
          activeCommand: null,
        }
        : state;
    case 'branchSelected':
      return isCurrentGeneration(state, event.generation)
        && state.cloneDialogOpen
        && state.phase === 'idle'
        ? { ...state, selectedBranch: event.branch }
        : state;
    case 'commandStarted':
      if (
        !isCurrentGeneration(state, event.command.generation)
        || state.phase !== 'idle'
      ) {
        return state;
      }
      return {
        ...state,
        branches: event.command.kind === 'discovery' ? [] : state.branches,
        selectedBranch: event.command.kind === 'discovery' ? '' : state.selectedBranch,
        hasDiscoveredBranches: event.command.kind === 'discovery'
          ? false
          : state.hasDiscoveredBranches,
        phase: event.command.kind === 'initialize'
          ? 'initializing'
          : event.command.kind === 'discovery'
            ? 'discovering'
            : 'cloning',
        error: null,
        activeCommand: event.command,
      };
    case 'initializeSucceeded':
      return isRepositorySetupCommandActive(state, event.command)
        ? createInitialRepositorySetupState(state.generation)
        : state;
    case 'initializeFailed':
      return isRepositorySetupCommandActive(state, event.command)
        ? { ...state, phase: 'idle', error: 'initializeFailed', activeCommand: null }
        : state;
    case 'discoverySucceeded':
      if (
        !isRepositorySetupCommandActive(state, event.command)
        || state.remoteUrl.trim() !== event.remoteUrl
      ) {
        return state;
      }
      {
        const branches = normalizeBranches(event.result);
        return {
          ...state,
          branches,
          selectedBranch: getSelectedBranch(branches, event.result.defaultBranch),
          hasDiscoveredBranches: true,
          phase: 'idle',
          error: null,
          activeCommand: null,
        };
      }
    case 'discoveryFailed':
      if (
        !isRepositorySetupCommandActive(state, event.command)
        || state.remoteUrl.trim() !== event.remoteUrl
      ) {
        return state;
      }
      return {
        ...state,
        branches: [],
        selectedBranch: '',
        hasDiscoveredBranches: false,
        phase: 'idle',
        error: event.error,
        activeCommand: null,
      };
    case 'cloneSucceeded':
      return isRepositorySetupCommandActive(state, event.command)
        ? createInitialRepositorySetupState(state.generation)
        : state;
    case 'cloneFailed':
      return isRepositorySetupCommandActive(state, event.command)
        ? { ...state, phase: 'idle', error: event.error, activeCommand: null }
        : state;
    default:
      return state;
  }
};

export const repositorySetupBoundarySignature = (
  target: RepositorySetupTarget,
  capability: RepositorySetupCapability,
): string => {
  const repository = target.repository;
  return JSON.stringify([
    target.scopeKey.trim(),
    capability.canMutate === true,
    repository === null ? null : {
      isGitRepo: repository.isGitRepo === true,
      currentBranch: repository.currentBranch ?? null,
      remoteUrl: repository.remoteUrl ?? null,
      hasOrigin: repository.hasOrigin === true,
      hasLocalContent: repository.hasLocalContent === true,
      canCloneSafely: repository.canCloneSafely === true,
      canInitSafely: repository.canInitSafely === true,
      cloneBlockedReason: repository.cloneBlockedReason ?? null,
    },
  ]);
};

export const isRepositorySetupBoundarySafetyKnown = (
  target: RepositorySetupTarget,
): boolean => (
  target.repository !== null
  && typeof target.repository.canCloneSafely === 'boolean'
  && typeof target.repository.canInitSafely === 'boolean'
);

export const deriveRepositorySetupViewModel = (
  state: RepositorySetupState,
  target: RepositorySetupTarget,
  capability: RepositorySetupCapability,
  boundarySettled: boolean,
): RepositorySetupViewModel => {
  const repository = target.repository;
  const isScopeKnown = target.scopeKey.trim().length > 0;
  const canMutate = capability.canMutate === true;
  const repositoryKnown = repository !== null;
  const repositoryInitialized = repository?.isGitRepo === true;
  const safetyKnown = isRepositorySetupBoundarySafetyKnown(target);
  const canInitializeSafely = Boolean(
    boundarySettled
    && isScopeKnown
    && canMutate
    && repositoryKnown
    && !repositoryInitialized
    && repository?.canInitSafely === true,
  );
  const canCloneSafely = Boolean(
    boundarySettled
    && isScopeKnown
    && canMutate
    && repositoryKnown
    && !repositoryInitialized
    && repository?.canCloneSafely === true,
  );
  const isIdle = state.phase === 'idle';
  const canOpenInitialize = canInitializeSafely && isIdle;
  const canSubmitInitialize = Boolean(
    canOpenInitialize
    && state.initializeDialogOpen
    && state.defaultBranch.trim(),
  );
  const canOpenClone = canCloneSafely && isIdle;
  const canDiscoverBranches = Boolean(
    canOpenClone
    && state.cloneDialogOpen
    && state.remoteUrl.trim(),
  );
  const canSubmitClone = Boolean(
    canOpenClone
    && state.cloneDialogOpen
    && state.remoteUrl.trim()
    && state.hasDiscoveredBranches
    && (state.branches.length === 0 || state.selectedBranch),
  );

  return {
    initializeDialogOpen: state.initializeDialogOpen,
    defaultBranch: state.defaultBranch,
    cloneDialogOpen: state.cloneDialogOpen,
    remoteUrl: state.remoteUrl,
    branches: state.branches,
    selectedBranch: state.selectedBranch,
    hasDiscoveredBranches: state.hasDiscoveredBranches,
    hasLocalContent: repository?.hasLocalContent === true,
    canMutate,
    safetyKnown,
    phase: state.phase,
    error: state.error,
    canOpenInitialize,
    canSubmitInitialize,
    isCloneSafetyConfirmed: canCloneSafely,
    canOpenClone,
    canDiscoverBranches,
    canSubmitClone,
  };
};

export const hasRepositorySetupErrorCode = (
  error: unknown,
  expectedCode: string,
): boolean => (
  typeof error === 'object'
  && error !== null
  && 'errorCode' in error
  && error.errorCode === expectedCode
);

export const repositorySetupErrorFromEffect = (
  kind: RepositorySetupCommandKind,
  error: unknown,
): Exclude<RepositorySetupError, null> => {
  if (
    (kind === 'clone' || kind === 'discovery')
    && hasRepositorySetupErrorCode(error, 'VC_SSH_KEY_REQUIRED')
  ) {
    return 'sshKeyRequired';
  }
  if (kind === 'clone') return 'cloneFailed';
  if (kind === 'discovery') return 'discoveryFailed';
  return 'initializeFailed';
};

export const repositorySetupEventInvalidatesCommand = (
  event: RepositorySetupEvent,
): boolean => (
  event.type === 'boundaryReset'
  || event.type === 'closeInitialize'
  || event.type === 'closeClone'
  || event.type === 'remoteUrlChanged'
  || event.type === 'commandStarted'
);
