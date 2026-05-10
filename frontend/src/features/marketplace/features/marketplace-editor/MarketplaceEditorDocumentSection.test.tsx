import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Bot } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';

import { MarketplaceMarkdownEditorViewer } from './MarketplaceEditorDocumentSection';
import type { MarketplaceEditorResourceItem } from './marketplaceEditorResourceItems';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownEditor', () => ({
  MarkdownEditor: ({ value, onChange, placeholder }: {
    value: string;
    onChange: (value: string) => void;
    placeholder?: string;
  }) => (
    <textarea
      aria-label={placeholder ?? 'markdown-editor'}
      value={value}
      onChange={event => onChange(event.target.value)}
    />
  ),
}));

vi.mock('@/shared/components/file-workbench/viewer-entry', () => ({
  CodeTextEditor: ({ content, onContentChange, fileName }: {
    content: string;
    onContentChange: (content: string) => void;
    fileName: string;
  }) => (
    <textarea
      aria-label={fileName}
      value={content}
      onChange={event => onContentChange(event.target.value)}
    />
  ),
}));

const items: MarketplaceEditorResourceItem[] = [
  {
    id: 'alpha',
    title: 'Alpha',
    description: 'Alpha agent',
    path: 'agents/alpha.md',
    content: '# Alpha',
    badge: 'md',
  },
  {
    id: 'beta',
    title: 'Beta',
    description: 'Beta agent',
    path: 'agents/beta.md',
    content: '# Beta',
    badge: 'md',
  },
];

const renderDocumentViewer = (initialItems: MarketplaceEditorResourceItem[] = items) => {
  const callbacks = {
    onDirty: vi.fn(),
    onItemsChange: vi.fn(),
  };

  render(
    <MarketplaceMarkdownEditorViewer
      tab="agents"
      icon={Bot}
      items={initialItems}
      commitVersion={0}
      discardVersion={0}
      {...callbacks}
    />,
  );

  return callbacks;
};

describe('MarketplaceMarkdownEditorViewer', () => {
  it('creates a markdown resource and emits materialized items', async () => {
    const callbacks = renderDocumentViewer([]);

    fireEvent.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.actions.add' }));
    fireEvent.change(screen.getByLabelText('marketplace.editor.documentViewer.create.fields.path.label'), {
      target: { value: 'agents/new-agent' },
    });
    fireEvent.change(screen.getByLabelText('marketplace.editor.documentViewer.editor.placeholder'), {
      target: { value: '# New agent' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.create.actions.create' }));

    await waitFor(() => {
      expect(callbacks.onItemsChange).toHaveBeenLastCalledWith([
        expect.objectContaining({
          path: 'agents/new-agent.md',
          content: '# New agent',
        }),
      ]);
    });
    expect(callbacks.onDirty).toHaveBeenCalled();
  });

  it('selects, edits, and renames resources without mutating other drafts', async () => {
    const user = userEvent.setup();
    const callbacks = renderDocumentViewer();

    fireEvent.click(screen.getByText('beta.md'));
    fireEvent.change(screen.getByLabelText('marketplace.editor.documentViewer.editor.placeholder'), {
      target: { value: '# Updated beta' },
    });
    await user.click(screen.getByRole('button', { name: 'marketplace.editor.documentViewer.actions.more' }));
    await user.click(await screen.findByText('marketplace.editor.common.rename.action'));
    fireEvent.change(screen.getByPlaceholderText('marketplace.editor.common.rename.pathPlaceholder'), {
      target: { value: 'agents/renamed-beta.md' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'marketplace.common.actions.save' }));

    await waitFor(() => {
      expect(callbacks.onItemsChange).toHaveBeenLastCalledWith([
        expect.objectContaining({ path: 'agents/alpha.md', content: '# Alpha' }),
        expect.objectContaining({ path: 'agents/renamed-beta.md', content: '# Updated beta' }),
      ]);
    });
    expect(callbacks.onDirty).toHaveBeenCalled();
  });
});
