import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceShellAdapter } from './MarketplaceShellAdapter';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

const navigation = {
  content: ({ collapsed }: { collapsed: boolean }) => (
    <div>{collapsed ? 'navigation-collapsed' : 'navigation-expanded'}</div>
  ),
  accessibleLabel: 'marketplace.navigation',
  preset: 'settings-navigation' as const,
};

const navigator = {
  content: ({ collapsed }: { collapsed: boolean }) => (
    <div>{collapsed ? 'navigator-collapsed' : 'navigator-expanded'}</div>
  ),
  accessibleLabel: 'marketplace.navigator',
  preset: 'settings-navigator' as const,
};

describe('MarketplaceShellAdapter', () => {
  it('maps a settings surface to topBar, header, navigation, and main regions', () => {
    render(
      <MarketplaceShellAdapter
        navigationSlot={<div>global-navigation</div>}
        surface={{
          kind: 'settings',
          header: <div>settings-header</div>,
          navigation,
          navigator,
          main: {
            accessibleLabel: 'marketplace.settings.main',
            content: <div>settings-main</div>,
          },
        }}
      />,
    );

    expect(screen.getByTestId('product-shell')).toBeInTheDocument();
    expect(screen.getByTestId('product-shell')).toHaveTextContent(
      'global-navigationsettings-headernavigation-expandednavigator-expandedsettings-main',
    );
    expect(screen.getByRole('complementary', { name: 'marketplace.navigation' })).toBeInTheDocument();
    const navigatorRegion = screen.getByRole('complementary', { name: 'marketplace.navigator' });
    expect(navigatorRegion).toHaveStyle({ width: '270px' });
    expect(navigatorRegion.querySelector('[role="separator"]')).toBeInTheDocument();
    expect(screen.getByRole('main', { name: 'marketplace.settings.main' })).toBeInTheDocument();
  });

  it('keeps loading and fallback surfaces inside the same ProductShell state body', () => {
    render(
      <MarketplaceShellAdapter
        navigationSlot={<div>global-navigation</div>}
        surface={{ kind: 'state', content: <div>marketplace-loading</div> }}
      />,
    );

    expect(screen.getByTestId('product-shell')).toHaveTextContent('global-navigationmarketplace-loading');
    expect(screen.queryByRole('main')).not.toBeInTheDocument();
    expect(screen.getByTestId('product-shell').querySelector('[data-shell-state]')).toBeInTheDocument();
  });
});
