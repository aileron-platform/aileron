import type React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithQuery } from '@/__tests__/utils/render';
import { DocumentResourceWorkbench } from './DocumentResourceWorkbench';
import { createDocumentMetadataAdapter } from './documentMetadataAdapters';
import type {
  DocumentDialogProps,
  DocumentResourceItem,
  DocumentSource,
} from './model/documentResourceTypes';

const translateMock = vi.hoisted(() => vi.fn((key: string, values?: Record<string, unknown>) => {
  if (key === 'shared.documentWorkflow.metadata.errors.conflict') {
    return values?.name ? `${String(values.name)} already exists` : key;
  }
  return key;
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: translateMock,
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({ value, onChange }: { value: string; onChange(value: string): void }) => (
    <textarea aria-label="markdown-editor" value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}));

vi.mock('@/shared/components/file-workbench/viewer-entry', () => ({
  CodeTextEditor: ({
    content,
    onContentChange,
  }: {
    content: string;
    onContentChange(value: string): void;
  }) => (
    <textarea
      aria-label="code-text-editor"
      value={content}
      onChange={(event) => onContentChange(event.target.value)}
    />
  ),
}));

const PassthroughDialog = () => null;

const baseDoc = (id: string, content = ''): DocumentResourceItem => ({
  id,
  title: id,
  scope: 'project',
  content,
  metadata: { source: 'project', relativePath: id },
});

const LegacyDocumentDialog: React.FC<DocumentDialogProps> = ({
  open,
  mode,
  initialValue,
  onClose,
  onSubmit,
}) => {
  if (!open) {
    return null;
  }
  const submittedDocument = mode === 'create'
    ? baseDoc('legacy-created.md', 'CREATED')
    : {
        ...(initialValue ?? baseDoc('legacy-updated.md')),
        id: 'legacy-updated.md',
        title: 'legacy-updated.md',
        content: 'UPDATED',
      };
  return (
    <div role="dialog" aria-label="legacy-document-dialog">
      <span data-testid="legacy-dialog-mode">{mode}</span>
      <span data-testid="legacy-dialog-initial">{initialValue?.id ?? 'null'}</span>
      <button type="button" data-testid="legacy-dialog-close" onClick={onClose}>
        close
      </button>
      <button
        type="button"
        data-testid="legacy-dialog-submit"
        onClick={() => void onSubmit(submittedDocument)}
      >
        submit
      </button>
    </div>
  );
};

const makeSource = (overrides: Partial<DocumentSource> = {}): DocumentSource => ({
  list: vi.fn().mockResolvedValue({
    items: [baseDoc('greet.md', 'HELLO')],
    availableScopes: [],
  }),
  create: vi.fn(),
  update: vi.fn(),
  remove: vi.fn(),
  ...overrides,
});

const config = {
  metaKey: 'prompts' as const,
  contentFormat: 'markdown' as const,
  emptyStateTitle: 'empty.title',
  emptyStateDescription: 'empty.desc',
  dialogTitle: 'dialog.title',
};

describe('DocumentResourceWorkbench', () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.restoreAllMocks());

  it('lists documents from the source and selects the first by default', async () => {
    const source = makeSource();
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['prompts', 'codex']}
        source={source}
        dialog={PassthroughDialog}
        config={config}
        i18nNamespace="ns"
      />,
    );

    expect((await screen.findAllByText('greet.md')).length).toBeGreaterThan(0);
    expect(await screen.findByText('HELLO')).toBeInTheDocument();
    expect(source.list).toHaveBeenCalledTimes(1);
  });

  it('keeps Markdown edit mode inside the full-height editor surface', async () => {
    const source = makeSource();
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['prompts', 'full-height']}
        source={source}
        dialog={PassthroughDialog}
        config={config}
        i18nNamespace="ns"
        metadataAdapter={createDocumentMetadataAdapter('slashCommand')}
        templateResourceType="slashCommand"
      />,
    );

    await screen.findByText('HELLO');
    await userEvent.click(screen.getByRole('button', {
      name: 'shared.documentWorkflow.detail.actions.edit',
    }));

    const editor = await screen.findByLabelText('markdown-editor');
    expect(editor.closest('div.flex.min-h-0.flex-1.flex-col.overflow-hidden')).toBeInTheDocument();
    expect(editor.parentElement).toHaveClass('flex-1', 'overflow-hidden');
    expect(document.querySelector('div.flex-1.overflow-y-auto.p-4')).not.toBeInTheDocument();
  });

  it('uses shared TOML labels when the feature namespace does not define them', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [baseDoc('agent.toml', 'description = "Reviewer"\nprompt = "Review this change"')],
        availableScopes: [],
      }),
    });

    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'shared-toml-labels']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
        }}
        i18nNamespace="feature.documents"
      />,
    );

    expect(await screen.findByText('shared.documentResource.toml.description')).toBeInTheDocument();
    expect(screen.getByText('shared.documentResource.toml.prompt')).toBeInTheDocument();
    expect(screen.getByText('shared.documentResource.toml.raw')).toBeInTheDocument();
  });

  it('does not call the source when the runtime is unavailable', async () => {
    const source = makeSource();
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['prompts', 'runtime-unavailable']}
        source={source}
        dialog={PassthroughDialog}
        config={config}
        i18nNamespace="ns"
        isEnabled={false}
        disabledMessage="runtime unavailable"
      />,
    );

    expect(await screen.findByText('runtime unavailable')).toBeInTheDocument();
    expect(source.list).not.toHaveBeenCalled();
  });

  it('lazily loads content for the selected document when source.loadContent exists', async () => {
    const loadContent = vi.fn(async (document: DocumentResourceItem) => ({ ...document, content: 'LAZY BODY' }));
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [baseDoc('greet.md', '')],
        availableScopes: [],
      }),
      loadContent,
    });

    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['prompts', 'codex']}
        source={source}
        dialog={PassthroughDialog}
        config={config}
        i18nNamespace="ns"
      />,
    );

    await waitFor(() => expect(loadContent).toHaveBeenCalledWith(expect.objectContaining({ id: 'greet.md' })));
  });

  it('renders an optional header above the document page', async () => {
    const source = makeSource();
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'codex']}
        source={source}
        dialog={PassthroughDialog}
        config={config}
        i18nNamespace="ns"
        renderHeader={(docs) => <div data-testid="hdr">count:{docs.length}</div>}
      />,
    );

    expect((await screen.findByTestId('hdr')).textContent).toBe('count:1');
  });

  it('submits the legacy create dialog and selects the created document', async () => {
    const source = makeSource({
      create: vi.fn(async (document) => document),
    });
    const onSelect = vi.fn();
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['legacy', 'create']}
        source={source}
        dialog={LegacyDocumentDialog}
        config={{
          ...config,
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="ns"
        selectedId="greet.md"
        onSelect={onSelect}
      />,
    );

    await screen.findAllByText('greet.md');
    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));

    expect(screen.getByTestId('legacy-dialog-mode')).toHaveTextContent('create');
    expect(screen.getByTestId('legacy-dialog-initial')).toHaveTextContent('null');

    await userEvent.click(screen.getByTestId('legacy-dialog-submit'));

    await waitFor(() => expect(source.create).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'legacy-created.md', content: 'CREATED' }),
    ));
    expect(onSelect).toHaveBeenCalledWith('legacy-created.md');
    expect(screen.queryByRole('dialog', { name: 'legacy-document-dialog' })).not.toBeInTheDocument();
  });

  it('submits the selected document through the legacy edit dialog', async () => {
    const source = makeSource({
      update: vi.fn(async (document) => document),
    });
    const onSelect = vi.fn();
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['legacy', 'edit']}
        source={source}
        dialog={LegacyDocumentDialog}
        config={config}
        i18nNamespace="ns"
        selectedId="greet.md"
        onSelect={onSelect}
      />,
    );

    await screen.findAllByText('greet.md');
    await userEvent.click(screen.getByRole('button', {
      name: 'shared.documentWorkflow.metadata.actions.more',
    }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'ns.documents.actions.edit' }));

    expect(screen.getByTestId('legacy-dialog-mode')).toHaveTextContent('edit');
    expect(screen.getByTestId('legacy-dialog-initial')).toHaveTextContent('greet.md');

    await userEvent.click(screen.getByTestId('legacy-dialog-submit'));

    await waitFor(() => expect(source.update).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'legacy-updated.md', content: 'UPDATED' }),
    ));
    expect(onSelect).toHaveBeenCalledWith('legacy-updated.md');
    expect(screen.queryByRole('dialog', { name: 'legacy-document-dialog' })).not.toBeInTheDocument();
  });

  it('keeps navigation order and selects the first remaining document after delete', async () => {
    const user = userEvent.setup();
    const documents = [
      baseDoc('first.md', 'FIRST'),
      baseDoc('second.md', 'SECOND'),
      baseDoc('third.md', 'THIRD'),
    ];
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: documents, availableScopes: [] }),
      remove: vi.fn().mockResolvedValue(undefined),
    });
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { container } = renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['navigation', 'delete']}
        source={source}
        dialog={LegacyDocumentDialog}
        config={config}
        i18nNamespace="ns"
      />,
    );

    expect(await screen.findByRole('heading', { name: 'first.md' })).toBeInTheDocument();
    const previousButton = container.querySelector('.lucide-chevron-left')?.closest('button');
    const nextButton = container.querySelector('.lucide-chevron-right')?.closest('button');
    expect(previousButton).toBeDisabled();
    expect(nextButton).toBeEnabled();

    await user.click(nextButton as HTMLButtonElement);
    expect(await screen.findByRole('heading', { name: 'second.md' })).toBeInTheDocument();
    expect(previousButton).toBeEnabled();

    await user.click(previousButton as HTMLButtonElement);
    expect(await screen.findByRole('heading', { name: 'first.md' })).toBeInTheDocument();

    await user.click(nextButton as HTMLButtonElement);
    await user.click(screen.getByRole('button', {
      name: 'shared.documentWorkflow.metadata.actions.more',
    }));
    await user.click(screen.getByRole('menuitem', { name: 'ns.documents.actions.delete' }));

    expect(confirmSpy).toHaveBeenCalledWith('ns.documents.confirmDelete');
    await waitFor(() => expect(source.remove).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'second.md' }),
    ));
    expect(await screen.findByRole('heading', { name: 'first.md' })).toBeInTheDocument();
  });

  it('refreshes both the document list and lazy content query', async () => {
    const loadContent = vi.fn(async (document: DocumentResourceItem) => ({
      ...document,
      content: 'LAZY BODY',
    }));
    const source = makeSource({ loadContent });
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['refresh', 'lazy']}
        source={source}
        dialog={PassthroughDialog}
        config={config}
        i18nNamespace="ns"
      />,
    );

    await waitFor(() => expect(loadContent).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByRole('button', { name: 'ns.documents.actions.refresh' }));

    await waitFor(() => expect(source.list).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(loadContent).toHaveBeenCalledTimes(2));
  });

  it('renders developer instructions and keeps the TOML raw section toggleable', async () => {
    const content = [
      'description = "Reviewer"',
      'developer_instructions = """Review carefully"""',
    ].join('\n');
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [baseDoc('agent.toml', content)],
        availableScopes: [],
      }),
    });
    const { container } = renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['toml', 'raw-toggle']}
        source={source}
        config={{ ...config, contentFormat: 'toml' }}
        i18nNamespace="feature.documents"
      />,
    );

    expect(await screen.findByText('Review carefully')).toBeInTheDocument();
    const rawButton = screen.getByRole('button', {
      name: 'shared.documentResource.toml.raw',
    });
    expect(container.querySelector('pre')).toBeNull();

    await userEvent.click(rawButton);
    expect(container.querySelector('pre')?.textContent).toBe(content);

    await userEvent.click(rawButton);
    expect(container.querySelector('pre')).toBeNull();
  });

  it('shows raw TOML fallback when parsed fields are unavailable and raw controls are disabled', async () => {
    const content = 'model = "gpt-5"';
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [baseDoc('agent.toml', content)],
        availableScopes: [],
      }),
    });
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['toml', 'fallback']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          showRawToml: false,
        }}
        i18nNamespace="feature.documents"
      />,
    );

    expect(await screen.findByText(content)).toBeInTheDocument();
    expect(screen.queryByRole('button', {
      name: 'shared.documentResource.toml.raw',
    })).not.toBeInTheDocument();
  });

  it('renders the unsaved selection guard without taking over selection blocking', async () => {
    const source = makeSource();
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['selection', 'blocked']}
        source={source}
        dialog={PassthroughDialog}
        config={config}
        i18nNamespace="ns"
        documentSelectionBlocked
      />,
    );

    expect(await screen.findByText('shared.documentWorkflow.detail.unsavedGuard')).toBeInTheDocument();
  });

  it('selects the created document and requests inline edit mode', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
    });
    source.create = vi.fn(async (document) => ({ ...document, id: 'project:new.md' }));
    const metadataAdapter = createDocumentMetadataAdapter('slashCommand');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['test']}
        source={source}
        dialog={PassthroughDialog}
        config={{
          ...config,
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.claudeCode"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="slashCommand"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'new.md');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).toHaveBeenCalledWith(expect.objectContaining({
      content: expect.stringContaining('# new'),
    }));
    expect(await screen.findByLabelText('markdown-editor')).toBeInTheDocument();
  });

  it('uses the shared empty state for an empty document resource', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
    });
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['empty', 'style']}
        source={source}
        config={config}
        i18nNamespace="ns"
      />,
    );

    const title = await screen.findByText('empty.title');

    expect(title).toBeInTheDocument();
    expect(screen.getByText('empty.desc')).toBeInTheDocument();
    expect(title.parentElement?.querySelector('svg')).toBeInTheDocument();
  });

  it('normalizes missing markdown extension before inline create', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
    });
    source.create = vi.fn(async (document) => document);
    const metadataAdapter = createDocumentMetadataAdapter('slashCommand');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['slash', 'normalize-create']}
        source={source}
        dialog={PassthroughDialog}
        config={{
          ...config,
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.claudeCode"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="slashCommand"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'deploy');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).toHaveBeenCalledWith(expect.objectContaining({
      title: 'deploy.md',
      id: expect.stringContaining('deploy.md'),
      content: expect.stringContaining('# deploy'),
    }));
  });

  it('preserves namespace before inline slash command create', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
    });
    source.create = vi.fn(async (document) => document);
    const metadataAdapter = createDocumentMetadataAdapter('slashCommand');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['slash', 'namespace-create']}
        source={source}
        dialog={PassthroughDialog}
        config={{
          ...config,
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.claudeCode"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="slashCommand"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'greet');
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.namespace.label'), 'team');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).toHaveBeenCalledWith(expect.objectContaining({
      title: 'greet.md',
      id: 'project:team/greet.md',
      metadata: expect.objectContaining({ fileName: 'team/greet.md' }),
      content: expect.stringContaining('# greet'),
    }));
    expect(source.create).not.toHaveBeenCalledWith(expect.objectContaining({
      id: 'project:greet.md',
    }));
  });

  it('normalizes wrong extension before TOML subagent create', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
    });
    source.create = vi.fn(async (document) => document);
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'normalize-create']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'worker.md');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).toHaveBeenCalledWith(expect.objectContaining({
      title: 'worker.toml',
      id: expect.stringContaining('worker.toml'),
      content: expect.stringContaining('name = "worker"'),
    }));
  });

  it('preserves nested path before TOML subagent create', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
    });
    source.create = vi.fn(async (document) => document);
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'nested-create']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'team/worker.md');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).toHaveBeenCalledWith(expect.objectContaining({
      title: 'worker.toml',
      id: 'project:team/worker.toml',
      metadata: expect.objectContaining({ fileName: 'team/worker.toml' }),
      content: expect.stringContaining('name = "worker"'),
    }));
    expect(source.create).not.toHaveBeenCalledWith(expect.objectContaining({
      content: expect.stringContaining('name = "team/worker"'),
    }));
  });

  it('rejects extension-only names before inline create', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
    });
    source.create = vi.fn();
    const metadataAdapter = createDocumentMetadataAdapter('slashCommand');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['slash', 'reject-extension-only']}
        source={source}
        dialog={PassthroughDialog}
        config={{
          ...config,
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.claudeCode"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="slashCommand"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), '.toml');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).not.toHaveBeenCalled();
    expect(await screen.findByText('shared.documentWorkflow.metadata.errors.fileNameRequired')).toBeInTheDocument();
  });

  it('normalizes rename target before moving a TOML subagent', async () => {
    const user = userEvent.setup();
    const oldDocument: DocumentResourceItem = {
      ...baseDoc('project:old.toml', 'name = "old"'),
      title: 'old.toml',
      metadata: { source: 'project', relativePath: 'old.toml' },
    };
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [oldDocument],
        availableScopes: [{ scope: 'project', readOnly: false }],
      }),
      move: vi.fn(async (document) => document),
    });
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'normalize-rename']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await screen.findAllByText('old.toml');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.more' }));
    await user.click(screen.getByRole('menuitem', {
      name: 'shared.documentWorkflow.metadata.actions.rename',
    }));
    const fileNameInput = screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label');
    await user.clear(fileNameInput);
    await user.type(fileNameInput, 'new.md');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));

    await waitFor(() => expect(source.move).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'new.toml',
        metadata: expect.objectContaining({ previousFileName: 'old.toml' }),
      }),
      'new.toml',
    ));
  });

  it('preserves nested path before moving a TOML subagent', async () => {
    const user = userEvent.setup();
    const oldDocument: DocumentResourceItem = {
      ...baseDoc('project:old.toml', 'name = "old"'),
      title: 'old.toml',
      metadata: { source: 'project', relativePath: 'old.toml' },
    };
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [oldDocument],
        availableScopes: [{ scope: 'project', readOnly: false }],
      }),
      move: vi.fn(async (document) => document),
    });
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'nested-rename']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await screen.findAllByText('old.toml');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.more' }));
    await user.click(screen.getByRole('menuitem', {
      name: 'shared.documentWorkflow.metadata.actions.rename',
    }));
    const fileNameInput = screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label');
    await user.clear(fileNameInput);
    await user.type(fileNameInput, 'team/new.md');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));

    await waitFor(() => expect(source.move).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'new.toml',
        id: 'project:team/new.toml',
        metadata: expect.objectContaining({
          fileName: 'team/new.toml',
          previousFileName: 'old.toml',
        }),
      }),
      'team/new.toml',
    ));
  });

  it('rejects duplicate TOML subagent rename target before move', async () => {
    const user = userEvent.setup();
    const oldDocument: DocumentResourceItem = {
      ...baseDoc('project:old.toml', 'name = "old"'),
      title: 'old.toml',
      metadata: { source: 'project', relativePath: 'old.toml' },
    };
    const existingDocument: DocumentResourceItem = {
      ...baseDoc('project:new.toml', 'name = "new"'),
      title: 'new.toml',
      metadata: { source: 'project', relativePath: 'new.toml' },
    };
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [oldDocument, existingDocument],
        availableScopes: [{ scope: 'project', readOnly: false }],
      }),
      move: vi.fn(async (document) => document),
    });
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'duplicate-rename']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await screen.findAllByText('old.toml');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.more' }));
    await user.click(screen.getByRole('menuitem', {
      name: 'shared.documentWorkflow.metadata.actions.rename',
    }));
    const fileNameInput = screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label');
    await user.clear(fileNameInput);
    await user.type(fileNameInput, 'new.md');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));

    expect(source.move).not.toHaveBeenCalled();
    expect(translateMock).toHaveBeenCalledWith('shared.documentWorkflow.metadata.errors.conflict', {
      name: 'new.toml',
    });
    expect((await screen.findAllByText('new.toml already exists')).length).toBeGreaterThan(0);
  });

  it('rejects duplicate nested TOML subagent rename target before move', async () => {
    const user = userEvent.setup();
    const oldDocument: DocumentResourceItem = {
      ...baseDoc('project:old.toml', 'name = "old"'),
      title: 'old.toml',
      metadata: { source: 'project', relativePath: 'old.toml' },
    };
    const existingDocument: DocumentResourceItem = {
      ...baseDoc('project:team/new.toml', 'name = "new"'),
      title: 'new.toml',
      metadata: { source: 'project', relativePath: 'team/new.toml' },
    };
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [oldDocument, existingDocument],
        availableScopes: [{ scope: 'project', readOnly: false }],
      }),
      move: vi.fn(async (document) => document),
    });
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'duplicate-nested-rename']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await screen.findAllByText('old.toml');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.more' }));
    await user.click(screen.getByRole('menuitem', {
      name: 'shared.documentWorkflow.metadata.actions.rename',
    }));
    const fileNameInput = screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label');
    await user.clear(fileNameInput);
    await user.type(fileNameInput, 'team/new.md');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));

    expect(source.move).not.toHaveBeenCalled();
    expect(translateMock).toHaveBeenCalledWith('shared.documentWorkflow.metadata.errors.conflict', {
      name: 'new.toml',
    });
    expect((await screen.findAllByText('new.toml already exists')).length).toBeGreaterThan(0);
  });

  it('shows inline error when TOML subagent rename move fails', async () => {
    const user = userEvent.setup();
    const oldDocument: DocumentResourceItem = {
      ...baseDoc('project:old.toml', 'name = "old"'),
      title: 'old.toml',
      metadata: { source: 'project', relativePath: 'old.toml' },
    };
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [oldDocument],
        availableScopes: [{ scope: 'project', readOnly: false }],
      }),
      move: vi.fn(async () => {
        throw new Error('move failed');
      }),
    });
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'rename-failure']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await screen.findAllByText('old.toml');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.more' }));
    await user.click(screen.getByRole('menuitem', {
      name: 'shared.documentWorkflow.metadata.actions.rename',
    }));
    const fileNameInput = screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label');
    await user.clear(fileNameInput);
    await user.type(fileNameInput, 'new.toml');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));

    expect((await screen.findAllByText('move failed')).length).toBeGreaterThan(0);
    expect(source.move).toHaveBeenCalledTimes(1);
  });

  it('clears stale inline errors after closing metadata dialog', async () => {
    const user = userEvent.setup();
    const source = makeSource();
    const metadataAdapter = createDocumentMetadataAdapter('slashCommand');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['slash', 'clear-stale-create-error']}
        source={source}
        dialog={PassthroughDialog}
        config={{
          ...config,
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.claudeCode"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="slashCommand"
      />,
    );

    await screen.findAllByText('greet.md');
    await user.click(screen.getByRole('button', { name: 'create.label' }));
    await user.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), '.toml');
    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));
    expect((await screen.findAllByText('shared.documentWorkflow.metadata.errors.fileNameRequired')).length).toBeGreaterThan(0);

    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.cancel' }));
    await waitFor(() => {
      expect(screen.queryByText('shared.documentWorkflow.metadata.errors.fileNameRequired')).not.toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'create.label' }));
    expect(screen.queryByText('shared.documentWorkflow.metadata.errors.fileNameRequired')).not.toBeInTheDocument();
  });

  it('keeps the metadata dialog open and shows an inline error when inline create fails', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
    });
    source.create = vi.fn(async () => {
      const error = new Error('new.toml') as Error & { errorCode?: string };
      error.errorCode = 'SUBAGENT_CONFLICT';
      throw error;
    });
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'codex-create-failure']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'new.toml');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(await screen.findByText('new.toml already exists')).toBeInTheDocument();
    expect(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label')).toBeInTheDocument();
  });

  it('prevents inline create when the document already exists in the selected scope', async () => {
    const source = makeSource({
      list: vi.fn().mockResolvedValue({
        items: [{
          ...baseDoc('project:test.toml'),
          title: 'test.toml',
          metadata: { source: 'project', relativePath: 'test.toml' },
        }],
        availableScopes: [{ scope: 'project', readOnly: false }],
      }),
    });
    const metadataAdapter = createDocumentMetadataAdapter('subagent');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['subagents', 'codex-create-conflict']}
        source={source}
        config={{
          ...config,
          contentFormat: 'toml',
          createButtonLabel: 'create.label',
        }}
        i18nNamespace="workspace.agentSettings.codex"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="subagent"
      />,
    );

    await userEvent.click(screen.getByRole('button', { name: 'create.label' }));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'test.toml');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).not.toHaveBeenCalled();
    expect((await screen.findAllByText('test.toml already exists')).length).toBeGreaterThan(0);
  });

  it('hides scope badges, detail metadata, and metadata dialog scope when scopeMode is hidden', async () => {
    const user = userEvent.setup();
    const source = makeSource();
    const metadataAdapter = createDocumentMetadataAdapter('slashCommand');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['slash', 'hidden-scope']}
        source={source}
        dialog={PassthroughDialog}
        config={{
          ...config,
          createButtonLabel: 'create.label',
          scopeMode: 'hidden',
        }}
        i18nNamespace="ns"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="slashCommand"
      />,
    );

    await screen.findAllByText('greet.md');

    expect(screen.queryByText('ns.documents.scope.values.project')).not.toBeInTheDocument();
    expect(screen.queryByText('ns.documents.metadata.scope')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'create.label' }));

    expect(screen.queryByLabelText('shared.documentWorkflow.metadata.scope.label')).not.toBeInTheDocument();
  });

  it('keeps inline markdown editing available after canceling from the document header', async () => {
    const user = userEvent.setup();
    const source = makeSource();
    const metadataAdapter = createDocumentMetadataAdapter('slashCommand');
    renderWithQuery(
      <DocumentResourceWorkbench
        queryKey={['slash', 'claude']}
        source={source}
        dialog={PassthroughDialog}
        config={config}
        i18nNamespace="workspace.claudeCode"
        availableScopes={['project']}
        metadataAdapter={metadataAdapter}
        templateResourceType="slashCommand"
      />,
    );

    await screen.findAllByText('greet.md');
    const editButton = await screen.findByRole('button', {
      name: 'shared.documentWorkflow.detail.actions.edit',
    });
    await user.click(editButton);
    expect(await screen.findByLabelText('markdown-editor')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'shared.documentWorkflow.detail.actions.cancel' }));
    expect(screen.queryByLabelText('markdown-editor')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', {
      name: 'shared.documentWorkflow.detail.actions.edit',
    }));
    expect(await screen.findByLabelText('markdown-editor')).toBeInTheDocument();
  });
});
