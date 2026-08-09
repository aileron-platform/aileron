import { beforeEach, describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@/__tests__/utils/render';
import { render } from '@/__tests__/utils/render';
import { WorkspaceResetSettings } from './WorkspaceResetSettings';

const {
  getMock,
  stopWorkspaceMock,
  deleteWorkspaceMock,
  waitForWorkspaceDeletionMock,
  toastMock,
  reloadMock,
  resolveDeleteFallbackMock,
  workspacePermissions,
} = vi.hoisted(() => ({
  getMock: vi.fn(),
  stopWorkspaceMock: vi.fn(),
  deleteWorkspaceMock: vi.fn(),
  waitForWorkspaceDeletionMock: vi.fn(),
  toastMock: vi.fn(),
  reloadMock: vi.fn(),
  resolveDeleteFallbackMock: vi.fn(),
  workspacePermissions: {
    canDelete: true,
    canRunLifecycle: true,
  },
}));

const tMock = (key: string, options?: Record<string, unknown>) => {
  const translations: Record<string, string> = {
    'workspace.workspaceSettings.reset.header.title': 'Workspace reset',
    'workspace.workspaceSettings.reset.danger.title': 'Danger zone',
    'workspace.workspaceSettings.reset.danger.description': 'Dangerous actions',
    'workspace.workspaceSettings.reset.lifecycle.title': 'Lifecycle actions',
    'workspace.workspaceSettings.reset.lifecycle.description': 'Manage lifecycle',
    'workspace.workspaceSettings.reset.lifecycle.phases.running': 'Running',
    'workspace.workspaceSettings.reset.lifecycle.phases.stopped': 'Stopped',
    'workspace.workspaceSettings.reset.lifecycle.phases.stopping': 'Stopping',
    'workspace.workspaceSettings.reset.lifecycle.phases.unknown': 'Unknown',
    'workspace.workspaceSettings.reset.lifecycle.actions.workspace.title': 'Stop workspace',
    'workspace.workspaceSettings.reset.lifecycle.actions.workspace.description': 'Stop resources',
    'workspace.workspaceSettings.reset.lifecycle.actions.workspace.label': 'Stop workspace',
    'workspace.workspaceSettings.reset.lifecycle.actions.workspace.loading': 'Stopping workspace...',
    'workspace.workspaceSettings.reset.lifecycle.actions.workspace.successTitle': 'Workspace stop started',
    'workspace.workspaceSettings.reset.lifecycle.actions.workspace.successDescription': 'Stop submitted',
    'workspace.workspaceSettings.reset.lifecycle.actions.workspace.errorTitle': 'Workspace stop failed',
    'workspace.workspaceSettings.reset.lifecycle.actions.workspace.errorDescription': 'Stop failed',
    'workspace.workspaceSettings.reset.lifecycle.actions.runtime.title': 'Restart runtime',
    'workspace.workspaceSettings.reset.lifecycle.actions.runtime.description': 'Restart runtime',
    'workspace.workspaceSettings.reset.lifecycle.actions.runtime.label': 'Restart runtime',
    'workspace.workspaceSettings.reset.lifecycle.actions.runtime.loading': 'Restarting runtime...',
    'workspace.workspaceSettings.reset.lifecycle.actions.browser.title': 'Restart browser',
    'workspace.workspaceSettings.reset.lifecycle.actions.browser.description': 'Restart browser',
    'workspace.workspaceSettings.reset.lifecycle.actions.browser.label': 'Restart browser',
    'workspace.workspaceSettings.reset.lifecycle.actions.browser.loading': 'Restarting browser...',
    'workspace.workspaceSettings.reset.lifecycle.actions.canvas.title': 'Restart Canvas',
    'workspace.workspaceSettings.reset.lifecycle.actions.canvas.description': 'Restart Canvas',
    'workspace.workspaceSettings.reset.lifecycle.actions.canvas.label': 'Restart Canvas',
    'workspace.workspaceSettings.reset.lifecycle.actions.canvas.loading': 'Restarting Canvas...',
    'workspace.workspaceSettings.reset.lifecycle.operationState.submitted': 'Submitted',
    'workspace.workspaceSettings.reset.lifecycle.operationState.processing': 'In progress',
    'workspace.workspaceSettings.reset.lifecycle.operationState.completed': 'Completed',
    'workspace.workspaceSettings.reset.lifecycle.operationState.description': `Current operation state: ${String(options?.phase ?? '')}`,
    'workspace.workspaceSettings.reset.delete.title': 'Delete workspace',
    'workspace.workspaceSettings.reset.delete.description': 'Delete workspace',
    'workspace.workspaceSettings.reset.delete.trigger': 'Delete workspace',
  };
  return translations[key] ?? key;
};

vi.mock('@/shared/api/apiClient', () => ({
  apiClient: {
    get: getMock,
  },
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: tMock }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      workspaceId: 'ws-123',
      runtimeBaseUrl: 'http://runtime.example.test',
      reload: reloadMock,
    },
    permissions: workspacePermissions,
  }),
}));

vi.mock('@/features/workspace/hooks/useWorkspaceDeleteFallback', () => ({
  useWorkspaceDeleteFallback: () => resolveDeleteFallbackMock,
}));

vi.mock('../../../api/workspaceLifecycleApi', () => ({
  WORKSPACE_DELETION_PHASES: [
    'queued',
    'cancelling_automations',
    'stopping_runtime',
    'deleting_resources',
    'finalizing',
  ],
  workspaceLifecycleApi: {
    stopWorkspace: stopWorkspaceMock,
    restartComponent: vi.fn(),
    deleteWorkspace: deleteWorkspaceMock,
    waitForWorkspaceDeletion: waitForWorkspaceDeletionMock,
  },
}));

describe('WorkspaceResetSettings', () => {
  beforeEach(() => {
    getMock.mockReset();
    stopWorkspaceMock.mockReset();
    deleteWorkspaceMock.mockReset();
    waitForWorkspaceDeletionMock.mockReset();
    toastMock.mockReset();
    reloadMock.mockReset();
    resolveDeleteFallbackMock.mockReset();
    workspacePermissions.canDelete = true;
    workspacePermissions.canRunLifecycle = true;
    getMock.mockResolvedValue({
      id: 'ws-123',
      name: 'Test workspace',
      overallPhase: 'Running',
      runtimeStatus: { status: 'running' },
      components: {
        runtime: { phase: 'Running' },
        browser: { phase: 'Running' },
        canvas: { phase: 'Running' },
      },
    });
    stopWorkspaceMock.mockResolvedValue({
      workspaceId: 'ws-123',
      status: 'stopping',
      jobId: 'job-stop-1',
      correlationId: 'correlation-1',
      rootCorrelationId: 'correlation-1',
    });
    deleteWorkspaceMock.mockResolvedValue({
      workspaceId: 'ws-123',
      status: 'deleting',
      jobId: 'job-delete-1',
      correlationId: 'correlation-delete-1',
      rootCorrelationId: 'correlation-delete-1',
    });
    waitForWorkspaceDeletionMock.mockResolvedValue(undefined);
  });

  it('exposes the workspace stop action and submits the lifecycle command', async () => {
    const user = userEvent.setup();

    render(<WorkspaceResetSettings />);

    const stopButton = await screen.findByRole('button', { name: 'Stop workspace' });
    expect(stopButton).toBeEnabled();

    await user.click(stopButton);

    await waitFor(() => {
      expect(stopWorkspaceMock).toHaveBeenCalledWith('ws-123');
    });
    expect(toastMock).toHaveBeenCalledWith({
      title: 'Workspace stop started',
      description: 'Stop submitted',
      variant: 'default',
    });
  });

  it('uses the shared full-name confirmation dialog for the ready Settings entry', async () => {
    const user = userEvent.setup();

    render(<WorkspaceResetSettings />);

    await user.click(await screen.findByRole('button', {
      name: 'Delete workspace',
    }));

    const confirmationInput = screen.getByRole('textbox');
    const confirmButton = screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.dialog.confirm',
    });
    await user.type(confirmationInput, 'Test');
    expect(confirmButton).toBeDisabled();

    await user.type(confirmationInput, ' workspace');
    expect(confirmButton).toBeEnabled();
    await user.click(confirmButton);

    await waitFor(() => {
      expect(deleteWorkspaceMock).toHaveBeenCalledWith('ws-123', 'Test workspace');
    });
  });
});
