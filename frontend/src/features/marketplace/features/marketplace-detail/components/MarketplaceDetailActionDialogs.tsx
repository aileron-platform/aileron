import React from 'react';
import {
  CheckCircle2,
  Download,
  Info,
  RefreshCw,
  Trash2,
} from 'lucide-react';
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
import {
  AlertDialogHeading,
  DialogHeading,
} from '@/shared/components/ui/dialog-heading';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { useI18n } from '@/shared/hooks/useI18n';
import type { MarketplacePackageDetail } from '@/features/marketplace/model/marketplaceTypes';
import { deletePackage, exportPackage } from '../../../api/marketplaceApi';
import {
  getMarketplaceErrorCode,
  getMarketplacePackageActionErrorKey,
} from '../../../model/marketplacePackageActionModel';
import { downloadBlob } from '../../../utils/downloadBlob';
import { MarketplaceInfoGridRow } from './MarketplaceInfoGridRow';

interface MarketplacePackageActionDialogProps {
  open: boolean;
  detail: MarketplacePackageDetail;
  onOpenChange: (open: boolean) => void;
}

interface MarketplaceDeleteDialogProps extends MarketplacePackageActionDialogProps {
  onDeleted: () => void;
}

export const MarketplaceExportDialog: React.FC<
  MarketplacePackageActionDialogProps
> = ({ open, detail, onOpenChange }) => {
  const { t } = useI18n();
  const [status, setStatus] = React.useState<
    'idle' | 'running' | 'success' | 'failed'
  >('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setStatus('idle');
      setErrorCode(null);
    }
  }, [open]);

  const runExport = async () => {
    setStatus('running');
    setErrorCode(null);
    try {
      const archive = await exportPackage({
        targetClient: detail.targetClient,
        packageFormat: detail.packageFormat,
        packageId: detail.packageId,
      });
      downloadBlob(archive, `${detail.targetClient}-${detail.packageId}.zip`);
      setStatus('success');
    } catch (error) {
      setErrorCode(
        getMarketplaceErrorCode(error, 'marketplace.export.result.failed'),
      );
      setStatus('failed');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogHeading icon={Download}>
            {t('marketplace.export.title')}
          </DialogHeading>
          <DialogDescription>
            {t('marketplace.export.description')}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <MarketplaceInfoGridRow
            label={t('marketplace.export.fields.archive')}
            value={`${detail.packageId}.zip`}
            monospace
          />
          <MarketplaceInfoGridRow
            label={t('marketplace.export.fields.root')}
            value={detail.registryPath}
            monospace
          />
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              {t('marketplace.export.compatibilityNotice')}
            </AlertDescription>
          </Alert>
          {status === 'success' ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                {t('marketplace.export.result.ready')}
              </AlertDescription>
            </Alert>
          ) : null}
          {status === 'failed' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>
                {t(getMarketplacePackageActionErrorKey('export', errorCode))}
              </AlertDescription>
            </Alert>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t('marketplace.common.actions.cancel')}
          </Button>
          <Button onClick={() => void runExport()} disabled={status === 'running'}>
            {status === 'running' ? (
              <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Download className="mr-1.5 h-4 w-4" />
            )}
            {t('marketplace.export.actions.export')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const MarketplaceDeleteDialog: React.FC<
  MarketplaceDeleteDialogProps
> = ({ open, detail, onOpenChange, onDeleted }) => {
  const { t } = useI18n();
  const [status, setStatus] = React.useState<
    'idle' | 'running' | 'success' | 'failed'
  >('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setStatus('idle');
      setErrorCode(null);
    }
  }, [open]);

  const runDelete = async () => {
    setStatus('running');
    setErrorCode(null);
    try {
      const result = await deletePackage({
        targetClient: detail.targetClient,
        packageId: detail.packageId,
        revision: detail.revision,
      });
      if (result.deleted) {
        setStatus('success');
        return;
      }
      setStatus('failed');
      setErrorCode(result.errorCode ?? 'marketplace.package.delete_failed');
    } catch (error) {
      setErrorCode(
        getMarketplaceErrorCode(error, 'marketplace.package.delete_failed'),
      );
      setStatus('failed');
    }
  };

  const handleDeleteOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
    if (!nextOpen && status === 'success') {
      onDeleted();
    }
  };

  return (
    <AlertDialog open={open} onOpenChange={handleDeleteOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogHeading icon={Trash2}>
            {t('marketplace.delete.title')}
          </AlertDialogHeading>
          <AlertDialogDescription>
            {t('marketplace.delete.description')}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-4">
          <Alert variant="destructive">
            <Trash2 className="h-4 w-4" />
            <AlertDescription>
              {t('marketplace.delete.warning')}
            </AlertDescription>
          </Alert>
          <MarketplaceInfoGridRow
            label={t('marketplace.delete.fields.package')}
            value={detail.packageId}
            monospace
          />
          <MarketplaceInfoGridRow
            label={t('marketplace.delete.fields.revision')}
            value={detail.revision}
            monospace
          />
          {status === 'success' ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>
                {t('marketplace.delete.result.success')}
              </AlertDescription>
            </Alert>
          ) : null}
          {status === 'failed' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>
                {t(getMarketplacePackageActionErrorKey('delete', errorCode))}
              </AlertDescription>
            </Alert>
          ) : null}
        </div>
        <AlertDialogFooter>
          {status === 'success' ? (
            <AlertDialogCancel>
              {t('marketplace.common.actions.close')}
            </AlertDialogCancel>
          ) : (
            <>
              <AlertDialogCancel onClick={() => onOpenChange(false)}>
                {t('marketplace.common.actions.cancel')}
              </AlertDialogCancel>
              <AlertDialogAction
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                onClick={event => {
                  event.preventDefault();
                  void runDelete();
                }}
                disabled={status === 'running'}
              >
                {status === 'running' ? (
                  <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="mr-1.5 h-4 w-4" />
                )}
                {t('marketplace.delete.actions.delete')}
              </AlertDialogAction>
            </>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
