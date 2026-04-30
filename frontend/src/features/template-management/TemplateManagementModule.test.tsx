import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { TemplateManagementModule } from './TemplateManagementModule';
import {
  cloneRepository,
  getRepositoryStatus,
  initRepository,
} from '@/features/template-management/api/templateGitApi';
import { apiClient } from '@/shared/api/apiClient';
import * as templateApi from '@/features/template-management/api/templateApi';

vi.mock('@/app/components/navigation/GlobalNavigation', () => ({
  GlobalNavigation: () => <div data-testid="global-navigation" />,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, string>) => {
      const values: Record<string, string> = {
        'template.center.onboarding.loading': 'Checking Template Center repository...',
        'template.center.onboarding.title': 'Set up Template Center registry',
        'template.center.onboarding.description': 'Clone or initialize before entering Template Center.',
        'template.center.onboarding.clone.title': 'Clone existing registry',
        'template.center.onboarding.clone.description': 'Clone description',
        'template.center.onboarding.clone.blockedTitle': 'Clone is unavailable',
        'template.center.onboarding.clone.blockedDescription': 'Clone blocked description',
        'template.center.onboarding.clone.blockedReason': 'Initialize the current registry instead.',
        'template.center.onboarding.clone.urlLabel': 'Repository URL',
        'template.center.onboarding.clone.urlPlaceholder': 'git@example.com:repo.git',
        'template.center.onboarding.clone.branchLabel': 'Branch',
        'template.center.onboarding.clone.branchPlaceholder': 'main',
        'template.center.onboarding.clone.branchHelper': 'Leave blank.',
        'template.center.onboarding.clone.progressTitle': 'Clone progress',
        'template.center.onboarding.clone.actions.clone': 'Clone registry',
        'template.center.onboarding.clone.actions.cloning': 'Cloning...',
        'template.center.onboarding.init.title': 'Initialize current registry',
        'template.center.onboarding.init.description': 'Initialize description',
        'template.center.onboarding.init.actions.init': 'Initialize registry',
        'template.center.onboarding.init.actions.initializing': 'Initializing...',
        'template.center.onboarding.statusError.title': 'Unable to check repository status',
        'template.center.onboarding.statusError.description': 'Status failed.',
        'template.center.onboarding.actions.retry': 'Retry',
        'template.center.onboarding.validation.cloneUrlRequired': 'Repository URL is required.',
        'template.center.onboarding.toasts.cloneStarted.title': 'Clone started',
        'template.center.onboarding.toasts.cloneStarted.description': 'Clone started description',
        'template.center.onboarding.toasts.cloneFailed.title': 'Clone failed',
        'template.center.onboarding.toasts.cloneFailed.description': `Clone failed: ${params?.error ?? ''}`,
        'template.center.onboarding.toasts.initSuccess.title': 'Registry initialized',
        'template.center.onboarding.toasts.initSuccess.description': 'Registry initialized description',
        'template.center.onboarding.toasts.initFailed.title': 'Initialization failed',
        'template.center.onboarding.toasts.initFailed.description': `Initialization failed: ${params?.error ?? ''}`,
        'template.center.onboarding.unknownError': 'Unknown error',
      };
      return values[key] ?? key;
    },
  }),
}));

vi.mock('@/features/template-management/api/templateGitApi', () => ({
  getRepositoryStatus: vi.fn(),
  initRepository: vi.fn(),
  cloneRepository: vi.fn(),
  getCloneProgress: vi.fn(),
}));

vi.mock('@/features/template-management/api/templateApi', () => ({
  listTemplates: vi.fn(),
  deleteTemplate: vi.fn(),
  importTemplate: vi.fn(),
  exportTemplate: vi.fn(),
  installTemplate: vi.fn(),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

vi.mock('./features/template-center/TemplateCenterView', () => ({
  TemplateCenterView: () => <div data-testid="template-center-view">Template Center View</div>,
}));

vi.mock('./features/template-center-settings/TemplateCenterSettingsView', () => ({
  TemplateCenterSettingsView: () => <div data-testid="template-settings-view">Template Settings View</div>,
}));

vi.mock('./features/template-detail/TemplateDetailView', () => ({
  TemplateDetailView: () => <div data-testid="template-detail-view">Template Detail View</div>,
}));

vi.mock('./features/template-editor/TemplateEditorView', () => ({
  TemplateEditorView: ({ mode }: { mode: string }) => <div data-testid={`template-editor-${mode}`}>Template Editor</div>,
}));

const notInitializedStatus = {
  isGitRepo: false,
  currentBranch: null,
  remoteUrl: null,
  hasOrigin: false,
  hasLocalContent: false,
  canCloneSafely: true,
  canInitSafely: true,
  cloneBlockedReason: null,
};

const blockedCloneStatus = {
  ...notInitializedStatus,
  hasLocalContent: true,
  canCloneSafely: false,
  cloneBlockedReason: 'GIT_CLONE_TARGET_NOT_EMPTY',
};

const initializedStatus = {
  isGitRepo: true,
  currentBranch: 'main',
  remoteUrl: null,
  hasOrigin: false,
  hasLocalContent: true,
  canCloneSafely: false,
  canInitSafely: false,
  cloneBlockedReason: 'GIT_REPOSITORY_ALREADY_INITIALIZED',
};

const renderModule = (initialEntry = '/templates/templates') => render(
  <MemoryRouter initialEntries={[initialEntry]}>
    <Routes>
      <Route path="/templates/*" element={<TemplateManagementModule />} />
    </Routes>
  </MemoryRouter>,
);

describe('TemplateManagementModule repository onboarding', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(templateApi.listTemplates).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      limit: 100,
    });
    vi.mocked(apiClient.get).mockImplementation(async (url: string) => {
      if (url === '/templates/categories') {
        return { items: [] };
      }
      if (url === '/workspaces/?page=1&pageSize=100') {
        return { items: [] };
      }
      return { items: [] };
    });
  });

  it('renders onboarding and skips normal data loading when repository is missing', async () => {
    vi.mocked(getRepositoryStatus).mockResolvedValue(notInitializedStatus);

    renderModule();

    expect(await screen.findByText('Set up Template Center registry')).toBeInTheDocument();
    expect(screen.queryByTestId('template-center-view')).not.toBeInTheDocument();
    expect(templateApi.listTemplates).not.toHaveBeenCalled();
    expect(apiClient.get).not.toHaveBeenCalledWith('/templates/categories');
    expect(apiClient.get).not.toHaveBeenCalledWith('/workspaces/?page=1&pageSize=100');
  });

  it('enables clone setup when clone is safe', async () => {
    const user = userEvent.setup();
    vi.mocked(getRepositoryStatus).mockResolvedValue(notInitializedStatus);
    vi.mocked(cloneRepository).mockResolvedValue({ success: true });

    renderModule();

    await user.type(await screen.findByLabelText('Repository URL'), 'git@example.com:registry.git');
    await user.type(screen.getByLabelText('Branch'), 'main');
    await user.click(screen.getByRole('button', { name: 'Clone registry' }));

    expect(cloneRepository).toHaveBeenCalledWith({
      url: 'git@example.com:registry.git',
      branch: 'main',
    });
  });

  it('shows clone-blocked guidance when local content prevents safe clone', async () => {
    vi.mocked(getRepositoryStatus).mockResolvedValue(blockedCloneStatus);

    renderModule();

    expect(await screen.findByText('Clone is unavailable')).toBeInTheDocument();
    expect(screen.getByText('Initialize the current registry instead.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clone registry' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Initialize registry' })).toBeEnabled();
  });

  it('loads normal routes after initialization refresh confirms Git repository', async () => {
    const user = userEvent.setup();
    vi.mocked(getRepositoryStatus)
      .mockResolvedValueOnce(notInitializedStatus)
      .mockResolvedValueOnce(initializedStatus);
    vi.mocked(initRepository).mockResolvedValue({ success: true, message: 'ok' });

    renderModule();

    await user.click(await screen.findByRole('button', { name: 'Initialize registry' }));

    expect(await screen.findByTestId('template-center-view')).toBeInTheDocument();
    expect(templateApi.listTemplates).toHaveBeenCalled();
    expect(apiClient.get).toHaveBeenCalledWith('/templates/categories');
    expect(apiClient.get).toHaveBeenCalledWith('/workspaces/?page=1&pageSize=100');
  });

  it('gates deep-linked template routes before onboarding', async () => {
    vi.mocked(getRepositoryStatus).mockResolvedValue(notInitializedStatus);

    renderModule('/templates/templates/template-1/edit');

    expect(await screen.findByText('Set up Template Center registry')).toBeInTheDocument();
    expect(screen.queryByTestId('template-editor-edit')).not.toBeInTheDocument();
  });

  it('falls back to the list when an initialized deep-link target is unavailable', async () => {
    vi.mocked(getRepositoryStatus).mockResolvedValue(initializedStatus);

    renderModule('/templates/templates/missing-template/edit');

    expect(await screen.findByTestId('template-center-view')).toBeInTheDocument();
    expect(screen.queryByTestId('template-editor-edit')).not.toBeInTheDocument();
  });

  it('allows initialized registries without origin to enter normal Template Center routes', async () => {
    vi.mocked(getRepositoryStatus).mockResolvedValue(initializedStatus);

    renderModule('/templates/templates/settings');

    expect(await screen.findByTestId('template-settings-view')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByTestId('template-center-view')).not.toBeInTheDocument());
  });
});
