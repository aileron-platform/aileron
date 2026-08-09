import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WorkspaceCreationStep from './WorkspaceCreationStep';
import { workspaceWizardService } from '../../services/workspaceWizardService';
import { apiClient } from '@/shared/api/apiClient';

vi.mock('../../services/workspaceWizardService', () => ({
  workspaceWizardService: {
    getRuntimeLogs: vi.fn(),
  },
}));

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const translations: Record<string, string> = {
  'workspace.wizard.steps.workspaceCreation.title': 'Provisioning workspace',
  'workspace.wizard.steps.workspaceCreation.subtitle': 'Step {{current}}/{{total}}: Building runtime environment',
  'workspace.wizard.steps.workspaceCreation.cardTitle': 'Workspace status',
  'workspace.wizard.steps.workspaceCreation.cardDescription': 'Preparing services',
  'workspace.wizard.steps.workspaceCreation.progress.label': 'Workspace creation progress',
  'workspace.wizard.steps.workspaceCreation.progress.percent': '{{value}}%',
  'workspace.wizard.steps.workspaceCreation.progress.provisioningTitle': 'Creating workspace infrastructure',
  'workspace.wizard.steps.workspaceCreation.progress.provisioningDescription': 'Containers are being prepared.',
  'workspace.wizard.steps.workspaceCreation.progress.healthTitle': 'Verifying runtime health',
  'workspace.wizard.steps.workspaceCreation.progress.healthDescription': 'The runtime service is starting.',
  'workspace.wizard.steps.workspaceCreation.progress.readyTitle': 'Workspace runtime is ready',
  'workspace.wizard.steps.workspaceCreation.progress.readyDescription': 'All services are healthy.',
  'workspace.wizard.steps.workspaceCreation.progress.failedTitle': 'Workspace creation needs attention',
  'workspace.wizard.steps.workspaceCreation.progress.failedDescription': 'Review the error and logs.',
  'workspace.wizard.steps.workspaceCreation.infrastructure.title': 'Container provisioning',
  'workspace.wizard.steps.workspaceCreation.infrastructure.pending': 'Creating containers...',
  'workspace.wizard.steps.workspaceCreation.infrastructure.failed': 'Provisioning failed',
  'workspace.wizard.steps.workspaceCreation.infrastructure.success': 'Containers are ready',
  'workspace.wizard.steps.workspaceCreation.health.title': 'Service health check',
  'workspace.wizard.steps.workspaceCreation.health.pending': 'Checking service availability...',
  'workspace.wizard.steps.workspaceCreation.health.success': 'Service is healthy',
  'workspace.wizard.steps.workspaceCreation.health.waiting': 'Waiting for containers to start',
  'workspace.wizard.steps.workspaceCreation.health.retrying': 'Service is starting up. Please wait...',
  'workspace.wizard.steps.workspaceCreation.workspaceId.label': 'Workspace ID',
  'workspace.wizard.steps.workspaceCreation.workspaceId.copyTitle': 'Copy full workspace ID',
  'workspace.wizard.steps.workspaceCreation.logs.open': 'Logs ({{count}})',
  'workspace.wizard.steps.workspaceCreation.logs.dialogTitle': 'Provisioning log details',
  'workspace.wizard.steps.workspaceCreation.logs.dialogDescription': 'Runtime events collected while creating the workspace.',
  'workspace.wizard.steps.workspaceCreation.logs.empty': 'No logs yet',
  'workspace.wizard.steps.workspaceCreation.logs.loading': 'Loading logs...',
  'workspace.wizard.buttons.previous': 'Previous',
  'workspace.wizard.buttons.retry': 'Retry',
  'workspace.wizard.buttons.next': 'Next',
  'workspace.wizard.buttons.finish': 'Finish setup',
  'workspace.wizard.error.provisionWorkspace': 'Workspace provisioning failed.',
  'common.messages.waitingComplete': 'Waiting for completion',
};

const t = (key: string, params?: Record<string, string | number>) => {
  let value = translations[key] ?? key;
  Object.entries(params ?? {}).forEach(([paramKey, paramValue]) => {
    value = value.replace(`{{${paramKey}}}`, String(paramValue));
  });
  return value;
};

const defaultProps = {
  workspaceId: 'workspace-1234567890',
  isPolling: true,
  errorKey: null,
  onPrevious: vi.fn(),
  onRetry: vi.fn(),
  onComplete: vi.fn(),
  t,
};

describe('WorkspaceCreationStep', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(workspaceWizardService.getRuntimeLogs).mockResolvedValue([]);
    vi.mocked(apiClient.get).mockResolvedValue({
      runtimeStatus: {
        runtimeUrl: '/workspaces/workspace-1234567890/runtime',
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('is the final wizard step and completes without a settings sync gate', () => {
    render(<WorkspaceCreationStep {...defaultProps} workspaceId={null} />);

    expect(screen.getByText('Step 3/3: Building runtime environment')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Waiting for completion' })).toBeDisabled();
  });

  it('shows provisioning as progress while containers are being created', () => {
    render(<WorkspaceCreationStep {...defaultProps} workspaceId={null} />);

    expect(screen.getByText('Creating workspace infrastructure')).toBeInTheDocument();
    expect(screen.getByText('35%')).toBeInTheDocument();
    expect(screen.getByText('Creating containers...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Waiting for completion' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Retry' })).toBeDisabled();
  });

  it('enables retry only after provisioning reaches a terminal error', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    render(
      <WorkspaceCreationStep
        {...defaultProps}
        isPolling={false}
        errorKey="error.provisionWorkspace"
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText('Workspace provisioning failed.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('keeps health check visible as the active long-running phase', async () => {
    render(<WorkspaceCreationStep {...defaultProps} isPolling={false} />);

    expect(screen.getByText('Verifying runtime health')).toBeInTheDocument();
    expect(screen.getByText('72%')).toBeInTheDocument();
    expect(screen.getByText('Checking service availability...')).toBeInTheDocument();

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith('/workspaces/workspace-1234567890');
    });
    expect(fetch).toHaveBeenCalledWith(
      '/workspaces/workspace-1234567890/runtime/health',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('opens runtime logs in a dialog from the logs control', async () => {
    const user = userEvent.setup();
    vi.mocked(workspaceWizardService.getRuntimeLogs).mockResolvedValue([
      {
        id: 'log-1',
        workspaceId: 'workspace-1234567890',
        stage: 'health_check',
        message: 'Runtime health endpoint is not ready yet',
        metadata: {},
        createdAt: '2026-04-30T00:00:00.000Z',
      },
    ]);

    render(<WorkspaceCreationStep {...defaultProps} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Logs \(1\)/ })).toBeInTheDocument();
    });

    expect(screen.queryByText('Runtime health endpoint is not ready yet')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Logs \(1\)/ }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Provisioning log details')).toBeInTheDocument();
    expect(screen.getByText('Runtime health endpoint is not ready yet')).toBeInTheDocument();
    expect(screen.getByText('health_check')).toBeInTheDocument();
  });
});
