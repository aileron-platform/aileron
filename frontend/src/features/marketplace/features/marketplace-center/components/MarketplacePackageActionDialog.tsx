import React from 'react';
import { CheckCircle2, Download, Info, Trash2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
} from '@/shared/components/ui/alert-dialog';
import { AlertDialogHeading } from '@/shared/components/ui/dialog-heading';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageSummary } from '@/features/marketplace/model/marketplaceTypes';
import {
  deletePackage,
  exportPackage,
} from '../../../api/marketplaceApi';
import { MarketplaceInstallDialog } from '../../../components/MarketplaceInstallDialog';
import {
  getMarketplaceErrorCode,
  getMarketplacePackageActionErrorKey,
  type MarketplacePackageActionType,
} from '../../../model/marketplacePackageActionModel';
import {
  buildMarketplaceDeleteRequest,
  buildMarketplaceExportRequest,
  getMarketplaceActionTextKeys,
} from '../marketplacePackageActionModel';

interface MarketplacePackageActionDialogProps {
  action: {
    type: 'install' | MarketplacePackageActionType;
    item: MarketplacePackageSummary;
  } | null;
  onOpenChange: (open: boolean) => void;
  onDeleted: () => void;
}

export const MarketplacePackageActionDialog: React.FC<MarketplacePackageActionDialogProps> = ({
  action,
  onOpenChange,
  onDeleted,
}) => {
  const { t } = useI18n();
  const [status, setStatus] = React.useState<'idle' | 'running' | 'success' | 'failed'>('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (action) {
      setStatus('idle');
      setErrorCode(null);
    }
  }, [action]);

  if (!action) return null;
  if (action.type === 'install') {
    return (
      <MarketplaceInstallDialog
        open
        item={action.item}
        onOpenChange={onOpenChange}
      />
    );
  }

  const { item } = action;
  const actionTextKeys = getMarketplaceActionTextKeys(action.type);
  const actionHeading = {
    export: { icon: Download, tone: 'primary' as const },
    delete: { icon: Trash2, tone: 'destructive' as const },
  }[action.type];

  const runAction = async () => {
    setStatus('running');
    setErrorCode(null);
    try {
      if (action.type === 'export') {
        await exportPackage(buildMarketplaceExportRequest(item));
        setStatus('success');
        return;
      }
      const result = await deletePackage(buildMarketplaceDeleteRequest(item));
      if (result.deleted) {
        setStatus('success');
        onDeleted();
        return;
      }
      setStatus('failed');
      setErrorCode(result.errorCode ?? 'marketplace.package.delete_failed');
    } catch (err) {
      setStatus('failed');
      setErrorCode(getMarketplaceErrorCode(err, `marketplace.${action.type}.failed`));
    }
  };

  const shouldShowCloseOnlyFooter = status === 'success' && action.type === 'delete';

  return (
    <AlertDialog open={Boolean(action)} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogHeading icon={actionHeading.icon} tone={actionHeading.tone}>
            {t(actionTextKeys.titleKey)}
          </AlertDialogHeading>
          <AlertDialogDescription>{t(actionTextKeys.descriptionKey)}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-4">
          <div className="grid gap-3 rounded-md border border-border p-3 text-sm">
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">{t('marketplace.install.fields.targetClient')}</span>
              <span>{t(`marketplace.targetClients.${item.targetClient}`)}</span>
            </div>
            <div className="flex justify-between gap-4">
              <span className="text-muted-foreground">{t('marketplace.install.fields.package')}</span>
              <span className="font-mono">{item.packageId}</span>
            </div>
          </div>
          {action.type === 'export' ? (
            <Alert>
              <Download className="h-4 w-4" />
              <AlertDescription>{t('marketplace.export.compatibilityNotice')}</AlertDescription>
            </Alert>
          ) : null}
          {action.type === 'delete' ? (
            <Alert variant="destructive">
              <Trash2 className="h-4 w-4" />
              <AlertDescription>{t('marketplace.delete.warning')}</AlertDescription>
            </Alert>
          ) : null}
          {status === 'success' ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                {action.type === 'export'
                    ? t('marketplace.export.result.ready')
                    : t('marketplace.delete.result.success')}
              </AlertDescription>
            </Alert>
          ) : null}
          {status === 'failed' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>
                {t(getMarketplacePackageActionErrorKey(
                  action.type,
                  errorCode,
                ))}
              </AlertDescription>
            </Alert>
          ) : null}
        </div>
        <AlertDialogFooter>
          {shouldShowCloseOnlyFooter ? (
            <AlertDialogCancel onClick={() => onOpenChange(false)}>
              {t('marketplace.common.actions.close')}
            </AlertDialogCancel>
          ) : (
            <>
              <AlertDialogCancel onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</AlertDialogCancel>
              <AlertDialogAction
                className={action.type === 'delete' ? 'bg-destructive text-destructive-foreground hover:bg-destructive/90' : undefined}
                onClick={(event) => {
                  event.preventDefault();
                  void runAction();
                }}
                disabled={status === 'running'}
              >
                {status === 'running' ? <LoadingSpinner size="sm" className="mr-1.5" /> : null}
                {t(actionTextKeys.actionKey)}
              </AlertDialogAction>
            </>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
