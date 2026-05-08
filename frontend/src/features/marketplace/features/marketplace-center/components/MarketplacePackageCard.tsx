import React from 'react';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/shared/components/ui/dropdown-menu';
import { Download, Edit, MoreVertical, Play, Trash2 } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplaceFeatureKey, MarketplacePackageSummary } from '@/shared/types/marketplace';
import { getMarketplaceFeatureLabelKey } from '../../../utils/featureLabels';

export interface MarketplacePackageCardProps {
  item: MarketplacePackageSummary;
  onOpenDetail: (item: MarketplacePackageSummary) => void;
  onInstall?: (item: MarketplacePackageSummary) => void;
  onEdit?: (item: MarketplacePackageSummary) => void;
  onDelete?: (item: MarketplacePackageSummary) => void;
  onExport?: (item: MarketplacePackageSummary) => void;
}

const marketplaceFeatureOrder: MarketplaceFeatureKey[] = ['agentsMd', 'hooks', 'mcp', 'agents', 'commands', 'outputStyle', 'skills'];

const getPackageFeatures = (item: MarketplacePackageSummary): MarketplaceFeatureKey[] => {
  const haystack = [...item.indexedResourceNames, ...item.tags].join(' ').toLowerCase();
  return marketplaceFeatureOrder.filter(feature => {
    switch (feature) {
      case 'agentsMd':
        return haystack.includes('agentsmd') || haystack.includes('agents.md') || haystack.includes('claude.md') || haystack.includes('gemini.md');
      case 'hooks':
        return haystack.includes('hook');
      case 'mcp':
        return haystack.includes('mcp');
      case 'agents':
        return haystack.includes('agent') || haystack.includes('subagent');
      case 'commands':
        return haystack.includes('command') || haystack.includes('slash');
      case 'outputStyle':
        return haystack.includes('outputstyle') || haystack.includes('output-style') || haystack.includes('output style');
      case 'skills':
        return haystack.includes('skill');
    }
  });
};

export const MarketplacePackageCard: React.FC<MarketplacePackageCardProps> = ({
  item,
  onOpenDetail,
  onInstall,
  onEdit,
  onDelete,
  onExport,
}) => {
  const { t } = useI18n();
  const featureBadges = getPackageFeatures(item);
  const siblingVariants = item.variants.filter(variant => (
    variant.provider !== item.provider || variant.packageId !== item.packageId
  ));

  return (
    <Card className="p-5 h-full flex flex-col border-border/80 hover:border-primary/60 transition-colors">
      <div className="flex items-start justify-between gap-4">
        <button className="space-y-1 text-left min-w-0" onClick={() => onOpenDetail(item)}>
          <p className="text-xs uppercase text-muted-foreground">
            {t(`marketplace.providers.${item.provider}`)} · {item.category ?? t('marketplace.common.uncategorized')}
          </p>
          <h3 className="text-lg font-semibold text-foreground hover:text-primary">
            {item.displayName}
          </h3>
          <p className="text-xs font-mono text-muted-foreground">ID: {item.packageId}</p>
          <p className="text-sm text-muted-foreground line-clamp-2">{item.description}</p>
        </button>

        {onEdit || onDelete || onExport ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {onEdit ? (
                <DropdownMenuItem onClick={() => onEdit(item)}>
                  <Edit className="h-4 w-4 mr-2" />
                  {t('marketplace.center.card.actions.edit')}
                </DropdownMenuItem>
              ) : null}
              {onExport ? (
                <DropdownMenuItem onClick={() => onExport(item)}>
                  <Download className="h-4 w-4 mr-2" />
                  {t('marketplace.center.card.actions.export')}
                </DropdownMenuItem>
              ) : null}
              {onDelete ? (
                <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => onDelete(item)}>
                  <Trash2 className="h-4 w-4 mr-2" />
                  {t('marketplace.center.card.actions.delete')}
                </DropdownMenuItem>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>

      <div className="mt-4 mb-5 flex flex-wrap gap-2">
        {siblingVariants.length > 0 ? (
          item.variants.map(variant => (
            <Badge key={`${variant.provider}:${variant.packageId}`} variant="outline" className="text-xs">
              {t(`marketplace.providers.${variant.provider}`)}
            </Badge>
          ))
        ) : null}
        {featureBadges.map(feature => (
          <Badge key={feature} variant="secondary" className="text-xs">
            {t(getMarketplaceFeatureLabelKey(item.provider, feature))}
          </Badge>
        ))}
      </div>

      <div className="flex-1" />

      <div className="mt-6 flex items-center gap-2">
        <Button className="flex-1" disabled={!onInstall} onClick={() => onInstall?.(item)}>
          <Play className="h-4 w-4 mr-2" />
          {t('marketplace.center.card.actions.install')}
        </Button>
        <Button variant="outline" className="flex-1" disabled={!onExport} onClick={() => onExport?.(item)}>
          <Download className="h-4 w-4 mr-2" />
          {t('marketplace.center.card.actions.export')}
        </Button>
      </div>
    </Card>
  );
};

export default MarketplacePackageCard;
