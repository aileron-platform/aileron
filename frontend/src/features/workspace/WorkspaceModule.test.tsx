import type React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceModule } from './WorkspaceModule';

const {
  authState,
  fetchWorkspaceListMock,
  setSelectedWorkspaceId,
  selectionState,
  workspacePermissionState,
  workspaceAllowedOperations,
} = vi.hoisted(() => ({
  authState: {
    platformRole: 'member' as 'admin' | 'member' | null,
    allowedOperations: [] as string[],
  },
  fetchWorkspaceListMock: vi.fn(),
  setSelectedWorkspaceId: vi.fn(),
  selectionState: { selectedWorkspaceId: null as string | null },
  workspacePermissionState: {
    accessRole: 'owner' as 'owner' | 'manager' | 'reader' | null,
  },
  workspaceAllowedOperations: new Set<string>(),
}));

vi.mock('./api/workspaceListApi', () => ({
  fetchWorkspaceList: fetchWorkspaceListMock,
}));

vi.mock('./selection/WorkspaceSelectionContext', () => ({
  useWorkspaceSelection: () => ({
    selectedWorkspaceId: selectionState.selectedWorkspaceId,
    setSelectedWorkspaceId,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({ useI18n: () => ({ t: (key: string) => key }) }));

vi.mock('@/features/auth/public', () => ({
  AuthorizationDeniedState: () => <div role="alert">workspace-access-denied</div>,
  useAuth: () => ({
    user: { id: 'u-1' },
    isAuthenticated: true,
    isLoading: false,
    platformRole: authState.platformRole,
    hasPlatformOperation: (operationId: string) => authState.allowedOperations.includes(operationId),
  }),
}));

vi.mock('./deep-link/useWorkspaceFileOpenQuery', () => ({
  useWorkspaceFileOpenQuery: () => undefined,
}));

vi.mock('./availability/useWorkspaceAvailabilityController', () => ({
  useWorkspaceAvailabilityController: () => ({
    view: workspacePermissionState.accessRole !== null
      && workspaceAllowedOperations.has('workspace.detail.read')
      ? { kind: 'execution' }
      : { kind: 'authorization-denied' },
    refresh: vi.fn(),
    runAction: vi.fn(),
    returnToWorkspaceList: vi.fn(),
  }),
}));

vi.mock('./hooks/useWorkspaceRuntime', () => ({
  useWorkspaceRuntime: () => ({
    workspaceId: 'ws-1',
    workspaceName: 'Workspace',
    runtimeBaseUrl: 'http://runtime.example',
    agenticTools: ['claude-code'],
    accessRole: workspacePermissionState.accessRole,
    accessSource: null,
    accessSources: [],
    allowedOperations: Array.from(workspaceAllowedOperations),
    runtimeStatus: null,
    isLoading: false,
    isAuthorizationResolved: true,
    error: null,
    errorCode: null,
    reload: vi.fn(),
    changeWorkspace: vi.fn(),
  }),
}));

vi.mock('./layout/WorkspaceShell', async () => {
  const { useLocation } = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    WorkspaceShell: ({
      children,
      navigationSlot,
    }: {
      children: React.ReactNode;
      navigationSlot: React.ReactNode;
    }) => {
      const location = useLocation();
      return (
        <>
          {navigationSlot}
          <div data-testid="workspace-location">
            {`${location.pathname}${location.search}${location.hash}`}
          </div>
          {children}
        </>
      );
    },
  };
});

vi.mock('./providers/WorkspaceProvider', () => ({
  WorkspaceProvider: ({
    children,
    workspaceId,
  }: {
    children: React.ReactNode;
    workspaceId?: string | null;
  }) => (
    <div data-testid="provider-workspace-id" data-workspace-id={workspaceId ?? 'null'}>
      {children}
    </div>
  ),
  useWorkspace: () => {
    const hasOperation = (operation: string) => (
      workspacePermissionState.accessRole !== null
      && workspaceAllowedOperations.has(operation)
    );

    return {
      dispatch: vi.fn(),
      fileManagementTabsRestoreStatus: {
        ready: true,
        workspaceId: 'ws-1',
        contextId: null,
      },
      permissions: {
        canRead: hasOperation('workspace.detail.read'),
        canRunLifecycle: hasOperation('workspace.lifecycle.execute'),
        canUseChat: hasOperation('workspace.agent_chat.use'),
        hasOperation,
      },
      state: {
        versionControl: {
          selectedGitContextId: null,
        },
      },
      openFileInTab: vi.fn(),
      workspaceRuntime: {
        workspaceId: 'ws-1',
        isLoading: false,
        isAuthorizationResolved: true,
        error: null,
        errorCode: null,
      },
    };
  },
}));

vi.mock('./features/file-management/FileManagementPage', () => ({
  default: () => <div>file-management-feature</div>,
}));

vi.mock('./features/version-control/VersionControlPage', () => ({
  default: () => <div>version-control-feature</div>,
}));

vi.mock('./features/workspace-settings/WorkspaceSettingsPage', () => ({
  default: () => <div>workspace-settings-feature</div>,
}));

vi.mock('./features/container-management/ContainerManagementPage', () => ({
  default: () => <div>container-management-feature</div>,
}));

vi.mock('./routes/WorkspaceAutomationRoute', () => ({
  default: () => <div>workspace-automation-feature</div>,
}));

vi.mock('@/features/ai-chat/public', () => ({
  loadAiChatPage: () => Promise.resolve({
    default: () => <div>ai-chat-home-feature</div>,
  }),
}));

const renderWorkspaceRoute = (initialEntry: string) => render(
  <MemoryRouter initialEntries={[initialEntry]}>
    <Routes>
      <Route path="/workspaces/workspace-wizard" element={<div>workspace-wizard</div>} />
      <Route
        path="/workspaces/*"
        element={<WorkspaceModule navigationSlot={<div data-testid="workspace-navigation-slot" />} />}
      />
    </Routes>
  </MemoryRouter>,
);

describe('WorkspaceModule canonical routes', () => {
  beforeEach(() => {
    setSelectedWorkspaceId.mockClear();
    fetchWorkspaceListMock.mockReset().mockResolvedValue({ items: [] });
    selectionState.selectedWorkspaceId = null;
    workspacePermissionState.accessRole = 'owner';
    workspaceAllowedOperations.clear();
    [
      'workspace.detail.read',
      'workspace.agent_chat.use',
      'workspace.automation.execute',
    ].forEach(operation => workspaceAllowedOperations.add(operation));
    authState.platformRole = 'member';
    authState.allowedOperations = ['workspace.create'];
  });

  it.each([
    ['/workspaces/ws-route/home', 'ai-chat-home-feature'],
    ['/workspaces/ws-route/files', 'file-management-feature'],
    ['/workspaces/ws-route/version-control/history', 'version-control-feature'],
    ['/workspaces/ws-route/workspace-settings/access', 'workspace-settings-feature'],
    ['/workspaces/ws-route/container-management/terminal', 'container-management-feature'],
    ['/workspaces/ws-route/workspace-automation', 'workspace-automation-feature'],
  ])('renders %s with URL workspace identity', async (path, expectedFeature) => {
    renderWorkspaceRoute(path);

    expect(await screen.findByText(expectedFeature)).toBeInTheDocument();
    expect(screen.getByTestId('provider-workspace-id')).toHaveAttribute('data-workspace-id', 'ws-route');
    await waitFor(() => {
      expect(setSelectedWorkspaceId).toHaveBeenCalledWith('ws-route');
    });
  });

  it.each([
    '/workspaces/ws-route/canvas',
    '/workspaces/ws-route/browser',
    '/workspaces/ws-route/claude-code/settings',
    '/workspaces/ws-route/opencode/settings',
    '/workspaces/ws-route/codex/settings',
  ])('accepts the canonical shell-owned route %s', async (path) => {
    renderWorkspaceRoute(path);

    expect(await screen.findByTestId('provider-workspace-id')).toHaveAttribute(
      'data-workspace-id',
      'ws-route',
    );
    expect(screen.queryByText('workspace.layout.featureNotFound')).not.toBeInTheDocument();
    expect(screen.getByTestId('workspace-location')).toHaveTextContent(path);
  });

  it.each([
    '/workspaces/ws-route/canvas/browser',
    '/workspaces/ws-route/canvas/web-canvas',
    '/workspaces/ws-route/browser/session',
  ])('rejects the removed Canvas and Browser subview route %s', async (path) => {
    renderWorkspaceRoute(path);

    expect(await screen.findByText('workspace.layout.featureNotFound')).toBeInTheDocument();
  });

  it('resolves /workspaces to the selected workspace canonical home', async () => {
    selectionState.selectedWorkspaceId = 'ws-selected';
    fetchWorkspaceListMock.mockResolvedValue({
      items: [{
        id: 'ws-selected',
        name: 'Selected workspace',
        accessRole: 'manager',
        allowedOperations: [
          'workspace.detail.read',
          'workspace.agent_chat.use',
        ],
      }],
    });
    renderWorkspaceRoute('/workspaces');

    expect(await screen.findByText('ai-chat-home-feature')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-location')).toHaveTextContent(
      '/workspaces/ws-selected/home',
    );
  });

  it('selects the first workspace when the persisted selection is stale', async () => {
    selectionState.selectedWorkspaceId = 'ws-stale';
    fetchWorkspaceListMock.mockResolvedValue({
      items: [
        {
          id: 'ws-first',
          name: 'First workspace',
          accessRole: 'manager',
          allowedOperations: [
            'workspace.detail.read',
            'workspace.agent_chat.use',
          ],
        },
        {
          id: 'ws-second',
          name: 'Second workspace',
          accessRole: 'manager',
          allowedOperations: [
            'workspace.detail.read',
            'workspace.agent_chat.use',
          ],
        },
      ],
    });

    renderWorkspaceRoute('/workspaces');

    expect(await screen.findByText('ai-chat-home-feature')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-location')).toHaveTextContent(
      '/workspaces/ws-first/home',
    );
    expect(setSelectedWorkspaceId).toHaveBeenCalledWith('ws-first');
  });

  it('renders an empty state without automatically opening the wizard', async () => {
    renderWorkspaceRoute('/workspaces');

    expect(await screen.findByText('common.entry.title')).toBeInTheDocument();
    expect(screen.queryByText('workspace-wizard')).not.toBeInTheDocument();
    expect(setSelectedWorkspaceId).toHaveBeenCalledWith(null);
  });

  it('opens the workspace wizard only from the empty-state action', async () => {
    renderWorkspaceRoute('/workspaces');

    fireEvent.click(
      await screen.findByRole('button', {
        name: 'common.entry.actions.create',
      }),
    );

    expect(await screen.findByText('workspace-wizard')).toBeInTheDocument();
  });

  it('hides the empty-state create action without the confirmed platform operation', async () => {
    authState.allowedOperations = [];

    renderWorkspaceRoute('/workspaces');

    expect(await screen.findByText('common.entry.title')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'common.entry.actions.create' }),
    ).not.toBeInTheDocument();
  });

  it('routes to Files when detail read is present without agent chat use', async () => {
    fetchWorkspaceListMock.mockResolvedValue({
      items: [{
        id: 'ws-view-only',
        name: 'View-only workspace',
        accessRole: 'manager',
        allowedOperations: ['workspace.detail.read'],
      }],
    });

    renderWorkspaceRoute('/workspaces');

    expect(await screen.findByText('file-management-feature')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-location')).toHaveTextContent(
      '/workspaces/ws-view-only/files',
    );
  });

  it('routes a reader to Files even when agent_chat.use is present', async () => {
    workspacePermissionState.accessRole = 'reader';
    fetchWorkspaceListMock.mockResolvedValue({
      items: [{
        id: 'ws-reader',
        name: 'Viewer workspace',
        accessRole: 'reader',
        allowedOperations: ['workspace.detail.read'],
      }],
    });

    renderWorkspaceRoute('/workspaces');

    expect(await screen.findByText('file-management-feature')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-location')).toHaveTextContent(
      '/workspaces/ws-reader/files',
    );
  });

  it('denies a workspace file route when the effective read operation is unavailable', async () => {
    workspaceAllowedOperations.delete('workspace.detail.read');

    renderWorkspaceRoute('/workspaces/ws-route/files');

    expect(await screen.findByText('WORKSPACE_ACCESS_DENIED')).toBeInTheDocument();
    expect(screen.queryByTestId('provider-workspace-id')).not.toBeInTheDocument();
    expect(screen.queryByText('file-management-feature')).not.toBeInTheDocument();
  });

  it('denies workspace automation when its effective operation is unavailable', async () => {
    workspaceAllowedOperations.delete('workspace.automation.execute');

    renderWorkspaceRoute('/workspaces/ws-route/workspace-automation');

    expect(await screen.findByRole('alert')).toHaveTextContent('workspace-access-denied');
    expect(screen.queryByText('workspace-automation-feature')).not.toBeInTheDocument();
  });

  it('renders loading while the workspace list is pending', () => {
    fetchWorkspaceListMock.mockReturnValue(new Promise(() => {}));

    renderWorkspaceRoute('/workspaces');

    expect(screen.getByTestId('entry-frame')).toBeInTheDocument();
  });

  it('renders an error state and retries the workspace list request', async () => {
    fetchWorkspaceListMock
      .mockRejectedValueOnce(new Error('list unavailable'))
      .mockResolvedValueOnce({ items: [] });
    renderWorkspaceRoute('/workspaces');

    fireEvent.click(
      await screen.findByRole('button', { name: 'common.entry.actions.refresh' }),
    );

    expect(await screen.findByText('common.entry.title')).toBeInTheDocument();
    expect(fetchWorkspaceListMock).toHaveBeenCalledTimes(2);
  });

  it('preserves query and hash on a canonical route', async () => {
    renderWorkspaceRoute('/workspaces/ws-route/files?open=%2Fdocs%2Fplan.md#preview');

    expect(await screen.findByText('file-management-feature')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-location')).toHaveTextContent(
      '/workspaces/ws-route/files?open=%2Fdocs%2Fplan.md#preview',
    );
  });
});
