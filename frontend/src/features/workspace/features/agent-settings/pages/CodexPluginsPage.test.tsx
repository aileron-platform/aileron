import { describe, expect, it, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@testing-library/react';
import { renderWithQuery } from '@/__tests__/utils/render';
import CodexPluginsPage from './CodexPluginsPage';

const api = {
  listCodexPlugins: vi.fn(),
  getCodexPlugin: vi.fn(),
  setCodexPluginEnabled: vi.fn(),
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
      if (values?.layer && values?.state) return `${key}:${values.layer}:${values.state}`;
      if (values?.layer) return `${key}:${values.layer}`;
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
    id: 'alpha@local',
    name: 'alpha',
    displayName: 'Alpha Plugin',
    shortDescription: 'Alpha review helper',
    version: '1.0.0',
    authorName: 'Team',
    category: 'Review',
    capabilities: [],
    brandColor: null,
    homepage: null,
    marketplace: 'local',
    listed: true,
    installed: true,
    effectiveEnabled: true,
    layers: [
      { layer: 'user', configured: true, enabled: true },
      { layer: 'project', configured: false, enabled: null },
    ],
    path: null,
    sourcePath: null,
    resourceCounts: { skills: 1, mcpServers: 0, apps: 0, hooks: 0 },
  },
  {
    id: 'beta@remote',
    name: 'beta',
    displayName: 'Beta Plugin',
    shortDescription: 'Beta build helper',
    version: '1.0.0',
    authorName: 'Team',
    category: 'Build',
    capabilities: [],
    brandColor: null,
    homepage: null,
    marketplace: 'remote',
    listed: true,
    installed: true,
    effectiveEnabled: false,
    layers: [
      { layer: 'user', configured: false, enabled: null },
      { layer: 'project', configured: true, enabled: false },
    ],
    path: null,
    sourcePath: null,
    resourceCounts: { skills: 0, mcpServers: 0, apps: 0, hooks: 0 },
  },
  {
    id: 'gamma@local',
    name: 'gamma',
    displayName: 'Gamma Plugin',
    shortDescription: 'Gamma override helper',
    version: '1.0.0',
    authorName: 'Team',
    category: 'Review',
    capabilities: [],
    brandColor: null,
    homepage: null,
    marketplace: 'local',
    listed: true,
    installed: true,
    effectiveEnabled: false,
    layers: [
      { layer: 'user', configured: true, enabled: true },
      { layer: 'project', configured: true, enabled: false },
    ],
    path: null,
    sourcePath: null,
    resourceCounts: { skills: 0, mcpServers: 0, apps: 0, hooks: 0 },
  },
];

describe('CodexPluginsPage', () => {
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
    api.listCodexPlugins.mockResolvedValue({ workspaceId: 'workspace-1', plugins, installReserved: true });
    api.getCodexPlugin.mockResolvedValue({ workspaceId: 'workspace-1', plugin: plugins[0] });
    api.setCodexPluginEnabled.mockResolvedValue({ workspaceId: 'workspace-1', layer: 'user', pluginId: 'gamma@local', enabled: false, newThreadRequired: true });
  });

  it('renders marketplace and category filters and composes them with display mode', async () => {
    const user = userEvent.setup();
    renderWithQuery(<CodexPluginsPage />);

    expect(await screen.findByText('Alpha Plugin')).toBeInTheDocument();
    expect(screen.queryByText('Beta Plugin')).not.toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.plugins.filters.marketplaceLabel')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.plugins.filters.categoryLabel')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.common.plugins.displayModes.all' }));
    await user.click(screen.getAllByRole('combobox')[1]);
    await user.click(await screen.findByRole('option', { name: 'remote' }));

    expect(screen.getByText('Beta Plugin')).toBeInTheDocument();
    expect(screen.queryByText('Alpha Plugin')).not.toBeInTheDocument();
  });

  it('uses selected Codex layer state for toggle and shows project override messaging', async () => {
    const user = userEvent.setup();
    renderWithQuery(<CodexPluginsPage />);

    await screen.findByText('Alpha Plugin');
    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.common.plugins.displayModes.all' }));
    await user.click(screen.getAllByRole('combobox')[0]);
    await user.click(await screen.findByRole('option', { name: 'workspace.agentSettings.codex.plugins.layers.user' }));
    await user.type(screen.getByLabelText('workspace.agentSettings.common.plugins.search.label'), 'gamma');

    expect(screen.getByText('Gamma Plugin')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.plugins.layers.projectOverride')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.common.plugins.actions.more' }));
    await user.click(screen.getByText('workspace.agentSettings.common.plugins.actions.disable'));

    await waitFor(() => {
      expect(api.setCodexPluginEnabled).toHaveBeenCalledWith(
        'http://runtime.test',
        'workspace-1',
        'gamma@local',
        'user',
        false,
      );
    });
  });
});
