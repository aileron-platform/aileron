import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { Network } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceFeatureContentSection } from './MarketplaceFeatureContentSection';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

interface TestItem {
  id: string;
  name: string;
}

const items: TestItem[] = [
  { id: 'alpha', name: 'Alpha' },
  { id: 'beta', name: 'Beta' },
];

describe('MarketplaceFeatureContentSection', () => {
  it('renders title, count, actions, and injected items', () => {
    const onAdd = vi.fn();

    render(
      <MarketplaceFeatureContentSection
        title="MCP"
        icon={Network}
        items={items}
        countLabel="2 items"
        emptyTitle="No items"
        emptyDescription="Add one"
        addLabel="Add"
        onAdd={onAdd}
        getItemKey={item => item.id}
        renderItem={item => <div>{item.name}</div>}
      />,
    );

    expect(screen.getByText('MCP')).toBeInTheDocument();
    expect(screen.getByText('2 items')).toBeInTheDocument();
    expect(screen.getByText('Alpha')).toBeInTheDocument();
    expect(screen.getByText('Beta')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Add/ }));

    expect(onAdd).toHaveBeenCalledTimes(1);
  });

  it('renders empty state and empty add action', () => {
    const onAdd = vi.fn();

    render(
      <MarketplaceFeatureContentSection
        title="MCP"
        icon={Network}
        items={[]}
        countLabel="0 items"
        emptyTitle="No items"
        emptyDescription="Add one"
        addLabel="Add"
        onAdd={onAdd}
        getItemKey={item => item.id}
        renderItem={item => <div>{item.name}</div>}
      />,
    );

    expect(screen.getByText('No items')).toBeInTheDocument();
    expect(screen.getByText('Add one')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: /Add/ })[0]);

    expect(onAdd).toHaveBeenCalledTimes(1);
  });
});
