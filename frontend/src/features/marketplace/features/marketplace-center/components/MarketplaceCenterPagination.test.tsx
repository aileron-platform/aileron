import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceCenterPagination } from './MarketplaceCenterPagination';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceCenterPagination', () => {
  it('dispatches page and page-size changes', async () => {
    const user = userEvent.setup();
    const onPageChange = vi.fn();
    const onPageSizeChange = vi.fn();

    render(
      <MarketplaceCenterPagination
        page={2}
        totalPages={3}
        pageSize={12}
        onPageChange={onPageChange}
        onPageSizeChange={onPageSizeChange}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'marketplace.center.pagination.previous' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.pagination.next' }));
    await user.click(screen.getAllByRole('button', { name: 'marketplace.center.pagination.perPageOption' })[2]);

    expect(onPageChange).toHaveBeenCalledWith(1);
    expect(onPageChange).toHaveBeenCalledWith(3);
    expect(onPageSizeChange).toHaveBeenCalledWith(24);
  });
});
