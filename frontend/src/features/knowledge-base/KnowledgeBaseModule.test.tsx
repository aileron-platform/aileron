import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as knowledgeBaseApi from '@/features/knowledge-base/api/knowledgeBaseApi';
import { KnowledgeBaseModule } from './KnowledgeBaseModule';

const { translateMock } = vi.hoisted(() => ({
  translateMock: vi.fn((key: string, params?: Record<string, string | number>) => {
    const translations: Record<string, string> = {
      'knowledgeBase.list.title': '知識庫中心',
      'knowledgeBase.create.routeTitle': '新建知識庫',
      'knowledgeBase.detail.settingsAction': '設定',
      'knowledgeBase.detail.deleteAction': '刪除',
      'knowledgeBase.detail.settings.title': '知識庫設定',
      'knowledgeBase.detail.settings.description': '更新這個知識庫的顯示資訊與容量上限。',
      'knowledgeBase.detail.settings.nameLabel': '名稱',
      'knowledgeBase.detail.settings.slugLabel': 'Slug',
      'knowledgeBase.detail.settings.slugHint': 'Slug 不可變更。',
      'knowledgeBase.detail.settings.descriptionLabel': '描述',
      'knowledgeBase.detail.settings.quotaLabel': '容量上限（bytes）',
      'knowledgeBase.detail.settings.quotaPlaceholder': '留空以使用預設容量上限',
      'knowledgeBase.detail.settings.quotaHint': '目前使用量：{{usage}}',
      'knowledgeBase.detail.settings.validation.nameRequired': '名稱為必填。',
      'knowledgeBase.detail.settings.validation.quotaNumeric': '容量上限必須是非負整數 bytes。',
      'knowledgeBase.detail.settings.validation.quotaBelowUsage': '容量上限不可低於目前使用量（{{usage}}）。',
      'knowledgeBase.detail.settings.toasts.saveSuccess.title': '知識庫已更新',
      'knowledgeBase.detail.settings.toasts.saveFailed.title': '更新知識庫失敗',
      'knowledgeBase.detail.settings.toasts.saveFailed.description': '請稍後再試。',
      'knowledgeBase.detail.delete.title': '刪除知識庫',
      'knowledgeBase.detail.delete.description': '要刪除 {{name}} 嗎？',
      'knowledgeBase.detail.delete.cancel': '取消',
      'knowledgeBase.detail.delete.confirm': '確認刪除',
      'knowledgeBase.detail.delete.toasts.success.title': '知識庫已刪除',
      'knowledgeBase.detail.delete.toasts.failed.title': '刪除知識庫失敗',
      'knowledgeBase.detail.delete.toasts.failed.description': '請先從工作區解除掛載後再試一次。',
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
      'knowledgeBase.common.actions.cancel': '取消',
      'knowledgeBase.common.actions.save': '儲存',
    };
    const template = translations[key] ?? key;
    return Object.entries(params ?? {}).reduce(
      (value, [paramKey, paramValue]) => value.replaceAll(`{{${paramKey}}}`, String(paramValue)),
      template,
    );
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(async () => ({ items: [] })),
  },
}));

vi.mock('@/features/knowledge-base/api/knowledgeBaseApi', () => ({
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
          workspaceName: 'Workspace One',
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
  getKnowledgeBase: vi.fn(async (kbId: string) => {
    const accessRole = kbId === 'kb-editor'
      ? 'editor'
      : kbId === 'kb-viewer'
        ? 'viewer'
        : 'owner';
    return {
      id: kbId,
      slug: 'product-docs',
      name: kbId === 'kb-1' ? '產品文件中心' : '新知識庫',
      description: '集中保存產品與營運文件',
      ownerId: 'user-1',
      currentSizeBytes: 2048,
      quotaBytes: 4096,
      accessRole,
      createdAt: '2026-04-21T00:00:00Z',
      updatedAt: '2026-04-21T00:00:00Z',
    };
  }),
  updateKnowledgeBase: vi.fn(async (kbId: string, payload: { name?: string; description?: string; quotaBytes?: number | null }) => ({
    id: kbId,
    slug: 'product-docs',
    name: payload.name ?? '產品文件中心',
    description: payload.description ?? '集中保存產品與營運文件',
    ownerId: 'user-1',
    currentSizeBytes: 2048,
    quotaBytes: payload.quotaBytes,
    accessRole: 'owner',
    createdAt: '2026-04-21T00:00:00Z',
    updatedAt: '2026-04-21T00:00:00Z',
  })),
  deleteKnowledgeBase: vi.fn(async () => undefined),
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
    workspaceName: 'Workspace Two',
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
    workspaceName: 'Workspace One',
    kbId: 'kb-1',
    mountAlias: 'product-docs-renamed',
    mode: 'ro',
    attachedById: 'user-1',
    createdAt: '2026-04-21T00:00:00Z',
    updatedAt: '2026-04-21T00:00:00Z',
  })),
  deleteKnowledgeBaseAttachment: vi.fn(async () => undefined),
}));

vi.mock('@/app/components/navigation/GlobalNavigation', () => ({
  GlobalNavigation: () => <div>global-navigation</div>,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

describe('KnowledgeBaseModule', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

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

  it('allows owners to open knowledge base settings', async () => {
    const user = userEvent.setup();
    renderModule('/knowledge-bases/kb-1/files');

    await screen.findByText('產品文件中心');
    await user.click(screen.getByRole('button', { name: '設定' }));

    expect(screen.getByText('知識庫設定')).toBeInTheDocument();
    expect(screen.getByLabelText('名稱')).toHaveValue('產品文件中心');
    expect(screen.getByLabelText('Slug')).toHaveValue('product-docs');
    expect(screen.getByLabelText('容量上限（bytes）')).toHaveValue('4096');
  });

  it.each([
    ['/knowledge-bases/kb-editor/files'],
    ['/knowledge-bases/kb-viewer/files'],
  ])('keeps settings and delete unavailable for non-manager roles on %s', async (route) => {
    renderModule(route);

    await screen.findByText('新知識庫');

    expect(screen.getByRole('button', { name: '設定' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '刪除' })).toBeDisabled();
  });

  it('saves metadata and quota through the update API', async () => {
    const user = userEvent.setup();
    renderModule('/knowledge-bases/kb-1/files');

    await screen.findByText('產品文件中心');
    await user.click(screen.getByRole('button', { name: '設定' }));
    await user.clear(screen.getByLabelText('名稱'));
    await user.type(screen.getByLabelText('名稱'), '更新後知識庫');
    await user.clear(screen.getByLabelText('描述'));
    await user.type(screen.getByLabelText('描述'), '更新後描述');
    await user.clear(screen.getByLabelText('容量上限（bytes）'));
    await user.type(screen.getByLabelText('容量上限（bytes）'), '8192');
    await user.click(screen.getByRole('button', { name: '儲存' }));

    await waitFor(() => {
      expect(knowledgeBaseApi.updateKnowledgeBase).toHaveBeenCalledWith('kb-1', {
        name: '更新後知識庫',
        description: '更新後描述',
        quotaBytes: 8192,
      });
    });
    expect(await screen.findByText('更新後知識庫')).toBeInTheDocument();
    expect(screen.getByText('Storage: 2 KB / 8 KB')).toBeInTheDocument();
  });

  it('submits null quota when the quota field is cleared', async () => {
    const user = userEvent.setup();
    renderModule('/knowledge-bases/kb-1/files');

    await screen.findByText('產品文件中心');
    await user.click(screen.getByRole('button', { name: '設定' }));
    await user.clear(screen.getByLabelText('容量上限（bytes）'));
    await user.click(screen.getByRole('button', { name: '儲存' }));

    await waitFor(() => {
      expect(knowledgeBaseApi.updateKnowledgeBase).toHaveBeenCalledWith('kb-1', {
        name: '產品文件中心',
        description: '集中保存產品與營運文件',
        quotaBytes: null,
      });
    });
  });

  it('shows quota validation before submitting invalid quota', async () => {
    const user = userEvent.setup();
    renderModule('/knowledge-bases/kb-1/files');

    await screen.findByText('產品文件中心');
    await user.click(screen.getByRole('button', { name: '設定' }));
    await user.clear(screen.getByLabelText('容量上限（bytes）'));
    await user.type(screen.getByLabelText('容量上限（bytes）'), '1024');
    await user.click(screen.getByRole('button', { name: '儲存' }));

    expect(screen.getByText('容量上限不可低於目前使用量（2 KB）。')).toBeInTheDocument();
    expect(knowledgeBaseApi.updateKnowledgeBase).not.toHaveBeenCalled();
  });

  it('deletes a knowledge base and navigates back to the list', async () => {
    const user = userEvent.setup();
    renderModule('/knowledge-bases/kb-1/files');

    await screen.findByText('產品文件中心');
    await user.click(screen.getByRole('button', { name: '刪除' }));
    await user.click(screen.getByRole('button', { name: '確認刪除' }));

    await waitFor(() => {
      expect(knowledgeBaseApi.deleteKnowledgeBase).toHaveBeenCalledWith('kb-1');
    });
    expect(await screen.findByText('知識庫中心')).toBeInTheDocument();
  });

  it('keeps detail state when delete is blocked', async () => {
    vi.mocked(knowledgeBaseApi.deleteKnowledgeBase).mockRejectedValueOnce(new Error('still attached'));
    const user = userEvent.setup();
    renderModule('/knowledge-bases/kb-1/files');

    await screen.findByText('產品文件中心');
    await user.click(screen.getByRole('button', { name: '刪除' }));
    await user.click(screen.getByRole('button', { name: '確認刪除' }));

    await waitFor(() => {
      expect(knowledgeBaseApi.deleteKnowledgeBase).toHaveBeenCalledWith('kb-1');
    });
    expect(screen.getByText('產品文件中心')).toBeInTheDocument();
  });
});
