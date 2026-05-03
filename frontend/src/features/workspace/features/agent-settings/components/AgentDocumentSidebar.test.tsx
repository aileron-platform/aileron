import React from 'react';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AgentDocumentSidebar from './AgentDocumentSidebar';

const apiMock = {
  listSlashCommands: vi.fn(),
  listSubagents: vi.fn(),
};

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    layout: { secondColumnCollapsed: false },
    toggleSecondColumn: vi.fn(),
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('../services/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/agentSettingsApi')>();
  return {
    ...actual,
    createAgentSettingsApi: () => apiMock,
  };
});

describe('AgentDocumentSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listSlashCommands.mockResolvedValue([
      {
        id: 'project:help.md',
        title: 'Help',
        scope: 'project',
        metadata: { fileName: 'help.md' },
      },
      {
        id: 'user:todo.md',
        title: 'Todo',
        scope: 'user',
        metadata: { fileName: 'todo.md' },
      },
    ]);
    apiMock.listSubagents.mockResolvedValue([
      {
        id: 'project:agent-a.toml',
        title: 'Agent A',
        scope: 'project',
        metadata: { fileName: 'agent-a.toml' },
      },
    ]);
  });

  it('renders slash-command documents and auto selects the first item', async () => {
    const onSelect = vi.fn();
    render(<AgentDocumentSidebar resource="slash-commands" selectedId={null} onSelect={onSelect} />);

    expect(await screen.findByText('Help')).toBeInTheDocument();
    expect(screen.getByText('Todo')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.common.documents.meta.slash-commands.title')).toBeInTheDocument();
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('project:help.md'));
  });

  it('switches selection by click after search filter', async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<AgentDocumentSidebar resource="slash-commands" selectedId="project:help.md" onSelect={onSelect} />);

    const searchInput = await screen.findByPlaceholderText('workspace.agentSettings.common.documents.sidebar.searchPlaceholder');
    await user.type(searchInput, 'todo');

    expect(screen.getByText('Todo')).toBeInTheDocument();
    expect(screen.queryByText('Help')).not.toBeInTheDocument();

    await user.click(screen.getByText('Todo'));
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('user:todo.md'));
  });

  it('auto reselects first document when selected id is missing', async () => {
    const onSelect = vi.fn();
    render(<AgentDocumentSidebar resource="subagents" selectedId="user:missing.toml" onSelect={onSelect} />);

    expect(await screen.findByText('Agent A')).toBeInTheDocument();
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('project:agent-a.toml'));
  });
});
