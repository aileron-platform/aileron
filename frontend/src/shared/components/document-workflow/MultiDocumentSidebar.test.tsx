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

import { MultiDocumentSidebar, type MultiDocumentSidebarItem } from './MultiDocumentSidebar';

const items: MultiDocumentSidebarItem[] = [
  { id: 'alpha', label: 'Alpha', description: 'alpha.md' },
  { id: 'beta', label: 'Beta', description: 'beta.md' },
];

const labels = {
  searchPlaceholder: 'shared.documentWorkflow.sidebar.searchPlaceholder',
  loading: 'shared.documentWorkflow.sidebar.loading',
  empty: 'shared.documentWorkflow.sidebar.empty',
  dirty: 'shared.documentWorkflow.sidebar.dirty',
};

describe('MultiDocumentSidebar', () => {
  it('renders items, actions, and a dirty indicator without search', () => {
    render(
      <MultiDocumentSidebar
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
  });

  it('renders search input only when search is enabled', async () => {
    const user = userEvent.setup();
    const onSearchChange = vi.fn();

    render(
      <MultiDocumentSidebar
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
      <MultiDocumentSidebar
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
      <MultiDocumentSidebar
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
});
