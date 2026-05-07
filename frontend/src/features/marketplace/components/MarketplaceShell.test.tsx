import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceShell } from './MarketplaceShell';

vi.mock('@/app/components/navigation/GlobalNavigation', () => ({
  GlobalNavigation: () => <nav>global-navigation</nav>,
}));

describe('MarketplaceShell', () => {
  it('renders global navigation and Marketplace content inside the shell', () => {
    render(
      <MarketplaceShell>
        <main>marketplace-content</main>
      </MarketplaceShell>,
    );

    expect(screen.getByText('global-navigation')).toBeInTheDocument();
    expect(screen.getByText('marketplace-content')).toBeInTheDocument();
  });
});
