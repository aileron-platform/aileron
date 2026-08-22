import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceInstallOutput } from './MarketplaceInstallOutput';
import type { MarketplacePluginCommandResult } from '@/features/marketplace/model/marketplaceTypes';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceInstallOutput', () => {
  it('renders targetClient CLI terminal output without lifecycle projections', () => {
    const result: MarketplacePluginCommandResult = {
      status: 'failed',
      targetClient: 'codex',
      packageId: 'demo-plugin',
      marketplaceId: 'team-tools',
      workspaceId: 'workspace-1',
      operationId: 'a'.repeat(32),
      stage: 'plugin-install',
      exitCode: 1,
      cliMessage: 'Plugin install failed',
      stdout: 'Preparing plugin',
      stderr: 'Token [REDACTED] was hidden',
      truncated: true,
    };

    render(<MarketplaceInstallOutput result={result} />);

    expect(screen.getByText('marketplace.install.output.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.targetClients.codex')).toBeInTheDocument();
    expect(screen.getByText('marketplace.install.stages.plugin-install')).toBeInTheDocument();
    expect(screen.getByText('Plugin install failed')).toBeInTheDocument();
    expect(screen.getByText('Preparing plugin')).toBeInTheDocument();
    expect(screen.getByText('Token [REDACTED] was hidden')).toBeInTheDocument();
    expect(screen.getByText('marketplace.install.output.truncated')).toBeInTheDocument();
  });
});
