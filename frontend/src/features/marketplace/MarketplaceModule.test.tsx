import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MarketplaceModule } from './MarketplaceModule';

const mockCenterState = vi.hoisted(() => ({
  shouldThrow: false,
}));
const marketplaceSettingsPageMock = vi.hoisted(() => vi.fn());
const authState = vi.hoisted(() => ({ isPlatformAdmin: true, isLoading: false }));

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/features/auth/public', () => ({
  AuthorizationDeniedState: () => <div role="alert">access-denied</div>,
  useAuth: () => authState,
}));

vi.mock('@/shared/components/shell', () => ({
  ProductShell: ({
    topBar,
    header,
    body,
  }: {
    topBar?: React.ReactNode;
    header?: React.ReactNode;
    body: { kind: 'state' | 'regions'; content?: React.ReactNode };
  }) => (
    <div data-testid="product-shell">
      {topBar}
      {header}
      {body.kind === 'state' ? body.content : null}
    </div>
  ),
}));

vi.mock('./features/marketplace-center/MarketplaceCenterPage', () => ({
  MarketplaceCenterPage: () => {
    if (mockCenterState.shouldThrow) {
      throw new Error('forced marketplace center failure');
    }
    return <div>marketplace-center</div>;
  },
}));

vi.mock('./features/marketplace-detail/MarketplaceDetailPage', () => ({
  MarketplaceDetailPage: () => <div>marketplace-detail</div>,
}));

vi.mock('./features/marketplace-editor/MarketplaceEditorPage', () => ({
  MarketplaceEditorPage: ({ mode }: { mode: string }) => <div>marketplace-editor-{mode}</div>,
}));

vi.mock('./features/marketplace-settings/MarketplaceSettingsPage', () => ({
  MarketplaceSettingsPage: ({ userId }: { userId: string | null }) => {
    marketplaceSettingsPageMock(userId);
    return <div>marketplace-settings</div>;
  },
}));

const renderMarketplaceRoute = (initialEntry: string) => render(
  <MemoryRouter initialEntries={[initialEntry]}>
    <Routes>
      <Route
        path="/marketplace/*"
        element={<MarketplaceModule navigationSlot={<div>global-navigation</div>} userId="user-123" />}
      />
    </Routes>
  </MemoryRouter>,
);

describe('MarketplaceModule', () => {
  beforeEach(() => {
    mockCenterState.shouldThrow = false;
    marketplaceSettingsPageMock.mockClear();
    authState.isPlatformAdmin = true;
  });

  it('redirects the Marketplace root route to packages', async () => {
    renderMarketplaceRoute('/marketplace');

    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
  });

  it('guards invalid targetClient package routes', async () => {
    renderMarketplaceRoute('/marketplace/packages/unknown-targetClient/package-a/edit');

    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
    expect(screen.queryByText('marketplace-editor-edit')).not.toBeInTheDocument();
  });

  it('guards removed Gemini package routes', async () => {
    renderMarketplaceRoute('/marketplace/packages/gemini/package-a/edit');

    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
    expect(screen.queryByText('marketplace-editor-edit')).not.toBeInTheDocument();
  });

  it('renders valid package edit routes', async () => {
    renderMarketplaceRoute('/marketplace/packages/codex/package-a/edit');

    expect(await screen.findByText('marketplace-editor-edit')).toBeInTheDocument();
  });

  it('does not mount the Marketplace editor for a member', async () => {
    authState.isPlatformAdmin = false;

    renderMarketplaceRoute('/marketplace/packages/codex/package-a/edit');

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'access-denied',
    );
    expect(screen.queryByText('marketplace-editor-edit')).not.toBeInTheDocument();
  });

  it('mounts the edit editor for /edit and /edit/:section', async () => {
    const base = renderMarketplaceRoute('/marketplace/packages/claude-code/pkg/edit');
    expect(await screen.findByText('marketplace-editor-edit')).toBeInTheDocument();
    base.unmount();

    renderMarketplaceRoute('/marketplace/packages/claude-code/pkg/edit/skills');
    expect(await screen.findByText('marketplace-editor-edit')).toBeInTheDocument();
  });

  it('redirects removed package create routes to the Marketplace center', async () => {
    const base = renderMarketplaceRoute('/marketplace/packages/new');
    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
    base.unmount();

    renderMarketplaceRoute('/marketplace/packages/new/skills');
    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
  });

  it('renders settings, create, detail, and wildcard routes through the Marketplace shell', async () => {
    const settings = renderMarketplaceRoute('/marketplace/packages/settings');
    expect(await screen.findByText('marketplace-settings')).toBeInTheDocument();
    expect(marketplaceSettingsPageMock).toHaveBeenCalledWith('user-123');
    settings.unmount();

    const create = renderMarketplaceRoute('/marketplace/packages/new');
    expect(await screen.findByText('marketplace-center')).toBeInTheDocument();
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
