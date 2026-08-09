import { describe, expect, it, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { render, renderWithoutRouter } from '@/__tests__/utils/render';
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

vi.mock('../../api/agentSettingsApi', () => ({
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
    scopes: [
      { scope: 'user', configured: true, enabled: true },
      { scope: 'project', configured: false, enabled: null },
    ],
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
    scopes: [
      { scope: 'user', configured: false, enabled: null },
      { scope: 'project', configured: true, enabled: false },
    ],
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
    scopes: [
      { scope: 'user', configured: true, enabled: true },
      { scope: 'project', configured: true, enabled: false },
    ],
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
    api.setCodexPluginEnabled.mockResolvedValue({ workspaceId: 'workspace-1', scope: 'user', pluginId: 'gamma@local', enabled: false, newThreadRequired: true });
  });

  it('renders marketplace and category filters and composes them with display mode', async () => {
    const user = userEvent.setup();
    render(<CodexPluginsPage />, {
      initialRoute: '/workspaces/workspace-1/codex/plugins',
    });

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
    render(<CodexPluginsPage />, {
      initialRoute: '/workspaces/workspace-1/codex/plugins',
    });

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

  it('keeps installed app metadata without supporting the removed Apps settings deep link', async () => {
    api.listCodexPlugins.mockResolvedValue({
      workspaceId: 'workspace-1',
      providerResourceGeneration: 9,
      plugins,
      installReserved: true,
    });
    api.getCodexPlugin.mockResolvedValue({
      workspaceId: 'workspace-1',
      providerResourceGeneration: 9,
      plugin: {
        ...plugins[0],
        longDescription: 'Canonical plugin detail',
        keywords: [],
        license: null,
        repository: null,
        websiteURL: null,
        privacyPolicyURL: null,
        termsOfServiceURL: null,
        defaultPrompts: ['Review this change for regressions.'],
        readme: null,
        skills: [],
        mcpServers: [],
        apps: [{
          name: 'review-connector',
          config: { path: 'apps/review.json' },
        }],
        hooks: [],
      },
    });

    renderWithoutRouter(
      <MemoryRouter
        initialEntries={[
          '/workspaces/workspace-1/codex/plugins?pluginId=alpha%40local&resource=apps',
        ]}
      >
        <CodexPluginsPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(api.getCodexPlugin).toHaveBeenCalledWith(
        'http://runtime.test',
        'workspace-1',
        'alpha@local',
      );
    });
    expect(await screen.findByRole('tab', {
      name: 'workspace.agentSettings.codex.plugins.detail.tabs.overview',
    })).toHaveAttribute('data-state', 'active');

    const user = userEvent.setup();
    await user.click(
      screen.getByRole('tab', {
        name: 'workspace.agentSettings.codex.plugins.detail.tabs.resources',
      }),
    );
    expect(await screen.findByText(
      'workspace.agentSettings.codex.plugins.detail.apps',
    )).toBeInTheDocument();
    expect(screen.queryByRole('link', {
      name: 'workspace.agentSettings.codex.plugins.detail.openResource',
    })).not.toBeInTheDocument();

    await user.click(
      screen.getByRole('tab', {
        name: 'workspace.agentSettings.codex.plugins.detail.tabs.overview',
      }),
    );
    expect(
      screen.getByText('Review this change for regressions.'),
    ).toBeInTheDocument();
  });
});
