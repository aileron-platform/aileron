import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithQuery } from '@/__tests__/utils/render';
import SlashCommandsPage from './SlashCommandsPage';

const api = {
  listSlashCommands: vi.fn(),
  createSlashCommand: vi.fn(),
  updateSlashCommand: vi.fn(),
  deleteSlashCommand: vi.fn(),
};

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'workspace-1',
    },
  }),
}));

vi.mock('@/features/workspace/events/templateInstallCoordinator', () => ({
  useWorkspaceTemplateInstallRefresh: vi.fn(),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, unknown>) => {
      if (typeof values?.count === 'number') return `${key}:${values.count}`;
      if (values?.title) return `${key}:${values.title}`;
      return key;
    },
  }),
}));

vi.mock('../services/agentSettingsApi', () => ({
  createAgentSettingsApi: () => api,
}));

describe('SlashCommandsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listSlashCommands.mockResolvedValue([
      {
        id: 'project:deploy.toml',
        title: 'deploy.toml',
        description: '',
        scope: 'project',
        content: 'description = "Deploy command"\nprompt = "Run deploy"\n',
        metadata: { fileName: 'deploy.toml' },
      },
    ]);
  });

  it('renders parsed TOML fields without showing the raw TOML block', async () => {
    renderWithQuery(<SlashCommandsPage format="toml" />);

    expect(await screen.findByText('deploy.toml')).toBeInTheDocument();
    expect(screen.getByText('Deploy command')).toBeInTheDocument();
    expect(screen.getByText('Run deploy')).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.common.documents.toml.raw')).not.toBeInTheDocument();
    expect(screen.queryByText('description = "Deploy command"')).not.toBeInTheDocument();
  });

  it('falls back to full TOML content when slash command fields cannot be parsed', async () => {
    api.listSlashCommands.mockResolvedValue([
      {
        id: 'project:legacy.toml',
        title: 'legacy.toml',
        description: '',
        scope: 'project',
        content: "title = 'Legacy command'\nbody = 'Run legacy deploy'\n",
        metadata: { fileName: 'legacy.toml' },
      },
    ]);

    renderWithQuery(<SlashCommandsPage format="toml" />);

    expect(await screen.findByText('legacy.toml')).toBeInTheDocument();
    expect(screen.getByText(/title = 'Legacy command'/)).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.common.documents.toml.raw')).not.toBeInTheDocument();
  });
});
