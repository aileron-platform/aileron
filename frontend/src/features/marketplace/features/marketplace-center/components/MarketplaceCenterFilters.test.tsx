import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceCenterFilters } from './MarketplaceCenterFilters';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceCenterFilters', () => {
  it('renders filters and dispatches filter changes', async () => {
    const user = userEvent.setup();
    const onSearchTermChange = vi.fn();
    const onTargetClientChange = vi.fn();
    const onActiveFeaturesChange = vi.fn();
    const onCategoryChange = vi.fn();
    const onResetFilters = vi.fn();

    const Harness = () => {
      const [searchTerm, setSearchTerm] = React.useState('');
      const handleSearchTermChange = (value: string) => {
        setSearchTerm(value);
        onSearchTermChange(value);
      };
      return (
        <MarketplaceCenterFilters
          searchTerm={searchTerm}
          targetClient="all"
          activeFeatures={new Set()}
          category="all"
          categories={['coding']}
          onSearchTermChange={handleSearchTermChange}
          onTargetClientChange={onTargetClientChange}
          onActiveFeaturesChange={onActiveFeaturesChange}
          onCategoryChange={onCategoryChange}
          onResetFilters={onResetFilters}
        />
      );
    };

    render(<Harness />);

    await user.type(screen.getByPlaceholderText('marketplace.center.filters.searchPlaceholder'), 'figma');
    await user.click(screen.getByRole('button', { name: 'marketplace.targetClients.codex' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.features.mcp' }));
    await user.click(screen.getByRole('button', { name: 'coding' }));
    await user.click(screen.getAllByRole('button', { name: 'marketplace.center.filters.clear' })[0]);

    expect(onSearchTermChange).toHaveBeenLastCalledWith('figma');
    expect(onTargetClientChange).toHaveBeenCalledWith('codex');
    expect(onActiveFeaturesChange).toHaveBeenCalledWith(new Set(['mcp']));
    expect(onCategoryChange).toHaveBeenCalledWith('coding');
    expect(onResetFilters).toHaveBeenCalled();
  });
});
