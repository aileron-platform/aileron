import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceCenterHeaderActions } from './MarketplaceCenterHeaderActions';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceCenterHeaderActions', () => {
  it('renders permitted actions and dispatches clicks', async () => {
    const user = userEvent.setup();
    const onImport = vi.fn();
    const onCreate = vi.fn();
    const onSettings = vi.fn();
    const onRefresh = vi.fn();

    render(
      <MarketplaceCenterHeaderActions
        permissions={{
          canImport: true,
          canEdit: true,
          canManageRegistry: true,
        }}
        onImport={onImport}
        onCreate={onCreate}
        onSettings={onSettings}
        onRefresh={onRefresh}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.import' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.create' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.settings' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.actions.refresh' }));

    expect(onImport).toHaveBeenCalled();
    expect(onCreate).toHaveBeenCalled();
    expect(onSettings).toHaveBeenCalled();
    expect(onRefresh).toHaveBeenCalled();
  });

  it('hides restricted actions and keeps refresh available', () => {
    render(
      <MarketplaceCenterHeaderActions
        permissions={{
          canImport: false,
          canEdit: false,
          canManageRegistry: false,
        }}
        onImport={vi.fn()}
        onCreate={vi.fn()}
        onSettings={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.queryByRole('button', { name: 'marketplace.center.actions.import' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'marketplace.center.actions.create' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'marketplace.center.actions.settings' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'marketplace.center.actions.refresh' })).toBeInTheDocument();
  });
});
