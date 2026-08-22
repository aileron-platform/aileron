import { Info, type LucideIcon } from 'lucide-react';
import { CollapsedSidebarIcon } from '@/shared/components/layout/CollapsedSidebarControls';
import { Badge } from '@/shared/components/ui/badge';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';

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
  onChange: (tab: TTab) => void;
  collapsed?: boolean;
}

export const MarketplaceDetailTopTabs = <TTab extends string>({
  detail,
  tabs,
  activeTab,
  onChange,
  collapsed = false,
}: MarketplaceDetailTopTabsProps<TTab>) => {
  const { t } = useI18n();

  return (
    <div
      data-testid="marketplace-detail-nav-sidebar"
      aria-label={t('marketplace.detail.sidebar.info.title')}
      className="flex h-full min-h-0 flex-col bg-background"
    >
      {collapsed ? (
        <div className="flex flex-1 items-start justify-center pt-3">
          <CollapsedSidebarIcon icon={Info} testId="marketplace-detail-nav-sidebar-collapsed-icon" />
        </div>
      ) : (
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
                  <span className="text-muted-foreground">{t('marketplace.detail.sidebar.info.targetClientLabel')}</span>
                  <span className="font-medium">{t(`marketplace.targetClients.${detail.targetClient}`)}</span>
                </div>
              </div>
            </section>

            <section>
              <h4 className="mb-3 font-medium text-foreground">{t('marketplace.detail.sidebar.features.title')}</h4>
              <div className="space-y-1" role="tablist">
                {tabs.map(tab => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      role="tab"
                      aria-selected={isActive}
                      tabIndex={isActive ? 0 : -1}
                      onClick={() => onChange(tab.id)}
                      className={[
                        'inline-flex h-8 w-full items-center justify-start rounded-md px-2 text-xs',
                        isActive
                          ? 'bg-primary text-primary-foreground shadow-sm'
                          : 'bg-transparent text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                      ].join(' ')}
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
                    </button>
                  );
                })}
              </div>
            </section>

          </div>
        </div>
      )}
    </div>
  );
};
