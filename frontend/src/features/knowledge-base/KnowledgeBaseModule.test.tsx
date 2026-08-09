import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { KnowledgeBaseModule } from './KnowledgeBaseModule';

const { translateMock } = vi.hoisted(() => ({
  translateMock: vi.fn((key: string, params?: Record<string, string | number>) => {
    const translations: Record<string, string> = {
      'knowledgeBase.list.title': '\u77e5\u8b58\u5eab\u4e2d\u5fc3',
      'knowledgeBase.detail.breadcrumbRoot': '\u77e5\u8b58\u5eab\u4e2d\u5fc3',
      'knowledgeBase.detail.actions.backToList': '\u8fd4\u56de\u5217\u8868',
      'knowledgeBase.navigation.files': '\u6a94\u6848\u7ba1\u7406',
      'knowledgeBase.create.routeTitle': '\u65b0\u5efa\u77e5\u8b58\u5eab',
      'knowledgeBase.detail.cards.storageTitle': 'Storage',
      'knowledgeBase.sharing.description': '\u7ba1\u7406\u8ab0\u53ef\u4ee5\u67e5\u770b、\u7de8\u8f2f\u6216\u7ba1\u7406\u9019\u500b\u77e5\u8b58\u5eab。',
      'knowledgeBase.attachments.description': '\u67e5\u770b\u6b64\u77e5\u8b58\u5eab\u76ee\u524d\u88ab\u54ea\u4e9b\u5de5\u4f5c\u5340\u4f7f\u7528；\u639b\u8f09\u7570\u52d5\u8acb\u5f9e\u5404\u5de5\u4f5c\u5340\u7ba1\u7406。',
      'knowledgeBase.attachments.status.active': '\u4f7f\u7528\u4e2d',
      'knowledgeBase.attachments.hiddenWorkspaces': '\u53e6\u6709 {{count}} \u500b\u639b\u8f09\u5df2\u96b1\u85cf',
    };
    const template = translations[key] ?? key;
    return Object.entries(params ?? {}).reduce(
      (value, [paramKey, paramValue]) => value.replaceAll(`{{${paramKey}}}`, String(paramValue)),
      template,
    );
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  registerCsrfTokenProvider: vi.fn(),
  registerExecutionGrantProvider: vi.fn(),
  registerExecutionGrantRejectionHandler: vi.fn(),
  apiClient: {
    get: vi.fn(async () => ({ items: [] })),
  },
  ApiClient: vi.fn().mockImplementation(() => ({
    get: vi.fn(async () => ({
      isGitRepo: false,
      currentBranch: null,
      remoteUrl: null,
      hasOrigin: false,
      hasLocalContent: true,
      canCloneSafely: false,
      canInitSafely: true,
    })),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  })),
  ApiError: class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  },
  subscribeApiError: vi.fn(() => () => undefined),
}));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => ({
  listKnowledgeBases: vi.fn(async () => [
    {
      id: 'kb-1',
      slug: 'product-docs',
      name: '\u7522\u54c1\u6587\u4ef6\u4e2d\u5fc3',
      description: '\u96c6\u4e2d\u4fdd\u5b58\u7522\u54c1\u8207\u71df\u904b\u6587\u4ef6',
      ownerId: 'user-1',
      currentSizeBytes: 2048,
      quotaBytes: 4096,
      effectiveQuotaBytes: 4096,
      quotaSource: 'custom',
      utilizationPercent: 50,
      ownerQuotaUsedBytes: 2048,
      ownerEffectiveQuotaBytes: 5 * 1024 ** 3,
      accessRole: 'owner',
      accessSource: 'owned',
      accessSources: ['owned'],
      visibility: 'private',
      allowedOperations: [
        'knowledge_base.detail.read',
        'knowledge_base.content.write',
        'knowledge_base.settings.manage',
        'knowledge_base.share.manage',
        'knowledge_base.delete',
      ],
      createdAt: '2026-04-21T00:00:00Z',
      updatedAt: '2026-04-21T00:00:00Z',
    },
  ]),
  getKnowledgeBaseWorkspaceUsage: vi.fn(async () => ({
    visibleItems: [
      {
        attachmentId: 'att-1',
        workspaceId: 'ws-1',
        workspaceName: 'Workspace One',
        mountAlias: 'product-docs',
        attachmentStatus: 'active',
      },
    ],
    hiddenWorkspaceCount: 1,
    attachmentCount: 2,
  })),
  getKnowledgeBase: vi.fn(async (kbId: string) => {
    const accessRole = kbId === 'kb-manager'
      ? 'manager'
      : kbId === 'kb-reader'
        ? 'reader'
        : 'owner';
    return {
      id: kbId,
      slug: 'product-docs',
      name: kbId === 'kb-1' ? '\u7522\u54c1\u6587\u4ef6\u4e2d\u5fc3' : '\u65b0\u77e5\u8b58\u5eab',
      description: '\u96c6\u4e2d\u4fdd\u5b58\u7522\u54c1\u8207\u71df\u904b\u6587\u4ef6',
      ownerId: 'user-1',
      currentSizeBytes: 2048,
      quotaBytes: 4096,
      effectiveQuotaBytes: 4096,
      quotaSource: 'custom',
      utilizationPercent: 50,
      ownerQuotaUsedBytes: 2048,
      ownerEffectiveQuotaBytes: 5 * 1024 ** 3,
      accessRole,
      accessSource: accessRole === 'owner' ? 'owned' : 'direct_share',
      accessSources: [accessRole === 'owner' ? 'owned' : 'direct_share'],
      visibility: 'private',
      allowedOperations: accessRole === 'reader'
        ? ['knowledge_base.detail.read']
        : accessRole === 'manager'
          ? [
              'knowledge_base.detail.read',
              'knowledge_base.content.write',
            ]
          : [
              'knowledge_base.detail.read',
              'knowledge_base.content.write',
              'knowledge_base.settings.manage',
              'knowledge_base.share.manage',
              'knowledge_base.delete',
            ],
      createdAt: '2026-04-21T00:00:00Z',
      updatedAt: '2026-04-21T00:00:00Z',
    };
  }),
  updateKnowledgeBase: vi.fn(async (kbId: string, payload: { name?: string; description?: string }) => ({
    id: kbId,
    slug: 'product-docs',
    name: payload.name ?? '\u7522\u54c1\u6587\u4ef6\u4e2d\u5fc3',
    description: payload.description ?? '\u96c6\u4e2d\u4fdd\u5b58\u7522\u54c1\u8207\u71df\u904b\u6587\u4ef6',
    ownerId: 'user-1',
    currentSizeBytes: 2048,
    quotaBytes: 4096,
    effectiveQuotaBytes: 4096,
    quotaSource: 'custom',
    utilizationPercent: 50,
    ownerQuotaUsedBytes: 2048,
    ownerEffectiveQuotaBytes: 5 * 1024 ** 3,
    accessRole: 'owner',
    accessSource: 'owned',
    accessSources: ['owned'],
    visibility: 'private',
    allowedOperations: [
      'knowledge_base.detail.read',
      'knowledge_base.content.write',
      'knowledge_base.settings.manage',
      'knowledge_base.share.manage',
      'knowledge_base.delete',
    ],
    createdAt: '2026-04-21T00:00:00Z',
    updatedAt: '2026-04-21T00:00:00Z',
  })),
  deleteKnowledgeBase: vi.fn(async () => undefined),
  listKnowledgeBaseShares: vi.fn(async () => [
    {
      id: 'share-1',
      kbId: 'kb-1',
      targetType: 'user',
      targetId: 'user-2',
      targetLabel: 'Existing User',
      role: 'reader',
      grantedById: 'user-1',
      createdAt: '2026-04-21T00:00:00Z',
    },
  ]),
  createKnowledgeBase: vi.fn(async () => ({
    id: 'kb-2',
    slug: 'new-kb',
    name: '\u65b0\u77e5\u8b58\u5eab',
    description: 'desc',
    ownerId: 'user-1',
    currentSizeBytes: 0,
    quotaBytes: null,
    effectiveQuotaBytes: 512 * 1024 ** 2,
    quotaSource: 'platform_default',
    utilizationPercent: 0,
    ownerQuotaUsedBytes: 0,
    ownerEffectiveQuotaBytes: 5 * 1024 ** 3,
    accessRole: 'owner',
    accessSource: 'owned',
    accessSources: ['owned'],
    visibility: 'private',
    createdAt: '2026-04-21T00:00:00Z',
    updatedAt: '2026-04-21T00:00:00Z',
  })),
  createKnowledgeBaseShare: vi.fn(async () => ({
    id: 'share-2',
    kbId: 'kb-1',
    targetType: 'user',
    targetId: 'user-3',
    targetLabel: 'Candidate User',
    role: 'manager',
    grantedById: 'user-1',
    createdAt: '2026-04-21T00:00:00Z',
  })),
  updateKnowledgeBaseShare: vi.fn(async () => ({
    id: 'share-1',
    kbId: 'kb-1',
    targetType: 'user',
    targetId: 'user-2',
    targetLabel: 'Existing User',
    role: 'manager',
    grantedById: 'user-1',
    createdAt: '2026-04-21T00:00:00Z',
  })),
  deleteKnowledgeBaseShare: vi.fn(async () => undefined),
  searchKnowledgeBaseShareCandidates: vi.fn(async () => []),
}));

vi.mock('@/features/knowledge-base/components/KnowledgeBaseFilesTab', () => ({
  KnowledgeBaseFilesTab: ({
    renderRegions,
  }: {
    renderRegions?: (regions: {
      navigator: ReactNode;
      navigatorActions: ReactNode;
      main: ReactNode;
    }) => ReactNode;
  }) => {
    const content = <div data-testid="knowledge-base-files-tab" />;
    return renderRegions
      ? renderRegions({
          navigator: <div data-testid="knowledge-base-files-navigator" />,
          navigatorActions: null,
          main: content,
        })
      : content;
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    state: { currentLanguage: 'zh-TW' },
    t: translateMock,
  }),
}));

describe('KnowledgeBaseModule', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderModule = (initialEntry: string) => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    return render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>
          <Routes>
            <Route
              path="/knowledge-bases/*"
              element={<KnowledgeBaseModule navigationSlot={<div>global-navigation</div>} />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };

  it('renders the knowledge base list route', async () => {
    renderModule('/knowledge-bases');

    expect(await screen.findByText('\u77e5\u8b58\u5eab\u4e2d\u5fc3')).toBeInTheDocument();
    expect(screen.getByText('global-navigation')).toBeInTheDocument();
    expect(await screen.findByText('\u7522\u54c1\u6587\u4ef6\u4e2d\u5fc3')).toBeInTheDocument();
  });

  it('renders knowledge base routes inside the shared ProductShell', async () => {
    renderModule('/knowledge-bases');

    expect(screen.getByText('global-navigation')).toBeInTheDocument();
    await screen.findByText('\u77e5\u8b58\u5eab\u4e2d\u5fc3');
    const productShell = screen.getByTestId('product-shell');
    const listMain = screen.getByRole('main', { name: '\u77e5\u8b58\u5eab\u4e2d\u5fc3' });
    expect(listMain).toBeInTheDocument();
    expect(productShell).toContainElement(listMain);
  });

  it('renders the knowledge base create route', async () => {
    renderModule('/knowledge-bases/new');

    expect(await screen.findByText('\u65b0\u5efa\u77e5\u8b58\u5eab')).toBeInTheDocument();
  });

  it('renders the knowledge base detail sharing route', async () => {
    renderModule('/knowledge-bases/kb-1/sharing');

    expect(await screen.findAllByText('\u7522\u54c1\u6587\u4ef6\u4e2d\u5fc3')).toHaveLength(2);
    expect(screen.getByRole('button', { name: 'knowledgeBase.navigation.settings' })).toBeInTheDocument();
    expect(screen.getByText('2 KB / 4 KB')).toBeInTheDocument();
    expect(screen.queryByText('product-docs')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '\u6a94\u6848\u7ba1\u7406' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'knowledgeBase.navigation.versionControl' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'knowledgeBase.navigation.sharing' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'knowledgeBase.navigation.workspaces' })).toBeInTheDocument();
    expect(await screen.findByText('\u7ba1\u7406\u8ab0\u53ef\u4ee5\u67e5\u770b、\u7de8\u8f2f\u6216\u7ba1\u7406\u9019\u500b\u77e5\u8b58\u5eab。')).toBeInTheDocument();
    expect(await screen.findByText('Existing User')).toBeInTheDocument();
    expect(screen.queryByText('user-2')).not.toBeInTheDocument();
  });

  it('redirects the detail root to files', async () => {
    renderModule('/knowledge-bases/kb-1');

    await waitFor(() => {
      expect(screen.getByTestId('knowledge-base-files-tab')).toBeInTheDocument();
    });
  });

  it('renders detail breadcrumbs above the three-column knowledge base shell', async () => {
    renderModule('/knowledge-bases/kb-1/files');

    const breadcrumbBar = await screen.findByTestId('feature-shell-breadcrumb-bar');
    expect(breadcrumbBar).toHaveClass('h-10');
    expect(breadcrumbBar).toHaveTextContent('\u77e5\u8b58\u5eab\u4e2d\u5fc3');
    await waitFor(() => {
      expect(breadcrumbBar).toHaveTextContent('\u7522\u54c1\u6587\u4ef6\u4e2d\u5fc3');
    });
    expect(breadcrumbBar).toHaveTextContent('\u6a94\u6848\u7ba1\u7406');
    expect(screen.getByTestId('feature-shell-breadcrumb-icon')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '\u6a94\u6848\u7ba1\u7406' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '\u77e5\u8b58\u5eab\u4e2d\u5fc3' })).toHaveAttribute('href', '/knowledge-bases');
    const backToListButton = screen.getByRole('link', { name: '\u8fd4\u56de\u5217\u8868' });
    expect(backToListButton).toHaveAttribute('href', '/knowledge-bases');
    expect(backToListButton).toHaveClass('h-7', 'text-xs');
  });

  it('renders not found for an unknown detail route', async () => {
    renderModule('/knowledge-bases/kb-1/unknown');

    expect(await screen.findByText('common.notFound')).toBeInTheDocument();
    expect(screen.queryByTestId('knowledge-base-files-tab')).not.toBeInTheDocument();
  });

  it('renders the knowledge base detail workspaces route', async () => {
    renderModule('/knowledge-bases/kb-1/workspaces');

    expect(await screen.findByText('\u67e5\u770b\u6b64\u77e5\u8b58\u5eab\u76ee\u524d\u88ab\u54ea\u4e9b\u5de5\u4f5c\u5340\u4f7f\u7528；\u639b\u8f09\u7570\u52d5\u8acb\u5f9e\u5404\u5de5\u4f5c\u5340\u7ba1\u7406。')).toBeInTheDocument();
    expect(screen.getByText('Workspace One')).toBeInTheDocument();
    expect(screen.getByText('\u4f7f\u7528\u4e2d')).toBeInTheDocument();
    expect(screen.getByText('\u53e6\u6709 1 \u500b\u639b\u8f09\u5df2\u96b1\u85cf')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '\u639b\u8f09\u5230\u5de5\u4f5c\u5340' })).not.toBeInTheDocument();
  });
});
