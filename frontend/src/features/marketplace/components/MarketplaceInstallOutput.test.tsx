import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarketplaceInstallOutput } from './MarketplaceInstallOutput';
import type { MarketplaceInstallResult } from '@/shared/types/marketplace';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceInstallOutput', () => {
  it('renders stdout, stderr, and truncation messaging from a redacted install result', () => {
    const result: MarketplaceInstallResult = {
      status: 'failed',
      errorCode: 'cliUnavailable',
      commandPreview: 'codex install demo-plugin',
      stdout: 'Installed package files',
      stderr: 'Token [REDACTED] was hidden',
      truncated: true,
    };

    render(<MarketplaceInstallOutput result={result} />);

    expect(screen.getByText('marketplace.install.output.title')).toBeInTheDocument();
    expect(screen.getByText('marketplace.install.output.stdout')).toBeInTheDocument();
    expect(screen.getByText('Installed package files')).toBeInTheDocument();
    expect(screen.getByText('marketplace.install.output.stderr')).toBeInTheDocument();
    expect(screen.getByText('Token [REDACTED] was hidden')).toBeInTheDocument();
    expect(screen.getByText('marketplace.install.output.truncated')).toBeInTheDocument();
  });
});
