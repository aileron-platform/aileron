import React from 'react';
import { LayoutGrid, List } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceCenterViewMode } from '../../../storage/marketplaceStorage';

interface MarketplaceCenterListToolbarProps {
  viewMode: MarketplaceCenterViewMode;
  visibleCount: number;
  totalCount: number;
  currentPage: number;
  totalPages: number;
  onViewModeChange: (mode: MarketplaceCenterViewMode) => void;
}

export const MarketplaceCenterListToolbar: React.FC<MarketplaceCenterListToolbarProps> = ({
  viewMode,
  visibleCount,
  totalCount,
  currentPage,
  totalPages,
  onViewModeChange,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex h-10 items-center border-b border-border bg-muted/10 px-4">
      <div className="flex flex-wrap items-center gap-3 w-full">
        <div className="flex items-center gap-2">
          <LayoutGrid className="h-4 w-4 text-primary" />
          <p className="text-sm font-semibold text-foreground">
            {t('marketplace.center.list.title')}
          </p>
        </div>

        <div className="ml-auto flex items-center gap-2 text-xs text-muted-foreground">
          <div className="mr-2 flex items-center rounded-md border border-border bg-background p-0.5">
            <Button
              variant={viewMode === 'grid' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 px-2 text-xs"
              aria-label={t('marketplace.center.viewModes.grid')}
              onClick={() => onViewModeChange('grid')}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant={viewMode === 'list' ? 'secondary' : 'ghost'}
              size="sm"
              className="h-7 px-2 text-xs"
              aria-label={t('marketplace.center.viewModes.list')}
              onClick={() => onViewModeChange('list')}
            >
              <List className="h-3.5 w-3.5" />
            </Button>
          </div>
          <span>
            {t('marketplace.center.list.stats.visible', {
              visible: visibleCount,
              total: totalCount,
            })}
          </span>
          <span>
            {t('marketplace.center.list.stats.page', {
              current: currentPage,
              total: totalPages,
            })}
          </span>
        </div>
      </div>
    </div>
  );
};
