import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageDetail } from '@/shared/types/marketplace';

interface MarketplaceDetailTopTabItem<TTab extends string> {
  id: TTab;
  name: string;
  icon: LucideIcon;
  count: number;
}

interface MarketplaceDetailTopTabsProps<TTab extends string> {
  detail: MarketplacePackageDetail;
  tabs: Array<MarketplaceDetailTopTabItem<TTab>>;
  activeTab: TTab;
  leftWidth: number;
  onChange: (tab: TTab) => void;
}

export const MarketplaceDetailTopTabs = <TTab extends string>({
  detail,
  tabs,
  activeTab,
  leftWidth,
  onChange,
}: MarketplaceDetailTopTabsProps<TTab>) => {
  const { t } = useI18n();

  return (
    <div className="h-full border-r border-border bg-background" style={{ width: leftWidth }}>
      <div className="flex h-full flex-col">
        <div className="flex-1 overflow-y-auto p-4">
          <div className="space-y-4">
            <section>
              <h3 className="mb-3 font-semibold text-foreground">{t('marketplace.detail.sidebar.info.title')}</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">{t('marketplace.detail.sidebar.info.categoryLabel')}</span>
                  <Badge variant="secondary">{detail.category || t('marketplace.common.uncategorized')}</Badge>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">{t('marketplace.detail.sidebar.info.versionLabel')}</span>
                  <span className="font-medium">{detail.version ?? t('marketplace.common.noVersion')}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">{t('marketplace.detail.sidebar.info.providerLabel')}</span>
                  <span className="font-medium">{t(`marketplace.providers.${detail.provider}`)}</span>
                </div>
              </div>
            </section>

            <section>
              <h4 className="mb-3 font-medium text-foreground">{t('marketplace.detail.sidebar.features.title')}</h4>
              <div className="space-y-1">
                {tabs.map(tab => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <Button
                      key={tab.id}
                      variant={isActive ? 'default' : 'ghost'}
                      className="h-8 w-full justify-start px-2 text-xs"
                      onClick={() => onChange(tab.id)}
                    >
                      <Icon className="mr-2 h-4 w-4" />
                      <span className="flex-1 text-left">{tab.name}</span>
                      {tab.count > 0 && (
                        <Badge
                          variant="outline"
                          className={`ml-auto text-xs ${isActive ? 'bg-background text-foreground border-transparent' : ''}`}
                        >
                          {tab.count}
                        </Badge>
                      )}
                    </Button>
                  );
                })}
              </div>
            </section>

          </div>
        </div>
      </div>
    </div>
  );
};
