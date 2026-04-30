import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, GitBranch, GitPullRequest, CheckCircle2, Loader2, Save } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/shared/components/ui/card';
import { Input } from '@/shared/components/ui/input';
import { Label } from '@/shared/components/ui/label';
import { Button } from '@/shared/components/ui/button';
import { Alert, AlertDescription } from '@/shared/components/ui/alert';
import { useI18n } from '@/shared/hooks/useI18n';
import { useTaskProgress } from '@/shared/hooks/useTaskProgress';
import { TaskProgressCard } from '@/shared/components/task-progress/TaskProgressCard';
import type { GitRepositoryStatus, GitUserConfigRequest } from '@/features/template-management/api/templateGitApi';
import { getCloneProgress } from '@/features/template-management/api/templateGitApi';

interface GitUserConfigTabProps {
  value: GitUserConfigRequest | null;
  remoteUrl: string;
  repositoryStatus: GitRepositoryStatus | null;
  onSave: (value: GitUserConfigRequest) => Promise<void> | void;
  onSaveRemoteUrl: (remoteUrl: string) => Promise<void> | void;
  onCloneRepository: (url: string, branch?: string) => Promise<{ task_id?: string } | void> | { task_id?: string } | void;
  onInitRepository: () => Promise<void> | void;
  onRepositoryStatusRefresh: () => Promise<GitRepositoryStatus> | void;
  isSaving?: boolean;
  isSavingRemoteUrl?: boolean;
  isCloningRepository?: boolean;
  isInitializingRepository?: boolean;
  showRepositorySettings?: boolean;
  showUserConfig?: boolean;
}

const emptyConfig: GitUserConfigRequest = {
  userName: '',
  userEmail: '',
};

export const GitUserConfigTab: React.FC<GitUserConfigTabProps> = ({
  value,
  remoteUrl,
  repositoryStatus,
  onSave,
  onSaveRemoteUrl,
  onCloneRepository,
  onInitRepository,
  onRepositoryStatusRefresh,
  isSaving,
  isSavingRemoteUrl,
  isCloningRepository,
  isInitializingRepository,
  showRepositorySettings = true,
  showUserConfig = true
}) => {
  const { t } = useI18n();
  const [formValue, setFormValue] = useState<GitUserConfigRequest>(emptyConfig);
  const [repoUrlValue, setRepoUrlValue] = useState<string>('');
  const [branchValue, setBranchValue] = useState<string>('');

  // 使用 useTaskProgress Hook 管理 clone 進度
  const {
    progress: taskProgress,
    isPolling,
    startPolling,
    resetProgress: resetCloneProgress,
  } = useTaskProgress(null, getCloneProgress, {
    onComplete: () => {
      void onRepositoryStatusRefresh();
    },
  });

  useEffect(() => {
    if (value) {
      setFormValue({ ...value });
    } else {
      setFormValue(emptyConfig);
    }
  }, [value]);

  useEffect(() => {
    setRepoUrlValue(remoteUrl);
  }, [remoteUrl]);

  const initialUserName = value?.userName ?? '';
  const initialUserEmail = value?.userEmail ?? '';

  const isUserConfigDirty = useMemo(() => {
    return (
      formValue.userName !== initialUserName ||
      formValue.userEmail !== initialUserEmail
    );
  }, [formValue.userEmail, formValue.userName, initialUserEmail, initialUserName]);

  const isUserConfigValid = useMemo(() => {
    return Boolean(formValue.userName.trim()) && Boolean(formValue.userEmail.trim());
  }, [formValue.userEmail, formValue.userName]);

  const isRepoUrlValid = useMemo(() => {
    return Boolean(repoUrlValue.trim());
  }, [repoUrlValue]);

  const isRemoteUrlDirty = repoUrlValue !== (remoteUrl ?? '');
  const isRepositoryInitialized = Boolean(repositoryStatus?.isGitRepo);

  const handleChange = (key: keyof GitUserConfigRequest, nextValue: string) => {
    setFormValue((prev) => ({
      ...prev,
      [key]: nextValue,
    }));
  };

  const handleSubmitUserConfig = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isUserConfigValid) {
      return;
    }
    void onSave({
      userName: formValue.userName.trim(),
      userEmail: formValue.userEmail.trim(),
    });
  };

  const handleCloneRepository = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!isRepoUrlValid) {
      return;
    }

    try {
      const result = await onCloneRepository(repoUrlValue.trim(), branchValue.trim() || undefined);
      if (result && result.task_id) {
        startPolling(result.task_id);
      } else {
        await onRepositoryStatusRefresh();
      }
    } catch (error) {
      // 錯誤由父組件的 toast 處理
    }
  };

  const handleSaveRemoteUrl = (event: React.FormEvent) => {
    event.preventDefault();
    if (!isRepoUrlValid) {
      return;
    }
    void onSaveRemoteUrl(repoUrlValue.trim());
  };

  return (
    <div className="space-y-4">
      {/* Repository lifecycle */}
      {showRepositorySettings && (!isRepositoryInitialized ? (
      <form onSubmit={handleCloneRepository}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitPullRequest className="h-5 w-5" />
              {t('template.center.settingsDialog.git.repositorySetup.title')}
            </CardTitle>
            <CardDescription>
              {t('template.center.settingsDialog.git.repositorySetup.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {repositoryStatus?.hasLocalContent && (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  {t('template.center.settingsDialog.git.repositorySetup.localContentWarning')}
                </AlertDescription>
              </Alert>
            )}

            <div className="space-y-2">
              <Label htmlFor="gitRepoUrl">
                {t('template.center.settingsDialog.git.cloneRepo.urlLabel')}
              </Label>
              <div className="relative">
                <Input
                  id="gitRepoUrl"
                  value={repoUrlValue}
                  placeholder={t('template.center.settingsDialog.git.cloneRepo.urlPlaceholder')}
                  onChange={(event) => setRepoUrlValue(event.target.value)}
                  disabled={isCloningRepository || isPolling}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="gitBranch">
                {t('template.center.settingsDialog.git.cloneRepo.branchLabel')}
              </Label>
              <Input
                id="gitBranch"
                value={branchValue}
                placeholder={t('template.center.settingsDialog.git.cloneRepo.branchPlaceholder')}
                onChange={(event) => setBranchValue(event.target.value)}
                disabled={isCloningRepository || isPolling}
              />
              <p className="text-xs text-muted-foreground">
                {t('template.center.settingsDialog.git.cloneRepo.branchHelper')}
              </p>
            </div>

            <p className="text-xs text-muted-foreground">
              {repositoryStatus?.canCloneSafely
                ? t('template.center.settingsDialog.git.cloneRepo.helper')
                : t('template.center.settingsDialog.git.repositorySetup.cloneDisabledHelper')}
            </p>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={isInitializingRepository || isCloningRepository || isPolling}
                onClick={() => void onInitRepository()}
              >
                {isInitializingRepository ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('template.center.settingsDialog.git.repositorySetup.actions.initializing')}
                  </>
                ) : (
                  t('template.center.settingsDialog.git.repositorySetup.actions.init')
                )}
              </Button>
              <Button
                type="submit"
                disabled={!isRepoUrlValid || !repositoryStatus?.canCloneSafely || isCloningRepository || isPolling}
              >
                {isPolling ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('template.center.settingsDialog.git.cloneRepo.actions.cloning')}
                  </>
                ) : isCloningRepository ? (
                  t('template.center.settingsDialog.git.cloneRepo.actions.cloning')
                ) : (
                  t('template.center.settingsDialog.git.cloneRepo.actions.clone')
                )}
              </Button>
            </div>

            {/* 進度顯示 */}
            {taskProgress && (
              <div className="border-t pt-4">
                <TaskProgressCard
                  progress={taskProgress}
                  title={t('template.center.settingsDialog.git.cloneRepo.cloneProgressTitle')}
                  onDismiss={resetCloneProgress}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </form>
      ) : (
        <form onSubmit={handleSaveRemoteUrl}>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitPullRequest className="h-5 w-5" />
                {t('template.center.settingsDialog.git.remote.title')}
              </CardTitle>
              <CardDescription>
                {t('template.center.settingsDialog.git.remote.description')}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert className="border-green-200 bg-green-50">
                <CheckCircle2 className="h-4 w-4 text-green-600" />
                <AlertDescription className="text-green-800">
                  <div className="font-medium">
                    {t('template.center.settingsDialog.git.repositorySetup.initializedAlertTitle')}
                  </div>
                  <div className="text-sm mt-1">
                    {t('template.center.settingsDialog.git.cloneRepo.branchStatusLabel')}: {repositoryStatus?.currentBranch || t('template.center.settingsDialog.git.remote.noBranch')}
                  </div>
                </AlertDescription>
              </Alert>
              {!repositoryStatus?.hasOrigin && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    {t('template.center.settingsDialog.git.remote.missingOrigin')}
                  </AlertDescription>
                </Alert>
              )}
              <div className="space-y-2">
                <Label htmlFor="gitRepoUrl">
                  {t('template.center.settingsDialog.git.remote.urlLabel')}
                </Label>
                <Input
                  id="gitRepoUrl"
                  value={repoUrlValue}
                  placeholder={t('template.center.settingsDialog.git.cloneRepo.urlPlaceholder')}
                  onChange={(event) => setRepoUrlValue(event.target.value)}
                  disabled={isSavingRemoteUrl}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {t('template.center.settingsDialog.git.remote.helper')}
              </p>
              <div className="flex justify-end">
                <Button type="submit" disabled={!isRemoteUrlDirty || !isRepoUrlValid || isSavingRemoteUrl}>
                  {isSavingRemoteUrl ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('template.center.settingsDialog.git.remote.actions.saving')}
                    </>
                  ) : (
                    <>
                      <Save className="mr-2 h-4 w-4" />
                      {t('template.center.settingsDialog.git.remote.actions.save')}
                    </>
                  )}
                </Button>
              </div>
            </CardContent>
          </Card>
        </form>
      ))}

      {/* Git 使用者設定 */}
      {showUserConfig && (
      <form onSubmit={handleSubmitUserConfig}>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <GitBranch className="h-5 w-5" />
              {t('template.center.settingsDialog.git.userConfig.title')}
            </CardTitle>
            <CardDescription>
              {t('template.center.settingsDialog.git.userConfig.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="gitUserName">
                {t('template.center.settingsDialog.git.userConfig.userNameLabel')}
              </Label>
              <Input
                id="gitUserName"
                value={formValue.userName}
                placeholder={t('template.center.settingsDialog.git.userConfig.userNamePlaceholder')}
                onChange={(event) => handleChange('userName', event.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="gitUserEmail">
                {t('template.center.settingsDialog.git.userConfig.userEmailLabel')}
              </Label>
              <Input
                id="gitUserEmail"
                type="email"
                value={formValue.userEmail}
                placeholder={t('template.center.settingsDialog.git.userConfig.userEmailPlaceholder')}
                onChange={(event) => handleChange('userEmail', event.target.value)}
              />
            </div>

            <p className="text-xs text-muted-foreground">
              {t('template.center.settingsDialog.git.userConfig.helper')}
            </p>

            <div className="flex justify-end">
              <Button type="submit" disabled={!isUserConfigDirty || !isUserConfigValid || isSaving}>
                {isSaving
                  ? t('template.center.settingsDialog.git.userConfig.actions.saving')
                  : t('template.center.settingsDialog.git.userConfig.actions.save')}
              </Button>
            </div>
          </CardContent>
        </Card>
      </form>
      )}
    </div>
  );
};

export default GitUserConfigTab;
