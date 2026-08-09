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
  workspacePermissions,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  patchMock: vi.fn(),
  deleteMock: vi.fn(),
  workspacePermissions: {
    accessRole: 'manager' as 'reader' | 'manager',
    canManageSettings: true,
  },
  translateMock: vi.fn((key: string, params?: Record<string, string>) => {
    const translations: Record<string, string> = {
      'workspace.workspaceSettings.access.header.title': 'Workspace Access',
      'workspace.workspaceSettings.access.status.loading': 'Loading workspace access...',
      'workspace.workspaceSettings.access.status.unavailable':
        'Workspace access is unavailable.',
      'workspace.workspaceSettings.access.notifications.candidateSearchFailed':
        'Failed to search sharing candidates.',
      'workspace.workspaceSettings.access.currentAccess.title': 'Current Access',
      'workspace.workspaceSettings.access.currentAccess.description':
        'Ownership and delegated workspace permissions.',
      'workspace.workspaceSettings.access.currentAccess.ownerLabel': 'Owner',
      'workspace.workspaceSettings.access.currentAccess.yourAccessLabel': 'Your access',
      'workspace.workspaceSettings.access.currentAccess.unknownOwner': 'Unknown owner',
      'workspace.workspaceSettings.access.badges.owned': 'Owned',
      'workspace.workspaceSettings.access.badges.directShare': 'Direct share',
      'workspace.workspaceSettings.access.roles.owner': 'owner',
      'workspace.workspaceSettings.access.roles.reader': 'reader',
      'workspace.workspaceSettings.access.roles.manager': 'manager',
      'workspace.workspaceSettings.access.sharing.title': 'Sharing',
      'workspace.workspaceSettings.access.sharing.description':
        'Add, change, or remove workspace access for users and user groups.',
      'workspace.workspaceSettings.access.sharing.targetTypes.user': 'User',
      'workspace.workspaceSettings.access.sharing.targetTypes.group': 'User group',
      'workspace.workspaceSettings.access.sharing.targetLabel': 'Share with',
      'workspace.workspaceSettings.access.sharing.targetPlaceholder': 'Choose a user or group',
      'workspace.workspaceSettings.access.sharing.searchPlaceholder': 'Search users or groups...',
      'workspace.workspaceSettings.access.sharing.startTyping': 'Start typing to search.',
      'workspace.workspaceSettings.access.sharing.searching': 'Searching...',
      'workspace.workspaceSettings.access.sharing.noMatches': 'No matching users or groups found.',
      'workspace.workspaceSettings.access.sharing.roleLabel': 'Role',
      'workspace.workspaceSettings.access.sharing.addAction': 'Add share',
      'workspace.workspaceSettings.access.sharing.removeAction': 'Remove',
      'workspace.workspaceSettings.access.sharing.loading': 'Loading workspace shares...',
      'workspace.workspaceSettings.access.sharing.empty': 'No shares yet.',
    };

    if (key === 'workspace.workspaceSettings.access.badges.directShare') {
      return `Direct share · ${params?.role ?? ''}`;
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
    permissions: workspacePermissions,
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
    workspacePermissions.accessRole = 'manager';
    workspacePermissions.canManageSettings = true;
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    });
  });

  it('shows read-only sharing state for reader role', async () => {
    workspacePermissions.accessRole = 'reader';
    workspacePermissions.canManageSettings = false;
    getMock.mockResolvedValue({
      id: 'ws-123',
      accessRole: 'reader',
      accessSource: 'direct_share',
      owner: {
        id: 'owner-1',
        displayName: 'Workspace Owner',
        email: 'owner@example.com',
      },
    });

    render(<WorkspaceAccessSettings />);

    expect(await screen.findByText('Direct share · reader')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add share' })).toBeDisabled();
    expect(screen.getByRole('combobox', { name: 'Share with' })).toBeDisabled();
  });

  it('loads sharing controls and share list for manager role', async () => {
    getMock
      .mockResolvedValueOnce({
        id: 'ws-123',
        accessRole: 'manager',
        accessSource: 'direct_share',
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
            targetType: 'user',
            targetId: 'user-2',
            targetLabel: 'Shared Member',
            role: 'manager',
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

  it('searches member-safe user candidates and creates a target-based share', async () => {
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
            label: 'Candidate User',
          },
        ],
      });
    postMock.mockResolvedValue({
      id: 'share-2',
      targetType: 'user',
      targetId: 'user-3',
      targetLabel: 'Candidate User',
      role: 'reader',
      grantedBy: { id: 'owner-1', displayName: 'Workspace Owner' },
      createdAt: '2026-07-31T00:00:00Z',
    });

    render(<WorkspaceAccessSettings />);

    const trigger = await screen.findByRole('combobox', { name: 'Share with' });
    expect(trigger).toHaveTextContent('Choose a user or group');
    await user.click(trigger);
    const searchInput = await screen.findByPlaceholderText('Search users or groups...');
    fireEvent.change(searchInput, { target: { value: 'candidate' } });
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(getMock).toHaveBeenNthCalledWith(
      3,
      '/workspaces/ws-123/share-candidate-users?query=candidate&limit=8'
    );
    await user.click(await screen.findByText('Candidate User'));
    await user.click(screen.getByRole('button', { name: 'Add share' }));
    expect(postMock).toHaveBeenCalledWith('/workspaces/ws-123/shares', {
      targetType: 'user',
      targetId: 'user-3',
      role: 'reader',
    });
  });
});
