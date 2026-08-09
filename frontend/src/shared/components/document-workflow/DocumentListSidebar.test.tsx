import React from 'react';
import userEvent from '@testing-library/user-event';
import { FileText } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@/__tests__/utils/render';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

import { DocumentListSidebar, type DocumentListSidebarItem } from './DocumentListSidebar';

const items: DocumentListSidebarItem[] = [
  { id: 'alpha', label: 'Alpha', description: 'alpha.md' },
  { id: 'beta', label: 'Beta', description: 'beta.md' },
];

const labels = {
  searchPlaceholder: 'shared.documentWorkflow.sidebar.searchPlaceholder',
  loading: 'shared.documentWorkflow.sidebar.loading',
  empty: 'shared.documentWorkflow.sidebar.empty',
  dirty: 'shared.documentWorkflow.sidebar.dirty',
};

describe('DocumentListSidebar', () => {
  it('renders items, actions, and a dirty indicator without search', () => {
    render(
      <DocumentListSidebar
        title="shared.documentWorkflow.sidebar.title"
        icon={FileText}
        items={items}
        selectedId="beta"
        onSelect={vi.fn()}
        labels={labels}
        actions={<button type="button">shared.documentWorkflow.sidebar.actions.refresh</button>}
        getDirty={(item) => item.id === 'beta'}
        renderItemMeta={(item) => <span>{`${item.id}-meta`}</span>}
      />,
    );

    expect(screen.getByText('shared.documentWorkflow.sidebar.title')).toBeInTheDocument();
    expect(screen.getByText('shared.documentWorkflow.sidebar.actions.refresh')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();
    expect(screen.getByText('beta-meta')).toBeInTheDocument();
    expect(screen.getByLabelText(labels.dirty)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(labels.searchPlaceholder)).not.toBeInTheDocument();

    const row = screen.getByRole('button', { name: /Beta/ });
    expect(row.closest('.border-r')).toBeInTheDocument();
    expect(row.closest('.overflow-y-auto')).toBeInTheDocument();
  });

  it('renders search input only when search is enabled', async () => {
    const user = userEvent.setup();
    const onSearchChange = vi.fn();

    render(
      <DocumentListSidebar
        title="shared.documentWorkflow.sidebar.title"
        icon={FileText}
        items={items}
        selectedId={null}
        onSelect={vi.fn()}
        labels={labels}
        showSearch
        searchValue=""
        onSearchChange={onSearchChange}
      />,
    );

    await user.type(screen.getByPlaceholderText(labels.searchPlaceholder), 'alp');

    expect(onSearchChange).toHaveBeenCalledWith('a');
  });

  it('renders loading and empty states', () => {
    const { rerender } = render(
      <DocumentListSidebar
        title="shared.documentWorkflow.sidebar.title"
        icon={FileText}
        items={[]}
        selectedId={null}
        onSelect={vi.fn()}
        labels={labels}
        isLoading
      />,
    );

    expect(screen.getByText(labels.loading)).toBeInTheDocument();

    rerender(
      <DocumentListSidebar
        title="shared.documentWorkflow.sidebar.title"
        icon={FileText}
        items={[]}
        selectedId={null}
        onSelect={vi.fn()}
        labels={labels}
      />,
    );

    expect(screen.getByText(labels.empty)).toBeInTheDocument();
  });

  it('renders empty search results instead of loading when original items exist', () => {
    render(
      <DocumentListSidebar
        title="shared.documentWorkflow.sidebar.title"
        icon={FileText}
        items={items}
        selectedId="alpha"
        onSelect={vi.fn()}
        labels={labels}
        showSearch
        searchValue="not-found"
        onSearchChange={vi.fn()}
        isLoading
      />,
    );

    expect(screen.getByText(labels.empty)).toBeInTheDocument();
    expect(screen.queryByText(labels.loading)).not.toBeInTheDocument();
  });

  it('hides title and actions but keeps the list when showHeader is false', () => {
    render(
      <DocumentListSidebar
        title="shared.documentWorkflow.sidebar.title"
        icon={FileText}
        items={items}
        selectedId="alpha"
        onSelect={vi.fn()}
        labels={labels}
        actions={<button type="button">shared.documentWorkflow.sidebar.actions.refresh</button>}
        showHeader={false}
      />,
    );

    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.queryByText('shared.documentWorkflow.sidebar.title')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'shared.documentWorkflow.sidebar.actions.refresh' })).not.toBeInTheDocument();
  });

  it('renders title and actions by default', () => {
    render(
      <DocumentListSidebar
        title="shared.documentWorkflow.sidebar.title"
        icon={FileText}
        items={items}
        selectedId="alpha"
        onSelect={vi.fn()}
        labels={labels}
        actions={<button type="button">shared.documentWorkflow.sidebar.actions.refresh</button>}
      />,
    );

    expect(screen.getByText('shared.documentWorkflow.sidebar.title')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'shared.documentWorkflow.sidebar.actions.refresh' })).toBeInTheDocument();
  });

  it('opens item context menu on row right click', async () => {
    const user = userEvent.setup();

    render(
      <DocumentListSidebar
        title="shared.documentWorkflow.sidebar.title"
        icon={FileText}
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
});
