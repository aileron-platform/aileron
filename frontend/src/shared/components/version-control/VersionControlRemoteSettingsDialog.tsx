import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  GitPullRequest,
  Loader2,
  Save,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';

export interface VersionControlRemoteSettingsState {
  currentBranch?: string | null;
  remoteUrl?: string | null;
  hasOrigin?: boolean;
}

interface VersionControlRemoteSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  repository: VersionControlRemoteSettingsState | null;
  onSaveRemoteUrl: (remoteUrl: string) => void | Promise<void>;
  isSavingRemoteUrl?: boolean;
  initializedSlot?: React.ReactNode;
}

export const VersionControlRemoteSettingsDialog: React.FC<VersionControlRemoteSettingsDialogProps> = ({
  open,
  onOpenChange,
  repository,
  onSaveRemoteUrl,
  isSavingRemoteUrl = false,
  initializedSlot,
}) => {
  const { t } = useI18n();
  const [remoteUrlValue, setRemoteUrlValue] = useState('');

  useEffect(() => {
    if (open) {
      setRemoteUrlValue(repository?.remoteUrl ?? '');
    }
  }, [open, repository?.remoteUrl]);

  const isRemoteUrlValid = Boolean(remoteUrlValue.trim());
  const isRemoteUrlDirty = remoteUrlValue !== (repository?.remoteUrl ?? '');

  const handleSaveRemoteUrl = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isRemoteUrlValid || isSavingRemoteUrl) {
      return;
    }
    void onSaveRemoteUrl(remoteUrlValue.trim());
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen && isSavingRemoteUrl) {
      return;
    }
    onOpenChange(nextOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-w-lg flex-col overflow-hidden">
        <DialogHeader>
          <DialogHeading icon={GitPullRequest} iconClassName="h-4 w-4">
            {t('shared.versionControl.remoteDialog.title')}
          </DialogHeading>
          <DialogDescription>
            {t('shared.versionControl.remoteDialog.description')}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSaveRemoteUrl} className="space-y-4">
          <Alert className="border-green-200 bg-green-50">
            <CheckCircle2 className="h-4 w-4 text-green-600" />
            <AlertDescription className="text-green-800">
              <div className="font-medium">
                {t('shared.versionControl.remoteDialog.initialized.title')}
              </div>
              <div className="mt-1 text-sm">
                {t('shared.versionControl.remoteDialog.initialized.branch', {
                  branch: repository?.currentBranch
                    || t('shared.versionControl.remoteDialog.initialized.noBranch'),
                })}
              </div>
            </AlertDescription>
          </Alert>
          {!repository?.hasOrigin && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {t('shared.versionControl.remoteDialog.remote.missingOrigin')}
              </AlertDescription>
            </Alert>
          )}
          {initializedSlot}
          <div className="space-y-2">
            <Label htmlFor="version-control-remote-url">
              {t('shared.versionControl.remoteDialog.remote.urlLabel')}
            </Label>
            <Input
              id="version-control-remote-url"
              value={remoteUrlValue}
              placeholder={t('shared.versionControl.remoteDialog.remote.urlPlaceholder')}
              onChange={(event) => setRemoteUrlValue(event.target.value)}
              disabled={isSavingRemoteUrl}
            />
          </div>
          <p className="text-xs text-muted-foreground">
            {t('shared.versionControl.remoteDialog.remote.helper')}
          </p>
          <div className="flex justify-end">
            <Button
              type="submit"
              disabled={!isRemoteUrlDirty || !isRemoteUrlValid || isSavingRemoteUrl}
            >
              {isSavingRemoteUrl ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('shared.versionControl.remoteDialog.remote.actions.saving')}
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  {t('shared.versionControl.remoteDialog.remote.actions.save')}
                </>
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
