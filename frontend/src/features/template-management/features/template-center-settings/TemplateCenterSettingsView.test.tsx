import { render, screen, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { TemplateCenterSettingsView } from './TemplateCenterSettingsView';

const tMock = vi.hoisted(() => (key: string) => {
  const values: Record<string, string> = {
    'template.center.loading': 'Loading...',
    'template.center.settingsDialog.title': 'Template center settings',
    'template.center.settingsDialog.description': 'Settings description',
    'template.center.settingsDialog.actions.back': 'Back',
    'template.center.settingsDialog.actions.save': 'Save',
    'template.center.settings.tabs.general': 'General',
    'template.center.settings.tabs.versionControl': 'Version Control',
    'template.center.settings.tabs.remote': 'Remote',
    'template.center.settings.tabs.sshKeys': 'SSH Keys',
    'template.center.settingsDialog.basicInfo.title': 'Registry metadata',
    'template.center.settingsDialog.basicInfo.nameLabel': 'Name',
    'template.center.settingsDialog.basicInfo.versionLabel': 'Version',
    'template.center.settingsDialog.basicInfo.descriptionLabel': 'Description',
    'template.center.settingsDialog.basicInfo.descriptionPlaceholder': 'Description placeholder',
    'template.center.settingsDialog.basicInfo.homepageLabel': 'Homepage',
    'template.center.settingsDialog.basicInfo.homepagePlaceholder': 'Homepage placeholder',
    'template.center.settingsDialog.owner.title': 'Owner',
    'template.center.settingsDialog.owner.nameLabel': 'Owner name',
    'template.center.settingsDialog.owner.emailLabel': 'Owner email',
  };
  return values[key] ?? key;
});

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(async (path: string) => {
      if (path === '/templates/marketplace/config') {
        return {
          success: true,
          data: {
            name: 'registry',
            owner: { name: 'Owner', email: 'owner@example.com' },
            metadata: { description: 'Registry description', version: '1.0.0', homepage: 'https://example.com' },
          },
        };
      }
      return { success: true };
    }),
    put: vi.fn(async () => ({ success: true })),
  },
}));

vi.mock('@/shared/services/templateGitApi', () => ({
  checkCloneStatus: vi.fn(async () => ({ success: true, data: { remote_url: 'git@example.com:repo.git' } })),
  getGitUserConfig: vi.fn(async () => ({ success: true, data: { userName: 'Owner', userEmail: 'owner@example.com' } })),
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
  it('renders the settings route sections with the new responsibility labels', async () => {
    render(<TemplateCenterSettingsView />, {
      initialRoute: '/templates/templates/settings',
    });

    await waitFor(() => expect(screen.getByRole('tab', { name: 'General' })).toBeInTheDocument());

    expect(screen.getByRole('tab', { name: 'Version Control' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Remote' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'SSH Keys' })).toBeInTheDocument();
    expect(screen.getByText('Registry metadata')).toBeInTheDocument();
    expect(screen.getByText('Owner')).toBeInTheDocument();
  });
});
