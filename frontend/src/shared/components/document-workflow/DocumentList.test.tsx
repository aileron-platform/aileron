import React from 'react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@/__tests__/utils/render';
import { DocumentList, type DocumentListItem } from './DocumentList';

const items: DocumentListItem[] = [
  { id: 'alpha', label: 'Alpha', description: 'alpha.md' },
  { id: 'beta', label: 'Beta', description: 'beta.md' },
];

const labels = {
  loading: 'shared.documentWorkflow.sidebar.loading',
  empty: 'shared.documentWorkflow.sidebar.empty',
  dirty: 'shared.documentWorkflow.sidebar.dirty',
};

describe('DocumentList', () => {
  it('renders rows, dirty indicator, metadata, and no sidebar shell', () => {
    render(
      <DocumentList
        items={items}
        selectedId="beta"
        onSelect={vi.fn()}
        labels={labels}
        getDirty={(item) => item.id === 'beta'}
        renderItemMeta={(item) => <span>{`${item.id}-meta`}</span>}
      />,
    );

    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('beta-meta')).toBeInTheDocument();
    expect(screen.getByLabelText(labels.dirty)).toBeInTheDocument();

    const row = screen.getByRole('button', { name: /Beta/ });
    expect(row.closest('.border-r')).toBeNull();
    expect(row.closest('.overflow-y-auto')).toBeNull();
  });

  it('renders loading and empty states without creating a scroll container', () => {
    const { rerender } = render(
      <DocumentList
        items={[]}
        selectedId={null}
        onSelect={vi.fn()}
        labels={labels}
        isLoading
      />,
    );

    expect(screen.getByText(labels.loading)).toBeInTheDocument();
    expect(screen.getByText(labels.loading).closest('.overflow-y-auto')).toBeNull();

    rerender(
      <DocumentList
        items={[]}
        selectedId={null}
        onSelect={vi.fn()}
        labels={labels}
      />,
    );

    expect(screen.getByText(labels.empty)).toBeInTheDocument();
    expect(screen.getByText(labels.empty).closest('.overflow-y-auto')).toBeNull();
  });

  it('opens item context menu on row right click', async () => {
    const user = userEvent.setup();

    render(
      <DocumentList
        items={items}
        selectedId="alpha"
        onSelect={vi.fn()}
        labels={labels}
        renderItemContextMenu={(item) => (
          <button type="button" role="menuitem">
            {`rename-${item.id}`}
          </button>
        )}
      />,
    );

    await user.pointer({ keys: '[MouseRight]', target: screen.getByText('Beta') });

    expect(screen.getByRole('menu')).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'rename-beta' })).toBeInTheDocument();
  });

  it('clears selection when emptySelectionBehavior is clearOnEmpty', async () => {
    const onSelect = vi.fn();

    render(
      <DocumentList
        items={[]}
        selectedId="alpha"
        onSelect={onSelect}
        labels={labels}
        emptySelectionBehavior="clearOnEmpty"
      />,
    );

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(null));
  });

  it('clears selection by default when items are empty', async () => {
    const onSelect = vi.fn();

    render(
      <DocumentList
        items={[]}
        selectedId="alpha"
        onSelect={onSelect}
        labels={labels}
      />,
    );

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(null));
  });

  it('preserves selection when emptySelectionBehavior is preserveOnEmpty', async () => {
    const onSelect = vi.fn();

    render(
      <DocumentList
        items={[]}
        selectedId="alpha"
        onSelect={onSelect}
        labels={labels}
        emptySelectionBehavior="preserveOnEmpty"
      />,
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(onSelect).not.toHaveBeenCalled();
  });
});
