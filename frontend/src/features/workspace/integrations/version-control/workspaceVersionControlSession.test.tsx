import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiClient, ApiError } from '@/shared/api/apiClient';
import { useVersionControlPagedChanges } from '@/shared/components/version-control';
import { createWorkspaceVersionControlSession } from './workspaceVersionControlSession';

const { getMock, postMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => ({
    delete: vi.fn(),
    get: getMock,
    patch: vi.fn(),
    post: postMock,
    put: vi.fn(),
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
      queries: { retry: false },
    },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
};

const changesResponse = {
  staged: { items: [], total: 0, nextCursor: null, hasMore: false },
  unstaged: {
    items: [{
      name: 'notes.md',
      path: 'notes.md',
      status: 'M',
      type: 'modified' as const,
    }],
    total: 1,
    nextCursor: null,
    hasMore: false,
  },
  untracked: { items: [], total: 0, nextCursor: null, hasMore: false },
  conflicts: { items: [], total: 0, nextCursor: null, hasMore: false },
};

describe('workspaceVersionControlSession', () => {
  beforeEach(() => {
    vi.mocked(ApiClient).mockClear();
    getMock.mockReset();
    postMock.mockReset();
  });

  it('exposes the workspace-only worktree capability with the shared contract', () => {
    const session = createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime',
    });

    expect(Object.keys(session).sort()).toEqual([
      'changes',
      'history',
      'refresh',
      'remote',
    ]);
    expect(Object.keys(session.changes).sort()).toEqual([
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
    expect(Object.keys(session.history).sort()).toEqual([
      'useBranchesQuery',
      'useCommitFilesQuery',
      'useCommitsInfiniteQuery',
      'useContextsQuery',
      'useCreateBranchMutation',
      'useDeleteBranchMutation',
      'usePublishBranchMutation',
      'useRenameBranchMutation',
      'useRevertCommitMutation',
      'useSwitchBranchMutation',
    ]);
    expect(Object.keys(session.remote).sort()).toEqual([
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
      'useRemoteSettingsQuery',
      'useRepositoryQuery',
      'useSetRemoteUrlMutation',
      'useUpdateLfsPatternsMutation',
    ]);
  });

  it('uses one runtime-authorized client for every workspace version-control request', () => {
    createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime',
    });

    expect(ApiClient).toHaveBeenCalledTimes(1);
    expect(ApiClient).toHaveBeenCalledWith({
      baseUrl: 'http://runtime/api/v1',
      executionAudience: 'workspace-runtime',
      unauthorizedBehavior: 'propagate',
    });
  });

  it('loads workspace contexts through the runtime-authorized core without a target context', async () => {
    getMock.mockResolvedValue({ activeContextId: 'primary', contexts: [] });
    const session = createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime',
      contextId: 'worktree-1',
    });
    const { wrapper } = createHarness();

    const result = renderHook(() => session.history.useContextsQuery(), { wrapper });

    await waitFor(() => expect(result.result.current.isSuccess).toBe(true));
    expect(getMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/version-control/contexts',
    );
  });

  it('does not query version control before the runtime resolves', () => {
    const session = createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: '',
    });
    const { wrapper } = createHarness();

    const result = renderHook(() => ({
      changes: session.changes.useChangesQuery({ page: 1 }),
      history: session.history.useCommitsInfiniteQuery({ pageSize: 20 }),
      remote: session.remote.useRemoteSettingsQuery(),
    }), { wrapper });

    expect(result.result.current.changes.fetchStatus).toBe('idle');
    expect(result.result.current.history.fetchStatus).toBe('idle');
    expect(result.result.current.remote.fetchStatus).toBe('idle');
    expect(getMock).not.toHaveBeenCalled();
  });

  it('builds workspace mutation paths', async () => {
    postMock.mockResolvedValue({ branch: 'feature/new', created: true });
    const session = createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime',
    });
    const { wrapper } = createHarness();
    const mutations = renderHook(() => ({
      createBranch: session.history.useCreateBranchMutation(),
      initialize: session.remote.useInitializeRepositoryMutation(),
      clone: session.remote.useCloneRepositoryMutation(),
      remoteBranches: session.remote.useRemoteBranchesMutation(),
    }), { wrapper });

    await act(async () => {
      await mutations.result.current.createBranch.mutateAsync({
        name: 'feature/new',
        startPoint: 'origin/main',
      });
      await mutations.result.current.initialize.mutateAsync(undefined);
      await mutations.result.current.clone.mutateAsync({
        remoteUrl: 'git@example.com:team/repository.git',
        branch: 'develop',
      });
      await mutations.result.current.remoteBranches.mutateAsync(
        'git@example.com:team/repository.git',
      );
    });

    expect(postMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/version-control/branches/create',
      { name: 'feature/new', startPoint: 'origin/main' },
    );
    expect(postMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/version-control/init',
      undefined,
    );
    expect(postMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/version-control/clone',
      {
        remoteUrl: 'git@example.com:team/repository.git',
        branch: 'develop',
      },
    );
    expect(postMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/version-control/remote-branches',
      { remoteUrl: 'git@example.com:team/repository.git' },
    );
  });

  it('propagates an active changes refresh failure', async () => {
    getMock.mockResolvedValue(changesResponse);
    const session = createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime',
    });
    const { queryClient, wrapper } = createHarness();
    const changes = renderHook(
      () => session.changes.useChangesQuery(),
      { wrapper },
    );
    await waitFor(() => expect(changes.result.current.isSuccess).toBe(true));
    getMock.mockRejectedValue(new ApiError('refresh failed', 400));

    await expect(session.refresh(queryClient, ['changes']))
      .rejects.toThrow('refresh failed');
  });

  it('holds back paged changes until the repository reports an initialized status', async () => {
    getMock.mockImplementation(async (path: string) => (
      path.endsWith('/status')
        ? { isInitialized: false, currentBranch: null, hasConflicts: false }
        : changesResponse
    ));
    const session = createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime',
    });
    const { wrapper } = createHarness();

    const paged = renderHook(
      () => useVersionControlPagedChanges(session.changes),
      { wrapper },
    );

    await waitFor(() => expect(getMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/version-control/status',
    ));
    expect(paged.result.current.queries.all.every(query => query.fetchStatus === 'idle'))
      .toBe(true);
    expect(getMock.mock.calls.every(([path]) => !String(path).includes('/changes')))
      .toBe(true);
  });

  it('queries paged changes once the repository is initialized', async () => {
    getMock.mockImplementation(async (path: string) => (
      path.endsWith('/status')
        ? { isInitialized: true, currentBranch: 'main', hasConflicts: false }
        : changesResponse
    ));
    const session = createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime',
    });
    const { wrapper } = createHarness();

    const paged = renderHook(
      () => useVersionControlPagedChanges(session.changes),
      { wrapper },
    );

    await waitFor(() => expect(paged.result.current.files.unstaged).toHaveLength(1));
    expect(getMock).toHaveBeenCalledWith(
      '/workspaces/ws-1/version-control/changes?group=staged&limit=100&includeStats=false',
    );
  });

  it('preserves the Git change group on paged files used by the diff viewer', async () => {
    const groupedChangesResponse = {
      ...changesResponse,
      staged: {
        items: [{
          name: 'new-report.md',
          path: 'new-report.md',
          status: 'A',
          type: 'added' as const,
        }],
        total: 1,
        nextCursor: null,
        hasMore: false,
      },
      untracked: {
        items: [{
          name: 'draft.md',
          path: 'draft.md',
          status: '?',
          type: 'untracked' as const,
        }],
        total: 1,
        nextCursor: null,
        hasMore: false,
      },
    };
    getMock.mockImplementation(async (path: string) => (
      path.endsWith('/status')
        ? { isInitialized: true, currentBranch: 'main', hasConflicts: false }
        : groupedChangesResponse
    ));
    const session = createWorkspaceVersionControlSession({
      workspaceId: 'ws-1',
      runtimeBaseUrl: 'http://runtime',
    });
    const { wrapper } = createHarness();

    const paged = renderHook(
      () => useVersionControlPagedChanges(session.changes),
      { wrapper },
    );

    await waitFor(() => expect(paged.result.current.files.staged).toHaveLength(1));
    expect(paged.result.current.files.staged[0]).toMatchObject({
      path: 'new-report.md',
      changeType: 'staged',
    });
    expect(paged.result.current.files.unstaged[0]).toMatchObject({
      path: 'notes.md',
      changeType: 'unstaged',
    });
    expect(paged.result.current.files.untracked[0]).toMatchObject({
      path: 'draft.md',
      changeType: 'untracked',
    });
  });
});
