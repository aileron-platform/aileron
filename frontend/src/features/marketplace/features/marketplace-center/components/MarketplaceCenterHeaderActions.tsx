import React from 'react';
import { Plus, RefreshCcw, Settings, Upload } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { useI18n } from '@/shared/hooks/useI18n';

interface MarketplaceCenterHeaderActionsProps {
  permissions: {
    canImport: boolean;
    canEdit: boolean;
    canManageRegistry: boolean;
  };
  onImport: () => void;
  onCreate: () => void;
  onSettings: () => void;
  onRefresh: () => void;
}

export const MarketplaceCenterHeaderActions: React.FC<MarketplaceCenterHeaderActionsProps> = ({
  permissions,
  onImport,
  onCreate,
  onSettings,
  onRefresh,
}) => {
  const { t } = useI18n();

  return (
    <div className="flex items-center gap-2">
      {permissions.canImport ? (
        <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onImport}>
          <Upload className="h-3.5 w-3.5 mr-1" />
          {t('marketplace.center.actions.import')}
        </Button>
      ) : null}
      {permissions.canEdit ? (
        <Button size="sm" className="h-7 px-2 text-xs" onClick={onCreate}>
          <Plus className="h-3.5 w-3.5 mr-1" />
          {t('marketplace.center.actions.create')}
        </Button>
      ) : null}
      {permissions.canManageRegistry ? (
        <Button variant="outline" size="sm" className="h-7 px-2 text-xs" onClick={onSettings}>
          <Settings className="h-3.5 w-3.5 mr-1" />
          {t('marketplace.center.actions.settings')}
        </Button>
      ) : null}
      <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={onRefresh}>
        <RefreshCcw className="h-3.5 w-3.5 mr-1" />
        {t('marketplace.center.actions.refresh')}
      </Button>
    </div>
  );
};
