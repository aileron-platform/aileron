import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseModule } from './KnowledgeBaseModule';

const { translateMock } = vi.hoisted(() => ({
  translateMock: vi.fn((key: string) => {
    const translations: Record<string, string> = {
      'knowledgeBase.list.title': '知識庫中心',
      'knowledgeBase.create.routeTitle': '新建知識庫',
      'knowledgeBase.detail.settingsAction': '設定',
      'knowledgeBase.detail.deleteAction': '刪除',
      'knowledgeBase.detail.tabs.files': '檔案',
      'knowledgeBase.detail.tabs.graph': '關聯圖',
      'knowledgeBase.detail.tabs.versionControl': '版本控制',
      'knowledgeBase.detail.tabs.schedules': '排程',
      'knowledgeBase.detail.tabs.sharing': '分享',
      'knowledgeBase.detail.tabs.workspaces': '工作區',
      'knowledgeBase.detail.cards.storageTitle': 'Storage',
      'knowledgeBase.sharing.description': '管理誰可以查看、編輯或管理這個知識庫。',
      'knowledgeBase.attachments.description': '管理這個知識庫掛載到哪些工作區，以及 alias / mode。',
      'knowledgeBase.attachments.attachAction': '掛載到工作區',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(async () => ({ items: [] })),
  },
}));

vi.mock('@/shared/services/knowledgeBaseApi', () => ({
  listKnowledgeBases: vi.fn(async () => [
    {
      id: 'kb-1',
      slug: 'product-docs',
      name: '產品文件中心',
      description: '集中保存產品與營運文件',
      ownerId: 'user-1',
      currentSizeBytes: 2048,
      quotaBytes: 4096,
      accessRole: 'owner',
      createdAt: '2026-04-21T00:00:00Z',
      updatedAt: '2026-04-21T00:00:00Z',
    },
  ]),
  listKnowledgeBaseAttachments: vi.fn(async (kbId: string) => (
    kbId === 'kb-1'
      ? [
        {
          id: 'att-1',
          workspaceId: 'ws-1',
          kbId: 'kb-1',
          mountAlias: 'product-docs',
          mode: 'rw',
          attachedById: 'user-1',
          createdAt: '2026-04-21T00:00:00Z',
          updatedAt: '2026-04-21T00:00:00Z',
        },
      ]
      : []
  )),
  getKnowledgeBase: vi.fn(async (kbId: string) => ({
    id: kbId,
    slug: 'product-docs',
    name: kbId === 'kb-1' ? '產品文件中心' : '新知識庫',
    description: '集中保存產品與營運文件',
    ownerId: 'user-1',
    currentSizeBytes: 2048,
    quotaBytes: 4096,
    accessRole: 'owner',
    createdAt: '2026-04-21T00:00:00Z',
    updatedAt: '2026-04-21T00:00:00Z',
  })),
  listKnowledgeBaseShares: vi.fn(async () => [
    {
      id: 'share-1',
      kbId: 'kb-1',
      userId: 'user-2',
      role: 'viewer',
      grantedById: 'user-1',
      createdAt: '2026-04-21T00:00:00Z',
    },
  ]),
  getKnowledgeBaseGraph: vi.fn(async () => ({
    kbId: 'kb-1',
    generatedAt: '2026-04-29T00:00:00Z',
    nodes: [],
    edges: [],
  })),
  getKnowledgeBaseGitRepositoryStatus: vi.fn(async () => ({
    isGitRepo: false,
    currentBranch: null,
    remoteUrl: null,
    hasOrigin: false,
    hasLocalContent: true,
    canCloneSafely: false,
    canInitSafely: true,
    cloneBlockedReason: null,
  })),
  getKnowledgeBaseVersionControlStatus: vi.fn(async () => ({
    branch: 'main',
    ahead: 0,
    behind: 0,
    detached: false,
    hasConflicts: false,
    stagedCount: 0,
    unstagedCount: 0,
    untrackedCount: 0,
  })),
  enableKnowledgeBaseGitRepository: vi.fn(async () => ({
    isGitRepo: true,
    currentBranch: 'main',
    remoteUrl: null,
    hasOrigin: false,
    hasLocalContent: true,
    canCloneSafely: false,
    canInitSafely: false,
    cloneBlockedReason: null,
  })),
  enableKnowledgeBaseGitLfs: vi.fn(async () => ({ success: true, message: 'ok' })),
  createKnowledgeBase: vi.fn(async () => ({
    id: 'kb-2',
    slug: 'new-kb',
    name: '新知識庫',
    description: 'desc',
    ownerId: 'user-1',
    currentSizeBytes: 0,
    quotaBytes: null,
    accessRole: 'owner',
    createdAt: '2026-04-21T00:00:00Z',
    updatedAt: '2026-04-21T00:00:00Z',
  })),
  createKnowledgeBaseShare: vi.fn(async () => ({
    id: 'share-2',
    kbId: 'kb-1',
    userId: 'user-3',
    role: 'editor',
    grantedById: 'user-1',
    createdAt: '2026-04-21T00:00:00Z',
  })),
  updateKnowledgeBaseShare: vi.fn(async () => ({
    id: 'share-1',
    kbId: 'kb-1',
    userId: 'user-2',
    role: 'manager',
    grantedById: 'user-1',
    createdAt: '2026-04-21T00:00:00Z',
  })),
  deleteKnowledgeBaseShare: vi.fn(async () => undefined),
  createKnowledgeBaseAttachment: vi.fn(async () => ({
    id: 'att-2',
    workspaceId: 'ws-2',
    kbId: 'kb-1',
    mountAlias: 'product-docs-2',
    mode: 'rw',
    attachedById: 'user-1',
    createdAt: '2026-04-21T00:00:00Z',
    updatedAt: '2026-04-21T00:00:00Z',
  })),
  updateKnowledgeBaseAttachment: vi.fn(async () => ({
    id: 'att-1',
    workspaceId: 'ws-1',
    kbId: 'kb-1',
    mountAlias: 'product-docs-renamed',
    mode: 'ro',
    attachedById: 'user-1',
    createdAt: '2026-04-21T00:00:00Z',
    updatedAt: '2026-04-21T00:00:00Z',
  })),
  deleteKnowledgeBaseAttachment: vi.fn(async () => undefined),
}));

vi.mock('@/shared/components/navigation/GlobalNavigation', () => ({
  GlobalNavigation: () => <div>global-navigation</div>,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

describe('KnowledgeBaseModule', () => {
  const renderModule = (initialEntry: string) => {
    return render(
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/knowledge-bases/*" element={<KnowledgeBaseModule />} />
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders the knowledge base list route', async () => {
    renderModule('/knowledge-bases');

    expect(await screen.findByText('知識庫中心')).toBeInTheDocument();
    expect(screen.getByText('global-navigation')).toBeInTheDocument();
    expect(await screen.findByText('產品文件中心')).toBeInTheDocument();
  });

  it('renders the knowledge base create route', async () => {
    renderModule('/knowledge-bases/new');

    expect(await screen.findByText('新建知識庫')).toBeInTheDocument();
  });

  it('renders the knowledge base detail sharing route', async () => {
    renderModule('/knowledge-bases/kb-1/sharing');

    expect(await screen.findByText('產品文件中心')).toBeInTheDocument();
    expect(screen.getByText('設定')).toBeInTheDocument();
    expect(screen.getByText('刪除')).toBeInTheDocument();
    expect(screen.getByText('Storage: 2 KB / 4 KB')).toBeInTheDocument();
    expect(screen.queryByText('Team Wiki')).not.toBeInTheDocument();
    expect(screen.queryByText('product-docs')).not.toBeInTheDocument();
    expect(screen.getByText('檔案')).toBeInTheDocument();
    expect(screen.getByText('關聯圖')).toBeInTheDocument();
    expect(screen.getByText('版本控制')).toBeInTheDocument();
    expect(screen.getByText('排程')).toBeInTheDocument();
    expect(screen.getByText('分享')).toBeInTheDocument();
    expect(screen.getByText('工作區')).toBeInTheDocument();
    expect(await screen.findByText('管理誰可以查看、編輯或管理這個知識庫。')).toBeInTheDocument();
    expect(await screen.findByText('user-2')).toBeInTheDocument();
  });

  it('renders the knowledge base detail workspaces route', async () => {
    renderModule('/knowledge-bases/kb-1/workspaces');

    expect(await screen.findByText('管理這個知識庫掛載到哪些工作區，以及 alias / mode。')).toBeInTheDocument();
    expect(screen.getByText('掛載到工作區')).toBeInTheDocument();
  });
});
