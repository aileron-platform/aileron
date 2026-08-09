import React from 'react';
import { FileArchive, Info, Search, Upload } from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Checkbox } from '@/shared/components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { LoadingSpinner } from '@/shared/components/ui/loading-spinner';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/shared/components/ui/select';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import type {
  MarketplaceImportCandidate,
  MarketplaceImportProvider,
  MarketplaceImportResult,
} from '@/features/marketplace/model/marketplaceTypes';
import {
  importCandidates,
  scanImportSource,
  uploadImportSource,
} from '../../../api/marketplaceApi';
import {
  IMPORT_PROVIDERS,
  translateMarketplaceMessage,
} from '../marketplaceCenterModel';
import { getMarketplaceErrorCode } from '../../../model/marketplacePackageActionModel';
import {
  buildGitImportSource,
  buildImportResultSummary,
  buildUploadedLocalImportSource,
  getSelectableCandidateIds,
  getVisibleImportValidationResults,
  isImportScanBlocked,
  resolveLocalUploadProvider,
  toggleImportCandidateSelection,
  updateImportCandidateDuplicateAction,
  updateImportCandidateNewPackageId,
} from '../marketplaceImportDialogModel';

interface MarketplaceImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: (result: MarketplaceImportResult) => void;
}

export const MarketplaceImportDialog: React.FC<MarketplaceImportDialogProps> = ({
  open,
  onOpenChange,
  onImported,
}) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [provider, setProvider] = React.useState<MarketplaceImportProvider>('all');
  const [sourceKind, setSourceKind] = React.useState<'git' | 'local'>('git');
  const [source, setSource] = React.useState('');
  const [localFile, setLocalFile] = React.useState<File | null>(null);
  const [uploadedLocalSource, setUploadedLocalSource] = React.useState('');
  const localFileInputRef = React.useRef<HTMLInputElement | null>(null);
  const [isScanning, setIsScanning] = React.useState(false);
  const [isImporting, setIsImporting] = React.useState(false);
  const [candidates, setCandidates] = React.useState<MarketplaceImportCandidate[]>([]);
  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
  const [resultStatus, setResultStatus] = React.useState<'idle' | 'scanned'>('idle');
  const [scanErrorKey, setScanErrorKey] = React.useState<string | null>(null);
  const scanBlocked = isImportScanBlocked({
    sourceKind,
    source,
    localFile,
    uploadedLocalSource,
  });

  React.useEffect(() => {
    if (!open) {
      setCandidates([]);
      setSelectedIds(new Set());
      setResultStatus('idle');
      setScanErrorKey(null);
      return;
    }
  }, [open]);

  const resetScanState = React.useCallback(() => {
    setCandidates([]);
    setSelectedIds(new Set());
    setResultStatus('idle');
    setScanErrorKey(null);
  }, []);

  const scan = async () => {
    setIsScanning(true);
    setScanErrorKey(null);
    try {
      const importSource = sourceKind === 'local'
        ? (localFile
          ? (await uploadImportSource(resolveLocalUploadProvider(provider), localFile)).source
          : buildUploadedLocalImportSource(provider, uploadedLocalSource))
        : buildGitImportSource(provider, source);
      if (sourceKind === 'local') {
        setUploadedLocalSource(importSource.source);
      }
      const scanned = await scanImportSource(importSource);
      setCandidates(scanned);
      setSelectedIds(new Set());
      setResultStatus('scanned');
    } catch (err) {
      setScanErrorKey(getMarketplaceErrorCode(err, 'marketplace.import.validation.cloneFailed'));
    } finally {
      setIsScanning(false);
    }
  };

  const runImport = async () => {
    setIsImporting(true);
    setScanErrorKey(null);
    try {
      const selected = candidates.filter(candidate => selectedIds.has(candidate.id));
      const result = await importCandidates(selected);
      const summary = buildImportResultSummary(result, selected);
      const summaryParams = {
        imported: summary.imported,
        skipped: summary.skipped,
        failed: summary.failed,
        duplicates: summary.duplicates,
        warnings: summary.warnings,
      };
      const failedDetails = result.failed.map(candidate => t('marketplace.import.result.failedDetailItem', {
        displayName: candidate.displayName,
        packageId: candidate.packageId,
        message: translateMarketplaceMessage(t, candidate.errorCode),
      }));
      toast({
        title: t('marketplace.import.result.summary', summaryParams),
        description: failedDetails.length
          ? t('marketplace.import.result.failedDetailsDescription', { details: failedDetails.join('; ') })
          : undefined,
        variant: summary.failed > 0 ? 'destructive' : summary.warnings > 0 ? 'info' : 'success',
      });
      onImported(result);
      onOpenChange(false);
    } catch (err) {
      setScanErrorKey(getMarketplaceErrorCode(err, 'marketplace.import.validation.cloneFailed'));
      setResultStatus('scanned');
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[min(90vh,760px)] max-w-3xl flex-col overflow-hidden">
        <DialogHeader>
          <DialogHeading icon={Upload}>
            {t('marketplace.import.title')}
          </DialogHeading>
          <DialogDescription>{t('marketplace.import.description')}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>{t('marketplace.import.fields.provider')}</Label>
              <Select value={provider} onValueChange={value => {
                setProvider(value as MarketplaceImportProvider);
                resetScanState();
              }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {IMPORT_PROVIDERS.map(value => (
                    <SelectItem key={value} value={value}>
                      {value === 'all'
                        ? t('marketplace.import.providers.all')
                        : t(`marketplace.providers.${value}`)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{t('marketplace.import.fields.sourceKind')}</Label>
              <Select value={sourceKind} onValueChange={value => {
                setSourceKind(value as 'git' | 'local');
                resetScanState();
              }}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="git">{t('marketplace.import.sourceKinds.git')}</SelectItem>
                  <SelectItem value="local">{t('marketplace.import.sourceKinds.local')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          {sourceKind === 'git' ? (
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
              <div className="space-y-2">
                <Label htmlFor="marketplace-import-source">{t('marketplace.import.fields.source')}</Label>
                <Input id="marketplace-import-source" value={source} onChange={event => {
                  setSource(event.target.value);
                  resetScanState();
                }} />
              </div>
              <Button
                type="button"
                variant="outline"
                className="w-full md:w-auto"
                onClick={scan}
                disabled={isScanning || scanBlocked}
              >
                {isScanning ? <LoadingSpinner size="sm" className="mr-1.5" /> : <Search className="mr-1.5 h-3.5 w-3.5" />}
                {t('marketplace.import.actions.scan')}
              </Button>
            </div>
          ) : (
            <div className="space-y-2">
              <Label htmlFor="marketplace-import-file">{t('marketplace.import.fields.localFile')}</Label>
              <div className="flex flex-wrap items-center gap-3 rounded-md border border-border p-3">
                <input
                  id="marketplace-import-file"
                  ref={localFileInputRef}
                  className="sr-only"
                  type="file"
                  accept=".zip,application/zip"
                  onChange={event => {
                    const file = event.target.files?.[0] ?? null;
                    setLocalFile(file);
                    setUploadedLocalSource('');
                    resetScanState();
                  }}
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 px-3 text-xs"
                  onClick={() => localFileInputRef.current?.click()}
                >
                  <FileArchive className="mr-1.5 h-3.5 w-3.5" />
                  {t('marketplace.import.actions.chooseFile')}
                </Button>
                <span className="min-w-0 truncate text-sm text-muted-foreground">
                  {localFile?.name ?? t('marketplace.import.localFile.empty')}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="ml-auto h-8 px-3 text-xs"
                  onClick={scan}
                  disabled={isScanning || scanBlocked}
                >
                  {isScanning ? <LoadingSpinner size="sm" className="mr-1.5" /> : <Search className="mr-1.5 h-3.5 w-3.5" />}
                  {t('marketplace.import.actions.scan')}
                </Button>
              </div>
            </div>
          )}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">{t('marketplace.import.candidates.title')}</h3>
              <div className="flex flex-wrap items-center gap-2">
                {candidates.length > 0 ? (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      onClick={() => setSelectedIds(new Set(getSelectableCandidateIds(candidates)))}
                      disabled={selectedIds.size === candidates.length}
                    >
                      {t('marketplace.import.actions.selectAll')}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 px-2 text-xs"
                      onClick={() => setSelectedIds(new Set())}
                      disabled={selectedIds.size === 0}
                    >
                      {t('marketplace.import.actions.clearSelection')}
                    </Button>
                  </>
                ) : null}
              </div>
            </div>
            <div className="max-h-[min(34vh,320px)] space-y-2 overflow-y-auto rounded-md border border-border p-3">
              {candidates.length === 0 ? (
                <p className="text-sm text-muted-foreground">{t('marketplace.import.candidates.empty')}</p>
              ) : candidates.map(candidate => {
                const visibleValidationResults = getVisibleImportValidationResults(candidate);
                return (
                  <div key={candidate.id} className="flex items-start gap-3 rounded-md border border-border px-3 py-2">
                    <Checkbox
                      checked={selectedIds.has(candidate.id)}
                      onCheckedChange={checked => setSelectedIds(toggleImportCandidateSelection(
                        selectedIds,
                        candidate.id,
                        Boolean(checked),
                      ))}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{candidate.displayName}</span>
                        <span className="font-mono text-xs text-muted-foreground">{candidate.packageId}</span>
                        {candidate.variantStatus === 'invalid' || candidate.variantStatus === 'unrelated-duplicate' ? (
                          <Badge variant="destructive">
                            {t(`marketplace.import.variantStatuses.${candidate.variantStatus}`)}
                          </Badge>
                        ) : null}
                        {candidate.duplicate ? (
                          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                            {t('marketplace.import.candidates.duplicate')}
                          </span>
                        ) : null}
                      </div>
                      {candidate.familyDisplayName || candidate.sourceIdentity ? (
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                          {candidate.familyDisplayName ? (
                            <span>{t('marketplace.import.candidates.family', { family: candidate.familyDisplayName })}</span>
                          ) : null}
                          {candidate.sourceIdentity ? (
                            <span className="font-mono">{candidate.sourceIdentity}</span>
                          ) : null}
                        </div>
                      ) : null}
                      <div className="mt-1 font-mono text-xs text-muted-foreground">{candidate.sourcePath}</div>
                      {visibleValidationResults.length > 0 ? (
                        <div className="mt-2 space-y-1">
                          {visibleValidationResults.map(result => (
                            <div key={`${candidate.id}-${result.code}`} className="text-xs text-amber-700">
                              {t(result.messageKey)}
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                    {candidate.duplicate ? (
                      <div className="w-48 space-y-2">
                        <Select
                          value={candidate.duplicateAction}
                          onValueChange={value => setCandidates(items => updateImportCandidateDuplicateAction(
                            items,
                            candidate.id,
                            value as MarketplaceImportCandidate['duplicateAction'],
                          ))}
                        >
                          <SelectTrigger className="w-full"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="skip">{t('marketplace.import.duplicateActions.skip')}</SelectItem>
                            <SelectItem value="overwrite">{t('marketplace.import.duplicateActions.overwrite')}</SelectItem>
                            <SelectItem value="import-as-new">{t('marketplace.import.duplicateActions.importAsNew')}</SelectItem>
                          </SelectContent>
                        </Select>
                        {candidate.duplicateAction === 'import-as-new' ? (
                          <Input
                            value={candidate.newPackageId ?? ''}
                            aria-label={t('marketplace.import.fields.newPackageId')}
                            placeholder={t('marketplace.import.fields.newPackageIdPlaceholder')}
                            onChange={event => setCandidates(items => updateImportCandidateNewPackageId(
                              items,
                              candidate.id,
                              event.target.value,
                            ))}
                          />
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        {scanErrorKey ? (
          <Alert variant="destructive" className="shrink-0">
            <Info className="h-4 w-4" />
            <AlertDescription>{translateMarketplaceMessage(t, scanErrorKey)}</AlertDescription>
          </Alert>
        ) : null}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>{t('marketplace.common.actions.cancel')}</Button>
          <Button onClick={runImport} disabled={selectedIds.size === 0 || isImporting || resultStatus === 'idle'}>
            {isImporting ? <LoadingSpinner size="sm" className="mr-1.5" /> : null}
            {t('marketplace.import.actions.import')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
