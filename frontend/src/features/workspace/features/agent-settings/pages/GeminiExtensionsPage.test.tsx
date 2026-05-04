import { describe, expect, it, vi, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@testing-library/react';
import { renderWithQuery } from '@/__tests__/utils/render';
import GeminiExtensionsPage from './GeminiExtensionsPage';

const api = {
  listGeminiExtensions: vi.fn(),
  getGeminiExtension: vi.fn(),
  enableGeminiExtension: vi.fn(),
  disableGeminiExtension: vi.fn(),
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
      if (values?.name) {
        return `${key}:${values.name}`;
      }
      if (typeof values?.count === 'number') {
        return `${key}:${values.count}`;
      }
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

const extensions = [
  {
    name: 'enabled-extension',
    version: '1.0.0',
    description: 'Enabled extension description',
    contextFileName: 'GEMINI.md',
    installSource: 'github:example/enabled',
    installType: 'git',
    releaseTag: 'v1.0.0',
    enabledHere: true,
    overrides: ['/workspace/*'],
    resourceCounts: { mcp: 1, commands: 2, skills: 3, hooks: 4, policies: 5 },
    excludeToolsCount: 6,
  },
  {
    name: 'disabled-extension',
    version: null,
    description: null,
    contextFileName: null,
    installSource: null,
    installType: null,
    releaseTag: null,
    enabledHere: false,
    overrides: ['!/workspace/*'],
    resourceCounts: { mcp: 0, commands: 1, skills: 0, hooks: 0, policies: 0 },
    excludeToolsCount: 0,
  },
];

const buildExtension = (name: string, enabledHere = true) => ({
  name,
  version: '1.0.0',
  description: `${name} description`,
  contextFileName: 'GEMINI.md',
  installSource: `github:example/${name}`,
  installType: 'git',
  releaseTag: 'v1.0.0',
  enabledHere,
  overrides: [],
  resourceCounts: { mcp: 0, commands: 0, skills: 0, hooks: 0, policies: 0 },
  excludeToolsCount: 0,
});

const detail = {
  name: 'enabled-extension',
  version: '1.0.0',
  installInfo: { source: 'github:example/enabled', type: 'git', releaseTag: 'v1.0.0' },
  enabledHere: true,
  overrides: ['/workspace/*'],
  contextFile: { path: '/extension/GEMINI.md', content: 'Context preview' },
  policies: [{ path: '/extension/policies/policy.toml', content: 'allow = true' }],
  excludeTools: ['Shell'],
  mcpServers: [{ name: 'fs', config: {} }],
  slashCommands: [{ fileName: 'deploy.toml' }],
  skills: [{ name: 'review' }],
  hooks: [{ path: '/extension/hooks/hooks.json' }],
};

describe('GeminiExtensionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listGeminiExtensions.mockResolvedValue({ workspaceId: 'workspace-1', extensions });
    api.getGeminiExtension.mockResolvedValue({ workspaceId: 'workspace-1', extension: detail });
    api.enableGeminiExtension.mockResolvedValue({});
    api.disableGeminiExtension.mockResolvedValue({});
  });

  it('defaults to enabled-only gallery cards', async () => {
    renderWithQuery(<GeminiExtensionsPage />);

    expect(await screen.findByText('enabled-extension')).toBeInTheDocument();
    expect(screen.getByText('Enabled extension description')).toBeInTheDocument();
    expect(screen.getByText('GEMINI.md')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.geminiExtensions.counts.mcp:1')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.geminiExtensions.counts.commands:2')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.geminiExtensions.counts.skills:3')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.geminiExtensions.counts.hooks:4')).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.geminiExtensions.counts.policies:5')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.geminiExtensions.counts.excludeTools:6')).not.toBeInTheDocument();
    expect(screen.queryByText('disabled-extension')).not.toBeInTheDocument();
  });

  it('shortens GitHub install source URLs in card metadata', async () => {
    api.listGeminiExtensions.mockResolvedValue({
      workspaceId: 'workspace-1',
      extensions: [{
        ...extensions[0],
        installSource: 'https://github.com/apify/agent-skills',
      }],
    });
    renderWithQuery(<GeminiExtensionsPage />);

    expect(await screen.findByText('apify/agent-skills')).toBeInTheDocument();
    expect(screen.queryByText('https://github.com/apify/agent-skills')).not.toBeInTheDocument();
  });

  it('shows disabled cards and fallback descriptions in all mode', async () => {
    const user = userEvent.setup();
    renderWithQuery(<GeminiExtensionsPage />);

    await screen.findByText('enabled-extension');
    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.geminiExtensions.displayModes.all' }));

    expect(screen.getByText('disabled-extension')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.geminiExtensions.descriptionFallback')).toBeInTheDocument();
  });

  it('filters cards with search and can clear the search', async () => {
    const user = userEvent.setup();
    renderWithQuery(<GeminiExtensionsPage />);

    await screen.findByText('enabled-extension');
    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.geminiExtensions.displayModes.all' }));
    await user.type(
      screen.getByLabelText('workspace.agentSettings.geminiExtensions.search.label'),
      'disabled',
    );

    expect(screen.getByText('disabled-extension')).toBeInTheDocument();
    expect(screen.queryByText('enabled-extension')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.geminiExtensions.actions.clearSearch' }));

    expect(screen.getByText('enabled-extension')).toBeInTheDocument();
    expect(screen.getByText('disabled-extension')).toBeInTheDocument();
  });

  it('paginates gallery cards when there are more extensions than one page', async () => {
    const user = userEvent.setup();
    api.listGeminiExtensions.mockResolvedValue({
      workspaceId: 'workspace-1',
      extensions: Array.from({ length: 7 }, (_item, index) => buildExtension(`page-extension-${index + 1}`)),
    });

    renderWithQuery(<GeminiExtensionsPage />);

    expect(await screen.findByText('page-extension-1')).toBeInTheDocument();
    expect(screen.getByText('page-extension-6')).toBeInTheDocument();
    expect(screen.queryByText('page-extension-7')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.geminiExtensions.pagination.next' }));

    expect(screen.getByText('page-extension-7')).toBeInTheDocument();
    expect(screen.queryByText('page-extension-1')).not.toBeInTheDocument();
  });

  it('runs workspace enable and disable actions from card action menus', async () => {
    const user = userEvent.setup();
    renderWithQuery(<GeminiExtensionsPage />);

    await screen.findByText('enabled-extension');
    await user.click(screen.getAllByRole('button', { name: 'workspace.agentSettings.geminiExtensions.actions.more' })[0]);
    await user.click(screen.getByText('workspace.agentSettings.geminiExtensions.actions.disableWorkspace'));

    await waitFor(() => {
      expect(api.disableGeminiExtension).toHaveBeenCalledWith(
        'http://runtime.test',
        'workspace-1',
        'enabled-extension',
        'workspace',
      );
    });

    await user.click(screen.getByRole('button', { name: 'workspace.agentSettings.geminiExtensions.displayModes.all' }));
    await user.click(screen.getAllByRole('button', { name: 'workspace.agentSettings.geminiExtensions.actions.more' })[1]);
    await user.click(screen.getByText('workspace.agentSettings.geminiExtensions.actions.enableWorkspace'));

    await waitFor(() => {
      expect(api.enableGeminiExtension).toHaveBeenCalledWith(
        'http://runtime.test',
        'workspace-1',
        'disabled-extension',
        'workspace',
      );
    });
  });

  it('exposes secondary user-scope actions and opens details', async () => {
    const user = userEvent.setup();
    renderWithQuery(<GeminiExtensionsPage />);

    await screen.findByText('enabled-extension');
    await user.click(screen.getAllByRole('button', { name: 'workspace.agentSettings.geminiExtensions.actions.more' })[0]);
    await user.click(screen.getByText('workspace.agentSettings.geminiExtensions.actions.disableUser'));

    await waitFor(() => {
      expect(api.disableGeminiExtension).toHaveBeenCalledWith(
        'http://runtime.test',
        'workspace-1',
        'enabled-extension',
        'user',
      );
    });

    await user.click(screen.getAllByRole('button', { name: 'workspace.agentSettings.geminiExtensions.actions.more' })[0]);
    await user.click(screen.getByText('workspace.agentSettings.geminiExtensions.actions.details'));

    expect(await screen.findByText('Context preview')).toBeInTheDocument();
    expect(screen.getByText('allow = true')).toBeInTheDocument();
  });
});
