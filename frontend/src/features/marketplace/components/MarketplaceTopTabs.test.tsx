import React from 'react';
import { render, screen } from '@testing-library/react';
import { FileText, Info } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import { Tabs } from '@/shared/components/ui/tabs';
import { MarketplaceTopTabs } from './MarketplaceTopTabs';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

describe('MarketplaceTopTabs', () => {
  it('renders tab labels and count badges', () => {
    render(
      <Tabs value="basic">
        <MarketplaceTopTabs
          provider="codex"
          tabs={['basic', 'files']}
          icons={{ basic: Info, files: FileText }}
          counts={{ basic: 0, files: 3 }}
          getLabelKey={(_provider, tab) => `marketplace.editor.tabs.${tab}`}
        />
      </Tabs>,
    );

    expect(screen.getByRole('tab', { name: /marketplace.editor.tabs.basic/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /marketplace.editor.tabs.files/ })).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });
});
