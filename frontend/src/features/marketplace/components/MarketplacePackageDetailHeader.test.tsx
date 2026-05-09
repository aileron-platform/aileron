import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketplacePackageDetail } from '@/shared/types/marketplace';
import type { MarketplaceActionPermissions } from '../permissions';
import { MarketplacePackageDetailHeader } from './MarketplacePackageDetailHeader';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

const detail = {
  packageId: 'pkg.test',
  provider: 'codex',
  displayName: 'Test package',
  version: '1.2.3',
  category: 'tools',
} as MarketplacePackageDetail;

const permissions: MarketplaceActionPermissions = {
  canView: true,
  canEdit: true,
  canDelete: true,
  canExport: true,
  canImport: true,
  canInstall: true,
  canManageRegistry: true,
};

describe('MarketplacePackageDetailHeader', () => {
  it('renders package metadata and dispatches visible actions', () => {
    const handlers = {
      onBack: vi.fn(),
      onEdit: vi.fn(),
      onExport: vi.fn(),
      onInstall: vi.fn(),
      onDelete: vi.fn(),
    };

    render(<MarketplacePackageDetailHeader detail={detail} permissions={permissions} {...handlers} />);

    expect(screen.getByText('Test package')).toBeInTheDocument();
    expect(screen.getByText(/marketplace.detail.header.version/)).toBeInTheDocument();
    expect(screen.getByText(/marketplace.detail.header.provider/)).toBeInTheDocument();
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
    render(
      <MarketplacePackageDetailHeader
        detail={detail}
        permissions={{
          ...permissions,
          canEdit: false,
          canDelete: false,
          canExport: false,
          canInstall: false,
        }}
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
