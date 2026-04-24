import { render, screen, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { TemplateCenterSettingsView } from './TemplateCenterSettingsView';

const tMock = vi.hoisted(() => (key: string) => {
  const values: Record<string, string> = {
    'template.center.loading': 'Loading...',
    'template.center.settingsDialog.title': 'Template center settings',
    'template.center.settingsDialog.description': 'Settings description',
    'template.center.settingsDialog.actions.back': 'Back',
    'template.center.settings.tabs.versionControl': 'Version Control',
    'template.center.settings.tabs.remote': 'Remote',
    'template.center.settings.tabs.gitUser': 'Git User',
    'template.center.settings.tabs.sshKeys': 'SSH Keys',
  };
  return values[key] ?? key;
});

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

vi.mock('@/shared/services/templateGitApi', () => ({
  checkCloneStatus: vi.fn(async () => ({ success: true, data: { remote_url: 'git@example.com:repo.git' } })),
  getRepositoryStatus: vi.fn(async () => ({
    isGitRepo: true,
    currentBranch: 'main',
    remoteUrl: 'git@example.com:repo.git',
    hasOrigin: true,
    hasLocalContent: true,
    canCloneSafely: false,
    canInitSafely: false,
  })),
  getGitUserConfig: vi.fn(async () => ({ success: true, data: { userName: 'Owner', userEmail: 'owner@example.com' } })),
  initRepository: vi.fn(async () => ({ success: true })),
  setGitRemoteUrl: vi.fn(async () => ({ success: true })),
  updateGitUserConfig: vi.fn(async () => ({ success: true })),
  cloneRepository: vi.fn(async () => ({ success: true })),
}));

vi.mock('./components/TemplateRegistryVersionControlTab', () => ({
  TemplateRegistryVersionControlTab: () => <div data-testid="template-version-control-tab" />,
}));

vi.mock('./components/GitUserConfigTab', () => ({
  GitUserConfigTab: () => <div data-testid="template-remote-tab" />,
}));

vi.mock('./components/SSHKeysTab', () => ({
  SSHKeysTab: () => <div data-testid="template-ssh-keys-tab" />,
}));

describe('TemplateCenterSettingsView', () => {
  it('renders only current Git-centered settings sections', async () => {
    render(<TemplateCenterSettingsView />, {
      initialRoute: '/templates/templates/settings',
    });

    await waitFor(() => expect(screen.getByRole('tab', { name: 'Version Control' })).toBeInTheDocument());

    expect(screen.queryByRole('tab', { name: 'General' })).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Version Control' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Remote' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Git User' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'SSH Keys' })).toBeInTheDocument();
    expect(screen.getByTestId('template-version-control-tab')).toBeInTheDocument();
    expect(screen.queryByText('Registry metadata')).not.toBeInTheDocument();
    expect(screen.queryByText('Owner')).not.toBeInTheDocument();
  });
});
