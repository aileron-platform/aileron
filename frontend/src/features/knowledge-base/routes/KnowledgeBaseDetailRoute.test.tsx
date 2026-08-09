import type React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { KnowledgeBaseDetail } from '../model/knowledgeBaseTypes';
import { OPERATION_IDS, type OperationId } from '@/shared/authorization/operationIds';
import { KnowledgeBaseDetailRoute } from './KnowledgeBaseDetailRoute';

const mocks = vi.hoisted(() => ({
  apiErrorHandler: {
    current: null as ((event: {
      status: number;
      errorCode?: string;
      responseUrl: string;
    }) => void) | null,
  },
  detailsById: {} as Record<string, KnowledgeBaseDetail>,
  nextFilesTabInstanceId: 0,
  loadKnowledgeBaseDetail: vi.fn(),
  loadKnowledgeBaseShares: vi.fn(),
  loadKnowledgeBaseWorkspaceUsage: vi.fn(),
  settingsTabProps: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/shared/api/apiClient')>();
  return {
    ...actual,
    subscribeApiError: vi.fn((handler: typeof mocks.apiErrorHandler.current) => {
      mocks.apiErrorHandler.current = handler;
      return () => {
        if (mocks.apiErrorHandler.current === handler) {
          mocks.apiErrorHandler.current = null;
        }
      };
    }),
  };
});

vi.mock('@/shared/components/shell', () => ({
  FeatureShellBreadcrumbBar: () => null,
  ProductShell: ({
    topBar,
    header,
    body,
  }: {
    topBar?: React.ReactNode;
    header?: React.ReactNode;
    body: {
      kind: 'state' | 'regions';
      content?: React.ReactNode;
      navigation?: { content: (state: { collapsed: boolean }) => React.ReactNode };
      navigator?: { content: (state: { collapsed: boolean }) => React.ReactNode };
      main?: { content: React.ReactNode };
    };
  }) => (
    <div data-testid="product-shell">
      <div data-shell-top-bar>{topBar}</div>
      <div data-shell-header>{header}</div>
      {body.kind === 'state' ? body.content : (
        <>
          <div data-shell-navigation>{body.navigation?.content({ collapsed: false })}</div>
          <div data-shell-navigator>{body.navigator?.content({ collapsed: false })}</div>
          <div data-shell-main>{body.main?.content}</div>
        </>
      )}
    </div>
  ),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../components/KnowledgeBaseFilesTab', async () => {
  const React = await vi.importActual<typeof import('react')>('react');
  return {
    KnowledgeBaseFilesTab: ({
      knowledgeBaseId,
      canWrite,
      renderRegions,
    }: {
      knowledgeBaseId: string;
      canWrite: boolean;
      renderRegions?: (regions: {
        navigator: React.ReactNode;
        navigatorActions: React.ReactNode;
        main: React.ReactNode;
      }) => React.ReactNode;
    }) => {
      const instanceId = React.useRef<number | null>(null);
      if (instanceId.current === null) {
        mocks.nextFilesTabInstanceId += 1;
        instanceId.current = mocks.nextFilesTabInstanceId;
      }
      const content = (
        <div
          data-testid="knowledge-base-files-tab"
          data-instance-id={instanceId.current}
          data-can-write={String(canWrite)}
        >
          {knowledgeBaseId}
        </div>
      );
      return renderRegions
        ? renderRegions({
            navigator: <div data-testid="knowledge-base-files-navigator" />,
            navigatorActions: null,
            main: content,
          })
        : content;
    },
  };
});

vi.mock('../components/KnowledgeBaseSidebar', () => ({
  KnowledgeBaseSidebar: () => null,
}));

vi.mock('../components/KnowledgeBaseSettingsTab', () => ({
  KnowledgeBaseSettingsTab: (props: {
    knowledgeBaseId: string;
    canManage: boolean;
    canManageVisibility: boolean;
    canDelete: boolean;
  }) => {
    mocks.settingsTabProps(props);
    return <div data-testid="knowledge-base-settings-tab" />;
  },
}));

vi.mock('../components/KnowledgeBaseSharingTab', () => ({
  KnowledgeBaseSharingTab: () => null,
}));

vi.mock('../components/KnowledgeBaseWorkspacesTab', () => ({
  KnowledgeBaseWorkspacesTab: () => null,
}));

vi.mock('../providers/KnowledgeBaseProvider', () => ({
  useKnowledgeBase: () => ({
    detailById: mocks.detailsById,
    sharesById: {},
    workspaceUsageById: {},
    loadKnowledgeBaseDetail: mocks.loadKnowledgeBaseDetail,
    loadKnowledgeBaseShares: mocks.loadKnowledgeBaseShares,
    loadKnowledgeBaseWorkspaceUsage: mocks.loadKnowledgeBaseWorkspaceUsage,
  }),
}));

const createDetail = (
  id: string,
  accessRole: KnowledgeBaseDetail['accessRole'] = 'owner',
  allowedOperations: OperationId[] = [
    OPERATION_IDS.knowledgeBaseDetailRead,
    OPERATION_IDS.knowledgeBaseContentWrite,
    OPERATION_IDS.knowledgeBaseSettingsManage,
    OPERATION_IDS.knowledgeBaseShareManage,
    OPERATION_IDS.knowledgeBaseDelete,
  ],
): KnowledgeBaseDetail => ({
  id,
  slug: id,
  name: `Knowledge Base ${id}`,
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
  createdAt: '2026-07-30T00:00:00Z',
  updatedAt: '2026-07-30T00:00:00Z',
});

const renderDetailRoute = (path = '/knowledge-bases/kb-1/files') => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route
        path="/knowledge-bases/:knowledgeBaseId/*"
        element={<KnowledgeBaseDetailRoute />}
      />
    </Routes>
  </MemoryRouter>,
);

describe('KnowledgeBaseDetailRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.apiErrorHandler.current = null;
    mocks.nextFilesTabInstanceId = 0;
    mocks.detailsById = {
      'kb-1': createDetail('kb-1'),
      'kb-2': createDetail('kb-2'),
    };
    mocks.loadKnowledgeBaseDetail.mockImplementation(
      async (knowledgeBaseId: string) => mocks.detailsById[knowledgeBaseId],
    );
    mocks.loadKnowledgeBaseShares.mockResolvedValue([]);
    mocks.loadKnowledgeBaseWorkspaceUsage.mockResolvedValue({
      visibleItems: [],
      hiddenWorkspaceCount: 0,
      attachmentCount: 0,
    });
  });

  it('remounts the files tab when the Knowledge Base identity changes', async () => {
    const NavigateToSecondKnowledgeBase = () => {
      const navigate = useNavigate();
      return (
        <button
          type="button"
          onClick={() => navigate('/knowledge-bases/kb-2/files')}
        >
          open second knowledge base
        </button>
      );
    };
    render(
      <MemoryRouter initialEntries={['/knowledge-bases/kb-1/files']}>
        <NavigateToSecondKnowledgeBase />
        <Routes>
          <Route
            path="/knowledge-bases/:knowledgeBaseId/*"
            element={<KnowledgeBaseDetailRoute />}
          />
        </Routes>
      </MemoryRouter>,
    );

    const firstFilesTab = await screen.findByTestId('knowledge-base-files-tab');
    const firstInstanceId = firstFilesTab.getAttribute('data-instance-id');
    expect(firstFilesTab).toHaveTextContent('kb-1');

    fireEvent.click(screen.getByRole('button', { name: 'open second knowledge base' }));

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-base-files-tab')).toHaveTextContent('kb-2');
    });
    expect(screen.getByTestId('knowledge-base-files-tab'))
      .not.toHaveAttribute('data-instance-id', firstInstanceId);
  });

  it('loads manager-only shares and workspace usage for a manager', async () => {
    mocks.detailsById['kb-1'] = createDetail('kb-1', 'manager', [
      OPERATION_IDS.knowledgeBaseDetailRead,
      OPERATION_IDS.knowledgeBaseContentWrite,
      OPERATION_IDS.knowledgeBaseSettingsManage,
      OPERATION_IDS.knowledgeBaseShareManage,
    ]);

    renderDetailRoute();

    await screen.findByTestId('knowledge-base-files-tab');
    await waitFor(() => {
      expect(mocks.loadKnowledgeBaseShares).toHaveBeenCalledWith('kb-1');
      expect(mocks.loadKnowledgeBaseWorkspaceUsage).toHaveBeenCalledWith('kb-1');
    });
  });

  it('keeps reader content read-only without mounting manager-only queries', async () => {
    mocks.detailsById['kb-1'] = createDetail('kb-1', 'reader', [
      OPERATION_IDS.knowledgeBaseDetailRead,
    ]);

    renderDetailRoute();

    expect(await screen.findByTestId('knowledge-base-files-tab'))
      .toHaveAttribute('data-can-write', 'false');
    expect(mocks.loadKnowledgeBaseShares).not.toHaveBeenCalled();
    expect(mocks.loadKnowledgeBaseWorkspaceUsage).not.toHaveBeenCalled();
  });

  it('exposes deletion in settings only to an owner', async () => {
    mocks.detailsById['kb-1'] = createDetail('kb-1', 'manager', [
      OPERATION_IDS.knowledgeBaseDetailRead,
      OPERATION_IDS.knowledgeBaseContentWrite,
      OPERATION_IDS.knowledgeBaseSettingsManage,
      OPERATION_IDS.knowledgeBaseShareManage,
    ]);
    renderDetailRoute('/knowledge-bases/kb-1/settings');

    await screen.findByTestId('knowledge-base-settings-tab');
    expect(mocks.settingsTabProps).toHaveBeenLastCalledWith(expect.objectContaining({
      knowledgeBaseId: 'kb-1',
      canManage: true,
      canDelete: false,
    }));
  });

  it('exposes deletion in settings to an owner', async () => {
    renderDetailRoute('/knowledge-bases/kb-1/settings');

    await screen.findByTestId('knowledge-base-settings-tab');
    expect(mocks.settingsTabProps).toHaveBeenLastCalledWith(expect.objectContaining({
      knowledgeBaseId: 'kb-1',
      canManage: true,
      canDelete: true,
    }));
  });

  it('fails closed for an invalid role without mounting content or manager-only queries', async () => {
    mocks.detailsById['kb-1'] = createDetail(
      'kb-1',
      'unexpected-role' as KnowledgeBaseDetail['accessRole'],
    );

    renderDetailRoute();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'common.authorization.accessDeniedTitle',
    );
    expect(screen.queryByTestId('knowledge-base-files-tab')).not.toBeInTheDocument();
    expect(mocks.loadKnowledgeBaseShares).not.toHaveBeenCalled();
    expect(mocks.loadKnowledgeBaseWorkspaceUsage).not.toHaveBeenCalled();
  });

  it('reloads the active detail on focus, visible, and Knowledge Base denial events', async () => {
    const visibilityState = vi
      .spyOn(document, 'visibilityState', 'get')
      .mockReturnValue('visible');
    renderDetailRoute();
    await screen.findByTestId('knowledge-base-files-tab');
    expect(mocks.loadKnowledgeBaseDetail).toHaveBeenCalledTimes(1);

    fireEvent(window, new Event('focus'));
    await waitFor(() => {
      expect(mocks.loadKnowledgeBaseDetail).toHaveBeenCalledTimes(2);
    });
    await Promise.resolve();

    fireEvent(document, new Event('visibilitychange'));
    await waitFor(() => {
      expect(mocks.loadKnowledgeBaseDetail).toHaveBeenCalledTimes(3);
    });
    await Promise.resolve();

    await act(async () => {
      mocks.apiErrorHandler.current?.({
        status: 403,
        errorCode: 'KB_PERMISSION_DENIED',
        responseUrl: '/api/v1/knowledge-bases/kb-1/files',
      });
      await Promise.resolve();
    });
    await waitFor(() => {
      expect(mocks.loadKnowledgeBaseDetail).toHaveBeenCalledTimes(4);
    });
    await Promise.resolve();

    mocks.apiErrorHandler.current?.({
      status: 403,
      errorCode: 'WORKSPACE_ACCESS_DENIED',
      responseUrl: '/api/v1/workspaces/ws-1',
    });
    await Promise.resolve();
    expect(mocks.loadKnowledgeBaseDetail).toHaveBeenCalledTimes(4);
    visibilityState.mockRestore();
  });
});
