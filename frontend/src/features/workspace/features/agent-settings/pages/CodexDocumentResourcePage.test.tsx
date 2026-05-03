import React from 'react';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import CodexDocumentResourcePage from './CodexDocumentResourcePage';

const apiMock = {
  listCodexFiles: vi.fn(),
  getCodexFile: vi.fn(),
  updateCodexFile: vi.fn(),
  deleteCodexFile: vi.fn(),
  listCodexSubagents: vi.fn(),
  getCodexSubagent: vi.fn(),
  saveCodexSubagent: vi.fn(),
  deleteCodexSubagent: vi.fn(),
};

vi.mock('@/features/workspace/providers/WorkspaceProvider', () => ({
  useWorkspace: () => ({
    workspaceRuntime: {
      runtimeBaseUrl: 'http://runtime.test',
      workspaceId: 'ws-1',
    },
  }),
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params?.count !== undefined) return `${key}:${String(params.count)}`;
      return key;
    },
  }),
}));

vi.mock('../services/agentSettingsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/agentSettingsApi')>();
  return {
    ...actual,
    createAgentSettingsApi: () => apiMock,
  };
});

describe('CodexDocumentResourcePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiMock.listCodexFiles.mockResolvedValue({ files: [] });
    apiMock.getCodexFile.mockResolvedValue({ content: '# Content' });
    apiMock.listCodexSubagents.mockResolvedValue({ items: [], registry: [] });
    apiMock.getCodexSubagent.mockResolvedValue({
      id: 'built_in:worker',
      name: 'worker',
      source: 'built_in',
      editable: false,
      readOnly: true,
      path: 'worker.toml',
      relativePath: 'worker.toml',
      content: 'name = "worker"\ndescription = "Worker"\ndeveloper_instructions = "Do work."\n',
      definition: {
        name: 'worker',
        description: 'Worker',
        developer_instructions: 'Do work.',
      },
      effective: true,
      overridden: false,
      metadata: { format: 'toml' },
    });
    apiMock.saveCodexSubagent.mockResolvedValue({
      id: 'project:reviewer.toml',
      name: 'reviewer',
      source: 'project',
      editable: true,
      readOnly: false,
      path: 'reviewer.toml',
      relativePath: 'reviewer.toml',
      content: 'name = "reviewer"\ndescription = "Reviews code"\ndeveloper_instructions = "Review code."\n',
      definition: {
        name: 'reviewer',
        description: 'Reviews code',
        developer_instructions: 'Review code.',
      },
      effective: true,
      overridden: false,
      metadata: { format: 'toml' },
    });
  });

  it('renders prompts with Codex prompt terminology and document workflow actions', async () => {
    apiMock.listCodexFiles
      .mockResolvedValueOnce({
        files: [
          {
            name: 'deploy.md',
            path: 'deploy.md',
            sizeBytes: 9,
            source: 'project',
            readOnly: false,
            metadata: {},
          },
        ],
      })
      .mockResolvedValueOnce({ files: [] });
    apiMock.getCodexFile.mockResolvedValue({ content: '# Deploy' });

    render(<CodexDocumentResourcePage resource="prompts" />);

    expect(await screen.findByText('workspace.agentSettings.codex.prompts.pageTitle')).toBeInTheDocument();
    expect(screen.getByText('deploy.md')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.prompts.actions.create')).toBeInTheDocument();
    await waitFor(() => expect(apiMock.getCodexFile).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'prompts',
      'project',
      'deploy.md',
    ));
  });

  it('reselects an available prompt when the external selected id is stale', async () => {
    const onSelect = vi.fn();
    apiMock.listCodexFiles
      .mockResolvedValueOnce({
        files: [
          {
            name: 'deploy.md',
            path: 'deploy.md',
            sizeBytes: 9,
            source: 'project',
            readOnly: false,
            metadata: {},
          },
        ],
      })
      .mockResolvedValueOnce({ files: [] });
    apiMock.getCodexFile.mockResolvedValueOnce({ content: '# Deploy' });

    const { rerender } = render(
      <CodexDocumentResourcePage
        resource="prompts"
        selectedId="project:stale.md"
        onSelect={onSelect}
      />,
    );

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith('project:deploy.md'));

    rerender(
      <CodexDocumentResourcePage
        resource="prompts"
        selectedId="project:deploy.md"
        onSelect={onSelect}
      />,
    );

    expect(await screen.findByText('Deploy')).toBeInTheDocument();
  });

  it('loads selected prompt content directly when the list content is stale', async () => {
    apiMock.listCodexFiles
      .mockResolvedValueOnce({
        files: [
          {
            name: 'deploy.md',
            path: 'deploy.md',
            sizeBytes: 0,
            source: 'project',
            readOnly: false,
            metadata: {},
          },
        ],
      })
      .mockResolvedValueOnce({ files: [] });
    apiMock.getCodexFile.mockResolvedValueOnce({ content: '# Loaded Later' });

    render(
      <CodexDocumentResourcePage
        resource="prompts"
        selectedId="project:deploy.md"
        onSelect={vi.fn()}
      />,
    );

    expect(await screen.findByText('Loaded Later')).toBeInTheDocument();
  });

  it('does not fetch every prompt body before rendering the list', async () => {
    apiMock.listCodexFiles
      .mockResolvedValueOnce({
        files: [
          { name: 'alpha.md', path: 'alpha.md', sizeBytes: 5, source: 'project', readOnly: false, metadata: {} },
          { name: 'beta.md', path: 'beta.md', sizeBytes: 5, source: 'project', readOnly: false, metadata: {} },
        ],
      })
      .mockResolvedValueOnce({ files: [] });
    apiMock.getCodexFile.mockResolvedValue({ content: '# Alpha' });

    render(
      <CodexDocumentResourcePage
        resource="prompts"
        selectedId="project:alpha.md"
        onSelect={vi.fn()}
      />,
    );

    expect(await screen.findByText('alpha.md')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.documents.stats.total:2')).toBeInTheDocument();
    await waitFor(() => expect(apiMock.getCodexFile).toHaveBeenCalledTimes(1));
    expect(apiMock.getCodexFile).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'prompts',
      'project',
      'alpha.md',
    );
  });

  it('renders read-only subagent sources without fetching editable content', async () => {
    apiMock.listCodexSubagents.mockResolvedValueOnce({
      registry: [
        {
          layer: 'user',
          path: '/home/developer/.codex/config.toml',
          settings: { max_threads: 4, max_depth: 1, job_max_runtime_seconds: 1800 },
        },
      ],
      items: [
          {
            id: 'built_in:worker',
            name: 'worker',
            source: 'built_in',
            editable: false,
            readOnly: true,
            path: 'worker.toml',
            relativePath: 'worker.toml',
            content: '',
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

    render(<CodexDocumentResourcePage resource="subagents" />);

    expect(await screen.findByText('workspace.agentSettings.codex.subagents.pageTitle')).toBeInTheDocument();
    expect(screen.getByText('worker')).toBeInTheDocument();
    expect(screen.getByText('Worker')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.documents.status.effective')).toBeInTheDocument();
    expect(screen.getByText('workspace.agentSettings.codex.subagents.registry.summary')).toBeInTheDocument();
    expect(apiMock.listCodexSubagents).toHaveBeenCalledWith('http://runtime.test', 'ws-1');
    expect(apiMock.getCodexFile).not.toHaveBeenCalled();
    expect(apiMock.getCodexSubagent).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      'built_in',
      'worker.toml',
      undefined,
    );
  });

  it('creates a structured Codex subagent definition with optional fields', async () => {
    const user = userEvent.setup();
    render(<CodexDocumentResourcePage resource="subagents" />);

    await user.click(await screen.findByText('workspace.agentSettings.codex.subagents.actions.create'));
    await user.type(
      screen.getByLabelText('workspace.agentSettings.codex.subagents.dialog.fields.name.label'),
      'reviewer',
    );
    await user.type(
      screen.getByLabelText('workspace.agentSettings.codex.subagents.dialog.fields.description.label'),
      'Reviews code',
    );
    await user.type(
      screen.getByLabelText('workspace.agentSettings.codex.subagents.dialog.fields.developerInstructions.label'),
      'Review code.',
    );
    await user.type(
      screen.getByLabelText('workspace.agentSettings.codex.subagents.dialog.fields.nicknameCandidates.label'),
      'Atlas\nDelta',
    );
    await user.type(
      screen.getByLabelText('workspace.agentSettings.codex.subagents.dialog.fields.model.label'),
      'gpt-5.4',
    );
    expect(screen.getByLabelText('workspace.agentSettings.codex.subagents.dialog.fields.modelReasoningEffort.label')).toHaveTextContent(
      'workspace.agentSettings.codex.subagents.dialog.fields.modelReasoningEffort.options.medium.label',
    );
    expect(screen.getByLabelText('workspace.agentSettings.codex.subagents.dialog.fields.sandboxMode.label')).toHaveTextContent(
      'workspace.agentSettings.codex.subagents.dialog.fields.sandboxMode.options.workspace-write.label',
    );
    await user.click(screen.getByText('workspace.agentSettings.codex.subagents.dialog.actions.create'));

    await waitFor(() => expect(apiMock.saveCodexSubagent).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      {
        layer: 'project',
        path: null,
        content: null,
        definition: {
          name: 'reviewer',
          description: 'Reviews code',
          developer_instructions: 'Review code.',
          nickname_candidates: ['Atlas', 'Delta'],
          model: 'gpt-5.4',
          model_reasoning_effort: 'medium',
          sandbox_mode: 'workspace-write',
        },
      },
    ));
  });

  it('validates raw TOML mode and submits raw content without structured fields', async () => {
    const user = userEvent.setup();
    render(<CodexDocumentResourcePage resource="subagents" />);

    await user.click(await screen.findByText('workspace.agentSettings.codex.subagents.actions.create'));
    await user.click(screen.getByText('workspace.agentSettings.codex.subagents.dialog.tabs.raw'));
    await user.click(screen.getByText('workspace.agentSettings.codex.subagents.dialog.actions.create'));

    expect(screen.getByText('workspace.agentSettings.codex.subagents.dialog.validation.rawContent')).toBeInTheDocument();
    expect(apiMock.saveCodexSubagent).not.toHaveBeenCalled();

    await user.type(
      screen.getByLabelText('workspace.agentSettings.codex.subagents.dialog.fields.rawContent.label'),
      'name = "reviewer"\ndescription = "Reviews code"\ndeveloper_instructions = "Review code."\nunknown_field = true',
    );
    await user.click(screen.getByText('workspace.agentSettings.codex.subagents.dialog.actions.create'));

    await waitFor(() => expect(apiMock.saveCodexSubagent).toHaveBeenCalledWith(
      'http://runtime.test',
      'ws-1',
      {
        layer: 'project',
        path: null,
        content: 'name = "reviewer"\ndescription = "Reviews code"\ndeveloper_instructions = "Review code."\nunknown_field = true',
        definition: null,
      },
    ));
  });
});
