import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AppRouter } from './AppRouter';

vi.mock('@/features/auth/public', () => ({
  RequireAuth: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  RequirePlatformMember: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="platform-member-guard">{children}</div>
  ),
  RequirePlatformAdmin: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="platform-admin-guard">{children}</div>
  ),
  RequirePlatformOperation: ({
    children,
    operationId,
  }: {
    children: React.ReactNode;
    operationId: string;
  }) => (
    <div data-operation-id={operationId} data-testid="platform-operation-guard">
      {children}
    </div>
  ),
  PublicRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  loadLoginPage: () => Promise.resolve({
    default: () => <div>login-page</div>,
  }),
  loadRegisterPage: () => Promise.resolve({
    default: () => <div>register-page</div>,
  }),
  loadCallbackPage: () => Promise.resolve({
    default: () => <div>callback-page</div>,
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      user: { id: 'user-1' },
    },
  }),
}));

vi.mock('./routes/WorkspaceRoute', () => ({
  WorkspaceRoute: () => <div>workspace-module</div>,
  WorkspaceDeepLinkRoute: () => <div>workspace-file-deep-link-route</div>,
}));

vi.mock('@/features/marketplace/public', () => ({
  loadMarketplaceModule: () => Promise.resolve({
    default: ({ userId }: { userId: string | null }) => (
      <div>marketplace-module:{userId}</div>
    ),
  }),
}));

vi.mock('@/features/workspace-wizard/public', () => ({
  loadWorkspaceWizardPage: () => Promise.resolve({
    default: ({
      navigationSlot,
      userId,
    }: {
      navigationSlot: React.ReactNode;
      userId?: string;
    }) => (
      <div>
        {navigationSlot}
        <div>workspace-wizard-page:{userId}</div>
      </div>
    ),
  }),
}));

vi.mock('@/app/components/navigation/GlobalNavigation', () => ({
  GlobalNavigation: () => <div>global-navigation</div>,
}));

vi.mock('@/features/workspace-automation/public', () => ({
  loadAutomationModule: () => Promise.resolve({
    default: ({ navigationSlot }: { navigationSlot: React.ReactNode }) => (
      <div>
        {navigationSlot}
        <div>automation-module</div>
      </div>
    ),
  }),
}));

vi.mock('@/features/knowledge-base/public', () => ({
  loadKnowledgeBaseModule: () => Promise.resolve({
    default: () => <div>knowledge-base-module</div>,
  }),
}));

vi.mock('@/features/user-management/public', () => ({
  loadUserManagementModule: () => Promise.resolve({
    default: ({ navigationSlot }: { navigationSlot: React.ReactNode }) => (
      <div>
        {navigationSlot}
        <div>user-management-module</div>
      </div>
    ),
  }),
}));

vi.mock('@/features/platform-resources/public', () => ({
  loadPlatformResourcesModule: () => Promise.resolve({
    default: ({ navigationSlot }: { navigationSlot: React.ReactNode }) => (
      <div>
        {navigationSlot}
        <div>platform-resources-module</div>
      </div>
    ),
  }),
}));

vi.mock('../pages/ProfilePage', () => ({
  default: () => <div>profile-page</div>,
}));

vi.mock('../pages/SettingsPage', () => ({
  default: () => <div>settings-page</div>,
}));

describe('AppRouter', () => {
  it('renders the workspace wizard through its public entry', async () => {
    render(
      <MemoryRouter initialEntries={['/workspaces/workspace-wizard']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('workspace-wizard-page:user-1')).toBeInTheDocument();
    expect(screen.getByText('global-navigation')).toBeInTheDocument();
    expect(screen.getByTestId('platform-member-guard')).toBeInTheDocument();
  });

  it('renders workspace file deep link route on singular workspace paths', async () => {
    render(
      <MemoryRouter initialEntries={['/workspace/.aileron/canvases/demo/page.tsx']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('workspace-file-deep-link-route')).toBeInTheDocument();
    expect(screen.getByTestId('platform-member-guard')).toBeInTheDocument();
  });

  it('renders marketplace on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/marketplace/packages/codex/abc/edit']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('marketplace-module:user-1')).toBeInTheDocument();
    expect(screen.getByTestId('platform-member-guard')).toBeInTheDocument();
  });

  it('renders automation on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/automation?status=running']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('automation-module')).toBeInTheDocument();
    expect(screen.getByText('global-navigation')).toBeInTheDocument();
    expect(screen.getByTestId('platform-member-guard')).toBeInTheDocument();
  });

  it('renders knowledge base center on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-bases/kb-1/sharing']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('knowledge-base-module')).toBeInTheDocument();
    expect(screen.getByTestId('platform-member-guard')).toBeInTheDocument();
  });

  it('renders user management on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/user-management/groups']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('user-management-module')).toBeInTheDocument();
    expect(screen.getByText('global-navigation')).toBeInTheDocument();
    expect(screen.getByTestId('platform-admin-guard')).toContainElement(
      screen.getByText('user-management-module'),
    );
  });

  it('renders platform resources only inside its authoritative operation guard', async () => {
    render(
      <MemoryRouter initialEntries={['/platform-resources/workspaces']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('platform-resources-module')).toBeInTheDocument();
    expect(screen.getByTestId('platform-operation-guard')).toHaveAttribute(
      'data-operation-id',
      'platform_resources.read',
    );
    expect(screen.getByTestId('platform-operation-guard')).toContainElement(
      screen.getByText('platform-resources-module'),
    );
  });

  it('renders profile on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/profile']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('profile-page')).toBeInTheDocument();
  });

  it('renders settings on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/settings']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('settings-page')).toBeInTheDocument();
  });

});
