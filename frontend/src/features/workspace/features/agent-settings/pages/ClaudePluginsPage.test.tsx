import { describe, expect, it, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@testing-library/react';
import { renderWithQuery } from '@/__tests__/utils/render';
import ClaudePluginsPage from './ClaudePluginsPage';

const api = {
  listClaudePlugins: vi.fn(),
  getClaudePlugin: vi.fn(),
  setClaudePluginEnabled: vi.fn(),
};

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'workspace-1',
      isLoading: false,
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => {
      if (values?.name) return `${key}:${values.name}`;
      if (typeof values?.count === 'number') return `${key}:${values.count}`;
      return key;
    },
  }),
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock('../services/agentSettingsApi', () => ({
  createAgentSettingsApi: () => api,
}));

const plugins = [
  {
    id: 'review@official',
    name: 'Review Plugin',
    marketplace: 'official',
    version: '1.0.0',
    description: 'Review helper',
    author: 'Team',
    category: 'Review',
    homepage: null,
    enabled: true,
    installations: [{ scope: 'user', enabled: true, installPath: '/plugins/review', projectPath: null, version: '1.0.0', installedAt: null, lastUpdated: null }],
    errors: [],
    resourceCounts: { commands: 1, agents: 0, hooks: 0, mcpServers: 0, skills: 1, lspServers: 0 },
  },
  {
    id: 'build@community',
    name: 'Build Plugin',
    marketplace: 'community',
    version: '1.0.0',
    description: 'Build helper',
    author: 'Team',
    category: 'Build',
    homepage: null,
    enabled: true,
    installations: [{ scope: 'project', enabled: true, installPath: '/plugins/build', projectPath: '/workspace', version: '1.0.0', installedAt: null, lastUpdated: null }],
    errors: [],
    resourceCounts: { commands: 0, agents: 0, hooks: 0, mcpServers: 0, skills: 0, lspServers: 0 },
  },
  {
    id: 'mixed@official',
    name: 'Mixed Plugin',
    marketplace: 'official',
    version: '1.0.0',
    description: 'Mixed scope helper',
    author: 'Team',
    category: 'Ops',
    homepage: null,
    enabled: false,
    installations: [
      { scope: 'user', enabled: true, installPath: '/plugins/mixed-user', projectPath: null, version: '1.0.0', installedAt: null, lastUpdated: null },
      { scope: 'local', enabled: false, installPath: '/plugins/mixed-local', projectPath: '/workspace', version: '1.0.0', installedAt: null, lastUpdated: null },
    ],
    errors: [],
    resourceCounts: { commands: 0, agents: 0, hooks: 0, mcpServers: 0, skills: 0, lspServers: 0 },
  },
];

describe('ClaudePluginsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', {
      configurable: true,
      value: () => false,
    });
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: () => undefined,
    });
    api.listClaudePlugins.mockResolvedValue({
      workspaceId: 'workspace-1',
      plugins,
      marketplaces: [
        { name: 'official', pluginCount: 1, owner: null, source: null },
        { name: 'community', pluginCount: 1, owner: null, source: null },
      ],
    });
    api.getClaudePlugin.mockResolvedValue({ workspaceId: 'workspace-1', plugin: plugins[0] });
    api.setClaudePluginEnabled.mockResolvedValue({});
  });

  it('renders marketplace and category filters and composes selected filters', async () => {
    const user = userEvent.setup();
    renderWithQuery(<ClaudePluginsPage />);

    expect(await screen.findByText('Review Plugin')).toBeInTheDocument();
    expect(screen.getByText('Build Plugin')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.claude.plugins.filters.marketplaceLabel')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.claude.plugins.filters.categoryLabel')).toBeInTheDocument();

    await user.click(screen.getAllByRole('combobox')[2]);
    await user.click(await screen.findByRole('option', { name: 'Build' }));

    expect(screen.getByText('Build Plugin')).toBeInTheDocument();
    expect(screen.queryByText('Review Plugin')).not.toBeInTheDocument();
  });

  it('uses the selected scope installation state when toggling', async () => {
    const user = userEvent.setup();
    renderWithQuery(<ClaudePluginsPage />);

    await screen.findByText('Review Plugin');
    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.common.plugins.displayModes.all' }));
    await user.click(screen.getAllByRole('combobox')[0]);
    await user.click(await screen.findByRole('option', { name: 'workspace.agentSettings.claude.plugins.scopes.user' }));
    await user.type(screen.getByLabelText('workspace.agentSettings.common.plugins.search.label'), 'mixed');

    expect(screen.getByText('Mixed Plugin')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.common.plugins.actions.more' }));
    await user.click(screen.getByText('workspace.agentSettings.common.plugins.actions.disable'));

    await waitFor(() => {
      expect(api.setClaudePluginEnabled).toHaveBeenCalledWith(
        'http://runtime.test',
        'workspace-1',
        'mixed@official',
        'user',
        false,
      );
    });
  });
});
