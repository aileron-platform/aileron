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

interface VersionControlForceUnlockDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => Promise<void>;
}

export const VersionControlForceUnlockDialog: React.FC<VersionControlForceUnlockDialogProps> = ({
  open,
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

  const setOpen = (nextOpen: boolean) => {
    if (!nextOpen && isPending) return;
    onOpenChange(nextOpen);
  };

  const confirm = async () => {
    if (isPending) return;
    setError(null);
    setIsPending(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch (unlockError) {
      setError(unlockError instanceof Error
        ? unlockError.message
        : t('shared.versionControl.conflict.forceUnlockFailed.description'));
    } finally {
      setIsPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent
        className="flex max-h-[calc(100vh-2rem)] max-w-md flex-col overflow-hidden"
        aria-busy={isPending}
        onEscapeKeyDown={(event) => { if (isPending) event.preventDefault(); }}
        onPointerDownOutside={(event) => { if (isPending) event.preventDefault(); }}
      >
        <DialogHeader>
          <DialogHeading icon={AlertTriangle} iconClassName="h-4 w-4 text-destructive">
            {t('shared.versionControl.conflict.forceUnlockDialog.title')}
          </DialogHeading>
          <DialogDescription>
            {t('shared.versionControl.conflict.forceUnlockDialog.description')}
          </DialogDescription>
        </DialogHeader>
        {error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
        <DialogFooter className="sm:justify-between sm:space-x-0">
          <Button type="button" variant="outline" disabled={isPending} onClick={() => setOpen(false)}>
            {t('shared.versionControl.conflict.forceUnlockDialog.cancel')}
          </Button>
          <Button type="button" variant="destructive" disabled={isPending} onClick={() => void confirm()}>
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isPending
              ? t('shared.versionControl.conflict.forceUnlockDialog.pending')
              : t('shared.versionControl.conflict.forceUnlockDialog.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
