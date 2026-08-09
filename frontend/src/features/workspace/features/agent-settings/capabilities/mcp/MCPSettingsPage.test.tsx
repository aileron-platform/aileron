import React from 'react';
import userEvent from '@testing-library/user-event';
import {
  createTestQueryClient,
  render,
  screen,
  waitFor,
} from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import MCPSettingsPage from './MCPSettingsPage';

const apiMock = {
  listMcpServers: vi.fn(),
  refreshCache: vi.fn(),
  createMcpServer: vi.fn(),
  updateMcpServer: vi.fn(),
  deleteMcpServer: vi.fn(),
  toggleMcpServerStatus: vi.fn(),
  importMcpServers: vi.fn(),
  updateCodexPluginMcpPolicy: vi.fn(),
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

vi.mock('../../api/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../api/agentSettingsApi')>();
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

const codexPluginPolicyServer = {
  id: 'plugin:demo@local:search',
  name: 'search',
  scope: 'plugin',
  transport: 'stdio',
  command: 'node',
  enabled: true,
  serverId: 'search',
  pluginId: 'demo@local',
  pluginName: 'Demo',
  marketplaceName: 'local',
  readOnly: true,
  editable: false,
  effective: true,
  policyRevision: 'policy-r1',
  policy: {
    enabled: true,
    defaultToolsApprovalMode: 'prompt',
    enabledTools: ['search'],
    disabledTools: null,
    tools: {},
  },
} as const;

describe('MCPSettingsPage Codex plugin scope', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    apiMock.refreshCache.mockResolvedValue({ refreshed: true });
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
    expect(apiMock.listMcpServers).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      expect.any(AbortSignal),
    );
  });

  it('keeps the plugin definition read-only while saving its independent MCP policy', async () => {
    const user = userEvent.setup();
    const queryClient = createTestQueryClient();
    apiMock.listMcpServers.mockResolvedValue([codexPluginPolicyServer]);
    apiMock.updateCodexPluginMcpPolicy.mockResolvedValue({
      revision: 'policy-r2',
      providerResourceGeneration: 2,
      newThreadRequired: true,
    });

    render(
      <MCPSettingsPage
        apiPrefix="codex"
        availableScopes={['project', 'user', 'plugin']}
        supportsToggle
      />,
      { queryClient },
    );

    expect(await screen.findByText('search')).toBeInTheDocument();
    expect(screen.getByRole('region', {
      name: 'workspace.agentSettings.common.mcp.pluginPolicy.title',
    })).toBeInTheDocument();
    expect(screen.queryByLabelText('workspace.agentSettings.common.mcp.actions.edit')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('workspace.agentSettings.common.mcp.actions.delete')).not.toBeInTheDocument();

    await user.click(screen.getByRole('switch', {
      name: 'workspace.agentSettings.common.mcp.pluginPolicy.fields.enabled',
    }));
    await user.click(screen.getByRole('button', {
      name: 'workspace.agentSettings.common.mcp.pluginPolicy.actions.save',
    }));

    await waitFor(() => expect(apiMock.updateCodexPluginMcpPolicy).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'demo@local',
      'search',
      {
        enabled: false,
        defaultToolsApprovalMode: 'prompt',
        enabledTools: ['search'],
        disabledTools: null,
        tools: {},
      },
      'policy-r1',
    ));
    expect(screen.getByText('search')).toBeInTheDocument();
  });

  it('maps MCP policy backend errors without exposing raw messages', async () => {
    const user = userEvent.setup();
    apiMock.listMcpServers.mockResolvedValue([codexPluginPolicyServer]);
    apiMock.updateCodexPluginMcpPolicy.mockRejectedValue(
      Object.assign(new Error('sensitive runtime detail'), {
        errorCode: 'REVISION_CONFLICT',
      }),
    );

    render(
      <MCPSettingsPage
        apiPrefix="codex"
        availableScopes={['project', 'user', 'plugin']}
        supportsToggle
      />,
    );

    expect(await screen.findByText('search')).toBeInTheDocument();
    await user.click(screen.getByRole('button', {
      name: 'workspace.agentSettings.common.mcp.pluginPolicy.actions.save',
    }));

    await waitFor(() => expect(toastMock).toHaveBeenCalledWith({
      variant: 'destructive',
      title: 'workspace.agentSettings.common.mcp.pluginPolicy.messages.saveFailed',
      description:
        'workspace.agentSettings.pluginResources.controlErrors.revisionConflict',
    }));
    expect(JSON.stringify(toastMock.mock.calls)).not.toContain(
      'sensitive runtime detail',
    );
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
    expect(apiMock.listMcpServers).toHaveBeenCalledTimes(1);
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

  it('clears the scoped backend cache before replacing MCP inventory', async () => {
    const user = userEvent.setup();
    const queryClient = createTestQueryClient();
    apiMock.listMcpServers
      .mockResolvedValueOnce([{
        id: 'plugin:demo:old',
        name: 'old-server',
        scope: 'plugin',
        command: 'node',
        enabled: true,
      }])
      .mockResolvedValue([{
        id: 'plugin:demo:new',
        name: 'new-server',
        scope: 'plugin',
        command: 'node',
        enabled: true,
      }]);

    render(
      <MCPSettingsPage
        apiPrefix="codex"
        availableScopes={['project', 'user', 'plugin']}
        supportsToggle
      />,
      { queryClient },
    );

    expect(await screen.findByText('old-server')).toBeInTheDocument();
    await user.click(screen.getByRole('button', {
      name: 'workspace.agentSettings.common.mcp.header.actions.refresh',
    }));

    expect(await screen.findByText('new-server')).toBeInTheDocument();
    expect(screen.queryByText('old-server')).not.toBeInTheDocument();
    expect(apiMock.refreshCache).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      {
        provider: 'codex',
        capability: 'mcp',
        scope: 'all',
      },
    );
    expect(apiMock.listMcpServers.mock.calls.length).toBeGreaterThanOrEqual(2);
  });
});
