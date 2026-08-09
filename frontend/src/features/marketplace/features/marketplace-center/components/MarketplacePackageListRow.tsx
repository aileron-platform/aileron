import React from 'react';
import { Download, Terminal } from 'lucide-react';
import type { MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

export interface MarketplacePackageListRowProps {
  item: MarketplacePackageSummary;
  onOpenDetail: (item: MarketplacePackageSummary) => void;
  onInstall?: (item: MarketplacePackageSummary) => void;
  onEdit?: (item: MarketplacePackageSummary) => void;
  onDelete?: (item: MarketplacePackageSummary) => void;
  onExport?: (item: MarketplacePackageSummary) => void;
}

export const MarketplacePackageListRow: React.FC<MarketplacePackageListRowProps> = ({
  item,
  onOpenDetail,
  onInstall,
  onEdit,
  onDelete,
  onExport,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex flex-wrap items-center gap-4 rounded-md border border-border bg-card p-4">
      <button className="min-w-0 flex-1 text-left" onClick={() => onOpenDetail(item)}>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="truncate text-sm font-semibold text-foreground hover:text-primary">{item.displayName}</h3>
          <Badge variant="outline">{t(`marketplace.providers.${item.provider}`)}</Badge>
          <Badge variant={item.lifecycleStatus === 'draft' ? 'outline' : 'secondary'}>
            {t(`marketplace.lifecycle.${item.lifecycleStatus}`)}
          </Badge>
          {item.variants.length > 1 ? (
            item.variants.map(variant => (
              <Badge key={`${variant.provider}:${variant.packageId}`} variant="secondary">
                {t(`marketplace.providers.${variant.provider}`)}
              </Badge>
            ))
          ) : null}
          {item.category ? <Badge variant="secondary">{item.category}</Badge> : null}
        </div>
        <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{item.packageId}</p>
        <p className="mt-1 line-clamp-1 text-sm text-muted-foreground">{item.description}</p>
      </button>

      <div className="flex flex-wrap items-center gap-2">
        {onInstall ? (
          <Button
            size="sm"
            className="h-7 px-2 text-xs"
            disabled={item.lifecycleStatus !== 'ready'}
            onClick={() => onInstall(item)}
            title={
              item.lifecycleStatus === 'draft'
                ? t('marketplace.lifecycle.draftInstallDisabled')
                : undefined
            }
          >
            <Terminal className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.center.card.actions.install')}
          </Button>
        ) : null}
        {onExport ? (
          <Button
            size="sm"
            variant="outline"
            className="h-7 px-2 text-xs"
            onClick={() => onExport(item)}
          >
            <Download className="mr-1.5 h-3.5 w-3.5" />
            {t('marketplace.center.card.actions.export')}
          </Button>
        ) : null}
        {onEdit ? (
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => onEdit(item)}>
            {t('marketplace.center.card.actions.edit')}
          </Button>
        ) : null}
        {onDelete ? (
          <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-destructive hover:text-destructive" onClick={() => onDelete(item)}>
            {t('marketplace.center.card.actions.delete')}
          </Button>
        ) : null}
      </div>
    </div>
  );
};
