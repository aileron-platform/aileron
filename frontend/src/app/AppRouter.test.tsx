import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { AppRouter } from './AppRouter';

vi.mock('../features/auth/components/RequireAuth', () => ({
  RequireAuth: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  PublicRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock('../features/workspace/WorkspaceModule', () => ({
  default: () => <div>workspace-module</div>,
}));

vi.mock('../features/template-management/TemplateManagementModule', () => ({
  default: () => <div>template-module</div>,
}));

vi.mock('../features/workspace-wizard/WorkspaceWizardPage', () => ({
  default: () => <div>workspace-wizard-page</div>,
}));

vi.mock('../features/automation/AutomationModule', () => ({
  default: () => <div>automation-module</div>,
}));

vi.mock('../features/knowledge-base/KnowledgeBaseModule', () => ({
  default: () => <div>knowledge-base-module</div>,
}));

vi.mock('../pages/ProfilePage', () => ({
  default: () => <div>profile-page</div>,
}));

vi.mock('../pages/SettingsPage', () => ({
  default: () => <div>settings-page</div>,
}));

vi.mock('../features/auth/pages/LoginPage', () => ({
  default: () => <div>login-page</div>,
}));

vi.mock('../features/auth/pages/RegisterPage', () => ({
  default: () => <div>register-page</div>,
}));

vi.mock('../features/auth/pages/CallbackPage', () => ({
  default: () => <div>callback-page</div>,
}));

vi.mock('../pages/ClaudeToolWidgetDemo', () => ({
  default: () => <div>claude-tool-widget-demo</div>,
}));

describe('AppRouter', () => {
  it('renders template management on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/templates/templates/abc/edit']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('template-module')).toBeInTheDocument();
  });

  it('renders automation on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/automation?status=running']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('automation-module')).toBeInTheDocument();
  });

  it('renders knowledge base center on the new root path', async () => {
    render(
      <MemoryRouter initialEntries={['/knowledge-bases/kb-1/sharing']}>
        <AppRouter />
      </MemoryRouter>
    );

    expect(await screen.findByText('knowledge-base-module')).toBeInTheDocument();
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
