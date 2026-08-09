import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { WorkspaceRuntimeErrorPage } from './WorkspaceRuntimeErrorPage';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'common.error.workspaceRuntime.title': 'Workspace Connection Failed',
        'common.error.workspaceRuntime.connectionFailed': 'Workspace is not started or unable to connect',
        'common.error.workspaceRuntime.noWorkspace': 'No Workspace Created',
        'common.error.workspaceRuntime.noWorkspaceErrorMessage': 'No workspace has been created yet',
        'common.error.workspaceRuntime.invalidWorkspaceErrorMessage': 'No valid workspace was found',
        'common.error.workspaceRuntime.noWorkspaceHint': 'Please create a workspace to get started',
        'common.error.workspaceRuntime.createWorkspace': 'Create New Workspace',
        'common.error.workspaceRuntime.troubleshoot': 'Check service status',
        'common.refresh': 'Refresh',
        'common.reconnect': 'Reconnect',
        'common.reconnecting': 'Reconnecting...',
      };
      return translations[key] ?? key;
    },
  }),
}));

describe('WorkspaceRuntimeErrorPage', () => {
  it('shows create workspace action when no-workspace error is passed as an i18n key', () => {
    render(
      <WorkspaceRuntimeErrorPage
        error="common.error.workspaceRuntime.noWorkspaceErrorMessage"
        onCreateWorkspace={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('No workspace has been created yet')).toBeInTheDocument();
    expect(screen.getByText('No Workspace Created')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create New Workspace' })).toBeInTheDocument();
  });

  it('shows create workspace action for no-workspace runtime errors', () => {
    render(
      <WorkspaceRuntimeErrorPage
        error="No workspace has been created yet"
        onCreateWorkspace={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('No Workspace Created')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create New Workspace' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument();
  });

});
