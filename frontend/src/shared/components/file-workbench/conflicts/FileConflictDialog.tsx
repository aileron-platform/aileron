import { AlertTriangle, File, Folder, Loader2, ShieldAlert } from 'lucide-react';
import { useI18n } from '@/shared/hooks/useI18n';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/components/ui/dialog';
import { RadioGroup, RadioGroupItem } from '@/shared/components/ui/radio-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import {
  canApplyFileConflictStrategyToAll,
  getEffectiveFileConflictStrategy,
  type FileConflictItemStrategies,
} from './fileConflictModel';
import type {
  FileConflictItem,
  FileConflictOperation,
  ResolvableFileConflictStrategy,
} from './types';

const STRATEGIES: ResolvableFileConflictStrategy[] = ['keep-both', 'replace', 'skip'];

export interface FileConflictDialogProps {
  open: boolean;
  operation: FileConflictOperation | null;
  conflicts: FileConflictItem[];
  defaultStrategy: ResolvableFileConflictStrategy;
  itemStrategies: FileConflictItemStrategies;
  pending: boolean;
  error: unknown;
  getAffectedUnsavedTabsCount?: (paths: string[]) => number;
  onDefaultStrategyChange: (strategy: ResolvableFileConflictStrategy) => void;
  onItemStrategyChange: (
    sourcePath: string,
    strategy: ResolvableFileConflictStrategy,
  ) => void;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
}

export const FileConflictDialog = ({
  open,
  operation,
  conflicts,
  defaultStrategy,
  itemStrategies,
  pending,
  error,
  getAffectedUnsavedTabsCount,
  onDefaultStrategyChange,
  onItemStrategyChange,
  onCancel,
  onConfirm,
}: FileConflictDialogProps) => {
  const { t } = useI18n();
  const replaceAllAvailable = canApplyFileConflictStrategyToAll(conflicts, 'replace');
  const unsavedConflictPaths = conflicts
    .filter((conflict) => getEffectiveFileConflictStrategy(
      conflict.sourcePath,
      defaultStrategy,
      itemStrategies,
    ) === 'replace')
    .map((conflict) => conflict.targetPath);
  const affectedUnsavedTabsCount = getAffectedUnsavedTabsCount?.(unsavedConflictPaths) ?? 0;

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen && !pending) onCancel();
      }}
    >
      <DialogContent
        className="grid max-h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-2xl grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden p-0"
        onEscapeKeyDown={(event) => {
          if (pending) event.preventDefault();
        }}
        onInteractOutside={(event) => event.preventDefault()}
      >
        <DialogHeader className="shrink-0 border-b border-border px-6 py-5 pr-12 text-left">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 rounded-md border border-amber-500/30 bg-amber-500/10 p-2 text-amber-600 dark:text-amber-400">
              <ShieldAlert className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <DialogTitle>{t('shared.fileWorkbench.conflict.title')}</DialogTitle>
              <DialogDescription className="mt-1">
                {t('shared.fileWorkbench.conflict.description', {
                  count: conflicts.length,
                  operation: operation
                    ? t(`shared.fileWorkbench.conflict.operation.${operation}`)
                    : '',
                })}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div
          data-testid="file-conflict-list"
          className="min-h-0 overflow-y-auto overscroll-contain px-6 py-5"
        >
          <section aria-labelledby="file-conflict-apply-all" className="rounded-lg border border-border bg-muted/20 p-4">
            <div id="file-conflict-apply-all" className="text-sm font-medium">
              {t('shared.fileWorkbench.conflict.applyAll')}
            </div>
            <RadioGroup
              className="mt-3 grid-cols-1 sm:grid-cols-3"
              value={defaultStrategy}
              onValueChange={(value) => onDefaultStrategyChange(
                value as ResolvableFileConflictStrategy,
              )}
              aria-label={t('shared.fileWorkbench.conflict.applyAll')}
              disabled={pending}
            >
              {STRATEGIES.map((strategy) => {
                const disabled = strategy === 'replace' && !replaceAllAvailable;
                return (
                  <label
                    key={strategy}
                    className="flex min-w-0 items-start gap-2 rounded-md border border-border bg-background px-3 py-2.5 has-[:checked]:border-primary has-[:checked]:bg-primary/5 has-[:disabled]:cursor-not-allowed has-[:disabled]:opacity-50"
                  >
                    <RadioGroupItem
                      className="mt-0.5 shrink-0"
                      value={strategy}
                      disabled={disabled}
                      aria-label={t(`shared.fileWorkbench.conflict.strategy.${strategy}.label`)}
                    />
                    <span className="min-w-0">
                      <span className="block text-sm font-medium">
                        {t(`shared.fileWorkbench.conflict.strategy.${strategy}.label`)}
                      </span>
                      <span className="mt-0.5 block text-xs leading-4 text-muted-foreground">
                        {t(`shared.fileWorkbench.conflict.strategy.${strategy}.description`)}
                      </span>
                    </span>
                  </label>
                );
              })}
            </RadioGroup>
            {!replaceAllAvailable ? (
              <p className="mt-2 text-xs text-muted-foreground">
                {t('shared.fileWorkbench.conflict.replaceUnavailable.batch')}
              </p>
            ) : null}
          </section>

          <div className="mt-5 space-y-3">
            {conflicts.map((conflict, index) => {
              const reasonId = `file-conflict-replace-reason-${index}`;
              const effectiveStrategy = getEffectiveFileConflictStrategy(
                conflict.sourcePath,
                defaultStrategy,
                itemStrategies,
              );
              const SourceIcon = conflict.sourceType === 'directory' ? Folder : File;
              return (
                <section
                  key={conflict.sourcePath}
                  data-conflict-row
                  className="rounded-lg border border-border bg-card p-4"
                  aria-labelledby={`file-conflict-path-${index}`}
                >
                  <div className="flex min-w-0 flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="flex min-w-0 items-start gap-3">
                      <SourceIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                      <div className="min-w-0">
                        <p
                          id={`file-conflict-path-${index}`}
                          className="break-all font-mono text-sm font-medium text-foreground"
                        >
                          {conflict.targetPath}
                        </p>
                        <p className="mt-1 text-xs text-muted-foreground">
                          {t('shared.fileWorkbench.conflict.typeSummary', {
                            sourceType: t(`shared.fileWorkbench.conflict.entryType.${conflict.sourceType}`),
                            targetType: t(`shared.fileWorkbench.conflict.entryType.${conflict.targetType}`),
                          })}
                        </p>
                      </div>
                    </div>

                    <Select
                      value={effectiveStrategy}
                      onValueChange={(value) => onItemStrategyChange(
                        conflict.sourcePath,
                        value as ResolvableFileConflictStrategy,
                      )}
                      disabled={pending}
                    >
                      <SelectTrigger
                        className="w-full shrink-0 sm:w-40"
                        aria-label={t('shared.fileWorkbench.conflict.itemStrategy', {
                          path: conflict.targetPath,
                        })}
                        aria-describedby={!conflict.canReplace ? reasonId : undefined}
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent collisionPadding={8}>
                        {STRATEGIES.map((strategy) => (
                          <SelectItem
                            key={strategy}
                            value={strategy}
                            disabled={strategy === 'replace' && !conflict.canReplace}
                          >
                            {t(`shared.fileWorkbench.conflict.strategy.${strategy}.label`)}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {!conflict.canReplace ? (
                    <p
                      id={reasonId}
                      className="mt-3 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-300"
                    >
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      {t('shared.fileWorkbench.conflict.replaceUnavailable.typeMismatch', {
                        sourceType: t(`shared.fileWorkbench.conflict.entryType.${conflict.sourceType}`),
                        targetType: t(`shared.fileWorkbench.conflict.entryType.${conflict.targetType}`),
                      })}
                    </p>
                  ) : null}
                </section>
              );
            })}
          </div>

          {affectedUnsavedTabsCount > 0 ? (
            <p className="mt-4 rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
              {t('shared.fileWorkbench.conflict.unsavedTabs', { count: affectedUnsavedTabsCount })}
            </p>
          ) : null}

          {error ? (
            <div role="alert" className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              {t('shared.fileWorkbench.conflict.error.execute')}
            </div>
          ) : null}
        </div>

        <DialogFooter className="shrink-0 flex-row justify-end gap-2 border-t border-border bg-background px-6 py-4 sm:space-x-0">
          <Button type="button" variant="outline" onClick={onCancel} disabled={pending}>
            {t('shared.fileWorkbench.conflict.actions.cancelBatch')}
          </Button>
          <Button
            type="button"
            onClick={() => { void onConfirm(); }}
            disabled={pending || conflicts.length === 0}
          >
            {pending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" /> : null}
            {pending
              ? t('shared.fileWorkbench.conflict.actions.processing')
              : t('shared.fileWorkbench.conflict.actions.continue')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
