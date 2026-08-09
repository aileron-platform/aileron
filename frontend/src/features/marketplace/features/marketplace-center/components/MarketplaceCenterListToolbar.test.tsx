import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceCenterListToolbar } from './MarketplaceCenterListToolbar';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceCenterListToolbar', () => {
  it('renders list stats and dispatches view mode changes', async () => {
    const user = userEvent.setup();
    const onViewModeChange = vi.fn();

    render(
      <MarketplaceCenterListToolbar
        viewMode="grid"
        visibleCount={2}
        totalCount={5}
        currentPage={1}
        totalPages={3}
        onViewModeChange={onViewModeChange}
      />,
    );

    expect(screen.getByText('marketplace.center.list.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.center.list.stats.visible')).toBeInTheDocument();
    expect(screen.getByText('marketplace.center.list.stats.page')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.center.viewModes.list' }));

    expect(onViewModeChange).toHaveBeenCalledWith('list');
  });
});
