import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { WorkspaceMCPServerDialog, type WorkspaceMCPServerData } from './WorkspaceMCPServerDialog';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, options?: Record<string, string | number>) => {
      const map: Record<string, string> = {
        'common.cancel': 'Cancel',
        'workspace.agentSettings.common.mcp.dialogs.server.title.create': 'Add MCP Server',
        'workspace.agentSettings.common.mcp.dialogs.server.title.edit': 'Edit MCP Server',
        'workspace.agentSettings.common.mcp.dialogs.server.description': 'Configure MCP server connection settings.',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.name.label': 'Server name',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.name.placeholder': 'filesystem',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.name.hint': 'Name hint',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.scope.label': 'Scope',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.scope.options.project.title': 'Project',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.scope.options.project.description': 'Project scope',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.scope.options.user.title': 'User',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.scope.options.user.description': 'User scope',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.scope.options.local.title': 'Local',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.scope.options.local.description': 'Local scope',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.transport.label': 'Transport',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.transport.options.stdio.title': 'Stdio',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.transport.options.stdio.description': 'stdio',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.transport.options.http.title': 'HTTP',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.transport.options.http.description': 'http',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.transport.options.sse.title': 'SSE',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.transport.options.sse.description': 'sse',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.command.label': 'Command',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.command.placeholder': 'npx',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.commandArgs.label': 'Arguments',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.commandArgs.add': 'Add argument',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.commandArgs.empty': 'No arguments',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.env.label': 'Environment',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.env.add': 'Add variable',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.env.keyPlaceholder': 'Variable name',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.env.valuePlaceholder': 'Variable value',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.env.empty': 'No environment',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.headers.label': 'Headers',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.headers.add': 'Add header',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.headers.keyPlaceholder': 'Header name',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.headers.valuePlaceholder': 'Header value',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.headers.empty': 'No headers',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.url.label': 'Server URL',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.url.placeholder.http': 'https://api.example.com/mcp',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.url.placeholder.sse': 'https://api.example.com/sse',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.url.hint.http': 'HTTP URL',
        'workspace.agentSettings.common.mcp.dialogs.server.fields.url.hint.sse': 'SSE URL',
        'workspace.agentSettings.common.mcp.dialogs.server.actions.create': 'Create server',
        'workspace.agentSettings.common.mcp.dialogs.server.actions.save': 'Save changes',
        'workspace.agentSettings.common.mcp.dialogs.server.errors.nameRequired': 'Name is required.',
        'workspace.agentSettings.common.mcp.dialogs.server.errors.commandRequired': 'Command is required.',
        'workspace.agentSettings.common.mcp.dialogs.server.errors.urlRequired': 'URL is required.',
        'workspace.agentSettings.common.mcp.dialogs.server.errors.saveFailed': 'Save failed',
      };

      if (key.endsWith('.placeholder') && options?.index) {
        return `Argument ${options.index}`;
      }

      return map[key] ?? key;
    },
  }),
}));

const renderDialog = (
  server: WorkspaceMCPServerData | null,
  mode: 'create' | 'edit' = 'create',
  onSubmit = vi.fn().mockResolvedValue(undefined),
  onClose = vi.fn(),
) => {
  render(
    <WorkspaceMCPServerDialog
      open
      mode={mode}
      server={server}
      onClose={onClose}
      onSubmit={onSubmit}
    />,
  );
  return { onClose, onSubmit };
};

describe('WorkspaceMCPServerDialog', () => {
  it('keeps environment input focus while editing an existing row', async () => {
    const user = userEvent.setup();

    renderDialog({
      id: 'project:test-server',
      name: 'test-server',
      scope: 'project',
      transport: 'stdio',
      command: 'npx',
      env: {
        FOO: 'bar',
      },
    }, 'edit');

    const envKeyInput = screen.getByDisplayValue('FOO');

    await user.click(envKeyInput);
    await user.type(envKeyInput, 'BAR');

    expect(envKeyInput).toHaveValue('FOOBAR');
    expect(document.activeElement).toBe(envKeyInput);
  });

  it('submits the workspace payload without template fields', async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderDialog(null);

    await user.type(screen.getByPlaceholderText('filesystem'), 'filesystem');
    await user.type(screen.getByPlaceholderText('npx'), ' npx ');
    await user.click(screen.getByRole('button', { name: 'Add argument' }));
    await user.type(screen.getByPlaceholderText('Argument 1'), ' --stdio ');
    await user.click(screen.getByRole('button', { name: 'Add variable' }));
    await user.type(screen.getByPlaceholderText('Variable name'), 'TOKEN');
    await user.type(screen.getByPlaceholderText('Variable value'), 'abc');
    await user.click(screen.getByRole('button', { name: 'Create server' }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        id: 'project:filesystem',
        name: 'filesystem',
        scope: 'project',
        transport: 'stdio',
        command: 'npx',
        args: ['--stdio'],
        env: { TOKEN: 'abc' },
        headers: undefined,
      });
    });
  });

  it('shows command validation and keeps the workspace payload unsent', async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderDialog(null);

    await user.type(screen.getByPlaceholderText('filesystem'), 'filesystem');
    await user.click(screen.getByRole('button', { name: 'Create server' }));

    expect(screen.getByText('Command is required.')).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('calls the workspace close handler from cancel', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    renderDialog(null, 'create', vi.fn().mockResolvedValue(undefined), onClose);

    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(onClose).toHaveBeenCalled();
  });
});
