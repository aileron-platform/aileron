import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsSyncStep } from './SettingsSyncStep';
import { apiClient } from '@/shared/api/apiClient';
import { WorkspaceSetupService } from '@/shared/services/workspaceSetupService';

vi.mock('@/app/providers/AppProvider', () => ({
  useApp: () => ({
    state: {
      user: {
        id: 'user-1',
        name: 'User',
        email: 'user@example.com',
        preferences: { theme: 'system', language: 'en' },
      },
    },
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

vi.mock('@/shared/services/workspaceSetupService', () => ({
  WorkspaceSetupService: {
    startInitialSync: vi.fn(),
    getStatus: vi.fn(),
  },
}));

const translations: Record<string, string> = {
  'workspace.wizard.steps.settingsSync.badge': 'Sync settings',
  'workspace.wizard.steps.settingsSync.title': 'Sync user settings',
  'workspace.wizard.steps.settingsSync.subtitle': 'Step {{current}}/{{total}}: Sync settings to the workspace',
  'workspace.wizard.steps.settingsSync.cardTitle': 'Sync settings to workspace',
  'workspace.wizard.steps.settingsSync.cardDescription': 'Copy settings into the workspace.',
  'workspace.wizard.steps.settingsSync.loading': 'Loading settings...',
  'workspace.wizard.steps.settingsSync.compactTitle': 'Settings and sync status',
  'workspace.wizard.steps.settingsSync.compactDescription': 'Workspace setup keeps these settings in sync.',
  'workspace.wizard.steps.settingsSync.syncStatus': 'Sync status',
  'workspace.wizard.steps.settingsSync.empty.title': 'No settings to sync',
  'workspace.wizard.steps.settingsSync.empty.description': 'You can configure settings later.',
  'workspace.wizard.steps.settingsSync.settings.configured': 'Configured',
  'workspace.wizard.steps.settingsSync.settings.notConfigured': 'Not configured',
  'workspace.wizard.steps.settingsSync.settings.ssh.title': 'SSH keys',
  'workspace.wizard.steps.settingsSync.settings.git.title': 'Git settings',
  'workspace.wizard.steps.settingsSync.settings.git.userName': 'Username: {{value}}',
  'workspace.wizard.steps.settingsSync.settings.git.userEmail': 'Email: {{value}}',
  'workspace.wizard.steps.settingsSync.notifications.successTitle': 'Sync completed',
  'workspace.wizard.steps.settingsSync.notifications.successDescription': 'All settings were synced.',
  'workspace.wizard.steps.settingsSync.notifications.partialDescription': 'Some settings failed.',
  'workspace.wizard.steps.settingsSync.notifications.failedDescription': 'The sync process failed.',
  'workspace.wizard.steps.settingsSync.status.pending': 'Waiting for sync result',
  'workspace.wizard.steps.settingsSync.status.preparing': 'Preparing to sync...',
  'workspace.wizard.steps.settingsSync.status.polling': 'Confirming sync results...',
  'workspace.wizard.steps.settingsSync.status.syncing': 'Syncing settings...',
  'workspace.wizard.steps.settingsSync.status.success': 'Sync completed',
  'workspace.wizard.steps.settingsSync.status.compactSuccessDescription': 'Settings are synced. You can finish the wizard.',
  'workspace.wizard.steps.settingsSync.status.compactRunningDescription': 'This runs in the background.',
  'workspace.wizard.steps.settingsSync.status.partial': 'Partially synced',
  'workspace.wizard.steps.settingsSync.status.failed': 'Sync failed',
  'workspace.wizard.steps.settingsSync.status.readyToSync': 'Ready to sync',
  'workspace.wizard.steps.settingsSync.status.idle': 'Click the button below to sync settings to the workspace.',
  'workspace.wizard.steps.settingsSync.actions.start': 'Start sync',
  'workspace.wizard.steps.settingsSync.actions.retry': 'Retry',
  'workspace.wizard.steps.settingsSync.actions.resync': 'Sync again',
  'workspace.wizard.buttons.previous': 'Previous',
  'workspace.wizard.buttons.finish': 'Finish',
};

const t = (key: string, params?: Record<string, string | number>) => {
  let value = translations[key] ?? key;
  Object.entries(params ?? {}).forEach(([paramKey, paramValue]) => {
    value = value.replace(`{{${paramKey}}}`, String(paramValue));
  });
  return value;
};

const defaultProps = {
  workspaceId: 'workspace-1',
  onPrevious: vi.fn(),
  onComplete: vi.fn(),
  isSubmitting: false,
  t,
};

describe('SettingsSyncStep', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows a compact empty state when there are no settings to sync', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: {} });

    render(<SettingsSyncStep {...defaultProps} />);

    expect(await screen.findByText('No settings to sync')).toBeInTheDocument();
    expect(screen.getByText('You can configure settings later.')).toBeInTheDocument();
    expect(WorkspaceSetupService.startInitialSync).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Finish' })).toBeEnabled();
  });

  it('shows compact success feedback after settings sync completes', async () => {
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        ssh: { privateKey: 'private-key', publicKey: 'public-key' },
        git: { userName: 'Aileron Dev', userEmail: 'dev@example.com' },
      },
    });
    vi.mocked(WorkspaceSetupService.startInitialSync).mockResolvedValue({
      workspaceId: 'workspace-1',
      completed: true,
      tasks: [
        { taskKey: 'ssh', taskName: 'ssh', status: 'success', message: 'SSH synced' },
        { taskKey: 'git', taskName: 'git', status: 'success', message: 'Git synced' },
      ],
    });

    render(<SettingsSyncStep {...defaultProps} />);

    expect(await screen.findByText('Settings and sync status')).toBeInTheDocument();
    expect(screen.getByText('SSH keys')).toBeInTheDocument();
    expect(screen.getByText('Git settings')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Settings are synced. You can finish the wizard.')).toBeInTheDocument();
    });

    expect(screen.getByText('SSH synced')).toBeInTheDocument();
    expect(screen.getByText('Git synced')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Finish' })).toBeEnabled();
  });
});
