import { act, renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type {
  RepositorySetupRemoteEffects,
  RepositorySetupTarget,
  VersionControlRemoteBranches,
  VersionControlRepositoryStatus,
} from './index';
import { useRepositorySetupWorkflow } from './repositorySetupWorkflow';

const safeRepository: VersionControlRepositoryStatus = {
  isGitRepo: false,
  currentBranch: null,
  remoteUrl: null,
  hasOrigin: false,
  hasLocalContent: false,
  canCloneSafely: true,
  canInitSafely: true,
  cloneBlockedReason: null,
};

const createTarget = (
  repository: VersionControlRepositoryStatus | null = safeRepository,
  scopeKey = 'workspace:one',
): RepositorySetupTarget => ({ scopeKey, repository });

const createEffects = (
  overrides: Partial<RepositorySetupRemoteEffects> = {},
): RepositorySetupRemoteEffects => ({
  initialize: vi.fn().mockResolvedValue(undefined),
  clone: vi.fn().mockResolvedValue(undefined),
  discoverBranches: vi.fn().mockResolvedValue({
    branches: ['main'],
    defaultBranch: 'main',
  }),
  ...overrides,
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const openCloneWithUrl = (
  result: { current: ReturnType<typeof useRepositorySetupWorkflow> },
  remoteUrl = 'git@example.com:team/repository.git',
) => {
  act(() => {
    result.current.events.openClone();
    result.current.events.changeRemoteUrl(remoteUrl);
  });
};

describe('useRepositorySetupWorkflow', () => {
  it('fails closed when the repository target safety status is unknown', async () => {
    const effects = createEffects();
    const { result } = renderHook(() => useRepositorySetupWorkflow({
      target: createTarget(null),
      capability: { canMutate: true },
      remoteEffects: effects,
    }));

    expect(result.current.state.safetyKnown).toBe(false);
    expect(result.current.state.canOpenInitialize).toBe(false);
    expect(result.current.state.canOpenClone).toBe(false);
    expect(await result.current.events.initialize()).toEqual({
      status: 'blocked',
      kind: 'initialize',
    });
    expect(await result.current.events.discoverBranches()).toEqual({
      status: 'blocked',
      kind: 'discovery',
    });
    expect(effects.initialize).not.toHaveBeenCalled();
    expect(effects.clone).not.toHaveBeenCalled();
    expect(effects.discoverBranches).not.toHaveBeenCalled();
  });

  it('keeps the setup surface read-only when the capability is missing', () => {
    const effects = createEffects();
    const { result } = renderHook(() => useRepositorySetupWorkflow({
      target: createTarget(),
      capability: { canMutate: false },
      remoteEffects: effects,
    }));

    expect(result.current.state.canMutate).toBe(false);
    expect(result.current.state.canOpenInitialize).toBe(false);
    expect(result.current.state.canOpenClone).toBe(false);
  });

  it('tracks initialize loading, failure, retry, and success', async () => {
    const initialize = vi.fn()
      .mockRejectedValueOnce(new Error('initialize failed'))
      .mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useRepositorySetupWorkflow({
      target: createTarget(),
      capability: { canMutate: true },
      remoteEffects: createEffects({ initialize }),
    }));

    act(() => result.current.events.openInitialize());
    expect(result.current.state.initializeDialogOpen).toBe(true);
    expect(result.current.state.canSubmitInitialize).toBe(true);

    let firstResult;
    await act(async () => {
      firstResult = await result.current.events.initialize();
    });
    expect(firstResult).toEqual({
      status: 'failed',
      kind: 'initialize',
      error: 'initializeFailed',
    });
    expect(initialize).toHaveBeenCalledWith('main');
    expect(result.current.state.phase).toBe('idle');
    expect(result.current.state.error).toBe('initializeFailed');
    expect(result.current.state.initializeDialogOpen).toBe(true);

    let retryResult;
    await act(async () => {
      retryResult = await result.current.events.initialize();
    });
    expect(retryResult).toEqual({ status: 'completed', kind: 'initialize' });
    expect(initialize).toHaveBeenCalledTimes(2);
    expect(result.current.state.initializeDialogOpen).toBe(false);
    expect(result.current.state.error).toBeNull();
  });

  it('tracks branch discovery loading, success, failure, and retry', async () => {
    const firstDiscovery = deferred<VersionControlRemoteBranches>();
    const discoverBranches = vi.fn()
      .mockReturnValueOnce(firstDiscovery.promise)
      .mockRejectedValueOnce(new Error('discovery failed'))
      .mockResolvedValueOnce({ branches: ['release'], defaultBranch: 'release' });
    const { result } = renderHook(() => useRepositorySetupWorkflow({
      target: createTarget(),
      capability: { canMutate: true },
      remoteEffects: createEffects({ discoverBranches }),
    }));

    openCloneWithUrl(result);
    let firstResultPromise: Promise<unknown>;
    act(() => {
      firstResultPromise = result.current.events.discoverBranches();
    });
    expect(result.current.state.phase).toBe('discovering');
    expect(result.current.state.canDiscoverBranches).toBe(false);

    await act(async () => {
      firstDiscovery.resolve({
        branches: ['main', 'main', 'develop'],
        defaultBranch: 'missing',
      });
      await firstResultPromise;
    });
    expect(result.current.state.phase).toBe('idle');
    expect(result.current.state.branches).toEqual(['main', 'develop']);
    expect(result.current.state.selectedBranch).toBe('main');

    let failedResult;
    await act(async () => {
      failedResult = await result.current.events.discoverBranches();
    });
    expect(failedResult).toEqual({
      status: 'failed',
      kind: 'discovery',
      error: 'discoveryFailed',
    });
    expect(result.current.state.error).toBe('discoveryFailed');
    expect(result.current.state.hasDiscoveredBranches).toBe(false);

    let retryResult;
    await act(async () => {
      retryResult = await result.current.events.discoverBranches();
    });
    expect(retryResult).toEqual({ status: 'completed', kind: 'discovery' });
    expect(result.current.state.branches).toEqual(['release']);
    expect(result.current.state.selectedBranch).toBe('release');
  });

  it('tracks clone loading, failure, retry, and success', async () => {
    const clone = vi.fn()
      .mockRejectedValueOnce({ errorCode: 'VC_SSH_KEY_REQUIRED' })
      .mockResolvedValueOnce(undefined);
    const { result } = renderHook(() => useRepositorySetupWorkflow({
      target: createTarget(),
      capability: { canMutate: true },
      remoteEffects: createEffects({ clone }),
    }));

    openCloneWithUrl(result);
    await act(async () => result.current.events.discoverBranches());
    expect(result.current.state.canSubmitClone).toBe(true);

    let failedResult;
    await act(async () => {
      failedResult = await result.current.events.clone();
    });
    expect(failedResult).toEqual({
      status: 'failed',
      kind: 'clone',
      error: 'sshKeyRequired',
    });
    expect(result.current.state.error).toBe('sshKeyRequired');
    expect(result.current.state.cloneDialogOpen).toBe(true);
    expect(result.current.state.canSubmitClone).toBe(true);

    let retryResult;
    await act(async () => {
      retryResult = await result.current.events.clone();
    });
    expect(retryResult).toEqual({ status: 'completed', kind: 'clone' });
    expect(clone).toHaveBeenCalledWith(
      'git@example.com:team/repository.git',
      'main',
    );
    expect(result.current.state.cloneDialogOpen).toBe(false);
    expect(result.current.state.error).toBeNull();
  });

  it('invalidates a pending discovery when the dialog closes', async () => {
    const pendingDiscovery = deferred<VersionControlRemoteBranches>();
    const { result } = renderHook(() => useRepositorySetupWorkflow({
      target: createTarget(),
      capability: { canMutate: true },
      remoteEffects: createEffects({
        discoverBranches: vi.fn().mockReturnValue(pendingDiscovery.promise),
      }),
    }));

    openCloneWithUrl(result);
    let discoveryResultPromise: Promise<unknown>;
    act(() => {
      discoveryResultPromise = result.current.events.discoverBranches();
    });
    act(() => result.current.events.closeClone());
    expect(result.current.state.cloneDialogOpen).toBe(false);

    let resultValue;
    await act(async () => {
      pendingDiscovery.resolve({ branches: ['stale'], defaultBranch: 'stale' });
      resultValue = await discoveryResultPromise;
    });
    expect(resultValue).toEqual({ status: 'stale', kind: 'discovery' });
    expect(result.current.state.branches).toEqual([]);
  });

  it('invalidates pending operations after a scope or safety boundary changes', async () => {
    const pendingInitialize = deferred<unknown>();
    const initialize = vi.fn().mockReturnValue(pendingInitialize.promise);
    const { result, rerender } = renderHook(({
      target,
    }: { target: RepositorySetupTarget }) => useRepositorySetupWorkflow({
      target,
      capability: { canMutate: true },
      remoteEffects: createEffects({ initialize }),
    }), {
      initialProps: { target: createTarget() },
    });

    act(() => result.current.events.openInitialize());
    let initializeResultPromise: Promise<unknown>;
    act(() => {
      initializeResultPromise = result.current.events.initialize();
    });
    expect(result.current.state.phase).toBe('initializing');

    rerender({ target: createTarget(safeRepository, 'workspace:two') });
    expect(result.current.state.initializeDialogOpen).toBe(false);
    rerender({
      target: createTarget({ ...safeRepository, canInitSafely: false }, 'workspace:two'),
    });
    expect(result.current.state.canOpenInitialize).toBe(false);

    let resultValue;
    await act(async () => {
      pendingInitialize.resolve(undefined);
      resultValue = await initializeResultPromise;
    });
    expect(resultValue).toEqual({ status: 'stale', kind: 'initialize' });
    expect(result.current.state.error).toBeNull();
  });

  it('ignores branch discovery settled for a previous remote URL', async () => {
    const first = deferred<VersionControlRemoteBranches>();
    const second = deferred<VersionControlRemoteBranches>();
    const discoverBranches = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    const { result } = renderHook(() => useRepositorySetupWorkflow({
      target: createTarget(),
      capability: { canMutate: true },
      remoteEffects: createEffects({ discoverBranches }),
    }));

    openCloneWithUrl(result, 'git@example.com:team/old.git');
    act(() => void result.current.events.discoverBranches());
    openCloneWithUrl(result, 'git@example.com:team/new.git');
    act(() => void result.current.events.discoverBranches());

    await act(async () => {
      second.resolve({ branches: ['main'], defaultBranch: 'main' });
      await second.promise;
    });
    expect(result.current.state.branches).toEqual(['main']);

    await act(async () => {
      first.resolve({ branches: ['stale'], defaultBranch: 'stale' });
      await first.promise;
    });
    expect(result.current.state.branches).toEqual(['main']);
    expect(result.current.state.selectedBranch).toBe('main');
  });
});
