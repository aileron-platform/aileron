import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/shared/api/apiClient';
import {
  createKnowledgeBaseVersionControlSession,
  createMarketplaceVersionControlSession,
} from './versionControlSession';

const {
  deleteMock,
  getMock,
  patchMock,
  postMock,
  putMock,
} = vi.hoisted(() => ({
  deleteMock: vi.fn(),
  getMock: vi.fn(),
  patchMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => ({
    delete: deleteMock,
    get: getMock,
    patch: patchMock,
    post: postMock,
    put: putMock,
  })),
  ApiError: class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

const createHarness = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false, retryDelay: 0 },
    },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
};

const changesResponse = {
  staged: { items: [], total: 0, nextCursor: null, hasMore: false },
  unstaged: { items: [{
    name: 'notes.md',
    path: 'notes.md',
    status: 'M',
    type: 'modified' as const,
  }], total: 1, nextCursor: null, hasMore: false },
  untracked: { items: [], total: 0, nextCursor: null, hasMore: false },
  conflicts: { items: [], total: 0, nextCursor: null, hasMore: false },
};

describe('versionControlSession capability interface', () => {
  it('only exposes operations supported by each surface', () => {
    const knowledgeBase = createKnowledgeBaseVersionControlSession({
      knowledgeBaseId: 'kb-1',
      isGitRepo: true,
    });
    const marketplace = createMarketplaceVersionControlSession({
      isGitRepo: true,
    });

    expect(Object.keys(knowledgeBase).sort()).toEqual([
      'changes',
      'history',
      'refresh',
      'remote',
    ]);
    expect(Object.keys(marketplace).sort()).toEqual([
      'changes',
      'history',
      'refresh',
      'remote',
    ]);

    expect(Object.keys(knowledgeBase.changes).sort()).toEqual(
      Object.keys(marketplace.changes).sort(),
    );
    expect(Object.keys(knowledgeBase.history).sort()).toEqual([
      'useBranchesQuery',
      'useCommitBlobQuery',
      'useCommitFilesQuery',
      'useCommitsQuery',
      'useCreateBranchMutation',
      'useDeleteBranchMutation',
      'usePublishBranchMutation',
      'useRenameBranchMutation',
      'useRevertCommitMutation',
      'useSwitchBranchMutation',
    ]);
    expect(Object.keys(knowledgeBase.remote).sort()).toEqual([
      'useCancelOperationMutation',
      'useCloneRepositoryMutation',
      'useConvertLfsSnapshotMutation',
      'useFetchMutation',
      'useInitializeRepositoryMutation',
      'useLfsPatternsQuery',
      'usePreviewLfsSnapshotMutation',
      'usePullMutation',
      'usePushMutation',
      'useRemoteBranchesMutation',
      'useRepositoryQuery',
      'useSetRemoteUrlMutation',
      'useUpdateLfsPatternsMutation',
    ]);

    expect(Object.keys(marketplace.changes).sort()).toEqual([
      'isFirstLoad',
      'useAbortConflictMutation',
      'useChangesNumstatQuery',
      'useChangesQuery',
      'useCommitMutation',
      'useDiffQuery',
      'useDiscardMutation',
      'useForceUnlockMutation',
      'useMarkResolvedMutation',
      'useOperationStatusQuery',
      'useStageMutation',
      'useStatusQuery',
      'useUnstageMutation',
    ]);
    expect(Object.keys(marketplace.history).sort()).toEqual([
      'useBranchesQuery',
      'useCommitDiffQuery',
      'useCommitFilesQuery',
      'useCommitsQuery',
      'useCreateBranchMutation',
      'useDeleteBranchMutation',
      'usePublishBranchMutation',
      'useRenameBranchMutation',
      'useRevertCommitMutation',
      'useSwitchBranchMutation',
    ]);
    expect(Object.keys(marketplace.remote).sort()).toEqual([
      'useCancelOperationMutation',
      'useCloneRepositoryMutation',
      'useConvertLfsSnapshotMutation',
      'useFetchMutation',
      'useInitializeRepositoryMutation',
      'useLfsPatternsQuery',
      'usePreviewLfsSnapshotMutation',
      'usePullMutation',
      'usePushMutation',
      'useRemoteBranchesMutation',
      'useRepositoryQuery',
      'useSetRemoteUrlMutation',
      'useUpdateLfsPatternsMutation',
    ]);
  });
});

describe('versionControlSession queries and gating', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    putMock.mockReset();
    patchMock.mockReset();
    deleteMock.mockReset();
  });

  it('keeps repository discovery enabled while git-dependent marketplace queries are gated', async () => {
    getMock.mockResolvedValue({
      isGitRepo: false,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: true,
    });
    const session = createMarketplaceVersionControlSession({ isGitRepo: false });
    const { wrapper } = createHarness();

    const result = renderHook(() => ({
      repository: session.remote.useRepositoryQuery(),
      changes: session.changes.useChangesQuery(),
      commits: session.history.useCommitsQuery(),
    }), { wrapper });

    await waitFor(() => expect(result.result.current.repository.data?.isGitRepo).toBe(false));
    expect(result.result.current.changes.fetchStatus).toBe('idle');
    expect(result.result.current.commits.fetchStatus).toBe('idle');
    expect(getMock).toHaveBeenCalledTimes(1);
    expect(getMock).toHaveBeenCalledWith('/marketplace/version-control/repository');
  });

  it('retries a transient numstat collision without changing its request payload', async () => {
    const retryableConflict = Object.assign(
      new ApiError('Version control operation already in progress', 409),
      {
        operationStatus: {
          isActive: true,
          operation: 'changes.numstat',
          actorDisplayName: null,
          startedAt: '2026-08-12T08:15:30+00:00',
          blockingScope: 'working_tree_target',
          stale: false,
          retryable: true,
          progressCurrent: 0,
          progressTotal: 0,
          phase: '',
          cancellable: false,
          cancelRequested: false,
        },
      },
    );
    postMock
      .mockRejectedValueOnce(retryableConflict)
      .mockResolvedValueOnce({ stats: {} });
    const session = createMarketplaceVersionControlSession({ isGitRepo: true });
    const { wrapper } = createHarness();
    const params = {
      stagedPaths: ['staged.ts'],
      unstagedPaths: ['unstaged.ts'],
    };

    const numstat = renderHook(
      () => session.changes.useChangesNumstatQuery(params),
      { wrapper },
    );

    await waitFor(() => expect(numstat.result.current.isSuccess).toBe(true));
    expect(postMock).toHaveBeenCalledTimes(2);
    expect(postMock).toHaveBeenNthCalledWith(
      1,
      '/marketplace/version-control/changes/numstat',
      params,
    );
    expect(postMock).toHaveBeenNthCalledWith(
      2,
      '/marketplace/version-control/changes/numstat',
      params,
    );
  });

  it('uses the direct marketplace history wire contract', async () => {
    getMock.mockImplementation(async (path: string) => {
      if (path.includes('/commits/abc/files')) {
        return {
          commitId: 'abc',
          files: [{ name: 'notes.md', path: 'nested/notes.md', status: 'M', type: 'modified' }],
        };
      }
      return {
        total: 1,
        nextCursor: null,
        hasMore: false,
        queryScope: 'current',
        items: [{
          id: 'abc',
          message: 'Update notes',
          author: 'Maintainer',
          timestamp: Date.parse('2026-07-30T00:00:00.000Z') / 1000,
          additions: 3,
          deletions: 1,
          files: 1,
        }],
      };
    });
    const session = createMarketplaceVersionControlSession({ isGitRepo: true });
    const { wrapper } = createHarness();

    const result = renderHook(() => ({
      commits: session.history.useCommitsQuery(),
      files: session.history.useCommitFilesQuery('abc'),
    }), { wrapper });

    await waitFor(() => expect(result.result.current.commits.data?.items).toHaveLength(1));
    await waitFor(() => expect(result.result.current.files.data).toHaveLength(1));
    expect(result.result.current.commits.data?.items[0]).toMatchObject({
      id: 'abc',
      timestamp: Date.parse('2026-07-30T00:00:00.000Z') / 1000,
      files: 1,
    });
    expect(result.result.current.files.data?.[0]).toMatchObject({
      name: 'notes.md',
      path: 'nested/notes.md',
    });
  });

  it('adapts knowledge-base requests to its exact backend contract', async () => {
    getMock.mockResolvedValue({ branches: [] });
    postMock.mockResolvedValue({ discarded: ['notes.md'] });
    const session = createKnowledgeBaseVersionControlSession({
      knowledgeBaseId: 'kb-1',
      isGitRepo: true,
    });
    const { wrapper } = createHarness();
    const result = renderHook(() => ({
      branches: session.history.useBranchesQuery(),
      discard: session.changes.useDiscardMutation(),
      initialize: session.remote.useInitializeRepositoryMutation(),
      clone: session.remote.useCloneRepositoryMutation(),
      remoteBranches: session.remote.useRemoteBranchesMutation(),
    }), { wrapper });

    await waitFor(() => expect(result.result.current.branches.isSuccess).toBe(true));
    await act(async () => {
      await result.result.current.discard.mutateAsync(['notes.md']);
      await result.result.current.initialize.mutateAsync({ defaultBranch: 'main' });
      await result.result.current.clone.mutateAsync({
        remoteUrl: 'git@example.com:team/knowledge.git',
        branch: 'develop',
      });
      await result.result.current.remoteBranches.mutateAsync(
        'git@example.com:team/knowledge.git',
      );
    });

    expect(getMock).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/version-control/branches',
    );
    expect(postMock).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/version-control/discard',
      { paths: ['notes.md'] },
    );
    expect(postMock).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/version-control/init',
      { defaultBranch: 'main' },
    );
    expect(postMock).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/version-control/clone',
      {
        remoteUrl: 'git@example.com:team/knowledge.git',
        branch: 'develop',
      },
    );
    expect(postMock).toHaveBeenCalledWith(
      '/knowledge-bases/kb-1/version-control/remote-branches',
      { remoteUrl: 'git@example.com:team/knowledge.git' },
    );
  });

  it('adapts marketplace stage and remote mutations without unsupported payloads', async () => {
    postMock.mockResolvedValue({ success: true });
    const session = createMarketplaceVersionControlSession({ isGitRepo: true });
    const { wrapper } = createHarness();
    const result = renderHook(() => ({
      stage: session.changes.useStageMutation(),
      fetch: session.remote.useFetchMutation(),
      pull: session.remote.usePullMutation(),
      push: session.remote.usePushMutation(),
      remoteBranches: session.remote.useRemoteBranchesMutation(),
    }), { wrapper });

    await act(async () => {
      await result.result.current.stage.mutateAsync(['notes.md']);
      await result.result.current.fetch.mutateAsync(undefined);
      await result.result.current.pull.mutateAsync(undefined);
      await result.result.current.push.mutateAsync(undefined);
      await result.result.current.remoteBranches.mutateAsync(
        'git@example.com:team/marketplace.git',
      );
    });

    expect(postMock).toHaveBeenCalledWith(
      '/marketplace/version-control/stage',
      { paths: ['notes.md'] },
    );
    expect(postMock).toHaveBeenCalledWith(
      '/marketplace/version-control/fetch',
      undefined,
    );
    expect(postMock).toHaveBeenCalledWith(
      '/marketplace/version-control/pull',
      undefined,
    );
    expect(postMock).toHaveBeenCalledWith(
      '/marketplace/version-control/push',
      undefined,
    );
    expect(postMock).toHaveBeenCalledWith(
      '/marketplace/version-control/remote-branches',
      { remoteUrl: 'git@example.com:team/marketplace.git' },
    );
  });

  it('propagates marketplace clone failures from the direct error envelope', async () => {
    postMock.mockRejectedValue(Object.assign(
      new ApiError('SSH key required', 409),
      { errorCode: 'VC_SSH_KEY_REQUIRED', messageKey: 'VC_SSH_KEY_REQUIRED' },
    ));
    const session = createMarketplaceVersionControlSession({ isGitRepo: false });
    const { wrapper } = createHarness();
    const clone = renderHook(
      () => session.remote.useCloneRepositoryMutation(),
      { wrapper },
    );

    await act(async () => {
      await expect(clone.result.current.mutateAsync({
        remoteUrl: 'git@example.com:team/marketplace.git',
      })).rejects.toMatchObject({
        errorCode: 'VC_SSH_KEY_REQUIRED',
      });
    });
  });

  it('optimistically stages all cached files and rolls back on failure', async () => {
    const serverChanges = changesResponse;
    getMock.mockImplementation(async (path: string) =>
      path.includes('/changes') ? serverChanges : {});
    postMock.mockRejectedValue(new Error('stage failed'));
    const session = createKnowledgeBaseVersionControlSession({
      knowledgeBaseId: 'kb-1',
      isGitRepo: true,
    });
    const { wrapper } = createHarness();
    const changes = renderHook(
      () => session.changes.useChangesQuery(),
      { wrapper },
    );
    await waitFor(() => expect(changes.result.current.data?.unstaged.items).toHaveLength(1));
    const stage = renderHook(
      () => session.changes.useStageMutation(),
      { wrapper },
    );

    await act(async () => {
      await expect(stage.result.current.mutateAsync({ all: true }))
        .rejects.toThrow('stage failed');
    });

    expect(changes.result.current.data).toEqual(serverChanges);
    expect(changes.result.current.data?.unstaged.items).toHaveLength(1);
  });

});
