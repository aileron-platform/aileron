import React from 'react';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { usePlatformResourcesDataSession } from './usePlatformResourcesDataSession';

const apiMocks = vi.hoisted(() => ({
  getPlatformResourceSummary: vi.fn(),
  getPlatformResourceResourceTrend: vi.fn(),
  getPlatformResourceCapacityTrend: vi.fn(),
  listPlatformWorkspaces: vi.fn(),
  listPlatformKnowledgeBases: vi.fn(),
  searchPlatformResourceOwnerCandidates: vi.fn(),
  reassignPlatformResourceOwner: vi.fn(),
  updatePlatformKnowledgeBaseQuota: vi.fn(),
  requestWorkspaceCapacityExpansion: vi.fn(),
  getWorkspaceCapacityExpansion: vi.fn(),
}));

vi.mock('../api/platformResourcesApi', () => apiMocks);

type SessionInput = Parameters<typeof usePlatformResourcesDataSession>[0];

const allowedOperations = [
  'platform_resources.read',
  'platform_resources.owner.reassign',
  'platform_resources.knowledge_base.quota.update',
  'platform_resources.workspace.capacity.expand',
] as const;

const defaultInput: SessionInput = {
  authSubject: 'subject-1',
  kind: 'workspaces',
  section: 'management',
  range: '30d',
  listQuery: { q: '', page: 1, pageSize: 25 },
  allowedOperations,
};

const owner = (id: string) => ({
  id,
  username: id,
  displayName: id,
  avatarUrl: null,
});

const workspace = (ownerId = 'owner-1') => ({
  id: 'ws-1',
  name: 'Workspace One',
  owner: owner(ownerId),
  runtimeStatus: 'running',
  workspaceData: null,
  runtimeHome: null,
  capacityRisk: 'normal' as const,
  provisioner: 'kubernetes' as const,
});

const knowledgeBase = (capacityRisk: 'normal' | 'critical' | 'stale') => ({
  id: 'kb-1',
  name: 'Knowledge Base One',
  owner: owner('owner-1'),
  visibility: 'private' as const,
  currentSizeBytes: 2 * 1024 ** 3,
  quotaBytes: 4 * 1024 ** 3,
  effectiveQuotaBytes: 4 * 1024 ** 3,
  quotaSource: 'custom' as const,
  utilizationPercent: 50,
  capacityRisk,
  indexingHealth: 'success' as const,
});

const statistics = (range: '7d' | '30d' | '90d') => ({
  range,
  timeZone: 'Asia/Taipei',
  calculatedAt: `${range}-calculated`,
  collectionStartedAt: null,
  isStale: false,
  metrics: {
    total: { value: 1, previousValue: null, changePercent: null },
    active: { value: 1, previousValue: null, changePercent: null },
    usedBytes: { value: 1, previousValue: null, changePercent: null },
    nearLimit: { value: 0, previousValue: null, changePercent: null },
  },
  distributions: [],
});

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
};

const renderSession = (input: SessionInput = defaultInput, queryClient?: QueryClient) => {
  const client = queryClient ?? new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return {
    ...renderHook(
      (props: SessionInput) => usePlatformResourcesDataSession(props),
      { initialProps: input, wrapper },
    ),
    queryClient: client,
  };
};

describe('usePlatformResourcesDataSession', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.listPlatformWorkspaces.mockResolvedValue({
      items: [workspace()], total: 1, page: 1, pageSize: 25,
    });
    apiMocks.listPlatformKnowledgeBases.mockResolvedValue({
      items: [knowledgeBase('normal')], total: 1, page: 1, pageSize: 25,
    });
    apiMocks.getPlatformResourceSummary.mockImplementation(
      (_kind, range) => Promise.resolve(statistics(range)),
    );
    apiMocks.getPlatformResourceResourceTrend.mockResolvedValue({
      range: '30d', timeZone: 'Asia/Taipei', calculatedAt: 'now',
      collectionStartedAt: null, isStale: false, points: [],
    });
    apiMocks.getPlatformResourceCapacityTrend.mockResolvedValue({
      range: '30d', timeZone: 'Asia/Taipei', calculatedAt: 'now',
      collectionStartedAt: null, isStale: false, points: [],
    });
    apiMocks.searchPlatformResourceOwnerCandidates.mockResolvedValue([]);
    apiMocks.reassignPlatformResourceOwner.mockResolvedValue(workspace('owner-2'));
    apiMocks.updatePlatformKnowledgeBaseQuota.mockResolvedValue({
      knowledgeBaseId: 'kb-1',
      currentSizeBytes: 2 * 1024 ** 3,
      quotaBytes: 8 * 1024 ** 3,
      effectiveQuotaBytes: 8 * 1024 ** 3,
      quotaSource: 'custom',
    });
    apiMocks.requestWorkspaceCapacityExpansion.mockResolvedValue({
      requestId: 'request-1', workspaceId: 'ws-1', phase: 'pending',
      storageKind: 'workspace_data', previousBytes: 20, requestedBytes: 30,
      createdAt: 'now', updatedAt: 'now',
    });
    apiMocks.getWorkspaceCapacityExpansion.mockResolvedValue({
      requestId: 'request-1', workspaceId: 'ws-1', phase: 'completed',
      storageKind: 'workspace_data', previousBytes: 20, requestedBytes: 30,
      createdAt: 'now', updatedAt: 'later',
    });
  });

  it('isolates analytics by range and aborts the stale request', async () => {
    const oldSummary = deferred<ReturnType<typeof statistics>>();
    const newSummary = deferred<ReturnType<typeof statistics>>();
    apiMocks.getPlatformResourceSummary
      .mockImplementationOnce(() => oldSummary.promise)
      .mockImplementationOnce(() => newSummary.promise);
    const initial = { ...defaultInput, section: 'analytics' as const };
    const view = renderSession(initial);

    await waitFor(() => expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(1));
    const oldSignal = apiMocks.getPlatformResourceSummary.mock.calls[0][3] as AbortSignal;
    view.rerender({ ...initial, range: '90d' });
    await waitFor(() => expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(2));
    expect(oldSignal.aborted).toBe(true);

    await act(async () => { newSummary.resolve(statistics('90d')); });
    await waitFor(() => expect(view.result.current.analytics.summary.data?.range).toBe('90d'));
    await act(async () => { oldSummary.resolve(statistics('30d')); });
    expect(view.result.current.analytics.summary.data?.range).toBe('90d');
  });

  it('cancels the active analytics fetch before refresh=true writes the same view', async () => {
    const initialSummary = deferred<ReturnType<typeof statistics>>();
    apiMocks.getPlatformResourceSummary
      .mockImplementationOnce(() => initialSummary.promise)
      .mockResolvedValueOnce(statistics('30d'));
    const view = renderSession({ ...defaultInput, section: 'analytics' });

    await waitFor(() => expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(1));
    const initialSignal = apiMocks.getPlatformResourceSummary.mock.calls[0][3] as AbortSignal;
    await act(async () => { await view.result.current.refresh.run(); });

    expect(initialSignal.aborted).toBe(true);
    expect(apiMocks.getPlatformResourceSummary).toHaveBeenLastCalledWith(
      'workspaces', '30d', true, expect.any(AbortSignal),
    );
    await waitFor(() => {
      expect(view.result.current.analytics.summary.data?.range).toBe('30d');
    });
  });

  it('does not expose stale candidates after reset and a new search', async () => {
    const oldCandidates = deferred<Array<{ id: string; username: string; displayName: string }>>();
    const newCandidates = deferred<Array<{ id: string; username: string; displayName: string }>>();
    apiMocks.searchPlatformResourceOwnerCandidates.mockImplementation(query => (
      query === 'old' ? oldCandidates.promise : newCandidates.promise
    ));
    const view = renderSession();
    await waitFor(() => expect(view.result.current.inventory.items[0]?.id).toBe('ws-1'));
    act(() => { view.result.current.commands.openOwnerReassignment(workspace()); });

    act(() => { void view.result.current.dialogs.ownerReassignment.search('old'); });
    await waitFor(() => expect(apiMocks.searchPlatformResourceOwnerCandidates).toHaveBeenCalledTimes(1));
    const oldSignal = apiMocks.searchPlatformResourceOwnerCandidates.mock.calls[0][1] as AbortSignal;
    act(() => { view.result.current.dialogs.ownerReassignment.reset(); });
    await waitFor(() => expect(oldSignal.aborted).toBe(true));
    act(() => { view.result.current.commands.openOwnerReassignment(workspace()); });
    act(() => { void view.result.current.dialogs.ownerReassignment.search('new'); });
    await waitFor(() => expect(apiMocks.searchPlatformResourceOwnerCandidates).toHaveBeenCalledTimes(2));

    await act(async () => {
      newCandidates.resolve([{ id: 'new', username: 'new', displayName: 'New Owner' }]);
    });
    await waitFor(() => expect(view.result.current.dialogs.ownerReassignment.candidates[0]?.id).toBe('new'));
    await act(async () => {
      oldCandidates.resolve([{ id: 'old', username: 'old', displayName: 'Old Owner' }]);
    });
    expect(view.result.current.dialogs.ownerReassignment.candidates[0]?.id).toBe('new');
  });

  it('retries a failed candidate search when the normalized query is unchanged', async () => {
    apiMocks.searchPlatformResourceOwnerCandidates
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce([{ id: 'new', username: 'new', displayName: 'New Owner' }]);
    const view = renderSession();
    await waitFor(() => expect(view.result.current.inventory.items[0]?.id).toBe('ws-1'));
    act(() => { view.result.current.commands.openOwnerReassignment(workspace()); });

    act(() => { void view.result.current.dialogs.ownerReassignment.search(' next owner '); });
    await waitFor(() => expect(view.result.current.dialogs.ownerReassignment.searchError).toBe(true));
    await act(async () => {
      await view.result.current.dialogs.ownerReassignment.search('next owner');
    });

    expect(apiMocks.searchPlatformResourceOwnerCandidates).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect(view.result.current.dialogs.ownerReassignment.candidates[0]?.id).toBe('new');
    });
  });

  it('hides an old workspace expansion while its durable monitor continues', async () => {
    const oldStatus = deferred<Awaited<ReturnType<typeof apiMocks.getWorkspaceCapacityExpansion>>>();
    apiMocks.getWorkspaceCapacityExpansion.mockImplementation(() => oldStatus.promise);
    const view = renderSession();
    await waitFor(() => expect(view.result.current.inventory.items[0]?.id).toBe('ws-1'));
    act(() => { view.result.current.commands.openCapacityExpansion(workspace()); });

    await act(async () => {
      await view.result.current.dialogs.capacityExpansion.submit({
        storageKind: 'workspace_data', requestedBytes: 30,
      });
    });
    await waitFor(() => expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(1));
    const oldSignal = apiMocks.getWorkspaceCapacityExpansion.mock.calls[0][2] as AbortSignal;
    act(() => { view.result.current.commands.openCapacityExpansion({ ...workspace(), id: 'ws-2' }); });

    expect(view.result.current.dialogs.capacityExpansion.status).toBeNull();
    await act(async () => {
      oldStatus.resolve({
        requestId: 'request-1', workspaceId: 'ws-1', phase: 'completed',
        storageKind: 'workspace_data', previousBytes: 20, requestedBytes: 30,
        createdAt: 'now', updatedAt: 'later',
      });
    });
    expect(oldSignal.aborted).toBe(false);
    expect(view.result.current.dialogs.capacityExpansion.status).toBeNull();
  });

  it('does not expose an old subject expansion while monitoring its submitted subject', async () => {
    const request = deferred<Awaited<ReturnType<typeof apiMocks.requestWorkspaceCapacityExpansion>>>();
    apiMocks.requestWorkspaceCapacityExpansion.mockImplementation(() => request.promise);
    const view = renderSession();
    await waitFor(() => expect(view.result.current.inventory.items[0]?.id).toBe('ws-1'));
    act(() => { view.result.current.commands.openCapacityExpansion(workspace()); });
    let submission!: Promise<void>;

    act(() => {
      submission = view.result.current.dialogs.capacityExpansion.submit({
        storageKind: 'workspace_data', requestedBytes: 30,
      });
    });
    await waitFor(() => expect(apiMocks.requestWorkspaceCapacityExpansion).toHaveBeenCalledTimes(1));
    view.rerender({ ...defaultInput, authSubject: 'subject-2' });
    expect(view.result.current.dialogs.capacityExpansion.isSubmitting).toBe(false);
    expect(view.result.current.dialogs.capacityExpansion.status).toBeNull();

    await act(async () => {
      request.resolve({
        requestId: 'request-1', workspaceId: 'ws-1', phase: 'pending',
        storageKind: 'workspace_data', previousBytes: 20, requestedBytes: 30,
        createdAt: 'now', updatedAt: 'now',
      });
      await submission;
    });
    expect(view.result.current.dialogs.capacityExpansion.status).toBeNull();
    await waitFor(() => expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(1));
  });

  it('does not reattach an old expansion status after leaving and returning to a context', async () => {
    const status = deferred<Awaited<ReturnType<typeof apiMocks.getWorkspaceCapacityExpansion>>>();
    apiMocks.getWorkspaceCapacityExpansion.mockImplementation(() => status.promise);
    const view = renderSession();
    await waitFor(() => expect(view.result.current.inventory.items[0]?.id).toBe('ws-1'));
    act(() => { view.result.current.commands.openCapacityExpansion(workspace()); });

    await act(async () => {
      await view.result.current.dialogs.capacityExpansion.submit({
        storageKind: 'workspace_data', requestedBytes: 30,
      });
    });
    await waitFor(() => expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(1));
    const oldSignal = apiMocks.getWorkspaceCapacityExpansion.mock.calls[0][2] as AbortSignal;
    view.rerender({ ...defaultInput, section: 'analytics' });
    view.rerender(defaultInput);

    expect(oldSignal.aborted).toBe(false);
    expect(view.result.current.dialogs.capacityExpansion.status).toBeNull();
    expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(1);
    await act(async () => {
      status.resolve({
        requestId: 'request-1', workspaceId: 'ws-1', phase: 'completed',
        storageKind: 'workspace_data', previousBytes: 20, requestedBytes: 30,
        createdAt: 'now', updatedAt: 'later',
      });
    });
  });

  it('refetches Manager projection after quota mutation without inferring risk', async () => {
    apiMocks.listPlatformKnowledgeBases
      .mockResolvedValueOnce({
        items: [knowledgeBase('critical')], total: 1, page: 1, pageSize: 25,
      })
      .mockResolvedValueOnce({
        items: [knowledgeBase('stale')], total: 1, page: 1, pageSize: 25,
      });
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    renderSession({
      ...defaultInput,
      kind: 'knowledge-bases',
      section: 'analytics',
    }, queryClient);
    const view = renderSession({
      ...defaultInput,
      kind: 'knowledge-bases',
    }, queryClient);
    await waitFor(() => expect(view.result.current.inventory.items[0]?.capacityRisk).toBe('critical'));
    await waitFor(() => expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(1));
    act(() => {
      view.result.current.commands.openKnowledgeBaseQuota(knowledgeBase('critical'));
    });

    await act(async () => {
      await view.result.current.dialogs.knowledgeBaseQuota.submit(8 * 1024 ** 3);
    });

    expect(apiMocks.listPlatformKnowledgeBases).toHaveBeenCalledTimes(2);
    expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(2);
    expect(apiMocks.getPlatformResourceCapacityTrend).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect(view.result.current.inventory.items[0]?.capacityRisk).toBe('stale');
    });
  });

  it('completes reassignment only after the active inventory refetches', async () => {
    apiMocks.listPlatformWorkspaces
      .mockResolvedValueOnce({ items: [workspace('owner-1')], total: 1, page: 1, pageSize: 25 })
      .mockResolvedValueOnce({ items: [workspace('owner-2')], total: 1, page: 1, pageSize: 25 });
    const view = renderSession();
    await waitFor(() => expect(view.result.current.inventory.items[0]?.owner.id).toBe('owner-1'));
    act(() => { view.result.current.commands.openOwnerReassignment(workspace()); });

    await act(async () => {
      await view.result.current.dialogs.ownerReassignment.submit({
        targetUserId: 'owner-2', reason: 'Operational change',
      });
    });

    expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledTimes(2);
    await waitFor(() => {
      expect(view.result.current.inventory.items[0]?.owner.id).toBe('owner-2');
    });
  });

  it('keeps reassignment bound to the submitted kind and resource identity', async () => {
    const reassignment = deferred<ReturnType<typeof workspace>>();
    apiMocks.reassignPlatformResourceOwner.mockImplementation(() => reassignment.promise);
    const view = renderSession();
    await waitFor(() => expect(view.result.current.inventory.items[0]?.id).toBe('ws-1'));
    act(() => { view.result.current.commands.openOwnerReassignment(workspace()); });
    let submission!: Promise<void>;

    act(() => {
      submission = view.result.current.dialogs.ownerReassignment.submit({
        targetUserId: 'owner-2', reason: 'Operational change',
      });
    });
    view.rerender({
      ...defaultInput,
      kind: 'knowledge-bases',
    });
    await waitFor(() => {
      expect(apiMocks.reassignPlatformResourceOwner).toHaveBeenCalledWith(
        'workspaces',
        'ws-1',
        { targetUserId: 'owner-2', reason: 'Operational change' },
      );
    });
    await act(async () => {
      reassignment.resolve(workspace('owner-2'));
      await submission;
    });
  });

  it('invalidates Workspace projections at terminal after the dialog resets and session unmounts', async () => {
    const status = deferred<Awaited<ReturnType<typeof apiMocks.getWorkspaceCapacityExpansion>>>();
    apiMocks.getWorkspaceCapacityExpansion.mockImplementation(() => status.promise);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    renderSession({ ...defaultInput, section: 'analytics' }, queryClient);
    const management = renderSession({
      ...defaultInput,
    }, queryClient);
    await waitFor(() => {
      expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledTimes(1);
      expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(1);
    });
    act(() => { management.result.current.commands.openCapacityExpansion(workspace()); });

    await act(async () => {
      await management.result.current.dialogs.capacityExpansion.submit({
        storageKind: 'workspace_data', requestedBytes: 30,
      });
    });
    await waitFor(() => {
      expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledTimes(2);
      expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(2);
      expect(apiMocks.getPlatformResourceCapacityTrend).toHaveBeenCalledTimes(2);
    });
    expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(1);
    act(() => { management.result.current.dialogs.capacityExpansion.reset(); });
    management.unmount();

    await act(async () => {
      status.resolve({
        requestId: 'request-1', workspaceId: 'ws-1', phase: 'completed',
        storageKind: 'workspace_data', previousBytes: 20, requestedBytes: 30,
        createdAt: 'now', updatedAt: 'later',
      });
    });
    await waitFor(() => {
      expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(3);
      expect(apiMocks.getPlatformResourceCapacityTrend).toHaveBeenCalledTimes(3);
    });
    expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledTimes(2);
    const reopenedManagement = renderSession(defaultInput, queryClient);
    await waitFor(() => {
      expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledTimes(3);
      expect(reopenedManagement.result.current.inventory.items).toHaveLength(1);
    });
    expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(1);
  });

  it('keeps monitoring through repeated transport errors until an authoritative terminal phase', async () => {
    vi.useFakeTimers();
    try {
      apiMocks.getWorkspaceCapacityExpansion
        .mockRejectedValueOnce(new Error('status unavailable 1'))
        .mockRejectedValueOnce(new Error('status unavailable 2'))
        .mockRejectedValueOnce(new Error('status unavailable 3'))
        .mockResolvedValueOnce({
          requestId: 'request-1', workspaceId: 'ws-1', phase: 'completed',
          storageKind: 'workspace_data', previousBytes: 20, requestedBytes: 30,
          createdAt: 'now', updatedAt: 'later',
        });
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
      });
      const analytics = renderSession({ ...defaultInput, section: 'analytics' }, queryClient);
      const management = renderSession({
        ...defaultInput,
      }, queryClient);
      await act(async () => { await Promise.resolve(); });
      act(() => { management.result.current.commands.openCapacityExpansion(workspace()); });

      await act(async () => {
        await management.result.current.dialogs.capacityExpansion.submit({
          storageKind: 'workspace_data', requestedBytes: 30,
        });
      });
      expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(1);

      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(2);
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(3);
      expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledTimes(2);
      expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(2);

      await act(async () => { await vi.advanceTimersByTimeAsync(4000); });
      expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(4);
      expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledTimes(3);
      expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledTimes(3);

      await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
      expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledTimes(4);
      management.unmount();
      analytics.unmount();
    } finally {
      vi.useRealTimers();
    }
  });

  it('scopes cache by auth subject and hides cached data when read is denied', async () => {
    const secondUser = deferred<{ items: ReturnType<typeof workspace>[]; total: number; page: number; pageSize: number }>();
    apiMocks.listPlatformWorkspaces
      .mockResolvedValueOnce({ items: [workspace('owner-1')], total: 1, page: 1, pageSize: 25 })
      .mockImplementationOnce(() => secondUser.promise);
    const view = renderSession(defaultInput);
    await waitFor(() => expect(view.result.current.inventory.items[0]?.owner.id).toBe('owner-1'));

    view.rerender({ ...defaultInput, authSubject: 'subject-2' });
    expect(view.result.current.inventory.items).toEqual([]);
    await act(async () => {
      secondUser.resolve({ items: [workspace('owner-2')], total: 1, page: 1, pageSize: 25 });
    });
    await waitFor(() => expect(view.result.current.inventory.items[0]?.owner.id).toBe('owner-2'));

    view.rerender({
      ...defaultInput,
      authSubject: 'subject-1',
      allowedOperations: [],
    });
    expect(view.result.current.inventory.items).toEqual([]);
  });
});
