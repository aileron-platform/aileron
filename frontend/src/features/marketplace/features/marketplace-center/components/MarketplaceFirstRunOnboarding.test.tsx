import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceFirstRunOnboarding } from './MarketplaceFirstRunOnboarding';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => (
      params?.path ? `${key}:${params.path}` : key
    ),
  }),
}));

describe('MarketplaceFirstRunOnboarding', () => {
  it('renders onboarding content and dispatches setup actions', async () => {
    const user = userEvent.setup();
    const onInitialize = vi.fn();
    const onClone = vi.fn();

    render(
      <MarketplaceFirstRunOnboarding
        rootPath="~/.ai-developer-hub/marketplace"
        canManageRegistry
        onInitialize={onInitialize}
        onClone={onClone}
      />,
    );

    expect(screen.getByText('marketplace.onboarding.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.onboarding.setupTitle')).toBeInTheDocument();
    expect(screen.getByText('marketplace.onboarding.rootPath:~/.ai-developer-hub/marketplace')).toBeInTheDocument();

    const setupCard = screen.getByText('marketplace.onboarding.setupTitle').closest('.max-w-2xl');
    expect(setupCard?.parentElement).toHaveClass('flex-1', 'items-center', 'justify-center');
    expect(setupCard?.parentElement?.parentElement).toHaveClass(
      'h-full',
      'min-h-0',
      'min-w-0',
      'flex-1',
    );
    expect(screen.getByText('marketplace.onboarding.description').parentElement?.parentElement)
      .not.toHaveClass('flex-1');

    await user.click(screen.getByRole('button', { name: /marketplace\.onboarding\.actions\.initialize/ }));
    await user.click(screen.getByRole('button', { name: /marketplace\.onboarding\.actions\.clone/ }));

    expect(onInitialize).toHaveBeenCalledTimes(1);
    expect(onClone).toHaveBeenCalledTimes(1);
  });

  it('does not expose repository setup actions without registry management capability', () => {
    render(
      <MarketplaceFirstRunOnboarding
        rootPath="~/.ai-developer-hub/marketplace"
        canManageRegistry={false}
        onInitialize={vi.fn()}
        onClone={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole('button', { name: /marketplace\.onboarding\.actions\.initialize/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /marketplace\.onboarding\.actions\.clone/ }),
    ).not.toBeInTheDocument();
  });
});
