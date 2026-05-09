import React from 'react';
import { CheckCircle2, Download, Info, Play, RefreshCw, Terminal, Trash2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/shared/components/ui/alert-dialog';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { fetchWorkspaceList } from '@/features/workspace/services/workspaceRuntimeApi';
import { ApiError } from '@/shared/api/apiClient';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  MarketplaceCliPreflight,
  MarketplaceInstallResult,
  MarketplacePackageDetail,
  MarketplaceProvider,
} from '@/shared/types/marketplace';
import { deletePackage, exportPackage, getInstallPreflight, installPackage } from '../api/marketplaceApi';
import { FALLBACK_WORKSPACE_ID, MARKETPLACE_STORAGE_USER_SCOPE } from '../constants';
import { MarketplaceInstallOutput } from './MarketplaceInstallOutput';
import { downloadBlob } from '../utils/downloadBlob';
import {
  resolveMarketplaceInstallWorkspaceId,
  saveMarketplaceInstallWorkspaceId,
  type MarketplaceWorkspaceOption,
} from '../utils/marketplaceLocalStorage';

interface MarketplacePackageActionDialogProps {
  open: boolean;
  detail: MarketplacePackageDetail;
  onOpenChange: (open: boolean) => void;
}

interface MarketplaceDeleteDialogProps extends MarketplacePackageActionDialogProps {
  onDeleted: () => void;
}

interface InfoGridRowProps {
  label: string;
  value: React.ReactNode;
  monospace?: boolean;
}

const getMarketplaceInstallCommandName = (
  provider: MarketplaceProvider,
  t: (key: string) => string,
) => t(`marketplace.install.commandNames.${provider}`);

const getMarketplaceErrorCode = (err: unknown, fallback: string) => (
  err instanceof ApiError
    ? (err.errorCode ?? err.message ?? fallback)
    : err instanceof Error
      ? err.message
      : typeof err === 'string'
        ? err
        : fallback
);

const InfoGridRow: React.FC<InfoGridRowProps> = ({ label, value, monospace = false }) => (
  <div className="grid grid-cols-3 gap-4">
    <div className="text-sm font-medium text-muted-foreground">{label}</div>
    <div className={`col-span-2 break-words text-sm text-foreground ${monospace ? 'font-mono' : ''}`}>{value}</div>
  </div>
);

export const MarketplaceInstallDialog: React.FC<MarketplacePackageActionDialogProps> = ({ open, detail, onOpenChange }) => {
  const { t } = useI18n();
  const [workspaceId, setWorkspaceId] = React.useState(FALLBACK_WORKSPACE_ID);
  const [workspaceOptions, setWorkspaceOptions] = React.useState<MarketplaceWorkspaceOption[]>([]);
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = React.useState(false);
  const [status, setStatus] = React.useState<'idle' | 'running' | MarketplaceInstallResult['status']>('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);
  const [installResult, setInstallResult] = React.useState<MarketplaceInstallResult | null>(null);
  const [preflight, setPreflight] = React.useState<MarketplaceCliPreflight | null>(null);
  const [isLoadingPreflight, setIsLoadingPreflight] = React.useState(false);
  const commandName = getMarketplaceInstallCommandName(detail.provider, t);

  React.useEffect(() => {
    if (open) {
      setStatus('idle');
      setErrorCode(null);
      setInstallResult(null);
      setPreflight(null);
    }
  }, [open]);

  React.useEffect(() => {
    if (!open) return;
    let isActive = true;
    setIsLoadingWorkspaces(true);
    void fetchWorkspaceList()
      .then(result => {
        if (!isActive) return;
        const options = result.items.map(workspace => ({
          id: workspace.id,
          label: workspace.name || workspace.id,
        }));
        setWorkspaceOptions(options);
        setWorkspaceId(resolveMarketplaceInstallWorkspaceId(
          options,
          FALLBACK_WORKSPACE_ID,
          MARKETPLACE_STORAGE_USER_SCOPE,
        ));
      })
      .catch(() => {
        if (!isActive) return;
        setWorkspaceOptions([]);
        setWorkspaceId(resolveMarketplaceInstallWorkspaceId(
          [],
          FALLBACK_WORKSPACE_ID,
          MARKETPLACE_STORAGE_USER_SCOPE,
        ));
      })
      .finally(() => {
        if (isActive) setIsLoadingWorkspaces(false);
      });
    return () => { isActive = false; };
  }, [open]);

  React.useEffect(() => {
    if (!open || !workspaceId) return;
    let isActive = true;
    setIsLoadingPreflight(true);
    void getInstallPreflight(detail.provider, workspaceId)
      .then(result => {
        if (isActive) setPreflight(result);
      })
      .catch(err => {
        if (!isActive) return;
        setPreflight({
          provider: detail.provider,
          available: false,
          capabilities: {
            supportsUserScope: false,
            supportsMarketplaceAdd: false,
            supportsExtensionInstall: false,
          },
          errorCode: err instanceof Error ? err.message : 'marketplace.install.preflight.failed',
        });
      })
      .finally(() => {
        if (isActive) setIsLoadingPreflight(false);
      });
    return () => { isActive = false; };
  }, [detail.provider, open, workspaceId]);

  const runInstall = async () => {
    setStatus('running');
    saveMarketplaceInstallWorkspaceId(MARKETPLACE_STORAGE_USER_SCOPE, workspaceId);
    const result = await installPackage({
      provider: detail.provider,
      packageId: detail.packageId,
      revision: detail.revision,
      workspaceId,
    });
    setStatus(result.status);
    setErrorCode(result.errorCode ?? null);
    setInstallResult(result);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{t('marketplace.install.title')}</DialogTitle>
          <DialogDescription>{t('marketplace.install.description', { commandName })}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <InfoGridRow label={t('marketplace.install.fields.provider')} value={t(`marketplace.providers.${detail.provider}`)} />
            <InfoGridRow label={t('marketplace.install.fields.package')} value={detail.packageId} monospace />
          </div>
          <div className="space-y-2">
            <Label htmlFor="marketplace-install-workspace">{t('marketplace.install.fields.workspace')}</Label>
            <Select
              value={workspaceId}
              onValueChange={(value) => {
                setWorkspaceId(value);
                saveMarketplaceInstallWorkspaceId(MARKETPLACE_STORAGE_USER_SCOPE, value);
              }}
              disabled={isLoadingWorkspaces}
            >
              <SelectTrigger id="marketplace-install-workspace">
                <SelectValue placeholder={t('marketplace.install.workspaceSelect.placeholder')} />
              </SelectTrigger>
              <SelectContent>
                {workspaceOptions.length > 0 ? (
                  workspaceOptions.map(workspace => (
                    <SelectItem key={workspace.id} value={workspace.id}>
                      {workspace.label}
                    </SelectItem>
                  ))
                ) : (
                  <SelectItem value={FALLBACK_WORKSPACE_ID}>
                    {isLoadingWorkspaces
                      ? t('marketplace.install.workspaceSelect.loading')
                      : t('marketplace.install.workspaceSelect.currentWorkspace')}
                  </SelectItem>
                )}
              </SelectContent>
            </Select>
          </div>
          <Alert variant={preflight && !preflight.available ? 'destructive' : 'default'}>
            <Terminal className="h-4 w-4" />
            <AlertDescription>
              {isLoadingPreflight
                ? t('marketplace.install.preflight.loading', { commandName })
                : preflight?.available
                  ? t('marketplace.install.preflight.ready', { commandName, version: preflight.version ?? t('marketplace.install.preflight.unknownVersion') })
                  : t('marketplace.install.preflight.unavailable', { commandName, code: preflight?.errorCode ?? 'unknown' })}
            </AlertDescription>
          </Alert>
          <div className="rounded-md border border-border bg-muted/30 p-3">
            <div className="text-xs font-medium text-muted-foreground">{t('marketplace.install.commandPreview')}</div>
            <code className="mt-2 block break-all text-xs">
              {detail.provider === 'gemini'
                ? `gemini extensions install ${detail.registryPath}`
                : `${detail.provider === 'claude-code' ? 'claude' : 'codex'} plugin install ${detail.packageId} --scope user`}
            </code>
          </div>
          {installResult && status !== 'success' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>{t(`marketplace.install.result.${installResult.status}`, { commandName, code: errorCode ?? 'unknown' })}</AlertDescription>
            </Alert>
          ) : null}
          {status === 'success' ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{t('marketplace.install.result.success')}</AlertDescription>
            </Alert>
          ) : null}
          {installResult?.stdout || installResult?.stderr ? (
            <MarketplaceInstallOutput result={installResult} />
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</Button>
          <Button onClick={runInstall} disabled={status === 'running'}>
            {status === 'running' ? <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" /> : <Play className="mr-1.5 h-4 w-4" />}
            {t('marketplace.install.actions.install')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const MarketplaceExportDialog: React.FC<MarketplacePackageActionDialogProps> = ({ open, detail, onOpenChange }) => {
  const { t } = useI18n();
  const [status, setStatus] = React.useState<'idle' | 'running' | 'success' | 'failed'>('idle');
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
      const archive = await exportPackage({ provider: detail.provider, packageId: detail.packageId, revision: detail.revision });
      downloadBlob(archive, `${detail.provider}-${detail.packageId}.zip`);
      setStatus('success');
    } catch (err) {
      setErrorCode(getMarketplaceErrorCode(err, 'marketplace.export.result.failed'));
      setStatus('failed');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{t('marketplace.export.title')}</DialogTitle>
          <DialogDescription>{t('marketplace.export.description')}</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <InfoGridRow label={t('marketplace.export.fields.archive')} value={`${detail.packageId}.zip`} monospace />
          <InfoGridRow label={t('marketplace.export.fields.root')} value={detail.registryPath} monospace />
          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>{t('marketplace.export.compatibilityNotice')}</AlertDescription>
          </Alert>
          {status === 'success' ? (
            <Alert>
              <CheckCircle2 className="h-4 w-4" />
              <AlertDescription>{t('marketplace.export.result.ready')}</AlertDescription>
            </Alert>
          ) : null}
          {status === 'failed' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>{t('marketplace.export.result.failed', { code: errorCode ?? 'unknown' })}</AlertDescription>
            </Alert>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</Button>
          <Button onClick={runExport} disabled={status === 'running'}>
            {status === 'running' ? <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" /> : <Download className="mr-1.5 h-4 w-4" />}
            {t('marketplace.export.actions.export')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const MarketplaceDeleteDialog: React.FC<MarketplaceDeleteDialogProps> = ({ open, detail, onOpenChange, onDeleted }) => {
  const { t } = useI18n();
  const [confirmText, setConfirmText] = React.useState('');
  const [status, setStatus] = React.useState<'idle' | 'running' | 'failed'>('idle');
  const [errorCode, setErrorCode] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setConfirmText('');
      setStatus('idle');
      setErrorCode(null);
    }
  }, [open]);

  const runDelete = async () => {
    setStatus('running');
    const result = await deletePackage({
      provider: detail.provider,
      packageId: detail.packageId,
      revision: detail.revision,
    });
    if (result.deleted) {
      onOpenChange(false);
      onDeleted();
      return;
    }
    setStatus('failed');
    setErrorCode(result.errorCode ?? 'marketplace.package.delete_failed');
  };

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>{t('marketplace.delete.title')}</AlertDialogTitle>
          <AlertDialogDescription>{t('marketplace.delete.description')}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="space-y-4">
          <Alert variant="destructive">
            <Trash2 className="h-4 w-4" />
            <AlertDescription>{t('marketplace.delete.warning')}</AlertDescription>
          </Alert>
          <InfoGridRow label={t('marketplace.delete.fields.package')} value={detail.packageId} monospace />
          <InfoGridRow label={t('marketplace.delete.fields.revision')} value={detail.revision} monospace />
          <div className="space-y-2">
            <Label htmlFor="marketplace-delete-confirm">{t('marketplace.delete.fields.confirm', { id: detail.packageId })}</Label>
            <Input id="marketplace-delete-confirm" value={confirmText} onChange={event => setConfirmText(event.target.value)} />
          </div>
          {status === 'failed' ? (
            <Alert variant="destructive">
              <Info className="h-4 w-4" />
              <AlertDescription>{t('marketplace.delete.result.failed', { code: errorCode ?? 'unknown' })}</AlertDescription>
            </Alert>
          ) : null}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={(event) => {
              event.preventDefault();
              void runDelete();
            }}
            disabled={confirmText !== detail.packageId || status === 'running'}
          >
            {status === 'running' ? <RefreshCw className="mr-1.5 h-4 w-4 animate-spin" /> : <Trash2 className="mr-1.5 h-4 w-4" />}
            {t('marketplace.delete.actions.delete')}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
