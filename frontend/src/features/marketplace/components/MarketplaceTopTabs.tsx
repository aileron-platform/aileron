import React from 'react';
import { TopTabsBar, TopTabsCountBadge, TopTabsList, TopTabsTrigger } from '@/shared/components/navigation/TopTabs';
import { useI18n } from '@/shared/hooks/useI18n';

interface MarketplaceTopTabsProps<TTab extends string> {
  provider: string;
  tabs: TTab[];
  icons: Record<TTab, React.ComponentType<{ className?: string }>>;
  counts: Partial<Record<TTab, number>>;
  getLabelKey: (provider: string, tab: TTab) => string;
}

export const MarketplaceTopTabs = <TTab extends string>({
  provider,
  tabs,
  icons,
  counts,
  getLabelKey,
}: MarketplaceTopTabsProps<TTab>) => {
  const { t } = useI18n();

  return (
    <TopTabsBar>
      <TopTabsList>
        {tabs.map(tab => {
          const Icon = icons[tab];
          const count = counts[tab] ?? 0;
          return (
            <TopTabsTrigger key={tab} value={tab}>
              <Icon className="h-4 w-4" />
              {t(getLabelKey(provider, tab))}
              <TopTabsCountBadge count={count} />
            </TopTabsTrigger>
          );
        })}
      </TopTabsList>
    </TopTabsBar>
  );
};
