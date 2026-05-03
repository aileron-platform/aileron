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

describe('MCPSettingsPage Codex plugin scope', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

  it('exposes plugin scope when Codex has enabled plugins without MCP servers', async () => {
    const user = userEvent.setup();
    Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', {
      configurable: true,
      value: () => false,
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: () => undefined,
    });
    apiMock.listMcpServers.mockResolvedValue([
      {
        id: 'project:docs',
        name: 'docs',
        scope: 'project',
        command: 'npx',
        enabled: true,
      },
    ]);
    apiMock.listCodexPlugins.mockResolvedValue({ plugins: [{ id: 'github@openai-curated', enabled: true }] });

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
  });
});
