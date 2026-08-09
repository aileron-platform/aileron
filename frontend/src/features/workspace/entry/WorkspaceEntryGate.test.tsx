import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { WorkspaceAvailabilityResponse } from '../api/workspaceLifecycleApi';
import { WorkspaceEntryGate } from './WorkspaceEntryGate';

const state = vi.hoisted(() => ({
  auth: {
    isAuthenticated: true,
    isLoading: false,
  },
  workspace: {
    canRead: true,
    canRunLifecycle: true,
    canDelete: false,
    isAuthorizationResolved: true,
    errorCode: null as string | null,
  },
  view: { kind: 'execution' as string },
  refresh: vi.fn(),
  runAction: vi.fn(),
  returnToWorkspaceList: vi.fn(),
  workspaceProviderMount: vi.fn(),
  deletion: {
    isDeleting: false,
    progress: null,
    requestDelete: vi.fn(),
  },
}));

vi.mock('@/features/auth/public', () => ({
  useAuth: () => state.auth,
}));

vi.mock('../providers/WorkspaceProvider', () => ({
  WorkspaceProvider: ({ children }: { children: React.ReactNode }) => {
    state.workspaceProviderMount();
    return <>{children}</>;
  },
}));

vi.mock('../hooks/useWorkspaceRuntime', () => ({
  useWorkspaceRuntime: () => ({
    workspaceId: 'ws-1',
    workspaceName: 'Workspace',
    runtimeBaseUrl: 'http://runtime.example',
    agenticTools: ['claude-code'],
    accessRole: state.workspace.canRead ? 'owner' : null,
    accessSource: null,
    accessSources: [],
    allowedOperations: [
      ...(state.workspace.canRead ? ['workspace.detail.read'] : []),
      ...(state.workspace.canRunLifecycle ? ['workspace.lifecycle.execute'] : []),
      ...(state.workspace.canDelete ? ['workspace.delete'] : []),
    ],
    runtimeStatus: null,
    isLoading: !state.workspace.isAuthorizationResolved,
    isAuthorizationResolved: state.workspace.isAuthorizationResolved,
    error: null,
    errorCode: state.workspace.errorCode,
    reload: vi.fn(),
    changeWorkspace: vi.fn(),
  }),
}));

vi.mock('../availability/useWorkspaceAvailabilityController', () => ({
  useWorkspaceAvailabilityController: () => ({
    view: state.view,
    refresh: state.refresh,
    runAction: state.runAction,
    returnToWorkspaceList: state.returnToWorkspaceList,
  }),
}));

vi.mock('../hooks/useWorkspaceDeletion', () => ({
  useWorkspaceDeletion: () => state.deletion,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const availabilityFixture = (
  overrides: Partial<WorkspaceAvailabilityResponse> = {},
): WorkspaceAvailabilityResponse => ({
  workspaceId: 'ws-1',
  availability: 'stopped',
  reasonCode: 'WORKSPACE_RUNTIME_STOPPED',
  runtimeStatus: 'stopped',
  runtimeInstanceId: 'runtime-1',
  runtimeAccessDesiredRevision: 1,
  runtimeAccessObservedRevision: 1,
  retryable: true,
  allowedActions: ['start', 'return'],
  retryAfterMs: null,
  knowledgeMountStatus: {
    status: 'ready',
    desiredRevision: 1,
    observedRevision: 1,
    lastKnownGoodRevision: 1,
    errorCode: null,
    compensating: false,
  },
  deletion: {
    availability: 'stopped',
    allowedActions: ['delete'],
    phase: null,
    status: null,
    errorCode: null,
  },
  ...overrides,
});

const renderGate = () => render(
  <MemoryRouter initialEntries={['/workspaces/ws-1/files']}>
    <WorkspaceEntryGate
      workspaceId="ws-1"
      navigationSlot={<header data-testid="navigation-slot" />}
    >
      <div data-testid="workspace-content" />
    </WorkspaceEntryGate>
  </MemoryRouter>,
);

describe('WorkspaceEntryGate', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  beforeEach(() => {
    state.auth.isAuthenticated = true;
    state.auth.isLoading = false;
    state.workspace.canRead = true;
    state.workspace.canRunLifecycle = true;
    state.workspace.canDelete = false;
    state.workspace.isAuthorizationResolved = true;
    state.workspace.errorCode = null;
    state.view = { kind: 'execution' };
    state.refresh.mockReset();
    state.runAction.mockReset();
    state.returnToWorkspaceList.mockReset();
    state.workspaceProviderMount.mockReset();
    state.deletion.requestDelete.mockReset();
    state.deletion.isDeleting = false;
    state.deletion.progress = null;
  });

  it('mounts Workspace content only after the availability controller is ready', () => {
    renderGate();

    expect(screen.getByTestId('workspace-content')).toBeInTheDocument();
    expect(screen.queryByTestId('entry-progress-panel')).not.toBeInTheDocument();
  });

  it('projects stopped Runtime and dispatches only API-allowed lifecycle actions', async () => {
    state.view = {
      kind: 'unavailable',
      availability: availabilityFixture(),
      loadError: null,
      actionErrorCode: null,
      isRefreshing: false,
      actionInFlight: null,
      canRunLifecycle: true,
    };

    renderGate();

    expect(await screen.findByRole('button', { name: 'common.entry.actions.start' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.entry.actions.return' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.actions.rebuild' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('workspace-content')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'common.entry.actions.start' }));
    expect(state.runAction).toHaveBeenCalledWith('start');
  });

  it('shows the owner-only delete dialog for a blocked existing workspace', async () => {
    state.workspace.canDelete = true;
    state.view = {
      kind: 'unavailable',
      availability: availabilityFixture({
        availability: 'blocked',
        reasonCode: 'WORKSPACE_RUNTIME_ERROR',
        allowedActions: ['retry', 'return'],
      }),
      loadError: null,
      actionErrorCode: null,
      isRefreshing: false,
      actionInFlight: null,
      canRunLifecycle: true,
    };

    renderGate();

    const deleteButton = await screen.findByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.trigger',
    });
    fireEvent.click(deleteButton);

    const confirmationInput = screen.getByRole('textbox');
    fireEvent.change(confirmationInput, { target: { value: 'Work' } });
    expect(screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.dialog.confirm',
    })).toBeDisabled();
    fireEvent.change(confirmationInput, { target: { value: 'Workspace' } });
    expect(screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.dialog.confirm',
    })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.dialog.confirm',
    }));
    expect(state.deletion.requestDelete).toHaveBeenCalledWith('Workspace');
  });

  it('fails closed on execution plane drift and offers only Workspace deletion', async () => {
    state.workspace.canDelete = true;
    state.view = {
      kind: 'unavailable',
      availability: availabilityFixture({
        availability: 'blocked',
        reasonCode: 'WORKSPACE_EXECUTION_PLANE_DRIFT' as WorkspaceAvailabilityResponse['reasonCode'],
        allowedActions: ['retry', 'rebuild', 'return'],
      }),
      loadError: null,
      actionErrorCode: null,
      isRefreshing: false,
      actionInFlight: null,
      canRunLifecycle: true,
    };

    renderGate();

    expect(await screen.findByText('common.entry.descriptions.executionPlaneDrift')).toBeInTheDocument();
    expect(screen.getByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.trigger',
    })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.actions.retry' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.actions.rebuild' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.actions.return' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('workspace-content')).not.toBeInTheDocument();
    expect(state.workspaceProviderMount).not.toHaveBeenCalled();
  });

  it('fails closed on execution plane drift and directs non-deleters to an owner or administrator', async () => {
    state.view = {
      kind: 'unavailable',
      availability: availabilityFixture({
        availability: 'blocked',
        reasonCode: 'WORKSPACE_EXECUTION_PLANE_DRIFT' as WorkspaceAvailabilityResponse['reasonCode'],
        allowedActions: ['retry', 'rebuild', 'return'],
      }),
      loadError: null,
      actionErrorCode: null,
      isRefreshing: false,
      actionInFlight: null,
      canRunLifecycle: true,
    };

    renderGate();

    expect(await screen.findByText('common.entry.executionPlaneDrift.contactOwner')).toBeInTheDocument();
    expect(screen.queryByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.trigger',
    })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.actions.retry' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.actions.rebuild' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.actions.return' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('workspace-content')).not.toBeInTheDocument();
    expect(state.workspaceProviderMount).not.toHaveBeenCalled();
  });

  it('shows deletion progress and disables API mutation actions while the workspace is deleting', async () => {
    state.workspace.canDelete = true;
    state.view = {
      kind: 'unavailable',
      availability: availabilityFixture({
        availability: 'deleting',
        reasonCode: 'WORKSPACE_DELETING',
        allowedActions: ['start', 'return'],
        deletion: {
          availability: 'deleting',
          allowedActions: [],
          phase: 'stopping_runtime',
          status: 'running',
          errorCode: null,
        },
      }),
      loadError: null,
      actionErrorCode: null,
      isRefreshing: false,
      actionInFlight: null,
      canRunLifecycle: true,
    };
    state.deletion.isDeleting = true;
    state.deletion.progress = {
      jobId: 'job-delete-1',
      status: 'running',
      phase: 'stopping_runtime',
      errorCode: null,
    };

    renderGate();

    expect(await screen.findByTestId('workspace-deletion-progress')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'common.entry.actions.start' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'common.entry.actions.return' })).toBeEnabled();
    expect(screen.queryByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.trigger',
    })).not.toBeInTheDocument();
  });

  it('does not mount a deletion mutation for a missing workspace', async () => {
    state.workspace.canDelete = true;
    state.view = {
      kind: 'unavailable',
      availability: availabilityFixture({
        availability: 'not_found',
        reasonCode: 'WORKSPACE_NOT_FOUND',
        allowedActions: ['return'],
      }),
      loadError: null,
      actionErrorCode: null,
      isRefreshing: false,
      actionInFlight: null,
      canRunLifecycle: true,
    };

    renderGate();

    expect(await screen.findByRole('button', { name: 'common.entry.actions.return' })).toBeInTheDocument();
    expect(screen.queryByTestId('workspace-deletion-action')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {
      name: 'workspace.workspaceSettings.reset.delete.trigger',
    })).not.toBeInTheDocument();
    expect(state.deletion.requestDelete).not.toHaveBeenCalled();
  });

  it('requires confirmation before dispatching a rebuild action', async () => {
    state.view = {
      kind: 'unavailable',
      availability: availabilityFixture({ allowedActions: ['rebuild', 'return'] }),
      loadError: null,
      actionErrorCode: null,
      isRefreshing: false,
      actionInFlight: null,
      canRunLifecycle: true,
    };
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);

    renderGate();

    fireEvent.click(await screen.findByRole('button', { name: 'common.entry.actions.rebuild' }));
    expect(confirm).toHaveBeenCalledWith('common.entry.confirmRebuild');
    expect(state.runAction).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: 'common.entry.actions.rebuild' }));
    expect(state.runAction).toHaveBeenCalledWith('rebuild');
    confirm.mockRestore();
  });

  it('uses local refresh when availability evidence is uncertain', async () => {
    state.view = {
      kind: 'unavailable',
      availability: null,
      loadError: new Error('network details must not reach the UI'),
      actionErrorCode: null,
      isRefreshing: false,
      actionInFlight: null,
      canRunLifecycle: true,
    };

    renderGate();

    expect(await screen.findByRole('button', { name: 'common.entry.actions.refresh' })).toBeInTheDocument();
    expect(screen.getByText('WORKSPACE_AVAILABILITY_UNCERTAIN')).toBeInTheDocument();
    expect(screen.queryByText('network details must not reach the UI')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'common.entry.actions.return' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'common.entry.actions.refresh' }));
    expect(state.refresh).toHaveBeenCalledTimes(1);
  });

  it('fails closed on revoked Workspace access and does not mount content', async () => {
    state.workspace.canRead = false;
    state.view = { kind: 'authorization-denied' };

    renderGate();

    expect(await screen.findByText('WORKSPACE_ACCESS_DENIED')).toBeInTheDocument();
    expect(screen.queryByTestId('workspace-content')).not.toBeInTheDocument();
  });
});
