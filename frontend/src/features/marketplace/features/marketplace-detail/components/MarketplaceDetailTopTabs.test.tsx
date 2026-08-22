import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { FileText, Info } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import { MarketplaceDetailTopTabs } from './MarketplaceDetailTopTabs';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

const detail = {
  targetClient: 'codex',
  category: 'tools',
  version: '1.2.3',
} as MarketplacePackageDetail;

const renderTopTabs = (ui: React.ReactElement) => render(ui);

describe('MarketplaceDetailTopTabs', () => {
  it('renders package metadata, tab badges, and dispatches tab changes', () => {
    const onChange = vi.fn();

    renderTopTabs(
      <MarketplaceDetailTopTabs
        detail={detail}
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
    expect(screen.getByText('marketplace.targetClients.codex')).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Basic/ })).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /Guidance/ }));

    expect(onChange).toHaveBeenCalledWith('agents-md');
  });

});
