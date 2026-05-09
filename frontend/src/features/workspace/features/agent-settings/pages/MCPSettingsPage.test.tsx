import React from 'react';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MCPSettingsPage from './MCPSettingsPage';

const apiMock = {
  listMcpServers: vi.fn(),
  listCodexPlugins: vi.fn(),
  createMcpServer: vi.fn(),
  updateMcpServer: vi.fn(),
  deleteMcpServer: vi.fn(),
  toggleMcpServerStatus: vi.fn(),
  importMcpServers: vi.fn(),
};

const tMock = (key: string, values?: Record<string, unknown>) => (
  values?.count !== undefined ? `${key}:${values.count}` : key
);
const toastMock = vi.fn();

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
      error: null,
      isLoading: false,
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: toastMock }),
}));

vi.mock('../services/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/agentSettingsApi')>();
  return {
    ...actual,
    createAgentSettingsApi: () => apiMock,
  };
});

const installSelectPolyfills = () => {
  Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', {
    configurable: true,
    value: () => false,
  });
  Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
    configurable: true,
    value: () => undefined,
  });
};

describe('MCPSettingsPage Codex plugin scope', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    apiMock.listCodexPlugins.mockResolvedValue({ plugins: [] });
  });

  it('renders plugin MCP servers without per-server toggle controls', async () => {
    apiMock.listMcpServers.mockResolvedValue([
      {
        id: 'project:docs',
        name: 'docs',
        scope: 'project',
        command: 'npx',
        enabled: true,
      },
      {
        id: 'plugin:demo:search',
        name: 'search',
        scope: 'plugin',
        command: 'node',
        enabled: true,
        pluginName: 'Demo',
        marketplaceName: 'local',
      },
    ]);
    apiMock.listCodexPlugins.mockResolvedValue({ plugins: [{ id: 'demo@local', enabled: true }] });

    render(
      <MCPSettingsPage
        apiPrefix="codex"
        availableScopes={['project', 'user', 'plugin']}
        supportsToggle
      />,
    );

    expect(await screen.findByText('docs')).toBeInTheDocument();
    expect(screen.getByText('search')).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByRole('switch')).toHaveLength(1));
    expect(screen.getByText('Demo@local')).toBeInTheDocument();
  });

  it('exposes plugin scope even when there are no plugin MCP servers', async () => {
    const user = userEvent.setup();
    installSelectPolyfills();
    apiMock.listMcpServers.mockResolvedValue([
      {
        id: 'project:docs',
        name: 'docs',
        scope: 'project',
        command: 'npx',
        enabled: true,
      },
    ]);
    apiMock.listCodexPlugins.mockResolvedValue({ plugins: [] });

    render(
      <MCPSettingsPage
        apiPrefix="codex"
        availableScopes={['project', 'user', 'plugin']}
        supportsToggle
      />,
    );

    expect(await screen.findByText('docs')).toBeInTheDocument();
    await user.click(screen.getByRole('combobox'));
    expect(await screen.findByText('workspace.agentSettings.common.mcp.server.scope.plugin')).toBeInTheDocument();
    expect(apiMock.listCodexPlugins).not.toHaveBeenCalled();
  });

  it('filters MCP servers by search and scope dropdown', async () => {
    const user = userEvent.setup();
    installSelectPolyfills();
    apiMock.listMcpServers.mockResolvedValue([
      {
        id: 'project:docs',
        name: 'docs',
        scope: 'project',
        command: 'npx',
        enabled: true,
      },
      {
        id: 'user:search',
        name: 'search',
        scope: 'user',
        command: 'node',
        args: ['index.js'],
        enabled: true,
      },
    ]);

    render(
      <MCPSettingsPage
        apiPrefix="codex"
        availableScopes={['project', 'user']}
        supportsToggle
      />,
    );

    expect(await screen.findByText('docs')).toBeInTheDocument();
    await user.type(screen.getByPlaceholderText('workspace.agentSettings.common.mcp.search.placeholder'), 'node');

    expect(screen.queryByText('docs')).not.toBeInTheDocument();
    expect(screen.getByText('search')).toBeInTheDocument();

    await user.clear(screen.getByPlaceholderText('workspace.agentSettings.common.mcp.search.placeholder'));
    await user.click(screen.getByRole('combobox'));
    await user.click(await screen.findByRole('option', { name: /workspace\.agentSettings\.common\.mcp\.server\.scope\.project/ }));

    expect(screen.getByText('docs')).toBeInTheDocument();
    expect(screen.queryByText('search')).not.toBeInTheDocument();
  });

  it('keeps toggle and delete callbacks in the MCP page', async () => {
    const user = userEvent.setup();
    apiMock.listMcpServers.mockResolvedValue([
      {
        id: 'project:docs',
        name: 'docs',
        scope: 'project',
        command: 'npx',
        enabled: true,
      },
    ]);
    apiMock.toggleMcpServerStatus.mockResolvedValue(undefined);
    apiMock.deleteMcpServer.mockResolvedValue(undefined);

    render(<MCPSettingsPage apiPrefix="codex" availableScopes={['project']} supportsToggle />);

    expect(await screen.findByText('docs')).toBeInTheDocument();
    await user.click(screen.getByRole('switch'));

    await waitFor(() => expect(apiMock.toggleMcpServerStatus).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      expect.objectContaining({ id: 'project:docs' }),
      false,
    ));

    await user.click(screen.getByLabelText('workspace.agentSettings.common.mcp.actions.delete'));

    await waitFor(() => expect(apiMock.deleteMcpServer).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      expect.objectContaining({ id: 'project:docs' }),
    ));
  });

  it('opens create and edit dialogs from the header actions', async () => {
    const user = userEvent.setup();
    apiMock.listMcpServers.mockResolvedValue([
      {
        id: 'project:docs',
        name: 'docs',
        scope: 'project',
        command: 'npx',
        enabled: true,
      },
    ]);

    render(<MCPSettingsPage apiPrefix="codex" availableScopes={['project']} supportsToggle />);

    expect(await screen.findByText('docs')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /workspace\.agentSettings\.common\.mcp\.header\.actions\.create/ }));
    expect(await screen.findByText('workspace.agentSettings.common.mcp.dialogs.server.title.create')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'common.cancel' }));

    await user.click(screen.getByLabelText('workspace.agentSettings.common.mcp.actions.edit'));
    expect(await screen.findByText('workspace.agentSettings.common.mcp.dialogs.server.title.edit')).toBeInTheDocument();
  });
});
