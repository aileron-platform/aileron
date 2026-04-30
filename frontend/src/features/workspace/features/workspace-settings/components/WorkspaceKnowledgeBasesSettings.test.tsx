import { beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { WorkspaceKnowledgeBasesSettings } from './WorkspaceKnowledgeBasesSettings';

const {
  getMock,
  postMock,
  patchMock,
  deleteMock,
  toastMock,
  reloadMock,
  translateMock,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
  toastMock: vi.fn(),
  reloadMock: vi.fn(),
  translateMock: vi.fn((key: string) => {
    const translations: Record<string, string> = {
      'workspace.workspaceSettings.knowledgeBases.header.title': 'Knowledge Bases',
      'workspace.workspaceSettings.knowledgeBases.desired.title': 'Desired attachments',
      'workspace.workspaceSettings.knowledgeBases.desired.description':
        'Manage which knowledge bases should be attached to this workspace, including alias and mode.',
      'workspace.workspaceSettings.knowledgeBases.desired.attachAction': 'Attach knowledge base',
      'workspace.workspaceSettings.knowledgeBases.desired.detachAction': 'Detach',
      'workspace.workspaceSettings.knowledgeBases.desired.empty':
        'No knowledge base attachments are configured for this workspace yet.',
      'workspace.workspaceSettings.knowledgeBases.mounted.title': 'Mounted knowledge bases',
      'workspace.workspaceSettings.knowledgeBases.mounted.description':
        'Shows the knowledge base mounts currently applied in the workspace.',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingBadge': 'Pending',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingHint':
        'The mounted state does not match the desired attachments yet.',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingTitle':
        'Mount changes are waiting to be applied',
      'workspace.workspaceSettings.knowledgeBases.mounted.pendingDescription':
        'Restart the workspace to apply the latest knowledge base attachments.',
      'workspace.workspaceSettings.knowledgeBases.mounted.restart.label':
        'Restart workspace to apply',
      'workspace.workspaceSettings.knowledgeBases.mounted.signatureLabel': 'Mounted signature',
      'workspace.workspaceSettings.knowledgeBases.mounted.signatureMissing': 'No mounted signature yet',
      'workspace.workspaceSettings.knowledgeBases.readOnlyNotice':
        'Only members with editor access or above on this workspace can change knowledge base attachments.',
      'workspace.workspaceSettings.knowledgeBases.dialog.title': 'Attach knowledge base',
      'workspace.workspaceSettings.knowledgeBases.dialog.description':
        'Select a knowledge base to mount into this workspace and configure alias and mode.',
      'workspace.workspaceSettings.knowledgeBases.dialog.placeholder': 'Select a knowledge base',
      'workspace.workspaceSettings.knowledgeBases.dialog.searchPlaceholder': 'Search knowledge bases...',
      'workspace.workspaceSettings.knowledgeBases.dialog.empty':
        'No knowledge bases available to attach.',
      'workspace.workspaceSettings.knowledgeBases.dialog.cancel': 'Cancel',
      'workspace.workspaceSettings.knowledgeBases.dialog.confirm': 'Attach',
      'workspace.workspaceSettings.knowledgeBases.form.knowledgeBaseLabel': 'Knowledge Base',
      'workspace.workspaceSettings.knowledgeBases.form.aliasLabel': 'Mount alias',
      'workspace.workspaceSettings.knowledgeBases.form.aliasPlaceholder':
        'Defaults to the knowledge base slug',
      'workspace.workspaceSettings.knowledgeBases.form.modeLabel': 'Mode',
      'workspace.workspaceSettings.knowledgeBases.modeLocked':
        'Your role on this knowledge base is viewer, so the mode is locked to ro.',
      'workspace.workspaceSettings.knowledgeBases.notifications.attachSuccessTitle':
        'Knowledge base attached',
      'workspace.workspaceSettings.knowledgeBases.notifications.loadFailed':
        'Failed to load workspace knowledge bases.',
      'knowledgeBase.common.mode.ro': 'Read only',
      'knowledgeBase.common.mode.rw': 'Read / Write',
    };
    return translations[key] ?? key;
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: getMock,
    post: postMock,
    patch: patchMock,
    delete: deleteMock,
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: toastMock,
  }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      workspaceId: 'ws-123',
      reload: reloadMock,
    },
  }),
}));

describe('WorkspaceKnowledgeBasesSettings', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    patchMock.mockReset();
    deleteMock.mockReset();
    toastMock.mockReset();
    reloadMock.mockReset();
    translateMock.mockClear();
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('顯示目前 workspace desired attachments 與 pending mounted badge', async () => {
    getMock.mockResolvedValue({
      id: 'ws-123',
      accessRole: 'manager',
      attachedKnowledgeBases: [
        {
          id: 'att-1',
          kbId: 'kb-1',
          name: 'Product Docs',
          slug: 'product-docs',
          role: 'editor',
          mountAlias: 'docs',
          mode: 'rw',
          attachedById: 'user-1',
          createdAt: '2026-04-21T00:00:00Z',
        },
      ],
      mountedKbSignature: 'abc123456789',
      hasPendingKbChanges: true,
    });

    render(<WorkspaceKnowledgeBasesSettings />);

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/workspaces/ws-123');
    });

    expect(await screen.findByText('Product Docs')).toBeInTheDocument();
    expect(screen.getByText('Desired attachments')).toBeInTheDocument();
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByText('Restart workspace to apply')).toBeInTheDocument();
  });

  it('attach dialog 會在選到 viewer KB 時把 mode 鎖成 ro', async () => {
    const user = userEvent.setup();
    getMock
      .mockResolvedValueOnce({
        id: 'ws-123',
        accessRole: 'manager',
        attachedKnowledgeBases: [],
        mountedKbSignature: null,
        hasPendingKbChanges: false,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'kb-viewer',
            slug: 'kb-viewer',
            name: 'Viewer KB',
            ownerId: 'owner-1',
            currentSizeBytes: 0,
            quotaBytes: null,
            accessRole: 'viewer',
            createdAt: '2026-04-21T00:00:00Z',
            updatedAt: '2026-04-21T00:00:00Z',
          },
        ],
      });

    render(<WorkspaceKnowledgeBasesSettings />);

    await screen.findByText('Attach knowledge base');
    await user.click(screen.getByText('Attach knowledge base'));

    await waitFor(() => {
      expect(getMock).toHaveBeenNthCalledWith(2, '/knowledge-bases');
    });

    await user.click(screen.getByRole('combobox', { name: 'Knowledge Base' }));
    await user.click(await screen.findByText('Viewer KB'));

    expect(
      screen.getByText('Your role on this knowledge base is viewer, so the mode is locked to ro.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Mode' })).toHaveAttribute('data-disabled');
  });

  it('可從 workspace settings attach 新的 knowledge base', async () => {
    const user = userEvent.setup();
    getMock
      .mockResolvedValueOnce({
        id: 'ws-123',
        accessRole: 'manager',
        attachedKnowledgeBases: [],
        mountedKbSignature: null,
        hasPendingKbChanges: false,
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'kb-2',
            slug: 'api-guides',
            name: 'API Guides',
            ownerId: 'owner-1',
            currentSizeBytes: 0,
            quotaBytes: null,
            accessRole: 'editor',
            createdAt: '2026-04-21T00:00:00Z',
            updatedAt: '2026-04-21T00:00:00Z',
          },
        ],
      })
      .mockResolvedValueOnce({
        id: 'ws-123',
        accessRole: 'manager',
        attachedKnowledgeBases: [
          {
            id: 'att-2',
            kbId: 'kb-2',
            name: 'API Guides',
            slug: 'api-guides',
            role: 'editor',
            mountAlias: 'guides',
            mode: 'rw',
            attachedById: 'user-1',
            createdAt: '2026-04-21T00:00:00Z',
          },
        ],
        mountedKbSignature: null,
        hasPendingKbChanges: true,
      });
    postMock.mockResolvedValue({});

    render(<WorkspaceKnowledgeBasesSettings />);

    await screen.findByText('Attach knowledge base');
    await user.click(screen.getByText('Attach knowledge base'));
    await user.click(screen.getByRole('combobox', { name: 'Knowledge Base' }));
    await user.click(await screen.findByText('API Guides'));
    await user.type(screen.getByLabelText('Mount alias'), 'guides');
    await user.click(screen.getByRole('button', { name: 'Attach' }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/workspaces/ws-123/knowledge-bases', {
        kbId: 'kb-2',
        mountAlias: 'guides',
        mode: 'rw',
      });
    });
  });
});
