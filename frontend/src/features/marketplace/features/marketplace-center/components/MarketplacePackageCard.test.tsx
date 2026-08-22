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
  targetClient: 'claude-code',
  packageType: 'plugin',
  packageId: 'workspace-tools',
  displayName: 'Workspace Tools',
  version: '0.1.0',
  description: 'Workspace helpers.',
  category: 'productivity',
  tags: ['claude.md', 'slash command', 'skill'],
  indexedResourceNames: ['hooks/pre-submit.json', 'mcp/server.json', 'subagent.md', 'output-style.md'],
  validationSeverity: 'none',
  authoringCapabilities: {
    basic: 'read-write', agentsMd: 'read-write', hooks: 'read-write', mcp: 'read-write',
    agents: 'read-write', commands: 'read-write', outputStyle: 'read-write', skills: 'read-write', files: 'read-write',
  },
  registryPath: 'claude-code/plugins/workspace-tools',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [{
    targetClient: 'claude-code',
    packageFormat: 'claude-native',
    packageId: 'workspace-tools',
    displayName: 'Workspace Tools',
    registryPath: 'claude-code/plugins/workspace-tools',
    revision: 'rev-1',
  }, {
    targetClient: 'codex',
    packageFormat: 'codex-native',
    packageId: 'workspace-tools',
    displayName: 'Workspace Tools',
    registryPath: 'codex/plugins/workspace-tools',
    revision: 'rev-2',
  }],
};

describe('MarketplacePackageCard', () => {
  it('renders targetClient-specific feature badges and dispatches card actions', async () => {
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
    expect(screen.getByText('marketplace.targetClients.claude-code · claude-native')).toBeInTheDocument();
    expect(screen.getByText('marketplace.targetClients.codex · codex-native')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.hooks')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.mcp')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.subagents')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.slashCommands')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.outputStyle')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.skills')).toBeInTheDocument();
    expect(screen.queryByText('marketplace.lifecycle.ready')).not.toBeInTheDocument();

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

  it('keeps install available when validation reports an error', () => {
    render(
      <MarketplacePackageCard
        item={{ ...packageItem, validationSeverity: 'error' }}
        onOpenDetail={vi.fn()}
        onInstall={vi.fn()}
      />,
    );

    expect(screen.getByText('marketplace.validation.severity.error')).toBeInTheDocument();
    const installButton = screen.getByRole('button', {
      name: 'marketplace.center.card.actions.install',
    });
    expect(installButton).toBeEnabled();
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
