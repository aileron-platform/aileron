import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  Database,
  FileArchive,
  Loader2,
  Plus,
  RotateCcw,
  ScanSearch,
  Square,
  Trash2,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
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
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Progress } from '@/shared/components/ui/progress';
import { Separator } from '@/shared/components/ui/separator';
import { useI18n } from '@/shared/hooks/useI18n';
import type { VersionControlOperationStatus } from '@/shared/version-control/types';
import {
  getLfsConversionProgress,
  isCompleteLfsSnapshotPreview,
  normalizeLfsPatterns,
  type VersionControlLfsSnapshotPreview,
} from '@/shared/version-control/versionControlLfs';

type LfsRequestError = 'patterns' | 'save' | 'preview' | 'convert' | 'cancel';
type LfsPendingRequest = 'save' | 'preview' | 'convert' | 'cancel' | null;

export interface VersionControlLfsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  requestIdentity?: string;
  patterns?: string[];
  isPatternsLoading?: boolean;
  patternsError?: boolean;
  operationStatus?: VersionControlOperationStatus | null;
  onReloadPatterns?: () => Promise<unknown> | unknown;
  onSavePatterns: (patterns: string[]) => Promise<unknown>;
  onPreview: (patterns: string[]) => Promise<VersionControlLfsSnapshotPreview>;
  onConvert: (paths: string[]) => Promise<unknown>;
  onCancel: () => Promise<unknown>;
}

const patternToken = (patterns: readonly string[]): string => (
  JSON.stringify(normalizeLfsPatterns(patterns))
);

const isLfsConversionOperation = (
  operationStatus: VersionControlOperationStatus | null | undefined,
): operationStatus is VersionControlOperationStatus => Boolean(
  operationStatus?.isActive && operationStatus.operation?.includes('lfs'),
);

export const VersionControlLfsDialog = ({
  open,
  onOpenChange,
  requestIdentity = 'default',
  patterns = [],
  isPatternsLoading = false,
  patternsError = false,
  operationStatus,
  onReloadPatterns,
  onSavePatterns,
  onPreview,
  onConvert,
  onCancel,
}: VersionControlLfsDialogProps) => {
  const { t } = useI18n();
  const [draftPatterns, setDraftPatterns] = useState<string[]>([]);
  const [savedPatterns, setSavedPatterns] = useState<string[]>([]);
  const [newPattern, setNewPattern] = useState('');
  const [preview, setPreview] = useState<VersionControlLfsSnapshotPreview | null>(null);
  const [pendingRequest, setPendingRequest] = useState<LfsPendingRequest>(null);
  const [requestError, setRequestError] = useState<LfsRequestError | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const requestEpochRef = useRef(0);

  const normalizedDraft = useMemo(
    () => normalizeLfsPatterns(draftPatterns),
    [draftPatterns],
  );
  const incomingPatternsToken = patternToken(patterns);
  const isDirty = patternToken(normalizedDraft) !== patternToken(savedPatterns);
  const conversionOperation = isLfsConversionOperation(operationStatus)
    ? operationStatus
    : null;
  const isBusy = pendingRequest !== null || Boolean(conversionOperation);
  const previewIsComplete = preview ? isCompleteLfsSnapshotPreview(preview) : false;

  useEffect(() => {
    requestEpochRef.current += 1;
    if (!open) {
      return;
    }
    const normalized = JSON.parse(incomingPatternsToken) as string[];
    setDraftPatterns(normalized);
    setSavedPatterns(normalized);
    setNewPattern('');
    setPreview(null);
    setPendingRequest(null);
    setRequestError(patternsError ? 'patterns' : null);
    setConfirmOpen(false);
  }, [open, requestIdentity]);

  useEffect(() => {
    if (!open || isDirty || isPatternsLoading || patternsError) {
      return;
    }
    const normalized = JSON.parse(incomingPatternsToken) as string[];
    setDraftPatterns(normalized);
    setSavedPatterns(normalized);
  }, [incomingPatternsToken, isDirty, isPatternsLoading, open, patternsError]);

  useEffect(() => {
    if (patternsError) {
      setRequestError('patterns');
    }
  }, [patternsError]);

  const invalidatePreview = () => {
    setPreview(null);
    setConfirmOpen(false);
    setRequestError(null);
  };

  const updatePattern = (index: number, value: string) => {
    setDraftPatterns(current => current.map((pattern, currentIndex) => (
      currentIndex === index ? value : pattern
    )));
    invalidatePreview();
  };

  const removePattern = (index: number) => {
    setDraftPatterns(current => current.filter((_, currentIndex) => currentIndex !== index));
    invalidatePreview();
  };

  const addPattern = () => {
    const nextPattern = newPattern.trim();
    if (!nextPattern) {
      return;
    }
    setDraftPatterns(current => normalizeLfsPatterns([...current, nextPattern]));
    setNewPattern('');
    invalidatePreview();
  };

  const runRequest = async <T,>(
    kind: Exclude<LfsPendingRequest, null>,
    request: () => Promise<T>,
    onSuccess: (value: T) => void,
  ): Promise<void> => {
    const requestEpoch = requestEpochRef.current;
    setPendingRequest(kind);
    setRequestError(null);
    try {
      const value = await request();
      if (requestEpoch !== requestEpochRef.current) {
        return;
      }
      onSuccess(value);
    } catch {
      if (requestEpoch === requestEpochRef.current) {
        setRequestError(kind);
      }
    } finally {
      if (requestEpoch === requestEpochRef.current) {
        setPendingRequest(null);
      }
    }
  };

  const savePatterns = () => runRequest(
    'save',
    () => onSavePatterns(normalizedDraft),
    () => {
      setDraftPatterns(normalizedDraft);
      setSavedPatterns(normalizedDraft);
    },
  );

  const previewSnapshot = () => runRequest(
    'preview',
    () => onPreview(normalizedDraft),
    value => setPreview(value),
  );

  const convertSnapshot = () => {
    if (!preview || !isCompleteLfsSnapshotPreview(preview)) {
      return Promise.resolve();
    }
    setConfirmOpen(false);
    return runRequest(
      'convert',
      () => onConvert(preview.pathSample),
      () => {
        setPreview(null);
      },
    );
  };

  const cancelOperation = () => runRequest(
    'cancel',
    onCancel,
    () => undefined,
  );

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && isBusy) {
      return;
    }
    onOpenChange(nextOpen);
  };

  const progressValue = conversionOperation
    ? getLfsConversionProgress(
      conversionOperation.progressCurrent,
      conversionOperation.progressTotal,
    )
    : 0;
  const phaseKey = conversionOperation?.phase === 'renormalizing'
    ? 'shared.versionControl.lfs.dialog.progress.phase.renormalizing'
    : 'shared.versionControl.lfs.dialog.progress.phase.working';

  return (
    <>
      <Dialog open={open} onOpenChange={handleOpenChange}>
        <DialogContent
          className="flex max-h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-2xl flex-col overflow-hidden p-0"
          aria-busy={isBusy}
          onEscapeKeyDown={(event) => { if (isBusy) event.preventDefault(); }}
          onPointerDownOutside={(event) => { if (isBusy) event.preventDefault(); }}
        >
          <DialogHeader className="shrink-0 border-b px-6 pb-4 pt-6">
            <DialogHeading icon={Database} iconClassName="h-4 w-4">
              {t('shared.versionControl.lfs.dialog.title')}
            </DialogHeading>
            <DialogDescription>
              {t('shared.versionControl.lfs.dialog.description')}
            </DialogDescription>
          </DialogHeader>

          <div
            data-testid="lfs-dialog-scroll-region"
            className="min-h-0 flex-1 space-y-6 overflow-y-auto px-6 py-5"
          >
            {isPatternsLoading ? (
              <div className="flex min-h-32 items-center justify-center text-sm text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('shared.versionControl.lfs.dialog.patterns.loading')}
              </div>
            ) : (
              <section className="space-y-3" aria-labelledby="version-control-lfs-patterns-title">
                <div className="space-y-1">
                  <h3 id="version-control-lfs-patterns-title" className="text-sm font-medium">
                    {t('shared.versionControl.lfs.dialog.patterns.title')}
                  </h3>
                  <p className="text-xs leading-5 text-muted-foreground">
                    {t('shared.versionControl.lfs.dialog.patterns.helper')}
                  </p>
                </div>

                <div className="rounded-md border bg-muted/20">
                  {draftPatterns.length === 0 ? (
                    <p className="px-3 py-4 text-sm text-muted-foreground">
                      {t('shared.versionControl.lfs.dialog.patterns.empty')}
                    </p>
                  ) : draftPatterns.map((pattern, index) => (
                    <div
                      key={index}
                      data-testid="lfs-pattern-row"
                      className="flex min-w-0 items-center gap-2 border-b px-3 py-2 last:border-b-0"
                    >
                      <FileArchive className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <Label htmlFor={`version-control-lfs-pattern-${index}`} className="sr-only">
                        {t('shared.versionControl.lfs.dialog.patterns.editLabel', { index: index + 1 })}
                      </Label>
                      <Input
                        id={`version-control-lfs-pattern-${index}`}
                        value={pattern}
                        className="h-8 min-w-0 border-0 bg-transparent font-mono text-xs shadow-none focus-visible:ring-1"
                        disabled={isBusy}
                        onChange={event => updatePattern(index, event.target.value)}
                      />
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-8 w-8 shrink-0"
                        disabled={isBusy}
                        aria-label={t('shared.versionControl.lfs.dialog.patterns.remove', { pattern })}
                        onClick={() => removePattern(index)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>

                <div className="flex min-w-0 gap-2">
                  <Label htmlFor="version-control-lfs-new-pattern" className="sr-only">
                    {t('shared.versionControl.lfs.dialog.patterns.newLabel')}
                  </Label>
                  <Input
                    id="version-control-lfs-new-pattern"
                    value={newPattern}
                    className="min-w-0 font-mono text-xs"
                    placeholder={t('shared.versionControl.lfs.dialog.patterns.placeholder')}
                    disabled={isBusy}
                    onChange={event => setNewPattern(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault();
                        addPattern();
                      }
                    }}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    className="shrink-0"
                    disabled={!newPattern.trim() || isBusy}
                    onClick={addPattern}
                  >
                    <Plus className="mr-2 h-4 w-4" />
                    {t('shared.versionControl.lfs.dialog.patterns.add')}
                  </Button>
                </div>
              </section>
            )}

            <Separator />

            <section className="space-y-3" aria-labelledby="version-control-lfs-conversion-title">
              <div className="space-y-1">
                <h3 id="version-control-lfs-conversion-title" className="text-sm font-medium">
                  {t('shared.versionControl.lfs.dialog.preview.title')}
                </h3>
                <p className="text-xs leading-5 text-muted-foreground">
                  {t('shared.versionControl.lfs.dialog.preview.helper')}
                </p>
                {isDirty ? (
                  <p className="text-xs font-medium text-foreground">
                    {t('shared.versionControl.lfs.dialog.preview.saveFirst')}
                  </p>
                ) : null}
              </div>

              {preview ? (
                <div className="overflow-hidden rounded-md border">
                  <div className="grid grid-cols-2 divide-x bg-muted/20">
                    <div className="px-4 py-3">
                      <p className="text-xs text-muted-foreground">
                        {t('shared.versionControl.lfs.dialog.preview.filesLabel')}
                      </p>
                      <p className="mt-1 text-lg font-semibold tabular-nums">
                        {t('shared.versionControl.lfs.dialog.preview.matchedTotal', {
                          count: preview.matchedTotal,
                        })}
                      </p>
                    </div>
                    <div className="px-4 py-3">
                      <p className="text-xs text-muted-foreground">
                        {t('shared.versionControl.lfs.dialog.preview.sizeLabel')}
                      </p>
                      <p className="mt-1 text-lg font-semibold tabular-nums">
                        {t('shared.versionControl.lfs.dialog.preview.totalSize', {
                          bytes: preview.totalSize,
                        })}
                      </p>
                    </div>
                  </div>
                  {preview.pathSample.length > 0 ? (
                    <div className="max-h-40 overflow-y-auto border-t bg-background px-4 py-3">
                      <p className="mb-2 text-xs font-medium text-muted-foreground">
                        {t('shared.versionControl.lfs.dialog.preview.pathSample')}
                      </p>
                      <ul className="space-y-1 font-mono text-xs">
                        {preview.pathSample.map(path => (
                          <li key={path} className="truncate" title={path}>{path}</li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <p className="border-t px-4 py-3 text-sm text-muted-foreground">
                      {t('shared.versionControl.lfs.dialog.preview.empty')}
                    </p>
                  )}
                </div>
              ) : null}

              {preview && !previewIsComplete ? (
                <Alert variant="warning">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    {t('shared.versionControl.lfs.dialog.preview.truncated')}
                  </AlertDescription>
                </Alert>
              ) : null}
            </section>

            {conversionOperation ? (
              <section className="space-y-3 rounded-md border bg-muted/20 p-4" aria-live="polite">
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{t(phaseKey)}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t('shared.versionControl.lfs.dialog.progress.count', {
                        current: conversionOperation.progressCurrent,
                        total: conversionOperation.progressTotal,
                      })}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm font-medium tabular-nums">{progressValue}%</span>
                </div>
                <Progress
                  value={progressValue}
                  className="h-2"
                  aria-label={t('shared.versionControl.lfs.dialog.progress.label')}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={progressValue}
                />
                {conversionOperation.cancelRequested ? (
                  <p className="text-xs text-muted-foreground">
                    {t('shared.versionControl.lfs.dialog.progress.cancelRequested')}
                  </p>
                ) : null}
              </section>
            ) : null}

            {requestError ? (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>{t('shared.versionControl.lfs.dialog.errors.title')}</AlertTitle>
                <AlertDescription>
                  {t(`shared.versionControl.lfs.dialog.errors.${requestError}`)}
                </AlertDescription>
                {requestError === 'patterns' && onReloadPatterns ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-3"
                    onClick={() => void onReloadPatterns()}
                  >
                    <RotateCcw className="mr-2 h-4 w-4" />
                    {t('shared.versionControl.lfs.dialog.actions.retry')}
                  </Button>
                ) : null}
              </Alert>
            ) : null}

            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription className="space-y-1">
                <p>{t('shared.versionControl.lfs.dialog.safety.attributes')}</p>
                <p>{t('shared.versionControl.lfs.dialog.safety.history')}</p>
              </AlertDescription>
            </Alert>
          </div>

          <DialogFooter
            data-testid="lfs-dialog-footer"
            className="shrink-0 border-t px-6 py-4 sm:items-center sm:justify-between sm:space-x-0"
          >
            {conversionOperation ? (
              <Button
                type="button"
                variant="outline"
                disabled={!conversionOperation.cancellable
                  || conversionOperation.cancelRequested
                  || pendingRequest === 'cancel'}
                onClick={() => void cancelOperation()}
              >
                {pendingRequest === 'cancel' ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Square className="mr-2 h-3.5 w-3.5" />
                )}
                {t('shared.versionControl.lfs.dialog.actions.cancelOperation')}
              </Button>
            ) : (
              <Button
                type="button"
                variant="outline"
                disabled={isBusy}
                onClick={() => handleOpenChange(false)}
              >
                {t('shared.versionControl.lfs.dialog.actions.close')}
              </Button>
            )}
            <div className="flex flex-col-reverse gap-2 sm:flex-row">
              <Button
                type="button"
                variant="outline"
                disabled={normalizedDraft.length === 0 || isDirty || isBusy || isPatternsLoading}
                onClick={() => void previewSnapshot()}
              >
                {pendingRequest === 'preview' ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <ScanSearch className="mr-2 h-4 w-4" />
                )}
                {t('shared.versionControl.lfs.dialog.actions.preview')}
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={!isDirty || isBusy || isPatternsLoading}
                onClick={() => void savePatterns()}
              >
                {pendingRequest === 'save' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {t('shared.versionControl.lfs.dialog.actions.save')}
              </Button>
              <Button
                type="button"
                disabled={!preview || preview.matchedTotal === 0 || !previewIsComplete || isBusy}
                onClick={() => setConfirmOpen(true)}
              >
                {t('shared.versionControl.lfs.dialog.actions.prepareConversion')}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={confirmOpen}
        onOpenChange={(nextOpen) => {
          if (pendingRequest !== 'convert') {
            setConfirmOpen(nextOpen);
          }
        }}
      >
        <AlertDialogContent className="max-h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-md overflow-y-auto">
          <AlertDialogHeader>
            <AlertDialogTitle>{t('shared.versionControl.lfs.dialog.confirm.title')}</AlertDialogTitle>
            <AlertDialogDescription>
              {t('shared.versionControl.lfs.dialog.confirm.description', {
                count: preview?.matchedTotal ?? 0,
              })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <Alert variant="warning">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              {t('shared.versionControl.lfs.dialog.confirm.warning')}
            </AlertDescription>
          </Alert>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={pendingRequest === 'convert'}>
              {t('shared.versionControl.lfs.dialog.confirm.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={pendingRequest === 'convert'}
              onClick={(event) => {
                event.preventDefault();
                void convertSnapshot();
              }}
            >
              {pendingRequest === 'convert' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t('shared.versionControl.lfs.dialog.confirm.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
};
