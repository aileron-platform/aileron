import React, { useEffect, useState } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { useI18n } from '@/shared/hooks/useI18n';

interface VersionControlDiscardDialogProps {
  open: boolean;
  paths: string[];
  onOpenChange: (open: boolean) => void;
  onConfirm: (paths: string[]) => Promise<void> | void;
}

export const VersionControlDiscardDialog: React.FC<VersionControlDiscardDialogProps> = ({
  open,
  paths,
  onOpenChange,
  onConfirm,
}) => {
  const { t } = useI18n();
  const [isPending, setIsPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setError(null);
      setIsPending(false);
    }
  }, [open]);

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && isPending) {
      return;
    }
    onOpenChange(nextOpen);
  };

  const handleConfirm = async () => {
    if (isPending || paths.length === 0) {
      return;
    }

    setError(null);
    setIsPending(true);
    try {
      await onConfirm(paths);
      onOpenChange(false);
    } catch (discardError) {
      setError(discardError instanceof Error
        ? discardError.message
        : t('shared.versionControl.discardDialog.error'));
    } finally {
      setIsPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex max-h-[calc(100vh-2rem)] max-w-md flex-col overflow-hidden"
        aria-busy={isPending}
        onEscapeKeyDown={(event) => {
          if (isPending) event.preventDefault();
        }}
        onPointerDownOutside={(event) => {
          if (isPending) event.preventDefault();
        }}
      >
        <DialogHeader className="shrink-0">
          <DialogHeading icon={AlertTriangle} iconClassName="h-4 w-4 text-destructive">
            {t('shared.versionControl.discardDialog.title')}
          </DialogHeading>
          <DialogDescription>
            {t('shared.versionControl.discardDialog.description', { count: paths.length })}
          </DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-y-auto rounded-md border bg-muted/20 p-2">
          <ul className="space-y-1 font-mono text-xs">
            {paths.map(path => <li key={path} className="break-all">{path}</li>)}
          </ul>
        </div>
        {error && (
          <Alert variant="destructive" className="shrink-0">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <DialogFooter className="shrink-0 sm:justify-between sm:space-x-0">
          <Button
            type="button"
            variant="outline"
            disabled={isPending}
            onClick={() => handleOpenChange(false)}
          >
            {t('shared.versionControl.discardDialog.cancel')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            disabled={isPending || paths.length === 0}
            onClick={() => void handleConfirm()}
          >
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isPending
              ? t('shared.versionControl.discardDialog.pending')
              : t('shared.versionControl.discardDialog.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
