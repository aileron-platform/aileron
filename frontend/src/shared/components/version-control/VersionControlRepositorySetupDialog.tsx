import { DialogHeading } from '@/shared/components/ui/dialog-heading';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  GitPullRequest,
  KeyRound,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { Button } from '@/shared/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
} from '@/shared/components/ui/dialog';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/shared/components/ui/select';
import { useI18n } from '@/shared/hooks/useI18n';
import type { RepositorySetupWorkflow } from '@/shared/version-control/repositorySetupWorkflow';

interface VersionControlRepositorySetupDialogProps {
  workflow: RepositorySetupWorkflow;
}

export const VersionControlRepositorySetupDialog = ({
  workflow,
}: VersionControlRepositorySetupDialogProps) => {
  const { t } = useI18n();
  const { state, events } = workflow;
  const isDiscovering = state.phase === 'discovering';
  const isCloning = state.phase === 'cloning';
  const inputsDisabled = isDiscovering || isCloning;
  const cloneHelperKey = state.isCloneSafetyConfirmed
    ? 'shared.versionControl.repositorySetup.clone.helper'
    : 'shared.versionControl.repositorySetup.clone.disabledHelper';

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void events.clone();
  };

  const handleInitializeSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    void events.initialize();
  };

  return (
    <>
    <Dialog
      open={state.initializeDialogOpen}
      onOpenChange={(open) => { if (!open) events.closeInitialize(); }}
    >
      <DialogContent
        className="flex max-h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-2xl flex-col overflow-hidden"
        aria-busy={state.phase === 'initializing'}
        onEscapeKeyDown={(event) => { if (state.phase === 'initializing') event.preventDefault(); }}
        onPointerDownOutside={(event) => { if (state.phase === 'initializing') event.preventDefault(); }}
      >
        <DialogHeader>
          <DialogHeading icon={GitPullRequest} iconClassName="h-4 w-4">
            {t('shared.versionControl.repositorySetup.initializeDialog.title')}
          </DialogHeading>
          <DialogDescription>
            {t('shared.versionControl.repositorySetup.initializeDialog.description')}
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleInitializeSubmit} className="flex min-h-0 flex-1 flex-col gap-4">
          <div className="min-h-0 flex-1 overflow-auto py-2">
            <Label htmlFor="version-control-default-branch">
              {t('shared.versionControl.repositorySetup.initializeDialog.defaultBranchLabel')}
            </Label>
            <Input
              id="version-control-default-branch"
              value={state.defaultBranch}
              onChange={(event) => events.changeDefaultBranch(event.target.value)}
              disabled={state.phase === 'initializing'}
              autoFocus
            />
            {state.error === 'initializeFailed' ? (
              <Alert variant="destructive" className="mt-4">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>{t('shared.versionControl.repositorySetup.errors.title')}</AlertTitle>
                <AlertDescription>{t('shared.versionControl.repositorySetup.errors.init')}</AlertDescription>
              </Alert>
            ) : null}
          </div>
          <DialogFooter className="shrink-0 sm:justify-between sm:space-x-0">
            <Button type="button" variant="outline" disabled={state.phase === 'initializing'} onClick={events.closeInitialize}>
              {t('shared.versionControl.repositorySetup.initializeDialog.cancel')}
            </Button>
            <Button type="submit" disabled={!state.canSubmitInitialize}>
              {state.phase === 'initializing' && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {t(state.phase === 'initializing'
                ? 'shared.versionControl.repositorySetup.actions.initializing'
                : 'shared.versionControl.repositorySetup.actions.init')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
    <Dialog
      open={state.cloneDialogOpen}
      onOpenChange={(open) => {
        if (!open) events.closeClone();
      }}
    >
      <DialogContent
        className="flex max-h-[calc(100vh-2rem)] w-[calc(100vw-2rem)] max-w-2xl flex-col overflow-hidden"
        aria-busy={inputsDisabled}
        onEscapeKeyDown={(event) => { if (inputsDisabled) event.preventDefault(); }}
        onPointerDownOutside={(event) => { if (inputsDisabled) event.preventDefault(); }}
      >
        <DialogHeader>
          <DialogHeading icon={GitPullRequest} iconClassName="h-4 w-4">
            {t('shared.versionControl.repositorySetup.dialog.title')}
          </DialogHeading>
          <DialogDescription>
            {t('shared.versionControl.repositorySetup.dialog.description')}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="min-h-0 flex-1 space-y-4 overflow-auto">
          {state.hasLocalContent && (
            <Alert>
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                {t('shared.versionControl.repositorySetup.localContentWarning')}
              </AlertDescription>
            </Alert>
          )}

          <div className="space-y-2">
            <Label htmlFor="version-control-clone-url">
              {t('shared.versionControl.repositorySetup.clone.urlLabel')}
            </Label>
            <div className="flex items-center gap-2">
              <Input
                id="version-control-clone-url"
                value={state.remoteUrl}
                placeholder={t('shared.versionControl.repositorySetup.clone.urlPlaceholder')}
                onChange={(event) => events.changeRemoteUrl(event.target.value)}
                disabled={inputsDisabled}
              />
              <Button
                type="button"
                variant="outline"
                className="shrink-0"
                disabled={!state.canDiscoverBranches || inputsDisabled}
                onClick={() => void events.discoverBranches()}
              >
                {isDiscovering ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="mr-2 h-4 w-4" />
                )}
                {t(
                  isDiscovering
                    ? 'shared.versionControl.repositorySetup.clone.actions.loadingBranches'
                    : 'shared.versionControl.repositorySetup.clone.actions.loadBranches',
                )}
              </Button>
            </div>
          </div>

          {state.hasDiscoveredBranches && state.branches.length > 0 && (
            <div className="space-y-2">
              <Label htmlFor="version-control-clone-branch-trigger">
                {t('shared.versionControl.repositorySetup.clone.branchLabel')}
              </Label>
              <Select
                value={state.selectedBranch}
                onValueChange={events.selectBranch}
                disabled={inputsDisabled}
              >
                <SelectTrigger id="version-control-clone-branch-trigger">
                  <SelectValue
                    placeholder={t('shared.versionControl.repositorySetup.clone.branchPlaceholder')}
                  />
                </SelectTrigger>
                <SelectContent>
                  {state.branches.map(branch => (
                    <SelectItem key={branch} value={branch}>
                      {branch}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {t('shared.versionControl.repositorySetup.clone.branchHelper')}
              </p>
            </div>
          )}

          {state.hasDiscoveredBranches && state.branches.length === 0 && (
            <p className="text-xs text-muted-foreground">
              {t('shared.versionControl.repositorySetup.clone.branchesEmpty')}
            </p>
          )}

          {state.error === 'sshKeyRequired' && (
            <Alert variant="warning">
              <KeyRound className="h-4 w-4" />
              <AlertTitle>
                {t('shared.versionControl.repositorySetup.sshKeyRequired.title')}
              </AlertTitle>
              <AlertDescription className="space-y-3">
                <p>
                  {t('shared.versionControl.repositorySetup.sshKeyRequired.description')}
                </p>
                <Button asChild type="button" size="sm" variant="outline">
                  <Link to="/settings">
                    {t('shared.versionControl.repositorySetup.sshKeyRequired.action')}
                  </Link>
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {(state.error === 'cloneFailed' || state.error === 'discoveryFailed') && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>
                {t('shared.versionControl.repositorySetup.errors.title')}
              </AlertTitle>
              <AlertDescription>
                {t(
                  state.error === 'cloneFailed'
                    ? 'shared.versionControl.repositorySetup.errors.clone'
                    : 'shared.versionControl.repositorySetup.errors.discovery',
                )}
              </AlertDescription>
            </Alert>
          )}

          <p className="text-xs text-muted-foreground">{t(cloneHelperKey)}</p>
          <div className="flex justify-end">
            <Button type="submit" disabled={!state.canSubmitClone || inputsDisabled}>
              {isCloning ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t('shared.versionControl.repositorySetup.clone.actions.cloning')}
                </>
              ) : (
                t('shared.versionControl.repositorySetup.actions.clone')
              )}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
    </>
  );
};
