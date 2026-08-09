import { render, screen, fireEvent } from '@/__tests__/utils/render';
import { describe, expect, it, vi } from 'vitest';
import { MCPServerCard } from './MCPServerCard';

const labels = {
  enabled: 'Enabled',
  disabled: 'Disabled',
  transportType: 'Transport',
  serverUrl: 'URL',
  headers: 'Headers',
  command: 'Command',
  commandArgs: 'Arguments',
  env: 'Environment',
  showEnvValues: 'Show values',
  hideEnvValues: 'Hide values',
  edit: 'Edit server',
  delete: 'Delete server',
  readOnlyTooltip: 'Read-only',
};

describe('MCPServerCard', () => {
  it('renders stdio server details and masks environment values', () => {
    render(
      <MCPServerCard
        server={{
          id: 'project:filesystem',
          name: 'filesystem',
          scope: 'project',
          transport: 'stdio',
          command: 'npx',
          args: ['-y', '@modelcontextprotocol/server-filesystem'],
          env: { TOKEN: 'secret' },
        }}
        scopeBadge={<span>Project</span>}
        labels={labels}
      />,
    );

    expect(screen.getByText('filesystem')).toBeInTheDocument();
    expect(screen.getByText('STDIO')).toBeInTheDocument();
    expect(screen.getByText('npx')).toBeInTheDocument();
    expect(screen.getByText('-y @modelcontextprotocol/server-filesystem')).toBeInTheDocument();
    expect(screen.getByText('***')).toBeInTheDocument();
    expect(screen.queryByText('secret')).not.toBeInTheDocument();
  });

  it('delegates edit, delete, toggle, and env visibility actions', () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    const onToggleStatus = vi.fn();
    const onToggleEnvVisibility = vi.fn();
    const server = {
      id: 'project:filesystem',
      name: 'filesystem',
      scope: 'project',
      transport: 'stdio' as const,
      command: 'npx',
      env: { TOKEN: 'secret' },
    };

    render(
      <MCPServerCard
        server={server}
        scopeBadge={<span>Project</span>}
        labels={labels}
        onEdit={onEdit}
        onDelete={onDelete}
        onToggleStatus={onToggleStatus}
        onToggleEnvVisibility={onToggleEnvVisibility}
      />,
    );

    fireEvent.click(screen.getByTitle('Show values'));
    expect(onToggleEnvVisibility).toHaveBeenCalledWith(server);

    fireEvent.click(screen.getByRole('switch'));
    expect(onToggleStatus).toHaveBeenCalledWith(server, false);

    fireEvent.click(screen.getByRole('button', { name: 'Edit server' }));
    expect(onEdit).toHaveBeenCalledWith(server);

    fireEvent.click(screen.getByRole('button', { name: 'Delete server' }));
    expect(onDelete).toHaveBeenCalledWith(server);
  });
});
