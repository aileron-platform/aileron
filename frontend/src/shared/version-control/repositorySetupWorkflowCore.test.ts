import { describe, expect, it } from 'vitest';
import {
  createInitialRepositorySetupState,
  createRepositorySetupCommand,
  deriveRepositorySetupViewModel,
  reduceRepositorySetupState,
  repositorySetupBoundarySignature,
  type RepositorySetupCapability,
  type RepositorySetupTarget,
} from './repositorySetupWorkflowCore';
import type { VersionControlRepositoryStatus } from './types';

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

const target: RepositorySetupTarget = {
  scopeKey: 'knowledge-base:one',
  repository: safeRepository,
};

const capability: RepositorySetupCapability = { canMutate: true };

describe('repository setup workflow core', () => {
  it('derives a fail-closed view model for unknown safety', () => {
    const viewModel = deriveRepositorySetupViewModel(
      createInitialRepositorySetupState(0),
      { ...target, repository: null },
      capability,
      true,
    );

    expect(viewModel.safetyKnown).toBe(false);
    expect(viewModel.canOpenInitialize).toBe(false);
    expect(viewModel.canOpenClone).toBe(false);
    expect(viewModel.canDiscoverBranches).toBe(false);
    expect(viewModel.canSubmitClone).toBe(false);
  });

  it('owns initialize phase transitions and ignores an old command settlement', () => {
    const initial = createInitialRepositorySetupState(0);
    const opened = reduceRepositorySetupState(initial, {
      type: 'openInitialize',
      generation: 0,
    });
    const command = createRepositorySetupCommand(0, 1, 'initialize');
    const loading = reduceRepositorySetupState(opened, {
      type: 'commandStarted',
      command,
    });

    expect(loading.phase).toBe('initializing');
    expect(loading.initializeDialogOpen).toBe(true);

    const closed = reduceRepositorySetupState(loading, {
      type: 'closeInitialize',
      generation: 0,
    });
    expect(closed.phase).toBe('idle');
    expect(closed.activeCommand).toBeNull();
    expect(reduceRepositorySetupState(closed, {
      type: 'initializeSucceeded',
      command,
    })).toEqual(closed);
  });

  it('invalidates the boundary when target identity or safety changes', () => {
    const initialSignature = repositorySetupBoundarySignature(target, capability);
    const nextSignature = repositorySetupBoundarySignature(
      {
        ...target,
        scopeKey: 'knowledge-base:two',
      },
      capability,
    );
    const unsafeSignature = repositorySetupBoundarySignature(
      {
        ...target,
        repository: { ...safeRepository, canCloneSafely: false },
      },
      capability,
    );

    expect(nextSignature).not.toBe(initialSignature);
    expect(unsafeSignature).not.toBe(initialSignature);
  });

  it('reconciles discovered branches to a valid selected branch', () => {
    const opened = reduceRepositorySetupState(
      createInitialRepositorySetupState(0),
      { type: 'openClone', generation: 0 },
    );
    const withUrl = reduceRepositorySetupState(opened, {
      type: 'remoteUrlChanged',
      generation: 0,
      remoteUrl: 'git@example.com:team/repository.git',
    });
    const command = createRepositorySetupCommand(0, 1, 'discovery');
    const loading = reduceRepositorySetupState(withUrl, {
      type: 'commandStarted',
      command,
    });
    const settled = reduceRepositorySetupState(loading, {
      type: 'discoverySucceeded',
      command,
      remoteUrl: 'git@example.com:team/repository.git',
      result: {
        branches: ['main', 'main', 'develop'],
        defaultBranch: 'missing',
      },
    });

    expect(settled.branches).toEqual(['main', 'develop']);
    expect(settled.selectedBranch).toBe('main');
    expect(settled.hasDiscoveredBranches).toBe(true);
  });
});
