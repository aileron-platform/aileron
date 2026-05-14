import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, GitPullRequest, Loader2, Save } from 'lucide-react';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader } from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { useI18n } from '@/shared/hooks/useI18n';

export interface VersionControlRemoteSettingsState {
  isRepositoryInitialized: boolean;
  currentBranch?: string | null;
  remoteUrl?: string | null;
  hasOrigin?: boolean;
  hasLocalContent?: boolean;
  canCloneSafely?: boolean;
  canInitSafely?: boolean;
}

export interface VersionControlRemoteSettingsCapabilities {
  canConfigureRemote?: boolean;
  supportsRemoteInit?: boolean;
  supportsRemoteClone?: boolean;
}

interface VersionControlRemoteSettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  repository: VersionControlRemoteSettingsState | null;
  capabilities: VersionControlRemoteSettingsCapabilities;
  onSaveRemoteUrl?: (remoteUrl: string) => void | Promise<void>;
  onInitRepository?: () => void | Promise<void>;
  onCloneRepository?: (remoteUrl: string, branch?: string) => void | Promise<void>;
  isSavingRemoteUrl?: boolean;
  isInitializingRepository?: boolean;
  isCloningRepository?: boolean;
  isCloneProgressActive?: boolean;
  progressSlot?: React.ReactNode;
}

export const VersionControlRemoteSettingsDialog: React.FC<VersionControlRemoteSettingsDialogProps> = ({
  open,
  onOpenChange,
  repository,
  capabilities,
  onSaveRemoteUrl,
  onInitRepository,
  onCloneRepository,
  isSavingRemoteUrl = false,
  isInitializingRepository = false,
  isCloningRepository = false,
  isCloneProgressActive = false,
  progressSlot,
}) => {
  const { t } = useI18n();
  const [remoteUrlValue, setRemoteUrlValue] = useState('');
  const [branchValue, setBranchValue] = useState('');

  useEffect(() => {
    if (open) {
      setRemoteUrlValue(repository?.remoteUrl ?? '');
      setBranchValue('');
    }
  }, [open, repository?.remoteUrl]);

  const isRepositoryInitialized = Boolean(repository?.isRepositoryInitialized);
  const isRemoteUrlValid = Boolean(remoteUrlValue.trim());
  const isRemoteUrlDirty = remoteUrlValue !== (repository?.remoteUrl ?? '');
  const isBusy = isSavingRemoteUrl || isInitializingRepository || isCloningRepository || isCloneProgressActive;
  const canConfigureRemote = Boolean(capabilities.canConfigureRemote && onSaveRemoteUrl);
  const canInit = Boolean(capabilities.supportsRemoteInit && onInitRepository);
  const canClone = Boolean(capabilities.supportsRemoteClone && onCloneRepository);
  const canCloneSafely = repository?.canCloneSafely ?? true;
  const canInitSafely = repository?.canInitSafely ?? true;

  const cloneHelperKey = useMemo(() => (
    canCloneSafely
      ? 'shared.versionControl.remoteDialog.clone.helper'
      : 'shared.versionControl.remoteDialog.clone.disabledHelper'
  ), [canCloneSafely]);

  const handleSaveRemoteUrl = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isRemoteUrlValid || !canConfigureRemote) {
      return;
    }
    void onSaveRemoteUrl?.(remoteUrlValue.trim());
  };

  const handleCloneRepository = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isRemoteUrlValid || !canClone) {
      return;
    }
    void onCloneRepository?.(remoteUrlValue.trim(), branchValue.trim() || undefined);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogHeading icon={GitPullRequest} iconClassName="h-4 w-4">
            {t('shared.versionControl.remoteDialog.title')}
          </DialogHeading>
          <DialogDescription>{t('shared.versionControl.remoteDialog.description')}</DialogDescription>
        </DialogHeader>

        {isRepositoryInitialized ? (
          <form onSubmit={handleSaveRemoteUrl} className="space-y-4">
            <Alert className="border-green-200 bg-green-50">
              <CheckCircle2 className="h-4 w-4 text-green-600" />
              <AlertDescription className="text-green-800">
                <div className="font-medium">
                  {t('shared.versionControl.remoteDialog.initialized.title')}
                </div>
                <div className="mt-1 text-sm">
                  {t('shared.versionControl.remoteDialog.initialized.branch', {
                    branch: repository?.currentBranch || t('shared.versionControl.remoteDialog.initialized.noBranch'),
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
            {canConfigureRemote && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="version-control-remote-url">
                    {t('shared.versionControl.remoteDialog.remote.urlLabel')}
                  </Label>
                  <Input
                    id="version-control-remote-url"
                    value={remoteUrlValue}
                    placeholder={t('shared.versionControl.remoteDialog.remote.urlPlaceholder')}
                    onChange={(event) => setRemoteUrlValue(event.target.value)}
                    disabled={isBusy}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  {t('shared.versionControl.remoteDialog.remote.helper')}
                </p>
                <div className="flex justify-end">
                  <Button type="submit" disabled={!isRemoteUrlDirty || !isRemoteUrlValid || isBusy}>
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
              </>
            )}
          </form>
        ) : (
          <form onSubmit={handleCloneRepository} className="space-y-4">
            {repository?.hasLocalContent && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {t('shared.versionControl.remoteDialog.setup.localContentWarning')}
                </AlertDescription>
              </Alert>
            )}
            {canClone && (
              <>
                <div className="space-y-2">
                  <Label htmlFor="version-control-clone-url">
                    {t('shared.versionControl.remoteDialog.clone.urlLabel')}
                  </Label>
                  <Input
                    id="version-control-clone-url"
                    value={remoteUrlValue}
                    placeholder={t('shared.versionControl.remoteDialog.remote.urlPlaceholder')}
                    onChange={(event) => setRemoteUrlValue(event.target.value)}
                    disabled={isBusy}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="version-control-clone-branch">
                    {t('shared.versionControl.remoteDialog.clone.branchLabel')}
                  </Label>
                  <Input
                    id="version-control-clone-branch"
                    value={branchValue}
                    placeholder={t('shared.versionControl.remoteDialog.clone.branchPlaceholder')}
                    onChange={(event) => setBranchValue(event.target.value)}
                    disabled={isBusy}
                  />
                  <p className="text-xs text-muted-foreground">
                    {t('shared.versionControl.remoteDialog.clone.branchHelper')}
                  </p>
                </div>
                <p className="text-xs text-muted-foreground">{t(cloneHelperKey)}</p>
              </>
            )}
            <div className="flex justify-end gap-2">
              {canInit && (
                <Button
                  type="button"
                  variant="outline"
                  disabled={!canInitSafely || isBusy}
                  onClick={() => void onInitRepository?.()}
                >
                  {isInitializingRepository ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('shared.versionControl.remoteDialog.setup.actions.initializing')}
                    </>
                  ) : (
                    t('shared.versionControl.remoteDialog.setup.actions.init')
                  )}
                </Button>
              )}
              {canClone && (
                <Button type="submit" disabled={!isRemoteUrlValid || !canCloneSafely || isBusy}>
                  {isCloneProgressActive || isCloningRepository ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('shared.versionControl.remoteDialog.clone.actions.cloning')}
                    </>
                  ) : (
                    t('shared.versionControl.remoteDialog.clone.actions.clone')
                  )}
                </Button>
              )}
            </div>
            {progressSlot && <div className="border-t pt-4">{progressSlot}</div>}
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default VersionControlRemoteSettingsDialog;
