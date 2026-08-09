import type React from 'react';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GlobalNavigation } from './GlobalNavigation';

const {
  apiGetMock,
  fetchWorkspaceListMock,
  setSelectedWorkspaceId,
  selectionState,
  authState,
} = vi.hoisted(() => ({
  apiGetMock: vi.fn(),
  fetchWorkspaceListMock: vi.fn(),
  setSelectedWorkspaceId: vi.fn(),
  selectionState: {
    selectedWorkspaceId: null as string | null,
  },
  authState: {
    platformRole: 'admin' as 'admin' | 'member' | null,
    isPlatformAdmin: true,
    allowedOperations: ['platform_resources.read'] as string[],
  },
}));

vi.mock('@/features/workspace/public', () => ({
  useWorkspaceSelection: () => ({
    selectedWorkspaceId: selectionState.selectedWorkspaceId,
    setSelectedWorkspaceId,
  }),
  fetchWorkspaceList: fetchWorkspaceListMock,
  resolveWorkspacePermissions: (
    _accessRole: string | null | undefined,
    allowedOperations: readonly string[] | undefined,
  ) => ({
    canUseChat: allowedOperations?.includes('workspace.agent_chat.use') ?? false,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/features/auth/public', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    platformRole: authState.platformRole,
    isPlatformAdmin: authState.isPlatformAdmin,
    hasPlatformOperation: (operationId: string) => (
      authState.allowedOperations.includes(operationId)
    ),
    logout: vi.fn(),
    user: {
      sub: 'user-1',
      preferred_username: 'admin',
      email: 'admin@example.com',
    },
  }),
}));

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      user: {
        id: 'user-1',
      },
    },
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: apiGetMock,
  },
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}));

vi.mock('@/shared/components/ui/dropdown-menu', () => {
  const Container = ({ children }: { children: React.ReactNode }) => <div>{children}</div>;
  const Trigger = ({ children }: { children: React.ReactNode }) => <>{children}</>;
  const Item = ({
    children,
    onClick,
    onSelect,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & { onSelect?: () => void }) => (
    <button
      {...props}
      type="button"
      onClick={(event) => {
        onSelect?.();
        onClick?.(event);
      }}
    >
      {children}
    </button>
  );

  return {
    DropdownMenu: Container,
    DropdownMenuContent: Container,
    DropdownMenuGroup: Container,
    DropdownMenuItem: Item,
    DropdownMenuLabel: Container,
    DropdownMenuSeparator: () => <hr />,
    DropdownMenuTrigger: Trigger,
  };
});

describe('GlobalNavigation', () => {
  beforeEach(() => {
    apiGetMock.mockReset();
    fetchWorkspaceListMock.mockReset().mockResolvedValue({ items: [] });
    setSelectedWorkspaceId.mockReset();
    selectionState.selectedWorkspaceId = null;
    authState.platformRole = 'admin';
    authState.isPlatformAdmin = true;
    authState.allowedOperations = ['platform_resources.read'];
  });

  it('shows the user management entry for platform administrators', async () => {
    render(
      <MemoryRouter initialEntries={['/workspaces']}>
        <GlobalNavigation />
      </MemoryRouter>
    );

    expect(await screen.findByText('navigation.userManagement')).toBeInTheDocument();
    expect(screen.getByText('platformResources.navigation')).toBeInTheDocument();
  });

  it('separates workspace, application, and administration navigation groups', async () => {
    render(
      <MemoryRouter initialEntries={['/workspaces']}>
        <GlobalNavigation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(setSelectedWorkspaceId).toHaveBeenCalledWith(null);
    });

    const workspaceGroup = screen.getByTestId('global-navigation-workspace-group');
    const applicationGroup = screen.getByTestId('global-navigation-application-group');
    const administrationGroup = screen.getByTestId('global-navigation-administration-group');

    expect(within(workspaceGroup).getByText('navigation.workspace')).toBeInTheDocument();
    expect(within(applicationGroup).getByText('navigation.automation')).toBeInTheDocument();
    expect(within(applicationGroup).getByText('navigation.marketplace')).toBeInTheDocument();
    expect(within(applicationGroup).getByText('navigation.knowledgeBaseCenter')).toBeInTheDocument();
    expect(within(applicationGroup).queryByText('platformResources.navigation')).not.toBeInTheDocument();
    expect(within(administrationGroup).getByText('platformResources.navigation')).toBeInTheDocument();
    expect(within(administrationGroup).getByText('navigation.userManagement')).toBeInTheDocument();
  });

  it('hides the user management entry from platform members', async () => {
    authState.platformRole = 'member';
    authState.isPlatformAdmin = false;
    authState.allowedOperations = [];

    render(
      <MemoryRouter initialEntries={['/workspaces']}>
        <GlobalNavigation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(fetchWorkspaceListMock).toHaveBeenCalled();
    });
    expect(screen.queryByText('navigation.userManagement')).not.toBeInTheDocument();
    expect(screen.queryByText('platformResources.navigation')).not.toBeInTheDocument();
    expect(screen.queryByTestId('global-navigation-administration-group')).not.toBeInTheDocument();
  });

  it('does not fetch or render member modules when platform authorization is absent', async () => {
    authState.platformRole = null;
    authState.isPlatformAdmin = false;
    authState.allowedOperations = [];

    render(
      <MemoryRouter initialEntries={['/workspaces']}>
        <GlobalNavigation />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(fetchWorkspaceListMock).not.toHaveBeenCalled();
    });
    expect(screen.queryByText('navigation.workspace')).not.toBeInTheDocument();
    expect(screen.queryByText('navigation.automation')).not.toBeInTheDocument();
    expect(screen.queryByText('navigation.marketplace')).not.toBeInTheDocument();
    expect(screen.queryByText('navigation.userManagement')).not.toBeInTheDocument();
  });

  it('hides Platform Resources when an admin snapshot lacks its read operation', async () => {
    authState.allowedOperations = [];

    render(
      <MemoryRouter initialEntries={['/workspaces']}>
        <GlobalNavigation />
      </MemoryRouter>
    );

    expect(await screen.findByText('navigation.userManagement')).toBeInTheDocument();
    expect(screen.queryByText('platformResources.navigation')).not.toBeInTheDocument();
  });

  it('navigates workspace selection directly to the selected canonical home', async () => {
    selectionState.selectedWorkspaceId = 'ws-a';
    fetchWorkspaceListMock.mockResolvedValue({
      items: [
        {
          id: 'ws-a',
          name: 'Workspace A',
          accessRole: 'owner',
          allowedOperations: [
            'workspace.detail.read',
            'workspace.agent_chat.use',
          ],
        },
        {
          id: 'ws-b',
          name: 'Workspace B',
          accessRole: 'owner',
          allowedOperations: [
            'workspace.detail.read',
            'workspace.agent_chat.use',
          ],
        },
      ],
    });

    const LocationProbe = () => {
      const location = useLocation();
      return <div data-testid="location">{location.pathname}</div>;
    };

    render(
      <MemoryRouter initialEntries={['/workspaces/ws-a/files']}>
        <GlobalNavigation />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByTestId('workspace-option-ws-b'));

    expect(setSelectedWorkspaceId).toHaveBeenCalledWith('ws-b');
    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/workspaces/ws-b/home');
    });
  });

  it('navigates workspace selection to Files without effective Chat permission', async () => {
    selectionState.selectedWorkspaceId = 'ws-a';
    fetchWorkspaceListMock.mockResolvedValue({
      items: [
        {
          id: 'ws-a',
          name: 'Workspace A',
          accessRole: 'owner',
          allowedOperations: ['workspace.detail.read'],
        },
        {
          id: 'ws-b',
          name: 'Workspace B',
          accessRole: 'owner',
          allowedOperations: ['workspace.detail.read'],
        },
      ],
    });

    const LocationProbe = () => {
      const location = useLocation();
      return <div data-testid="location">{location.pathname}</div>;
    };

    render(
      <MemoryRouter initialEntries={['/workspaces/ws-a/files']}>
        <GlobalNavigation />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.click(await screen.findByTestId('workspace-option-ws-b'));

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/workspaces/ws-b/files');
    });
  });

  it('does not replace URL-owned workspace identity from the workspace list', async () => {
    fetchWorkspaceListMock.mockResolvedValue({
      items: [{
        id: 'ws-list-default',
        name: 'Workspace Default',
        accessRole: 'owner',
        allowedOperations: ['workspace.detail.read'],
      }],
    });

    render(
      <MemoryRouter initialEntries={['/workspaces/ws-from-route/files']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/*" element={<GlobalNavigation />} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByTestId('workspace-option-ws-list-default');
    expect(setSelectedWorkspaceId).not.toHaveBeenCalledWith('ws-list-default');
  });

  it('opens the workspace wizard without requiring completed system settings', async () => {
    apiGetMock.mockResolvedValue({ data: {} });

    const LocationProbe = () => {
      const location = useLocation();
      return <div data-testid="location">{location.pathname}</div>;
    };

    render(
      <MemoryRouter initialEntries={['/workspaces']}>
        <GlobalNavigation />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.click(
      await screen.findByTitle('navigation.workspaceSelector.newWorkspace'),
    );

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent(
        '/workspaces/workspace-wizard',
      );
    });
    expect(apiGetMock).not.toHaveBeenCalled();
  });
});
