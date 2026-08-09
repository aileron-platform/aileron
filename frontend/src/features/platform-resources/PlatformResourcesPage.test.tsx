import { fireEvent, render as testingLibraryRender, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PlatformResourcesPage } from './PlatformResourcesPage';

const apiMocks = vi.hoisted(() => ({
  getPlatformResourceSummary: vi.fn(),
  getPlatformResourceResourceTrend: vi.fn(),
  getPlatformResourceCapacityTrend: vi.fn(),
  listPlatformWorkspaces: vi.fn(),
  listPlatformKnowledgeBases: vi.fn(),
  requestWorkspaceCapacityExpansion: vi.fn(),
  getWorkspaceCapacityExpansion: vi.fn(),
  updatePlatformKnowledgeBaseQuota: vi.fn(),
  reassignPlatformResourceOwner: vi.fn(),
  searchPlatformResourceOwnerCandidates: vi.fn(),
}));

const authState = vi.hoisted(() => ({
  user: { id: 'user-1' } as { id: string } | null,
  allowedOperations: [
    'platform_resources.read',
    'platform_resources.owner.reassign',
    'platform_resources.knowledge_base.quota.update',
    'platform_resources.workspace.capacity.expand',
  ] as string[],
}));

vi.mock('./api/platformResourcesApi', () => apiMocks);

vi.mock('@/features/auth/public', () => ({
  useAuth: () => ({
    allowedOperations: authState.allowedOperations,
    user: authState.user,
  }),
  AuthorizationDeniedState: () => (
    <div role="alert">common.authorization.accessDeniedTitle</div>
  ),
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  LineChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CartesianGrid: () => null,
  Legend: () => null,
  Line: () => null,
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => (
      values ? `${key}:${JSON.stringify(values)}` : key
    ),
  }),
}));

const owner = {
  id: 'user-1',
  username: 'current-owner',
  displayName: 'Current Owner',
  avatarUrl: null,
};

const render = (ui: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  const result = testingLibraryRender(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
  return {
    ...result,
    rerender: (nextUi: React.ReactElement) => result.rerender(
      <QueryClientProvider client={queryClient}>{nextUi}</QueryClientProvider>,
    ),
  };
};

describe('PlatformResourcesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    authState.user = { id: 'user-1' };
    authState.allowedOperations = [
      'platform_resources.read',
      'platform_resources.owner.reassign',
      'platform_resources.knowledge_base.quota.update',
      'platform_resources.workspace.capacity.expand',
    ];
    apiMocks.getPlatformResourceSummary.mockResolvedValue({
      range: '30d',
      timeZone: 'Asia/Taipei',
      calculatedAt: '2026-08-01T01:00:00Z',
      collectionStartedAt: '2026-07-01T00:00:00Z',
      isStale: false,
      metrics: {
        total: { value: 26, previousValue: 20, changePercent: 30 },
        active: { value: 18, previousValue: 15, changePercent: 20 },
        usedBytes: { value: 3221225472, previousValue: 2147483648, changePercent: 50 },
        nearLimit: { value: 2, previousValue: 1, changePercent: 100 },
      },
      distributions: [
        { key: 'running', count: 20 },
        { key: 'transitioning', count: 2 },
        { key: 'stopped', count: 3 },
        { key: 'error', count: 1 },
      ],
    });
    apiMocks.getPlatformResourceResourceTrend.mockResolvedValue({
      range: '30d',
      timeZone: 'Asia/Taipei',
      calculatedAt: '2026-08-01T01:00:00Z',
      collectionStartedAt: '2026-07-01T00:00:00Z',
      isStale: false,
      points: [{ date: '2026-08-01', total: 26, created: 2, active: 18, deleted: 1 }],
    });
    apiMocks.getPlatformResourceCapacityTrend.mockResolvedValue({
      range: '30d',
      timeZone: 'Asia/Taipei',
      calculatedAt: '2026-08-01T01:00:00Z',
      collectionStartedAt: '2026-07-01T00:00:00Z',
      isStale: false,
      points: [{
        date: '2026-08-01',
        usedBytes: 3221225472,
        allocatedBytes: 10737418240,
        unknownCount: 1,
        staleCount: 2,
      }],
    });
    apiMocks.listPlatformWorkspaces.mockResolvedValue({
      items: [{
        id: 'ws-1',
        name: 'Workspace One',
        owner,
        runtimeStatus: 'running',
        workspaceData: {
          usedBytes: 2147483648,
          allocatedBytes: 21474836480,
          utilizationPercent: 10,
          risk: 'normal',
          measuredAt: '2026-08-01T01:00:00Z',
          expansionSupported: true,
        },
        runtimeHome: {
          usedBytes: 1073741824,
          allocatedBytes: 2147483648,
          utilizationPercent: 50,
          risk: 'normal',
          measuredAt: '2026-08-01T01:00:00Z',
          expansionSupported: true,
        },
        capacityRisk: 'normal',
        provisioner: 'kubernetes',
      }],
      total: 26,
      page: 1,
      pageSize: 25,
    });
    apiMocks.listPlatformKnowledgeBases.mockResolvedValue({
      items: [{
        id: 'kb-1',
        name: 'Knowledge Base One',
        owner,
        visibility: 'private',
        currentSizeBytes: 2147483648,
        quotaBytes: 4294967296,
        effectiveQuotaBytes: 4294967296,
        quotaSource: 'custom',
        utilizationPercent: 50,
        capacityRisk: 'normal',
        indexingHealth: 'success',
      }],
      total: 1,
      page: 1,
      pageSize: 25,
    });
    apiMocks.searchPlatformResourceOwnerCandidates.mockResolvedValue([]);
    apiMocks.requestWorkspaceCapacityExpansion.mockResolvedValue({
      requestId: 'expansion-1',
      workspaceId: 'ws-1',
      phase: 'pending',
      storageKind: 'workspace_data',
      previousBytes: 21474836480,
      requestedBytes: 32212254720,
      createdAt: '2026-08-01T01:00:00Z',
      updatedAt: '2026-08-01T01:00:00Z',
    });
    apiMocks.getWorkspaceCapacityExpansion.mockResolvedValue({
      requestId: 'expansion-1',
      workspaceId: 'ws-1',
      phase: 'completed',
      storageKind: 'workspace_data',
      previousBytes: 21474836480,
      requestedBytes: 32212254720,
      createdAt: '2026-08-01T01:00:00Z',
      updatedAt: '2026-08-01T01:05:00Z',
    });
    apiMocks.updatePlatformKnowledgeBaseQuota.mockResolvedValue({
      knowledgeBaseId: 'kb-1',
      currentSizeBytes: 2147483648,
      quotaBytes: 8589934592,
      effectiveQuotaBytes: 8589934592,
      quotaSource: 'custom',
    });
  });

  it('loads workspace management without requesting analytics', async () => {
    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Workspace One')).toBeInTheDocument();
    expect(screen.getByTestId('platform-resources-title-icon')).toBeInTheDocument();
    expect(screen.getByText('Current Owner')).toBeInTheDocument();
    expect(screen.getAllByText('platformResources.runtimeStatus.running').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'platformResources.actions.viewDetails' }))
      .toHaveAttribute('href', '/workspaces/ws-1/home');
    expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledWith({
      q: '',
      page: 1,
      pageSize: 25,
    }, expect.any(AbortSignal));
    expect(apiMocks.getPlatformResourceSummary).not.toHaveBeenCalled();
    expect(apiMocks.getPlatformResourceResourceTrend).not.toHaveBeenCalled();
    expect(apiMocks.getPlatformResourceCapacityTrend).not.toHaveBeenCalled();
    expect(screen.getByText('platformResources.sections.management')).toBeInTheDocument();
    expect(screen.getByText('platformResources.sections.analytics')).toBeInTheDocument();
    expect(screen.getByText('2 GiB / 20 GiB')).toBeInTheDocument();
    expect(screen.getByText(/1 GiB \/ 2 GiB/)).toBeInTheDocument();
    expect(screen.queryByText('platformResources.statistics.cards.total')).not.toBeInTheDocument();
  });

  it('loads analytics without requesting the management inventory', async () => {
    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="analytics" />
      </MemoryRouter>,
    );

    expect(await screen.findByText('platformResources.statistics.cards.total')).toBeInTheDocument();
    expect(await screen.findByText('platformResources.statistics.distributions.running'))
      .toBeInTheDocument();
    expect(screen.getByRole('table', {
      name: 'platformResources.statistics.resourceTrend.accessibleTableLabel',
    })).toBeInTheDocument();
    expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledWith(
      'workspaces', '30d', false, expect.any(AbortSignal),
    );
    expect(apiMocks.listPlatformWorkspaces).not.toHaveBeenCalled();
  });

  it('keeps analytics trend blocks usable when the summary fails', async () => {
    apiMocks.getPlatformResourceSummary.mockRejectedValue(new Error('summary unavailable'));

    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="analytics" />
      </MemoryRouter>,
    );

    expect(await screen.findByText('platformResources.statistics.errors.summary')).toBeInTheDocument();
    expect(screen.getByRole('table', {
      name: 'platformResources.statistics.resourceTrend.accessibleTableLabel',
    })).toBeInTheDocument();
  });

  it('restores management query and page from URL query parameters', async () => {
    render(
      <MemoryRouter initialEntries={['/platform-resources/workspaces?range=90d&q=operations&page=2']}>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Workspace One');
    expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledWith({
      q: 'operations',
      page: 2,
      pageSize: 25,
    }, expect.any(AbortSignal));
    expect(apiMocks.getPlatformResourceSummary).not.toHaveBeenCalled();
  });

  it('restores analytics range from URL query parameters', async () => {
    render(
      <MemoryRouter initialEntries={['/platform-resources/analytics/workspaces?range=90d']}>
        <PlatformResourcesPage kind="workspaces" section="analytics" />
      </MemoryRouter>,
    );

    await screen.findByText('platformResources.statistics.cards.total');
    expect(apiMocks.getPlatformResourceSummary).toHaveBeenCalledWith(
      'workspaces', '90d', false, expect.any(AbortSignal),
    );
    expect(screen.getByRole('button', { name: 'platformResources.statistics.ranges.90d' }))
      .toHaveAttribute('aria-pressed', 'true');
  });

  it('restores inventory filters and sorting from URL query parameters', async () => {
    render(
      <MemoryRouter initialEntries={['/platform-resources/workspaces?health=running&capacityRisk=warning&sort=utilization&order=desc']}>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Workspace One');
    expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledWith({
      q: '',
      page: 1,
      pageSize: 25,
      health: 'running',
      capacityRisk: 'warning',
      sort: 'utilization',
      order: 'desc',
    }, expect.any(AbortSignal));
  });

  it('submits search from page one and supports server-side pagination', async () => {
    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Workspace One');
    fireEvent.change(
      screen.getByRole('searchbox', { name: 'platformResources.search.label' }),
      { target: { value: 'operations' } },
    );
    fireEvent.click(screen.getByRole('button', { name: 'platformResources.search.submit' }));

    await waitFor(() => {
      expect(apiMocks.listPlatformWorkspaces).toHaveBeenLastCalledWith({
        q: 'operations',
        page: 1,
        pageSize: 25,
      }, expect.any(AbortSignal));
    });

    const nextButton = screen.getByRole('button', { name: 'platformResources.pagination.next' });
    await waitFor(() => expect(nextButton).toBeEnabled());
    fireEvent.click(nextButton);
    await waitFor(() => {
      expect(apiMocks.listPlatformWorkspaces).toHaveBeenLastCalledWith({
        q: 'operations',
        page: 2,
        pageSize: 25,
      }, expect.any(AbortSignal));
    });
  });

  it('loads knowledge bases through their distinct endpoint and detail route', async () => {
    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="knowledge-bases" section="management" />
      </MemoryRouter>,
    );

    expect(await screen.findByText('Knowledge Base One')).toBeInTheDocument();
    expect(screen.getAllByText('platformResources.visibility.private').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: 'platformResources.actions.viewDetails' }))
      .toHaveAttribute('href', '/knowledge-bases/kb-1/files');
    expect(apiMocks.listPlatformKnowledgeBases).toHaveBeenCalledWith({
      q: '',
      page: 1,
      pageSize: 25,
    }, expect.any(AbortSignal));
    expect(screen.getByText('2 GiB / 4 GiB')).toBeInTheDocument();
  });

  it('updates a knowledge base quota in GiB from the admin dialog', async () => {
    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="knowledge-bases" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Knowledge Base One');
    fireEvent.click(screen.getByRole('button', { name: 'platformResources.actions.manageQuota' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('platformResources.quotaDialog.quotaGiBLabel'), {
      target: { value: '8' },
    });
    fireEvent.click(within(dialog).getByRole('button', {
      name: 'platformResources.quotaDialog.confirm',
    }));

    await waitFor(() => {
      expect(apiMocks.updatePlatformKnowledgeBaseQuota).toHaveBeenCalledWith('kb-1', 8589934592);
    });
  });

  it('requests a workspace capacity expansion and polls its status', async () => {
    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Workspace One');
    fireEvent.click(screen.getByRole('button', { name: 'platformResources.actions.expandCapacity' }));
    const dialog = screen.getByRole('dialog');
    fireEvent.change(within(dialog).getByLabelText('platformResources.expansionDialog.requestedGiBLabel'), {
      target: { value: '30' },
    });
    fireEvent.click(within(dialog).getByRole('button', {
      name: 'platformResources.expansionDialog.confirm',
    }));

    await waitFor(() => {
      expect(apiMocks.requestWorkspaceCapacityExpansion).toHaveBeenCalledWith('ws-1', {
        storageKind: 'workspace_data',
        requestedBytes: 32212254720,
      });
      expect(apiMocks.getWorkspaceCapacityExpansion).toHaveBeenCalledWith(
        'ws-1', 'expansion-1', expect.any(AbortSignal),
      );
    });
    expect(await within(dialog).findByText('platformResources.expansionDialog.phases.completed'))
      .toBeInTheDocument();
  });

  it('uses the refreshed Workspace projection for expansion validation', async () => {
    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );
    await screen.findByText('Workspace One');
    fireEvent.click(screen.getByRole('button', {
      name: 'platformResources.actions.expandCapacity',
    }));
    const dialog = screen.getByRole('dialog');
    const requestedGiB = within(dialog).getByLabelText(
      'platformResources.expansionDialog.requestedGiBLabel',
    );
    fireEvent.change(requestedGiB, { target: { value: '30' } });
    expect(within(dialog).getByRole('button', {
      name: 'platformResources.expansionDialog.confirm',
    })).toBeEnabled();

    apiMocks.listPlatformWorkspaces.mockResolvedValue({
      items: [{
        id: 'ws-1',
        name: 'Workspace One',
        owner,
        runtimeStatus: 'running',
        workspaceData: {
          usedBytes: 32212254720,
          allocatedBytes: 42949672960,
          utilizationPercent: 75,
          risk: 'warning',
          measuredAt: '2026-08-01T02:00:00Z',
          expansionSupported: false,
        },
        runtimeHome: null,
        capacityRisk: 'warning',
        provisioner: 'kubernetes',
      }],
      total: 1,
      page: 1,
      pageSize: 25,
    });
    fireEvent.click(screen.getByText('platformResources.actions.refresh'));

    await waitFor(() => expect(apiMocks.listPlatformWorkspaces).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(requestedGiB).toHaveValue(''));
    expect(within(dialog).getByRole('button', {
      name: 'platformResources.expansionDialog.confirm',
    })).toBeDisabled();
  });

  it('uses the refreshed Knowledge Base projection for quota validation', async () => {
    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="knowledge-bases" section="management" />
      </MemoryRouter>,
    );
    await screen.findByText('Knowledge Base One');
    fireEvent.click(screen.getByRole('button', {
      name: 'platformResources.actions.manageQuota',
    }));
    const dialog = screen.getByRole('dialog');

    apiMocks.listPlatformKnowledgeBases.mockResolvedValue({
      items: [{
        id: 'kb-1',
        name: 'Knowledge Base One',
        owner,
        visibility: 'private',
        currentSizeBytes: 5 * 1024 ** 3,
        quotaBytes: 6 * 1024 ** 3,
        effectiveQuotaBytes: 6 * 1024 ** 3,
        quotaSource: 'custom',
        utilizationPercent: 83.33,
        capacityRisk: 'warning',
        indexingHealth: 'success',
      }],
      total: 1,
      page: 1,
      pageSize: 25,
    });
    fireEvent.click(screen.getByText('platformResources.actions.refresh'));
    await waitFor(() => expect(apiMocks.listPlatformKnowledgeBases).toHaveBeenCalledTimes(2));
    const quotaGiB = within(dialog).getByLabelText(
      'platformResources.quotaDialog.quotaGiBLabel',
    );
    await waitFor(() => expect(quotaGiB).toHaveValue('6'));
    fireEvent.change(quotaGiB, { target: { value: '4' } });
    expect(within(dialog).getByRole('button', {
      name: 'platformResources.quotaDialog.confirm',
    })).toBeDisabled();
  });

  it('keeps reassignment fail-closed until a candidate and valid reason are selected', async () => {
    apiMocks.searchPlatformResourceOwnerCandidates.mockResolvedValue([{
      id: 'user-2',
      username: 'next-owner',
      displayName: 'Next Owner',
    }]);
    const reassignedWorkspace = {
      id: 'ws-1',
      name: 'Workspace One',
      owner: {
        id: 'user-2',
        username: 'next-owner',
        displayName: 'Next Owner',
        avatarUrl: null,
      },
      runtimeStatus: 'running',
      workspaceData: {
        usedBytes: 2147483648,
        allocatedBytes: 21474836480,
        utilizationPercent: 10,
        risk: 'normal',
        measuredAt: '2026-08-01T01:00:00Z',
        expansionSupported: true,
      },
      runtimeHome: {
        usedBytes: 1073741824,
        allocatedBytes: 2147483648,
        utilizationPercent: 50,
        risk: 'normal',
        measuredAt: '2026-08-01T01:00:00Z',
        expansionSupported: true,
      },
      capacityRisk: 'normal',
      provisioner: 'kubernetes',
    };
    apiMocks.reassignPlatformResourceOwner.mockResolvedValue(reassignedWorkspace);
    apiMocks.listPlatformWorkspaces.mockResolvedValue({
      items: [reassignedWorkspace],
      total: 26,
      page: 1,
      pageSize: 25,
    });

    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Workspace One');
    fireEvent.click(screen.getByRole('button', { name: 'platformResources.actions.reassignOwner' }));
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', {
      name: 'platformResources.ownerReassignment.confirm',
    });
    expect(confirm).toBeDisabled();

    fireEvent.change(
      within(dialog).getByRole('searchbox', {
        name: 'platformResources.ownerReassignment.userSearchLabel',
      }),
      { target: { value: 'next owner' } },
    );
    fireEvent.click(within(dialog).getByRole('button', {
      name: 'platformResources.ownerReassignment.search',
    }));
    expect(await within(dialog).findByText('Next Owner')).toBeInTheDocument();
    expect(apiMocks.searchPlatformResourceOwnerCandidates).toHaveBeenCalledWith(
      'next owner', expect.any(AbortSignal),
    );

    fireEvent.click(within(dialog).getByRole('button', { name: /Next Owner/ }));
    fireEvent.change(
      within(dialog).getByRole('textbox', {
        name: 'platformResources.ownerReassignment.reasonLabel',
      }),
      { target: { value: 'no' } },
    );
    expect(confirm).toBeDisabled();

    fireEvent.change(
      within(dialog).getByRole('textbox', {
        name: 'platformResources.ownerReassignment.reasonLabel',
      }),
      { target: { value: 'Operational ownership change' } },
    );
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() => {
      expect(apiMocks.reassignPlatformResourceOwner).toHaveBeenCalledWith(
        'workspaces',
        'ws-1',
        {
          targetUserId: 'user-2',
          reason: 'Operational ownership change',
        },
      );
    });
    expect(await screen.findByText('Next Owner')).toBeInTheDocument();
  });

  it('clears dialog identities across auth subject, resource kind, and section boundaries', async () => {
    const view = render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Workspace One');
    fireEvent.click(screen.getByRole('button', {
      name: 'platformResources.actions.reassignOwner',
    }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    authState.user = { id: 'user-2' };
    view.rerender(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    await screen.findByText('Workspace One');
    fireEvent.click(screen.getByRole('button', {
      name: 'platformResources.actions.expandCapacity',
    }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    view.rerender(
      <MemoryRouter>
        <PlatformResourcesPage kind="knowledge-bases" section="management" />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());

    await screen.findByText('Knowledge Base One');
    fireEvent.click(screen.getByRole('button', {
      name: 'platformResources.actions.manageQuota',
    }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    view.rerender(
      <MemoryRouter>
        <PlatformResourcesPage kind="knowledge-bases" section="analytics" />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    view.rerender(
      <MemoryRouter>
        <PlatformResourcesPage kind="knowledge-bases" section="management" />
      </MemoryRouter>,
    );
    await screen.findByText('Knowledge Base One');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('does not start Platform Resources queries without the read operation', async () => {
    authState.allowedOperations = [];

    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent(
      'common.authorization.accessDeniedTitle',
    );
    await waitFor(() => {
      expect(apiMocks.listPlatformWorkspaces).not.toHaveBeenCalled();
      expect(apiMocks.getPlatformResourceSummary).not.toHaveBeenCalled();
      expect(apiMocks.getPlatformResourceResourceTrend).not.toHaveBeenCalled();
      expect(apiMocks.getPlatformResourceCapacityTrend).not.toHaveBeenCalled();
    });
  });

  it('hides Workspace mutations when their exact operations are absent', async () => {
    authState.allowedOperations = ['platform_resources.read'];

    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="workspaces" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Workspace One');
    expect(screen.queryByRole('button', {
      name: 'platformResources.actions.expandCapacity',
    })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {
      name: 'platformResources.actions.reassignOwner',
    })).not.toBeInTheDocument();
    expect(apiMocks.requestWorkspaceCapacityExpansion).not.toHaveBeenCalled();
    expect(apiMocks.searchPlatformResourceOwnerCandidates).not.toHaveBeenCalled();
    expect(apiMocks.reassignPlatformResourceOwner).not.toHaveBeenCalled();
  });

  it('hides Knowledge Base mutations when their exact operations are absent', async () => {
    authState.allowedOperations = ['platform_resources.read'];

    render(
      <MemoryRouter>
        <PlatformResourcesPage kind="knowledge-bases" section="management" />
      </MemoryRouter>,
    );

    await screen.findByText('Knowledge Base One');
    expect(screen.queryByRole('button', {
      name: 'platformResources.actions.manageQuota',
    })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {
      name: 'platformResources.actions.reassignOwner',
    })).not.toBeInTheDocument();
    expect(apiMocks.updatePlatformKnowledgeBaseQuota).not.toHaveBeenCalled();
  });
});
