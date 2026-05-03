import React from 'react';
import userEvent from '@testing-library/user-event';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CodexDocumentSidebar from './CodexDocumentSidebar';

const apiMock = {
  listCodexFiles: vi.fn(),
  listCodexRules: vi.fn(),
  listCodexSubagents: vi.fn(),
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

describe('CodexDocumentSidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listCodexRules.mockResolvedValue({ files: [] });
    apiMock.listCodexSubagents.mockResolvedValue({ items: [], registry: [] });
    apiMock.listCodexFiles
      .mockResolvedValueOnce({
        files: [
          {
            name: 'review.md',
            path: 'team/review.md',
            sizeBytes: 12,
            source: 'project',
            readOnly: false,
            metadata: {},
          },
        ],
      })
      .mockResolvedValueOnce({
        files: [
          {
            name: 'personal.md',
            path: 'personal.md',
            sizeBytes: 7,
            source: 'user',
            readOnly: false,
            metadata: {},
          },
        ],
      });
  });

  it('renders a selectable Codex document list for four-column mode', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();

    render(<CodexDocumentSidebar resource="prompts" selectedId={null} onSelect={onSelect} />);

    expect(await screen.findByText('review.md')).toBeInTheDocument();
    expect(screen.getAllByText('personal.md').length).toBeGreaterThan(0);
    expect(screen.getByText('workspace.agentSettings.codex.documents.meta.prompts.title')).toBeInTheDocument();

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('user:personal.md'));

    await user.click(screen.getByText('review.md'));

    expect(onSelect).toHaveBeenCalledWith('project:team/review.md');
  });

  it('reselects the first filtered document when selected id is stale', async () => {
    const onSelect = vi.fn();

    render(<CodexDocumentSidebar resource="prompts" selectedId="project:missing.md" onSelect={onSelect} />);

    expect(await screen.findByText('review.md')).toBeInTheDocument();
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('user:personal.md'));
  });

  it('renders rules documents from project and user scopes', async () => {
    const onSelect = vi.fn();
    apiMock.listCodexRules
      .mockResolvedValueOnce({
        files: [{ name: 'project.rules', path: 'project.rules', sizeBytes: 11 }],
      })
      .mockResolvedValueOnce({
        files: [{ name: 'default.rules', path: 'default.rules', sizeBytes: 7 }],
      });

    render(<CodexDocumentSidebar resource="rules" selectedId={null} onSelect={onSelect} />);

    await waitFor(() => expect(screen.getAllByText('project.rules').length).toBeGreaterThan(0));
    expect(screen.queryByText('default.rules')).not.toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.documents.meta.rules.title')).toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.codex.documents.sidebar.scope.all')).not.toBeInTheDocument();
    expect(screen.queryByText('workspace.agentSettings.codex.documents.scope.values.plugin')).not.toBeInTheDocument();
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('project:project.rules'));
  });

  it('renders Codex subagents from the structured subagents endpoint', async () => {
    const onSelect = vi.fn();
    apiMock.listCodexSubagents.mockResolvedValueOnce({
      registry: [],
      items: [
        {
          id: 'built_in:worker',
          name: 'worker',
          source: 'built_in',
          editable: false,
          readOnly: true,
          path: 'worker.toml',
          relativePath: 'worker.toml',
          content: 'name = "worker"\n',
          definition: {
            name: 'worker',
            description: 'Worker',
            developer_instructions: 'Do work.',
          },
          effective: true,
          overridden: false,
          metadata: { format: 'toml' },
        },
      ],
    });

    render(<CodexDocumentSidebar resource="subagents" selectedId={null} onSelect={onSelect} />);

    await waitFor(() => expect(screen.getAllByText('worker.toml').length).toBeGreaterThan(0));
    expect(apiMock.listCodexSubagents).toHaveBeenCalledWith('http://runtime.test', 'ws-1');
    expect(apiMock.listCodexFiles).not.toHaveBeenCalled();
    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('built_in:worker'));
  });
});
