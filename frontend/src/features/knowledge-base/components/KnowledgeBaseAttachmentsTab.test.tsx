import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { KnowledgeBaseAttachmentsTab } from './KnowledgeBaseAttachmentsTab';

const {
  apiGetMock,
  toastMock,
  loadAttachmentsMock,
  createAttachmentMock,
  updateAttachmentMock,
  deleteAttachmentMock,
  translateMock,
} = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
  toastMock: vi.fn(),
  loadAttachmentsMock: vi.fn(),
  createAttachmentMock: vi.fn(),
  updateAttachmentMock: vi.fn(),
  deleteAttachmentMock: vi.fn(),
  translateMock: vi.fn((key: string) => {
    const translations: Record<string, string> = {
      'knowledgeBase.attachments.title': '已掛載工作區',
      'knowledgeBase.attachments.description': '管理這個知識庫掛載到哪些工作區，以及 alias / mode。',
      'knowledgeBase.attachments.attachAction': '掛載到工作區',
      'knowledgeBase.attachments.modeLocked': '你在這個知識庫的角色是檢視者，因此只能使用 ro 模式。',
      'knowledgeBase.attachments.labels.mode': '模式',
      'knowledgeBase.attachments.labels.workspace': '工作區',
      'knowledgeBase.attachments.dialog.confirm': '掛載',
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
    attachmentsById: {
      'kb-1': [
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
      ],
    },
    isMutating: false,
    loadKnowledgeBaseAttachments: loadAttachmentsMock,
    createKnowledgeBaseAttachment: createAttachmentMock,
    updateKnowledgeBaseAttachment: updateAttachmentMock,
    deleteKnowledgeBaseAttachment: deleteAttachmentMock,
  }),
}));

describe('KnowledgeBaseAttachmentsTab', () => {
  beforeEach(() => {
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
    apiGetMock.mockReset();
    toastMock.mockReset();
    loadAttachmentsMock.mockReset();
    createAttachmentMock.mockReset();
    updateAttachmentMock.mockReset();
    deleteAttachmentMock.mockReset();
    translateMock.mockClear();
  });

  it('manager 可看到現有 attachment 與 attach 按鈕', () => {
    render(<KnowledgeBaseAttachmentsTab knowledgeBaseId="kb-1" accessRole="manager" />);

    expect(screen.getByText('管理這個知識庫掛載到哪些工作區，以及 alias / mode。')).toBeInTheDocument();
    expect(screen.getAllByText('ws-1')).toHaveLength(2);
    expect(screen.getByText('掛載到工作區')).toBeInTheDocument();
    expect(loadAttachmentsMock).not.toHaveBeenCalled();
  });

  it('viewer attach dialog 會把 mode 鎖成 ro', async () => {
    const user = userEvent.setup();
    apiGetMock.mockResolvedValue({
      items: [
        { id: 'ws-2', name: 'Workspace Two', accessRole: 'manager' },
      ],
    });

    render(<KnowledgeBaseAttachmentsTab knowledgeBaseId="kb-1" accessRole="viewer" />);

    await user.click(screen.getByText('掛載到工作區'));
    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith('/workspaces/?page=1&pageSize=100');
    });

    expect(screen.getAllByText('你在這個知識庫的角色是檢視者，因此只能使用 ro 模式。').length).toBeGreaterThan(0);
    expect(screen.getByRole('combobox', { name: '模式' })).toHaveAttribute('data-disabled');
  });

  it('可選擇 workspace 並建立 attachment', async () => {
    const user = userEvent.setup();
    createAttachmentMock.mockResolvedValue({
      id: 'att-2',
      workspaceId: 'ws-2',
      kbId: 'kb-1',
      mountAlias: 'product-docs-2',
      mode: 'rw',
      attachedById: 'user-1',
      createdAt: '2026-04-21T00:00:00Z',
      updatedAt: '2026-04-21T00:00:00Z',
    });
    apiGetMock.mockResolvedValue({
      items: [
        { id: 'ws-2', name: 'Workspace Two', accessRole: 'manager' },
      ],
    });

    render(<KnowledgeBaseAttachmentsTab knowledgeBaseId="kb-1" accessRole="manager" />);

    await user.click(screen.getByText('掛載到工作區'));
    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith('/workspaces/?page=1&pageSize=100');
    });

    await user.click(screen.getByRole('combobox', { name: '工作區' }));
    await user.click(await screen.findByText('Workspace Two'));
    fireEvent.change(document.getElementById('kb-attach-alias') as HTMLInputElement, { target: { value: 'docs-kb' } });
    await user.click(screen.getByRole('button', { name: '掛載' }));

    await waitFor(() => {
      expect(createAttachmentMock).toHaveBeenCalledWith('kb-1', {
        workspaceId: 'ws-2',
        mountAlias: 'docs-kb',
        mode: 'rw',
      });
    });
  });
});
