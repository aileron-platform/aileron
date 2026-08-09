import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import type {
  KnowledgeBaseDetail,
  KnowledgeBaseSummary,
} from '@/features/knowledge-base/model/knowledgeBaseTypes';
import { OPERATION_IDS, type OperationId } from '@/shared/authorization/operationIds';
import { KnowledgeBaseProvider, useKnowledgeBase } from './KnowledgeBaseProvider';

const apiMocks = vi.hoisted(() => ({
  listKnowledgeBases: vi.fn(),
  getKnowledgeBase: vi.fn(),
  createKnowledgeBase: vi.fn(),
  updateKnowledgeBase: vi.fn(),
  updateKnowledgeBaseVisibility: vi.fn(),
  deleteKnowledgeBase: vi.fn(),
  listKnowledgeBaseShares: vi.fn(),
  createKnowledgeBaseShare: vi.fn(),
  updateKnowledgeBaseShare: vi.fn(),
  deleteKnowledgeBaseShare: vi.fn(),
  getKnowledgeBaseWorkspaceUsage: vi.fn(),
}));
const translateMock = vi.hoisted(() => vi.fn((key: string) => key));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => apiMocks);

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

vi.mock('@/shared/services/logger', () => ({
  createLogger: () => ({
    error: vi.fn(),
    warn: vi.fn(),
  }),
}));

const createKnowledgeBase = (
  accessRole: KnowledgeBaseSummary['accessRole'],
  allowedOperations: OperationId[] = [
    OPERATION_IDS.knowledgeBaseDetailRead,
    OPERATION_IDS.knowledgeBaseContentWrite,
    OPERATION_IDS.knowledgeBaseSettingsManage,
    OPERATION_IDS.knowledgeBaseShareManage,
    OPERATION_IDS.knowledgeBaseVisibilityManage,
    OPERATION_IDS.knowledgeBaseDelete,
  ],
): KnowledgeBaseDetail => ({
  id: 'kb-1',
  slug: 'kb-1',
  name: 'Knowledge Base',
  ownerId: 'user-1',
  currentSizeBytes: 0,
  quotaBytes: null,
  effectiveQuotaBytes: 512 * 1024 ** 2,
  quotaSource: 'platform_default',
  utilizationPercent: 0,
  ownerQuotaUsedBytes: 0,
  ownerEffectiveQuotaBytes: 5 * 1024 ** 3,
  accessRole,
  accessSource: accessRole === 'owner' ? 'owned' : 'direct_share',
  accessSources: [accessRole === 'owner' ? 'owned' : 'direct_share'],
  visibility: 'private',
  allowedOperations,
  createdAt: '2026-07-30T00:00:00.000Z',
  updatedAt: '2026-07-30T00:00:00.000Z',
});

const KNOWLEDGE_BASE_READ_OPERATIONS = [
  OPERATION_IDS.knowledgeBaseDetailRead,
];
const KNOWLEDGE_BASE_MANAGER_OPERATIONS = [
  OPERATION_IDS.knowledgeBaseDetailRead,
  OPERATION_IDS.knowledgeBaseContentWrite,
  OPERATION_IDS.knowledgeBaseSettingsManage,
  OPERATION_IDS.knowledgeBaseShareManage,
];

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>
    <KnowledgeBaseProvider>{children}</KnowledgeBaseProvider>
  </QueryClientProvider>
);

const expectPermissionDenied = async (promise: Promise<unknown>) => {
  await expect(promise).rejects.toMatchObject({
    errorCode: 'KB_PERMISSION_DENIED',
  });
};

describe('KnowledgeBaseProvider authorization guards', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient.clear();
    window.localStorage.clear();
    apiMocks.getKnowledgeBaseWorkspaceUsage.mockResolvedValue({
      visibleItems: [],
      hiddenWorkspaceCount: 0,
      attachmentCount: 0,
    });
    apiMocks.listKnowledgeBaseShares.mockResolvedValue([]);
  });

  it('allows reader loaders while failing closed before mutations', async () => {
    apiMocks.listKnowledgeBases.mockResolvedValue([createKnowledgeBase('reader', KNOWLEDGE_BASE_READ_OPERATIONS)]);
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });

    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));

    await act(async () => {
      await result.current.loadKnowledgeBaseShares('kb-1');
      await result.current.loadKnowledgeBaseWorkspaceUsage('kb-1');
    });
    await expectPermissionDenied(result.current.updateKnowledgeBase('kb-1', { name: 'Denied' }));
    await expectPermissionDenied(result.current.deleteKnowledgeBase('kb-1', 'Knowledge Base'));
    await expectPermissionDenied(result.current.updateKnowledgeBaseVisibility('kb-1', {
      visibility: 'public',
    }));
    await expectPermissionDenied(result.current.createKnowledgeBaseShare('kb-1', {
      targetType: 'user',
      targetId: 'user-2',
      role: 'reader',
    }));
    await expectPermissionDenied(result.current.updateKnowledgeBaseShare('kb-1', 'share-1', {
      role: 'manager',
    }));
    await expectPermissionDenied(result.current.deleteKnowledgeBaseShare('kb-1', 'share-1'));

    expect(apiMocks.listKnowledgeBaseShares).toHaveBeenCalledWith('kb-1');
    expect(apiMocks.getKnowledgeBaseWorkspaceUsage).toHaveBeenCalledWith('kb-1');
    expect(apiMocks.updateKnowledgeBase).not.toHaveBeenCalled();
    expect(apiMocks.deleteKnowledgeBase).not.toHaveBeenCalled();
    expect(apiMocks.createKnowledgeBaseShare).not.toHaveBeenCalled();
    expect(apiMocks.updateKnowledgeBaseShare).not.toHaveBeenCalled();
    expect(apiMocks.deleteKnowledgeBaseShare).not.toHaveBeenCalled();
  });

  it('requires owner access for deletion while retaining manager operations', async () => {
    apiMocks.listKnowledgeBases.mockResolvedValue([createKnowledgeBase('manager', KNOWLEDGE_BASE_MANAGER_OPERATIONS)]);
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });

    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));
    apiMocks.getKnowledgeBaseWorkspaceUsage.mockClear();

    await expectPermissionDenied(result.current.deleteKnowledgeBase('kb-1', 'Knowledge Base'));
    await act(async () => {
      await result.current.loadKnowledgeBaseWorkspaceUsage('kb-1');
    });

    expect(apiMocks.deleteKnowledgeBase).not.toHaveBeenCalled();
    expect(apiMocks.getKnowledgeBaseWorkspaceUsage).toHaveBeenCalledWith('kb-1');
  });

  it('rechecks the current role when an older callback is invoked after downgrade', async () => {
    apiMocks.listKnowledgeBases.mockResolvedValue([createKnowledgeBase('manager', KNOWLEDGE_BASE_MANAGER_OPERATIONS)]);
    apiMocks.getKnowledgeBase.mockResolvedValue(createKnowledgeBase('reader', KNOWLEDGE_BASE_READ_OPERATIONS));
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });

    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));
    const staleLoadShares = result.current.loadKnowledgeBaseShares;
    const staleUpdate = result.current.updateKnowledgeBase;

    await act(async () => {
      await result.current.loadKnowledgeBaseDetail('kb-1');
    });

    await act(async () => {
      await expect(staleLoadShares('kb-1')).resolves.toEqual([]);
    });
    await expectPermissionDenied(staleUpdate('kb-1', { name: 'Denied after downgrade' }));

    expect(apiMocks.listKnowledgeBaseShares).toHaveBeenCalledWith('kb-1');
    expect(apiMocks.updateKnowledgeBase).not.toHaveBeenCalled();
  });

  it('does not let an older list response restore manager access after detail downgrade', async () => {
    let resolveList: ((items: KnowledgeBaseSummary[]) => void) | undefined;
    apiMocks.listKnowledgeBases.mockImplementation(() => new Promise((resolve) => {
      resolveList = resolve;
    }));
    apiMocks.getKnowledgeBase.mockResolvedValue(createKnowledgeBase('reader', KNOWLEDGE_BASE_READ_OPERATIONS));
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });

    await waitFor(() => expect(apiMocks.listKnowledgeBases).toHaveBeenCalledTimes(1));
    await act(async () => {
      await result.current.loadKnowledgeBaseDetail('kb-1');
    });
    resolveList?.([createKnowledgeBase('manager', KNOWLEDGE_BASE_MANAGER_OPERATIONS)]);

    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));
    await act(async () => {
      await expect(result.current.loadKnowledgeBaseShares('kb-1')).resolves.toEqual([]);
    });
    await expectPermissionDenied(result.current.updateKnowledgeBase('kb-1', {
      name: 'Denied stale list update',
    }));

    expect(result.current.detailById['kb-1']?.accessRole).toBe('reader');
    expect(result.current.knowledgeBases).toEqual([
      expect.objectContaining({
        id: 'kb-1',
        accessRole: 'reader',
      }),
    ]);
    expect(apiMocks.getKnowledgeBaseWorkspaceUsage).not.toHaveBeenCalled();
    expect(apiMocks.listKnowledgeBaseShares).toHaveBeenCalledWith('kb-1');
    expect(apiMocks.updateKnowledgeBase).not.toHaveBeenCalled();
  });

  it('keeps detail content when a newer list response establishes readable access', async () => {
    let resolveDetail: ((detail: KnowledgeBaseDetail) => void) | undefined;
    apiMocks.listKnowledgeBases.mockResolvedValueOnce([]);
    apiMocks.getKnowledgeBase.mockImplementation(() => new Promise((resolve) => {
      resolveDetail = resolve;
    }));
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });
    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));

    const pendingDetail = result.current.loadKnowledgeBaseDetail('kb-1');
    apiMocks.listKnowledgeBases.mockResolvedValueOnce([createKnowledgeBase('owner')]);
    await act(async () => {
      await result.current.reloadKnowledgeBases();
    });
    await act(async () => {
      resolveDetail?.(createKnowledgeBase('owner'));
      await pendingDetail;
    });

    expect(result.current.detailById['kb-1']).toMatchObject({
      id: 'kb-1',
      accessRole: 'owner',
    });
  });

  it('clears only the revoked Knowledge Base archive operations after access denial', async () => {
    apiMocks.listKnowledgeBases.mockResolvedValue([createKnowledgeBase('owner')]);
    apiMocks.getKnowledgeBase.mockRejectedValue(
      Object.assign(new Error('Denied'), { status: 403 }),
    );
    window.localStorage.setItem(
      'knowledgeBase.files.archiveOperations.v1',
      JSON.stringify([
        {
          operationId: 'revoked-operation',
          archiveName: 'revoked.zip',
          paths: ['/docs'],
          context: { knowledgeBaseId: 'kb-1' },
          startedAt: '2026-07-30T00:00:00.000Z',
        },
        {
          operationId: 'retained-operation',
          archiveName: 'retained.zip',
          paths: ['/docs'],
          context: { knowledgeBaseId: 'kb-2' },
          startedAt: '2026-07-30T00:00:00.000Z',
        },
      ]),
    );
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });
    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));

    await act(async () => {
      await expect(result.current.loadKnowledgeBaseDetail('kb-1')).rejects.toMatchObject({
        status: 403,
      });
    });

    expect(JSON.parse(
      window.localStorage.getItem('knowledgeBase.files.archiveOperations.v1') ?? '[]',
    )).toEqual([
      expect.objectContaining({ operationId: 'retained-operation' }),
    ]);
  });

  it('clears React, archive, and TanStack query cache when a Knowledge Base disappears', async () => {
    apiMocks.listKnowledgeBases
      .mockResolvedValueOnce([createKnowledgeBase('owner')])
      .mockResolvedValueOnce([]);
    apiMocks.getKnowledgeBase.mockResolvedValue(createKnowledgeBase('owner'));
    window.localStorage.setItem(
      'knowledgeBase.files.archiveOperations.v1',
      JSON.stringify([{
        operationId: 'revoked-operation',
        archiveName: 'revoked.zip',
        paths: ['/docs'],
        context: { knowledgeBaseId: 'kb-1' },
        startedAt: '2026-07-30T00:00:00.000Z',
      }]),
    );
    queryClient.setQueryData(
      ['version-control', 'knowledge-bases', 'kb-1', 'primary', 'changes', 'status'],
      { branch: 'main' },
    );
    queryClient.setQueryData(
      ['version-control', 'knowledge-bases', 'kb-2', 'primary', 'changes', 'status'],
      { branch: 'main' },
    );
    let inFlightQueryAborted = false;
    const inFlightQuery = queryClient.fetchQuery({
      queryKey: ['version-control', 'knowledge-bases', 'kb-1', 'primary', 'history', 'commits'],
      queryFn: ({ signal }) => new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => {
          inFlightQueryAborted = true;
          reject(new Error('Query cancelled'));
        }, { once: true });
      }),
    }).catch(() => undefined);
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });
    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));
    await waitFor(() => expect(queryClient.getQueryState(
      ['version-control', 'knowledge-bases', 'kb-1', 'primary', 'history', 'commits'],
    )?.fetchStatus).toBe('fetching'));
    await act(async () => {
      await result.current.loadKnowledgeBaseDetail('kb-1');
      await result.current.reloadKnowledgeBases();
    });
    await inFlightQuery;

    expect(result.current.knowledgeBases).toEqual([]);
    expect(result.current.detailById['kb-1']).toBeUndefined();
    expect(result.current.sharesById['kb-1']).toBeUndefined();
    expect(result.current.workspaceUsageById['kb-1']).toBeUndefined();
    expect(JSON.parse(
      window.localStorage.getItem('knowledgeBase.files.archiveOperations.v1') ?? '[]',
    )).toEqual([]);
    expect(queryClient.getQueryData(
      ['version-control', 'knowledge-bases', 'kb-1', 'primary', 'changes', 'status'],
    )).toBeUndefined();
    expect(queryClient.getQueryData(
      ['version-control', 'knowledge-bases', 'kb-2', 'primary', 'changes', 'status'],
    )).toEqual({ branch: 'main' });
    expect(inFlightQueryAborted).toBe(true);
  });

  it('keeps readable loader data when access changes from manager to reader', async () => {
    let resolveShares: ((value: Array<{
      id: string;
      kbId: string;
      targetType: 'user';
      targetId: string;
      targetLabel: string;
      role: 'reader';
      grantedById: string;
      createdAt: string;
    }>) => void) | undefined;
    apiMocks.listKnowledgeBases.mockResolvedValue([createKnowledgeBase('manager', KNOWLEDGE_BASE_MANAGER_OPERATIONS)]);
    apiMocks.getKnowledgeBase.mockResolvedValue(createKnowledgeBase('reader', KNOWLEDGE_BASE_READ_OPERATIONS));
    apiMocks.listKnowledgeBaseShares.mockImplementation(() => new Promise((resolve) => {
      resolveShares = resolve;
    }));
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });

    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));
    const pendingShares = result.current.loadKnowledgeBaseShares('kb-1');
    await waitFor(() => expect(apiMocks.listKnowledgeBaseShares).toHaveBeenCalledWith('kb-1'));

    await act(async () => {
      await result.current.loadKnowledgeBaseDetail('kb-1');
    });
    await act(async () => {
      resolveShares?.([{
        id: 'share-1',
        kbId: 'kb-1',
        targetType: 'user',
        targetId: 'user-2',
        targetLabel: 'User 2',
        role: 'reader',
        grantedById: 'user-1',
        createdAt: '2026-07-30T00:00:00.000Z',
      }]);
      await pendingShares;
    });

    expect(result.current.sharesById['kb-1']).toEqual([
      expect.objectContaining({ id: 'share-1' }),
    ]);
  });

  it.each([
    ['missing', undefined],
    ['unknown', 'unexpected-role'],
    ['malformed', { role: 'owner' }],
  ])('fails closed for a create response with a %s access role', async (_label, accessRole) => {
    apiMocks.listKnowledgeBases.mockResolvedValue([]);
    apiMocks.createKnowledgeBase.mockResolvedValue({
      ...createKnowledgeBase('owner'),
      accessRole,
    });
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });
    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));

    await act(async () => {
      await expectPermissionDenied(result.current.createKnowledgeBase({
        name: 'Created Knowledge Base',
        slug: 'created-knowledge-base',
      }));
    });

    expect(result.current.knowledgeBases).toEqual([]);
    expect(result.current.detailById['kb-1']).toBeUndefined();
  });

  it.each([
    ['missing', undefined],
    ['unknown', 'unexpected-role'],
    ['malformed', { role: 'manager' }],
  ])('clears protected state for an update response with a %s access role', async (
    _label,
    accessRole,
  ) => {
    apiMocks.listKnowledgeBases.mockResolvedValue([createKnowledgeBase('manager', KNOWLEDGE_BASE_MANAGER_OPERATIONS)]);
    apiMocks.getKnowledgeBase.mockResolvedValue(createKnowledgeBase('manager', KNOWLEDGE_BASE_MANAGER_OPERATIONS));
    apiMocks.updateKnowledgeBase.mockResolvedValue({
      ...createKnowledgeBase('manager', KNOWLEDGE_BASE_MANAGER_OPERATIONS),
      accessRole,
    });
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });
    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));
    await act(async () => {
      await result.current.loadKnowledgeBaseDetail('kb-1');
    });

    await act(async () => {
      await expectPermissionDenied(result.current.updateKnowledgeBase('kb-1', {
        name: 'Malformed update',
      }));
    });

    expect(result.current.knowledgeBases).toEqual([]);
    expect(result.current.detailById['kb-1']).toBeUndefined();
  });

  it('keeps normalized state for valid create and update responses', async () => {
    apiMocks.listKnowledgeBases.mockResolvedValue([]);
    apiMocks.createKnowledgeBase.mockResolvedValue(createKnowledgeBase('owner'));
    apiMocks.updateKnowledgeBase.mockResolvedValue({
      ...createKnowledgeBase('manager', KNOWLEDGE_BASE_MANAGER_OPERATIONS),
      name: 'Updated Knowledge Base',
    });
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });
    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));

    await act(async () => {
      await result.current.createKnowledgeBase({
        name: 'Created Knowledge Base',
        slug: 'created-knowledge-base',
      });
      await result.current.updateKnowledgeBase('kb-1', {
        name: 'Updated Knowledge Base',
      });
    });

    expect(result.current.knowledgeBases).toEqual([
      expect.objectContaining({
        id: 'kb-1',
        name: 'Updated Knowledge Base',
        accessRole: 'manager',
      }),
    ]);
    expect(result.current.detailById['kb-1']).toMatchObject({
      id: 'kb-1',
      name: 'Updated Knowledge Base',
      accessRole: 'manager',
    });
  });

  it('rejects manager-only operations when the current role is missing or malformed', async () => {
    apiMocks.listKnowledgeBases.mockResolvedValue([
      {
        ...createKnowledgeBase('reader', KNOWLEDGE_BASE_READ_OPERATIONS),
        accessRole: 'unexpected-role',
      },
    ]);
    const { result } = renderHook(() => useKnowledgeBase(), { wrapper });

    await waitFor(() => expect(result.current.isLoadingKnowledgeBases).toBe(false));

    await expectPermissionDenied(result.current.loadKnowledgeBaseShares('kb-1'));
    await expectPermissionDenied(result.current.updateKnowledgeBase('missing-kb', { name: 'Denied' }));

    expect(apiMocks.listKnowledgeBaseShares).not.toHaveBeenCalled();
    expect(apiMocks.updateKnowledgeBase).not.toHaveBeenCalled();
  });
});
