import { render, screen } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { RuntimeErrorPage } from './RuntimeErrorPage';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'common.error.workspaceRuntime.title': 'Workspace Connection Failed',
        'common.error.workspaceRuntime.connectionFailed': 'Workspace is not started or unable to connect',
        'common.error.workspaceRuntime.noWorkspace': 'No Workspace Created',
        'common.error.workspaceRuntime.noWorkspaceErrorMessage': '尚未建立任何工作區',
        'common.error.workspaceRuntime.invalidWorkspaceErrorMessage': '找不到有效的工作區',
        'common.error.workspaceRuntime.noWorkspaceHint': 'Please create a workspace to get started',
        'common.error.workspaceRuntime.createWorkspace': 'Create New Workspace',
        'common.error.workspaceRuntime.deleteWorkspace': 'Delete Workspace',
        'common.error.workspaceRuntime.troubleshoot': 'Check service status',
        'common.refresh': 'Refresh',
        'common.reconnect': 'Reconnect',
        'common.reconnecting': 'Reconnecting...',
      };
      return translations[key] ?? key;
    },
  }),
}));

describe('RuntimeErrorPage', () => {
  it('shows create workspace action for no-workspace runtime errors', () => {
    render(
      <RuntimeErrorPage
        error="尚未建立任何工作區"
        onCreateWorkspace={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText('No Workspace Created')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create New Workspace' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument();
  });

  it('shows reconnect and delete actions for existing workspace runtime errors', () => {
    render(
      <RuntimeErrorPage
        error="runtime unavailable"
        workspaceId="ws-1"
        onRetry={vi.fn()}
        onDeleteWorkspace={vi.fn()}
      />,
    );

    expect(screen.getByText('Workspace Connection Failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reconnect' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete Workspace' })).toBeInTheDocument();
  });
});
