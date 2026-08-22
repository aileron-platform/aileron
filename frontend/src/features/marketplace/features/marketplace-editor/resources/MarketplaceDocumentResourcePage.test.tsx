import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { screen } from '@/__tests__/utils/render';
import { renderWithQuery } from '@/__tests__/utils/render';
import {
  MarketplaceDocumentResourcePage,
  marketplaceDocumentResourceQueryKey,
} from './MarketplaceDocumentResourcePage';
import type { DocumentResourceItem } from '@/shared/components/document-resource';
import type { MarketplaceDocumentMutationResult } from '../../../model/marketplaceMutation';

const translateMock = vi.hoisted(() => vi.fn((key: string, values?: Record<string, unknown>) => {
  if (key === 'shared.documentWorkflow.metadata.errors.conflict') {
    return values?.name ? `${String(values.name)} already exists` : key;
  }
  return key;
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: translateMock }),
}));

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({ value, onChange }: { value: string; onChange(value: string): void }) => (
    <textarea aria-label="markdown-editor" value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}));

const agentCommandDocument = (path = 'prompts/a.md', content = 'old'): DocumentResourceItem => ({
  id: path,
  title: path.split('/').pop()?.replace(/\.[^.]+$/, '') ?? path,
  description: path,
  scope: 'project',
  content,
  metadata: {
    fileName: path,
  },
});

const mutationResult = (
  path = 'prompts/a.md',
  revision = 'rev2',
): MarketplaceDocumentMutationResult => ({
  success: true,
  path,
  revision,
  ownerFilePath: null,
  baseEntryFingerprint: null,
});

const documentMutation = (
  document: DocumentResourceItem,
  revision = 'rev2',
) => ({
  document,
  result: mutationResult(document.id, revision),
});

const renderResourcePage = (ui: React.ReactElement) => renderWithQuery(ui);

describe('MarketplaceDocumentResourcePage', () => {
  it('keeps targetClient and package identity in the collection query key', () => {
    expect(marketplaceDocumentResourceQueryKey('codex', 'toolkit', 'commands'))
      .toEqual(['marketplace', 'codex', 'toolkit', 'commands']);
    expect(marketplaceDocumentResourceQueryKey('codex', 'other', 'commands'))
      .not.toEqual(marketplaceDocumentResourceQueryKey('codex', 'toolkit', 'commands'));
  });

  it.each([
    ['commands', 'marketplace.resources.commands'],
    ['subagents', 'marketplace.resources.subagents'],
    ['output-styles', 'marketplace.resources.outputStyles'],
  ] as const)('renders %s through the semantic workbench surface without a shell fallback', async (resourceType, titleKey) => {
    const source = {
      list: vi.fn().mockResolvedValue({ items: [agentCommandDocument()], availableScopes: [] }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument()),
      create: vi.fn(),
      update: vi.fn(),
      move: vi.fn(),
      remove: vi.fn(),
    };

    renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType={resourceType}
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={vi.fn()}
      />,
    );

    expect(screen.queryByTestId('product-shell')).not.toBeInTheDocument();
    expect(await screen.findByPlaceholderText('marketplace.editor.documents.sidebar.searchPlaceholder')).toBeInTheDocument();
    expect(screen.getAllByText(titleKey)).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'marketplace.editor.documents.actions.refresh' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'marketplace.editor.documents.actions.create' })).toHaveLength(1);
  });

  it('forwards mutation result and uses returned document for list updates', async () => {
    const onMutation = vi.fn().mockResolvedValue(undefined);
    const updateResult = mutationResult();
    const source = {
      list: vi.fn().mockResolvedValue({ items: [agentCommandDocument()], availableScopes: [] }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument()),
      create: vi.fn(),
      update: vi.fn().mockResolvedValue({
        document: agentCommandDocument('prompts/a.md', 'new'),
        result: updateResult,
      }),
      move: vi.fn(),
      remove: vi.fn(),
    };

    const { container } = renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType="commands"
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={onMutation}
      />,
    );

    expect(container.firstElementChild).toHaveClass('flex-1');
    await userEvent.click(await screen.findByText('a'));
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.detail.actions.edit' }));
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.detail.actions.save' }));

    expect(source.update).toHaveBeenCalledWith(expect.objectContaining({ id: 'prompts/a.md' }));
    expect(onMutation).toHaveBeenCalledWith(updateResult);
  });

  it('roots the created command path under the resource directory with an extension', async () => {
    const onMutation = vi.fn();
    const source = {
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument('prompts/greet.md')),
      create: vi.fn().mockResolvedValue(
        documentMutation(agentCommandDocument('prompts/greet.md')),
      ),
      update: vi.fn(),
      move: vi.fn(),
      remove: vi.fn(),
    };

    renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType="commands"
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={onMutation}
      />,
    );

    await userEvent.click((await screen.findAllByRole('button', { name: 'marketplace.editor.documents.actions.create' }))[0]);
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'greet');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).toHaveBeenCalledWith(expect.objectContaining({
      id: 'prompts/greet.md',
      title: 'greet.md',
      metadata: expect.objectContaining({ fileName: 'prompts/greet.md' }),
    }));
  }, 20_000);

  it('preserves nested command path before marketplace create', async () => {
    const onMutation = vi.fn();
    const source = {
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument('prompts/team/greet.md')),
      create: vi.fn().mockResolvedValue(
        documentMutation(agentCommandDocument('prompts/team/greet.md')),
      ),
      update: vi.fn(),
      move: vi.fn(),
      remove: vi.fn(),
    };

    renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType="commands"
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={onMutation}
      />,
    );

    await userEvent.click((await screen.findAllByRole('button', { name: 'marketplace.editor.documents.actions.create' }))[0]);
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'team/greet');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).toHaveBeenCalledWith(expect.objectContaining({
      id: 'prompts/team/greet.md',
      title: 'greet.md',
      metadata: expect.objectContaining({ fileName: 'prompts/team/greet.md' }),
      content: expect.stringContaining('# greet'),
    }));
  }, 20_000);

  it('preserves namespace before marketplace command create', async () => {
    const onMutation = vi.fn();
    const source = {
      list: vi.fn().mockResolvedValue({ items: [], availableScopes: [] }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument('prompts/team/greet.md')),
      create: vi.fn().mockResolvedValue(
        documentMutation(agentCommandDocument('prompts/team/greet.md')),
      ),
      update: vi.fn(),
      move: vi.fn(),
      remove: vi.fn(),
    };

    renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType="commands"
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={onMutation}
      />,
    );

    await userEvent.click((await screen.findAllByRole('button', { name: 'marketplace.editor.documents.actions.create' }))[0]);
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'greet');
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.namespace.label'), 'team');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).toHaveBeenCalledWith(expect.objectContaining({
      id: 'prompts/team/greet.md',
      title: 'greet.md',
      metadata: expect.objectContaining({ fileName: 'prompts/team/greet.md' }),
      content: expect.stringContaining('# greet'),
    }));
  });

  it('rejects nested create when the target marketplace document already exists', async () => {
    const onMutation = vi.fn();
    const source = {
      list: vi.fn().mockResolvedValue({
        items: [agentCommandDocument('prompts/team/greet.md')],
        availableScopes: [],
      }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument('prompts/team/greet.md')),
      create: vi.fn().mockResolvedValue(
        documentMutation(agentCommandDocument('prompts/team/greet.md')),
      ),
      update: vi.fn(),
      move: vi.fn(),
      remove: vi.fn(),
    };

    renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType="commands"
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={onMutation}
      />,
    );

    await userEvent.click((await screen.findAllByRole('button', { name: 'marketplace.editor.documents.actions.create' }))[0]);
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'team/greet');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.create' }));

    expect(source.create).not.toHaveBeenCalled();
    expect(translateMock).toHaveBeenCalledWith('shared.documentWorkflow.metadata.errors.conflict', {
      name: 'greet.md',
    });
    expect((await screen.findAllByText('greet.md already exists')).length).toBeGreaterThan(0);
  });

  it('passes package-relative nextPath to source rename', async () => {
    const onMutation = vi.fn();
    const source = {
      list: vi.fn().mockResolvedValue({ items: [agentCommandDocument()], availableScopes: [] }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument()),
      create: vi.fn(),
      update: vi.fn(),
      move: vi.fn().mockResolvedValue(
        documentMutation(agentCommandDocument('prompts/b.md')),
      ),
      remove: vi.fn(),
    };

    renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType="commands"
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={onMutation}
      />,
    );

    await userEvent.click(await screen.findByText('a'));
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.more' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'shared.documentWorkflow.metadata.actions.rename' }));
    await userEvent.clear(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'b.md');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));

    expect(source.move).toHaveBeenCalledWith(
      expect.objectContaining({
        id: 'prompts/b.md',
        metadata: expect.objectContaining({ previousFileName: 'prompts/a.md' }),
      }),
      'prompts/b.md',
    );
  });

  it('rejects rename when the target marketplace document already exists', async () => {
    const onMutation = vi.fn();
    const source = {
      list: vi.fn().mockResolvedValue({
        items: [
          agentCommandDocument('prompts/a.md'),
          agentCommandDocument('prompts/b.md'),
        ],
        availableScopes: [],
      }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument()),
      create: vi.fn(),
      update: vi.fn(),
      move: vi.fn(),
      remove: vi.fn(),
    };

    renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType="commands"
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={onMutation}
      />,
    );

    await userEvent.click(await screen.findByText('a'));
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.more' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'shared.documentWorkflow.metadata.actions.rename' }));
    await userEvent.clear(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'b.md');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));

    expect(source.move).not.toHaveBeenCalled();
    expect(translateMock).toHaveBeenCalledWith('shared.documentWorkflow.metadata.errors.conflict', {
      name: 'b.md',
    });
    expect((await screen.findAllByText('b.md already exists')).length).toBeGreaterThan(0);
  });

  it('rejects nested rename when the target marketplace document already exists', async () => {
    const onMutation = vi.fn();
    const source = {
      list: vi.fn().mockResolvedValue({
        items: [
          agentCommandDocument('prompts/a.md'),
          agentCommandDocument('prompts/team/b.md'),
        ],
        availableScopes: [],
      }),
      loadContent: vi.fn().mockResolvedValue(agentCommandDocument()),
      create: vi.fn(),
      update: vi.fn(),
      move: vi.fn(),
      remove: vi.fn(),
    };

    renderResourcePage(
      <MarketplaceDocumentResourcePage
        targetClient="codex"
        packageId="toolkit"
        resourceType="commands"
        initialRevision="rev1"
        sourceAdapter={source}
        onMutation={onMutation}
      />,
    );

    await userEvent.click(await screen.findByText('a'));
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.more' }));
    await userEvent.click(screen.getByRole('menuitem', { name: 'shared.documentWorkflow.metadata.actions.rename' }));
    await userEvent.clear(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'));
    await userEvent.type(screen.getByLabelText('shared.documentWorkflow.metadata.fileName.label'), 'team/b.md');
    await userEvent.click(screen.getByRole('button', { name: 'shared.documentWorkflow.metadata.actions.rename' }));

    expect(source.move).not.toHaveBeenCalled();
    expect(translateMock).toHaveBeenCalledWith('shared.documentWorkflow.metadata.errors.conflict', {
      name: 'b.md',
    });
    expect((await screen.findAllByText('b.md already exists')).length).toBeGreaterThan(0);
  });
});
