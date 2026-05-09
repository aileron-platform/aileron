import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { FileText, Info } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketplacePackageDetail } from '@/shared/types/marketplace';
import { MarketplaceDetailTopTabs } from './MarketplaceDetailTopTabs';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const detail = {
  provider: 'codex',
  category: 'tools',
  version: '1.2.3',
} as MarketplacePackageDetail;

describe('MarketplaceDetailTopTabs', () => {
  it('renders package metadata, tab badges, and dispatches tab changes', () => {
    const onChange = vi.fn();

    render(
      <MarketplaceDetailTopTabs
        detail={detail}
        leftWidth={280}
        activeTab="basic-info"
        onChange={onChange}
        tabs={[
          { id: 'basic-info', name: 'Basic', icon: Info, count: 0 },
          { id: 'agents-md', name: 'Guidance', icon: FileText, count: 1 },
        ]}
      />,
    );

    expect(screen.getByText('marketplace.detail.sidebar.info.title')).toBeInTheDocument();
    expect(screen.getByText('tools')).toBeInTheDocument();
    expect(screen.getByText('1.2.3')).toBeInTheDocument();
    expect(screen.getByText('marketplace.providers.codex')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Basic/ })).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Guidance/ }));

    expect(onChange).toHaveBeenCalledWith('agents-md');
  });
});
