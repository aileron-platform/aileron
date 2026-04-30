import React, { useCallback, useEffect, useState } from 'react';
import { AlertCircle, GitBranch, Loader2, Play, RefreshCcw } from 'lucide-react';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/shared/components/ui/alert';
import { TaskProgressCard } from '@/shared/components/task-progress/TaskProgressCard';
import { useTaskProgress } from '@/shared/hooks/useTaskProgress';
import { useToast } from '@/shared/components/ui/use-toast';
import { useI18n } from '@/shared/hooks/useI18n';
import { createLogger } from '@/shared/services/logger';
import {
  cloneRepository,
  getCloneProgress,
  getRepositoryStatus,
  initRepository,
  type GitRepositoryStatus,
} from '@/features/template-management/api/templateGitApi';

const logger = createLogger('TemplateRegistryOnboardingBoundary');

export interface TemplateRegistryOnboardingBoundaryProps {
  children: React.ReactNode;
}

export const TemplateRegistryOnboardingBoundary: React.FC<TemplateRegistryOnboardingBoundaryProps> = ({ children }) => {
  const { t } = useI18n();
  const { toast } = useToast();
  const [repositoryStatus, setRepositoryStatus] = useState<GitRepositoryStatus | null>(null);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [statusError, setStatusError] = useState(false);
  const [cloneUrl, setCloneUrl] = useState('');
  const [cloneBranch, setCloneBranch] = useState('');
  const [isSubmittingClone, setIsSubmittingClone] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);

  const refreshRepositoryStatus = useCallback(async () => {
    setIsLoadingStatus(true);
    setStatusError(false);
    try {
      const nextStatus = await getRepositoryStatus();
      setRepositoryStatus(nextStatus);
      return nextStatus;
    } catch (error) {
      logger.error('Failed to load Template Center repository status', { error });
      setStatusError(true);
      return null;
    } finally {
      setIsLoadingStatus(false);
    }
  }, []);

  const {
    progress: cloneProgress,
    isPolling: isClonePolling,
    startPolling: startClonePolling,
    resetProgress: resetCloneProgress,
  } = useTaskProgress(null, getCloneProgress, {
    onComplete: (progress) => {
      if (progress.status === 'completed') {
        void refreshRepositoryStatus();
      }
    },
    onError: (error) => {
      logger.error('Failed to poll Template Center clone progress', { error });
    },
  });

  useEffect(() => {
    void refreshRepositoryStatus();
  }, [refreshRepositoryStatus]);

  const handleClone = async () => {
    const url = cloneUrl.trim();
    if (!url) {
      toast({
        title: t('template.center.onboarding.toasts.cloneFailed.title'),
        description: t('template.center.onboarding.validation.cloneUrlRequired'),
        variant: 'destructive',
      });
      return;
    }

    setIsSubmittingClone(true);
    resetCloneProgress();
    try {
      const response = await cloneRepository({
        url,
        branch: cloneBranch.trim() || undefined,
      });

      if (response.success) {
        toast({
          title: t('template.center.onboarding.toasts.cloneStarted.title'),
          description: t('template.center.onboarding.toasts.cloneStarted.description'),
          variant: 'success',
        });

        if (response.task_id) {
          startClonePolling(response.task_id);
        } else {
          await refreshRepositoryStatus();
        }
      } else {
        toast({
          title: t('template.center.onboarding.toasts.cloneFailed.title'),
          description: t('template.center.onboarding.toasts.cloneFailed.description', {
            error: response.error || response.message || t('template.center.onboarding.unknownError'),
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('Failed to start Template Center clone', { error });
      toast({
        title: t('template.center.onboarding.toasts.cloneFailed.title'),
        description: t('template.center.onboarding.toasts.cloneFailed.description', {
          error: error instanceof Error ? error.message : t('template.center.onboarding.unknownError'),
        }),
        variant: 'destructive',
      });
    } finally {
      setIsSubmittingClone(false);
    }
  };

  const handleInitialize = async () => {
    setIsInitializing(true);
    try {
      const response = await initRepository();
      if (response.success) {
        toast({
          title: t('template.center.onboarding.toasts.initSuccess.title'),
          description: t('template.center.onboarding.toasts.initSuccess.description'),
          variant: 'success',
        });
        await refreshRepositoryStatus();
      } else {
        toast({
          title: t('template.center.onboarding.toasts.initFailed.title'),
          description: t('template.center.onboarding.toasts.initFailed.description', {
            error: response.error || response.message || t('template.center.onboarding.unknownError'),
          }),
          variant: 'destructive',
        });
      }
    } catch (error) {
      logger.error('Failed to initialize Template Center repository', { error });
      toast({
        title: t('template.center.onboarding.toasts.initFailed.title'),
        description: t('template.center.onboarding.toasts.initFailed.description', {
          error: error instanceof Error ? error.message : t('template.center.onboarding.unknownError'),
        }),
        variant: 'destructive',
      });
    } finally {
      setIsInitializing(false);
    }
  };

  if (isLoadingStatus) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('template.center.onboarding.loading')}
        </div>
      </div>
    );
  }

  if (statusError) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="w-full max-w-xl space-y-4 rounded-lg border border-border bg-background p-6">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t('template.center.onboarding.statusError.title')}</AlertTitle>
            <AlertDescription>{t('template.center.onboarding.statusError.description')}</AlertDescription>
          </Alert>
          <div className="flex justify-end">
            <Button type="button" variant="outline" onClick={() => void refreshRepositoryStatus()}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              {t('template.center.onboarding.actions.retry')}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (repositoryStatus?.isGitRepo) {
    return <>{children}</>;
  }

  const canClone = Boolean(repositoryStatus?.canCloneSafely);
  const canInit = repositoryStatus?.canInitSafely !== false;
  const cloneDisabled = !canClone || isSubmittingClone || isClonePolling;
  const initializeDisabled = !canInit || isInitializing || isClonePolling;

  return (
    <div className="flex h-full min-h-0 items-center justify-center overflow-auto p-4 sm:p-6">
      <div className="w-full max-w-3xl rounded-lg border border-border bg-background">
        <div className="border-b border-border px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <GitBranch className="h-5 w-5" />
            </div>
            <div className="min-w-0 space-y-1">
              <h2 className="text-lg font-semibold leading-tight">{t('template.center.onboarding.title')}</h2>
              <p className="text-sm text-muted-foreground">{t('template.center.onboarding.description')}</p>
            </div>
          </div>
        </div>

        <div className="grid gap-4 p-5 sm:grid-cols-[1.2fr_0.8fr] sm:p-6">
          <section className="space-y-4 rounded-lg border border-border p-4">
            <div className="space-y-1">
              <h3 className="text-sm font-semibold">{t('template.center.onboarding.clone.title')}</h3>
              <p className="text-sm text-muted-foreground">
                {canClone
                  ? t('template.center.onboarding.clone.description')
                  : t('template.center.onboarding.clone.blockedDescription')}
              </p>
            </div>

            {!canClone && (
              <Alert>
                <AlertCircle className="h-4 w-4" />
                <AlertTitle>{t('template.center.onboarding.clone.blockedTitle')}</AlertTitle>
                <AlertDescription>{t('template.center.onboarding.clone.blockedReason')}</AlertDescription>
              </Alert>
            )}

            <div className="space-y-3">
              <div className="space-y-1.5">
                <Label htmlFor="template-registry-clone-url">
                  {t('template.center.onboarding.clone.urlLabel')}
                </Label>
                <Input
                  id="template-registry-clone-url"
                  value={cloneUrl}
                  onChange={(event) => setCloneUrl(event.target.value)}
                  placeholder={t('template.center.onboarding.clone.urlPlaceholder')}
                  disabled={!canClone || isSubmittingClone || isClonePolling}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="template-registry-clone-branch">
                  {t('template.center.onboarding.clone.branchLabel')}
                </Label>
                <Input
                  id="template-registry-clone-branch"
                  value={cloneBranch}
                  onChange={(event) => setCloneBranch(event.target.value)}
                  placeholder={t('template.center.onboarding.clone.branchPlaceholder')}
                  disabled={!canClone || isSubmittingClone || isClonePolling}
                />
                <p className="text-xs text-muted-foreground">
                  {t('template.center.onboarding.clone.branchHelper')}
                </p>
              </div>
            </div>

            <Button type="button" className="w-full sm:w-auto" disabled={cloneDisabled} onClick={handleClone}>
              {isSubmittingClone || isClonePolling ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <GitBranch className="mr-2 h-4 w-4" />
              )}
              {isSubmittingClone || isClonePolling
                ? t('template.center.onboarding.clone.actions.cloning')
                : t('template.center.onboarding.clone.actions.clone')}
            </Button>

            {cloneProgress && (
              <TaskProgressCard
                progress={cloneProgress}
                title={t('template.center.onboarding.clone.progressTitle')}
                className="mt-2"
              />
            )}
          </section>

          <section className="space-y-4 rounded-lg border border-border p-4">
            <div className="space-y-1">
              <h3 className="text-sm font-semibold">{t('template.center.onboarding.init.title')}</h3>
              <p className="text-sm text-muted-foreground">{t('template.center.onboarding.init.description')}</p>
            </div>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={initializeDisabled}
              onClick={handleInitialize}
            >
              {isInitializing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Play className="mr-2 h-4 w-4" />
              )}
              {isInitializing
                ? t('template.center.onboarding.init.actions.initializing')
                : t('template.center.onboarding.init.actions.init')}
            </Button>
          </section>
        </div>
      </div>
    </div>
  );
};

export default TemplateRegistryOnboardingBoundary;
