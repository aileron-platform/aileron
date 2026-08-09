import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplacePackageCard } from './MarketplacePackageCard';
import type { MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const packageItem: MarketplacePackageSummary = {
  provider: 'claude-code',
  packageType: 'plugin',
  packageId: 'workspace-tools',
  displayName: 'Workspace Tools',
  version: '0.1.0',
  description: 'Workspace helpers.',
  category: 'productivity',
  tags: ['claude.md', 'slash command', 'skill'],
  sourceType: 'created',
  indexedResourceNames: ['hooks/pre-submit.json', 'mcp/server.json', 'subagent.md', 'output-style.md'],
  validationSeverity: 'none',
  lifecycleStatus: 'ready',
  registryPath: 'claude-code/plugins/workspace-tools',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [{
    provider: 'claude-code',
    packageId: 'workspace-tools',
    displayName: 'Workspace Tools',
    registryPath: 'claude-code/plugins/workspace-tools',
    revision: 'rev-1',
  }, {
    provider: 'codex',
    packageId: 'workspace-tools',
    displayName: 'Workspace Tools',
    registryPath: 'codex/plugins/workspace-tools',
    revision: 'rev-2',
  }],
};

describe('MarketplacePackageCard', () => {
  it('renders provider-specific feature badges and dispatches card actions', async () => {
    const user = userEvent.setup();
    const onOpenDetail = vi.fn();
    const onInstall = vi.fn();
    const onExport = vi.fn();
    const onEdit = vi.fn();
    const onDelete = vi.fn();

    render(
      <MarketplacePackageCard
        item={packageItem}
        onOpenDetail={onOpenDetail}
        onInstall={onInstall}
        onExport={onExport}
        onEdit={onEdit}
        onDelete={onDelete}
      />,
    );

    expect(screen.getByText('marketplace.features.claudeMd')).toBeInTheDocument();
    expect(screen.getByText('marketplace.providers.claude-code')).toBeInTheDocument();
    expect(screen.getByText('marketplace.providers.codex')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.hooks')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.mcp')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.subagents')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.slashCommands')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.outputStyle')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.skills')).toBeInTheDocument();
    expect(screen.getByText('marketplace.lifecycle.ready')).toBeInTheDocument();

    await user.click(screen.getByText('Workspace Tools'));
    expect(onOpenDetail).toHaveBeenCalledWith(packageItem);

    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.install' }));
    await user.click(screen.getByRole('button', { name: 'marketplace.center.card.actions.export' }));
    expect(onInstall).toHaveBeenCalledWith(packageItem);
    expect(onExport).toHaveBeenCalledWith(packageItem);

    await user.click(screen.getByRole('button', { name: '' }));
    await user.click(screen.getByRole('menuitem', { name: 'marketplace.center.card.actions.edit' }));
    await user.click(screen.getByRole('button', { name: '' }));
    await user.click(screen.getByRole('menuitem', { name: 'marketplace.center.card.actions.delete' }));
    expect(onEdit).toHaveBeenCalledWith(packageItem);
    expect(onDelete).toHaveBeenCalledWith(packageItem);
  });

  it('renders draft lifecycle state and explains why install is disabled', () => {
    render(
      <MarketplacePackageCard
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

  it('does not render actions whose capability callback is unavailable', () => {
    render(
      <MarketplacePackageCard
        item={packageItem}
        onOpenDetail={vi.fn()}
      />,
    );

    expect(
      screen.queryByRole('button', {
        name: 'marketplace.center.card.actions.install',
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', {
        name: 'marketplace.center.card.actions.export',
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '' }),
    ).not.toBeInTheDocument();
  });
});
