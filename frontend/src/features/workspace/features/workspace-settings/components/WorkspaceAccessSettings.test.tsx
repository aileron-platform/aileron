import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { fireEvent } from '@testing-library/react';
import { WorkspaceAccessSettings } from './WorkspaceAccessSettings';

const {
  getMock,
  postMock,
  patchMock,
  deleteMock,
  translateMock,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
  translateMock: vi.fn((key: string, params?: Record<string, string>) => {
    const translations: Record<string, string> = {
      'workspace.workspaceSettings.access.header.title': 'Workspace Access',
      'workspace.workspaceSettings.access.status.loading': 'Loading workspace access...',
      'workspace.workspaceSettings.access.status.unavailable':
        'Workspace access is unavailable.',
      'workspace.workspaceSettings.access.notifications.userSearchFailed':
        'Failed to search members.',
      'workspace.workspaceSettings.access.currentAccess.title': 'Current Access',
      'workspace.workspaceSettings.access.currentAccess.description':
        'Ownership and delegated workspace permissions.',
      'workspace.workspaceSettings.access.currentAccess.ownerLabel': 'Owner',
      'workspace.workspaceSettings.access.currentAccess.yourAccessLabel': 'Your access',
      'workspace.workspaceSettings.access.currentAccess.unknownOwner': 'Unknown owner',
      'workspace.workspaceSettings.access.badges.owned': 'Owned',
      'workspace.workspaceSettings.access.roles.owner': 'owner',
      'workspace.workspaceSettings.access.roles.viewer': 'viewer',
      'workspace.workspaceSettings.access.roles.editor': 'editor',
      'workspace.workspaceSettings.access.roles.manager': 'manager',
      'workspace.workspaceSettings.access.sharing.title': 'Sharing',
      'workspace.workspaceSettings.access.sharing.description':
        'Add, change, or remove workspace access for other members.',
      'workspace.workspaceSettings.access.sharing.emailLabel': 'Member email',
      'workspace.workspaceSettings.access.sharing.emailPlaceholder': 'member@example.com',
      'workspace.workspaceSettings.access.sharing.emailAutocompleteHint':
        'Start typing to see matching member emails.',
      'workspace.workspaceSettings.access.sharing.searchPlaceholder': 'Search member email...',
      'workspace.workspaceSettings.access.sharing.startTyping': 'Start typing to search members.',
      'workspace.workspaceSettings.access.sharing.searching': 'Searching members...',
      'workspace.workspaceSettings.access.sharing.noMatches': 'No matching members found.',
      'workspace.workspaceSettings.access.sharing.roleLabel': 'Role',
      'workspace.workspaceSettings.access.sharing.addAction': 'Add share',
      'workspace.workspaceSettings.access.sharing.removeAction': 'Remove',
      'workspace.workspaceSettings.access.sharing.loading': 'Loading workspace shares...',
      'workspace.workspaceSettings.access.sharing.empty': 'No shared users yet.',
      'workspace.workspaceSettings.access.readOnlyNotice':
        'Sharing can only be managed by the workspace owner or a shared manager.',
    };

    if (key === 'workspace.workspaceSettings.access.badges.shared') {
      return `Shared · ${params?.role ?? ''}`;
    }

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

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      workspaceId: 'ws-123',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

describe('WorkspaceAccessSettings', () => {
  beforeEach(() => {
    getMock.mockReset();
    postMock.mockReset();
    patchMock.mockReset();
    deleteMock.mockReset();
    translateMock.mockClear();
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('shows read-only sharing state for viewer role', async () => {
    getMock.mockResolvedValue({
      id: 'ws-123',
      accessRole: 'viewer',
      accessSource: 'shared',
      owner: {
        id: 'owner-1',
        displayName: 'Workspace Owner',
        email: 'owner@example.com',
      },
    });

    render(<WorkspaceAccessSettings />);

    expect(await screen.findByText('Shared · viewer')).toBeInTheDocument();
    expect(
      screen.getByText('Sharing can only be managed by the workspace owner or a shared manager.')
    ).toBeInTheDocument();
    expect(screen.queryByText('Add share')).not.toBeInTheDocument();
  });

  it('loads sharing controls and share list for manager role', async () => {
    getMock
      .mockResolvedValueOnce({
        id: 'ws-123',
        accessRole: 'manager',
        accessSource: 'shared',
        owner: {
          id: 'owner-1',
          displayName: 'Workspace Owner',
          email: 'owner@example.com',
        },
      })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'share-1',
            user: {
              id: 'user-2',
              displayName: 'Shared Member',
              email: 'member@example.com',
            },
            role: 'editor',
            grantedBy: {
              id: 'owner-1',
              displayName: 'Workspace Owner',
            },
            createdAt: '2026-04-16T00:00:00Z',
          },
        ],
      })
      ;

    render(<WorkspaceAccessSettings />);

    expect(await screen.findByText('Add share')).toBeInTheDocument();
    expect(await screen.findByText('Shared Member')).toBeInTheDocument();
    expect(getMock).toHaveBeenNthCalledWith(2, '/workspaces/ws-123/shares');
  });

  it('shows member email combobox suggestions', async () => {
    const user = userEvent.setup();
    getMock
      .mockResolvedValueOnce({
        id: 'ws-123',
        accessRole: 'manager',
        accessSource: 'owned',
        owner: {
          id: 'owner-1',
          displayName: 'Workspace Owner',
          email: 'owner@example.com',
        },
      })
      .mockResolvedValueOnce({ items: [] })
      .mockResolvedValueOnce({
        items: [
          {
            id: 'user-3',
            email: 'candidate@example.com',
            username: 'candidate',
            displayName: 'Candidate User',
          },
        ],
      });

    render(<WorkspaceAccessSettings />);

    const trigger = await screen.findByRole('combobox', { name: 'Member email' });
    expect(trigger).toHaveTextContent('member@example.com');
    await user.click(trigger);
    const searchInput = await screen.findByPlaceholderText('Search member email...');
    fireEvent.change(searchInput, { target: { value: 'candidate@example.com' } });
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(getMock).toHaveBeenNthCalledWith(
      3,
      '/users?query=candidate%40example.com&limit=8'
    );
    expect(await screen.findByText('Candidate User')).toBeInTheDocument();
    expect(screen.getByText('candidate@example.com · candidate')).toBeInTheDocument();
  });
});
