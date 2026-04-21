import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Tabs } from '@/shared/components/ui/tabs';
import { TopTabsBar, TopTabsCountBadge, TopTabsList, TopTabsTrigger } from './TopTabs';

describe('TopTabs', () => {
  it('renders a shared top tab bar and hides zero-count badges', () => {
    render(
      <Tabs defaultValue="files">
        <TopTabsBar data-testid="top-tabs-bar">
          <TopTabsList>
            <TopTabsTrigger value="files">Files<TopTabsCountBadge count={3} /></TopTabsTrigger>
            <TopTabsTrigger value="sharing">Sharing<TopTabsCountBadge count={0} /></TopTabsTrigger>
          </TopTabsList>
        </TopTabsBar>
      </Tabs>,
    );

    expect(screen.getByTestId('top-tabs-bar')).toHaveClass('border-b', 'bg-background');
    expect(screen.getByRole('tab', { name: /files 3/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /sharing/i })).toBeInTheDocument();
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });
});
