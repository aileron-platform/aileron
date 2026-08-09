import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';
import { MarketplacePackageListRow } from './MarketplacePackageListRow';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const packageItem: MarketplacePackageSummary = {
  provider: 'codex',
  packageType: 'plugin',
  packageId: 'figma-context',
  displayName: 'Figma Context',
  version: '0.1.0',
  description: 'Figma context plugin.',
  category: 'coding',
  tags: ['mcp'],
  sourceType: 'created',
  indexedResourceNames: ['mcp'],
  validationSeverity: 'none',
  lifecycleStatus: 'ready',
  registryPath: 'codex/plugins/figma-context',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [{
    provider: 'codex',
    packageId: 'figma-context',
    displayName: 'Figma Context',
    registryPath: 'codex/plugins/figma-context',
    revision: 'rev-1',
  }, {
    provider: 'claude-code',
    packageId: 'figma-context',
    displayName: 'Figma Context',
    registryPath: 'claude-code/plugins/figma-context',
    revision: 'rev-2',
  }],
};

describe('MarketplacePackageListRow', () => {
  it('renders package metadata and dispatches row actions', async () => {
    const user = userEvent.setup();
    const onOpenDetail = vi.fn();
    const onInstall = vi.fn();
    const onExport = vi.fn();
    const onEdit = vi.fn();
    const onDelete = vi.fn();

    render(
      <MarketplacePackageListRow
        item={packageItem}
        onOpenDetail={onOpenDetail}
        onInstall={onInstall}
        onExport={onExport}
        onEdit={onEdit}
        onDelete={onDelete}
      />,
    );

    expect(screen.getByText('Figma Context')).toBeInTheDocument();
    expect(screen.getByText('figma-context')).toBeInTheDocument();
    expect(screen.getByText('Figma context plugin.')).toBeInTheDocument();
    expect(screen.getAllByText('marketplace.providers.codex').length).toBeGreaterThan(0);
    expect(screen.getByText('marketplace.providers.claude-code')).toBeInTheDocument();
    expect(screen.getByText('coding')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Figma Context/ }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.install' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.export' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.edit' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.delete' }));

    expect(onOpenDetail).toHaveBeenCalledWith(packageItem);
    expect(onInstall).toHaveBeenCalledWith(packageItem);
    expect(onExport).toHaveBeenCalledWith(packageItem);
    expect(onEdit).toHaveBeenCalledWith(packageItem);
    expect(onDelete).toHaveBeenCalledWith(packageItem);
  });

  it('does not render actions when capability callbacks are unavailable', () => {
    render(
      <MarketplacePackageListRow
        item={packageItem}
        onOpenDetail={vi.fn()}
      />,
    );

    expect(screen.queryByRole('button', { name: 'marketplace.center.card.actions.install' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'marketplace.center.card.actions.export' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'marketplace.center.card.actions.edit' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'marketplace.center.card.actions.delete' })).not.toBeInTheDocument();
  });

  it('shows draft state and disables install even when an action is supplied', () => {
    render(
      <MarketplacePackageListRow
        item={{ ...packageItem, lifecycleStatus: 'draft' }}
        onOpenDetail={vi.fn()}
        onInstall={vi.fn()}
      />,
    );

    expect(screen.getByText('marketplace.lifecycle.draft')).toBeInTheDocument();
    const installButton = screen.getByRole('button', {
      name: 'marketplace.center.card.actions.install',
    });
    expect(installButton).toBeDisabled();
    expect(installButton).toHaveAttribute(
      'title',
      'marketplace.lifecycle.draftInstallDisabled',
    );
  });
});
