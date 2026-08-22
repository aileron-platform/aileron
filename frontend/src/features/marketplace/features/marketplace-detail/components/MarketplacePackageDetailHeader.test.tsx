import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import type { MarketplaceActionPermissions } from '../../../model/marketplacePermissions';
import { MarketplacePackageDetailHeader } from './MarketplacePackageDetailHeader';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

const detail = {
  packageId: 'pkg.test',
  targetClient: 'codex',
  displayName: 'Test package',
  version: '1.2.3',
  category: 'tools',
} as MarketplacePackageDetail;

const permissions: MarketplaceActionPermissions = {
  canEdit: true,
  canDelete: true,
  canExport: true,
  canInstall: true,
  canManageRegistry: true,
};

const renderHeader = (ui: React.ReactElement) => render(
  <MemoryRouter>
    {ui}
  </MemoryRouter>,
);

describe('MarketplacePackageDetailHeader', () => {
  it('renders package metadata and dispatches visible actions', () => {
    const handlers = {
      onBack: vi.fn(),
      onEdit: vi.fn(),
      onExport: vi.fn(),
      onInstall: vi.fn(),
      onDelete: vi.fn(),
    };

    renderHeader(
      <MarketplacePackageDetailHeader
        detail={detail}
        permissions={permissions}
        breadcrumbs={[
          { label: 'marketplace.breadcrumbs.root', to: '/marketplace' },
          { label: 'marketplace.center.header.title', to: '/marketplace/packages' },
        ]}
        {...handlers}
      />,
    );

    expect(screen.getByText('marketplace.breadcrumbs.root')).toBeInTheDocument();
    expect(screen.getByText('marketplace.center.header.title')).toBeInTheDocument();
    expect(screen.getByText('Test package')).toBeInTheDocument();
    expect(screen.getByText(/marketplace.detail.header.version/)).toBeInTheDocument();
    expect(screen.getByText(/marketplace.detail.header.targetClient/)).toBeInTheDocument();
    expect(screen.getByText(/marketplace.detail.header.category/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /marketplace.detail.actions.back/ }));
    fireEvent.click(screen.getByRole('button', { name: /marketplace.detail.actions.edit/ }));
    fireEvent.click(screen.getByRole('button', { name: /marketplace.detail.actions.export/ }));
    fireEvent.click(screen.getByRole('button', { name: /marketplace.detail.actions.install/ }));
    fireEvent.click(screen.getByRole('button', { name: /marketplace.detail.actions.delete/ }));

    expect(handlers.onBack).toHaveBeenCalledTimes(1);
    expect(handlers.onEdit).toHaveBeenCalledTimes(1);
    expect(handlers.onExport).toHaveBeenCalledTimes(1);
    expect(handlers.onInstall).toHaveBeenCalledTimes(1);
    expect(handlers.onDelete).toHaveBeenCalledTimes(1);
  });

  it('hides action buttons when permissions are disabled', () => {
    renderHeader(
      <MarketplacePackageDetailHeader
        detail={detail}
        permissions={{
          ...permissions,
          canEdit: false,
          canDelete: false,
          canExport: false,
          canInstall: false,
        }}
        breadcrumbs={[
          { label: 'marketplace.breadcrumbs.root', to: '/marketplace' },
          { label: 'marketplace.center.header.title', to: '/marketplace/packages' },
        ]}
        onBack={vi.fn()}
        onEdit={vi.fn()}
        onExport={vi.fn()}
        onInstall={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: /marketplace.detail.actions.back/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /marketplace.detail.actions.edit/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /marketplace.detail.actions.export/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /marketplace.detail.actions.install/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /marketplace.detail.actions.delete/ })).not.toBeInTheDocument();
  });
});
