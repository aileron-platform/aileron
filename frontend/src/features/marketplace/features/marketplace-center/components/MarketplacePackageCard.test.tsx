import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MarketplacePackageCard } from './MarketplacePackageCard';
import type { MarketplacePackageSummary } from '@/shared/types/marketplace';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const packageItem: MarketplacePackageSummary = {
  provider: 'gemini',
  packageType: 'extension',
  packageId: 'workspace-tools',
  displayName: 'Workspace Tools',
  version: '0.1.0',
  description: 'Workspace helpers.',
  category: 'productivity',
  tags: ['gemini.md', 'slash command', 'skill'],
  sourceType: 'created',
  indexedResourceNames: ['hooks/pre-submit.json', 'mcp/server.json', 'subagent.md', 'output-style.md'],
  validationSeverity: 'none',
  registryPath: 'gemini/extensions/workspace-tools',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [{
    provider: 'gemini',
    packageId: 'workspace-tools',
    displayName: 'Workspace Tools',
    registryPath: 'gemini/extensions/workspace-tools',
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

    expect(screen.getByText('marketplace.features.geminiMd')).toBeInTheDocument();
    expect(screen.getByText('marketplace.providers.gemini')).toBeInTheDocument();
    expect(screen.getByText('marketplace.providers.codex')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.hooks')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.mcp')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.subagents')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.slashCommands')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.outputStyle')).toBeInTheDocument();
    expect(screen.getByText('marketplace.features.skills')).toBeInTheDocument();

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
});
