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
import type { VersionControlCommitSummary } from '@/shared/version-control';

interface VersionControlRevertCommitDialogProps {
  open: boolean;
  commit: VersionControlCommitSummary | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: (sha: string) => Promise<void>;
}

export const VersionControlRevertCommitDialog: React.FC<VersionControlRevertCommitDialogProps> = ({
  open,
  commit,
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
    if (!nextOpen && isPending) return;
    onOpenChange(nextOpen);
  };

  const handleConfirm = async () => {
    if (!commit || isPending) return;
    setError(null);
    setIsPending(true);
    try {
      await onConfirm(commit.id);
      onOpenChange(false);
    } catch (revertError) {
      setError(revertError instanceof Error
        ? revertError.message
        : t('shared.versionControl.commit.revertDialog.error'));
    } finally {
      setIsPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex max-h-[calc(100vh-2rem)] max-w-md flex-col overflow-hidden"
        aria-busy={isPending}
        onEscapeKeyDown={(event) => { if (isPending) event.preventDefault(); }}
        onPointerDownOutside={(event) => { if (isPending) event.preventDefault(); }}
      >
        <DialogHeader className="shrink-0">
          <DialogHeading icon={AlertTriangle} iconClassName="h-4 w-4 text-destructive">
            {t('shared.versionControl.commit.revertDialog.title')}
          </DialogHeading>
          <DialogDescription>
            {t('shared.versionControl.commit.revertDialog.description', { sha: commit?.id.slice(0, 8) ?? '' })}
          </DialogDescription>
        </DialogHeader>
        {commit && <div className="truncate rounded-md border bg-muted/20 p-2 text-sm">{commit.message}</div>}
        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <DialogFooter className="shrink-0 sm:justify-between sm:space-x-0">
          <Button type="button" variant="outline" disabled={isPending} onClick={() => handleOpenChange(false)}>
            {t('shared.versionControl.commit.revertDialog.cancel')}
          </Button>
          <Button type="button" variant="destructive" disabled={isPending || !commit} onClick={() => void handleConfirm()}>
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isPending
              ? t('shared.versionControl.commit.revertDialog.pending')
              : t('shared.versionControl.commit.revertDialog.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
