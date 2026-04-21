import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseSharingTab } from './KnowledgeBaseSharingTab';

const {
  createShareMock,
  updateShareMock,
  deleteShareMock,
  loadSharesMock,
  apiGetMock,
  toastMock,
  translateMock,
} = vi.hoisted(() => ({
  createShareMock: vi.fn(),
  updateShareMock: vi.fn(),
  deleteShareMock: vi.fn(),
  loadSharesMock: vi.fn(),
  apiGetMock: vi.fn(),
  toastMock: vi.fn(),
  translateMock: vi.fn((key: string) => {
    const translations: Record<string, string> = {
      'knowledgeBase.sharing.title': '分享',
      'knowledgeBase.sharing.description': '管理誰可以查看、編輯或管理這個知識庫。',
      'knowledgeBase.sharing.addAction': '新增分享',
      'knowledgeBase.sharing.readOnlyNotice': '只有擁有者或管理者可以新增、調整或移除分享；你目前只能查看分享清單。',
      'knowledgeBase.sharing.candidate.userLabel': '使用者',
      'knowledgeBase.sharing.candidate.userPlaceholder': '以 Email 或顯示名稱搜尋...',
      'knowledgeBase.sharing.candidate.confirm': '新增分享',
      'knowledgeBase.sharing.candidate.userEmpty': '找不到符合的使用者。',
      'workspace.workspaceSettings.access.sharing.searching': '搜尋會員中...',
      'workspace.workspaceSettings.access.sharing.startTyping': '開始輸入以搜尋會員。',
      'workspace.workspaceSettings.access.sharing.searchPlaceholder': '搜尋會員 Email...',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: apiGetMock,
  },
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

vi.mock('../providers/KnowledgeBaseProvider', () => ({
  useKnowledgeBase: () => ({
    sharesById: {
      'kb-1': [
        {
          id: 'share-1',
          kbId: 'kb-1',
          userId: 'user-2',
          role: 'viewer',
          grantedById: 'user-1',
          createdAt: '2026-04-21T00:00:00Z',
        },
      ],
    },
    isMutating: false,
    loadKnowledgeBaseShares: loadSharesMock,
    createKnowledgeBaseShare: createShareMock,
    updateKnowledgeBaseShare: updateShareMock,
    deleteKnowledgeBaseShare: deleteShareMock,
  }),
}));

describe('KnowledgeBaseSharingTab', () => {
  beforeEach(() => {
    createShareMock.mockReset();
    updateShareMock.mockReset();
    deleteShareMock.mockReset();
    loadSharesMock.mockReset();
    apiGetMock.mockReset();
    toastMock.mockReset();
    translateMock.mockClear();
  });

  it('manager 可以看到新增 share 入口與現有 share', async () => {
    render(<KnowledgeBaseSharingTab knowledgeBaseId="kb-1" accessRole="manager" />);

    expect(screen.getByText('管理誰可以查看、編輯或管理這個知識庫。')).toBeInTheDocument();
    expect(screen.getByText('user-2')).toBeInTheDocument();
    expect(screen.getByText('新增分享')).toBeInTheDocument();
    expect(loadSharesMock).not.toHaveBeenCalled();
  });

  it('viewer 只看到唯讀提示', () => {
    render(<KnowledgeBaseSharingTab knowledgeBaseId="kb-1" accessRole="viewer" />);

    expect(screen.getByText('只有擁有者或管理者可以新增、調整或移除分享；你目前只能查看分享清單。')).toBeInTheDocument();
    expect(screen.queryByText('新增分享')).not.toBeInTheDocument();
  });

  it('可搜尋使用者並建立 share', async () => {
    const user = userEvent.setup();
    createShareMock.mockResolvedValue({
      id: 'share-2',
      kbId: 'kb-1',
      userId: 'user-3',
      role: 'editor',
      grantedById: 'user-1',
      createdAt: '2026-04-21T00:00:00Z',
    });
    apiGetMock.mockResolvedValue({
      items: [
        {
          id: 'user-3',
          email: 'candidate@example.com',
          username: 'candidate',
          displayName: 'Candidate User',
        },
      ],
    });

    render(<KnowledgeBaseSharingTab knowledgeBaseId="kb-1" accessRole="manager" />);

    await user.click(screen.getByText('新增分享'));
    await user.click(screen.getByRole('combobox', { name: '使用者' }));

    const searchInput = await screen.findByPlaceholderText('以 Email 或顯示名稱搜尋...');
    fireEvent.change(searchInput, { target: { value: 'candidate@example.com' } });

    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith('/users?query=candidate%40example.com&limit=8');
    });

    await user.click(await screen.findByText('Candidate User'));
    await user.click(screen.getByRole('button', { name: '新增分享' }));

    await waitFor(() => {
      expect(createShareMock).toHaveBeenCalledWith('kb-1', {
        userId: 'user-3',
        role: 'viewer',
      });
    });
  });
});
