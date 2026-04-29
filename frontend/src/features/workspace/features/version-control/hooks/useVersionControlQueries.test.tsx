import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';

import {
  useCheckoutMutation,
  useCommitMutation,
  useDiscardMutation,
  useFetchMutation,
  usePullMutation,
  usePushMutation,
  useStageMutation,
  useUnstageMutation,
} from './useVersionControlQueries';
import { refreshVersionControlQueries } from '../lib/queryClient';

const { postMock, refreshMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  refreshMock: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  ApiClient: vi.fn().mockImplementation(() => ({
    post: postMock,
  })),
  ApiError: class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock('../lib/queryClient', async (importActual) => {
  const actual = await importActual<typeof import('../lib/queryClient')>();
  return {
    ...actual,
    refreshVersionControlQueries: refreshMock,
  };
});

describe('useVersionControlQueries mutations', () => {
  const options = {
    workspaceId: 'ws-1',
    runtimeBaseUrl: 'http://runtime',
    contextId: 'worktree:feature',
  };

  const createWrapper = () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });

    return ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };

  beforeEach(() => {
    vi.useFakeTimers();
    postMock.mockResolvedValue({});
    refreshMock.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    postMock.mockReset();
    refreshMock.mockReset();
  });

  it('refreshes only changes and status after stage, unstage, and discard', async () => {
    const stage = renderHook(() => useStageMutation(options), { wrapper: createWrapper() });
    const unstage = renderHook(() => useUnstageMutation(options), { wrapper: createWrapper() });
    const discard = renderHook(() => useDiscardMutation(options), { wrapper: createWrapper() });

    await act(async () => {
      const pending = stage.result.current.mutateAsync(['a.py']);
      await vi.advanceTimersByTimeAsync(100);
      await pending;
      const pendingUnstage = unstage.result.current.mutateAsync(['a.py']);
      await vi.advanceTimersByTimeAsync(100);
      await pendingUnstage;
      await discard.result.current.mutateAsync(['a.py']);
    });

    expect(refreshVersionControlQueries).toHaveBeenCalledTimes(3);
    for (const call of refreshMock.mock.calls) {
      expect(call[2]).toEqual({
        includeBranches: false,
        contextId: 'worktree:feature',
      });
    }
  });

  it('refreshes commit history after commit', async () => {
    const commit = renderHook(() => useCommitMutation(options), { wrapper: createWrapper() });

    await act(async () => {
      const pending = commit.result.current.mutateAsync('message');
      await vi.advanceTimersByTimeAsync(100);
      await pending;
    });

    expect(refreshVersionControlQueries).toHaveBeenCalledWith(
      expect.any(QueryClient),
      'ws-1',
      {
        includeCommits: true,
        contextId: 'worktree:feature',
      },
    );
  });

  it('sends remote operation payloads with context and refreshes broad version-control data', async () => {
    const fetch = renderHook(() => useFetchMutation(options), { wrapper: createWrapper() });
    const pull = renderHook(() => usePullMutation(options), { wrapper: createWrapper() });
    const push = renderHook(() => usePushMutation(options), { wrapper: createWrapper() });

    await act(async () => {
      await fetch.result.current.mutateAsync({ remote: 'origin' });
      await pull.result.current.mutateAsync({ remote: 'origin', branch: 'main', rebase: true, autostash: true });
      await push.result.current.mutateAsync({ remote: 'origin', branch: 'main', force: false });
    });

    expect(postMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-1/version-control/fetch?contextId=worktree%3Afeature',
      { remote: 'origin', prune: false },
    );
    expect(postMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/version-control/pull?contextId=worktree%3Afeature',
      { remote: 'origin', branch: 'main', rebase: true, autostash: true },
    );
    expect(postMock).toHaveBeenNthCalledWith(
      3,
      '/api/v1/workspaces/ws-1/version-control/push?contextId=worktree%3Afeature',
      { remote: 'origin', branch: 'main', force: false },
    );
    expect(refreshVersionControlQueries).toHaveBeenCalledTimes(3);
    for (const call of refreshMock.mock.calls) {
      expect(call[2]).toEqual({
        includeBranches: true,
        includeCommits: true,
        includeContexts: true,
        contextId: 'worktree:feature',
      });
    }
  });

  it('sends checkout and create branch payloads with context', async () => {
    const checkout = renderHook(() => useCheckoutMutation(options), { wrapper: createWrapper() });

    await act(async () => {
      await checkout.result.current.mutateAsync({ branch: 'feature/a', create: false, stashChanges: false });
      await checkout.result.current.mutateAsync({
        branch: 'feature/new',
        create: true,
        startPoint: 'origin/main',
        stashChanges: true,
      });
    });

    expect(postMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/workspaces/ws-1/version-control/branches/feature%2Fa/checkout?contextId=worktree%3Afeature',
      { create: false, startPoint: undefined, stashChanges: false },
    );
    expect(postMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/workspaces/ws-1/version-control/branches/feature%2Fnew/checkout?contextId=worktree%3Afeature',
      { create: true, startPoint: 'origin/main', stashChanges: true },
    );
  });
});
