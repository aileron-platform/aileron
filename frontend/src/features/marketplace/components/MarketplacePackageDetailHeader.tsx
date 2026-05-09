import React from 'react';
import { ArrowLeft, Download, FileText, PenSquare, Play, Trash2 } from 'lucide-react';
import { FeatureHeader } from '@/shared/components/layout/FeatureHeader';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageDetail } from '@/shared/types/marketplace';
import type { MarketplaceActionPermissions } from '../permissions';

interface MarketplacePackageDetailHeaderProps {
  detail: MarketplacePackageDetail;
  permissions: MarketplaceActionPermissions;
  onBack: () => void;
  onEdit: () => void;
  onExport: () => void;
  onInstall: () => void;
  onDelete: () => void;
}

export const MarketplacePackageDetailHeader: React.FC<MarketplacePackageDetailHeaderProps> = ({
  detail,
  permissions,
  onBack,
  onEdit,
  onExport,
  onInstall,
  onDelete,
}) => {
  const { t } = useI18n();

  return (
    <FeatureHeader
      title={detail.displayName}
      icon={FileText}
      info={(
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{t('marketplace.detail.header.version', { version: detail.version ?? t('marketplace.common.noVersion') })}</span>
          <span>{t('marketplace.detail.header.provider', { provider: t(`marketplace.providers.${detail.provider}`) })}</span>
          <span>{t('marketplace.detail.header.category', { category: detail.category || t('marketplace.common.uncategorized') })}</span>
        </div>
      )}
      actions={(
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onBack}>
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.back')}
          </Button>
          {permissions.canEdit ? (
            <Button
              variant="outline"
              size="sm"
              className="h-7 px-2 text-xs"
              onClick={onEdit}
            >
              <PenSquare className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.edit')}
            </Button>
          ) : null}
          {permissions.canExport ? (
            <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onExport}>
              <Download className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.export')}
            </Button>
          ) : null}
          {permissions.canInstall ? (
            <Button size="sm" className="h-7 px-2 text-xs" onClick={onInstall}>
              <Play className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.install')}
            </Button>
          ) : null}
          {permissions.canDelete ? (
            <Button variant="destructive" size="sm" className="h-7 px-2 text-xs" onClick={onDelete}>
              <Trash2 className="mr-1.5 h-3.5 w-3.5" /> {t('marketplace.detail.actions.delete')}
            </Button>
          ) : null}
        </div>
      )}
    />
  );
};
