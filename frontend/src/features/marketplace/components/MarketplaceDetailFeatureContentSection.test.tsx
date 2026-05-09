import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { Bot } from 'lucide-react';
import { describe, expect, it, vi } from 'vitest';
import type { MarketplaceFeatureContentItem } from '@/shared/types/marketplace';
import { MarketplaceDetailFeatureContentSection } from './MarketplaceDetailFeatureContentSection';

vi.mock('@/shared/hooks/useI18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => params ? `${key}:${JSON.stringify(params)}` : key,
  }),
}));

vi.mock('@/shared/components/markdown/MarkdownContent', () => ({
  MarkdownContent: ({ content }: { content: string }) => <article>{content}</article>,
}));

vi.mock('@/shared/components/ui/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

const items: MarketplaceFeatureContentItem[] = [
  {
    id: 'alpha-agent',
    name: 'Alpha agent',
    description: 'Handles alpha tasks',
    path: 'agents/alpha.md',
    content: '# Alpha',
  },
  {
    id: 'beta-agent',
    name: 'Beta agent',
    description: 'Handles beta tasks',
    path: 'agents/beta.md',
    content: '# Beta',
  },
];

describe('MarketplaceDetailFeatureContentSection', () => {
  it('renders feature items, supports selection, and keeps markdown content rendering', () => {
    render(
      <MarketplaceDetailFeatureContentSection
        title="Agents"
        items={items}
        icon={Bot}
        emptyLabel="No items"
      />,
    );

    expect(screen.getByText('Agents')).toBeInTheDocument();
    expect(screen.getAllByText('alpha.md').length).toBeGreaterThan(0);
    expect(screen.getByText('# Alpha')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /beta.md/ }));

    expect(screen.getByText('# Beta')).toBeInTheDocument();
  });

  it('filters items and renders an empty state', () => {
    render(
      <MarketplaceDetailFeatureContentSection
        title="Agents"
        items={items}
        icon={Bot}
        emptyLabel="No items"
      />,
    );

    fireEvent.change(screen.getByPlaceholderText('marketplace.center.filters.searchPlaceholder'), {
      target: { value: 'missing' },
    });

    expect(screen.getAllByText('No items').length).toBeGreaterThan(0);
  });

  it('allows callers to customize selected item rendering', () => {
    render(
      <MarketplaceDetailFeatureContentSection
        title="Agents"
        items={items}
        icon={Bot}
        emptyLabel="No items"
        renderItem={item => <div>{`custom:${item.fileName}:${item.content}`}</div>}
      />,
    );

    expect(screen.getByText('custom:alpha.md:# Alpha')).toBeInTheDocument();
  });
});
