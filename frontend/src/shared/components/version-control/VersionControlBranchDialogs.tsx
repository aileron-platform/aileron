import React, { useEffect, useState } from 'react';
import { AlertTriangle, GitBranch, Loader2, UploadCloud } from 'lucide-react';
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
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';

interface DialogLifecycleProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const errorText = (error: unknown, fallback: string): string => (
  error instanceof Error ? error.message : fallback
);

export const VersionControlRenameBranchDialog: React.FC<DialogLifecycleProps & {
  branch: string;
  onConfirm: (newName: string) => Promise<void> | void;
}> = ({ open, branch, onOpenChange, onConfirm }) => {
  const { t } = useI18n();
  const [value, setValue] = useState(branch);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setValue(branch);
      setError(null);
    }
  }, [branch, open]);

  const close = (nextOpen: boolean) => {
    if (!nextOpen && pending) return;
    onOpenChange(nextOpen);
  };
  const submit = async () => {
    const newName = value.trim();
    if (!newName || newName === branch || pending) return;
    setPending(true);
    setError(null);
    try {
      await onConfirm(newName);
      onOpenChange(false);
    } catch (submitError) {
      setError(errorText(submitError, t('shared.versionControl.branch.rename.error')));
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="flex max-h-[calc(100vh-2rem)] max-w-lg flex-col overflow-hidden" aria-busy={pending}>
        <DialogHeader>
          <DialogHeading icon={GitBranch}>{t('shared.versionControl.branch.rename.title')}</DialogHeading>
          <DialogDescription>{t('shared.versionControl.branch.rename.description', { branch })}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-2 overflow-y-auto">
          <Label htmlFor="version-control-rename-branch">{t('shared.versionControl.branch.rename.label')}</Label>
          <Input
            id="version-control-rename-branch"
            value={value}
            disabled={pending}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void submit();
            }}
          />
        </div>
        {error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
        <DialogFooter className="sm:justify-between sm:space-x-0">
          <Button type="button" variant="outline" disabled={pending} onClick={() => close(false)}>
            {t('shared.versionControl.branch.dialog.cancel')}
          </Button>
          <Button type="button" disabled={!value.trim() || value.trim() === branch || pending} onClick={() => void submit()}>
            {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {pending ? t('shared.versionControl.branch.dialog.pending') : t('shared.versionControl.branch.rename.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const VersionControlDeleteBranchDialog: React.FC<DialogLifecycleProps & {
  branch: string;
  onConfirm: () => Promise<void> | void;
}> = ({ open, branch, onOpenChange, onConfirm }) => {
  const { t } = useI18n();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) setError(null);
  }, [open]);

  const close = (nextOpen: boolean) => {
    if (!nextOpen && pending) return;
    onOpenChange(nextOpen);
  };
  const submit = async () => {
    if (pending) return;
    setPending(true);
    setError(null);
    try {
      await onConfirm();
      onOpenChange(false);
    } catch (submitError) {
      setError(errorText(submitError, t('shared.versionControl.branch.delete.error')));
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="flex max-h-[calc(100vh-2rem)] max-w-md flex-col overflow-hidden" aria-busy={pending}>
        <DialogHeader>
          <DialogHeading icon={AlertTriangle} iconClassName="text-destructive">
            {t('shared.versionControl.branch.delete.title')}
          </DialogHeading>
          <DialogDescription>{t('shared.versionControl.branch.delete.description', { branch })}</DialogDescription>
        </DialogHeader>
        {error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
        <DialogFooter className="sm:justify-between sm:space-x-0">
          <Button type="button" variant="outline" disabled={pending} onClick={() => close(false)}>
            {t('shared.versionControl.branch.dialog.cancel')}
          </Button>
          <Button type="button" variant="destructive" disabled={pending} onClick={() => void submit()}>
            {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {pending ? t('shared.versionControl.branch.dialog.pending') : t('shared.versionControl.branch.delete.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export const VersionControlPublishBranchDialog: React.FC<DialogLifecycleProps & {
  branch: string;
  onConfirm: (remote: string, remoteName?: string) => Promise<void> | void;
}> = ({ open, branch, onOpenChange, onConfirm }) => {
  const { t } = useI18n();
  const [remote, setRemote] = useState('origin');
  const [remoteName, setRemoteName] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setRemote('origin');
      setRemoteName('');
      setError(null);
    }
  }, [open]);

  const close = (nextOpen: boolean) => {
    if (!nextOpen && pending) return;
    onOpenChange(nextOpen);
  };
  const submit = async () => {
    if (!remote.trim() || pending) return;
    setPending(true);
    setError(null);
    try {
      await onConfirm(remote.trim(), remoteName.trim() || undefined);
      onOpenChange(false);
    } catch (submitError) {
      setError(errorText(submitError, t('shared.versionControl.branch.publish.error')));
    } finally {
      setPending(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="flex max-h-[calc(100vh-2rem)] max-w-lg flex-col overflow-hidden" aria-busy={pending}>
        <DialogHeader>
          <DialogHeading icon={UploadCloud}>{t('shared.versionControl.branch.publish.title')}</DialogHeading>
          <DialogDescription>{t('shared.versionControl.branch.publish.description', { branch })}</DialogDescription>
        </DialogHeader>
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto">
          <div className="space-y-2">
            <Label htmlFor="version-control-publish-remote">{t('shared.versionControl.branch.publish.remoteLabel')}</Label>
            <Input id="version-control-publish-remote" value={remote} disabled={pending} onChange={(event) => setRemote(event.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="version-control-publish-name">{t('shared.versionControl.branch.publish.remoteNameLabel')}</Label>
            <Input id="version-control-publish-name" value={remoteName} disabled={pending} placeholder={branch} onChange={(event) => setRemoteName(event.target.value)} />
          </div>
        </div>
        {error && <Alert variant="destructive"><AlertTriangle className="h-4 w-4" /><AlertDescription>{error}</AlertDescription></Alert>}
        <DialogFooter className="sm:justify-between sm:space-x-0">
          <Button type="button" variant="outline" disabled={pending} onClick={() => close(false)}>
            {t('shared.versionControl.branch.dialog.cancel')}
          </Button>
          <Button type="button" disabled={!remote.trim() || pending} onClick={() => void submit()}>
            {pending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {pending ? t('shared.versionControl.branch.dialog.pending') : t('shared.versionControl.branch.publish.confirm')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
