import React from 'react';
import { Search } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceFeatureKey, MarketplaceTargetClient } from '@/features/marketplace/model/marketplaceTypes';
import {
  MARKETPLACE_FEATURES,
  toggleMarketplaceFeature,
} from '../marketplaceCenterModel';

interface MarketplaceCenterFiltersProps {
  searchTerm: string;
  targetClient: MarketplaceTargetClient | 'all';
  activeFeatures: Set<MarketplaceFeatureKey>;
  category: string;
  categories: string[];
  onSearchTermChange: (value: string) => void;
  onTargetClientChange: (value: MarketplaceTargetClient | 'all') => void;
  onActiveFeaturesChange: (value: Set<MarketplaceFeatureKey>) => void;
  onCategoryChange: (value: string) => void;
  onResetFilters: () => void;
}

export const MarketplaceCenterFilters: React.FC<MarketplaceCenterFiltersProps> = ({
  searchTerm,
  targetClient,
  activeFeatures,
  category,
  categories,
  onSearchTermChange,
  onTargetClientChange,
  onActiveFeaturesChange,
  onCategoryChange,
  onResetFilters,
}) => {
  const { t } = useI18n();

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <p className="text-sm font-semibold text-foreground">
          {t('marketplace.center.filters.searchLabel')}
        </p>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-10"
            value={searchTerm}
            placeholder={t('marketplace.center.filters.searchPlaceholder')}
            onChange={event => onSearchTermChange(event.target.value)}
          />
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-foreground">{t('marketplace.center.filters.cliLabel')}</p>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onResetFilters}>
            {t('marketplace.center.filters.clear')}
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {(['all', 'claude-code', 'codex'] as const).map(value => (
            <Button
              key={value}
              variant={targetClient === value ? 'default' : 'outline'}
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={() => onTargetClientChange(value)}
            >
              {value === 'all'
                ? t('marketplace.center.filters.allTargetClients')
                : t(`marketplace.targetClients.${value}`)}
            </Button>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-foreground">
            {t('marketplace.center.filters.featureLabel')}
          </p>
          <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onResetFilters}>
            {t('marketplace.center.filters.clear')}
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant={activeFeatures.size === 0 ? 'default' : 'outline'}
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => onActiveFeaturesChange(new Set())}
          >
            {t('marketplace.center.filters.allFeatures')}
          </Button>
          {MARKETPLACE_FEATURES.map(feature => {
            const isActive = activeFeatures.has(feature);
            return (
              <Button
                key={feature}
                variant={isActive ? 'default' : 'outline'}
                size="sm"
                className="h-7 px-2 text-xs"
                onClick={() => onActiveFeaturesChange(toggleMarketplaceFeature(activeFeatures, feature))}
              >
                {t(`marketplace.features.${feature}`)}
              </Button>
            );
          })}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-semibold text-foreground">
          {t('marketplace.center.filters.categoryLabel')}
        </p>
        <div className="flex flex-col gap-2">
          <Button
            variant={category === 'all' ? 'default' : 'outline'}
            size="sm"
            className="justify-start h-7 px-2 text-xs"
            onClick={() => onCategoryChange('all')}
          >
            {t('marketplace.center.filters.allCategories')}
          </Button>
          {categories.map(item => (
            <Button
              key={item}
              variant={category === item ? 'default' : 'outline'}
              size="sm"
              className="justify-start h-7 px-2 text-xs"
              onClick={() => onCategoryChange(item)}
            >
              {item}
            </Button>
          ))}
        </div>
      </div>
    </div>
  );
};
