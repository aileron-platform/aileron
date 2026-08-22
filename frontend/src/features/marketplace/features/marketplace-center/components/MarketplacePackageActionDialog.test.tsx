import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithoutRouter } from '@/__tests__/utils/render';
import { MarketplacePackageActionDialog } from './MarketplacePackageActionDialog';
import type { MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';
import {
  installMarketplacePlugin,
  deletePackage,
} from '../../../api/marketplaceApi';
import { fetchWorkspaceList } from '@/features/workspace/public';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => (
      params?.commandName ? `${key}:${params.commandName}` : key
    ),
  }),
}));

const mockExportPackage = vi.fn();

vi.mock('../../../api/marketplaceApi', () => ({
  deletePackage: vi.fn(),
  exportPackage: (...args: unknown[]) => mockExportPackage(...args),
  preflightMarketplaceUserCopy: vi.fn(),
  createMarketplaceUserCopy: vi.fn(),
  installMarketplacePlugin: vi.fn(),
}));

vi.mock('@/features/workspace/public', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/workspace/public')>()),
  fetchWorkspaceList: vi.fn(),
}));

const mockPackage: MarketplacePackageSummary = {
  targetClient: 'codex',
  packageFormat: 'codex-native',
  catalogPluginId: 'aileron-internal/figma-context',
  userCopyTargetClient: 'codex',
  packageType: 'plugin',
  packageId: 'figma-context',
  displayName: 'Figma Context',
  version: '0.1.0',
  description: 'Figma context plugin.',
  category: 'coding',
  tags: ['mcp'],
  indexedResourceNames: ['mcp'],
  validationSeverity: 'none',
  authoringCapabilities: {
    basic: 'read-write', agentsMd: 'read-write', hooks: 'read-write',
    mcp: 'read-write', agents: 'read-write', commands: 'read-write',
    outputStyle: 'unsupported', skills: 'read-write', files: 'read-write',
  },
  registryPath: 'codex/plugins/figma-context',
  revision: 'rev-1',
  updatedAt: '2026-05-07T00:00:00.000Z',
  variants: [],
};

describe('MarketplacePackageActionDialog', () => {
  beforeEach(() => {
    mockExportPackage.mockReset();
    mockExportPackage.mockResolvedValue({ archiveName: 'pkg.zip' });
    vi.mocked(deletePackage).mockReset();
    vi.mocked(installMarketplacePlugin).mockReset();
    vi.mocked(fetchWorkspaceList).mockReset();
    vi.mocked(deletePackage).mockResolvedValue({ deleted: true });
    vi.mocked(installMarketplacePlugin).mockResolvedValue({
      status: 'installed',
      targetClient: 'codex',
      packageId: 'figma-context',
      marketplaceId: 'team-tools',
      workspaceId: 'ws-1',
      operationId: 'a'.repeat(32),
      stage: 'completed',
      exitCode: 0,
      cliMessage: 'Installed',
      stdout: null,
      stderr: null,
      truncated: false,
    });
    vi.mocked(fetchWorkspaceList).mockResolvedValue({
      items: [{
        id: 'ws-1',
        name: 'Workspace One',
        accessRole: 'manager',
        agenticTools: ['codex'],
      }],
    });
  });

  it('exports the selected package and renders the localized success state', async () => {
    const user = userEvent.setup();
    renderWithoutRouter(
      <MarketplacePackageActionDialog
        action={{ type: 'export', item: mockPackage }}
        onOpenChange={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'marketplace.export.actions.export' }));

    await waitFor(() => {
      expect(mockExportPackage).toHaveBeenCalledWith({
        targetClient: 'codex',
        packageFormat: 'codex-native',
        packageId: 'figma-context',
      });
    });
    expect(screen.getByText('marketplace.export.result.ready')).toBeInTheDocument();
  });

  it('uses a localized fallback without rendering a raw export error', async () => {
    const user = userEvent.setup();
    mockExportPackage.mockRejectedValueOnce(new Error('raw CLI credential output'));
    renderWithoutRouter(
      <MarketplacePackageActionDialog
        action={{ type: 'export', item: mockPackage }}
        onOpenChange={vi.fn()}
        onDeleted={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole('button', { name: 'marketplace.export.actions.export' }),
    );

    expect(
      await screen.findByText('marketplace.export.result.failed'),
    ).toBeInTheDocument();
    expect(screen.queryByText('raw CLI credential output')).not.toBeInTheDocument();
  });

  it('only renders a close action after install succeeds', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    renderWithoutRouter(
      <MarketplacePackageActionDialog
        action={{ type: 'install', item: mockPackage }}
        onOpenChange={onOpenChange}
        onDeleted={vi.fn()}
      />,
    );

    expect(
      await screen.findByText('marketplace.install.plugin.publishReady'),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole('button', { name: 'marketplace.install.actions.install' }),
    );

    expect(await screen.findByText('marketplace.install.result.success.plugin')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'marketplace.install.actions.install' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'marketplace.common.actions.cancel' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.close' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('only renders a close action after delete succeeds', async () => {
    const user = userEvent.setup();
    const onOpenChange = vi.fn();
    const onDeleted = vi.fn();
    renderWithoutRouter(
      <MarketplacePackageActionDialog
        action={{ type: 'delete', item: mockPackage }}
        onOpenChange={onOpenChange}
        onDeleted={onDeleted}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'marketplace.delete.actions.delete' }));

    expect(await screen.findByText('marketplace.delete.result.success')).toBeInTheDocument();
    expect(onDeleted).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'marketplace.delete.actions.delete' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'marketplace.common.actions.cancel' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'marketplace.common.actions.close' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
