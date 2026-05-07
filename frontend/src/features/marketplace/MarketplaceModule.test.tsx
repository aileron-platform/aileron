import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceModule } from './MarketplaceModule';

const mockCenterState = vi.hoisted(() => ({
  shouldThrow: false,
}));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('./components/MarketplaceShell', () => ({
  MarketplaceShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('./features/marketplace-center/MarketplaceCenterView', () => ({
  MarketplaceCenterView: () => {
    if (mockCenterState.shouldThrow) {
      throw new Error('forced marketplace center failure');
    }
    return <div>marketplace-center</div>;
  },
}));

vi.mock('./features/marketplace-detail/MarketplaceDetailView', () => ({
  MarketplaceDetailView: () => <div>marketplace-detail</div>,
}));

vi.mock('./features/marketplace-editor/MarketplaceEditorView', () => ({
  MarketplaceEditorView: ({ mode }: { mode: string }) => <div>marketplace-editor-{mode}</div>,
}));

vi.mock('./features/marketplace-settings/MarketplaceSettingsView', () => ({
  MarketplaceSettingsView: () => <div>marketplace-settings</div>,
}));

const renderMarketplaceRoute = (initialEntry: string) => render(
  <MemoryRouter initialEntries={[initialEntry]}>
    <Routes>
      <Route path="/marketplace/*" element={<MarketplaceModule />} />
    </Routes>
  </MemoryRouter>,
);

describe('MarketplaceModule', () => {
  beforeEach(() => {
    mockCenterState.shouldThrow = false;
  });

  it('redirects the Marketplace root route to packages', async () => {
    renderMarketplaceRoute('/marketplace');

    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
  });

  it('guards invalid provider package routes', async () => {
    renderMarketplaceRoute('/marketplace/packages/unknown-provider/package-a/edit');

    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
    expect(screen.queryByText('marketplace-editor-edit')).not.toBeInTheDocument();
  });

  it('renders valid package edit routes', async () => {
    renderMarketplaceRoute('/marketplace/packages/codex/package-a/edit');

    expect(await screen.findByText('marketplace-editor-edit')).toBeInTheDocument();
  });

  it('renders settings, create, detail, and wildcard routes through the Marketplace shell', async () => {
    const settings = renderMarketplaceRoute('/marketplace/packages/settings');
    expect(await screen.findByText('marketplace-settings')).toBeInTheDocument();
    settings.unmount();

    const create = renderMarketplaceRoute('/marketplace/packages/new');
    expect(await screen.findByText('marketplace-editor-create')).toBeInTheDocument();
    create.unmount();

    const detail = renderMarketplaceRoute('/marketplace/packages/claude-code/review-assistant');
    expect(await screen.findByText('marketplace-detail')).toBeInTheDocument();
    detail.unmount();

    renderMarketplaceRoute('/marketplace/unknown');
    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
  });

  it('renders the localized module fallback when a child route throws', async () => {
    const locationAssign = vi.spyOn(window.location, 'assign').mockImplementation(() => undefined);
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    mockCenterState.shouldThrow = true;

    renderMarketplaceRoute('/marketplace/packages');

    expect(await screen.findByText('marketplace.errors.module.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.errors.module.description')).toBeInTheDocument();

    screen.getByRole('button', { name: 'marketplace.errors.module.action' }).click();
    expect(locationAssign).toHaveBeenCalledWith('/marketplace/packages');

    locationAssign.mockRestore();
    consoleError.mockRestore();
  });
});
